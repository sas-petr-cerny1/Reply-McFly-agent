import hashlib
import shutil
from pathlib import Path

import pytest

from reply_mcfly.application.product_catalog import (
    APPROVED_PRODUCT_IDS,
    CATALOG_DIRECTORY,
    CatalogError,
    chunk_document,
    load_catalog,
)
from reply_mcfly.rag import main as rag_cli

AIRDOCK = "PX01_McFly_AirDock_8.md"


@pytest.fixture
def catalog(tmp_path: Path) -> Path:
    for path in CATALOG_DIRECTORY.glob("*.md"):
        shutil.copy(path, tmp_path / path.name)
    return tmp_path


def _rewrite(catalog: Path, old: str, new: str, name: str = AIRDOCK) -> None:
    path = catalog / name
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new), encoding="utf-8")


def test_catalog_is_three_products_in_eighteen_section_chunks() -> None:
    chunks = load_catalog()

    assert len(chunks) == 18
    assert {chunk.product_id for chunk in chunks} == APPROVED_PRODUCT_IDS
    assert {chunk.document_version for chunk in chunks} == {"2026-11-13.1"}
    for product_id in APPROVED_PRODUCT_IDS:
        assert sum(chunk.product_id == product_id for chunk in chunks) == 6


def test_chunk_identity_matches_the_supplied_reference_corpus() -> None:
    by_id = {chunk.chunk_id: chunk for chunk in load_catalog()}

    price = by_id["mf-dock-08:cena-a-obsah-baleni"]
    assert price.source_id == "rag:mf-dock-08:cena-a-obsah-baleni:192ff842dafd"
    assert price.provenance == "PX01_McFly_AirDock_8.md#cena-a-obsah-baleni@2026-11-13.1"
    assert price.section_name == "Cena a obsah balení"
    assert price.content.startswith("# McFly AirDock 8 — dokovací stanice\n**ID produktu:** MF-")
    assert "- **Testovací cena:** 2 490 Kč včetně DPH." in price.content
    assert by_id["mf-audio-02:popis-produktu"].source_id.endswith(":d23f4e612f58")
    assert by_id["mf-sensor-03:mereni-a-provoz"].source_id.endswith(":6d71bdc8bcda")


def test_content_hash_covers_exactly_the_stored_text() -> None:
    for chunk in load_catalog():
        digest = hashlib.sha256(chunk.content.encode("utf-8")).hexdigest()
        assert chunk.content_sha256 == digest
        assert chunk.source_id == f"rag:{chunk.chunk_id}:{digest[:12]}"


def test_chunking_is_deterministic() -> None:
    assert load_catalog() == load_catalog()


def test_changed_fact_changes_only_that_chunks_source_id(catalog: Path) -> None:
    before = {chunk.chunk_id: chunk.source_id for chunk in load_catalog(catalog)}
    _rewrite(catalog, "2 490 Kč", "2 590 Kč")
    after = {chunk.chunk_id: chunk.source_id for chunk in load_catalog(catalog)}

    changed = {chunk_id for chunk_id in before if before[chunk_id] != after[chunk_id]}
    assert changed == {"mf-dock-08:cena-a-obsah-baleni"}


def test_new_document_version_is_visible_in_provenance(catalog: Path) -> None:
    _rewrite(catalog, "2026-11-13.1", "2026-12-01.1")
    airdock = [c for c in load_catalog(catalog) if c.product_id == "MF-DOCK-08"]

    assert {chunk.document_version for chunk in airdock} == {"2026-12-01.1"}
    assert all(chunk.provenance.endswith("@2026-12-01.1") for chunk in airdock)


def test_fourth_document_is_rejected(catalog: Path) -> None:
    shutil.copy(catalog / AIRDOCK, catalog / "PX04_McFly_Extra_1.md")
    with pytest.raises(CatalogError, match="CATALOG_DOCUMENT_COUNT_INVALID"):
        load_catalog(catalog)


def test_missing_document_is_rejected(catalog: Path) -> None:
    (catalog / AIRDOCK).unlink()
    with pytest.raises(CatalogError, match="CATALOG_DOCUMENT_COUNT_INVALID"):
        load_catalog(catalog)


def test_unapproved_product_is_rejected(catalog: Path) -> None:
    _rewrite(catalog, "MF-DOCK-08", "MF-OTHER-99")
    with pytest.raises(CatalogError, match="CATALOG_PRODUCTS_NOT_APPROVED"):
        load_catalog(catalog)


def test_same_product_in_two_documents_is_rejected(catalog: Path) -> None:
    _rewrite(catalog, "MF-AUDIO-02", "MF-DOCK-08", "PX02_McFly_SoundLoop_S2.md")
    with pytest.raises(CatalogError):
        load_catalog(catalog)


def test_removed_section_breaks_the_expected_chunk_count(catalog: Path) -> None:
    _rewrite(catalog, "## Často kladené otázky", "**Často kladené otázky**")
    with pytest.raises(CatalogError, match="CATALOG_CHUNK_COUNT_INVALID"):
        load_catalog(catalog)


@pytest.mark.parametrize(
    ("old", "new", "error"),
    [
        ("# McFly AirDock 8 — dokovací stanice", "McFly AirDock 8", "CATALOG_TITLE_MISSING"),
        ("**ID produktu:** MF-DOCK-08", "", "CATALOG_METADATA_MISSING"),
        ("**Verze znalostí:** 2026-11-13.1", "", "CATALOG_METADATA_MISSING"),
        ("**Typ:** Fiktivní produkt", "**Typ:** Produkt", "CATALOG_METADATA_MISSING"),
    ],
)
def test_invalid_document_metadata_is_rejected(
    catalog: Path, old: str, new: str, error: str
) -> None:
    _rewrite(catalog, old, new)
    with pytest.raises(CatalogError, match=error):
        load_catalog(catalog)


def test_empty_section_and_bad_name_are_rejected() -> None:
    raw = (CATALOG_DIRECTORY / AIRDOCK).read_text(encoding="utf-8")
    with pytest.raises(CatalogError, match="CATALOG_SECTION_EMPTY"):
        chunk_document(AIRDOCK, raw + "\n## Prázdná sekce\n")
    with pytest.raises(CatalogError, match="CATALOG_DOCUMENT_NAME_INVALID"):
        chunk_document("customer-email.md", raw)


def test_non_utf8_document_is_rejected(catalog: Path) -> None:
    (catalog / AIRDOCK).write_bytes(b"# Title \xff\xfe")
    with pytest.raises(CatalogError, match="CATALOG_DOCUMENT_NOT_UTF8"):
        load_catalog(catalog)


def test_catalog_is_kept_apart_from_the_markdown_knowledge_base() -> None:
    knowledge_base = CATALOG_DIRECTORY.parent / "knowledge_base"
    assert sorted(path.name for path in CATALOG_DIRECTORY.glob("*.md")) == [
        "PX01_McFly_AirDock_8.md",
        "PX02_McFly_SoundLoop_S2.md",
        "PX03_McFly_HomeSense_H3.md",
    ]
    assert not list(knowledge_base.glob("PX*"))


def test_validate_command_works_offline(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, catalog: Path
) -> None:
    monkeypatch.delenv("MCFLY_DATABASE_URL", raising=False)

    assert rag_cli(["validate"]) == 0
    assert '"chunk_count": 18' in capsys.readouterr().out

    (catalog / AIRDOCK).unlink()
    assert rag_cli(["--catalog", str(catalog), "validate"]) == 2
    assert "CATALOG_DOCUMENT_COUNT_INVALID" in capsys.readouterr().err
