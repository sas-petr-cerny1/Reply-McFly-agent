from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from reply_mcfly.adapters.postgres_adapter import PostgresAdapter, make_engine
from reply_mcfly.application.diagnostics import DiagnosticsService
from reply_mcfly.config.settings import Settings


def create_app(
    service_name: Literal["ingress", "worker"],
    diagnostics: DiagnosticsService | None = None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if diagnostics is not None:
            app.state.diagnostics = diagnostics
            yield
        else:
            settings = Settings()
            app.state.settings = settings
            engine = make_engine(settings.sqlalchemy_url())
            app.state.engine = engine
            app.state.diagnostics = DiagnosticsService(PostgresAdapter(engine))
            try:
                yield
            finally:
                engine.dispose()

    app = FastAPI(title=f"Reply McFly {service_name}", lifespan=lifespan)

    @app.get("/health")
    def health() -> JSONResponse:
        try:
            check: Callable[[], None] = app.state.diagnostics.check_health
            check()
        except (SQLAlchemyError, RuntimeError):
            return JSONResponse(
                status_code=503,
                content={
                    "status": "unavailable",
                    "service": service_name,
                    "database": "unavailable",
                },
            )
        return JSONResponse(content={"status": "ok", "service": service_name, "database": "ok"})

    return app
