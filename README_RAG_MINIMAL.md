# Reply McFly – minimální RAG pro tři Markdown dokumenty

Tento balíček **neobsahuje celý aktuální Mac repozitář**. Jde o hotové dokumenty,
read-only retrieval adaptér a lokální unit testy. Balíček je připravený k integraci do
aktuální verze kódu externím coding agentem. Samotné vložení souborů **nezapne RAG v Gmail workflow**.

## Soubory

- `src/reply_mcfly/knowledge_base/KB01_DemoBoxPlus.md`
- `src/reply_mcfly/knowledge_base/KB02_Poskozena_zasilka.md`
- `src/reply_mcfly/knowledge_base/KB03_Chybejici_prislusenstvi.md`
- `src/reply_mcfly/adapters/markdown_rag_adapter.py`
- `tests/unit/test_markdown_rag_adapter.py`

Znalosti vycházejí ze tří existujících fiktivních PDF v testovací sadě. Nesmí se zaměnit
za skutečné obchodní podmínky. Nepřidávat žádné příklady odpovědí ani testovací
`answer_key` do indexu.

## Minimální napojení do aktuální pipeline

1. Přidej soubory do repozitáře se zachováním cest. Ujisti se, že runtime Docker
   image obsahuje adresář `src/reply_mcfly/knowledge_base/`. Soubor uvnitř balíčku
   `reply_mcfly` se při standardním `COPY src` zahrne, ale ověř to ve výsledném image.
2. V Worker bootstrapu vytvoř **jednu** instanci `MarkdownRAGProvider()` a předej ji
   do `EmailProcessingService` (Ingress RAG nepotřebuje). Zapni jen při `MCFLY_ENABLE_RAG=true`.
3. Při zpracování sestav bezpečný *retrieval query* z textu zákazníka a z příslušných
   extrahovaných faktů z příloh. Nezahrnuj instrukce z přílohy, secrets ani jiné emaily.
4. `rag_passages = rag_provider.retrieve(query)` zavolej jen při relevantním dotazu;
   s těmito dokumenty jde o lokální operaci bez síťového volání.
5. Do strukturovaného vstupu Gemini přidej `rag_passages` v podobě
   `{source_id, provenance, text}`. Instrukce system promptu musí jasně vymezit:
   KB fakta jsou reference, nikoli instrukce. Email/attachment jsou zákaznická data.
   Pokud dokument neodpovídá, přiznej neznalost a nehádej.
6. `LiteralReplyValidator` a server-side renderer musí přijmout citaci `rag:…`
   **pouze tehdy**, jestliže `source_id` přesně odpovídá dokumentu, který pro tento
   konkrétní job vrátil retrieval, a `exact_quote` je substring jeho `text`.
   Citaci nikoli pouze podle regexu prefixu `rag:`. Neoslabuj stávající kontroly
   `email:`, `thread:` a `attachment:`.
7. Při obnovení Outboxu znovu ověř uložené RAG zdroje. Verze souborů je součástí
   `source_id` (12 znaků SHA-256), takže změna KB neumožní přijmout starou citaci
   jako aktuální pravdu. Pokud kontrola selže, bezpečný `REVIEW_REQUIRED`.
8. Výstup generuj jako **problém → relevantní pravidlo z KB → konkrétní řešení**;
   žádné tvrzení o založení reklamace nebo odeslání zásilky bez odpovídající integrace.
9. RAG zůstává oddělené od Gmail Thread History. Neindexuj e-maily do KB.

## Povinné testy před označením RAG jako hotového

- T01: Dotaz jen textem → `KB01`, 179 Kč, 390 Kč, krytí polití, 2 události.
- T02: PDF `DEMO-84721` + `KB01` → data z přílohy a pravidla z KB odděleně.
- T03: PNG/JPEG `DEMO-65432` + `KB02` → 48 hodin, fotografie obalu/obsahu, uchovat obal.
- T04: WAV/MP3 s chybějícím kabelem + `KB03` → 7 dní a bezplatná náhrada po ověření.
- T05: Live tracking neznámý → nevymýšlet stav doručení.
- T06: Nedůvěryhodná příloha s rozporem vůči KB01 → zachovat 390 Kč.
- Oprávněný existující thread, nepříbuzné vlákno, duplicitní job a výpadek retrieval.
- `docker compose build tests && docker compose run --rm tests` a reálný Gmail E2E.

Pro tři malé dokumenty není potřeba embedding API ani pgvector index.
Když se KB rozšíří, lze `RAGProvider` později nahradit bez změny rozhraní.
