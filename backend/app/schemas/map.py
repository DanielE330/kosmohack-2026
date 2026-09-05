from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.map import MapRole


class MapCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, examples=["Поля клиента N"])


class MapOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    owner_id: int
    created_at: datetime
    # Роль текущего пользователя на этой карте — owner неявный (см.
    # app/services/maps.py), поэтому это не то же самое, что MapRole.
    role: str = Field(..., description="'owner' | 'viewer' | 'editor'", examples=["owner"])


class InviteRequest(BaseModel):
    email: EmailStr = Field(..., examples=["colleague@example.com"])
    role: MapRole = Field(MapRole.viewer, examples=["viewer"])


class MemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    invited_email: str
    role: MapRole
