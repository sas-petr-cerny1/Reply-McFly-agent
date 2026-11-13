#!/usr/bin/env bash
# Local end-to-end run of one real Gmail message through the Worker pipeline in Docker.
#
#   scripts/local_e2e.sh up                          build, start, migrate, offline preflight
#   scripts/local_e2e.sh run --subject "My subject"  dry run: prepare the reply, send nothing
#   scripts/local_e2e.sh run --subject "My subject" --send   really send the reply
#   scripts/local_e2e.sh show JOB_ID                 job state and the stored reply
#   scripts/local_e2e.sh down                        stop the stack (data volume is kept)
#
# Uses the local PostgreSQL container only. "run" calls Gmail (read; send only with --send)
# and Vertex AI Gemini with your own credentials from ~/.config; nothing is copied or printed.
set -euo pipefail
cd "$(dirname "$0")/.."

AUTH_DIR="${HOME}/.config/reply-mcfly"
ADC_DIR="${HOME}/.config/gcloud"
# Local defaults; override by exporting the variable before calling the script.
export MCFLY_ENABLE_RAG="${MCFLY_ENABLE_RAG:-true}"
export MCFLY_RAG_BACKEND="${MCFLY_RAG_BACKEND:-markdown}"
export MCFLY_ENABLE_THREAD_HISTORY="${MCFLY_ENABLE_THREAD_HISTORY:-true}"

worker() {
  docker compose run --rm --no-deps -T \
    -v "${AUTH_DIR}:/home/app/.config/reply-mcfly:ro" \
    -v "${ADC_DIR}:/home/app/.config/gcloud:ro" \
    -e GOOGLE_APPLICATION_CREDENTIALS=/home/app/.config/gcloud/application_default_credentials.json \
    worker "$@"
}

require_credentials() {
  for file in "${AUTH_DIR}/gmail-token.json" "${ADC_DIR}/application_default_credentials.json"; do
    [ -f "${file}" ] || { echo "Missing ${file}" >&2; exit 2; }
  done
}

cmd_up() {
  require_credentials
  docker compose build ingress
  # Ingress applies migrations on start; the worker image is the same build.
  docker compose up -d --wait postgres ingress
  worker python - <<'PY'
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text

from reply_mcfly.adapters.google_clients import assert_private_credentials_file
from reply_mcfly.adapters.postgres_adapter import make_engine
from reply_mcfly.adapters.rag_factory import build_rag
from reply_mcfly.application.live_email_runner import validate_live_email_settings
from reply_mcfly.config.settings import Settings

settings = Settings()
validate_live_email_settings(settings.mailbox_id, settings.allowed_senders)
assert_private_credentials_file(Path.home() / ".config/reply-mcfly/gmail-token.json")
engine = make_engine(settings.sqlalchemy_url())
try:
    with engine.connect() as connection:
        revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    head = ScriptDirectory.from_config(Config("alembic.ini")).get_current_head()
    if revision != head:
        raise SystemExit(f"Database is at {revision}, expected {head}")
    rag = build_rag(settings, engine)
finally:
    engine.dispose()
senders = "any external sender" if settings.allowed_senders == {"*"} else sorted(settings.allowed_senders)
print("Preflight OK (no network calls were made)")
print("  mailbox:        ", settings.mailbox_id)
print("  allowed senders:", senders)
print("  migration:      ", revision)
print("  Gemini model:   ", settings.gemini_model, "@", settings.vertex_ai_location)
print("  RAG:            ", type(rag.provider).__name__ if rag.provider else "disabled")
print("  reply limit:    ", settings.sender_daily_reply_limit, "per sender / 24 h")
PY
}

cmd_run() {
  local subject="" send=""
  while [ $# -gt 0 ]; do
    case "$1" in
      --subject) subject="${2:-}"; shift 2 ;;
      --send) send="--send"; shift ;;
      *) echo "Unknown option: $1" >&2; exit 2 ;;
    esac
  done
  [ -n "${subject}" ] || { echo 'Usage: local_e2e.sh run --subject "exact subject" [--send]' >&2; exit 2; }
  require_credentials

  echo "== Looking for one unread inbox message with subject: ${subject}"
  local message_id
  message_id="$(worker python - "${subject}" <<'PY'
import sys
from email.header import decode_header, make_header
from pathlib import Path

from reply_mcfly.adapters.google_clients import GmailOAuthFileFactory
from reply_mcfly.config.settings import Settings

subject = sys.argv[1]
mailbox = Settings().mailbox_id.casefold()
service = GmailOAuthFileFactory(Path.home() / ".config/reply-mcfly/gmail-token.json")()
try:
    users = service.users()
    account = users.getProfile(userId="me").execute(num_retries=0)["emailAddress"].casefold()
    if account != mailbox:
        raise SystemExit("Gmail credentials belong to another mailbox than MCFLY_MAILBOX_ID")
    listing = users.messages().list(
        userId="me", labelIds=["INBOX", "UNREAD"], maxResults=50
    ).execute(num_retries=0)
    matches = []
    for item in listing.get("messages", []):
        message = users.messages().get(
            userId="me", id=item["id"], format="metadata", metadataHeaders=["Subject"]
        ).execute(num_retries=0)
        headers = {h["name"].lower(): h["value"] for h in message["payload"].get("headers", [])}
        if str(make_header(decode_header(headers.get("subject", "")))) == subject:
            matches.append(item["id"])
finally:
    service.close()
if len(matches) != 1:
    raise SystemExit(
        f"Expected exactly one unread INBOX message with that exact subject, found {len(matches)}."
        " Check spam, that the message is unread, and that the subject is unique."
    )
print(matches[0])
PY
)"
  echo "   Gmail message id: ${message_id}"
  echo "== Processing (${send:-dry run, nothing is sent})"
  local output status=0
  output="$(worker python -m reply_mcfly.live_email --message-id "${message_id}" ${send} 2>&1)" || status=$?
  echo "${output}"
  local job_id
  job_id="$(echo "${output}" | sed -n 's/.*"job_id": "\([0-9a-f-]\{36\}\)".*/\1/p' | tail -1)"
  if [ -n "${job_id}" ]; then
    cmd_show "${job_id}"
  fi
  if [ "${status}" -ne 0 ]; then
    echo "== Worker finished with an error. Do NOT simply repeat --send; read the job state above." >&2
  fi
  return "${status}"
}

cmd_show() {
  [ $# -eq 1 ] || { echo "Usage: local_e2e.sh show JOB_ID" >&2; exit 2; }
  echo "== Job $1"
  worker python - "$1" <<'PY'
import sys
from uuid import UUID

from sqlalchemy import select

from reply_mcfly.adapters.postgres_adapter import EmailJobModel, PostgresEmailRepository, make_engine
from reply_mcfly.config.settings import Settings

job_id = UUID(sys.argv[1])
engine = make_engine(Settings().sqlalchemy_url())
try:
    with engine.connect() as connection:
        row = connection.execute(
            select(
                EmailJobModel.status,
                EmailJobModel.error_code,
                EmailJobModel.attempt_count,
                EmailJobModel.gmail_thread_id,
            ).where(EmailJobModel.id == job_id)
        ).one_or_none()
    if row is None:
        raise SystemExit("No such job in the local database")
    print(f"status: {row[0]}   error_code: {row[1]}   attempts: {row[2]}   thread: {row[3]}")
    entry = PostgresEmailRepository(engine).outbox(job_id)
finally:
    engine.dispose()
if entry is None:
    print("No reply was prepared for this job.")
else:
    reason = f" ({entry.fallback_reason.value})" if entry.fallback_reason else ""
    print(f"response_type: {entry.response_type.value}{reason}")
    print(f"to: {entry.recipient}   subject: {entry.subject}")
    print(f"in_reply_to: {entry.in_reply_to}")
    print("evidence:")
    for source_id, quote in entry.evidence:
        print(f"  [{source_id}] {quote!r}")
    print(f"attachment passages stored: {len(entry.attachment_passages)}")
    print("----- reply body -----")
    print(entry.draft_body)
    print("----------------------")
PY
}

case "${1:-}" in
  up) shift; cmd_up "$@" ;;
  run) shift; cmd_run "$@" ;;
  show) shift; cmd_show "$@" ;;
  down) docker compose stop ;;
  *) sed -n '2,12p' "$0"; exit 2 ;;
esac
