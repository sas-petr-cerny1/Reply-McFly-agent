from pydantic import Field, PostgresDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MCFLY_", extra="ignore")

    database_url: SecretStr | None = None
    gcp_project_id: str = Field(default="reply-mcfly-poc", validation_alias="GCP_PROJECT_ID")
    gcp_region: str = Field(default="europe-west1", validation_alias="GCP_REGION")
    vertex_ai_location: str = Field(default="eu", validation_alias="VERTEX_AI_LOCATION")
    gemini_model: str = Field(default="gemini-3.5-flash", validation_alias="GEMINI_MODEL")
    mailbox_id: str = ""
    allowed_senders: frozenset[str] = frozenset()
    gmail_oauth_secret_version: str = ""
    sync_queue: str = ""
    process_queue: str = ""
    worker_url: str = ""
    ingress_audience: str = ""
    pubsub_service_account: str = ""
    tasks_service_account: str = ""

    def sqlalchemy_url(self) -> str:
        if self.database_url is None:
            raise ValueError("MCFLY_DATABASE_URL is required for Worker and database operations")
        value = self.database_url.get_secret_value()
        PostgresDsn(value)
        if not value.startswith("postgresql+psycopg://"):
            raise ValueError("MCFLY_DATABASE_URL must use postgresql+psycopg://")
        return value
