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
  `historyId` přijímá jako desetinný řetězec nebo kladné JSON celé číslo; číslo převede
  na řetězec se stávajícím limitem 32 znaků. Boolean a desetinná čísla odmítá.
- Sync čte Gmail History od uloženého checkpointu; nové příchozí nepřečtené zprávy eviduje
  v `email_jobs`. Checkpoint se posune až po zajištění Process Tasks.
- Gmail Watch žije 7 dní a obnovuje ho jen volání Gmail API `users.watch`; sync ho
  neobnovuje. Obnovu dělá `python -m reply_mcfly.bootstrap` (Cloud Run Job
  `reply-mcfly-gmail-bootstrap`), který je bezpečné spouštět denně: uloží nové vypršení,
  ale existující synchronizační checkpoint nikdy nepřepíše.
- Když Gmail odmítne uložený checkpoint (`HISTORY_EXPIRED`), sync zařadí nejnovějších
  100 nepřečtených zpráv z Inboxu a naváže na aktuální `historyId`. Starší nepřečtenou
  poštu musí zkontrolovat operátor.
- Worker atomicky rezervuje job s UUID lease tokenem; zastaralý proces nesmí přepsat jeho stav.
- Gmail adaptér používá OAuth ze Secret Manageru. Připravuje text, MIME a reply hlavičky.
- Gemini vrací strukturovaný návrh s důkazy. Backend dovolí jen doslovné pasáže
  aktuálního e-mailu ve formátu s výslovným připsáním odesílateli; nejde o ověření pravdivosti.
- Příjemce je původní From z allowlistu (`MCFLY_ALLOWED_SENDERS`) nebo z libovolného
  platného externího odesílatele v režimu `["*"]` (wildcard musí být jediná položka).
  Reply-To se ignoruje. Samotný From není ověření identity. Schránka asistenta, automatické
  odpovědi a typické bounce/no-reply odesílatele se neodesílají. Jednomu odesílateli odejde
  nejvýše `MCFLY_SENDER_DAILY_REPLY_LIMIT` odpovědí za 24 hodin (výchozí 20); další zprávy
  končí v REVIEW_REQUIRED s kódem `SENDER_REPLY_LIMIT_REACHED`.
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

### Jednoduchý lokální E2E: RAG + conversation history + thread messages

V aktuální aplikaci je conversation history tvořená staršími zprávami **stejného Gmail
vlákna** (`thread_history`), včetně odpovědí agenta. Nejde o další samostatnou paměť
konverzací. RAG používá oddělenou lokální Markdown KB; e-maily se do ní neindexují.

Opakovatelný test bez skutečného odesílání a bez OAuth:

```sh
docker compose build tests
docker compose run --rm --no-deps tests pytest -v tests/integration/test_email_workflow.py -k test_local_rag_conversation_e2e
```

Předpoklad: PostgreSQL a migrace již běží (`docker compose up -d --wait`). Test používá
skutečné Gmail/Gemini adaptéry, MIME parser, Markdown retrieval, validátor, PostgreSQL
a outbox. Google API jsou mockovaná až na hranici SDK; tento test neověřuje živý model
ani Gmail doručení. Syntetické DB záznamy po sobě odstraní.

Scénář má starší zákaznickou zprávu s `RM-E2E-105`, starší automatickou odpověď agenta
„Prosíme o datum převzetí zařízení.“ a nový dotaz bez těchto údajů. Odpověď musí použít
oba historické zdroje `thread:…` a pravidlo o spoluúčasti `390 Kč` z `rag:KB01_…`.
Test kontroluje také vynechání cizího odesílatele a budoucí zprávy, dry-run bez sendu,
obnovení uloženého outboxu, reply hlavičky a opakované zpracování se stejným jobem
a jediným voláním send. Celkem běží čtyři varianty zapnutí/vypnutí historie a RAG;
při neúplném kontextu řízená odpověď modelu volí schválený fallback.

### Stejný scénář se skutečným Gmailem a Gemini

Tento ruční test používá existující lokální helper `~/Downloads/reply_mcfly_send_once.py`
(není součástí repozitáře), připravené OAuth/ADC a stávající allowlist. Příkazy se
spouštějí v kořeni projektu. `--send` skutečně odešle odpověď.

1. Z povolené zákaznické adresy pošli do dedikované schránky novou zprávu s unikátním
   předmětem `RM POC RAG HISTORY 01` a textem:

   ```text
   Dobrý den,

   číslo mého testovacího požadavku je RM-POC-7429.
   Moje zařízení se službou DemoBox+ bylo náhodně polité vodou.

   Prosím potvrďte, jaké číslo požadavku a jaký problém jsem uvedl.

   Děkuji.
   ```

   Zpráva musí být v INBOX a nepřečtená. Zpracuj ji:

   ```sh
   MCFLY_ENABLE_RAG=true MCFLY_ENABLE_THREAD_HISTORY=true \
     uv run python ~/Downloads/reply_mcfly_send_once.py \
     --subject "RM POC RAG HISTORY 01" --send
   ```

   Očekávání: `SENT`, jedna nová odpověď ve stejném vlákně, obsahuje `RM-POC-7429`.

2. V zákaznické schránce otevři první doručenou odpověď od agenta a přímo u ní použij
   **Odpovědět**. Ponech předmět: Gmail musí zachovat stejné `threadId`; nový e-mail
   se stejným předmětem může založit jiné vlákno bez historie. Odstraň automaticky
   citovaný původní text, aby číslo požadavku nebylo i v aktuální zprávě. Pošli pouze:

   ```text
   Jaké číslo požadavku jsem uvedl a co se mému zařízení stalo?
   Jaké krytí, spoluúčast, měsíční cenu a limit událostí má podle vaší dokumentace služba DemoBox+?
   ```

   Produkt je záměrně uveden i v novém dotazu: retrieval query se sestavuje z aktuální
   zprávy a příloh, nikoli z historie. Nová zpráva musí zůstat nepřečtená. Připrav ji
   nejdřív bez odeslání; `--subject` musí přesně odpovídat jejímu předmětu:

   ```sh
   MCFLY_ENABLE_RAG=true MCFLY_ENABLE_THREAD_HISTORY=true \
     uv run python ~/Downloads/reply_mcfly_send_once.py \
     --subject "Re: RM POC RAG HISTORY 01"
   ```

   Očekávání: `READY_TO_SEND`. Z posledního JSON řádku zkopíruj `job_id` a ověř důkazy
   v uloženém outboxu (nahraď `JOB_UUID`):

   ```sh
   docker compose exec -T worker python - JOB_UUID <<'PY'
   import sys
   from uuid import UUID
   from reply_mcfly.adapters.postgres_adapter import PostgresEmailRepository, make_engine
   from reply_mcfly.config.settings import Settings
   from reply_mcfly.domain.email import ResponseType, Status

   engine = make_engine(Settings().sqlalchemy_url())
   try:
       repository = PostgresEmailRepository(engine)
       job_id = UUID(sys.argv[1])
       assert repository.get(job_id).status == Status.READY_TO_SEND
       entry = repository.outbox(job_id)
       assert entry is not None and entry.response_type == ResponseType.GENERATED
       assert "RM-POC-7429" in entry.draft_body
       assert "390 Kč" in entry.draft_body
       assert "179 Kč" in entry.draft_body
       assert "2 uznané škodní události" in entry.draft_body
       assert "12 po sobě jdoucích měsíců" in entry.draft_body
       assert any(s.startswith("thread:") and "RM-POC-7429" in q for s, q in entry.evidence)
       assert any(s.startswith("rag:KB01_") and "390 Kč" in q for s, q in entry.evidence)
       assert any(s.startswith("thread:") and "vodou" in q for s, q in entry.evidence)
       for fact in ("polití kapalinou", "179 Kč", "2 uznané škodní události"):
           assert any(s.startswith("rag:KB01_") and fact in q for s, q in entry.evidence)
       print("PASS: outbox obsahuje historii a krytí, spoluúčast, cenu i limit z KB.")
   finally:
       engine.dispose()
   PY
   ```

3. Po úspěšné kontrole můžeš stejným helperem a předmětem spustit `--send`, opět
   s oběma proměnnými nastavenými na `true`. Worker znovu ověří uložené důkazy
   a odešle již připravenou odpověď. Očekávání: `SENT`, právě jedna nová odpověď
   ve stejném vlákně, `RM-POC-7429` a `390 Kč` v jejím těle.

Každé nové celé opakování scénáře dělej s novým unikátním předmětem. Samotné `SENT`
neprokazuje RAG ani historii; rozhodující jsou oba zdroje v outboxu a obsah odpovědi.
Helper očekává právě jeden **nový** odeslaný e-mail, takže jeho opakované `--send`
nad již dokončenou zprávou není testem deduplikace. Tu ověřuje lokální test výše.

Při `INVALID_EVIDENCE` zůstává validátor přísný: i odstranění Markdown značek `**`
znamená neplatnou citaci. Instrukce Gemini proto výslovně vyžaduje kopírování všech
znaků zdroje. Job ve stavu `REVIEW_REQUIRED` se automaticky neopakuje; pro další
ověření pošli nový dotaz. Před výběrem helperem označ starší dotazy stejného předmětu
jako přečtené, aby odpovídal právě jeden nepřečtený e-mail.

Ověření 12. 11. 2026: skutečný lokální Gmail/Vertex dry-run nad novým dotazem ve
správném vlákně dosáhl `READY_TO_SEND` za 7,517 s. Aktuální zpráva neobsahovala
číslo požadavku ani popis nehody; uložený outbox měl dvě platné citace `thread:`
a čtyři `rag:KB01_` se všemi šesti očekávanými údaji. Celá Docker sada měla
153 passed. Po výslovném schválení následovalo odeslání stejného outboxu se stavem
`SENT`. Nezávislá kontrola Gmailu ověřila právě jednu novou SENT odpověď ve správném
vlákně, uložené Gmail API ID, příjemce, `In-Reply-To`, `References` a shodu těla
s outboxem při zohlednění SMTP konců řádků. Jde o lokální CLI E2E s ruční pauzou
na schválení, nikoliv o měření automatického Pub/Sub/Cloud Tasks průchodu.

Zachycené omezení: u této zprávy Gmail změnil odeslaný RFC `Message-ID`. Potvrzení
doručení výše používá Gmail API ID uložené z výsledku sendu. Stávající obnova
`DELIVERY_UNKNOWN` hledá podle původního RFC `Message-ID`; její spolehlivost při této
změně zůstává otevřeným bodem. Žádné opakované odeslání nebylo provedeno.

Conversation History a RAG jsou implementované za přepínači
`MCFLY_ENABLE_THREAD_HISTORY=true` a `MCFLY_ENABLE_RAG=true` (výchozí stav je vypnuto).
Live Web Search má rozhraní v `ports/capabilities.py`; jeho implementace zůstává
navazující prací a povinnou součástí finálního PoC.
Podporované přílohy se v textovém slice neinterpretují a míří k ruční kontrole.
U zjištěného nepodporovaného MIME může následovat schválený fallback; bezpečně ověřitelný
text může projít i bez využití takové přílohy. Detekce poškození a kontrola skutečných
signatur souborů bude součástí samostatného attachment inkrementu.

## Vektorový RAG nad pgvector (produktový katalog)

Vedle lokálního Markdown RAG (KB01–KB03, výchozí) umí Worker číst produktové znalosti
z PostgreSQL + pgvector. Přepíná se jen konfigurací:
`MCFLY_ENABLE_RAG=true MCFLY_RAG_BACKEND=pgvector`. Katalog tří fiktivních produktů je
v `src/reply_mcfly/product_catalog/` (18 sekčních chunků), odděleně od `knowledge_base/`.
Migrace 0004 přidává tabulku `rag_product_chunks`; tabulky e-mailového workflow nemění.

```sh
python -m reply_mcfly.rag validate                 # offline kontrola katalogu
python -m reply_mcfly.rag sync                     # dry-run: co by se změnilo
python -m reply_mcfly.rag sync --apply             # embeddingy přes Vertex AI + zápis
python -m reply_mcfly.rag search --query "Kolik stojí AirDock 8?"
```

Postup nasazení, ověření, chybové stavy a návrat k Markdown režimu popisuje
[`RUNBOOK_RAG_PGVECTOR.md`](RUNBOOK_RAG_PGVECTOR.md); nasazení celé verze, rollback a měření
latence [`RUNBOOK_DEPLOYMENT.md`](RUNBOOK_DEPLOYMENT.md). Živé Vertex AI embeddingy, Cloud SQL
a Gmail E2E s tímto backendem zatím **nebyly ověřeny**; lokální testy používají řízený fake.

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

## Aktuální Trivy runtime audit — 12. 11. 2026

**HIGH/CRITICAL gate zůstává FAIL.** Na větvi `feature/rag`, navazující na `80a5ed5`,
byl porovnán skutečný runtime před a po odstranění nepotřebného balíku `mount`.
Změna platí jen pro runtime stage; nemění aplikaci, migrace ani testovací stage.
APT simulace potvrdila odstranění pouze `mount`, bez dalších závislostí.
Aktuální APT indexy současně nabízely stejné verze dotčených balíků jako image;
`apt-get -s upgrade` hlásil 0 aktualizací.

Scanner: `aquasec/trivy:0.76.2`, uzamčený digestem
`sha256:8f6bb947dbc528902e11f2f5be52f7b519f6a39d5d148f41166f2040499768fb`.
Databáze byla aktualizovaná `2026-11-12T07:01:33Z` a stažená samostatně.
Oba skeny proběhly offline nad `docker image save` archivem, bez Docker socketu,
se stejnou DB a parametry `--scanners vuln,secret --severity HIGH,CRITICAL
--skip-db-update --offline-scan --exit-code 1 --format json`.
Nebyl použit ignore seznam, VEX výjimka ani `--ignore-unfixed`.

| Image / výsledek | Před změnou | Po změně |
|---|---|---|
| Runtime config ID (sha256) | `cdfc9ed931e50290760e79a281c33bb22e6609e3c3210a77e9bbe8a3ccb00f27` | `e7212000a9843af9480089c097a71a04e2a8c7a0fe852096dd76f40519586c85` |
| Platforma | linux/arm64 | linux/arm64 |
| HIGH balíkové nálezy | 47 | **43** |
| CRITICAL | 0 | 0 |
| Unikátní CVE | 11 | 11 |
| Python HIGH/CRITICAL / secrets HIGH/CRITICAL | 0 / 0 | 0 / 0 |
| Exit code | 1 | 1 |

Odstranění `mount` odstranilo čtyři balíkové nálezy a jeho spustitelné soubory,
neopravilo však stejné CVE hlášené u dalších balíků util-linux.
Zbývající nálezy jsou v Debianu, nikoli v uzamčených Python závislostech.
Trivy pro žádný z nich neuvádí opravenou verzi v použité distribuci.

| Skupina (HIGH balíkové nálezy) | Prověřená použitelnost a omezení |
|---|---|
| util-linux: CVE-2026-76642, CVE-2026-78408, CVE-2026-78409, CVE-2026-78410 (32) | `mount`/`umount` odstraněny, `nsenter` zůstává. Jde o lokální privilegované mount/cgroup scénáře; aplikace tyto nástroje přímo nevolá. Základní balík util-linux je Essential. |
| ncurses: CVE-2025-69720 (4) | Zranitelnost nástroje `infocmp`, který v image zůstává; aplikace jej přímo nevolá. ncurses-bin je Essential. |
| SQLite: CVE-2026-119373, CVE-2026-119374, CVE-2026-119379 (3) | Python sqlite3 a knihovna jsou přítomné. Aplikace používá PostgreSQL a nemá přímé volání SQLite ani vstup pro SQLite databáze/changesety. To není důkaz nepoužitelnosti ve všech závislostech. |
| systemd: CVE-2026-16742 (2) | `systemd-homed` není v image přítomný; zůstávají knihovny libsystemd0/libudev1 ze stejného zdrojového balíku. Kandidát na další posouzení použitelnosti, nikoli schválená výjimka. |
| ACL: CVE-2026-54369 (1) | Knihovna zůstává. Aplikace přímo nevolá ACL API ani privilegované operace s ACL; tranzitivní dosažitelnost nebyla plně analyzovaná. |
| Perl: CVE-2026-9538 (1) | `perl-base` je Essential, ale pokus načíst dotčený `Archive::Tar` v runtime selhal, modul není dostupný. Kandidát na posouzení použitelnosti, nikoli schválená výjimka. |

Stav a podmínky byly porovnány s Debian Security Trackerem:
[util-linux](https://security-tracker.debian.org/tracker/source-package/util-linux),
[ncurses](https://security-tracker.debian.org/tracker/CVE-2025-69720),
[SQLite](https://security-tracker.debian.org/tracker/CVE-2026-119374),
[systemd](https://security-tracker.debian.org/tracker/CVE-2026-16742),
[ACL](https://security-tracker.debian.org/tracker/CVE-2026-54369),
[Perl](https://security-tracker.debian.org/tracker/CVE-2026-9538).
Non-root UID 10001 a absence přímého použití některých komponent snižují expozici;
nenahrazují opravu ani schválení release. Balíky z Debian unstable nebyly míchány
se stable a nebyly vynuceně odstraňované Essential balíky nebo knihovny Pythonu.

Lokální JSON důkazy jsou v ignorovaném `docs/security/`:
`trivy-runtime-before-2026-11-12.json`, `trivy-runtime-after-2026-11-12.json`
a `trivy-db-2026-11-12.json`; nejsou součástí klonu repozitáře.

Ověření po změně: `docker build --target runtime -t reply-mcfly:local .` prošel;
`docker compose run --rm --no-deps tests pytest -q` má **148 passed in 3.31s**.
`docker compose up -d --wait --no-build ingress worker` má všechny tři služby healthy.
Na upraveném runtime mají oba health endpointy 200, neautorizované workflow POST 401,
`alembic check` nemá rozdíl modelů; runtime importy, UID 10001 a všechny tři KB soubory
byly ověřené bez sítě. Žádný skutečný e-mail nebyl v tomto auditu odeslán.

První nasazení stále blokuje otevřený HIGH/CRITICAL gate: je nutná oprava v podporované
základně nebo explicitně schválené, podložené posouzení zbývajících nálezů.
Dále chybí ověřený cílový cloudový build, dostupný cloudový runbook/runtime konfigurace
s aktivní historií a RAG, ověření IAM/SQL/secrets/Watch a jeho obnovování, živý cloudový
E2E včetně duplicit/souběhu a měření od přijetí zprávy do odeslání pod 120 sekund.
Žádná cloudová změna, push ani deployment v tomto auditu neproběhly.
