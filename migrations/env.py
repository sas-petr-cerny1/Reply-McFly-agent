from alembic import context

from reply_mcfly.adapters.postgres_adapter import Base, make_engine
from reply_mcfly.config.settings import Settings


def run_migrations() -> None:
    database_url = Settings().sqlalchemy_url()
    if context.is_offline_mode():
        context.configure(url=database_url, target_metadata=Base.metadata, literal_binds=True)
        with context.begin_transaction():
            context.run_migrations()
    else:
        # DDL on a populated table can outlast the 3 s limit meant for request queries.
        engine = make_engine(database_url, statement_timeout_ms=None)
        try:
            with engine.connect() as connection:
                context.configure(connection=connection, target_metadata=Base.metadata)
                with context.begin_transaction():
                    context.run_migrations()
        finally:
            engine.dispose()


run_migrations()
