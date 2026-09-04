from pydantic import BaseModel, ConfigDict, Field

Point = tuple[float, float]  # [lat, lon]

_EXAMPLE_POINTS = [[10.02, 105.77], [10.02, 105.79], [10.04, 105.79], [10.04, 105.77]]


class PolygonCreate(BaseModel):
    """Тело запроса `POST /polygons/custom` — пользователь нарисовал контур на карте."""

    points: list[Point] = Field(
        ...,
        min_length=3,
        description="Контур полигона: список точек [lat, lon], минимум 3 точки",
        examples=[_EXAMPLE_POINTS[:3]],
    )
    label: str | None = Field(None, description="Подпись, опционально", examples=["Мой полигон"])
    crop_type: str | None = Field(None, description="Культура, опционально", examples=["озимая пшеница"])


class PolygonUpdate(BaseModel):
    """Частичное обновление своего полигона (только владелец)."""

    label: str | None = Field(None, examples=["Поле №4"])
    crop_type: str | None = Field(None, examples=["подсолнечник"])
    points: list[Point] | None = Field(None, min_length=3)


class PolygonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    anon_polygon_id: str = Field(
        ..., validation_alias="id", description="Идентификатор полигона", examples=["AOI-0002"]
    )
    label: str | None = Field(None, description="Подпись для UI", examples=["AOI-0002"])
    crop_type: str | None = Field(None, description="Культура", examples=["озимая пшеница"])
    area_id: str | None = Field(None, description="Группировка по территории", examples=[None])
    is_custom: bool = Field(..., description="True — нарисован пользователем, False — из датасета", examples=[False])
    points: list[Point] = Field(
        ..., description="Контур полигона: список точек [lat, lon]", examples=[_EXAMPLE_POINTS]
    )
