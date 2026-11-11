# Handoff: plán rekonstrukce Git historie Reply McFly

## Účel a autorizace
Původně tento handoff pouze plánoval rekonstrukci bez oprávnění commitovat a mergovat. Nové výslovné zadání vlastníka z 11. 11. 2026 autorizovalo realizaci celého plánu a lokální sloučení do main. Vlastník následně schválil výjimku pro lokální rekonstrukci s přesnou evidencí neúspěšných nebo neověřených gates. Push ani cloudové operace nebyly autorizované. Výsledek a commit reference jsou v části Realizace níže; původní plán a inventura zůstávají zachované jako historický podklad. Komunikuj česky. Nehádej nevyřešená produktová nebo bezpečnostní rozhodnutí.

Tato konverzace je vedlejší chat. Implementace probíhá v hlavním chatu a může se souběžně měnit. Nespouštěj její rozpracované úlohy ani nezasahuj do jejích procesů. Bez výslovného oprávnění neposílej zprávy jinému chatu a nepoužívej subagenty.

## Repozitář a zdroje pravdy
Kořen repozitáře: /Users/thechesirecat/WorkDev/alza-use_case/Reply-McFly-agent
Nadřazený adresář alza-use_case není Git repozitář. Sousední Engineering_OS_Startovni_Balicek_CZ není součástí změny.
Při čtecí inventuře: main a lokální origin/main ukazovaly na 850a465 (gitignore); remote nebyl ověřován fetch příkazem. Existoval 1 sledovaný soubor .gitignore a 56 nových nesledovaných souborů. Žádné změny existujících sledovaných souborů nebyly hlášeny. Před realizací inventuru zopakuj, protože hlavní chat pokračuje.

Existující dokumenty, jejichž obsah neduplikuj:
- /Users/thechesirecat/WorkDev/alza-use_case/Reply-McFly-agent/docs/reply_mcfly_agent_BLUEPRINT.md
- /Users/thechesirecat/WorkDev/alza-use_case/Reply-McFly-agent/docs/reply_mcfly_agent_projekt.json
- /Users/thechesirecat/WorkDev/alza-use_case/Reply-McFly-agent/docs/operations/GCP_CLOUD_SHELL.md
- /Users/thechesirecat/WorkDev/alza-use_case/Reply-McFly-agent/README.md
Čti relevantní repository guidance v aktuálním stavu; při minulé kontrole nebyl nalezen projektový AGENTS.md.

## Zásady rekonstrukce
Jde o logickou rekonstrukci, nikoli o přesnou obnovu historických snapshotů: meziverze nejsou v Gitu. Nevymýšlej historická data commitů ani neprezentuj rekonstrukci jako skutečný dřívější záznam.
Každá další větev vznikne z main po mergi předchozí. Doporučené merge --no-ff zachová hranice větví, ale merge vyžaduje nové výslovné oprávnění a lidské review.
Pracuj až po autorizaci v odděleném pracovním stromu z main se stabilním snímkem verzovatelných zdrojů. Necheckoutuj větve přes živou rozpracovanou implementaci hlavního chatu.
Každý commit musí mít příslušné testy a konfiguraci; nepřebírej předčasně importy budoucích modulů. Lock a závislosti měň současně, bez neplánovaných upgradů. Prázdné package __init__.py patří k prvnímu zavedení balíčku.

## Plán větví a commitů
Cesty v této části jsou relativní vůči /Users/thechesirecat/WorkDev/alza-use_case/Reply-McFly-agent.

### B01 docs/project-blueprint
C01 docs: add project blueprint and requirements
Přidat docs/reply_mcfly_agent_BLUEPRINT.md a docs/reply_mcfly_agent_projekt.json. Zachovat rozdíl mezi potvrzenými požadavky a předpoklady.
Gate: validní JSON, soulad obou dokumentů, bez secrets, bez tvrzení o neprovedeném deploymentu.

### B02 feature/docker-postgres-skeleton
C02 feat: add FastAPI services and PostgreSQL diagnostics
První verze pyproject.toml, uv.lock, alembic.ini, migrations/env.py, migrations/script.py.mako, migrations/versions/0001_mailbox_sync_state.py.
První verze src/reply_mcfly/config/settings.py, adapters/postgres_adapter.py, application/diagnostics.py, api/health.py, api/ingress.py, api/worker.py a smoke.py.
Přidat src/reply_mcfly/__init__.py a __init__.py v adapters/, api/, application/, config/.
Přidat tests/unit/test_health.py a tests/integration/test_postgres.py.
Meziverze: pouze DB konfigurace, mailbox_sync_state, diagnostika a health. Bez workflow, Google SDK, doménových importů a telemetrie. Model odpovídá 0001, ještě bez lease_token.
C03 build: add reproducible Docker Compose environment
Přidat Dockerfile, docker-compose.yml, .dockerignore, .env.example, README.md pro RM-001. Společný image, tři služby, volume, lokální migrace, test stage.
C04 fix: harden runtime image and exclude local credentials
Přiřadit současný hardening Dockerfile: novější base, systémové aktualizace, build/test/runtime stages, non-root, omezený context a loopback porty. Nevyrábět úmyslně zranitelnou meziverzi jen pro historii.
Gate: build/start tří služeb, health obou, migrace a alembic check, pgvector, zápis/čtení, restart persistence, výpadek DB 503 a zotavení 200. Ruff/mypy/pytest/Bandit/pip-audit/Gitleaks/image scan.

### B03 feature/email-job-lifecycle
C05 feat: define email domain ports and workflow telemetry
Přidat src/reply_mcfly/domain/__init__.py, domain/email.py, ports/__init__.py, ports/email.py, application/telemetry.py. První DTO/stavy/porty; evidence přichází v B04. Telemetrie je zde kvůli importům DB adaptéru.
C06 feat: persist email jobs with fenced leases and outbox
Přidat migrations/versions/0002_email_workflow.py a repository část tests/integration/test_email_workflow.py. Rozšířit postgres_adapter.py o job/outbox modely, unique constraint, checkpointy, lease tokeny a transakce. Meziverze test fixture nesmí vyžadovat budoucí aplikační služby.
Gate: 0001→0002, shoda schématu, deduplikace, exkluzivní a souběžné claims, expirace lease, odmítnutí stale workeru, logování po úspěšných transakcích.

### B04 feature/verified-reply-policy
C07 feat: add approved fallback templates and literal reply verification
Přidat domain/reply_templates.py, domain/grounding.py, application/reply_service.py, tests/unit/test_grounding.py. Doplnit konečný ReplyDraft, typy odpovědí, recipient/thread/allowlist policy, odmítnutí automatických odesílatelů, header injection a rozpoznaných rizikových instrukcí do domain/email.py.
C08 feat: persist reply evidence and validate fallback metadata
Přidat migrations/versions/0003_reply_evidence.py. Rozšířit DTO, repository a testy o evidence JSONB, opětovnou validaci a constraint response_type/fallback_reason.
C09 feat: define provenance contracts for future context sources
Přidat ports/capabilities.py: pouze schválená rozhraní ThreadContext/RAG/WebSearch, ne jejich implementace.
Gate: přesnost obou schválených šablon, doslovné podklady, odmítnutí ceny/termínu/URL navíc, neexistujícího zdroje, falešné citace i parafráze s platnou citací; migrace 0003 a metadata constraints.

### B05 feature/gmail-adapter
C10 feat: add Gmail MIME history and threaded reply adapter
Přidat adapters/gmail_adapter.py, adapters/google_clients.py, typings/google_auth_httplib2.pyi, tests/unit/test_gmail_adapter.py. SDK, Secret Manager, OAuth factory, kontrola schránky, MIME/HTML, history, metadata, threading, send a dohledání sent. Watch metody až C18.
Závislosti a stuby do pyproject.toml/uv.lock; mypy_path a test-stage COPY typings do Dockerfile/.dockerignore.
C11 fix: prevent implicit Gmail resend after ambiguous HTTP failure
Doplnit OneShotHttp a chyby transportu. Založit tests/unit/test_google_security.py pouze s transportní částí.
Gate: From vs Reply-To, víceznačný/automatický odesílatel, HTML, reply hlavičky, nesprávná OAuth schránka, matching sent lookup a právě jeden transportní pokus po nejasné odpovědi.

### B06 feature/email-processing-workflow
C12 feat: enqueue idempotent authenticated Cloud Tasks
Přidat adapters/cloud_tasks_adapter.py; Cloud Tasks testy do test_google_security.py; SDK/stuby/lock. Stabilní task names, AlreadyExists, OIDC audience, payload pouze IDs.
C13 feat: generate structured Gemini drafts from current email context
Přidat adapters/gemini_adapter.py; SDK/lock a schválené projekt/model/location nastavení. Ověřit SDK kontrakt testy; reálné volání je samostatný cloudový gate.
C14 feat: orchestrate Gmail synchronization and safe email processing
Přidat application/gmail_sync_service.py a application/email_processing_service.py; rozšířit test_email_workflow.py o fake adaptéry a servisní scénáře. Checkpoint až po bezpečném enqueue, retry před send, fallback volba, DELIVERY_UNKNOWN reconciliation bez druhého send, latency telemetry.
Gate: skutečný PostgreSQL + fake Google; duplicity, queue failure/checkpoint, transient AI error, oba fallbacky, bezpečnost příjemce, prompt injection, invalid AI output, unknown delivery nalezeno/nenalezeno. Žádná tvrzení o reálném Gmail E2E.

### B07 feature/authenticated-workflow-api
C15 feat: verify Google OIDC signatures audiences and service identities
Přidat adapters/oidc_adapter.py a OIDC části test_google_security.py: syntetické RSA podpisy, audience/issuer/expiry/identity/email_verified, forged signature; bez sítě.
C16 feat: expose authenticated ingress and worker workflow endpoints
Přidat api/workflow.py. Rozšířit health.py/settings.py/Compose/.env.example o runtime kompozici. HTTP testy do test_email_workflow.py. Oddělit Ingress bez cloudových DB/Gmail credentials od Workeru; zachovat lokální DB health. Fake závislosti jen v testovací kompozici, ne implicitní produkční režim.
Gate: HTTP pipeline s fake dispatch, 401/403, chybná Base64/JSON/UUID, extra fields, unknown job 404, request limit, sanitizované chyby, unknown delivery 503, chybějící konfigurace fail-closed. Ověřit Ingress bez DB a Worker s povinnou DB.

### B08 feature/gmail-oauth-watch
C17 feat: add secure local Gmail OAuth setup
Přidat oauth_setup.py, typings/google_auth_oauthlib/__init__.pyi, typings/google_auth_oauthlib/flow.pyi; OAuthlib závislost/lock. Scopes, PKCE, 0600, žádné přepsání existujícího souboru.
C18 feat: initialize and renew Gmail Watch without losing checkpoints
Přidat bootstrap.py; Gmail profile_history/watch/WatchPayload, repository baseline/expiration a topic konfiguraci.
Gate: mockované OAuth/Watch testy, baseline před registrací, existující checkpoint se nepřepisuje, správný existující topic, neúplná konfigurace odmítnuta. Žádné skutečné OAuth/Watch volání jako vedlejší efekt testů.

### B09 docs/cloud-deployment-runbook
C19 docs: add reviewed Cloud Shell deployment sequence and infrastructure inventory
Přidat docs/operations/GCP_CLOUD_SHELL.md. Inventura, náklady, IAM review, DB migrátor vs runtime, digest, deployment a subscription/Watch pořadí. Existující prostředky nevytvářet znovu. Neexecutovat příkazy v tomto kroku.
C20 docs: reconcile configuration and verification status with implemented workflow
Dokončit současnou podobu README a příkladové konfigurace; pouze nutné schválené dodatky sladit v blueprint MD a JSON. Výsledky RM-001 označit jako historické nebo nahradit novými skutečnými výsledky. Starší image scan není sken nové varianty s Google SDK.
Gate: kontrola příkazů/proměnných/pořadí, existující vs navržené prostředky, žádné secrets, jasná cenová/IAM approval hranice, žádné nepravdivé cloudové PASS ani univerzální tvrdý budget limit.

## Matice opakovaně měněných souborů
- pyproject.toml + uv.lock: C02 základ; C10 Gmail/Secret Manager/stuby; C12 Tasks; C13 Gemini; C17 OAuthlib.
- Dockerfile: C03 Docker; C04 hardening; C10 typings v test stage.
- .dockerignore: C03 context; C04 secrets; C10 typings.
- docker-compose.yml: C03 služby/volume/testy; C16 runtime konfigurace.
- .env.example: C03 DB/porty; C13 AI hodnoty; C16 identity/workflow; C18 topic; C20 potvrzené názvy.
- settings.py: C02 DB; C13 AI; C16 role/workflow; C18 topic.
- postgres_adapter.py: C02 diagnostika; C06 job/lease/outbox; C08 evidence; C18 Watch baseline.
- domain/email.py + ports/email.py: C05 životní cyklus; C07/C08 reply/grounding kontrakt.
- health.py: C02 diagnostika; C16 API a Ingress bez DB.
- gmail_adapter.py: C10 MIME/history/reply; C11 transportní chyby; C18 Watch.
- google_clients.py: C10 credentials; C11 one-shot transport.
- test_email_workflow.py: C06 repository; C08 evidence; C14 služby; C16 HTTP.
- test_google_security.py: C11 transport; C12 Tasks; C15 OIDC.
- README.md: C03 RM-001; C04 bezpečnost; C20 aktuální stav.
- Blueprint MD/JSON: C01 zdrojové zadání; C20 potřebná schválená upřesnění.

## Kontroly a stav důkazů
Kontroly výše jsou požadované budoucí merge gates, nikoli tvrzení, že právě prošly. Tento plánovací chat nespouštěl testy ani Docker a neměnil soubory. Jen četl Git, seznam souborů a relevantní zdroje.
Pro každou kódovou větev Ruff lint/format, strict mypy, relevantní pytest a diff review. Od B02 zachovat Docker build/start a dřívější regrese. Schéma ověřit skutečným PostgreSQL; downgrade pouze na izolované testovací DB. Aktualizované závislosti znovu auditovat a runtime image znovu skenovat. Nevypínat kontroly, neschovávat nálezy, neoslabovat testy. Pokud potřebný test zatím neexistuje, je jeho doplnění podmínkou merge, nikoli hotovou prací.
README při inventuře stále uvádělo RM-001: 12 testů, migraci 0001 a starší image scan s 47 HIGH. To není aktuální potvrzení nejnovějšího workflow ani nového image; viz existující README.

Inventura pokrytí: B01 2 + B02 25 + B03 7 + B04 6 + B05 5 + B06 4 + B07 2 + B08 4 + B09 1 = 56 nových souborů. Bez chybějících či duplicitních přiřazení. Jediný nepřiřazený soubor .gitignore je již v commitu 850a465 a nemá se commitovat znovu.
Ignorované .env, credentials, cache, .venv, databázová data a testovací výstupy nejsou součástí historie.

## Cloudové hranice
Skutečný Gmail/GCP E2E do 120 s není dokončený a nepatří mezi zpětně vyrobené úspěchy těchto commitů. Placené prostředky a neodsouhlasené IAM změny vyžadují samostatné schválení. Uživatel chce oddělené příkazy pro Cloud Shell; lokální gcloud se nemá nyní autentizovat. Podrobná inventura a postup jsou v existujícím cloudovém runbooku, ne zde.

## Suggested skills
- handoff: přečti tento handoff a odkazované artefakty; při dalším předání použij stejný skill.
- code-review: až uživatel zadá review konkrétní větve. Nejprve přečti SKILL.md. Pokud workflow vyžaduje subagenty, nesmí se spustit ve vedlejší konverzaci bez změny tohoto omezení; zvol read-only review bez delegace nebo si vyjasni oprávnění.
- diagnosing-bugs: pouze při skutečném nejasném selhání rekonstrukce nebo testů.
- code-simplification: jen pokud review prokáže konkrétní zbytečnou složitost; není součástí rekonstrukce historie.
Skill tool použij, je-li k dispozici; jinak přečti příslušný SKILL.md standardním čtecím nástrojem. Nezahajuj develop/scope/sync ani paralelní agenty automaticky. Uživatel chce zachovat existující zdroje pravdy, nikoli nové workflow nebo duplicitní specifikace.

## První krok další session — původní pokyny před autorizací
Ověřit nové zadání a oprávnění, zopakovat čtecí inventuru a porovnat ji s pokrytím 56 souborů. Pokud se hlavní implementace změnila, aktualizovat plán před realizací. Teprve po autorizaci připravit stabilní snímek a izolovaný pracovní strom. Do té doby žádné větve, stage, commity, merge, push ani cloudové operace.


## Realizace — 11. 11. 2026

Celý plán byl realizován jako logická rekonstrukce bez zpětného datování.
Výchozí main: `b96d79b` (novější než původní inventura `850a465`).
Rekonstrukce vznikla ze stabilního snímku v odděleném worktree. Devět větví bylo
postupně sloučeno přes `--no-ff` do integrační větve; lokální main přebírá tentýž
hotový graf bez přepisování původních commitů. Remote nebyl měněn ani nově ověřován fetch příkazem.

### Dokončené commity

| Plán | Commit / stabilní Git reference | Název |
|---|---|---|
| C01 | `4fd64433` | docs: add project blueprint and requirements |
| C02 | `4506959c` | feat: add FastAPI services and PostgreSQL diagnostics |
| C03 | `77979591` | build: add reproducible Docker Compose environment |
| C04 | `eeda604b` | fix: harden runtime image and exclude local credentials |
| C05 | `95a155f9` | feat: define email domain ports and workflow telemetry |
| C06 | `0770e624` | feat: persist email jobs with fenced leases and outbox |
| C07 | `881b25a5` | feat: add approved fallback templates and literal reply verification |
| C08 | `0f8b5e28` | feat: persist reply evidence and validate fallback metadata |
| C09 | `ae9f19e9` | feat: define provenance contracts for future context sources |
| C10 | `5392de1f` | feat: add Gmail MIME history and threaded reply adapter |
| C11 | `1cde8807` | fix: prevent implicit Gmail resend after ambiguous HTTP failure |
| C12 | `f76384c2` | feat: enqueue idempotent authenticated Cloud Tasks |
| C13 | `a6890bc6` | feat: generate structured Gemini drafts from current email context |
| C14 | `2f0e12cc` | feat: orchestrate Gmail synchronization and safe email processing |
| C15 | `5d662296` | feat: verify Google OIDC signatures audiences and service identities |
| C16 | `7941dd23` | feat: expose authenticated ingress and worker workflow endpoints |
| C17 | `265c8a23` | feat: add secure local Gmail OAuth setup |
| C18 | `49bedd10` | feat: initialize and renew Gmail Watch without losing checkpoints |
| C19 | `73ce63c3` | docs: add reviewed Cloud Shell deployment sequence and infrastructure inventory |
| C20 | `docs/cloud-deployment-runbook` | docs: reconcile configuration and verification status with implemented workflow |

C20 je tip dokumentační větve; její reference umožňuje vyhledat commit bez
sebereferenčního SHA v obsahu stejného commitu:
`git rev-parse docs/cloud-deployment-runbook`.

### Dokončené merge hranice

| Plán | Větev | Merge reference |
|---|---|---|
| B01 | `docs/project-blueprint` | `a6f8d2a` |
| B02 | `feature/docker-postgres-skeleton` | `e003243` |
| B03 | `feature/email-job-lifecycle` | `c6612cc` |
| B04 | `feature/verified-reply-policy` | `1b816d4` |
| B05 | `feature/gmail-adapter` | `43cca72` |
| B06 | `feature/email-processing-workflow` | `d68a07d` |
| B07 | `feature/authenticated-workflow-api` | `153cee0` |
| B08 | `feature/gmail-oauth-watch` | `db8fa4f` |
| B09 | `docs/cloud-deployment-runbook` | `main (závěrečný merge B09)` |

### Skutečné kontroly a odchylky od původního plánu

- C01: JSON parsován; potvrzené požadavky a pracovní předpoklady zachované.
- C02–C18: před každým commitem Ruff lint/format, strict mypy, pytest se skutečným
  izolovaným PostgreSQL, `alembic upgrade head`, `alembic check`, Bandit a Git diff check.
  Počty testů: C02–C05 12; C06 16; C07 24; C08–C09 26; C10 36; C11 37;
  C12 38; C13 45; C14 59; C15 66; C16 70; C17 72; C18 76. Žádné skipy.
- Doplněny chybějící kontraktové testy: Gemini SDK/schema/timeout/chyby (C13),
  OAuth scopes/PKCE/0600/no-overwrite (C17), Watch pořadí a payload (C18),
  deduplikace repository (C06), evidence a DB metadata constraint (C08),
  zachování checkpointu při obnově Watch (C18). Žádné živé OAuth/Gmail/AI volání.
- Finální Docker build/start: PASS, tři healthy služby v odděleném Compose projektu.
  Finální Docker pytest: 76 passed in 2.17s (31 integrací, 45 unit), bez skipů.
  Ruff/format/strict mypy/Bandit také ověřeny ve finálním Docker test image.
- Upgrade/downgrade/upgrade a shoda modelů: PASS jen v nové dočasné testovací DB.
- Runtime UID 10001, vyloučení `.env`, tests, docs a uv, health 200 a Worker POST 401: PASS.
- Syntaxe 20 shell bloků README/runbooku: `bash -n` PASS; cloudové příkazy neprovedeny.
- pip-audit: PASS bez známých zranitelností; vlastní editable balíček vynechán.
  Gitleaks: PASS offline pro snímek i finální worktree, bez nálezů.
- Nový Trivy scan finálního runtime image: FAIL, 47 HIGH / 11 CVE, 0 CRITICAL,
  žádná uvedená opravená verze, 0 secrets. Runtime image ID je uvedené v README.
- Výjimka vlastníka dovoluje pouze lokální rekonstrukční merge s touto evidencí.
  Security release gate zůstává otevřený. Docker build/start a nový image scan byly
  provedeny pro finální snímek; samostatný Docker build/start a image audit každé
  meziverze/větve nebyly provedené. Restart persistence a DB outage/recovery nebyly
  znovu ověřené; starší důkazy jsou v README výslovně označené jako historické.
- C03 už obsahuje bezpečný non-root runtime a aktuální base; C04 doplňuje omezení
  contextu, neprivilegovanou test stage a její cache. Zranitelná meziverze nebyla vyráběna.
- Závislosti a jejich lock se měnily současně, uzamčené verze byly zachované.
  C20 odstraňuje pouze prázdný řádek vytvořený skládáním lock meziverzí.
- Všechny původní aplikační, konfigurační a deployment soubory jsou ve finále
  shodné se vstupním snímkem. Výjimkou jsou záměrně rozšířené testy a README/handoff.
  `.gitignore` zůstává beze změny včetně `docs/`; vybrané projektové dokumenty byly
  přidány výslovně přes `git add -f`. Lokální `.env`, caches ani credentials nejsou verzované.
- Přehled je součástí existujícího handoffu, nevznikl druhý tracker ani nový workflow.
  Cloudové gates, IAM/náklady, Gmail E2E, skutečná latence a Cloud Run/AMD64 zůstávají otevřené.
