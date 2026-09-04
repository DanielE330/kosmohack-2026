from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr = Field(
        ..., description="Email пользователя, используется как логин", examples=["agronomist@example.com"]
    )
    password: str = Field(..., min_length=8, description="Пароль, минимум 8 символов", examples=["StrongPass123"])
    full_name: str | None = Field(None, description="Имя пользователя (опционально)", examples=["Иван Агрономов"])


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., examples=[1])
    email: EmailStr
    full_name: str | None
    created_at: datetime
