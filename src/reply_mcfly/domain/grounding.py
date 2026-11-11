from reply_mcfly.domain.email import Evidence, IncomingEmail, ReplyDraft, WorkflowError


def render_verified_reply(evidence: list[Evidence]) -> str:
    quotes = "\n\n".join(
        "\n".join("> " + line for line in item.exact_quote.splitlines()) for item in evidence
    )
    return (
        "Dobrý den,\n\nve své zprávě uvádíte:\n\n"
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
        for item in draft.evidence:
            if (
                item.source_id != f"email:{email.metadata.message_id}"
                or not item.exact_quote.strip()
                or item.exact_quote not in email.text
            ):
                raise WorkflowError("INVALID_EVIDENCE")
        # Every variable byte of the outgoing body must be a literal attributed source quote.
        if draft.proposed_reply != render_verified_reply(draft.evidence):
            raise WorkflowError("UNSUPPORTED_REPLY_CLAIM")
