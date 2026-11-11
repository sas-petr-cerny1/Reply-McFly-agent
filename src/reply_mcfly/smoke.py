import argparse
from uuid import uuid4

from reply_mcfly.adapters.postgres_adapter import PostgresAdapter, make_engine
from reply_mcfly.application.diagnostics import DiagnosticsService
from reply_mcfly.config.settings import Settings


def main() -> None:
    parser = argparse.ArgumentParser(description="RM-001 synthetic database persistence check")
    parser.add_argument("--verify", metavar="MAILBOX_ID", help="Read an existing smoke record")
    args = parser.parse_args()
    engine = make_engine(Settings().sqlalchemy_url())
    try:
        service = DiagnosticsService(PostgresAdapter(engine))
        service.check_health()
        if args.verify:
            service.verify_test_mailbox(args.verify)
            print("Persistence check: OK")
        else:
            mailbox_id = f"{uuid4()}@smoke.invalid"
            service.create_test_mailbox(mailbox_id)
            print(mailbox_id)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
