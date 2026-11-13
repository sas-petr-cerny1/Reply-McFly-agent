from typing import Literal

from pydantic import Field, PostgresDsn, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from reply_mcfly.domain.sender_policy import (
    WILDCARD_SENDER,
    SenderConfigurationError,
    SenderPolicy,
    parse_sender_policy,
)

# Fixed by the database column type; changing it needs a migration and a full reindex.
RAG_VECTOR_DIMENSIONS = 768


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MCFLY_", extra="ignore")

    database_url: SecretStr | None = None
    gcp_project_id: str = Field(default="reply-mcfly-poc", validation_alias="GCP_PROJECT_ID")
    gcp_region: str = Field(default="europe-west1", validation_alias="GCP_REGION")
    vertex_ai_location: str = Field(default="eu", validation_alias="VERTEX_AI_LOCATION")
    gemini_model: str = Field(default="gemini-3.5-flash", validation_alias="GEMINI_MODEL")
    mailbox_id: str = ""
    allowed_senders: frozenset[str] = frozenset()

    @field_validator("mailbox_id")
    @classmethod
    def normalize_mailbox_id(cls, value: str) -> str:
        # One spelling everywhere: the value is a database key and an OIDC-checked identity.
        return value.strip().casefold()

    @field_validator("allowed_senders")
    @classmethod
    def validate_allowed_senders(cls, value: frozenset[str]) -> frozenset[str]:
        if not value:
            return value
        if WILDCARD_SENDER in value:
            if value != frozenset({WILDCARD_SENDER}):
                raise ValueError('MCFLY_ALLOWED_SENDERS allow-all mode requires exactly ["*"]')
            return value
        for address in value:
            if not address.strip() or "@" not in address:
                raise ValueError(
                    'MCFLY_ALLOWED_SENDERS must contain valid email addresses or ["*"]'
                )
        return frozenset(address.casefold() for address in value)

    def sender_policy(self) -> SenderPolicy:
        try:
            return parse_sender_policy(self.allowed_senders, self.mailbox_id)
        except SenderConfigurationError as error:
            raise ValueError(str(error)) from error

    gmail_oauth_secret_version: str = ""
    sync_queue: str = ""
    process_queue: str = ""
    worker_url: str = ""
    ingress_audience: str = ""
    pubsub_service_account: str = ""
    tasks_service_account: str = ""
    gmail_topic: str = "projects/reply-mcfly-poc/topics/gmail-events"
    # Replies to one sender per 24 hours before further mail goes to manual review.
    sender_daily_reply_limit: int = Field(default=20, ge=1)
    enable_rag: bool = False
    enable_web_search: bool = False
    web_search_timeout_seconds: float = Field(default=15.0, ge=4, le=30)
    rag_backend: Literal["markdown", "pgvector"] = "markdown"
    rag_embedding_model: str = Field(default="gemini-embedding-001", min_length=1)
    rag_embedding_dims: int = 768
    # Empty means GCP_REGION; the embedding model must be available in this location.
    rag_embedding_location: str = ""
    rag_top_k: int = Field(default=3, ge=1, le=3)
    rag_timeout_seconds: float = Field(default=10.0, ge=4, le=30)

    @field_validator("rag_embedding_dims")
    @classmethod
    def validate_rag_embedding_dims(cls, value: int) -> int:
        if value != RAG_VECTOR_DIMENSIONS:
            raise ValueError(
                f"MCFLY_RAG_EMBEDDING_DIMS must be {RAG_VECTOR_DIMENSIONS}: "
                "the rag_product_chunks.embedding column is vector(768)"
            )
        return value

    def sqlalchemy_url(self) -> str:
        if self.database_url is None:
            raise ValueError("MCFLY_DATABASE_URL is required for Worker and database operations")
        value = self.database_url.get_secret_value()
        PostgresDsn(value)
        if not value.startswith("postgresql+psycopg://"):
            raise ValueError("MCFLY_DATABASE_URL must use postgresql+psycopg://")
        return value
