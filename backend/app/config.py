from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://vegmon:vegmon@localhost:5432/vegmon"
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24
    cors_origins: list[str] = ["*"]
    sql_echo: bool = False

    # Витринные аккаунты для показа продукта заводятся на старте
    # (app/services/demo_seed.py). Флаг — чтобы боевой стенд мог их
    # выключить: пароли у них публичные и лежат прямо в репозитории.
    seed_demo_accounts: bool = True

    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_login: str | None = None
    smtp_password: str | None = None
    mail_from: str = "SkyTime <noreply@daniel.crazedns.ru>"
    frontend_base_url: str = "https://skytime.daniel.crazedns.ru"

    # Google Earth Engine — живой многоисточниковый сбор данных
    # (Sentinel-2/Landsat/MODIS/ERA5), см. app/services/gee_bridge.py.
    # Требует `earthengine authenticate` (кладёт credentials в
    # ~/.config/earthengine/credentials того пользователя, от которого
    # запущен процесс) — секрет, не хранится в репозитории.
    earthengine_project: str | None = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
