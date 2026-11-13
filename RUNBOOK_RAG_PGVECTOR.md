# Runbook – vektorový RAG (pgvector + Vertex AI embeddingy)

Stav: implementováno a otestováno lokálně proti skutečnému PostgreSQL s pgvector a
**řízenému fake embeddingu**. Živé Vertex AI embeddingy, Cloud SQL a Gmail E2E s tímto
backendem jsou **NOT VERIFIED** a čekají na schválení (viz poslední kapitola).

## Co to dělá

- Katalog: `src/reply_mcfly/product_catalog/PX01..PX03` – tři fiktivní produkty
  (`MF-DOCK-08`, `MF-AUDIO-02`, `MF-SENSOR-03`), 6 sekcí H2 na dokument = 18 chunků.
  Každý chunk nese název a ID produktu, `chunk_id` (`mf-dock-08:cena-a-obsah-baleni`),
  `content_sha256`, `source_id` (`rag:<chunk_id>:<12 znaků hashe>`) a `provenance`
  (`soubor#sekce@verze`). Zákaznické e-maily ani historie vláken se neindexují.
- Tabulka `rag_product_chunks` (migrace 0004), `embedding vector(768)`, přesné kosinové
  hledání (`ORDER BY embedding <=> …`), bez HNSW/IVFFlat indexu.
- `PgVectorRAGProvider` implementuje stávající `RAGProvider`. Dotaz = předmět + tělo
  e-mailu po očištění (bez citací, podpisu, adres, odkazů a dlouhých čísel, max 600 znaků).
  Přílohy a historie vlákna se do embedding API neposílají.
- Relevance: produkt se pozná podle ID nebo názvu. Jiný model známé řady („AirDock 9“)
  nebo neznámé „McFly <Název>“ nevrátí nic a embedding se vůbec nevolá. Bez jmenovaného
  produktu rozhoduje vektorové pořadí, ale pasáž musí s dotazem sdílet aspoň dvě věcná
  slova a vrací se jen jeden produkt. Pevný práh podobnosti se nepoužívá – vyžadoval by
  kalibraci na živých embeddingách.
- Citace: backend uzná jen `source_id` pasáže vrácené pro daný job a doslovný citát.
  Při opakování s uloženým outboxem se citované pasáže načtou z DB podle `source_id`
  (bez nového embeddingu). Když se dokument mezitím změnil, starý `source_id` neexistuje
  a job končí v `REVIEW_REQUIRED` (`INVALID_EVIDENCE`).

## Konfigurace

| Proměnná | Výchozí | Poznámka |
|---|---|---|
| `MCFLY_ENABLE_RAG` | `false` | beze změny |
| `MCFLY_RAG_BACKEND` | `markdown` | `markdown` nebo `pgvector` |
| `MCFLY_RAG_EMBEDDING_MODEL` | `gemini-embedding-001` | stejný pro indexaci i dotazy |
| `MCFLY_RAG_EMBEDDING_DIMS` | `768` | jiná hodnota se odmítne (sloupec je `vector(768)`) |
| `MCFLY_RAG_EMBEDDING_LOCATION` | prázdné = `GCP_REGION` | region embedding modelu |
| `MCFLY_RAG_TOP_K` | `3` | 1–3 pasáže |
| `MCFLY_RAG_TIMEOUT_SECONDS` | `10` | rozpočet retrievalu; bez něj se volání nezahájí |

Ingress se nemění. Worker potřebuje nad `rag_product_chunks` jen `SELECT`; zápis dělá
pouze administrační příkaz `rag sync --apply` pod oprávněnou identitou.

## Lokální spuštění (demo)

`rag sync --apply` a `rag search` volají Vertex AI (placené, řádově haléře za 18 krátkých
textů) a potřebují ADC s přístupem k projektu. Zápis jde do databáze z `MCFLY_DATABASE_URL`.

```sh
# 1. .env: MCFLY_ENABLE_RAG=true, MCFLY_RAG_BACKEND=pgvector
docker compose up -d --build            # ingress spustí alembic upgrade head
docker compose exec -T ingress alembic current       # očekávej 0005 (head)

# 2. kontrola katalogu a plán (bez sítě / bez zápisu)
docker compose exec -T worker python -m reply_mcfly.rag validate
docker compose exec -T worker python -m reply_mcfly.rag sync

# 3. indexace – skutečné embeddingy + zápis 18 chunků
docker compose exec -T worker python -m reply_mcfly.rag sync --apply
docker compose exec -T worker python -m reply_mcfly.rag sync     # očekávej "to_embed": []

# 4. ověření retrievalu
docker compose exec -T worker python -m reply_mcfly.rag search --query "Kolik stojí AirDock 8?"
docker compose exec -T worker python -m reply_mcfly.rag search --query "Podporuje SoundLoop S2 ANC?"
docker compose exec -T worker python -m reply_mcfly.rag search --query "Měří HomeSense H3 CO₂?"
docker compose exec -T worker python -m reply_mcfly.rag search --query "Kolik stojí AirDock 9?"   # 0 pasáží

# 5. jeden e-mail bez odeslání, potom s odesláním
docker compose exec -T worker python -m reply_mcfly.live_email --message-id GMAIL_MESSAGE_ID
docker compose exec -T worker python -m reply_mcfly.live_email --message-id GMAIL_MESSAGE_ID --send
```

Kontejner musí mít Google přihlašovací údaje stejně jako pro dosavadní volání Gemini.
Při běhu z hostitele nahraď `docker compose exec -T worker python` za `uv run python`
a nastav `MCFLY_DATABASE_URL`.

Očekávané pasáže (skutečná `source_id` z katalogu):

| Dotaz | První pasáž | Fakt |
|---|---|---|
| Kolik stojí AirDock 8? | `rag:mf-dock-08:cena-a-obsah-baleni:192ff842dafd` | 2 490 Kč včetně DPH |
| Podporuje SoundLoop S2 ANC? | `rag:mf-audio-02:pripojeni-a-funkce:6637746da9a6` nebo `…:popis-produktu:d23f4e612f58` | ANC lze zapnout a vypnout |
| Měří HomeSense H3 CO₂? | `rag:mf-sensor-03:mereni-a-provoz:6d71bdc8bcda` | Produkt neměří CO₂ |

Pořadí pasáží uvnitř produktu určuje živý model; lokálně je ověřeno jen s fake embeddingem.

## Oprávnění v databázi

Worker má znalostní tabulku jen číst; zapisuje do ní pouze indexace. Ostatní provozní
tabulky (`mailbox_sync_state`, `email_jobs`, `email_outbox`, `alembic_version`) zůstávají
Workeru beze změny. Šablona níže **nebyla spuštěna**; role doplňte podle skutečných
uživatelů v Cloud SQL a spusťte ji jako vlastník tabulky až po migraci 0004.

```sql
-- Samostatná identita pro `rag sync --apply` (heslo/IAM mimo repozitář).
CREATE ROLE mcfly_rag_indexer LOGIN;
GRANT USAGE ON SCHEMA public TO mcfly_rag_indexer;
GRANT SELECT, INSERT, UPDATE, DELETE ON rag_product_chunks TO mcfly_rag_indexer;
GRANT SELECT ON alembic_version TO mcfly_rag_indexer;   -- CLI vypisuje stav migrace

-- Worker: čtení znalostí, žádný zápis. <worker_role> = DB uživatel služby reply-mcfly-worker.
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON rag_product_chunks FROM <worker_role>;
GRANT SELECT ON rag_product_chunks TO <worker_role>;
```

Pokud je `<worker_role>` zároveň vlastníkem tabulky (spouštěl migrace), `REVOKE` ho
neomezí. Oddělení pak vyžaduje, aby migrace spouštěl jiný uživatel než Worker, nebo
`ALTER TABLE rag_product_chunks OWNER TO <migrační_role>`. Indexace se spouští s vlastním
`MCFLY_DATABASE_URL` identity `mcfly_rag_indexer`; Worker ji nikdy nepoužívá.

## Změna dokumentu

1. Uprav soubor v `product_catalog/` a zvyš `**Verze znalostí:**`.
2. `rag validate`, potom `rag sync` (dry-run ukáže `to_embed` / `to_delete`).
3. `rag sync --apply`. Vše proběhne v jedné transakci pod zámkem tabulky: čtenář vidí
   buď starý, nebo nový stav, nikdy směs verzí. Nezměněné chunky se znovu neembedují.
4. Rozpracované odpovědi citující starou verzi skončí v `REVIEW_REQUIRED`.

Změna `MCFLY_RAG_EMBEDDING_MODEL` vyžaduje `rag sync --apply` (přeembeduje všech 18 chunků).
Worker čte jen řádky svého modelu, takže do reindexu nevrátí nic. Jiná dimenze než 768
vyžaduje novou migraci.

## Chybové stavy

| Kód | Kdy | Výsledek jobu |
|---|---|---|
| `EMBEDDING_UNAVAILABLE` | timeout / výpadek spojení k Vertex AI | `RETRY_PENDING` |
| `EMBEDDING_API_ERROR` | 429/5xx → opakovat; 4xx (model/region/IAM) → ne | `RETRY_PENDING` / `REVIEW_REQUIRED` |
| `EMBEDDING_INVALID` | špatná dimenze, NaN/Inf, nulový nebo prázdný vektor | `REVIEW_REQUIRED` |
| `RAG_DATABASE_UNAVAILABLE` | výpadek DB při retrievalu | `RETRY_PENDING` |
| `RAG_VERSION_CONFLICT` | dvě verze jednoho dokumentu ve výsledku | `REVIEW_REQUIRED` |
| `DEPENDENCY_TIMEOUT` | na retrieval nezbývá čas v rámci 100 s | `RETRY_PENDING` |
| `INVALID_EVIDENCE` | vymyšlený `source_id`, upravený citát, změněný dokument | `REVIEW_REQUIRED` |

Při žádné z těchto chyb se neodesílá odpověď a nepoužije se potichu jiná znalostní báze.
Nulový výsledek retrievalu není chyba: model dostane prázdné `rag_passages` a má zvolit
schválený fallback.

Telemetrie `rag_retrieval`: `embedding_latency_ms`, `vector_query_latency_ms`,
`rag_total_latency_ms`, `rag_hit_count`, `rag_error_code`, `embedding_model`,
`document_version`. Událost `rag_context_attached` nese `job_id` a počet pasáží.
Text dotazu ani obsah e-mailu se nelogují.

## Rozpočet času

Zpracování má 100 s. Přílohy nejvýše 25 s, retrieval nejvýše `MCFLY_RAG_TIMEOUT_SECONDS`
(výchozí 10 s; SQL dotazy mají `statement_timeout` 3 s), generování nejvýše 30 s a před
odesláním musí zbývat 45 s. S přílohami i RAG v nejhorším případě job skončí
`DEPENDENCY_TIMEOUT` a zopakuje se. Skutečná latence proti limitu 120 s není změřena.

## Návrat k Markdown režimu

Nastav `MCFLY_RAG_BACKEND=markdown` (nebo `MCFLY_ENABLE_RAG=false`) a restartuj Worker.
Tabulku není nutné mazat; `alembic downgrade 0003` ji odstraní. Odeslané e-maily ani
uložený outbox se nemění. Rozpracované odpovědi s citacemi `rag:mf-…` po přepnutí
neprojdou znovuověřením a skončí v `REVIEW_REQUIRED`.

## Cloud – kroky čekající na schválení

Nic z toho nebylo provedeno:

1. Ověřit dostupnost `gemini-embedding-001` ve schváleném regionu
   (`MCFLY_RAG_EMBEDDING_LOCATION`); model nespouštět přes globální endpoint bez schválení.
2. Na Cloud SQL spustit `alembic upgrade head` (0004 tabulka RAG, 0005 sloupec outboxu).
3. Nastavit oddělená oprávnění podle kapitoly „Oprávnění v databázi“.
4. `rag sync --apply` proti Cloud SQL (zápis 18 chunků, 18 volání embedding API).
5. `rag search` pro tři referenční dotazy a jeden negativní.
6. Nastavit Workeru `MCFLY_RAG_BACKEND=pgvector` a nasadit.
7. Skutečný e-mail → odpověď ve stejném vlákně; změřit dobu od přijetí do Sent (< 120 s).
