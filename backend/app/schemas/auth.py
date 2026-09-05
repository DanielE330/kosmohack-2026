from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr = Field(..., examples=["agronomist@example.com"])
    password: str = Field(..., examples=["StrongPass123"])


class Token(BaseModel):
    access_token: str = Field(
        ..., description="JWT — передавать в заголовке `Authorization: Bearer <token>`"
    )
    token_type: str = Field("bearer", description="Тип токена — всегда 'bearer'")


class ConfirmEmailRequest(BaseModel):
    token: str = Field(..., description="Токен подтверждения из /auth/register")


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., examples=["StrongPass123"])
    new_password: str = Field(..., min_length=8, examples=["EvenStrongerPass456"])


class ChangeEmailRequest(BaseModel):
    new_email: EmailStr = Field(..., examples=["new-address@example.com"])
    password: str = Field(..., description="Текущий пароль — подтверждение, что смену запрашивает владелец")


class RegisterResponse(BaseModel):
    """Ответ на регистрацию.

    `email_confirmation_token` — временная замена реальной отправки письма
    (см. tasks/backend.md): пока нет почтового сервиса, токен отдаётся
    прямо в ответе, чтобы фронтенд мог сразу пройти подтверждение. Когда
    подключим реальную отправку — это поле уйдёт, останется только
    `user`."""

    user_id: int
    email: EmailStr
    email_confirmation_token: str
