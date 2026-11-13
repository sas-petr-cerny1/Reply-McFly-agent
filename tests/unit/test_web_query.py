from datetime import UTC, datetime

from reply_mcfly.application.web_query import (
    build_web_public_query,
    needs_live_web_context,
    should_invoke_web_search,
)
from reply_mcfly.domain.email import IncomingEmail, MessageMetadata, ThreadHistoryPassage


def _email(text: str, *, thread: bool = False) -> IncomingEmail:
    history: tuple[ThreadHistoryPassage, ...] = ()
    if thread:
        history = (
            ThreadHistoryPassage(
                "thread:m1",
                "customer@synthetic.invalid",
                "Předchozí zpráva.",
            ),
        )
    return IncomingEmail(
        MessageMetadata("m", "t", datetime.now(UTC), frozenset()),
        "customer@synthetic.invalid",
        "Dotaz",
        "",
        "",
        text,
        thread_history=history,
    )


def test_needs_live_web_context_detects_kurz() -> None:
    assert needs_live_web_context(_email("Jaký je aktuální kurz koruny vůči euru?"))


def test_should_not_invoke_web_when_thread_present() -> None:
    email = _email(
        "Jaké číslo jsem uvedl a jaký je aktuální kurz?",
        thread=True,
    )
    assert needs_live_web_context(email)
    assert not should_invoke_web_search(email)


def test_should_invoke_for_standalone_live_question() -> None:
    email = _email("Jaký je aktuální kurz koruny vůči euru?")
    assert should_invoke_web_search(email)


def test_build_web_public_query_strips_links() -> None:
    email = _email("Kurz na https://example.invalid/now prosím.")
    assert "http" not in build_web_public_query(email)
