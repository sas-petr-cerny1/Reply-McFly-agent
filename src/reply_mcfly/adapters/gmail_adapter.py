from __future__ import annotations

import base64
import binascii
import os
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime
from email import policy
from email.message import EmailMessage, MIMEPart
from email.parser import BytesParser
from email.utils import getaddresses
from html.parser import HTMLParser
from http.client import HTTPException
from typing import Any

from google.auth.exceptions import GoogleAuthError
from googleapiclient.errors import HttpError
from httplib2 import HttpLib2Error
from pydantic import BaseModel, Field, ValidationError

from reply_mcfly.domain.email import (
    EmailAttachment,
    IncomingEmail,
    Job,
    MessageMetadata,
    OutboxEntry,
    ThreadHistoryPassage,
    WorkflowError,
    require_mailbox,
)
from reply_mcfly.ports.email import HistoryPage


class GmailMessagePayload(BaseModel):
    id: str = Field(min_length=1, max_length=255)
    threadId: str = Field(min_length=1, max_length=255)
    internalDate: str = Field(pattern=r"^\d+$")
    labelIds: list[str] = Field(default_factory=list)
    raw: str | None = None

    def metadata(self) -> MessageMetadata:
        return MessageMetadata(
            self.id,
            self.threadId,
            datetime.fromtimestamp(int(self.internalDate) / 1000, UTC),
            frozenset(self.labelIds),
        )


class AddedMessage(BaseModel):
    message: GmailMessageId


class GmailMessageId(BaseModel):
    id: str = Field(min_length=1, max_length=255)


AddedMessage.model_rebuild()


class HistoryRecord(BaseModel):
    messagesAdded: list[AddedMessage] = Field(default_factory=list)


class HistoryPayload(BaseModel):
    historyId: str = Field(pattern=r"^\d+$")
    history: list[HistoryRecord] = Field(default_factory=list)
    nextPageToken: str | None = None


class WatchPayload(BaseModel):
    historyId: str = Field(pattern=r"^\d+$", max_length=32)
    expiration: str = Field(pattern=r"^\d+$", max_length=16)


class _ReadableHTML(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hidden = 0
        self.text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self.hidden += 1
        elif tag in {"p", "br", "div", "li"}:
            self.text.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            self.text.append(data)


# Gmail RAW contains the full RFC 2822 MIME message encoded in base64url.
# MIME attachments are usually base64-encoded inside that message as well.
# Keep bounded limits at both encoding layers; attachment validation remains separate.
MAX_GMAIL_RAW_CHARS = 16 * 1024 * 1024
MAX_GMAIL_DECODED_BYTES = 12 * 1024 * 1024
# One page keeps recovery inside a single sync deadline; older unread mail needs an operator.
RECOVERY_MESSAGE_LIMIT = 100


def decode_mime(payload: GmailMessagePayload) -> EmailMessage:
    if payload.raw is None or len(payload.raw) > MAX_GMAIL_RAW_CHARS:
        raise WorkflowError("EMAIL_TOO_LARGE_OR_MISSING")
    try:
        data = base64.b64decode(
            payload.raw + "=" * (-len(payload.raw) % 4), altchars=b"-_", validate=True
        )
        if len(data) > MAX_GMAIL_DECODED_BYTES:
            raise WorkflowError("EMAIL_TOO_LARGE_OR_MISSING")
        message = BytesParser(policy=policy.default).parsebytes(data)
    except (ValueError, binascii.Error):
        raise WorkflowError("INVALID_EMAIL") from None
    if not isinstance(message, EmailMessage) or any(part.defects for part in message.walk()):
        raise WorkflowError("INVALID_EMAIL")
    return message


def single_address(message: EmailMessage, name: str) -> str:
    headers = message.get_all(name, [])
    if len(headers) != 1:
        raise WorkflowError("AMBIGUOUS_EMAIL_ADDRESS")
    addresses = getaddresses([str(headers[0])])
    if len(addresses) != 1 or not addresses[0][1] or "@" not in addresses[0][1]:
        raise WorkflowError("AMBIGUOUS_EMAIL_ADDRESS")
    return addresses[0][1].casefold()


def _body_text(body: MIMEPart[Any, Any] | None) -> str:
    if body is None:
        return ""
    try:
        content = body.get_content()
    except (LookupError, UnicodeError, ValueError):
        raise WorkflowError("UNREADABLE_EMAIL_BODY") from None
    if not isinstance(content, str) or len(content) > 100_000:
        raise WorkflowError("INVALID_EMAIL_BODY")
    return content


def parse_message(payload: GmailMessagePayload) -> IncomingEmail:
    message = decode_mime(payload)
    sender = single_address(message, "From")
    for name in ("Subject", "Message-ID", "References", "Auto-Submitted", "Precedence"):
        if len(message.get_all(name, [])) > 1:
            raise WorkflowError("AMBIGUOUS_EMAIL_HEADERS")
    body = message.get_body(preferencelist=("plain", "html"))
    content = _body_text(body)
    if body and body.get_content_type() == "text/html":
        parser = _ReadableHTML()
        parser.feed(content)
        content = "".join(parser.text)
    suppress = str(message.get("X-Auto-Response-Suppress", "")).casefold()
    automatic = (
        str(message.get("Auto-Submitted", "no")).casefold() != "no"
        or str(message.get("Precedence", "")).casefold() in {"bulk", "list", "junk"}
        or message.get("List-ID") is not None
        or str(message.get("Return-Path", "")) == "<>"
        or sender.split("@")[0] in {"noreply", "no-reply", "mailer-daemon", "postmaster"}
        or suppress in {"all", "dr", "autoreply", "oof"}
    )
    attachment_parts = [
        part
        for part in message.walk()
        if part.get_filename()
        or part.get_content_disposition() == "attachment"
        or (not part.is_multipart() and part.get_content_type() not in {"text/plain", "text/html"})
    ]
    supported = {
        "application/pdf",
        "audio/mpeg",
        "audio/wav",
        "audio/x-wav",
        "image/jpeg",
        "image/png",
    }
    decoded: list[EmailAttachment] = []
    for index, part in enumerate(attachment_parts):
        try:
            part_bytes = part.get_payload(decode=True)
        except (TypeError, ValueError):
            raise WorkflowError("INVALID_ATTACHMENT") from None
        if not isinstance(part_bytes, bytes) or len(part_bytes) > 10 * 1024 * 1024:
            raise WorkflowError("ATTACHMENT_LIMIT_EXCEEDED")
        filename = str(part.get_filename() or f"attachment-{index + 1}")
        decoded.append(
            EmailAttachment(
                f"attachment:{index}",
                filename[:255],
                str(part.get_content_type()).casefold(),
                part_bytes,
            )
        )
    return IncomingEmail(
        payload.metadata(),
        sender,
        str(message.get("Subject", "")),
        str(message.get("Message-ID", "")),
        str(message.get("References", "")),
        content.strip(),
        automatic,
        bool(attachment_parts),
        any(part.get_content_type().casefold() not in supported for part in attachment_parts),
        tuple(decoded),
    )


def encode_reply(job: Job, entry: OutboxEntry) -> str:
    message = EmailMessage()
    message["From"] = job.mailbox_id
    message["To"] = entry.recipient
    message["Subject"] = entry.subject
    message["Message-ID"] = entry.outbound_message_id
    message["In-Reply-To"] = entry.in_reply_to
    message["References"] = entry.references
    message["Auto-Submitted"] = "auto-replied"
    message["X-Auto-Response-Suppress"] = "All"
    message.set_content(entry.draft_body)
    return base64.urlsafe_b64encode(message.as_bytes(policy=policy.SMTP)).decode("ascii")


class GmailAdapter:
    def __init__(self, service_factory: Callable[[], Any], mailbox_id: str) -> None:
        self.service_factory, self.mailbox_id = service_factory, mailbox_id
        self.enable_thread_history = os.environ.get(
            "MCFLY_ENABLE_THREAD_HISTORY", "false"
        ).casefold() in {"true", "1", "yes"}

    @contextmanager
    def _service(self) -> Iterator[Any]:
        service = self.service_factory()
        try:
            profile = self._execute(service.users().getProfile(userId="me"))
            if not isinstance(profile, dict) or not isinstance(profile.get("emailAddress"), str):
                raise WorkflowError("INVALID_GMAIL_PROFILE")
            require_mailbox(profile["emailAddress"], self.mailbox_id)
            yield service
        finally:
            service.close()

    def _execute(self, request: Any) -> Any:
        try:
            return request.execute(num_retries=0)
        except HttpError as error:
            status = int(error.resp.status)
            if status == 404:
                raise WorkflowError("GMAIL_RESOURCE_NOT_FOUND") from None
            raise WorkflowError(
                "GMAIL_API_ERROR", retryable=status in {408, 429} or status >= 500, status=503
            ) from None
        except (OSError, HttpLib2Error, GoogleAuthError, HTTPException):
            raise WorkflowError("GMAIL_API_ERROR", retryable=True, status=503) from None
        except ValueError:
            raise WorkflowError("INVALID_GMAIL_RESPONSE", status=503) from None

    def history(self, start: str) -> Iterator[HistoryPage]:
        deadline = time.monotonic() + 90
        with self._service() as service:
            token = None
            for _ in range(100):
                if time.monotonic() + 10 > deadline:
                    raise WorkflowError("DEPENDENCY_TIMEOUT", retryable=True, status=503)
                try:
                    result = self._execute(
                        service.users()
                        .history()
                        .list(
                            userId="me",
                            startHistoryId=start,
                            historyTypes=["messageAdded"],
                            pageToken=token,
                            maxResults=100,
                        )
                    )
                except WorkflowError as error:
                    if error.code == "GMAIL_RESOURCE_NOT_FOUND":
                        raise WorkflowError("HISTORY_EXPIRED", status=503) from None
                    raise
                try:
                    page = HistoryPayload.model_validate(result)
                except ValidationError:
                    raise WorkflowError("INVALID_GMAIL_HISTORY", status=503) from None
                yield HistoryPage(
                    tuple(
                        dict.fromkeys(
                            item.message.id
                            for record in page.history
                            for item in record.messagesAdded
                        )
                    ),
                    page.historyId,
                )
                token = page.nextPageToken
                if not token:
                    return
            raise WorkflowError("HISTORY_PAGE_LIMIT", retryable=True, status=503)

    def profile_history(self) -> str:
        with self._service() as service:
            result = self._execute(service.users().getProfile(userId="me"))
            if not isinstance(result, dict):
                raise WorkflowError("INVALID_GMAIL_PROFILE")
            history = result.get("historyId")
            if not isinstance(history, str) or not history.isdecimal():
                raise WorkflowError("INVALID_GMAIL_PROFILE")
            return history

    def watch(self, topic: str) -> WatchPayload:
        with self._service() as service:
            try:
                return WatchPayload.model_validate(
                    self._execute(
                        service.users().watch(
                            userId="me",
                            body={
                                "topicName": topic,
                                "labelIds": ["INBOX"],
                                "labelFilterBehavior": "include",
                            },
                        )
                    )
                )
            except ValidationError:
                raise WorkflowError("INVALID_GMAIL_WATCH") from None

    def renew_watch(self, topic: str) -> datetime:
        return datetime.fromtimestamp(int(self.watch(topic).expiration) / 1000, UTC)

    def unread_inbox(self) -> tuple[str, ...]:
        """Newest unread inbox messages; the recovery listing after an expired history id."""
        with self._service() as service:
            result = self._execute(
                service.users()
                .messages()
                .list(userId="me", labelIds=["INBOX", "UNREAD"], maxResults=RECOVERY_MESSAGE_LIMIT)
            )
            if not isinstance(result, dict) or not isinstance(result.get("messages", []), list):
                raise WorkflowError("INVALID_GMAIL_RESPONSE", status=503)
            try:
                return tuple(
                    dict.fromkeys(
                        GmailMessageId.model_validate(item).id
                        for item in result.get("messages", [])
                    )
                )
            except ValidationError:
                raise WorkflowError("INVALID_GMAIL_RESPONSE", status=503) from None

    def _get(self, message_id: str, format: str) -> GmailMessagePayload:
        with self._service() as service:
            try:
                result = GmailMessagePayload.model_validate(
                    self._execute(
                        service.users().messages().get(userId="me", id=message_id, format=format)
                    )
                )
            except ValidationError:
                raise WorkflowError("INVALID_GMAIL_MESSAGE") from None
        if result.id != message_id:
            raise WorkflowError("GMAIL_MESSAGE_MISMATCH")
        return result

    def metadata(self, message_id: str) -> MessageMetadata:
        return self._get(message_id, "metadata").metadata()

    def message(self, message_id: str) -> IncomingEmail:
        current = parse_message(self._get(message_id, "raw"))
        if not self.enable_thread_history:
            return current
        return replace(current, thread_history=self._thread_history(current))

    def _thread_history(self, current: IncomingEmail) -> tuple[ThreadHistoryPassage, ...]:
        """At most 3 earlier messages in this exact Gmail thread; no cross-thread data."""
        with self._service() as service:
            thread = self._execute(
                service.users()
                .threads()
                .get(userId="me", id=current.metadata.thread_id, format="minimal")
            )
            if not isinstance(thread, dict) or thread.get("id") != current.metadata.thread_id:
                raise WorkflowError("THREAD_CONTEXT_MISMATCH")
            items = thread.get("messages", [])
            if not isinstance(items, list) or len(items) > 40:
                raise WorkflowError("THREAD_CONTEXT_LIMIT")
            ids = [item.get("id") for item in items if isinstance(item, dict)]
            if current.metadata.message_id not in ids:
                raise WorkflowError("THREAD_CONTEXT_MISMATCH")
            before = ids[: ids.index(current.metadata.message_id)]
            selected: list[ThreadHistoryPassage] = []
            for previous_id in reversed(before[-8:]):
                if len(selected) == 3:
                    break
                if not isinstance(previous_id, str) or not previous_id:
                    continue
                result = self._execute(
                    service.users().messages().get(userId="me", id=previous_id, format="raw")
                )
                try:
                    payload = GmailMessagePayload.model_validate(result)
                except ValidationError:
                    raise WorkflowError("INVALID_THREAD_MESSAGE") from None
                if payload.id != previous_id or payload.threadId != current.metadata.thread_id:
                    raise WorkflowError("THREAD_CONTEXT_MISMATCH")
                previous = parse_message(payload)
                if (
                    previous.metadata.received_at >= current.metadata.received_at
                    or previous.sender not in {current.sender, self.mailbox_id.casefold()}
                    or previous.automatic
                    and previous.sender != self.mailbox_id.casefold()
                    or not previous.text.strip()
                    or previous.has_attachments
                ):
                    continue
                selected.append(
                    ThreadHistoryPassage(
                        source_id=f"thread:{previous_id}",
                        sender=previous.sender,
                        text=previous.text[:1200],
                    )
                )
            return tuple(reversed(selected))

    def send(self, job: Job, entry: OutboxEntry) -> str:
        with self._service() as service:
            result = self._execute(
                service.users()
                .messages()
                .send(
                    userId="me",
                    body={"raw": encode_reply(job, entry), "threadId": job.gmail_thread_id},
                )
            )
        if not isinstance(result, dict):
            raise WorkflowError("INVALID_GMAIL_RECEIPT")
        sent_id = result.get("id")
        if (
            not isinstance(sent_id, str)
            or not sent_id
            or result.get("threadId") != job.gmail_thread_id
        ):
            raise WorkflowError("INVALID_GMAIL_RECEIPT")
        return sent_id

    def find_sent(self, job: Job, entry: OutboxEntry) -> str | None:
        with self._service() as service:
            result = self._execute(
                service.users()
                .messages()
                .list(
                    userId="me", q=f"in:sent rfc822msgid:{entry.outbound_message_id}", maxResults=10
                )
            )
            if not isinstance(result, dict) or result.get("nextPageToken"):
                raise WorkflowError("AMBIGUOUS_SENT_RESULT")
            candidates = result.get("messages", [])
            if not isinstance(candidates, list):
                raise WorkflowError("INVALID_GMAIL_RESPONSE")
            matches: list[str] = []
            for candidate in candidates:
                identifier = GmailMessageId.model_validate(candidate).id
                payload = self._get(identifier, "raw")
                message = decode_mime(payload)
                body = message.get_body(preferencelist=("plain",))
                text = _body_text(body)
                if (
                    payload.threadId == job.gmail_thread_id
                    and "SENT" in payload.labelIds
                    and str(message.get("Message-ID")) == entry.outbound_message_id
                    and single_address(message, "From") == job.mailbox_id.casefold()
                    and single_address(message, "To") == entry.recipient.casefold()
                    and str(message.get("In-Reply-To")) == entry.in_reply_to
                    and str(message.get("Subject", "")) == entry.subject
                    and isinstance(text, str)
                    and text.strip() == entry.draft_body.strip()
                ):
                    matches.append(identifier)
            if len(matches) > 1:
                raise WorkflowError("AMBIGUOUS_SENT_RESULT")
            return matches[0] if matches else None
