"""Local live-email E2E runner — no Pub/Sub or Cloud Tasks."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from reply_mcfly.adapters.gemini_adapter import GeminiAdapter
from reply_mcfly.adapters.gmail_adapter import GmailAdapter
from reply_mcfly.adapters.google_clients import (
    GmailOAuthFileFactory,
    assert_private_credentials_file,
)
from reply_mcfly.adapters.markdown_rag_adapter import MarkdownRAGProvider
from reply_mcfly.adapters.postgres_adapter import PostgresEmailRepository, make_engine
from reply_mcfly.application.attachment_service import AttachmentService
from reply_mcfly.application.email_processing_service import EmailProcessingService
from reply_mcfly.application.live_email_runner import LiveEmailRunner, validate_live_email_settings
from reply_mcfly.application.reply_service import FallbackTemplates, ReplyService
from reply_mcfly.config.settings import Settings
from reply_mcfly.domain.email import Status, WorkflowError
from reply_mcfly.domain.grounding import LiteralReplyValidator

DEFAULT_CREDENTIALS = Path.home() / ".config/reply-mcfly/gmail-token.json"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Process one Gmail message locally through Reply McFly (default: dry-run, no send)"
        )
    )
    parser.add_argument(
        "--message-id",
        required=True,
        help="Gmail API message id to process (no automatic discovery)",
    )
    parser.add_argument(
        "--send",
        action="store_true",
        help="Send the reply after validation (default is dry-run without Gmail send)",
    )
    parser.add_argument(
        "--gmail-credentials",
        type=Path,
        default=DEFAULT_CREDENTIALS,
        help="OAuth authorized-user JSON (mode 0600, outside the repository)",
    )
    args = parser.parse_args()
    settings = Settings()
    try:
        allowed = validate_live_email_settings(settings.mailbox_id, settings.allowed_senders)
        database_url = settings.sqlalchemy_url()
        credentials_path = assert_private_credentials_file(args.gmail_credentials)
    except (RuntimeError, ValueError, WorkflowError) as error:
        print(json.dumps({"error": str(error)}), file=sys.stderr)
        return 2
    engine = make_engine(database_url)
    try:
        repository = PostgresEmailRepository(engine)
        mailbox = settings.mailbox_id.casefold()
        gmail = GmailAdapter(GmailOAuthFileFactory(credentials_path), mailbox)
        gemini = GeminiAdapter(
            settings.gcp_project_id, settings.vertex_ai_location, settings.gemini_model
        )
        rag = MarkdownRAGProvider() if settings.enable_rag else None
        replies = ReplyService(allowed, FallbackTemplates(), LiteralReplyValidator())
        processing = EmailProcessingService(
            repository,
            gmail,
            gemini,
            mailbox,
            replies,
            AttachmentService(gemini),
            rag=rag,
            enable_rag=settings.enable_rag,
        )
        live = LiveEmailRunner(repository, gmail, processing, mailbox)
        result = live.run(args.message_id, send_enabled=args.send)
    except WorkflowError as error:
        print(
            json.dumps(
                {
                    "error": error.code,
                    "retryable": error.retryable,
                    "send_enabled": args.send,
                }
            ),
            file=sys.stderr,
        )
        return 1
    finally:
        engine.dispose()
    summary = {
        "job_id": str(result.job_id),
        "gmail_message_id": result.gmail_message_id,
        "gmail_thread_id": result.gmail_thread_id,
        "status": result.status.value,
        "send_enabled": result.send_enabled,
        "duration_seconds": round(result.duration_seconds, 3),
    }
    print(json.dumps(summary))
    if result.status in {Status.SENT, Status.READY_TO_SEND}:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
