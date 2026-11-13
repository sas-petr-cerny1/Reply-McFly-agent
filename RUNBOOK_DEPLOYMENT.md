# Runbook – nasazení `version2` do existujícího Google Cloud

Nic z tohoto dokumentu nebylo provedeno. Příkazy `gcloud` jsou návrh pro projekt
`reply-mcfly-poc` / `europe-west1`; hodnoty v `<…>` doplňte podle skutečného prostředí.
Sestavení image a spuštění migrací proveďte stejným postupem jako u migrací 0001–0003.

## 0. Gmail Watch – termín nezávislý na nasazení

Watch byl aktivován 12. 11. 2026 a žije 7 dní: **bez obnovy vyprší 19. 11. 2026**. Obnovuje
ho jen `users.watch`, které volá `python -m reply_mcfly.bootstrap`. Opakované spuštění je
bezpečné i se současným image: uloží nové vypršení a existující checkpoint nepřepíše
(ověřeno testem `tests/integration/test_bootstrap_renewal.py`).

```sh
gcloud run jobs execute reply-mcfly-gmail-bootstrap --region europe-west1 --wait
```

Denní spouštění přes Cloud Scheduler (nová komponenta, až po schválení):

```sh
gcloud scheduler jobs create http reply-mcfly-watch-renewal \
  --location europe-west1 --schedule "17 3 * * *" --time-zone "Europe/Prague" \
  --http-method POST \
  --uri "https://run.googleapis.com/v2/projects/reply-mcfly-poc/locations/europe-west1/jobs/reply-mcfly-gmail-bootstrap:run" \
  --oauth-service-account-email <scheduler-sa>   # potřebuje roles/run.invoker na jobu
```

Selhání jobu je vidět jako neúspěšná exekuce; doporučený alert: žádná úspěšná exekuce za
48 hodin. `MCFLY_MAILBOX_ID` se nově normalizuje na malá písmena. Pokud je v jobu nebo ve
Workeru zapsán s velkými písmeny, ověřte před nasazením klíč v `mailbox_sync_state`.

## 1. Co se nasazením změní

- **Schéma:** 0004 přidá tabulku `rag_product_chunks`, 0005 sloupec
  `email_outbox.attachment_passages` s výchozí hodnotou. Obě změny jsou přídavné; současný
  kód s novým schématem funguje, proto se migruje **před** nasazením kódu.
- **Beze změny konfigurace** zůstává RAG v režimu `markdown` (KB01–KB03) jako dnes.
- **Nové chování:** přísnější kontrola citací (hranice slov), předmět e-mailu jde modelu
  a do vyhledávání, limit `MCFLY_SENDER_DAILY_REPLY_LIMIT` (výchozí 20 odpovědí na
  odesílatele za 24 h), odpovědi nesou hlavičku `X-Reply-McFly-Job`, `DELIVERY_UNKNOWN` se
  dohledává ve vlákně, sync přeskočí smazané zprávy a ukládá checkpoint po stránkách.

## 2. Postup

1. **Záloha:** on-demand backup instance `reply-mcfly-db-2`.
2. **Image:** sestavit z větve `version2` přes Cloud Build, zaznamenat digest.
3. **Migrace:** `alembic upgrade head` novým image proti Cloud SQL; očekávaný stav
   `0005 (head)`, `alembic check` bez rozdílu. Migrace už neběží s 3s `statement_timeout`.
4. **Worker bez provozu:** `gcloud run deploy reply-mcfly-worker --image <digest>
   --region europe-west1 --no-traffic --tag v2`; ověřit `GET /health` na tagované URL.
5. **Přepnutí Workeru:** `gcloud run services update-traffic reply-mcfly-worker
   --to-tags v2=100 --region europe-west1`. Ingress stejným způsobem (jeho kód se mění
   jen logováním chyb).
6. **Bootstrap job:** aktualizovat image jobu a jednou spustit (viz kapitola 0).
7. **Kouřový test:** e-mail z povolené adresy → odpověď ve stejném vlákně; druhý se
   stejným Pub/Sub doručením nesmí odeslat podruhé; jeden s přílohou (MP3).
8. **pgvector až potom, samostatně:** oprávnění → `rag sync --apply` identitou indexace →
   `rag search` → `MCFLY_RAG_BACKEND=pgvector` na Workeru. Postup je v
   `RUNBOOK_RAG_PGVECTOR.md`. Předtím ověřit dostupnost `gemini-embedding-001` v regionu.

## 3. Rollback

- **Kód:** `gcloud run services update-traffic <service> --to-revisions <předchozí>=100`.
  Předchozí revize se schématem 0005 funguje; databázi není třeba vracet.
- **RAG:** `MCFLY_RAG_BACKEND=markdown` a nová revize Workeru. Tabulka může zůstat.
- **Schéma (jen při nutnosti):** `alembic downgrade 0003` novým image. Smaže tabulku RAG
  a uložené pasáže příloh u rozpracovaných odpovědí; odeslané e-maily se nemění.
- Rozpracované joby po rollbacku: odpovědi připravené novým kódem starý kód znovu ověří
  svými pravidly a při neshodě skončí v `REVIEW_REQUIRED`; nic se neodešle dvakrát.
- Limit odesílatele lze uvolnit bez rollbacku zvýšením `MCFLY_SENDER_DAILY_REPLY_LIMIT`.

## 4. Měření E2E latence (cíl < 120 s)

Worker u každé odeslané odpovědi loguje `email_sent` s `duration_seconds` = čas od
přijetí zprávy Gmailem (`internalDate`) do potvrzeného odeslání. To je měřená veličina.

```sh
gcloud logging read \
  'resource.labels.service_name="reply-mcfly-worker" AND jsonPayload.event="email_sent"' \
  --project reply-mcfly-poc --freshness 1d --limit 200 \
  --format 'value(timestamp, jsonPayload.job_id, jsonPayload.duration_seconds)'
```

- Vzorek: alespoň 10 zpráv od každého typu – čistý text, text + RAG, příloha (PDF, MP3,
  WAV, JPEG, PNG), odpověď ve vlákně s historií. Vyhodnotit maximum a p95, ne průměr.
- Rozpad času: `rag_retrieval` (`embedding_latency_ms`, `vector_query_latency_ms`,
  `rag_total_latency_ms`), `processing_started` a `job_transition` se stejným `job_id`.
- Kontrola nezávislá na logu: rozdíl `internalDate` příchozí a odeslané zprávy ve vlákně.
- Měřit i studený start (první zpráva po nečinnosti) a opakovaný pokus Cloud Tasks; job
  ve stavu `RETRY_PENDING` se do limitu počítá od původního přijetí.
- `duration_seconds` porovnává hodiny Gmailu a Workeru; odchylka je v řádu sekund.
