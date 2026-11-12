from pathlib import Path


def test_knowledge_base_markdown_files_present_for_runtime_copy() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "reply_mcfly" / "knowledge_base"
    names = sorted(p.name for p in root.glob("*.md"))
    assert names == [
        "KB01_DemoBoxPlus.md",
        "KB02_Poskozena_zasilka.md",
        "KB03_Chybejici_prislusenstvi.md",
    ]
