"""Typed runtime configuration loaded from environment variables."""

from decimal import Decimal
from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings. Secrets are provided only by environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
    )

    app_env: str = Field(default="development", validation_alias="APP_ENV")
    app_name: str = Field(default="Velina Cosmetic Bot", validation_alias="APP_NAME")
    public_base_url: str = Field(default="https://romanandr.ru", validation_alias="PUBLIC_BASE_URL")
    database_url: str = Field(validation_alias="DATABASE_URL")
    redis_url: str = Field(default="redis://redis:6379/0", validation_alias="REDIS_URL")

    bot_token: SecretStr = Field(validation_alias="BOT_TOKEN")
    owner_telegram_id: int = Field(validation_alias="OWNER_TELEGRAM_ID")
    webhook_secret: SecretStr = Field(validation_alias="WEBHOOK_SECRET")
    loyalty_code_pepper: SecretStr = Field(validation_alias="LOYALTY_CODE_PEPPER")
    telegram_mode: Literal["webhook", "polling"] = Field(
        default="polling", validation_alias="TELEGRAM_MODE"
    )
    telegram_proxy_url: SecretStr | None = Field(
        default=None,
        validation_alias="TELEGRAM_PROXY_URL",
    )

    alert_telegram_id: int | None = Field(default=None, validation_alias="ALERT_TELEGRAM_ID")
    monitor_interval_seconds: int = Field(
        default=900, ge=30, validation_alias="MONITOR_INTERVAL_SECONDS"
    )
    disk_alert_percent: int = Field(default=85, ge=1, le=100, validation_alias="DISK_ALERT_PERCENT")
    backup_max_age_hours: int = Field(default=26, ge=1, validation_alias="BACKUP_MAX_AGE_HOURS")
    backup_dir: str = Field(default="/backups", validation_alias="BACKUP_DIR")
    fsm_ttl_seconds: int = Field(default=259200, ge=0, validation_alias="FSM_TTL_SECONDS")

    birthday_cashback_percent: Decimal = Field(
        default=Decimal("10.00"),
        ge=0,
        le=100,
        validation_alias="BIRTHDAY_CASHBACK_PERCENT",
    )
    birthday_cashback_window_days: int = Field(
        default=3,
        ge=0,
        le=31,
        validation_alias="BIRTHDAY_CASHBACK_WINDOW_DAYS",
    )

    google_sheets_credentials_file: str | None = Field(
        default=None,
        validation_alias="GOOGLE_SHEETS_CREDENTIALS_FILE",
    )
    google_sheet_name: str = Field(default="products", validation_alias="GOOGLE_SHEET_NAME")
    product_sync_interval_seconds: int = Field(
        default=3600,
        validation_alias="PRODUCT_SYNC_INTERVAL_SECONDS",
    )

    @property
    def webhook_url(self) -> str:
        """The Telegram webhook endpoint for the deployed application."""
        return f"{self.public_base_url.rstrip('/')}/api/telegram/webhook"

    @property
    def effective_alert_id(self) -> int:
        """Telegram chat that receives operational alerts, defaulting to the owner."""
        if self.alert_telegram_id is not None:
            return self.alert_telegram_id
        return self.owner_telegram_id


@lru_cache
def get_settings() -> Settings:
    """Build settings once per process."""
    return Settings()
