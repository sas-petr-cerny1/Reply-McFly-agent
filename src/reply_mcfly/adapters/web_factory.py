"""Selects the live web-search backend from configuration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from reply_mcfly.adapters.vertex_web_search_adapter import VertexWebSearchAdapter
from reply_mcfly.application.web_query import build_web_public_query
from reply_mcfly.config.settings import Settings
from reply_mcfly.domain.email import IncomingEmail
from reply_mcfly.ports.capabilities import WebSearchProvider


@dataclass(frozen=True)
class WebSearchComponents:
    provider: WebSearchProvider | None
    query_builder: Callable[[IncomingEmail], str]
    timeout: float


def build_web_search(settings: Settings) -> WebSearchComponents:
    if not settings.enable_web_search:
        return WebSearchComponents(None, build_web_public_query, 0.0)
    provider = VertexWebSearchAdapter(
        settings.gcp_project_id,
        settings.vertex_ai_location,
        settings.gemini_model,
    )
    return WebSearchComponents(
        provider,
        build_web_public_query,
        settings.web_search_timeout_seconds,
    )
