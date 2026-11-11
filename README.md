# Reply McFly agent

Lokální textový workflow navazující na RM-001 a schválených upřesnění.
Python 3.12, FastAPI Ingress a Worker ze stejného image, PostgreSQL 17 / pgvector,
SQLAlchemy 2 a Alembic.

Adresář `docs/` je v `.gitignore` a **není součástí Gitu** (blueprint, JSON požadavky,
Cloud Shell runbook a handoffy drž lokálně mimo verzování). Klon repozitáře je jen
aplikace, migrace a tento README.

**Lokální část je ověřená; skutečný Gmail/GCP E2E a cíl 120 sekund jsou NESPLNĚNÉ.**
Cloud Shell příkazy a inventura jsou v lokálním `docs/operations/GCP_CLOUD_SHELL.md`, pokud
máš projektový balíček dokumentace k dispozici.

## Spuštění v Dockeru

Potřebuješ spuštěný Docker Engine a Docker Compose v2 nebo novější.
Všechny následující příkazy spouštěj v kořeni tohoto repozitáře.

```sh
test -f .env || cp .env.example .env
docker compose up --build -d --wait
docker compose ps
curl --fail http://localhost:8080/health
curl --fail http://localhost:8081/health
```

Před prvním spuštěním nastav v ignorovaném `.env` vlastní lokální
`POSTGRES_PASSWORD` (použij hexadecimální znaky, protože je součástí databázového URL).
Případný existující `.env` zachovej. Heslo se předává za běhu, nevkládá se do image.
Pro změnu portů uprav `INGRESS_PORT` a `WORKER_PORT` v `.env`.

Běžně běží přesně tři služby: `postgres`, `ingress`, `worker`.
Ingress při startu provede `alembic upgrade head`; Worker čeká na zdravý Ingress.
Migraci tak automaticky nespouštějí dva procesy současně.
Tento postup je určen pro lokální Compose prostředí.

Oba health endpointy vracejí `200` s `status`, `service` a `database`.
Ověřují dostupnost tabulky `mailbox_sync_state`, Alembic revize a pgvector.
Při nedostupné nebo neinicializované DB vracejí `503` bez interních detailů.
HTTP porty jsou vystavené jen na loopbacku; PostgreSQL nemá port na hostiteli.
OIDC validace je implementovaná; skutečné Cloud Run IAM a cloudový deployment nejsou ověřené.
V cloudu může Ingress běžet bez databáze: health pak pravdivě vrací `database: not_used`.
Worker databázi vyžaduje. Lokální Compose dál ověřuje DB u obou služeb.

## Testy v Dockeru

```sh
docker compose run --build --rm tests
docker compose run --rm tests ruff check src tests migrations typings
docker compose run --rm tests ruff format --check src tests migrations typings
docker compose run --rm tests mypy
docker compose exec -T ingress alembic check
docker compose run --rm tests bandit -r src -q
docker compose run --rm tests pip-audit --local --skip-editable --progress-spinner off
```

Testovací profil vytvoří dočasný čtvrtý kontejner ze stage `test` stejného
Dockerfile. Google adaptéry a dispatch jsou v integračních testech fake; databáze je skutečný PostgreSQL.
HTTP test vede přes `/events/gmail`, `/tasks/sync` a `/tasks/process`. Ověřuje
GENERATED/FALLBACK, uložený outbox, deduplikaci a bezpečné odmítnutí.
Další testy kontrolují skutečné kryptografické OIDC podpisy se syntetickým klíčem,
MIME/reply hlavičky, SQL lease včetně souběhu a stavu DELIVERY_UNKNOWN.
Vkládají jen syntetické mailboxy a po sobě odstraňují vlastní záznamy.
Chybějící `TEST_DATABASE_URL` při integračním běhu je chyba, nikoliv přeskočený test.

## Zápis, čtení a restart

Interní diagnostická služba zapisuje syntetický záznam do skutečné blueprintové
tabulky `mailbox_sync_state`; neexistuje zapisovací HTTP endpoint.

```sh
MAILBOX_ID=$(docker compose exec -T worker python -m reply_mcfly.smoke)
docker compose restart postgres
docker compose up -d --wait
docker compose exec -T worker python -m reply_mcfly.smoke --verify "$MAILBOX_ID"
```

Očekávaný výsledek je `Persistence check: OK`. Záznam zůstává v pojmenovaném
volume `postgres_data`. `docker compose stop` nebo `docker compose down`
zastaví prostředí a zachová data. Parametr `down -v` smaže volume i data.
Změna hesla v `.env` nemění heslo již inicializované databáze.

## Textový workflow a bezpečnostní hranice

- Ingress přijme OIDC ověřenou Pub/Sub notifikaci, validuje schránku a zajistí Sync Task.
- Sync čte Gmail History od uloženého checkpointu; nové příchozí nepřečtené zprávy eviduje
  v `email_jobs`. Checkpoint se posune až po zajištění Process Tasks.
- Worker atomicky rezervuje job s UUID lease tokenem; zastaralý proces nesmí přepsat jeho stav.
- Gmail adaptér používá OAuth ze Secret Manageru. Připravuje text, MIME a reply hlavičky.
- Gemini vrací strukturovaný návrh s důkazy. Backend dovolí jen doslovné pasáže
  aktuálního e-mailu ve formátu s výslovným připsáním odesílateli; nejde o ověření pravdivosti.
- Příjemce je původní From z explicitního allowlistu; Reply-To se ignoruje.
  Samotný From není ověření identity. Vlastní a rozpoznané automatické zprávy se neodesílají.
- Schválené fallback texty jsou v `domain/reply_templates.py` a kontrolují je golden testy.
  LLM je nepřepisuje; outbox uchovává `response_type`, `fallback_reason` a důkazy.
- Neověřitelný výstup či bezpečnostní riziko vede do REVIEW_REQUIRED bez sendu.
  Nejasné odeslání vede do DELIVERY_UNKNOWN; retry pouze dohledá Sent a nikdy automaticky
  nezopakuje send. Nepotvrzený výsledek přechází k ruční kontrole.

Fake Google služby se připojují přes porty v testovací kompozici. Produkční entrypointy
používají skutečné adaptéry a žádný přepínač nevypíná jejich autentizaci.
Dokud není schránka, allowlist, OAuth a routing nakonfigurovaný, workflow vrací 503
(neautorizované požadavky 401), health zůstává dostupný. Lokálně se skutečné e-maily neposílají.

Reprodukovatelný lokální HTTP průchod s JSON auditními logy:

```sh
docker compose run --rm tests pytest -q -s tests/integration/test_email_workflow.py::test_http_pipeline_and_duplicate_notification
```

## Lokální live-email (mimo Pub/Sub)

Volitelný průchod **jedné** Gmail zprávy přes stejný processing stack jako Worker.
Default je **dry-run** (`READY_TO_SEND`, bez `gmail.send`). Skutečné API volání vyžaduje
OAuth soubor mimo repozitář a explicitní allowlist v `.env`; `--send` použij jen po schválení.

```sh
# Po docker compose up a lokálním OAuth (viz oauth_setup); credentials mimo repo, mode 0600
docker compose exec -T worker python -m reply_mcfly.live_email --message-id GMAIL_MESSAGE_ID
```

Příklad s odesláním (jen po vlastním schválení schránky a allowlistu):

```sh
docker compose exec -T worker python -m reply_mcfly.live_email --message-id GMAIL_MESSAGE_ID --send
```

Struktura: `api/` řeší HTTP a autentizaci, `application/` orchestraci, `domain/` pravidla
příjemce, grounding a šablony, `ports/` rozhraní, `adapters/` PostgreSQL/Google I/O.
Migrace 0002 přidává jobs/outbox a fencing tokeny; 0003 důkazy a constraint odpovědi.
Cloud Run Ingress má jen queue a OIDC závislosti; Worker má Gmail/LLM/persistence.
Malé lokální typové stuby v `typings/` doplňují chybějící SDK anotace, nevalidují API data;
ta procházejí Pydantic a doménovými kontrolami. Závislosti jsou uzamčené v `uv.lock`.
Runtime běží jako non-root, bez `.env`, testů, docs, Git historie a buildovacího `uv`.

Conversation History, RAG a Live Web Search mají rozhraní v `ports/capabilities.py`;
jejich implementace je navazující práce a všechny tři zůstávají povinné pro finální PoC.
Podporované přílohy se v textovém slice neinterpretují a míří k ruční kontrole.
U zjištěného nepodporovaného MIME může následovat schválený fallback; bezpečně ověřitelný
text může projít i bez využití takové přílohy. Detekce poškození a kontrola skutečných
signatur souborů bude součástí samostatného attachment inkrementu.

## Historické lokální výsledky před rekonstrukcí Git historie

11. 11. 2026, Docker Desktop / Linux ARM64, Python 3.12.16:

| Skutečně spuštěná kontrola | Výsledek |
|---|---|
| `docker compose up --build -d --wait` | PASS; 3 healthy služby |
| `docker compose run --build --rm tests` | **60 passed in 2.28s**; 27 PostgreSQL/HTTP integrací + 33 unit testů, bez skipů |
| Ruff lint a format | PASS; 44 Python/stub souborů |
| mypy strict | PASS; 41 zdrojových/testovacích souborů |
| `alembic upgrade head` / `alembic check` | PASS; head 0003, bez rozdílu proti modelům |
| Upgrade → downgrade → upgrade v nové dočasné DB | PASS; izolovaný roundtrip a shoda modelů |
| Živé lokální health a autentizace | PASS; oba health 200, oba neautorizované POST 401 |
| Shodný image a oddělení runtime | PASS; stejný image obou služeb, UID 10001, bez `.env`, tests, docs a `uv` |
| Cloud Shell příkazy | 16 bloků prošlo `bash -n`; nebyly provedené proti GCP |
| Bandit | PASS; bez potlačených pravidel |
| pip-audit | PASS; bez známých zranitelností auditovaných závislostí; vlastní editable balíček vynechán |
| Gitleaks 8.30.0 | PASS; verzovatelné soubory bez nalezených secrets |
| Trivy 0.76.2, runtime image | **FAIL** při prahu HIGH/CRITICAL: 0 CRITICAL, 47 HIGH, 11 CVE v Debianu, 0 secrets |

Gitleaks a sken obsahu image proběhly bez sítě s oficiálními images uzamčenými digestem.
Trivy databáze byla stažena odděleně. Pro zbývajících 47 HIGH nálezů scanner neuvádí
opravenou verzi; nejsou potlačené a dosažitelnost nebyla samostatně analyzována.
Bezpečnostní gate před merge/release zůstává otevřený.

U RM-001 byl navíc skutečně ověřen restart PostgreSQL a zachování syntetického záznamu,
HTTP 503 při výpadku DB a návrat na 200. Nový workflow testuje commit, rezervace a obnovu
expirovaného lease; netvrdí skutečnou obnovu cloudových služeb.

**NESPLNĚNO / NEPROVEDENO:** cloudový Gmail/GCP E2E, živé OAuth a Gemini `eu`,
modelové kvóty, skutečná latence pod 120 s, Cloud Run/AMD64 build a provoz, CI,
cloudové bezpečnostní a release gates. Automatický full resync při HISTORY_EXPIRED
ani Scheduler recovery nejsou hotové; checkpoint se bez kontroly nepřeskakuje.
IAM, placené prostředky, commit ani deployment v tomto kroku nebyly změněné/provedené.

**OAuth: OTEVŘENO.** Připravený přihlašovací postup nebyl spuštěn; získání tokenu,
potvrzení dedikované schránky a allowlistu zůstává na navazující krok.


## Ověření při rekonstrukci Git historie — 11. 11. 2026

C01–C20 a B01–B09 jsou logická rekonstrukce současných zdrojů, nikoliv původní
historické snapshoty. Přehled commitů a merge větví drž lokálně v `docs/` (mimo Git).
Původní aplikační zdroje, dependency verze a `.gitignore` zůstaly zachované.
Doplněny byly testy Gemini SDK, OAuth/Watch a repository kontraktů z plánu.

Nově skutečně provedené kontroly v izolovaném lokálním prostředí:

| Kontrola | Výsledek |
|---|---|
| Finální Docker build a start | PASS; 3 healthy služby, oddělený Compose projekt, testovací DB v RAM |
| Finální Docker pytest | **76 passed in 2.17s**; 31 PostgreSQL/HTTP integrací a 45 unit testů, bez skipů |
| Ruff lint / format, strict mypy, Bandit | PASS v meziverzích i finálním Docker test image |
| Alembic upgrade a kontrola modelů | PASS u všech kódových meziverzí; head 0003 |
| Alembic downgrade base → upgrade head → check | PASS, pouze samostatná dočasná testovací DB |
| Runtime a autentizace | PASS; UID 10001, health 200, nepřihlášený Worker POST 401, vyloučené lokální soubory |
| `bash -n` dokumentovaných shell bloků | PASS; 20 bloků z README a Cloud Shell runbooku, bez provedení cloudových příkazů |
| pip-audit | PASS; bez známých zranitelností, vlastní editable balíček vynechán |
| Gitleaks | PASS; offline kontrola snímku i finálního worktree bez nálezů |
| Nový Trivy runtime scan | **FAIL**; 47 HIGH / 11 CVE, 0 CRITICAL, žádná uvedená opravená verze, 0 secrets |

Skenovaný runtime image ID:
`sha256:51c48802d7735c4aee4a4ea68b81aba67654799fa4277e7828b854390fbdb841`.

Vlastník výslovně schválil lokální merge rekonstrukce s evidencí neúspěšných nebo
neověřených gates. Tato výjimka není schválením release, deploymentu ani cloudových změn.
Docker build/start a nový image audit proběhly pro finální snímek; samostatný Docker
build a image audit každé rekonstruované větve nebyly provedené. Restart persistence
a DB outage/recovery nebyly při rekonstrukci znovu ověřené; starší výsledky výše jsou historické.
Skutečné OAuth, Gmail/GCP E2E, latence 120 s a Cloud Run/AMD64 zůstávají neověřené.

## Ověření po sjednocení do main — 11. 11. 2026

| Kontrola | Výsledek |
|---|---|
| `docs/` v indexu Gitu | PASS; adresář jen lokálně, `.gitignore` |
| `docker compose run --build --rm tests` | **90 passed in 4.17s**; + dry-run integrace a live-email unit testy, bez skipů |
| Trivy runtime | **FAIL** beze změny (47 HIGH z rekonstrukce); release gate otevřený |

Skutečné Gmail/Vertex volání v `live_email` nebylo součástí Docker pytest; jen fake/mocked testy.
