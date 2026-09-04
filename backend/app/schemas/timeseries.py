from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class NdviPointOut(BaseModel):
    """Одна точка временного ряда, как её ждёт Flutter-клиент
    (`frontend/lib/models/ndvi_point.dart`)."""

    model_config = ConfigDict(from_attributes=True)

    date: date = Field(..., examples=["2025-06-14"])
    primary_ndvi: float | None = Field(
        None,
        description="Реальное наблюдение NDVI на эту дату; null — если это пропуск "
        "(естественный или скрытый is_synthetic_gap)",
        examples=[0.62],
    )
    primary_ndvi_pred: float | None = Field(
        None,
        description="Восстановленное/предсказанное значение NDVI — используется на "
        "графике вместо primary_ndvi, когда оно равно null",
        examples=[0.60],
    )
    is_synthetic_gap: bool = Field(
        False, description="True, если значение было скрыто организаторами для проверки восстановления"
    )
    climatology_mean: float | None = Field(
        None, validation_alias="ndvi_climatology_mean", description="Средний NDVI за этот день года", examples=[0.58]
    )
    climatology_std: float | None = Field(
        None,
        validation_alias="ndvi_climatology_std",
        description="Стандартное отклонение NDVI за этот день года",
        examples=[0.06],
    )
    crop_type: str | None = Field(None, examples=["озимая пшеница"])


class NdviObservationIn(BaseModel):
    """Одна строка сырых наблюдений ДЗЗ для загрузки через
    `POST /timeseries/{anon_polygon_id}/upload` — формат как в
    `train_dataset.csv`/`private_features.csv`."""

    date: date = Field(..., examples=["2025-06-14"])
    s2_ndvi: float | None = Field(None, examples=[0.61])
    s2_evi: float | None = Field(None, examples=[0.42])
    s2_ndwi: float | None = Field(None, examples=[0.12])
    landsat_ndvi: float | None = Field(None, examples=[None])
    landsat_evi: float | None = Field(None, examples=[None])
    landsat_ndwi: float | None = Field(None, examples=[None])
    modis_ndvi: float | None = Field(None, examples=[None])
    modis_evi: float | None = Field(None, examples=[None])
    era5_temp_c: float | None = Field(None, description="Температура воздуха, °C", examples=[24.3])
    era5_precip_mm: float | None = Field(None, description="Осадки, мм", examples=[0.4])
    primary_ndvi: float | None = Field(
        None,
        description="Значение сенсора, реально снявшего сцену в этот день (Sentinel-2 в "
        "приоритете). Оставить null, если наблюдения нет — будет восстановлено.",
        examples=[0.61],
    )
    crop_type: str | None = Field(None, examples=["озимая пшеница"])
