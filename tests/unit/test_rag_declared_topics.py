from pathlib import Path

import pytest

from reply_mcfly.adapters.markdown_rag_adapter import MarkdownRAGProvider

WARRANTY = """# KB04 – Záruka

**Témata:** záruka, záruční doba, reklamace, oprava.

- **Záruční doba:** 24 měsíců od převzetí zboží.
"""


def test_new_document_is_retrievable_through_its_own_topics_line(tmp_path: Path) -> None:
    (tmp_path / "KB04_Zaruka.md").write_text(WARRANTY, encoding="utf-8")
    provider = MarkdownRAGProvider(tmp_path)

    found = provider.retrieve("Jak dlouhá je záruční lhůta a jak probíhají opravy?")

    assert [item.provenance for item in found] == ["KB04_Zaruka.md"]
    assert provider.retrieve("Kde je nyní můj kurýr?") == ()


def test_document_without_any_anchors_is_rejected_at_startup(tmp_path: Path) -> None:
    (tmp_path / "KB04_Zaruka.md").write_text("Záruční doba je 24 měsíců.", encoding="utf-8")

    with pytest.raises(ValueError, match="RAG_DOCUMENT_TOPICS_MISSING"):
        MarkdownRAGProvider(tmp_path)
