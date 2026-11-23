from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "IDEA-1026"
    app_env: str = "local"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./idea1026.db"
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
