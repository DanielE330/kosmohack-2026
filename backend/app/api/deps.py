import httpx
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.security import decode_access_token

__all__ = ["get_db", "get_current_user", "get_http_client"]

_bearer_scheme = HTTPBearer(auto_error=False)


def get_http_client(request: Request) -> httpx.AsyncClient:
    """Общий на всё приложение `httpx.AsyncClient` (пул соединений) —
    используется для похода в внешние открытые источники (Overpass/Nominatim,
    см. `app/services/region_search.py`). Обычно создаётся/закрывается в
    `app.main.lifespan`; ленивое создание здесь — подстраховка для тестов
    через `ASGITransport`, который не гоняет lifespan-события."""
    client = getattr(request.app.state, "http_client", None)
    if client is None:
        client = httpx.AsyncClient()
        request.app.state.http_client = client
    return client


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Не авторизован")

    email = decode_access_token(credentials.credentials)
    if email is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Невалидный или истёкший токен")

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Пользователь не найден")
    return user


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Как [get_current_user], но `None` вместо 401 без токена/с невалидным
    токеном — нужно там, где часть ответа публична (открытые сидовые
    полигоны датасета), а часть видна только вошедшим (свои карты)."""
    if credentials is None:
        return None
    email = decode_access_token(credentials.credentials)
    if email is None:
        return None
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()
