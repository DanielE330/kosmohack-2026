import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.user import User
from app.schemas.auth import ConfirmEmailRequest, LoginRequest, RegisterResponse, Token
from app.schemas.user import UserCreate
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Регистрация пользователя (требует подтверждения почты перед входом)",
)
async def register(payload: UserCreate, db: AsyncSession = Depends(get_db)) -> RegisterResponse:
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Пользователь с таким email уже зарегистрирован")

    # Реальная отправка письма ещё не подключена — токен возвращается прямо
    # в ответе, фронтенд сразу ведёт пользователя на экран подтверждения.
    confirmation_token = secrets.token_urlsafe(24)
    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        is_email_confirmed=False,
        email_confirmation_token=confirmation_token,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return RegisterResponse(
        user_id=user.id, email=user.email, email_confirmation_token=confirmation_token
    )


@router.post(
    "/confirm-email",
    response_model=Token,
    summary="Подтвердить почту токеном из /auth/register и сразу получить JWT",
)
async def confirm_email(payload: ConfirmEmailRequest, db: AsyncSession = Depends(get_db)) -> Token:
    result = await db.execute(select(User).where(User.email_confirmation_token == payload.token))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Неверный или уже использованный токен")

    user.is_email_confirmed = True
    user.email_confirmation_token = None
    await db.commit()
    return Token(access_token=create_access_token(user.email))


@router.post("/login", response_model=Token, summary="Вход, получение JWT")
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> Token:
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Неверный email или пароль")
    if not user.is_email_confirmed:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Почта не подтверждена")
    return Token(access_token=create_access_token(user.email))
