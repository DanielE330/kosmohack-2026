"""Общие фикстуры для тестов эндпоинтов.

Тесты используют **отдельную** базу `vegmon_test` (создаётся сама при
первом запуске) — никогда не трогают основную `vegmon`, куда уже загружен
реальный `train_dataset.csv`. Каждый тест получает чистые таблицы
(`create_all` перед тестом, `drop_all` после) и свою async-сессию,
подставленную вместо `get_db` через `app.dependency_overrides` — реальная
БД поднимается один раз (`docker compose up -d db`), сам FastAPI-процесс
не нужен, эндпоинты вызываются напрямую через ASGI-транспорт.
"""

import os

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app

_DEV_DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+asyncpg://vegmon:vegmon@localhost:5432/vegmon"
)
# Тестовая БД — тот же сервер, что и dev, но отдельное имя.
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    _DEV_DATABASE_URL.rsplit("/", 1)[0] + "/vegmon_test",
)


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def _ensure_test_database_exists():
    # Не autouse: чистые юнит-тесты (test_gapfill.py, test_region_search.py)
    # не поднимают БД вообще и не должны требовать доступный Postgres —
    # только тесты, которые реально просят `db_session`/`client`.
    admin_url = _DEV_DATABASE_URL.rsplit("/", 1)[0] + "/vegmon"
    db_name = TEST_DATABASE_URL.rsplit("/", 1)[1]
    admin_engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    async with admin_engine.connect() as conn:
        exists = await conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": db_name}
        )
        if exists.scalar() is None:
            await conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    await admin_engine.dispose()


@pytest_asyncio.fixture
async def db_session(_ensure_test_database_exists):
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session):
    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
