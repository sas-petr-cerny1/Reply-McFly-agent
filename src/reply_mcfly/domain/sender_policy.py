from dataclasses import dataclass

WILDCARD_SENDER = "*"


class SenderConfigurationError(ValueError):
    pass


@dataclass(frozen=True)
class SenderPolicy:
    allow_all: bool
    allowed: frozenset[str] = frozenset()

    def permits_sender(self, sender: str) -> bool:
        folded = sender.casefold()
        if "@" not in folded or not folded.strip():
            return False
        if self.allow_all:
            return True
        return folded in self.allowed


def parse_sender_policy(allowed_senders: frozenset[str], mailbox_id: str) -> SenderPolicy:
    if not allowed_senders:
        raise SenderConfigurationError("EMPTY_ALLOWED_SENDERS")
    if WILDCARD_SENDER in allowed_senders:
        if allowed_senders != frozenset({WILDCARD_SENDER}):
            raise SenderConfigurationError("WILDCARD_NOT_EXCLUSIVE")
        _require_mailbox_address(mailbox_id)
        return SenderPolicy(allow_all=True)
    mailbox = mailbox_id.casefold()
    _require_mailbox_address(mailbox_id)
    allowed = frozenset(address.casefold() for address in allowed_senders)
    if mailbox in allowed:
        raise SenderConfigurationError("MAILBOX_IN_ALLOWLIST")
    if any("@" not in address or not address.strip() for address in allowed):
        raise SenderConfigurationError("MALFORMED_SENDER_ADDRESS")
    return SenderPolicy(allow_all=False, allowed=allowed)


def _require_mailbox_address(mailbox_id: str) -> None:
    if not mailbox_id or "@" not in mailbox_id:
        raise SenderConfigurationError("INVALID_MAILBOX_ID")
