"""Application settings, loaded from environment variables and the .env file."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    # hide_input_in_errors: a rejected value must not appear in a startup error or log.
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", hide_input_in_errors=True
    )

    app_name: str = "ShopEase Auth Service"
    app_version: str = "0.1.0"
    app_env: str = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "debug", "info", "warning", "error"] = "INFO"
    api_prefix: str = "/api"
    docs_enabled: bool = True

    mysql_database: str = "shopease_auth_db"
    mysql_user: str
    # SecretStr keeps secrets masked in repr() and logs. Neither secret has a default.
    mysql_password: SecretStr
    mysql_host: str = "127.0.0.1"
    mysql_port: int = Field(default=3306, ge=1, le=65535)

    jwt_secret_key: SecretStr = Field(min_length=32)
    # HMAC only: the service signs and verifies with one shared secret.
    jwt_algorithm: Literal["HS256", "HS384", "HS512"] = "HS256"
    access_token_expire_minutes: int = Field(default=30, ge=1, le=1440)

    @field_validator("mysql_password", "jwt_secret_key")
    @classmethod
    def reject_placeholder(cls, value: SecretStr) -> SecretStr:
        if value.get_secret_value().lower().startswith("change-me"):
            raise ValueError("replace the placeholder value from .env.example")
        return value

    @property
    def database_url(self) -> URL:
        """Connection URL. URL.create escapes special characters, and str(URL) masks the password."""
        return URL.create(
            "mysql+pymysql",
            username=self.mysql_user,
            password=self.mysql_password.get_secret_value(),
            host=self.mysql_host,
            port=self.mysql_port,
            database=self.mysql_database,
        )


@lru_cache
def get_settings() -> Settings:
    """Return one cached Settings instance for the whole process."""
    return Settings()
