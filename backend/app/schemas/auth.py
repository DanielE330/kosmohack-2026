from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr = Field(..., examples=["agronomist@example.com"])
    password: str = Field(..., examples=["StrongPass123"])


class Token(BaseModel):
    access_token: str = Field(
        ..., description="JWT — передавать в заголовке `Authorization: Bearer <token>`"
    )
    token_type: str = Field("bearer", description="Тип токена — всегда 'bearer'")
