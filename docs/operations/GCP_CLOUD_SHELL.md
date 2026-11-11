# Reply McFly v1.0 — samostatné kroky pro Cloud Shell

Stav 11. 11. 2026. Tento dokument je postup k review, ne záznam provedeného
deploymentu. **V tomto kroku nebyl změněn IAM ani vytvořen placený prostředek.
Cloudový E2E test je NESPLNĚNÝ.** Lokální výsledky jsou v kořenovém README.

## Potvrzená inventura a otevřené předpoklady

Zdroj: inventura dodaná vlastníkem projektu z Google Cloud Shellu v chatu.
Lokální gcloud skončil `PERMISSION_DENIED`; jeho prázdné výstupy nejsou důkazem absence.

- Projekt `reply-mcfly-poc`, číslo `881859376713`, billing a potřebná API aktivní.
- Existují účty `reply-mcfly-ingress`, `reply-mcfly-worker`, `reply-mcfly-tasks`.
- Existují `sync-queue` a `process-queue` v `europe-west1`: souběžnost 2,
  dispatch 1/s, max. 3 pokusy, backoff 10–60 s.
- Existuje topic `projects/reply-mcfly-poc/topics/gmail-events`; Gmail publisher
  `gmail-api-push@system.gserviceaccount.com` má na topicu `roles/pubsub.publisher`.
- Potvrzené IAM: Worker má Vertex AI User a Cloud SQL Client; Ingress/Worker mají
  enqueuer na příslušné frontě a Service Account User na účtu Tasks.
- Podle inventury dosud nejsou Cloud Run služby, SQL instance, Artifact Registry
  repozitář, push subscription a Scheduler úlohy.
- Gmail schránka, allowlist, OAuth, secrets a ostatní IAM vazby čekají na ověření.

Následující názvy nových prostředků jsou **návrh**: repozitář `reply-mcfly`,
SQL instance `reply-mcfly-sql`, databáze `mcfly`, služby `reply-mcfly-ingress`
a `reply-mcfly-worker`, subscription `gmail-events-push`. Nejprve ověř jejich absenci.
Existující účty, topic a fronty se znovu nevytvářejí.

## 1. Proměnné a opětovné čtení stavu

Pouze nesenzitivní hodnoty:

```sh
export PROJECT_ID=reply-mcfly-poc
export PROJECT_NUMBER=881859376713
export REGION=europe-west1
export INGRESS_SA=reply-mcfly-ingress@reply-mcfly-poc.iam.gserviceaccount.com
export WORKER_SA=reply-mcfly-worker@reply-mcfly-poc.iam.gserviceaccount.com
export TASKS_SA=reply-mcfly-tasks@reply-mcfly-poc.iam.gserviceaccount.com
export TOPIC=projects/reply-mcfly-poc/topics/gmail-events
```

Každý příkaz lze spustit samostatně; nemění konfiguraci:

```sh
gcloud projects describe "$PROJECT_ID" --format='yaml(projectId,projectNumber,lifecycleState)'
gcloud run services list --project="$PROJECT_ID" --region="$REGION"
gcloud sql instances list --project="$PROJECT_ID"
gcloud artifacts repositories list --project="$PROJECT_ID" --location="$REGION"
gcloud tasks queues describe sync-queue --project="$PROJECT_ID" --location="$REGION"
gcloud tasks queues describe process-queue --project="$PROJECT_ID" --location="$REGION"
gcloud pubsub topics describe "$TOPIC" --project="$PROJECT_ID"
gcloud pubsub topics get-iam-policy "$TOPIC" --project="$PROJECT_ID"
gcloud pubsub subscriptions list --project="$PROJECT_ID"
gcloud secrets list --project="$PROJECT_ID"
gcloud projects get-iam-policy "$PROJECT_ID"
```

Nečti hodnoty secret versions do konzole. Při 403 zastav kontrolu; nepoužívej
vzorec `describe || create`. S IAM výstupy zacházej jako s interní konfigurací.

## 2. Odhad nákladů a bod schválení

**Pouze odhad; žádost o vytvoření prostředků bude až samostatný krok.**
Scénář: 730 hodin/měsíc, 1 dedikovaná testovací schránka, 1 000 textových zpráv,
jedno Gemini volání na zprávu, 2 000 vstupních a 500 výstupních tokenů včetně
reasoningu na zprávu. Bez multimodality, RAG, Search, slev, DPH a odečtení kreditů.
Limity bezplatného provozu mohou být sdílené s jinými projekty; nespoléháme na ně.

| Položka | Návrh a plánovací částka za měsíc |
|---|---|
| Cloud SQL Enterprise | PostgreSQL 17, `db-f1-micro`, 0,6 GiB RAM, zonal, bez HA; compute + 10 GiB SSD + zálohy: orientačně **10–16 USD** |
| Cloud Run | Obě služby min. 0 instancí, 1 CPU / 512 MiB, Worker concurrency 1, max. 2 instance; při celkem 20–100 aktivních CPU sekundách na zprávu přibližně **0,51–2,53 USD** |
| Gemini 3.5 Flash v `eu` | Standard non-global: 2M input × 1,65 USD + 0,5M output × 9,90 USD = **8,25 USD** |
| Artifact Registry | Předpoklad 2 GiB uchovaných image: přibližně **0,20 USD** před free tierem |
| Secret Manager | Dvě aktivní verze + přibližně 4 000 čtení: přibližně **0,13 USD** před free tierem |
| Tasks / Pub/Sub | Několik tisíc malých operací/notifikací: řádově **pod 0,01 USD**, bez neočekávaných retry a velkých přenosů |
| Logging a drobné přenosy | Plánovací rezerva **1–2 USD**, nikoliv garantovaná cena |

Celková plánovací rezerva je **20–30 USD/měsíc** pro 1 000 takových zpráv.
Při 100 zprávách plánuj přibližně **12–20 USD/měsíc**; databáze se účtuje i bez e-mailů.
Rozpočet 20 USD proto není zaručeně dostačující pro první scénář.
Při 2 000 výstupních tokenech na každou z 1 000 zpráv (současný limit volání)
a stejném vstupu by samotný model stál 23,10 USD a celek přibližně 35–45 USD.
Ani tento scénář není finanční strop: vstup, retry a další funkce mohou spotřebu zvýšit.

Cloud SQL rozpětí není ověřená nabídka pro Belgium. Staticky dostupný ceník má
výchozí Iowa: micro 0,0105 USD/h, SSD 0,17 USD/GiB-měsíc a zálohy 0,08 USD/GiB-měsíc.
To dává referenci 7,67 + 1,70 + 0,80 = 10,17 USD při 10 GiB záloh.
Před schválením instance přilož regionální kalkulaci pro `europe-west1` a ověř
dostupnost micro tieru i skutečnou velikost záloh. Micro nemá SLA ani doložený výkon pro tento PoC.
[Cloud SQL ceník](https://cloud.google.com/sql/pricing).

Výpočet Cloud Run používá request billing 0,000024 USD/vCPU-s a
0,0000025 USD/GiB-s; nejde o naměřenou latenci.
[Cloud Run ceník](https://cloud.google.com/run/pricing).
Sazby modelu musí odpovídat Standard non-global, nikoliv levnějšímu Flex/Batch,
které nepředstavují tento workflow.
[Gemini ceník](https://cloud.google.com/model-garden/pricing).
Další zdroje: [Registry](https://cloud.google.com/artifact-registry/pricing),
[Secrets](https://cloud.google.com/secret-manager/pricing),
[Tasks](https://cloud.google.com/tasks/pricing), [Pub/Sub](https://cloud.google.com/pubsub/pricing).

Zůstatek kreditu není známý. Odhadovaný dopad je spotřeba přibližně stejné částky
z použitelného kreditu, případně fakturace dle účtu. Opakované inference, cold starty,
vyšší tokeny a budoucí Search/multimodalita mohou odhad zvýšit.

### Alerty a vynucené limity

Monitoring budget má být 20 USD s upozorněními 50/80/100 %. Alerts-only budget
nic automaticky nezastaví. Aktuální dokumentace podporuje samostatné spend caps
pro Cloud Run a Vertex AI, po jedné službě/projektu. Nepokrývají Cloud SQL a trvalé
úložiště; běžící požadavky doběhnou a vynucení není okamžité. Rozdělení dílčích
capů je další rozhodnutí před deploymentem, nikoliv automatické zdvojení rozpočtu.
[Spend caps a jejich omezení](https://docs.cloud.google.com/billing/docs/how-to/budgets-spend-caps).

Připravené příkazy pro alerts-only budget, nikoliv spend cap. `BILLING_ACCOUNT_ID`
doplň v Cloud Shellu; nejprve ověř, zda stejný budget již existuje. Tyto příkazy
nebyly spuštěny. Vyloučení kreditů z výpočtu sleduje hrubou spotřebu, aby ji trial kredit nezakryl:

```sh
gcloud billing budgets list --billing-account="${BILLING_ACCOUNT_ID:?Doplň billing account ID}"
gcloud billing budgets create --billing-account="$BILLING_ACCOUNT_ID" --display-name="Reply McFly PoC 20 USD" --budget-amount=20USD --calendar-period=month --filter-projects="projects/$PROJECT_NUMBER" --credit-types-treatment=exclude-all-credits --threshold-rule=percent=0.5 --threshold-rule=percent=0.8 --threshold-rule=percent=1.0
```

Další brzdy: max. instance, min. 0, concurrency/fronty, max. 3 pokusy,
token limit a vypnuté automatické zvětšování SQL disku. Nejde o globální finanční strop.

## 3. Chybějící prostředky — až po schválení nákladů

Tyto příkazy **nebyly spuštěny**. Spouštěj jednotlivě po schválení konkrétní
konfigurace a ověření, že prostředek skutečně chybí:

```sh
gcloud artifacts repositories create reply-mcfly --project="$PROJECT_ID" --location="$REGION" --repository-format=docker
```

```sh
gcloud sql instances create reply-mcfly-sql --project="$PROJECT_ID" --region="$REGION" --database-version=POSTGRES_17 --edition=ENTERPRISE --tier=db-f1-micro --availability-type=zonal --storage-type=SSD --storage-size=10GB --no-storage-auto-increase --backup-start-time=03:00 --retained-backups-count=7 --no-enable-point-in-time-recovery
```

Návrh je bez HA a PITR; denní zálohy se drží 7 dní. Čas zálohy je 03:00 UTC.
Před schválením potvrď, zda toto omezení vyhovuje PoC. Neotvírej přístup přes
`0.0.0.0/0`; pro spojení použij Cloud SQL Auth Proxy nebo vestavěný Cloud Run konektor.

```sh
gcloud sql instances describe reply-mcfly-sql --project="$PROJECT_ID" --format='yaml(connectionName,settings.tier,settings.ipConfiguration,settings.backupConfiguration)'
gcloud sql users set-password postgres --instance=reply-mcfly-sql --project="$PROJECT_ID" --prompt-for-password
```

DB role připrav v důvěryhodném SQL klientu přes Auth Proxy. Hesla zadávej
interaktivně přes `\password`, nikdy do zdrojáků, historie shellu nebo chatu:

```sql
CREATE ROLE mcfly_migrator LOGIN;
\password mcfly_migrator
CREATE ROLE mcfly_app LOGIN;
\password mcfly_app
CREATE DATABASE mcfly OWNER mcfly_migrator;
\connect mcfly
CREATE EXTENSION IF NOT EXISTS vector;
```

Po sestavení image v bodu 4 proveď migraci `alembic upgrade head` operátorem jako `mcfly_migrator` přes
lokální Auth Proxy; runtime účet ani Worker SA nesmí získat migrační credentials.
Pro tentýž image lze použít `docker run --rm --network host --env-file "$MIGRATION_ENV_FILE" "$IMAGE" alembic upgrade head`.
`MIGRATION_ENV_FILE` je soubor 0600 mimo Git s `MCFLY_DATABASE_URL` pro migrátora;
vytvoř jej bezpečně lokálně, ne pomocí vypsání hesla do shellu. Po použití odstraň jen tento dočasný soubor.
Potom jako vlastník tabulek uděl granty runtime účtu:

```sql
GRANT USAGE ON SCHEMA public TO mcfly_app;
GRANT SELECT, INSERT, UPDATE ON mailbox_sync_state, email_jobs, email_outbox TO mcfly_app;
GRANT SELECT ON alembic_version TO mcfly_app;
```

## 4. Image a konfigurace

V Cloud Shellu v checkoutu stejné revize, po schválení registru:

```sh
export IMAGE_TAG=europe-west1-docker.pkg.dev/reply-mcfly-poc/reply-mcfly/reply-mcfly:poc
gcloud auth configure-docker europe-west1-docker.pkg.dev
docker build --platform linux/amd64 --target runtime -t "$IMAGE_TAG" .
docker push "$IMAGE_TAG"
export IMAGE_DIGEST=$(gcloud artifacts docker images describe "$IMAGE_TAG" --project="$PROJECT_ID" --format='value(image_summary.digest)')
export IMAGE="europe-west1-docker.pkg.dev/reply-mcfly-poc/reply-mcfly/reply-mcfly@${IMAGE_DIGEST}"
```

Ingress i Worker nasazuj stejným `$IMAGE` s digestem. Lokální ověření bylo ARM64;
Cloud Run/AMD64 kompatibilita musí projít samostatným buildem a cloudovým testem.

Připrav `worker.env.yaml` mimo Git s nesenzitivní konfigurací podle `.env.example`:
projekt/region/model zůstávají schválené, `MCFLY_MAILBOX_ID` a JSON seznam
`MCFLY_ALLOWED_SENDERS` musí být nejprve potvrzené. Fronty jsou `sync-queue` a
`process-queue`. OAuth secret reference musí mít tvar
`projects/reply-mcfly-poc/secrets/NAZEV/versions/CISLO`.
URI databáze patří do Secret Manageru, ne do YAML.

Ingress env má jen projekt, region, mailbox, sync frontu, Worker URL, Tasks SA,
pubsub push SA a Ingress audience. **Ingress nepotřebuje DB URI, OAuth ani přístup k secrets.**

## 5. Gmail OAuth a secrets

**Stav: OTEVŘENO.** Podle posledního pokynu vlastníka se tento krok nyní neprovádí.

Nejprve potvrď dedikovanou schránku a allowlist. V Google Console připrav
OAuth klienta typu Desktop app a příslušné testovací uživatele consent screenu.
Na důvěryhodné pracovní stanici, se soubory mimo checkout:

```sh
uv run python -m reply_mcfly.oauth_setup --client-file /BEZPECNA_CESTA/client.json --output /BEZPECNA_CESTA/gmail-token.json
```

Program vyžaduje pouze `gmail.readonly` a `gmail.send`, používá loopback a PKCE,
soubor vytvoří s právy 0600 a existující soubor nepřepíše. Tento interaktivní
krok není provedený ani otestovaný proti skutečnému účtu.

Existenci secrets nejprve ověř. Až po schválení nákladů, s vybranými názvy:

```sh
gcloud secrets create "$OAUTH_SECRET_NAME" --project="$PROJECT_ID" --replication-policy=user-managed --locations="$REGION"
gcloud secrets versions add "$OAUTH_SECRET_NAME" --project="$PROJECT_ID" --data-file="$OAUTH_TOKEN_FILE"
gcloud secrets create "$DATABASE_SECRET_NAME" --project="$PROJECT_ID" --replication-policy=user-managed --locations="$REGION"
gcloud secrets versions add "$DATABASE_SECRET_NAME" --project="$PROJECT_ID" --data-file="$DATABASE_URI_FILE"
```

Všechny čtyři proměnné výše vyplň lokálně. Soubory musí být 0600 a mimo repo.
DB secret obsahuje URI runtime uživatele `mcfly_app` s Unix socketem
`/cloudsql/reply-mcfly-poc:europe-west1:reply-mcfly-sql`, nikoliv heslo migrátora.
Nezobrazuj secret values pomocí `gcloud secrets versions access` v konzoli.

## 6. IAM návrh — samostatná kontrola a schválení

Existující role z inventury nezakládej znovu. Následující tabulka popisuje
chybějící nebo neověřená oprávnění, **žádné nebylo aplikované**:

| Identita | Minimální účel a scope |
|---|---|
| Worker SA | Secret Accessor pouze na runtime DB a Gmail OAuth secretu |
| Tasks SA | Cloud Run Invoker pouze na Worker službě |
| Pub/Sub push identita | Cloud Run Invoker pouze na Ingress službě |
| Pub/Sub service agent | Token Creator na konkrétní push SA, pokud vazba chybí |
| Operátor deploymentu | Artifact push, Run deploy a actAs pouze potřebných runtime účtů; bez runtime zpřístupnění migračních secrets |

Návrh využije existující Ingress SA také jako push identitu. Použití musí projít
IAM review; případná samostatná push SA by byla další samostatně schválená změna.
Po schválení dané vazby jsou příkazy oddělené. Secret přístupy připrav před
nasazením Workeru:

```sh
gcloud secrets add-iam-policy-binding "$OAUTH_SECRET_NAME" --project="$PROJECT_ID" --member="serviceAccount:$WORKER_SA" --role=roles/secretmanager.secretAccessor
gcloud secrets add-iam-policy-binding "$DATABASE_SECRET_NAME" --project="$PROJECT_ID" --member="serviceAccount:$WORKER_SA" --role=roles/secretmanager.secretAccessor
```

Invoker vazby aplikuj až na existující služby po bodu 7, před subscription a Watch:

```sh
gcloud run services add-iam-policy-binding reply-mcfly-worker --project="$PROJECT_ID" --region="$REGION" --member="serviceAccount:$TASKS_SA" --role=roles/run.invoker
gcloud run services add-iam-policy-binding reply-mcfly-ingress --project="$PROJECT_ID" --region="$REGION" --member="serviceAccount:$INGRESS_SA" --role=roles/run.invoker
gcloud iam service-accounts add-iam-policy-binding "$INGRESS_SA" --project="$PROJECT_ID" --member="serviceAccount:service-${PROJECT_NUMBER}@gcp-sa-pubsub.iam.gserviceaccount.com" --role=roles/iam.serviceAccountTokenCreator
```

Pub/Sub model autentizace viz [oficiální postup](https://cloud.google.com/pubsub/docs/authenticate-push-subscriptions).
Ověř i existující Cloud Tasks service agent roli; nedoplňuj ji plošně bez evidence chybějící vazby.

## 7. Cloud Run — teprve po cenovém a IAM review

Předpoklady: migrace dokončená, existující secrets s explicitními verzemi,
vyplněný a schválený mailbox/allowlist, `worker.env.yaml` bez secrets,
`DATABASE_SECRET_VERSION` ve formátu `secret-name:version` a image s digestem.

```sh
gcloud run deploy reply-mcfly-worker --project="$PROJECT_ID" --region="$REGION" --image="$IMAGE" --service-account="$WORKER_SA" --no-allow-unauthenticated --cpu=1 --memory=512Mi --min-instances=0 --max-instances=2 --concurrency=1 --timeout=110 --add-cloudsql-instances="${PROJECT_ID}:${REGION}:reply-mcfly-sql" --env-vars-file=worker.env.yaml --set-secrets="MCFLY_DATABASE_URL=$DATABASE_SECRET_VERSION" --command=uvicorn --args=reply_mcfly.api.worker:create_worker,--factory,--host,0.0.0.0,--port,8080
export WORKER_URL=$(gcloud run services describe reply-mcfly-worker --project="$PROJECT_ID" --region="$REGION" --format='value(status.url)')
gcloud run services update reply-mcfly-worker --project="$PROJECT_ID" --region="$REGION" --update-env-vars="MCFLY_WORKER_URL=$WORKER_URL"
```

První Worker revision může mít Worker URL zatím prázdné: health ověří DB,
workflow zůstane 503 do nastavení vlastní audience. Ingress konfiguraci pak vyplň
s tímto Worker URL a schválenou push identitou; Ingress audience doplň po zjištění URL:

```sh
gcloud run deploy reply-mcfly-ingress --project="$PROJECT_ID" --region="$REGION" --image="$IMAGE" --service-account="$INGRESS_SA" --no-allow-unauthenticated --cpu=1 --memory=512Mi --min-instances=0 --max-instances=1 --concurrency=8 --timeout=30 --env-vars-file=ingress.env.yaml
export INGRESS_URL=$(gcloud run services describe reply-mcfly-ingress --project="$PROJECT_ID" --region="$REGION" --format='value(status.url)')
gcloud run services update reply-mcfly-ingress --project="$PROJECT_ID" --region="$REGION" --update-env-vars="MCFLY_INGRESS_AUDIENCE=$INGRESS_URL"
```

Obě služby vyžadují Cloud Run IAM a aplikace navíc ověřuje Google OIDC podpis,
issuer, audience, ověřený e-mail a přesnou servisní identitu. From zákazníka
není autentizace; allowlist pouze omezuje povolené adresáty automatické odpovědi.

## 8. Existující fronty a nová push subscription

Před finálním testem, po ověření deploymentu, uprav pouze souběžnost existující Sync Queue:

```sh
gcloud tasks queues update sync-queue --project="$PROJECT_ID" --location="$REGION" --max-concurrent-dispatches=1
```

Process Queue zůstává na 2. Nemění se retry/backoff a nevytváří se žádná fronta.
Subscription vytvoř až se známým HTTPS URL Ingressu a po IAM schválení:

```sh
gcloud pubsub subscriptions create gmail-events-push --project="$PROJECT_ID" --topic="$TOPIC" --push-endpoint="${INGRESS_URL}/events/gmail" --push-auth-service-account="$INGRESS_SA" --push-auth-token-audience="$INGRESS_URL" --ack-deadline=30 --min-retry-delay=10s --max-retry-delay=60s --message-retention-duration=7d
gcloud pubsub subscriptions describe gmail-events-push --project="$PROJECT_ID"
```

Audience je základní URL služby, endpoint obsahuje `/events/gmail`.
Topic `gmail-events` a jeho publisher binding se nemění.

## 9. Watch a skutečné ověření — NESPLNĚNO

Až bude OAuth hotové, mailbox/allowlist potvrzené a autentizované doručování
notifikací funkční, spusť jednorázově `python -m reply_mcfly.bootstrap` v důvěryhodném
prostředí s Worker konfigurací, DB spojením a ADC. Příkaz sám nenastavuje IAM ani
Pub/Sub. Uloží baseline před `watch`, zachová existující checkpoint a uloží expiraci.
Stejným příkazem lze Watch obnovit; automatický Scheduler bude další krok.

Živý gate musí doložit: Gmail → Pub/Sub → Ingress → sync/process → Gemini → Gmail,
threadId a reply hlavičky, pouze povoleného příjemce, jednu odpověď i při opakování
události a skutečnou latenci od Gmail internalDate do potvrzení odeslání pod 120 s.
Logy mají job_id, stav a dobu, nikoliv text zprávy, adresy, tokeny či odpovědi.
Ověř i skutečné Gemini `eu`: strukturovaný výstup, kvóty, multimodalitu a Search.
Dokumentace podporu modelu v `eu` uvádí, projektové ověření neproběhlo.
[Model a lokality](https://cloud.google.com/vertex-ai/generative-ai/docs/models/gemini/3-5-flash).
Přepnutí na `global` není povolené.

Recovery: při chybě fronty se neposune checkpoint, duplicitní jobs chrání UNIQUE,
expirovaný processing lease lze bezpečně převzít. `SENDING` po expiraci a
`DELIVERY_UNKNOWN` dovolují pouze dohledání Sent; nepotvrzené doručení přechází
do REVIEW_REQUIRED bez druhého sendu. Po vyčerpání Cloud Tasks pokusů potřebuje
operátor nový task pro tentýž job_id po expiraci lease. `HISTORY_EXPIRED` vyžaduje
řízenou resynchronizaci; automatický full resync zatím není implementovaný.
Neposouvej checkpoint ručně na aktuální hodnotu: mohl bys přeskočit nezpracované zprávy.

Samostatný recovery příkaz po ověření stavu a lease, s původním `JOB_ID`:

```sh
gcloud tasks create-http-task --project="$PROJECT_ID" --location="$REGION" --queue=process-queue --url="${WORKER_URL}/tasks/process" --method=POST --header='Content-Type:application/json' --body-content="{\"job_id\":\"${JOB_ID:?Doplň původní job UUID}\"}" --oidc-service-account-email="$TASKS_SA" --oidc-token-audience="$WORKER_URL"
```

Vytvoří nový task, ne nový email job. SENT a REVIEW_REQUIRED jsou ukončené stavy;
tento příkaz je neresetuje. Ruční změna FAILED na QUEUED zatím není implementovaná.
