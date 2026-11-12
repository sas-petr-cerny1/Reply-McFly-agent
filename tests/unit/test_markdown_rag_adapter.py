from pathlib import Path

import pytest

from reply_mcfly.adapters.markdown_rag_adapter import MarkdownRAGProvider


def test_demobox_facts_are_retrieved() -> None:
    result = MarkdownRAGProvider().retrieve(
        "Kolik stojí DemoBox+, kryje náhodné polití a kolik činí spoluúčast?"
    )
    assert result and result[0].source_id.startswith("rag:KB01_")
    assert "179 Kč" in result[0].text
    assert "390 Kč" in result[0].text
    assert "2 uznané škodní události" in result[0].text


def test_damaged_parcel_policy_is_retrieved() -> None:
    result = MarkdownRAGProvider().retrieve("Mám poškozenou krabici a protržený roh při přepravě")
    assert result and result[0].source_id.startswith("rag:KB02_")
    assert "48 hodin" in result[0].text
    assert "fotografie vnějšího obalu i obsahu" in result[0].text


def test_missing_cable_policy_is_retrieved() -> None:
    result = MarkdownRAGProvider().retrieve("V zásilce chybí napájecí kabel. Co mám doložit?")
    assert result and result[0].source_id.startswith("rag:KB03_")
    assert "7 kalendářních dnů" in result[0].text
    assert "bezplatně" in result[0].text


def test_no_false_live_tracking_answer() -> None:
    assert MarkdownRAGProvider().retrieve("Kde je nyní můj kurýr? Jaké je dnešní ETA?") == ()


def test_empty_or_too_many_docs_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="RAG_DOCUMENT_COUNT_INVALID"):
        MarkdownRAGProvider(tmp_path)
    for index in range(4):
        (tmp_path / f"file{index}.md").write_text("Data", encoding="utf-8")
    with pytest.raises(ValueError, match="RAG_DOCUMENT_COUNT_INVALID"):
        MarkdownRAGProvider(tmp_path)


def test_source_id_is_versioned(tmp_path: Path) -> None:
    file = tmp_path / "KB01_demo.md"
    file.write_text("DemoBox+ krytí\n", encoding="utf-8")
    first = MarkdownRAGProvider(tmp_path).retrieve("DemoBox+ krytí")
    file.write_text("DemoBox+ krytí změna\n", encoding="utf-8")
    second = MarkdownRAGProvider(tmp_path).retrieve("DemoBox+ krytí")
    assert first and second and first[0].source_id != second[0].source_id
