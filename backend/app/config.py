from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://vegmon:vegmon@localhost:5432/vegmon"
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24
    cors_origins: list[str] = ["*"]
    sql_echo: bool = False

    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_login: str | None = None
    smtp_password: str | None = None
    mail_from: str = "SkyTime <noreply@daniel.crazedns.ru>"
    frontend_base_url: str = "https://skytime.daniel.crazedns.ru"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
