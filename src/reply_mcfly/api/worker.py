from fastapi import FastAPI

from reply_mcfly.api.health import create_app


def create_worker() -> FastAPI:
    return create_app("worker")
