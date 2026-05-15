from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    discord_webhook_url: str = ""

    database_url: str = "sqlite+aiosqlite:///./perix_sentinel.db"


settings = Settings()
