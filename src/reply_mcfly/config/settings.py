from pydantic import PostgresDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MCFLY_", extra="ignore")

    database_url: SecretStr | None = None

    def sqlalchemy_url(self) -> str:
        if self.database_url is None:
            raise ValueError("MCFLY_DATABASE_URL is required for Worker and database operations")
        value = self.database_url.get_secret_value()
        PostgresDsn(value)
        if not value.startswith("postgresql+psycopg://"):
            raise ValueError("MCFLY_DATABASE_URL must use postgresql+psycopg://")
        return value
