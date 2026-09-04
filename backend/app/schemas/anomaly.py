from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import NdviStatus


class AnomalyOut(BaseModel):
    """Период аномалии, как его ждёт Flutter-клиент (`frontend/lib/models/anomaly.dart`)."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., examples=["AOI-0001-2025-06-14"])
    anon_polygon_id: str = Field(..., validation_alias="polygon_id", examples=["AOI-0001"])
    start_date: date = Field(..., examples=["2025-06-14"])
    end_date: date = Field(..., examples=["2025-09-01"])
    severity: NdviStatus = Field(
        ..., description="'suppression' (угнетение биомассы) или 'critical' (критическая аномалия)",
        examples=["critical"],
    )
    min_z_score: float = Field(..., description="Наихудший Z-score в периоде", examples=[-2.4])
    deviation: float = Field(
        ..., description="Отклонение NDVI от климатической нормы (отрицательное значение)", examples=[-0.31]
    )
    explanation: str = Field(
        "",
        description="Текстовая интерпретация вероятной причины аномалии (сопоставление с ERA5)",
        examples=[
            "NDVI ниже климатической нормы на 0.31; осадков за период почти не было "
            "(2.1 мм) — вероятна почвенная засуха."
        ],
    )
