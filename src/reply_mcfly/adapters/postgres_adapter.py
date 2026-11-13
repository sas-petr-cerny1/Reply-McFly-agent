from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    func,
    select,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.dialects.postgresql.base import ischema_names
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from sqlalchemy.types import UserDefinedType

from reply_mcfly.application.telemetry import emit
from reply_mcfly.domain.email import (
    TERMINAL,
    TRANSITIONS,
    AttachmentPassage,
    Evidence,
    FallbackReason,
    Job,
    MessageMetadata,
    OutboxEntry,
    ResponseType,
    Status,
    WorkflowError,
)


class Base(DeclarativeBase):
    pass


class MailboxSyncState(Base):
    __tablename__ = "mailbox_sync_state"

    mailbox_id: Mapped[str] = mapped_column(String(320), primary_key=True)
    history_id: Mapped[str | None] = mapped_column(String(255))
    watch_expiration: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_token: Mapped[UUID | None]
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


def make_engine(database_url: str) -> Engine:
    return create_engine(
        database_url,
        pool_pre_ping=True,
        pool_size=2,
        max_overflow=0,
        pool_timeout=5,
        hide_parameters=True,
        connect_args={"connect_timeout": 3, "options": "-c statement_timeout=3000"},
    )


class PostgresAdapter:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def check_health(self) -> None:
        with self.engine.connect() as connection:
            connection.execute(text("SELECT mailbox_id FROM mailbox_sync_state LIMIT 0"))
            revision = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
            vector_version = connection.execute(
                text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
            ).scalar_one()
            if not revision or not vector_version:
                raise RuntimeError("Database is not initialized")

    def create_mailbox(self, mailbox_id: str) -> None:
        with Session(self.engine) as session, session.begin():
            session.add(MailboxSyncState(mailbox_id=mailbox_id))

    def mailbox_exists(self, mailbox_id: str) -> bool:
        with Session(self.engine) as session:
            return session.get(MailboxSyncState, mailbox_id) is not None


class EmailJobModel(Base):
    __tablename__ = "email_jobs"
    __table_args__ = (
        UniqueConstraint("mailbox_id", "gmail_message_id", name="uq_job_mailbox_message"),
        CheckConstraint("attempt_count >= 0", name="ck_job_attempt_count"),
        CheckConstraint(
            "status IN (" + ",".join(f"'{s.value}'" for s in Status) + ")", name="ck_job_status"
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    mailbox_id: Mapped[str] = mapped_column(ForeignKey("mailbox_sync_state.mailbox_id"))
    gmail_message_id: Mapped[str] = mapped_column(String(255))
    gmail_thread_id: Mapped[str] = mapped_column(String(255), index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), index=True)
    attempt_count: Mapped[int] = mapped_column(Integer, server_default="0")
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    lease_token: Mapped[UUID | None]
    error_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EmailOutboxModel(Base):
    __tablename__ = "email_outbox"
    __table_args__ = (
        CheckConstraint(
            "(response_type = 'GENERATED' AND fallback_reason IS NULL) OR "
            "(response_type = 'FALLBACK' AND fallback_reason IN "
            "('INSUFFICIENT_INFORMATION','UNSUPPORTED_ATTACHMENT') "
            "AND fallback_reason IS NOT NULL)",
            name="ck_outbox_response_type",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(ForeignKey("email_jobs.id"), unique=True)
    outbound_message_id: Mapped[str] = mapped_column(String(998), unique=True)
    recipient: Mapped[str] = mapped_column(String(320))
    subject: Mapped[str] = mapped_column(String(998))
    draft_body: Mapped[str] = mapped_column(Text)
    response_type: Mapped[str] = mapped_column(String(16))
    fallback_reason: Mapped[str | None] = mapped_column(String(64))
    evidence: Mapped[list[dict[str, str]]] = mapped_column(JSONB, server_default="[]")
    attachment_passages: Mapped[list[dict[str, str]]] = mapped_column(JSONB, server_default="[]")
    in_reply_to: Mapped[str] = mapped_column(String(998))
    references: Mapped[str] = mapped_column(String(2000))
    status: Mapped[str] = mapped_column(String(32))
    gmail_sent_message_id: Mapped[str | None] = mapped_column(String(255))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


EMBEDDING_DIMENSIONS = 768


class Vector(UserDefinedType[str]):
    """pgvector column type; values travel as the textual ``[1,2,3]`` literal."""

    cache_ok = True

    def __init__(self, dimensions: int | None = None) -> None:
        self.dimensions = dimensions

    def get_col_spec(self, **kw: object) -> str:
        return "vector" if self.dimensions is None else f"vector({self.dimensions})"


# Lets schema reflection (alembic check) recognize the column instead of warning.
ischema_names["vector"] = Vector


class RagProductChunkModel(Base):
    """Approved product knowledge only; never customer mail or thread history."""

    __tablename__ = "rag_product_chunks"
    __table_args__ = (UniqueConstraint("source_id", name="uq_rag_product_chunks_source_id"),)
    chunk_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    document_id: Mapped[str] = mapped_column(String(255))
    product_id: Mapped[str] = mapped_column(String(64), index=True)
    product_name: Mapped[str] = mapped_column(String(255))
    section_name: Mapped[str] = mapped_column(String(255))
    document_version: Mapped[str] = mapped_column(String(64))
    language: Mapped[str] = mapped_column(String(8))
    content: Mapped[str] = mapped_column(Text)
    content_sha256: Mapped[str] = mapped_column(String(64))
    source_id: Mapped[str] = mapped_column(String(512))
    provenance: Mapped[str] = mapped_column(String(512))
    embedding_model: Mapped[str] = mapped_column(String(128))
    embedding: Mapped[str] = mapped_column(Vector(EMBEDDING_DIMENSIONS))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def _job(row: EmailJobModel) -> Job:
    return Job(
        row.id,
        row.mailbox_id,
        row.gmail_message_id,
        row.gmail_thread_id,
        row.received_at,
        Status(row.status),
        row.lease_token,
        row.lease_until,
        row.attempt_count,
    )


class PostgresEmailRepository:
    def __init__(self, engine: Engine, max_attempts: int = 3) -> None:
        self.engine = engine
        self.max_attempts = max_attempts

    def initialize(self, mailbox_id: str, history_id: str, expiration: datetime | None) -> None:
        with Session(self.engine) as session, session.begin():
            session.execute(
                insert(MailboxSyncState)
                .values(mailbox_id=mailbox_id, history_id=history_id, watch_expiration=expiration)
                .on_conflict_do_nothing(index_elements=["mailbox_id"])
            )
            row = session.get(MailboxSyncState, mailbox_id, with_for_update=True)
            if row is None:
                raise WorkflowError("MAILBOX_INITIALIZATION_FAILED", retryable=True, status=503)
            if row.history_id is None:
                row.history_id = history_id
            if expiration is not None:
                row.watch_expiration = expiration

    def acquire_sync(self, mailbox_id: str, token: UUID) -> str:
        with Session(self.engine) as session, session.begin():
            row = session.get(MailboxSyncState, mailbox_id, with_for_update=True)
            if row is None or row.history_id is None:
                raise WorkflowError("MAILBOX_NOT_INITIALIZED", retryable=True, status=503)
            now = session.execute(select(func.now())).scalar_one()
            if row.lease_until and row.lease_until > now:
                raise WorkflowError("SYNC_BUSY", retryable=True, status=503)
            row.lease_token = token
            row.lease_until = now + timedelta(seconds=110)
            return row.history_id

    def release_sync(self, mailbox_id: str, token: UUID) -> None:
        with Session(self.engine) as session, session.begin():
            row = session.get(MailboxSyncState, mailbox_id, with_for_update=True)
            if row and row.lease_token == token:
                row.lease_until = None
                row.lease_token = None

    def checkpoint(self, mailbox_id: str, token: UUID, history_id: str) -> None:
        with Session(self.engine) as session, session.begin():
            row = session.get(MailboxSyncState, mailbox_id, with_for_update=True)
            if (
                not row
                or row.lease_token != token
                or not row.lease_until
                or row.lease_until <= session.execute(select(func.now())).scalar_one()
            ):
                raise WorkflowError("LEASE_LOST", retryable=True, status=503)
            if int(history_id) < int(row.history_id or "0"):
                raise WorkflowError("INVALID_CHECKPOINT")
            row.history_id = history_id
            row.updated_at = datetime.now(UTC)

    def enqueue(self, mailbox_id: str, metadata: MessageMetadata) -> UUID:
        with Session(self.engine) as session, session.begin():
            session.execute(
                insert(EmailJobModel)
                .values(
                    id=uuid4(),
                    mailbox_id=mailbox_id,
                    gmail_message_id=metadata.message_id,
                    gmail_thread_id=metadata.thread_id,
                    received_at=metadata.received_at,
                    status=Status.QUEUED.value,
                )
                .on_conflict_do_nothing(constraint="uq_job_mailbox_message")
            )
            return session.execute(
                select(EmailJobModel.id).where(
                    EmailJobModel.mailbox_id == mailbox_id,
                    EmailJobModel.gmail_message_id == metadata.message_id,
                )
            ).scalar_one()

    def get(self, job_id: UUID) -> Job:
        with Session(self.engine) as session:
            row = session.get(EmailJobModel, job_id)
            if row is None:
                raise WorkflowError("JOB_NOT_FOUND", status=404)
            return _job(row)

    def claim(self, job_id: UUID, token: UUID) -> Job:
        with Session(self.engine) as session, session.begin():
            row = session.get(EmailJobModel, job_id, with_for_update=True)
            if row is None:
                raise WorkflowError("JOB_NOT_FOUND", status=404)
            if Status(row.status) in TERMINAL:
                return _job(row)
            now = session.execute(select(func.now())).scalar_one()
            if row.lease_until and row.lease_until > now:
                raise WorkflowError("JOB_BUSY", retryable=True, status=503)
            if row.status in {Status.SENDING, Status.DELIVERY_UNKNOWN}:
                row.status = Status.DELIVERY_UNKNOWN.value
            elif row.attempt_count >= self.max_attempts:
                row.status = Status.FAILED.value
                row.error_code = "ATTEMPTS_EXHAUSTED"
                return _job(row)
            else:
                row.status = Status.PROCESSING.value
                row.attempt_count += 1
            row.lease_token = token
            row.lease_until = now + timedelta(seconds=110)
            row.updated_at = now
            return _job(row)

    def _owned(self, session: Session, job: Job) -> EmailJobModel:
        row = session.get(EmailJobModel, job.id, with_for_update=True)
        if (
            not row
            or row.lease_token != job.lease_token
            or not row.lease_until
            or row.lease_until <= session.execute(select(func.now())).scalar_one()
        ):
            raise WorkflowError("LEASE_LOST", retryable=True, status=503)
        return row

    def _transition(
        self, session: Session, job: Job, target: Status, code: str | None
    ) -> EmailJobModel:
        row = self._owned(session, job)
        if target not in TRANSITIONS.get(Status(row.status), set()):
            raise WorkflowError("INVALID_TRANSITION")
        row.status = target.value
        row.error_code = code
        row.updated_at = datetime.now(UTC)
        if target in TERMINAL or target in {Status.RETRY_PENDING, Status.DELIVERY_UNKNOWN}:
            row.lease_until = None
            row.lease_token = None
        return row

    def transition(self, job: Job, target: Status, code: str | None = None) -> None:
        with Session(self.engine) as session, session.begin():
            self._transition(session, job, target, code)
            entry = session.scalar(
                select(EmailOutboxModel).where(EmailOutboxModel.job_id == job.id)
            )
            if entry:
                entry.status = target.value
        emit("job_transition", job_id=str(job.id), status=target.value, error_code=code)

    def prepare(self, job: Job, entry: OutboxEntry) -> None:
        if entry.job_id != job.id:
            raise WorkflowError("OUTBOX_MISMATCH")
        with Session(self.engine) as session, session.begin():
            self._transition(session, job, Status.READY_TO_SEND, None)
            values = {
                **entry.__dict__,
                "evidence": [
                    {"source_id": source, "exact_quote": quote} for source, quote in entry.evidence
                ],
                "attachment_passages": [
                    {"source_id": passage.source_id, "text": passage.text}
                    for passage in entry.attachment_passages
                ],
            }
            session.execute(
                insert(EmailOutboxModel)
                .values(id=uuid4(), **values, status=Status.READY_TO_SEND.value)
                .on_conflict_do_nothing(index_elements=["job_id"])
            )
        emit("reply_ready", job_id=str(job.id), status=Status.READY_TO_SEND.value)

    def outbox(self, job_id: UUID) -> OutboxEntry | None:
        with Session(self.engine) as session:
            row = session.scalar(select(EmailOutboxModel).where(EmailOutboxModel.job_id == job_id))
            if not row:
                return None
            return OutboxEntry(
                row.job_id,
                row.outbound_message_id,
                row.recipient,
                row.subject,
                row.draft_body,
                row.in_reply_to,
                row.references,
                ResponseType(row.response_type),
                FallbackReason(row.fallback_reason) if row.fallback_reason else None,
                tuple(
                    (item.source_id, item.exact_quote)
                    for item in (Evidence.model_validate(value) for value in row.evidence)
                ),
                tuple(
                    AttachmentPassage(value["source_id"], value["text"])
                    for value in row.attachment_passages
                ),
            )

    def sent(self, job: Job, gmail_message_id: str) -> None:
        with Session(self.engine) as session, session.begin():
            self._transition(session, job, Status.SENT, None)
            entry = session.execute(
                select(EmailOutboxModel).where(EmailOutboxModel.job_id == job.id)
            ).scalar_one()
            entry.status = Status.SENT.value
            entry.gmail_sent_message_id = gmail_message_id
            entry.sent_at = datetime.now(UTC)
        emit("delivery_confirmed", job_id=str(job.id), status=Status.SENT.value)

    def release_lease(self, job: Job) -> None:
        with Session(self.engine) as session, session.begin():
            row = session.get(EmailJobModel, job.id, with_for_update=True)
            if row and row.lease_token == job.lease_token:
                row.lease_until = None
                row.lease_token = None
