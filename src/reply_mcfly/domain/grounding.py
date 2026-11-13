from reply_mcfly.domain.email import Evidence, IncomingEmail, ReplyDraft, WorkflowError


def _reply_intro(evidence: list[Evidence]) -> str:
    kinds = {item.source_id.split(":", 1)[0] for item in evidence}
    if kinds == {"thread"}:
        return "Dobrý den,\n\nv naší předchozí e-mailové konverzaci zaznělo:\n\n"
    has_rag = "rag" in kinds
    has_web = "web" in kinds
    if kinds == {"attachment"}:
        return "Dobrý den,\n\nz ověřeného obsahu přílohy plyne:\n\n"
    if kinds == {"email"}:
        return "Dobrý den,\n\nve své zprávě uvádíte:\n\n"
    if kinds == {"rag"}:
        return "Dobrý den,\n\nrelevantní pravidlo z naší znalostní báze:\n\n"
    if kinds == {"web"}:
        return "Dobrý den,\n\nz veřejně dostupných zdrojů:\n\n"
    if has_rag or has_web:
        return "Dobrý den,\n\nna základě vašeho dotazu a ověřených podkladů:\n\n"
    return "Dobrý den,\n\nna základě ověřených podkladů:\n\n"


def render_verified_reply(evidence: list[Evidence]) -> str:
    quotes = "\n\n".join(
        "\n".join("> " + line for line in item.exact_quote.splitlines()) for item in evidence
    )
    intro = _reply_intro(evidence)
    return intro + quotes + "\n\nS pozdravem\nReply McFly – AI Email Assistant"


def _quoted_whole_words(quote: str, source: str) -> bool:
    """True when the quote occurs in the source without cutting a word in half.

    A bare substring check would accept "lze vrátit" from "nelze vrátit" and invert the
    meaning. This is a lexical guard only; it does not prove the quote keeps its context.
    """
    start = source.find(quote)
    while start != -1:
        end = start + len(quote)
        cuts_start = start > 0 and source[start - 1].isalnum() and quote[0].isalnum()
        cuts_end = end < len(source) and source[end].isalnum() and quote[-1].isalnum()
        if not cuts_start and not cuts_end:
            return True
        start = source.find(quote, start + 1)
    return False


class LiteralReplyValidator:
    def validate(self, email: IncomingEmail, draft: ReplyDraft) -> None:
        if (
            draft.response_type != "GENERATED"
            or draft.missing_information
            or draft.requires_review
            or not draft.evidence
        ):
            raise WorkflowError("UNVERIFIABLE_REPLY")
        sources = {f"email:{email.metadata.message_id}": email.text}
        sources.update({passage.source_id: passage.text for passage in email.thread_history})
        sources.update({passage.source_id: passage.text for passage in email.attachment_passages})
        sources.update({passage.source_id: passage.text for passage in email.rag_passages})
        sources.update({passage.source_id: passage.text for passage in email.web_passages})
        for item in draft.evidence:
            if (
                item.source_id not in sources
                or not item.exact_quote.strip()
                or not _quoted_whole_words(item.exact_quote, sources[item.source_id])
            ):
                raise WorkflowError("INVALID_EVIDENCE")
        # Outbound body comes from evidence; proposed_reply is model metadata only.
