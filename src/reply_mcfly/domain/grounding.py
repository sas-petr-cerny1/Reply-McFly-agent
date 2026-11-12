from reply_mcfly.domain.email import Evidence, IncomingEmail, ReplyDraft, WorkflowError


def _reply_intro(evidence: list[Evidence]) -> str:
    if any(item.source_id.startswith("thread:") for item in evidence):
        return "Dobrý den,\n\nv naší předchozí e-mailové konverzaci zaznělo:\n\n"
    kinds = {item.source_id.split(":", 1)[0] for item in evidence}
    has_rag = "rag" in kinds
    if kinds == {"attachment"}:
        return "Dobrý den,\n\nz ověřeného obsahu přílohy plyne:\n\n"
    if kinds == {"email"}:
        return "Dobrý den,\n\nve své zprávě uvádíte:\n\n"
    if kinds == {"rag"}:
        return "Dobrý den,\n\nrelevantní pravidlo z naší znalostní báze:\n\n"
    if has_rag:
        return "Dobrý den,\n\nna základě vašeho dotazu a ověřených podkladů:\n\n"
    return "Dobrý den,\n\nna základě ověřených podkladů:\n\n"


def render_verified_reply(evidence: list[Evidence]) -> str:
    quotes = "\n\n".join(
        "\n".join("> " + line for line in item.exact_quote.splitlines()) for item in evidence
    )
    intro = _reply_intro(evidence)
    return (
        intro
        + quotes
        + "\n\nS pozdravem\nReply McFly – AI Email Assistant"
    )


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
        for item in draft.evidence:
            if (
                item.source_id not in sources
                or not item.exact_quote.strip()
                or item.exact_quote not in sources[item.source_id]
            ):
                raise WorkflowError("INVALID_EVIDENCE")
        # Outbound body is assembled server-side from evidence; proposed_reply is model metadata only.
