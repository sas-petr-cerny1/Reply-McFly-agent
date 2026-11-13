from google.genai import types

from reply_mcfly.adapters.vertex_web_search_adapter import passages_from_grounding


def test_passages_from_grounding_groups_by_uri() -> None:
    response = types.GenerateContentResponse(
        candidates=[
            types.Candidate(
                grounding_metadata=types.GroundingMetadata(
                    grounding_chunks=[
                        types.GroundingChunk(
                            web=types.GroundingChunkWeb(
                                uri="https://example.invalid/kurz",
                                title="Kurz EUR/CZK",
                            )
                        )
                    ],
                    grounding_supports=[
                        types.GroundingSupport(
                            segment=types.Segment(
                                text="Aktuální testovací kurz je 24,80 Kč za euro."
                            ),
                            grounding_chunk_indices=[0],
                        )
                    ],
                )
            )
        ]
    )
    passages = passages_from_grounding(response)
    assert len(passages) == 1
    assert passages[0].source_id == "web:https://example.invalid/kurz"
    assert passages[0].source_type == "WEB"
    assert "24,80" in passages[0].text
