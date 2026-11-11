FROM ghcr.io/astral-sh/uv:0.13.5 AS uv
FROM python:3.12-slim-trixie AS python-base
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
RUN apt-get update \
    && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 10001 --create-home app

FROM python-base AS build
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_NO_CACHE=1
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
COPY migrations ./migrations
COPY alembic.ini ./
RUN uv sync --frozen --no-dev

FROM build AS test
RUN uv sync --frozen
COPY tests ./tests
COPY typings ./typings
ENV PYTEST_ADDOPTS="-o cache_dir=/tmp/pytest-cache" MYPY_CACHE_DIR=/tmp/mypy-cache RUFF_CACHE_DIR=/tmp/ruff-cache
USER app
CMD ["pytest"]

FROM python-base AS runtime
COPY --from=build /app /app
USER app
EXPOSE 8080
CMD ["uvicorn", "reply_mcfly.api.ingress:create_ingress", "--factory", "--host", "0.0.0.0", "--port", "8080"]
