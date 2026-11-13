"""Build public web-search queries and decide when live information is needed."""

from __future__ import annotations

import re

from reply_mcfly.application.rag_query import sanitize_product_question
from reply_mcfly.domain.email import IncomingEmail

_LIVE_TOPIC = re.compile(
    r"(?i)\b("
    r"aktuální|aktualni|aktuálně|aktualne|dnešní|dnesni|dnes|"
    r"nejnovější|nejnovějsi|nyní|nyni|kurz|počasí|pocasi|"
    r"burza|akcie|spotřeba|spotreba"
    r")\b"
)
_MAX_WEB_QUERY_CHARS = 600


def needs_live_web_context(email: IncomingEmail) -> bool:
    combined = f"{email.subject}\n{email.text}"
    return bool(_LIVE_TOPIC.search(combined))


def should_invoke_web_search(email: IncomingEmail) -> bool:
    """Live search only for primarily current-information questions.

    Mixed e-mails that also cite thread history are answered from thread/RAG;
    web search is not added for the live fragment alone.
    """
    if not needs_live_web_context(email):
        return False
    if email.thread_history:
        return False
    return True


def build_web_public_query(email: IncomingEmail) -> str:
    """Minimised question for a public search API; never attachment bytes or history."""
    return sanitize_product_question(f"{email.subject}\n{email.text}")[
        :_MAX_WEB_QUERY_CHARS
    ].strip()
