import time
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock, create_autospec
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.engine import Engine

from reply_mcfly.adapters.markdown_rag_adapter import MarkdownRAGProvider
from reply_mcfly.adapters.pgvector_rag_adapter import (
    PgVectorRAGProvider,
    _product,
    _select,
    identify_products,
    vector_literal,
)
from reply_mcfly.adapters.postgres_adapter import EMBEDDING_DIMENSIONS
from reply_mcfly.adapters.rag_factory import build_rag
from reply_mcfly.application.email_processing_service import EmailProcessingService
from reply_mcfly.application.product_catalog import load_catalog
from reply_mcfly.application.rag_query import (
    build_product_question,
    build_rag_retrieval_query,
    sanitize_product_question,
)
from reply_mcfly.application.reply_service import ReplyService
from reply_mcfly.config.settings import RAG_VECTOR_DIMENSIONS, Settings
from reply_mcfly.domain.email import (
    AttachmentPassage,
    IncomingEmail,
    MessageMetadata,
    ThreadHistoryPassage,
    WorkflowError,
)
from reply_mcfly.ports.capabilities import EmbeddingProvider, RAGProvider
from reply_mcfly.ports.email import EmailRepository, GmailPort, WorkflowRunner

PRODUCTS = [
    _product("MF-AUDIO-02", "McFly SoundLoop S2 — bezdrátová sluchátka"),
    _product("MF-DOCK-08", "McFly AirDock 8 — dokovací stanice"),
    _product("MF-SENSOR-03", "McFly HomeSense H3 — domácí senzor teploty a vlhkosti"),
]


def _rows() -> list[dict[str, Any]]:
    return [
        {
            "document_id": chunk.document_id,
            "product_id": chunk.product_id,
            "document_version": chunk.document_version,
            "content": chunk.content,
            "source_id": chunk.source_id,
            "provenance": chunk.provenance,
        }
        for chunk in load_catalog()
    ]


@pytest.mark.parametrize(
    ("question", "named"),
    [
        ("Kolik stojí AirDock 8?", ("MF-DOCK-08",)),
        ("Kolik stojí airdock?", ("MF-DOCK-08",)),
        ("Podporuje SoundLoop S2 ANC?", ("MF-AUDIO-02",)),
        ("Měří HomeSense H3 CO₂?", ("MF-SENSOR-03",)),
        ("Dotaz k MF-SENSOR-03", ("MF-SENSOR-03",)),
        ("Jakou výdrž má baterie u SoundLoopu?", ("MF-AUDIO-02",)),
        ("Porovnejte AirDock 8 a SoundLoop S2", ("MF-AUDIO-02", "MF-DOCK-08")),
        ("Jaká sluchátka mají potlačení hluku?", ()),
    ],
)
def test_products_named_in_the_question_are_identified(
    question: str, named: tuple[str, ...]
) -> None:
    assert identify_products(question, PRODUCTS) == (named, False)


@pytest.mark.parametrize(
    "question",
    [
        "Kolik stojí AirDock 9?",
        "Má SoundLoop S3 ANC?",
        "Kolik stojí McFly PowerHub 5?",
        "Měří HomeSense H4 CO₂?",
    ],
)
def test_unknown_model_is_not_mistaken_for_a_catalog_product(question: str) -> None:
    assert identify_products(question, PRODUCTS) == ((), True)


def test_named_product_keeps_vector_order_and_top_k() -> None:
    rows = [row for row in _rows() if row["product_id"] == "MF-DOCK-08"]

    assert _select(rows, ("MF-DOCK-08",), "Kolik stojí AirDock 8?", 3) == rows[:3]
    assert _select(rows, ("MF-DOCK-08",), "Kolik stojí AirDock 8?", 1) == rows[:1]


def test_two_named_products_each_get_their_best_passage() -> None:
    rows = _rows()
    audio = [row for row in rows if row["product_id"] == "MF-AUDIO-02"]
    dock = [row for row in rows if row["product_id"] == "MF-DOCK-08"]
    ranked = dock + audio  # every dock passage outranks every audio passage

    selected = _select(ranked, ("MF-AUDIO-02", "MF-DOCK-08"), "AirDock 8 a SoundLoop S2", 3)

    assert selected == [audio[0], dock[0], dock[1]]


def test_unnamed_question_needs_shared_vocabulary_and_one_product() -> None:
    rows = _rows()
    audio = [row for row in rows if row["product_id"] == "MF-AUDIO-02"]
    others = [row for row in rows if row["product_id"] != "MF-AUDIO-02"]

    selected = _select(audio + others, (), "Jaká sluchátka mají potlačení hluku?", 3)

    assert selected and {row["product_id"] for row in selected} == {"MF-AUDIO-02"}
    assert any("ANC lze zapnout a vypnout" in row["content"] for row in selected)


@pytest.mark.parametrize(
    "question",
    [
        "Kde je nyní můj kurýr? Jaké je dnešní ETA?",
        "Jaký je stav mojí objednávky?",
        "Kolik stojí iPhone?",
        "Jaké bude zítra počasí v Brně?",
    ],
)
def test_unrelated_question_gets_no_passage_whatever_the_vector_order(question: str) -> None:
    assert _select(_rows(), (), question, 3) == []


def test_vector_literal_is_a_pgvector_text_value() -> None:
    assert vector_literal((1, 0.5, -2e-05)) == "[1.0,0.5,-2e-05]"


def test_sanitizer_keeps_the_question_and_drops_personal_data() -> None:
    text = "\n".join(
        [
            "Dobrý den, kolik stojí AirDock 8 za 2 490 Kč?",
            "Moje objednávka 20261113004567, telefon +420 777 123 456.",
            "Pište na jana.novakova@example.invalid nebo https://example.invalid/u/42",
            "> Dne 12. 11. napsal Reply McFly: starší citovaná odpověď",
            "S pozdravem",
            "Jana Nováková, Dlouhá 12, Praha",
        ]
    )

    question = sanitize_product_question(text)

    assert "kolik stojí AirDock 8 za 2 490 Kč?" in question
    for leaked in ("20261113004567", "777", "@", "example.invalid", "citovaná", "Nováková"):
        assert leaked not in question
    assert len(sanitize_product_question("slovo " * 500)) <= 600
    assert sanitize_product_question("> jen citace\n-- \npodpis") == ""


def _email() -> IncomingEmail:
    return IncomingEmail(
        MessageMetadata("a1", "b1", datetime.now(UTC), frozenset({"INBOX", "UNREAD"})),
        "sender@customer.invalid",
        "Dotaz na AirDock 8",
        "<original@customer.invalid>",
        "",
        "Kolik stojí?",
        has_attachments=True,
        attachment_passages=(AttachmentPassage("attachment:0", "Soukromá faktura 123"),),
        thread_history=(ThreadHistoryPassage("thread:1", "sender@customer.invalid", "Starší"),),
    )


def test_vector_query_contains_subject_and_body_but_no_attachment_or_history() -> None:
    question = build_product_question(_email())

    assert question == "Dotaz na AirDock 8 Kolik stojí?"
    assert "faktura" in build_rag_retrieval_query(_email())  # the local lexical query differs


def test_markdown_stays_the_default_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("MCFLY_RAG_BACKEND", "MCFLY_ENABLE_RAG"):
        monkeypatch.delenv(name, raising=False)
    engine = create_autospec(Engine, instance=True)

    disabled = build_rag(Settings(), engine)
    markdown = build_rag(Settings(enable_rag=True), engine)

    assert Settings().rag_backend == "markdown"
    assert disabled.provider is None
    assert isinstance(markdown.provider, MarkdownRAGProvider)
    assert (markdown.query_builder, markdown.timeout) == (build_rag_retrieval_query, 0.0)


def test_pgvector_backend_is_selected_by_configuration_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MCFLY_ENABLE_RAG", "true")
    monkeypatch.setenv("MCFLY_RAG_BACKEND", "pgvector")
    monkeypatch.setenv("MCFLY_RAG_TOP_K", "2")
    monkeypatch.setenv("MCFLY_RAG_EMBEDDING_MODEL", "synthetic-embedding")
    monkeypatch.setenv("MCFLY_RAG_TIMEOUT_SECONDS", "8")

    components = build_rag(Settings(), create_autospec(Engine, instance=True))

    provider = components.provider
    assert isinstance(provider, PgVectorRAGProvider)
    assert (provider.top_k, provider.embedding_model) == (2, "synthetic-embedding")
    assert (components.query_builder, components.timeout) == (build_product_question, 8.0)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("MCFLY_RAG_BACKEND", "pinecone"),
        ("MCFLY_RAG_EMBEDDING_DIMS", "3072"),
        ("MCFLY_RAG_TOP_K", "0"),
        ("MCFLY_RAG_TOP_K", "4"),
        ("MCFLY_RAG_EMBEDDING_MODEL", ""),
        ("MCFLY_RAG_TIMEOUT_SECONDS", "60"),
    ],
)
def test_invalid_rag_configuration_fails_fast(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    monkeypatch.setenv(name, value)
    with pytest.raises(ValidationError):
        Settings()


def test_configured_dimension_matches_the_database_column() -> None:
    assert RAG_VECTOR_DIMENSIONS == EMBEDDING_DIMENSIONS == Settings().rag_embedding_dims


@pytest.mark.parametrize("top_k", [0, 4])
def test_provider_rejects_more_than_three_passages(top_k: int) -> None:
    with pytest.raises(ValueError, match="RAG_TOP_K_INVALID"):
        PgVectorRAGProvider(
            create_autospec(Engine, instance=True),
            create_autospec(EmbeddingProvider, instance=True),
            embedding_model="synthetic-embedding",
            top_k=top_k,
        )


def test_retrieval_is_not_started_when_the_deadline_cannot_fit_it() -> None:
    provider = MagicMock(spec=RAGProvider)
    service = EmailProcessingService(
        create_autospec(EmailRepository, instance=True),
        create_autospec(GmailPort, instance=True),
        create_autospec(WorkflowRunner, instance=True),
        "agent@agent.invalid",
        create_autospec(ReplyService, instance=True),
        rag=provider,
        enable_rag=True,
        rag_timeout=10.0,
    )

    with pytest.raises(WorkflowError, match="DEPENDENCY_TIMEOUT") as error:
        service._apply_rag(_email(), uuid4(), time.monotonic() + 50)

    assert error.value.retryable is True
    provider.retrieve.assert_not_called()


@pytest.mark.parametrize(
    "question",
    [
        "Kde je moje objednávka?",
        "Kdy mi dorazí balík?",
        "Chci vrátit peníze za objednávku.",
        "Dobrý den, potřebuji fakturu k nákupu z minulého týdne.",
        "Můžete mi poslat sledovací číslo zásilky?",
        "Kolik stojí doprava do Brna?",
        "Jak dlouhá je záruka na zboží?",
        "Nefunguje mi přihlášení do účtu, zapomněl jsem heslo.",
        "Chci reklamovat poškozenou zásilku, krabice byla promáčknutá.",
        "Děkuji za rychlou odpověď, hezký den.",
        "Jaká je aktuální sleva na sluchátka?",
        "Kolik stojí iPhone 15?",
        "Jaký notebook doporučujete pro studenta?",
        "Prodáváte televize s HDMI?",
    ],
)
def test_customer_service_questions_outside_the_catalog_get_no_passage(question: str) -> None:
    rows = _rows()

    assert identify_products(question, PRODUCTS) == ((), False)
    # Independent of how the embedding model happens to rank the chunks.
    assert _select(rows, (), question, 3) == []
    assert _select(rows[::-1], (), question, 3) == []


@pytest.mark.parametrize(
    ("question", "product_id"),
    [
        ("Jaká sluchátka mají potlačení hluku?", "MF-AUDIO-02"),
        ("Jak dlouho vydrží baterie sluchátek se zapnutým ANC?", "MF-AUDIO-02"),
        ("Hledám senzor na teplotu a vlhkost do bytu", "MF-SENSOR-03"),
        ("Funguje senzor na Wi-Fi 5 GHz?", "MF-SENSOR-03"),
        ("Potřebuji dokovací stanici k notebooku s HDMI a Ethernetem", "MF-DOCK-08"),
        ("Kolik monitorů lze připojit k dokovací stanici?", "MF-DOCK-08"),
    ],
)
def test_paraphrase_without_a_product_name_can_only_reach_the_right_product(
    question: str, product_id: str
) -> None:
    rows = _rows()

    for ranked in (rows, rows[::-1]):
        selected = _select(ranked, (), question, 3)
        assert selected and {row["product_id"] for row in selected} == {product_id}
