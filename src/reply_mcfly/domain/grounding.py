from reply_mcfly.domain.email import Evidence, IncomingEmail, ReplyDraft, WorkflowError


def render_verified_reply(evidence: list[Evidence]) -> str:
    quotes = "\n\n".join(
        "\n".join("> " + line for line in item.exact_quote.splitlines()) for item in evidence
    )
    intro = (
        "Dobrý den,\n\nv naší předchozí e-mailové konverzaci zaznělo:\n\n"
        if any(item.source_id.startswith("thread:") for item in evidence)
        else "Dobrý den,\n\nve své zprávě uvádíte:\n\n"
    )
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
        for item in draft.evidence:
            if (
                item.source_id not in sources
                or not item.exact_quote.strip()
                or item.exact_quote not in sources[item.source_id]
            ):
                raise WorkflowError("INVALID_EVIDENCE")
        # Outbound body is assembled server-side from evidence; proposed_reply is model metadata only.
