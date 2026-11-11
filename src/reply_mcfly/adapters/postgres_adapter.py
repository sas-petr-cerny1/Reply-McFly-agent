from datetime import datetime

from sqlalchemy import DateTime, String, create_engine, func, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


class Base(DeclarativeBase):
    pass


class MailboxSyncState(Base):
    __tablename__ = "mailbox_sync_state"

    mailbox_id: Mapped[str] = mapped_column(String(320), primary_key=True)
    history_id: Mapped[str | None] = mapped_column(String(255))
    watch_expiration: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
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
