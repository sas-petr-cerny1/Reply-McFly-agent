from typing import Protocol


class DiagnosticStore(Protocol):
    def check_health(self) -> None: ...
    def create_mailbox(self, mailbox_id: str) -> None: ...
    def mailbox_exists(self, mailbox_id: str) -> bool: ...


class DiagnosticsService:
    def __init__(self, store: DiagnosticStore) -> None:
        self.store = store

    def check_health(self) -> None:
        self.store.check_health()

    def create_test_mailbox(self, mailbox_id: str) -> None:
        if not mailbox_id.endswith("@smoke.invalid"):
            raise ValueError("Diagnostics only accepts synthetic @smoke.invalid mailboxes")
        self.store.create_mailbox(mailbox_id)
        if not self.store.mailbox_exists(mailbox_id):
            raise RuntimeError("Database read after write failed")

    def verify_test_mailbox(self, mailbox_id: str) -> None:
        if not self.store.mailbox_exists(mailbox_id):
            raise RuntimeError("Test mailbox was not found")
