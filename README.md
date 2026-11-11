# Reply McFly agent

Lokální Docker skeleton RM-001 podle `docs/reply_mcfly_agent_BLUEPRINT.md`
a schválených upřesnění. Python 3.12, FastAPI Ingress a Worker ze stejného image,
PostgreSQL 17 / pgvector, SQLAlchemy 2 a Alembic.

**Lokální část je ověřená; skutečný Gmail/GCP E2E a cíl 120 sekund jsou NESPLNĚNÉ.**
Rekonstruovaná meziverze; cloudový deployment nebyl proveden.

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
## Testy v Dockeru

```sh
docker compose run --build --rm tests
docker compose run --rm tests ruff check src tests migrations
docker compose run --rm tests ruff format --check src tests migrations
docker compose run --rm tests mypy
docker compose exec -T ingress alembic check
docker compose run --rm tests bandit -r src -q
docker compose run --rm tests pip-audit --local --skip-editable --progress-spinner off
```

Testovací profil vytvoří dočasný čtvrtý kontejner ze stage `test` stejného
Dockerfile. Integrační testy používají skutečný PostgreSQL a syntetická data.

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


Runtime a test stage běží pod UID 10001; build context vylučuje lokální credentials.
Security release gate zůstává oddělený od lokální rekonstrukce historie.
