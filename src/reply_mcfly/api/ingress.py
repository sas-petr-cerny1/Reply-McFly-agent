from fastapi import FastAPI

from reply_mcfly.api.health import create_app


def create_ingress() -> FastAPI:
    return create_app("ingress")
