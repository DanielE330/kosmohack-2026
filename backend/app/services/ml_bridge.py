"""Мост между FastAPI-бэкендом и обученным ML-ядром `backend/ml/`.

См. `backend/ml/README.md`, раздел «Контракт для Python-бэкенда»: пайплайн
восстановления пропусков и интерпретации аномалий поставляется как отдельный
пакет `backend/ml/src/*.py`, чьи модули импортируют друг друга голыми именами
(`from anomalies import ...`, `from config import ...`) в расчёте на
`sys.path.insert(0, "src")`. Здесь тот же приём делается абсолютным путём,
не зависящим от текущей рабочей директории — в Docker `WORKDIR=/app`
(содержимое `backend/`), а не `backend/ml/`, и локальный запуск pytest тоже
может стартовать из любого каталога.

Любая функция этого модуля обязана деградировать в `None`, а не бросать
исключение наружу — `app/services/gapfill.py` и `app/services/
anomaly_detection.py` при `None` откатываются на baseline-заглушки, поэтому
отсутствие ML-зависимостей в окружении не должно ронять веб-сервис.
"""

from __future__ import annotations

import logging
import sys
from datetime import date as date_type
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# backend/app/services/ml_bridge.py -> parents[2] == backend/
_ML_DIR = Path(__file__).resolve().parents[2] / "ml"
_ML_SRC_DIR = _ML_DIR / "src"
MODEL_PATH = _ML_DIR / "models" / "gap_model.joblib"

if str(_ML_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_ML_SRC_DIR))

try:
    import pandas as pd  # noqa: E402  (pandas всегда есть, см. requirements.txt)

    from anomalies import CRITICAL as ML_CRITICAL  # noqa: E402
    from anomalies import MODERATE as ML_MODERATE  # noqa: E402
    from anomalies import NORMAL as ML_NORMAL  # noqa: E402
    from anomalies import add_interpretation as _ml_add_interpretation  # noqa: E402
    from pipeline import restore_and_analyze as _restore_and_analyze  # noqa: E402

    ML_AVAILABLE = MODEL_PATH.exists()
    if not ML_AVAILABLE:
        logger.warning("Модель %s не найдена — ML gap-fill/интерпретация отключены", MODEL_PATH)
except Exception:  # pragma: no cover - защитный код на случай отсутствия ML-зависимостей
    logger.exception("backend/ml/src недоступен — используется baseline-логика")
    _ml_add_interpretation = None
    _restore_and_analyze = None
    ML_CRITICAL = "Критическая аномалия"
    ML_MODERATE = "Угнетение биомассы"
    ML_NORMAL = "Штатное развитие"
    ML_AVAILABLE = False


_SENSOR_FIELDS = [
    "s2_ndvi",
    "s2_evi",
    "s2_ndwi",
    "landsat_ndvi",
    "landsat_evi",
    "landsat_ndwi",
    "modis_ndvi",
    "modis_evi",
    "era5_temp_c",
    "era5_precip_mm",
]


def _observations_frame(observations: list) -> Any:
    rows = []
    for obs in observations:
        row = {
            "anon_polygon_id": obs.polygon_id,
            "date": obs.date,
            "crop_type": obs.crop_type,
            "primary_ndvi": obs.primary_ndvi,
            "doy": obs.doy,
            "ndvi_climatology_mean": obs.ndvi_climatology_mean,
            "ndvi_climatology_std": obs.ndvi_climatology_std,
            "n_reference_years": obs.n_reference_years,
        }
        for field in _SENSOR_FIELDS:
            row[field] = getattr(obs, field, None)
        rows.append(row)
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df["year"] = df["date"].dt.year.astype(float)
    df["is_synthetic_gap"] = df["primary_ndvi"].isna()
    return df


def predict_primary_ndvi(observations: list) -> dict[date_type, float] | None:
    """Восстанавливает `primary_ndvi` реальной обученной моделью
    (`backend/ml/models/gap_model.joblib`, контракт `pipeline.restore_and_analyze`)
    для ОДНОГО полигона.

    Возвращает ``{date: значение}`` для каждого наблюдения в ``observations``
    (известные значения возвращаются как есть, пропуски — прогнозом модели),
    либо ``None``, если ML недоступен или прогноз не удалось построить —
    тогда вызывающий код обязан откатиться на линейную интерполяцию.

    Считается только по наблюдениям одного полигона (без `reference`), поэтому
    признаки, требующие контекста других полигонов на ту же календарную дату
    (`date_target_median` и т.п. в `gap_features.py`), окажутся NaN — модель
    (HistGradientBoostingRegressor) обрабатывает NaN нативно, деградация
    качества некритична по сравнению с доминирующими признаками — соседними
    наблюдениями и историей самого полигона.
    """
    if not ML_AVAILABLE or _restore_and_analyze is None or not observations:
        return None
    try:
        df = _observations_frame(observations)
        if not df["is_synthetic_gap"].any():
            return {obs.date: obs.primary_ndvi for obs in observations}

        result = _restore_and_analyze(df, reference=None, model_path=MODEL_PATH)
        mapping: dict[date_type, float] = {}
        for row in result["series"]:
            value = row.get("primary_ndvi")
            if value is None:
                return None
            mapping[date_type.fromisoformat(row["date"])] = float(value)
        if len(mapping) != len(observations):
            return None
        return mapping
    except Exception:
        logger.exception("ML gap-fill упал — откатываемся на линейную интерполяцию")
        return None


def interpret_anomaly_causes(observations: list, status_lookup: dict[Any, str | None]) -> Any:
    """Строит по всему ряду полигона таблицу причин аномалий (`anomaly_reason`,
    `anomaly_cause`, `cause_confidence`, `requires_review` — см.
    `backend/ml/src/anomalies.add_interpretation`), НЕ пересчитывая сам факт
    аномалии: `anomaly_status` берётся из уже готового `status_lookup`
    (id объекта наблюдения -> одна из ML-строк ML_NORMAL/ML_MODERATE/
    ML_CRITICAL или None), посчитанного приложением по спецификации
    (`status_for_zscore` — эту формулу не трогаем). ML здесь только
    объясняет причину уже установленной аномалии.

    Возвращает DataFrame, индексированный ISO-датой (``YYYY-MM-DD``), либо
    ``None`` при недоступности ML или ошибке — тогда вызывающий код обязан
    откатиться на эвристику по ERA5.
    """
    if not ML_AVAILABLE or _ml_add_interpretation is None or not observations:
        return None
    try:
        rows = []
        for obs in observations:
            sensors = [v for v in (obs.s2_ndvi, obs.landsat_ndvi, obs.modis_ndvi) if v is not None]
            value_known = obs.primary_ndvi is not None
            rows.append(
                {
                    "anon_polygon_id": obs.polygon_id,
                    "date": obs.date,
                    "primary_ndvi": obs.primary_ndvi,
                    "crop_type": obs.crop_type,
                    "era5_temp_c": obs.era5_temp_c,
                    "era5_precip_mm": obs.era5_precip_mm,
                    "n_reference_years": obs.n_reference_years,
                    "value_kind": "measured" if value_known else "reconstructed",
                    "sensor_spread": (max(sensors) - min(sensors)) if len(sensors) >= 2 else None,
                    "anomaly_status": status_lookup.get(id(obs)),
                }
            )
        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"])
        result = _ml_add_interpretation(df)
        result = result.set_index(result["date"].dt.strftime("%Y-%m-%d"))
        return result
    except Exception:
        logger.exception("ML-интерпретация причины аномалии упала — используем эвристику ERA5")
        return None
