"""Synthetic end-to-end path for version2.

Drives the real Ingress and Worker HTTP handlers, Gmail sync, PostgreSQL and reply
generation. Gmail API, Gemini and embeddings are in-process fakes. Nothing here reads
Secret Manager, calls Cloud Tasks, Cloud SQL, or the Gmail API.

``synthetic_ms`` is time spent inside this process. It is not a Cloud Run measurement
and does not show that the 120 second latency target is met.

Live web search is not a dependency of ``EmailProcessingService``. The scenarios that
mention it prove the worker neither calls a search provider nor accepts invented web
facts. They do not prove a live search integration.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import time
import wave
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from pathlib import Path
from typing import cast
from uuid import UUID, uuid4

import httpx
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from google.genai import errors, types
from googleapiclient.errors import HttpError
from httplib2 import Response as HttpResponse
from sqlalchemy import create_engine, delete, inspect, select, text
from sqlalchemy.engine import Engine, make_url

from reply_mcfly.adapters.gemini_adapter import (
    AttachmentExtractionResult,
    ExtractedPassage,
    GeminiAdapter,
)
from reply_mcfly.adapters.gmail_adapter import JOB_HEADER, GmailAdapter
from reply_mcfly.adapters.markdown_rag_adapter import MarkdownRAGProvider, _tokens
from reply_mcfly.adapters.pgvector_rag_adapter import PgVectorRAGProvider, ProductCatalogIndex
from reply_mcfly.adapters.postgres_adapter import (
    EMBEDDING_DIMENSIONS,
    EmailJobModel,
    EmailOutboxModel,
    MailboxSyncState,
    PostgresAdapter,
    PostgresEmailRepository,
    make_engine,
)
from reply_mcfly.api.health import create_app
from reply_mcfly.api.workflow import IngressServices, WorkerServices
from reply_mcfly.application.attachment_service import AttachmentService
from reply_mcfly.application.diagnostics import DiagnosticsService
from reply_mcfly.application.email_processing_service import EmailProcessingService
from reply_mcfly.application.gmail_sync_service import GmailSyncService
from reply_mcfly.application.product_catalog import load_catalog
from reply_mcfly.application.rag_query import build_product_question, build_rag_retrieval_query
from reply_mcfly.application.reply_service import FallbackTemplates, ReplyService
from reply_mcfly.domain.email import (
    Evidence,
    IncomingEmail,
    Job,
    OutboxEntry,
    ReplyDraft,
    ResponseType,
    Status,
    WorkflowError,
)
from reply_mcfly.domain.grounding import LiteralReplyValidator
from reply_mcfly.domain.reply_templates import (
    FALLBACK_MISSING_INFORMATION,
    FALLBACK_UNSUPPORTED_ATTACHMENT,
)
from reply_mcfly.domain.sender_policy import parse_sender_policy
from reply_mcfly.ports.capabilities import RAGProvider, SourcePassage

pytestmark = pytest.mark.integration

SENDER = "customer@synthetic.invalid"
AUTH = {"Authorization": "Bearer synthetic-test-identity"}
WEB_URL = "https://synthetic.invalid/kurz"
WEB_FACT = "Aktuální testovací kurz je 24,80 Kč za euro."
PRICE_QUOTE = "- **Testovací cena:** 2 490 Kč včetně DPH."
_EMBEDDING_SYNONYMS = {"stoji": "cena", "kolik": "cena", "hluku": "anc", "potlaceni": "anc"}


class FakeEmbedder:
    """Same token-to-bucket map as the pgvector integration fake. No embedding API."""

    def __init__(self) -> None:
        self.queries: list[str] = []
        self.documents: list[str] = []

    def _vector(self, text_value: str) -> tuple[float, ...]:
        values = [0.0] * EMBEDDING_DIMENSIONS
        for token in _tokens(text_value):
            stem = _EMBEDDING_SYNONYMS.get(token, token)[:5]
            bucket = int.from_bytes(hashlib.sha256(stem.encode()).digest()[:4], "big")
            values[bucket % EMBEDDING_DIMENSIONS] += 1.0
        values[0] += 0.01
        return tuple(values)

    def embed_query(self, text: str, timeout: float) -> tuple[float, ...]:
        self.queries.append(text)
        return self._vector(text)

    def embed_document(self, title: str, text: str, timeout: float) -> tuple[float, ...]:
        self.documents.append(text)
        return self._vector(text)


_LOCAL_DB_HOSTS = frozenset({"postgres", "localhost", "127.0.0.1"})
_BASE = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)


@dataclass(frozen=True)
class ScenarioRow:
    name: str
    result: str
    expected: str
    actual: str
    sent: int
    sources: str
    synthetic_ms: float
    error: str


SCENARIO_ROWS: list[ScenarioRow] = []


def _local_database_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.fail("TEST_DATABASE_URL is required")
    parsed = make_url(url)
    host = (parsed.host or "").casefold()
    rendered = url.casefold()
    if host not in _LOCAL_DB_HOSTS or "cloudsql" in rendered or "googleapis" in rendered:
        pytest.fail("synthetic tests refuse a non-local database host")
    return url


def _http_error(status: int) -> HttpError:
    return HttpError(HttpResponse({"status": str(status)}), b"{}")


def _fact_bytes(prefix: bytes, sentence: str) -> bytes:
    return prefix + f"\nSYNTHETIC-FACT: {sentence}\n".encode()


def _wav_bytes(sentence: str) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(8000)
        handle.writeframes(b"\x00\x00" * 8)
    return _fact_bytes(buffer.getvalue(), sentence)


def _attachment(kind: str) -> tuple[str, str, bytes, str, str]:
    """Filename, MIME, bytes, question, and the sentence the extractor must return."""
    facts = {
        "pdf": (
            "zaruka.pdf",
            "application/pdf",
            _fact_bytes(b"%PDF-1.4\n", "Záruka PDF trvá 24 měsíců."),
            "Jak dlouho trvá záruka podle PDF?",
            "Záruka PDF trvá 24 měsíců.",
        ),
        "mp3": (
            "hlas.mp3",
            "audio/mpeg",
            _fact_bytes(b"ID3\x04", "Záznam MP3 uvádí kód SYN-AUDIO-31."),
            "Jaký kód uvádí záznam MP3?",
            "Záznam MP3 uvádí kód SYN-AUDIO-31.",
        ),
        "wav": (
            "hlas.wav",
            "audio/wav",
            _wav_bytes("Záznam WAV uvádí kód SYN-WAVE-32."),
            "Jaký kód uvádí záznam WAV?",
            "Záznam WAV uvádí kód SYN-WAVE-32.",
        ),
        "jpeg": (
            "foto.jpg",
            "image/jpeg",
            _fact_bytes(b"\xff\xd8\xff\xe0", "Fotografie JPEG ukazuje kód SYN-IMG-33."),
            "Jaký kód ukazuje fotografie JPEG?",
            "Fotografie JPEG ukazuje kód SYN-IMG-33.",
        ),
        "png": (
            "foto.png",
            "image/png",
            _fact_bytes(
                b"\x89PNG\r\n\x1a\n\x00\x00\x00\x0dIHDR",
                "Fotografie PNG ukazuje kód SYN-IMG-34.",
            ),
            "Jaký kód ukazuje fotografie PNG?",
            "Fotografie PNG ukazuje kód SYN-IMG-34.",
        ),
    }
    return facts[kind]


def _write_knowledge(directory: Path) -> None:
    documents = {
        "SYN01_LumenBox.md": """# SYN01 LumenBox

**Témata:** LumenBox, měsíční cena, předplatné

- **Měsíční cena LumenBox:** 249 Kč včetně DPH.
""",
        "SYN02_NimbusCable.md": """# SYN02 NimbusCable

**Témata:** NimbusCable, kabel, délka

- **Délka kabelu NimbusCable:** 1,8 m.
""",
        "SYN03_OrbitStand.md": """# SYN03 OrbitStand

**Témata:** OrbitStand, stojan, výška

- **Výška stojanu OrbitStand:** 120 cm.
""",
    }
    for name, body in documents.items():
        (directory / name).write_text(body, encoding="utf-8")


class SyntheticIdentityVerifier:
    def verify(self, token: str) -> None:
        if token != "synthetic-test-identity":
            raise WorkflowError("UNAUTHORIZED", status=401)


class LocalQueue:
    """Records tasks the handlers enqueue. The test delivers them by HTTP itself."""

    def __init__(self) -> None:
        self.syncs: list[tuple[str, str]] = []
        self.jobs: list[UUID] = []

    def sync(self, mailbox_id: str, event_id: str) -> None:
        self.syncs.append((mailbox_id, event_id))

    def process(self, job_id: UUID) -> None:
        self.jobs.append(job_id)


class _Call:
    def __init__(self, action: Callable[[], object]) -> None:
        self._action = action

    def execute(self, num_retries: int = 0) -> object:
        return self._action()


@dataclass
class StoredMessage:
    message_id: str
    thread_id: str
    internal_date: str
    labels: list[str]
    raw: str


class SyntheticGmailApi:
    """Gmail REST surface used by the real ``GmailAdapter``. No network."""

    def __init__(self, mailbox: str) -> None:
        self.mailbox = mailbox
        self.stored: dict[str, StoredMessage] = {}
        self.thread_order: dict[str, list[str]] = {}
        self.records: list[tuple[str, str]] = []
        self.deleted: set[str] = set()
        self.expired = False
        self.drop_receipt = False
        self.drop_before_store = False
        self.send_calls = 0
        self.profile_history = "100"
        self._next_history = 101

    def close(self) -> None:
        return None

    def users(self) -> SyntheticGmailApi:
        return self

    def getProfile(self, userId: str) -> _Call:
        assert userId == "me"

        def _profile() -> dict[str, str]:
            return {"emailAddress": self.mailbox, "historyId": self.profile_history}

        return _Call(_profile)

    def history(self) -> _History:
        return _History(self)

    def messages(self) -> _Messages:
        return _Messages(self)

    def threads(self) -> _Threads:
        return _Threads(self)

    def add(
        self,
        *,
        message_id: str,
        thread_id: str,
        text: str,
        subject: str,
        minutes: int,
        references: str = "",
        attachment: tuple[str, str, bytes] | None = None,
    ) -> str:
        rfc_id = f"<{message_id}@synthetic.invalid>"
        email = EmailMessage()
        email["From"] = SENDER
        email["To"] = self.mailbox
        email["Subject"] = subject
        email["Message-ID"] = rfc_id
        if references:
            email["References"] = references
        email.set_content(text)
        if attachment is not None:
            filename, mime, data = attachment
            maintype, subtype = mime.split("/", 1)
            email.add_attachment(data, maintype=maintype, subtype=subtype, filename=filename)
        self._remember(
            message_id,
            thread_id,
            email.as_bytes(),
            ["INBOX", "UNREAD"],
            minutes,
            history=True,
        )
        return rfc_id

    def _remember(
        self,
        message_id: str,
        thread_id: str,
        raw_bytes: bytes,
        labels: list[str],
        minutes: int,
        *,
        history: bool,
    ) -> None:
        received = _BASE + timedelta(minutes=minutes)
        self.stored[message_id] = StoredMessage(
            message_id,
            thread_id,
            str(int(received.timestamp() * 1000)),
            labels,
            base64.urlsafe_b64encode(raw_bytes).decode("ascii"),
        )
        self.thread_order.setdefault(thread_id, []).append(message_id)
        if history:
            history_id = str(self._next_history)
            self._next_history += 1
            self.profile_history = history_id
            self.records.append((history_id, message_id))

    def payload(self, message_id: str, mime_format: str) -> dict[str, object]:
        if message_id in self.deleted or message_id not in self.stored:
            raise _http_error(404)
        stored = self.stored[message_id]
        body: dict[str, object] = {
            "id": stored.message_id,
            "threadId": stored.thread_id,
            "internalDate": stored.internal_date,
            "labelIds": stored.labels,
        }
        if mime_format == "raw":
            body["raw"] = stored.raw
        return body


class _History:
    def __init__(self, api: SyntheticGmailApi) -> None:
        self._api = api

    def list(
        self,
        *,
        userId: str,
        startHistoryId: str,
        historyTypes: list[str],
        pageToken: str | None = None,
        maxResults: int = 100,
    ) -> _Call:
        def _list() -> dict[str, object]:
            if self._api.expired:
                raise _http_error(404)
            start = int(startHistoryId)
            records = [
                {"id": history_id, "messagesAdded": [{"message": {"id": message_id}}]}
                for history_id, message_id in self._api.records
                if int(history_id) > start
            ]
            return {"historyId": self._api.profile_history, "history": records}

        return _Call(_list)


class _Messages:
    def __init__(self, api: SyntheticGmailApi) -> None:
        self._api = api

    def get(self, *, userId: str, id: str, format: str) -> _Call:
        return _Call(lambda: self._api.payload(id, format))

    def list(self, *, userId: str, labelIds: list[str], maxResults: int) -> _Call:
        def _list() -> dict[str, object]:
            found = [
                {"id": item.message_id}
                for item in self._api.stored.values()
                if item.message_id not in self._api.deleted and set(labelIds) <= set(item.labels)
            ]
            return {"messages": found[:maxResults]}

        return _Call(_list)

    def send(self, *, userId: str, body: dict[str, str]) -> _Call:
        def _send() -> dict[str, str]:
            self._api.send_calls += 1
            sent_id = f"sent-{self._api.send_calls}"
            if not self._api.drop_before_store:
                padded = body["raw"] + "=" * (-len(body["raw"]) % 4)
                raw = base64.urlsafe_b64decode(padded)
                self._api._remember(
                    sent_id,
                    body["threadId"],
                    raw,
                    ["SENT"],
                    minutes=10_000,
                    history=False,
                )
            if self._api.drop_receipt:
                raise _http_error(500)
            if body["threadId"] not in self._api.thread_order:
                raise _http_error(500)
            return {"id": sent_id, "threadId": body["threadId"]}

        return _Call(_send)


class _Threads:
    def __init__(self, api: SyntheticGmailApi) -> None:
        self._api = api

    def get(self, *, userId: str, id: str, format: str) -> _Call:
        def _get() -> dict[str, object]:
            return {
                "id": id,
                "messages": [
                    {"id": message_id, "labelIds": self._api.stored[message_id].labels}
                    for message_id in self._api.thread_order.get(id, [])
                    if message_id not in self._api.deleted
                ],
            }

        return _Call(_get)


def _line_score(question: str, line: str) -> int:
    score = len(_tokens(question) & _tokens(line))
    if _tokens(question) & {"cena", "stoji", "kolik"} and "cena" in _tokens(line):
        score += 3
    return score


def _best_lines(question: str, source_id: str, text_value: str) -> tuple[str, str] | None:
    best: tuple[int, str] | None = None
    for line in text_value.splitlines():
        stripped = line.strip()
        folded = stripped.casefold()
        if (
            not stripped
            or stripped.endswith("?")
            or stripped.startswith("#")
            or folded.startswith("**témata:")
            or folded.startswith("**temata:")
        ):
            continue
        score = _line_score(question, stripped)
        if score > 0 and (best is None or score > best[0]):
            best = (score, stripped)
    if best is None:
        return None
    return source_id, best[1]


class DeterministicModel:
    """Quotes only lines present in the prompt Gemini actually received."""

    def __init__(self) -> None:
        self.failure: Exception | None = None
        self.fabricate = False
        self.prompts: list[dict[str, object]] = []
        self.generation_calls = 0
        self.extraction_calls = 0

    def respond(self, contents: object) -> types.GenerateContentResponse:
        if self.failure is not None:
            raise self.failure
        if isinstance(contents, list):
            self.extraction_calls += 1
            return self._extraction(contents)
        payload = json.loads(cast(str, contents))
        self.prompts.append(payload)
        self.generation_calls += 1
        draft = self._fabricated() if self.fabricate else self._grounded(payload)
        return types.GenerateContentResponse(
            candidates=[
                types.Candidate(
                    finish_reason=types.FinishReason.STOP,
                    content=types.Content(parts=[types.Part(text=draft.model_dump_json())]),
                )
            ],
            parsed=draft,
        )

    def _extraction(self, contents: list[object]) -> types.GenerateContentResponse:
        passages: list[ExtractedPassage] = []
        pending: str | None = None
        for content in contents:
            for part in getattr(content, "parts", None) or []:
                if getattr(part, "text", None):
                    meta = json.loads(part.text)
                    if "filename" in meta:
                        pending = str(meta["source_id"])
                inline = getattr(part, "inline_data", None)
                if inline is not None and pending is not None:
                    data = inline.data
                    if isinstance(data, str):
                        data = base64.b64decode(data)
                    marker = b"SYNTHETIC-FACT:"
                    start = data.find(marker)
                    if start < 0:
                        raise AssertionError("extractor received attachment bytes without a fact")
                    end = data.find(b"\n", start + len(marker))
                    sentence = data[start + len(marker) : end].decode().strip()
                    passages.append(ExtractedPassage(source_id=pending, extracted_text=sentence))
                    pending = None
        result = AttachmentExtractionResult(passages=passages)
        return types.GenerateContentResponse(
            candidates=[types.Candidate(finish_reason=types.FinishReason.STOP)],
            parsed=result,
        )

    def _grounded(self, payload: dict[str, object]) -> ReplyDraft:
        question = f"{payload['untrusted_subject']}\n{payload['untrusted_email_text']}"
        evidence: list[Evidence] = []
        for bucket, key in (
            ("thread_history", "untrusted_text"),
            ("attachment_passages", "untrusted_text"),
            ("rag_passages", "reference_text"),
        ):
            for item in cast(list[dict[str, str]], payload[bucket]):
                chosen = _best_lines(question, item["source_id"], item[key])
                if chosen is not None:
                    evidence.append(Evidence(source_id=chosen[0], exact_quote=chosen[1]))
        if not evidence:
            email_line = _best_lines(
                question, str(payload["source_id"]), str(payload["untrusted_email_text"])
            )
            if email_line is not None and any(character.isdigit() for character in email_line[1]):
                evidence.append(Evidence(source_id=email_line[0], exact_quote=email_line[1]))
        if not evidence:
            return ReplyDraft(
                response_type="FALLBACK",
                proposed_reply="",
                evidence=[],
                missing_information=["No supplied source answers the question"],
                requires_review=False,
            )
        return ReplyDraft(
            response_type="GENERATED",
            proposed_reply="",
            evidence=evidence[:8],
            missing_information=[],
            requires_review=False,
        )

    def _fabricated(self) -> ReplyDraft:
        return ReplyDraft(
            response_type="GENERATED",
            proposed_reply=WEB_FACT,
            evidence=[Evidence(source_id=f"web:{WEB_URL}", exact_quote=WEB_FACT)],
            missing_information=[],
            requires_review=False,
        )


class SyntheticWebSearch:
    """Stand-in for a provider this worker build does not call."""

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[str] = []

    def search(self, public_query: str) -> tuple[SourcePassage, ...]:
        self.calls.append(public_query)
        if self.fail:
            raise RuntimeError("synthetic web search failed")
        return (
            SourcePassage(
                source_id=f"web:{WEB_URL}",
                source_type="WEB",
                text=WEB_FACT,
                provenance=f"{WEB_URL} published 2026-11-12",
            ),
        )


def _install_model(monkeypatch: pytest.MonkeyPatch, model: DeterministicModel) -> None:
    class _Models:
        def generate_content(
            self, *, model: str, contents: object, config: object
        ) -> types.GenerateContentResponse:
            return deterministic.respond(contents)

    class _Client:
        def __init__(self, **kwargs: object) -> None:
            if kwargs.get("project") != "synthetic-project" or kwargs.get("vertexai") is not True:
                raise AssertionError("synthetic suite refused a non-local Gemini client")

        def __enter__(self) -> _Client:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        models = _Models()

    deterministic = model
    monkeypatch.setattr("reply_mcfly.adapters.gemini_adapter.genai.Client", _Client)


@dataclass
class World:
    engine: Engine
    mailbox: str
    api: SyntheticGmailApi
    model: DeterministicModel
    web: SyntheticWebSearch
    repository: PostgresEmailRepository
    queue: LocalQueue
    ingress: TestClient
    worker: TestClient
    _clients: tuple[TestClient, TestClient]

    def notification(self, history_id: int, message_id: str) -> dict[str, object]:
        if not isinstance(history_id, int):
            raise AssertionError("Pub/Sub historyId must be encoded as a JSON number")
        encoded = base64.b64encode(
            json.dumps({"emailAddress": self.mailbox, "historyId": history_id}).encode()
        ).decode()
        return {"message": {"messageId": message_id, "data": encoded}}

    def notify(self, history_id: int = 250, message_id: str | None = None) -> None:
        response = self.ingress.post(
            "/events/gmail",
            headers=AUTH,
            json=self.notification(history_id, message_id or f"push-{uuid4().hex}"),
        )
        if response.status_code != 204:
            raise AssertionError(response.text)

    def sync(self) -> int:
        discovered = 0
        while self.queue.syncs:
            mailbox_id, _event_id = self.queue.syncs.pop(0)
            response = self.worker.post(
                "/tasks/sync", headers=AUTH, json={"mailbox_id": mailbox_id}
            )
            if response.status_code != 200:
                raise AssertionError(response.text)
            discovered += int(response.json()["discovered"])
        return discovered

    def process_queued(self) -> list[httpx.Response]:
        responses: list[httpx.Response] = []
        while self.queue.jobs:
            responses.append(self.process(self.queue.jobs.pop(0)))
        return responses

    def process(self, job_id: UUID) -> httpx.Response:
        # TestClient is typed against httpx; this image returns the httpx2 drop-in.
        return cast(
            httpx.Response,
            self.worker.post("/tasks/process", headers=AUTH, json={"job_id": str(job_id)}),
        )

    def jobs(self) -> list[Job]:
        with self.engine.connect() as connection:
            identifiers = connection.execute(
                select(EmailJobModel.id)
                .where(EmailJobModel.mailbox_id == self.mailbox)
                .order_by(EmailJobModel.received_at)
            ).scalars()
            copied = list(identifiers)
        return [self.repository.get(identifier) for identifier in copied]

    def error_code(self, job_id: UUID) -> str | None:
        with self.engine.connect() as connection:
            return connection.execute(
                select(EmailJobModel.error_code).where(EmailJobModel.id == job_id)
            ).scalar_one()

    def outbox(self, job_id: UUID) -> OutboxEntry | None:
        return self.repository.outbox(job_id)

    def sent_mime(self, sent_id: str) -> EmailMessage:
        stored = self.api.stored[sent_id]
        return BytesParser(policy=policy.default).parsebytes(base64.urlsafe_b64decode(stored.raw))

    def checkpoint(self) -> str:
        with self.engine.connect() as connection:
            value = connection.execute(
                select(MailboxSyncState.history_id).where(
                    MailboxSyncState.mailbox_id == self.mailbox
                )
            ).scalar_one()
        return str(value)

    def close(self) -> None:
        self.ingress.close()
        self.worker.close()
        with self.engine.begin() as connection:
            identifiers = select(EmailJobModel.id).where(EmailJobModel.mailbox_id == self.mailbox)
            connection.execute(
                delete(EmailOutboxModel).where(EmailOutboxModel.job_id.in_(identifiers))
            )
            connection.execute(
                delete(EmailJobModel).where(EmailJobModel.mailbox_id == self.mailbox)
            )
            connection.execute(
                delete(MailboxSyncState).where(MailboxSyncState.mailbox_id == self.mailbox)
            )
        self.engine.dispose()


@contextmanager
def open_world(
    monkeypatch: pytest.MonkeyPatch,
    knowledge: Path,
    *,
    rag: RAGProvider | None = None,
    query_builder: Callable[[IncomingEmail], str] | None = None,
    rag_timeout: float = 0.0,
    daily_limit: int = 20,
    web_fails: bool = False,
) -> Iterator[World]:
    monkeypatch.setenv("MCFLY_ENABLE_THREAD_HISTORY", "true")
    engine = make_engine(_local_database_url())
    mailbox = f"{uuid4()}@agent.invalid"
    repository = PostgresEmailRepository(engine)
    repository.initialize(mailbox, "100", datetime.now(UTC) + timedelta(days=1))
    api = SyntheticGmailApi(mailbox)
    model = DeterministicModel()
    _install_model(monkeypatch, model)
    queue = LocalQueue()
    gmail = GmailAdapter(lambda: api, mailbox)
    gemini = GeminiAdapter("synthetic-project", "eu", "synthetic-model")
    provider = MarkdownRAGProvider(knowledge) if rag is None else rag
    processing = EmailProcessingService(
        repository,
        gmail,
        gemini,
        mailbox,
        ReplyService(
            parse_sender_policy(frozenset({SENDER}), mailbox),
            FallbackTemplates(),
            LiteralReplyValidator(),
        ),
        AttachmentService(gemini),
        rag=provider,
        enable_rag=True,
        rag_query_builder=query_builder or build_rag_retrieval_query,
        rag_timeout=rag_timeout,
        sender_daily_reply_limit=daily_limit,
    )
    diagnostics = DiagnosticsService(PostgresAdapter(engine))
    verifier = SyntheticIdentityVerifier()
    ingress = TestClient(
        create_app("ingress", diagnostics, IngressServices(mailbox, queue, verifier))
    )
    worker_services = WorkerServices(
        mailbox,
        GmailSyncService(repository, gmail, queue, maintenance=gmail),
        processing,
        verifier,
    )
    worker = TestClient(create_app("worker", diagnostics, worker_services))
    world = World(
        engine,
        mailbox,
        api,
        model,
        SyntheticWebSearch(fail=web_fails),
        repository,
        queue,
        ingress,
        worker,
        (ingress, worker),
    )
    try:
        yield world
    finally:
        world.close()


def _sources(entry: OutboxEntry | None) -> str:
    if entry is None:
        return "none"
    if entry.response_type == ResponseType.FALLBACK:
        reason = entry.fallback_reason.value if entry.fallback_reason else "unknown"
        return f"fallback:{reason}"
    kinds: list[str] = []
    for source_id, _quote in entry.evidence:
        kind = source_id.split(":", 1)[0]
        if kind not in kinds:
            kinds.append(kind)
    return "+".join(kinds) or "none"


def _record(
    name: str,
    *,
    expected: str,
    actual: str,
    sent: int,
    sources: str,
    started: float,
    error: str = "",
    ok: bool,
) -> None:
    row = ScenarioRow(
        name,
        "PASS" if ok else "FAIL",
        expected,
        actual,
        sent,
        sources,
        (time.perf_counter() - started) * 1000,
        error,
    )
    SCENARIO_ROWS.append(row)
    assert ok, f"{name}: expected {expected!r}, actual {actual!r}, error {error!r}"


@pytest.fixture
def knowledge(tmp_path: Path) -> Path:
    _write_knowledge(tmp_path)
    return tmp_path


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch, knowledge: Path) -> Iterator[World]:
    with open_world(monkeypatch, knowledge) as item:
        yield item


@pytest.fixture(autouse=True)
def forbid_cloud_clients(monkeypatch: pytest.MonkeyPatch) -> None:
    def banned(label: str) -> object:
        def _banned(*_args: object, **_kwargs: object) -> None:
            raise AssertionError(f"synthetic suite constructed {label}")

        return _banned

    monkeypatch.setattr(
        "reply_mcfly.adapters.cloud_tasks_adapter.CloudTasksAdapter.__init__",
        banned("CloudTasksAdapter"),
    )
    monkeypatch.setattr(
        "reply_mcfly.adapters.google_clients.GmailServiceFactory.__init__",
        banned("GmailServiceFactory"),
    )
    monkeypatch.setattr(
        "reply_mcfly.adapters.vertex_embedding_adapter.VertexEmbeddingAdapter.__init__",
        banned("VertexEmbeddingAdapter"),
    )


def test_new_email_sends_one_reply(world: World) -> None:
    started = time.perf_counter()
    world.api.add(
        message_id="m-new",
        thread_id="t-new",
        subject="Potvrzení požadavku",
        text="Číslo mého požadavku je SYN-REQ-1001.\nPotvrďte prosím toto číslo?",
        minutes=1,
    )
    world.notify(250)
    assert world.sync() == 1
    response = world.process_queued()[0]
    entry = world.outbox(world.jobs()[0].id)
    ok = (
        response.status_code == 200
        and response.json()["status"] == "SENT"
        and world.api.send_calls == 1
        and entry is not None
        and "SYN-REQ-1001" in entry.draft_body
        and WEB_FACT not in entry.draft_body
    )
    _record(
        "new_email",
        expected="SENT, jedna odpověď cituje číslo z e-mailu",
        actual=f"HTTP {response.status_code} {response.text} sends={world.api.send_calls}",
        sent=world.api.send_calls,
        sources=_sources(entry),
        started=started,
        ok=ok,
    )


def test_thread_history_is_used_for_the_second_message(world: World) -> None:
    started = time.perf_counter()
    world.api.add(
        message_id="m-hist-1",
        thread_id="t-hist",
        subject="Historie",
        text="V předchozí zprávě uvádím číslo SYN-HIST-77.",
        minutes=1,
    )
    world.api.add(
        message_id="m-hist-2",
        thread_id="t-hist",
        subject="Historie",
        text="Jaké číslo jsem uvedl v předchozí zprávě?",
        minutes=2,
        references="<m-hist-1@synthetic.invalid>",
    )
    world.notify(251)
    assert world.sync() == 2
    responses = world.process_queued()
    follow = world.jobs()[1]
    entry = world.outbox(follow.id)
    prompt = world.model.prompts[-1]
    history = cast(list[dict[str, str]], prompt["thread_history"])
    ok = (
        len(responses) == 2
        and all(item.status_code == 200 for item in responses)
        and world.api.send_calls == 2
        and entry is not None
        and "SYN-HIST-77" in entry.draft_body
        and history
        and history[0]["source_id"] == "thread:m-hist-1"
        and "SYN-HIST-77" not in str(prompt["untrusted_email_text"])
    )
    _record(
        "thread_history",
        expected="druhá zpráva cituje SYN-HIST-77 jen z historie vlákna",
        actual=f"sends={world.api.send_calls} history={history!r}",
        sent=world.api.send_calls,
        sources=_sources(entry),
        started=started,
        ok=bool(ok),
    )


def test_same_sender_threads_do_not_share_context(world: World) -> None:
    started = time.perf_counter()
    world.api.add(
        message_id="m-a",
        thread_id="t-a",
        subject="Vlákno A",
        text="Tajný kód vlákna A je CANARY-ALPHA-91.",
        minutes=1,
    )
    world.api.add(
        message_id="m-b",
        thread_id="t-b",
        subject="Vlákno B",
        text="Jaký tajný kód jsem uvedl?",
        minutes=2,
    )
    world.notify(252)
    assert world.sync() == 2
    world.process_queued()
    jobs = world.jobs()
    entry_a = world.outbox(jobs[0].id)
    entry_b = world.outbox(jobs[1].id)
    prompt_b = next(item for item in world.model.prompts if item["untrusted_subject"] == "Vlákno B")
    rendered = json.dumps(prompt_b, ensure_ascii=False)
    ok = (
        entry_a is not None
        and entry_b is not None
        and "CANARY-ALPHA-91" in entry_a.draft_body
        and "CANARY-ALPHA-91" not in entry_b.draft_body
        and "CANARY-ALPHA-91" not in rendered
        and prompt_b["thread_history"] == []
        and entry_b.response_type == ResponseType.FALLBACK
        and jobs[0].gmail_thread_id == "t-a"
        and jobs[1].gmail_thread_id == "t-b"
    )
    _record(
        "thread_isolation",
        expected="vlákno B je fallback a nevidí CANARY-ALPHA-91",
        actual=f"A={_sources(entry_a)} B={_sources(entry_b)} sends={world.api.send_calls}",
        sent=world.api.send_calls,
        sources=f"A:{_sources(entry_a)} B:{_sources(entry_b)}",
        started=started,
        ok=bool(ok),
    )


def test_product_question_uses_rag(world: World) -> None:
    started = time.perf_counter()
    world.api.add(
        message_id="m-rag",
        thread_id="t-rag",
        subject="Cena LumenBox",
        text="Jaká je měsíční cena LumenBox?",
        minutes=1,
    )
    world.notify(253)
    world.sync()
    response = world.process_queued()[0]
    entry = world.outbox(world.jobs()[0].id)
    ok = (
        response.status_code == 200
        and entry is not None
        and "249 Kč" in entry.draft_body
        and any(source.startswith("rag:SYN01_LumenBox") for source, _quote in entry.evidence)
        and "1,8 m" not in entry.draft_body
        and "120 cm" not in entry.draft_body
    )
    _record(
        "rag_product",
        expected="GENERATED cituje 249 Kč z dokumentu LumenBox",
        actual=f"HTTP {response.status_code} body={entry.draft_body if entry else None}",
        sent=world.api.send_calls,
        sources=_sources(entry),
        started=started,
        ok=ok,
    )


def test_unknown_question_does_not_invent_facts(world: World) -> None:
    started = time.perf_counter()
    world.api.add(
        message_id="m-unknown",
        thread_id="t-unknown",
        subject="Kurýr",
        text="Jaké je dnešní přesné ETA kurýra na adrese SYN-UNKNOWN?",
        minutes=1,
    )
    world.notify(254)
    world.sync()
    response = world.process_queued()[0]
    entry = world.outbox(world.jobs()[0].id)
    ok = (
        response.status_code == 200
        and entry is not None
        and entry.draft_body == FALLBACK_MISSING_INFORMATION
        and entry.evidence == ()
        and "SYN-UNKNOWN" not in entry.draft_body
        and world.api.send_calls == 1
    )
    _record(
        "outside_knowledge",
        expected="schválený fallback bez vymyšleného ETA",
        actual=f"type={entry.response_type if entry else None} sends={world.api.send_calls}",
        sent=world.api.send_calls,
        sources=_sources(entry),
        started=started,
        ok=ok,
    )


def test_current_question_does_not_call_web_search(world: World) -> None:
    started = time.perf_counter()
    world.api.add(
        message_id="m-web",
        thread_id="t-web",
        subject="Kurz",
        text="Jaký je aktuální kurz koruny vůči euru?",
        minutes=1,
    )
    world.notify(255)
    world.sync()
    response = world.process_queued()[0]
    entry = world.outbox(world.jobs()[0].id)
    ok = (
        response.status_code == 200
        and entry is not None
        and entry.draft_body == FALLBACK_MISSING_INFORMATION
        and WEB_FACT not in entry.draft_body
        and WEB_URL not in entry.draft_body
        and world.web.calls == []
    )
    _record(
        "web_search_unused",
        expected="fallback, provider se nevolá, kurz 24,80 se neobjeví",
        actual=f"calls={world.web.calls} sends={world.api.send_calls}",
        sent=world.api.send_calls,
        sources=_sources(entry),
        started=started,
        ok=ok,
    )


def test_web_search_failure_cannot_invent_a_result(
    monkeypatch: pytest.MonkeyPatch, knowledge: Path
) -> None:
    started = time.perf_counter()
    with open_world(monkeypatch, knowledge, web_fails=True) as world:
        world.api.add(
            message_id="m-web-down",
            thread_id="t-web-down",
            subject="Kurz",
            text="Jaký je aktuální kurz koruny vůči euru?",
            minutes=1,
        )
        world.notify(256)
        world.sync()
        response = world.process_queued()[0]
        entry = world.outbox(world.jobs()[0].id)
        try:
            if world.web.calls:
                world.web.search(world.web.calls[0])
        except RuntimeError as error:
            raised = str(error)
        else:
            raised = ""
        ok = (
            response.status_code == 200
            and entry is not None
            and entry.draft_body == FALLBACK_MISSING_INFORMATION
            and WEB_URL not in (entry.draft_body)
            and world.web.calls == []
            and raised == ""
        )
        _record(
            "web_search_failure",
            expected="pipeline provider nevolá, žádný vymyšlený výsledek",
            actual=f"calls={len(world.web.calls)} raised={raised!r}",
            sent=world.api.send_calls,
            sources=_sources(entry),
            started=started,
            error=raised,
            ok=ok,
        )


def test_fabricated_web_evidence_is_not_sent(world: World) -> None:
    started = time.perf_counter()
    world.model.fabricate = True
    world.api.add(
        message_id="m-fake-web",
        thread_id="t-fake-web",
        subject="Kurz",
        text="Jaký je aktuální kurz koruny vůči euru?",
        minutes=1,
    )
    world.notify(257)
    world.sync()
    response = world.process_queued()[0]
    job = world.jobs()[0]
    ok = (
        response.status_code == 200
        and response.json()["status"] == "REVIEW_REQUIRED"
        and world.error_code(job.id) == "INVALID_EVIDENCE"
        and world.outbox(job.id) is None
        and world.api.send_calls == 0
    )
    _record(
        "fabricated_web_fact",
        expected="REVIEW_REQUIRED, 0 odeslání, citace webu odmítnuta",
        actual=f"HTTP {response.status_code} {response.text} code={world.error_code(job.id)}",
        sent=world.api.send_calls,
        sources="none",
        started=started,
        ok=ok,
    )


@pytest.mark.parametrize("kind", ["pdf", "mp3", "wav", "jpeg", "png"])
def test_supported_attachment_is_quoted(world: World, kind: str) -> None:
    started = time.perf_counter()
    filename, mime, data, question, sentence = _attachment(kind)
    world.api.add(
        message_id=f"m-{kind}",
        thread_id=f"t-{kind}",
        subject=f"Příloha {kind}",
        text=question,
        minutes=1,
        attachment=(filename, mime, data),
    )
    world.notify(260)
    world.sync()
    response = world.process_queued()[0]
    entry = world.outbox(world.jobs()[0].id)
    ok = (
        response.status_code == 200
        and entry is not None
        and sentence in entry.draft_body
        and any(source.startswith("attachment:") for source, _quote in entry.evidence)
        and world.model.extraction_calls == 1
        and world.api.send_calls == 1
    )
    _record(
        f"attachment_{kind}",
        expected=f"GENERATED cituje větu extrahovanou z {kind}",
        actual=f"HTTP {response.status_code} extract={world.model.extraction_calls}",
        sent=world.api.send_calls,
        sources=_sources(entry),
        started=started,
        ok=ok,
    )


def test_invalid_attachment_is_not_sent(world: World) -> None:
    started = time.perf_counter()
    world.api.add(
        message_id="m-bad-pdf",
        thread_id="t-bad-pdf",
        subject="Špatné PDF",
        text="Prosím zpracujte přílohu.",
        minutes=1,
        attachment=("note.pdf", "application/pdf", b"this-is-not-a-pdf"),
    )
    world.notify(270)
    world.sync()
    response = world.process_queued()[0]
    job = world.jobs()[0]
    ok = (
        response.status_code == 200
        and response.json()["status"] == "REVIEW_REQUIRED"
        and world.error_code(job.id) == "ATTACHMENT_INVALID"
        and world.api.send_calls == 0
        and world.model.generation_calls == 0
        and world.model.extraction_calls == 0
    )
    _record(
        "invalid_attachment",
        expected="REVIEW_REQUIRED ATTACHMENT_INVALID, 0 odeslání, model se nevolá",
        actual=f"{response.text} code={world.error_code(job.id)}",
        sent=world.api.send_calls,
        sources="none",
        started=started,
        ok=ok,
    )


def test_unsupported_attachment_uses_the_approved_template(world: World) -> None:
    started = time.perf_counter()
    world.api.add(
        message_id="m-zip",
        thread_id="t-zip",
        subject="Archiv",
        text="",
        minutes=1,
        attachment=("bundle.zip", "application/zip", b"PK\x03\x04synthetic"),
    )
    world.notify(271)
    world.sync()
    response = world.process_queued()[0]
    entry = world.outbox(world.jobs()[0].id)
    ok = (
        response.status_code == 200
        and entry is not None
        and entry.draft_body == FALLBACK_UNSUPPORTED_ATTACHMENT
        and world.api.send_calls == 1
        and world.model.generation_calls == 0
    )
    _record(
        "unsupported_attachment",
        expected="odeslaný schválený fallback pro nepodporovaný formát",
        actual=f"HTTP {response.status_code} type={entry.response_type if entry else None}",
        sent=world.api.send_calls,
        sources=_sources(entry),
        started=started,
        ok=ok,
    )


def test_duplicate_notification_and_task_send_once(world: World) -> None:
    started = time.perf_counter()
    world.api.add(
        message_id="m-dup",
        thread_id="t-dup",
        subject="Duplicita",
        text="Číslo mého požadavku je SYN-DUP-1.\nPotvrďte to?",
        minutes=1,
    )
    world.notify(280, "push-dup-1")
    world.notify(280, "push-dup-2")
    assert world.sync() == 1
    job_id = world.jobs()[0].id
    queued = list(world.queue.jobs)
    world.queue.jobs.clear()
    assert queued == [job_id]
    first = world.process(job_id)
    # A redelivered Cloud Task for the same job must not send a second reply.
    second = world.process(job_id)
    ok = (
        first.status_code == 200
        and second.status_code == 200
        and first.json()["status"] == "SENT"
        and second.json()["status"] == "SENT"
        and world.api.send_calls == 1
        and world.model.generation_calls == 1
        and len(world.jobs()) == 1
    )
    _record(
        "duplicate_delivery",
        expected="dvě notifikace a dva tasky, právě jedno odeslání",
        actual=f"sends={world.api.send_calls} generations={world.model.generation_calls}",
        sent=world.api.send_calls,
        sources=_sources(world.outbox(world.jobs()[0].id)),
        started=started,
        ok=ok,
    )


def test_expired_history_recovers_without_losing_the_message(world: World) -> None:
    started = time.perf_counter()
    world.api.add(
        message_id="m-expired",
        thread_id="t-expired",
        subject="Obnova",
        text="Číslo mého požadavku je SYN-RECOVER-1.\nPotvrďte to?",
        minutes=1,
    )
    world.api.expired = True
    world.api.profile_history = "5000"
    world.notify(290)
    assert world.sync() == 1
    response = world.process_queued()[0]
    ok = (
        response.status_code == 200
        and response.json()["status"] == "SENT"
        and world.checkpoint() == "5000"
        and world.api.send_calls == 1
    )
    _record(
        "history_expired",
        expected="obnova z nepřečtených, checkpoint 5000, jedno odeslání",
        actual=f"checkpoint={world.checkpoint()} HTTP {response.status_code}",
        sent=world.api.send_calls,
        sources=_sources(world.outbox(world.jobs()[0].id)),
        started=started,
        ok=ok,
    )


def test_deleted_message_does_not_stop_sync(world: World) -> None:
    started = time.perf_counter()
    world.api.add(
        message_id="m-gone",
        thread_id="t-gone",
        subject="Smazáno",
        text="Tento text SYN-DELETED-9 nesmí odejít.",
        minutes=1,
    )
    world.api.add(
        message_id="m-kept",
        thread_id="t-kept",
        subject="Zůstává",
        text="Číslo mého požadavku je SYN-KEPT-2.\nPotvrďte to?",
        minutes=2,
    )
    world.api.deleted.add("m-gone")
    world.notify(291)
    assert world.sync() == 1
    response = world.process_queued()[0]
    entry = world.outbox(world.jobs()[0].id)
    ok = (
        response.status_code == 200
        and len(world.jobs()) == 1
        and world.jobs()[0].gmail_message_id == "m-kept"
        and entry is not None
        and "SYN-DELETED-9" not in entry.draft_body
        and world.api.send_calls == 1
        and world.checkpoint() == "102"
    )
    _record(
        "deleted_message",
        expected="smazaná zpráva se přeskočí, druhá se odešle, checkpoint 102",
        actual=f"jobs={len(world.jobs())} checkpoint={world.checkpoint()}",
        sent=world.api.send_calls,
        sources=_sources(entry),
        started=started,
        ok=ok,
    )


def test_delivery_unknown_reconciles_without_a_second_send(world: World) -> None:
    started = time.perf_counter()
    world.api.drop_receipt = True
    world.api.add(
        message_id="m-unknown-send",
        thread_id="t-unknown-send",
        subject="Doručení",
        text="Číslo mého požadavku je SYN-DELIVERY-1.\nPotvrďte to?",
        minutes=1,
        references="<root@synthetic.invalid>",
    )
    world.notify(292)
    world.sync()
    job = world.jobs()[0]
    first = world.process(job.id)
    world.api.drop_receipt = False
    second = world.process(job.id)
    entry = world.outbox(job.id)
    mime = world.sent_mime("sent-1")
    ok = (
        first.status_code == 503
        and first.json()["error"]["code"] == "DELIVERY_UNKNOWN"
        and second.status_code == 200
        and second.json()["status"] == "SENT"
        and world.api.send_calls == 1
        and str(mime[JOB_HEADER]) == str(job.id)
        and str(mime["In-Reply-To"]) == "<m-unknown-send@synthetic.invalid>"
        and entry is not None
    )
    _record(
        "delivery_unknown_reconciled",
        expected="503 a pak SENT, Gmail send právě jednou, hlavička jobu sedí",
        actual=(
            f"first={first.status_code} second={second.status_code} sends={world.api.send_calls}"
        ),
        sent=world.api.send_calls,
        sources=_sources(entry),
        started=started,
        ok=ok,
    )


def test_delivery_unknown_without_a_stored_reply_needs_review(world: World) -> None:
    started = time.perf_counter()
    world.api.drop_receipt = True
    world.api.drop_before_store = True
    world.api.add(
        message_id="m-lost-send",
        thread_id="t-lost-send",
        subject="Ztráta",
        text="Číslo mého požadavku je SYN-LOST-1.\nPotvrďte to?",
        minutes=1,
    )
    world.notify(293)
    world.sync()
    job = world.jobs()[0]
    first = world.process(job.id)
    second = world.process(job.id)
    ok = (
        first.status_code == 503
        and second.status_code == 200
        and second.json()["status"] == "REVIEW_REQUIRED"
        and world.error_code(job.id) == "DELIVERY_NOT_CONFIRMED"
        and world.api.send_calls == 1
    )
    _record(
        "delivery_unknown_review",
        expected="bez uložené zprávy REVIEW_REQUIRED a žádné druhé odeslání",
        actual=f"second={second.text} sends={world.api.send_calls}",
        sent=world.api.send_calls,
        sources="none",
        started=started,
        ok=ok,
    )


def test_gemini_api_error_is_retryable_without_sending(world: World) -> None:
    started = time.perf_counter()
    world.model.failure = errors.APIError(503, {"message": "synthetic"})
    world.api.add(
        message_id="m-gemini",
        thread_id="t-gemini",
        subject="Model",
        text="Číslo mého požadavku je SYN-GEMINI-1.\nPotvrďte to?",
        minutes=1,
    )
    world.notify(294)
    world.sync()
    job = world.jobs()[0]
    failed = world.process(job.id)
    pending = world.repository.get(job.id).status
    world.model.failure = None
    recovered = world.process(job.id)
    ok = (
        failed.status_code == 503
        and failed.json()["error"]["code"] == "GEMINI_API_ERROR"
        and pending == Status.RETRY_PENDING
        and recovered.status_code == 200
        and recovered.json()["status"] == "SENT"
        and world.api.send_calls == 1
    )
    _record(
        "gemini_api_error",
        expected="503 GEMINI_API_ERROR, pak jedno SENT",
        actual=f"failed={failed.status_code} recovered={recovered.status_code}",
        sent=world.api.send_calls,
        sources=_sources(world.outbox(job.id)),
        started=started,
        error="" if ok else failed.text,
        ok=ok,
    )


def test_gemini_timeout_is_retryable_without_sending(world: World) -> None:
    started = time.perf_counter()
    world.model.failure = httpx.ReadTimeout("synthetic timeout")
    world.api.add(
        message_id="m-timeout",
        thread_id="t-timeout",
        subject="Timeout",
        text="Číslo mého požadavku je SYN-TIMEOUT-1.\nPotvrďte to?",
        minutes=1,
    )
    world.notify(295)
    world.sync()
    job = world.jobs()[0]
    failed = world.process(job.id)
    world.model.failure = None
    recovered = world.process(job.id)
    ok = (
        failed.status_code == 503
        and failed.json()["error"]["code"] == "GEMINI_UNAVAILABLE"
        and recovered.status_code == 200
        and world.api.send_calls == 1
    )
    _record(
        "gemini_timeout",
        expected="503 GEMINI_UNAVAILABLE, retry odešle právě jednou",
        actual=f"failed={failed.json()['error']['code']} sends={world.api.send_calls}",
        sent=world.api.send_calls,
        sources=_sources(world.outbox(job.id)),
        started=started,
        ok=ok,
    )


def test_sender_rate_limit_allows_one_reply(
    monkeypatch: pytest.MonkeyPatch, knowledge: Path
) -> None:
    started = time.perf_counter()
    with open_world(monkeypatch, knowledge, daily_limit=1) as world:
        world.api.add(
            message_id="m-limit-1",
            thread_id="t-limit-1",
            subject="Limit 1",
            text="Číslo mého požadavku je SYN-LIMIT-1.\nPotvrďte to?",
            minutes=1,
        )
        world.api.add(
            message_id="m-limit-2",
            thread_id="t-limit-2",
            subject="Limit 2",
            text="Číslo mého požadavku je SYN-LIMIT-2.\nPotvrďte to?",
            minutes=2,
        )
        world.notify(296)
        assert world.sync() == 2
        first, second = world.process_queued()
        limited = world.jobs()[1]
        ok = (
            first.status_code == 200
            and first.json()["status"] == "SENT"
            and second.status_code == 200
            and second.json()["status"] == "REVIEW_REQUIRED"
            and world.error_code(limited.id) == "SENDER_REPLY_LIMIT_REACHED"
            and world.api.send_calls == 1
        )
        _record(
            "sender_rate_limit",
            expected="první SENT, druhá REVIEW_REQUIRED, jedno odeslání",
            actual=f"second={second.text} code={world.error_code(limited.id)}",
            sent=world.api.send_calls,
            sources="email+limit",
            started=started,
            ok=ok,
        )


def test_history_and_rag_together_do_not_add_web_facts(world: World) -> None:
    started = time.perf_counter()
    world.api.add(
        message_id="m-mix-1",
        thread_id="t-mix",
        subject="LumenBox",
        text="Číslo objednávky je SYN-ORD-55.",
        minutes=1,
    )
    world.api.add(
        message_id="m-mix-2",
        thread_id="t-mix",
        subject="LumenBox",
        text=(
            "Jaké číslo objednávky jsem uvedl a jaká je měsíční cena LumenBox? "
            "Jaký je aktuální kurz koruny vůči euru?"
        ),
        minutes=2,
        references="<m-mix-1@synthetic.invalid>",
    )
    world.notify(297)
    assert world.sync() == 2
    world.process_queued()
    entry = world.outbox(world.jobs()[1].id)
    prompt = world.model.prompts[-1]
    ok = (
        entry is not None
        and "SYN-ORD-55" in entry.draft_body
        and "249 Kč" in entry.draft_body
        and WEB_FACT not in entry.draft_body
        and WEB_URL not in entry.draft_body
        and world.web.calls == []
        and {item["source_id"] for item in cast(list[dict[str, str]], prompt["thread_history"])}
        == {"thread:m-mix-1"}
        and any(source.startswith("rag:") for source, _quote in entry.evidence)
        and any(source.startswith("thread:") for source, _quote in entry.evidence)
    )
    _record(
        "history_rag_without_web",
        expected="citace historie a RAG, web search ani kurz 24,80 nejsou v odpovědi",
        actual=f"sources={_sources(entry)} web_calls={len(world.web.calls)}",
        sent=world.api.send_calls,
        sources=_sources(entry),
        started=started,
        ok=bool(ok),
    )


def test_reply_uses_thread_id_and_rfc_headers(world: World) -> None:
    started = time.perf_counter()
    envelope = world.notification(298, "push-headers")
    message = cast(dict[str, object], envelope["message"])
    decoded = json.loads(base64.b64decode(cast(str, message["data"])))
    world.api.add(
        message_id="m-headers",
        thread_id="t-headers",
        subject="Hlavičky",
        text="Číslo mého požadavku je SYN-HEADER-1.\nPotvrďte to?",
        minutes=1,
        references="<root@synthetic.invalid>",
    )
    response = world.ingress.post("/events/gmail", headers=AUTH, json=envelope)
    assert response.status_code == 204
    world.sync()
    processed = world.process_queued()[0]
    job = world.jobs()[0]
    mime = world.sent_mime("sent-1")
    send_was_numeric = isinstance(decoded["historyId"], int) or decoded["historyId"] == "298"
    ok = (
        send_was_numeric
        and decoded["historyId"] in {298, "298"}
        and processed.status_code == 200
        and job.gmail_thread_id == "t-headers"
        and str(mime["In-Reply-To"]) == "<m-headers@synthetic.invalid>"
        and str(mime["References"]) == "<root@synthetic.invalid> <m-headers@synthetic.invalid>"
        and str(mime["To"]) == SENDER
        and world.api.thread_order["t-headers"][-1] == "sent-1"
    )
    _record(
        "reply_headers",
        expected="číselné historyId, threadId t-headers, In-Reply-To a References",
        actual=(
            f"historyId={decoded['historyId']!r} in_reply_to={mime['In-Reply-To']!r} "
            f"references={mime['References']!r}"
        ),
        sent=world.api.send_calls,
        sources=_sources(world.outbox(job.id)),
        started=started,
        ok=ok,
    )


def test_pgvector_product_question_uses_fake_embeddings(
    monkeypatch: pytest.MonkeyPatch, knowledge: Path
) -> None:
    started = time.perf_counter()
    schema = f"synthetic_rag_{uuid4().hex[:12]}"
    admin = make_engine(_local_database_url())
    with admin.begin() as connection:
        connection.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        connection.execute(text(f"CREATE SCHEMA {schema}"))
        connection.execute(
            text(
                f"CREATE TABLE {schema}.rag_product_chunks "
                "(LIKE public.rag_product_chunks INCLUDING ALL)"
            )
        )
    admin.dispose()
    vector_engine = create_engine(
        _local_database_url(),
        connect_args={
            "options": f"-c statement_timeout=3000 -c search_path={schema},public",
        },
    )
    embedder = FakeEmbedder()
    index = ProductCatalogIndex(vector_engine, "synthetic-embedding")
    index.apply(load_catalog(), embedder)
    provider = PgVectorRAGProvider(
        vector_engine, embedder, embedding_model="synthetic-embedding", timeout=10
    )
    try:
        with open_world(
            monkeypatch,
            knowledge,
            rag=provider,
            query_builder=build_product_question,
            rag_timeout=10,
        ) as world:
            world.api.add(
                message_id="m-vector",
                thread_id="t-vector",
                subject="Kolik stojí AirDock 8?",
                text="Kolik stojí AirDock 8?",
                minutes=1,
            )
            world.notify(299)
            world.sync()
            response = world.process_queued()[0]
            entry = world.outbox(world.jobs()[0].id)
            ok = (
                response.status_code == 200
                and entry is not None
                and PRICE_QUOTE in entry.draft_body
                and len(embedder.queries) == 1
                and len(embedder.documents) == 18
            )
            _record(
                "pgvector_rag",
                expected="GENERATED cituje testovací cenu AirDock z pgvector a fake embeddings",
                actual=(
                    f"HTTP {response.status_code} queries={len(embedder.queries)} "
                    f"docs={len(embedder.documents)} "
                    f"body={getattr(entry, 'draft_body', None)}"
                ),
                sent=world.api.send_calls,
                sources=_sources(entry),
                started=started,
                ok=ok,
            )
    finally:
        vector_engine.dispose()
        admin = make_engine(_local_database_url())
        with admin.begin() as connection:
            connection.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        admin.dispose()


def test_migrations_0003_0004_0005_on_a_separate_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started = time.perf_counter()
    name = f"synthetic_mig_{uuid4().hex[:12]}"
    # CREATE DATABASE cannot run inside a transaction.
    autocommit = create_engine(_local_database_url(), isolation_level="AUTOCOMMIT")
    probe: Engine | None = None
    error = ""
    ok = False
    actual = ""
    try:
        with autocommit.connect() as connection:
            connection.execute(text(f"CREATE DATABASE {name}"))
        migrated = make_url(_local_database_url()).set(database=name)
        if migrated.database in {None, "mcfly"}:
            pytest.fail("migration probe must not target the application database")
        monkeypatch.setenv("MCFLY_DATABASE_URL", migrated.render_as_string(hide_password=False))
        config = Config("alembic.ini")
        probe = make_engine(migrated.render_as_string(hide_password=False))
        command.upgrade(config, "0003")
        columns_0003 = _columns(probe, "email_outbox")
        tables_0003 = set(inspect(probe).get_table_names())
        command.upgrade(config, "0004")
        tables_0004 = set(inspect(probe).get_table_names())
        vector_type = _vector_type(probe)
        command.upgrade(config, "0005")
        columns_0005 = _columns(probe, "email_outbox")
        ok = (
            "evidence" in columns_0003
            and "attachment_passages" not in columns_0003
            and "rag_product_chunks" not in tables_0003
            and "rag_product_chunks" in tables_0004
            and vector_type == "vector(768)"
            and "attachment_passages" in columns_0005
        )
        actual = (
            f"0003 evidence={('evidence' in columns_0003)} "
            f"0004 vector={vector_type} 0005 passages={'attachment_passages' in columns_0005}"
        )
    except Exception as exc:  # noqa: BLE001 - the scenario row must keep the failure
        error = f"{type(exc).__name__}: {exc}"
        actual = error
    finally:
        if probe is not None:
            probe.dispose()
        with autocommit.connect() as connection:
            connection.execute(text(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)"))
        autocommit.dispose()
    _record(
        "migrations_0003_0004_0005",
        expected="0003 evidence, 0004 vector(768), 0005 attachment_passages na samostatné DB",
        actual=actual,
        sent=0,
        sources="schema",
        started=started,
        error=error,
        ok=ok,
    )


def _columns(engine: Engine, table: str) -> set[str]:
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = :table"
            ),
            {"table": table},
        ).scalars()
        return set(rows)


def _vector_type(engine: Engine) -> str:
    with engine.connect() as connection:
        value = connection.execute(
            text(
                "SELECT format_type(atttypid, atttypmod) FROM pg_attribute "
                "WHERE attrelid = 'public.rag_product_chunks'::regclass AND attname = 'embedding'"
            )
        ).scalar_one()
    return str(value)
