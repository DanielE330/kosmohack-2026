"""Детекция, объединение в периоды и интерпретация аномалий вегетации."""
from __future__ import annotations

import numpy as np
import pandas as pd

from config import (
    COLD_7D_C,
    DATE_COL,
    DRY_14D_MM,
    HARVEST_DROP_PER_DAY,
    HOT_7D_C,
    ID_COL,
    SENSOR_SPREAD_WARNING,
    TARGET_COL,
    Z_THRESHOLD_CRITICAL,
    Z_THRESHOLD_MODERATE,
)


NORMAL = "Штатное развитие"
MODERATE = "Угнетение биомассы"
CRITICAL = "Критическая аномалия"

CAUSE_SENSOR_CONFLICT = "sensor_conflict"
CAUSE_HEAT_DROUGHT = "heat_and_drought"
CAUSE_DROUGHT = "moisture_deficit"
CAUSE_HEAT = "heat_stress"
CAUSE_COLD = "cold_stress"
CAUSE_HARVEST = "possible_harvest"
CAUSE_MIXED = "weather_or_harvest"
CAUSE_UNKNOWN = "unconfirmed"


def compute_zscore(df: pd.DataFrame, ndvi_col: str = TARGET_COL) -> pd.DataFrame:
    result = df.copy()
    denominator = result["ndvi_climatology_std"].replace(0, np.nan)
    result["z_score"] = (
        result[ndvi_col] - result["ndvi_climatology_mean"]
    ) / denominator
    return result


def classify_anomaly(z: float) -> str | None:
    if pd.isna(z):
        return None
    if z >= Z_THRESHOLD_MODERATE:
        return NORMAL
    if z >= Z_THRESHOLD_CRITICAL:
        return MODERATE
    return CRITICAL


def _confidence(row: pd.Series) -> float | None:
    if pd.isna(row.get("z_score")):
        return None
    years = row.get("n_reference_years", np.nan)
    std = row.get("ndvi_climatology_std", np.nan)
    confidence = 0.35 if pd.isna(years) else min(0.9, 0.3 + 0.1 * float(years))
    if pd.isna(std) or std < 0.015:
        confidence *= 0.7
    if row.get("value_kind") == "reconstructed":
        # A filled value is useful for the curve, but cannot carry the same
        # evidential weight as a cloud-free satellite observation.
        confidence *= 0.55
    sensor_spread = row.get("sensor_spread", np.nan)
    if pd.notna(sensor_spread) and float(sensor_spread) > 0.10:
        confidence *= 0.70
    return round(float(confidence), 2)


def add_anomaly_status(df: pd.DataFrame) -> pd.DataFrame:
    result = compute_zscore(df)
    result["anomaly_status"] = result["z_score"].apply(classify_anomaly)
    result["anomaly_confidence"] = result.apply(_confidence, axis=1)
    return result


def add_weather_context(df: pd.DataFrame) -> pd.DataFrame:
    """Считает причинные погодные признаки только по прошлым и текущей датам."""
    result = df.copy()
    result[DATE_COL] = pd.to_datetime(result[DATE_COL])
    result = result.sort_values([ID_COL, DATE_COL])
    grouped = result.groupby(ID_COL, group_keys=False)

    if "era5_precip_mm" in result and "precip_14d" not in result:
        result["precip_14d"] = np.nan
        for _, indices in result.groupby(ID_COL).groups.items():
            ordered = result.loc[indices].sort_values(DATE_COL)
            rolling = (
                ordered.set_index(DATE_COL)["era5_precip_mm"]
                .rolling("14D", min_periods=1)
                .sum()
            )
            result.loc[ordered.index, "precip_14d"] = rolling.to_numpy()
    if "era5_temp_c" in result and "temp_7d" not in result:
        result["temp_7d"] = np.nan
        for _, indices in result.groupby(ID_COL).groups.items():
            ordered = result.loc[indices].sort_values(DATE_COL)
            rolling = (
                ordered.set_index(DATE_COL)["era5_temp_c"]
                .rolling("7D", min_periods=1)
                .mean()
            )
            result.loc[ordered.index, "temp_7d"] = rolling.to_numpy()

    # Скорость изменения считаем между настоящими спутниковыми наблюдениями.
    # Иначе ML-реконструкция сама могла бы создать аргумент в пользу причины.
    result["ndvi_change_per_day"] = np.nan
    result["previous_observation_source"] = None
    for _, indices in result.groupby(ID_COL).groups.items():
        ordered = result.loc[indices].sort_values(DATE_COL)
        if "value_kind" in ordered:
            measured = ordered[
                ordered["value_kind"].eq("measured") & ordered[TARGET_COL].notna()
            ]
        else:
            measured = ordered[ordered[TARGET_COL].notna()]
        elapsed = measured[DATE_COL].diff().dt.days.replace(0, np.nan)
        result.loc[measured.index, "ndvi_change_per_day"] = (
            measured[TARGET_COL].diff() / elapsed
        )
        if "observation_source" in measured:
            result.loc[measured.index, "previous_observation_source"] = (
                measured["observation_source"].shift(1).to_numpy()
            )
    result["_month"] = result[DATE_COL].dt.month
    return result


def _harvest_window(crop_type: str, day_of_year: int) -> bool:
    crop = str(crop_type).strip().lower()
    if "подсолнеч" in crop:
        return 220 <= day_of_year <= 305
    if "пшениц" in crop or "зернов" in crop:
        return 165 <= day_of_year <= 250
    return 180 <= day_of_year <= 285


def _evidence_text(row: pd.Series) -> str:
    evidence = []
    if pd.notna(row.get("precip_14d")):
        evidence.append(f"осадки за 14 дней {float(row['precip_14d']):.1f} мм")
    if pd.notna(row.get("temp_7d")):
        evidence.append(f"температура за 7 дней {float(row['temp_7d']):.1f} °C")
    if pd.notna(row.get("sensor_spread")):
        evidence.append(f"разброс сенсоров {float(row['sensor_spread']):.3f}")
    if pd.notna(row.get("ndvi_change_per_day")):
        evidence.append(
            f"изменение NDVI {float(row['ndvi_change_per_day']):+.3f}/день"
        )
    return "; ".join(evidence)


def add_interpretation(df: pd.DataFrame) -> pd.DataFrame:
    """Добавляет осторожную и проверяемую гипотезу о причине аномалии.

    Причина не является диагнозом. Мы используем абсолютные физически
    интерпретируемые пороги, а не квантили одного анализируемого сезона: иначе
    самый тёплый октябрьский день ошибочно назывался бы тепловым стрессом.
    """
    result = add_weather_context(df)
    reasons: list[str | None] = []
    cause_codes: list[str | None] = []
    cause_confidences: list[float | None] = []
    evidence_texts: list[str | None] = []
    review_flags: list[bool] = []

    for idx, row in result.iterrows():
        if row.get("anomaly_status") in (None, NORMAL) or pd.isna(
            row.get("anomaly_status")
        ):
            reasons.append(None)
            cause_codes.append(None)
            cause_confidences.append(None)
            evidence_texts.append(None)
            review_flags.append(False)
            continue

        day_of_year = int(row[DATE_COL].dayofyear)
        slope = row.get("ndvi_change_per_day", np.nan)
        harvest = (
            pd.notna(slope)
            and float(slope) <= HARVEST_DROP_PER_DAY
            and _harvest_window(row.get("crop_type", "unknown"), day_of_year)
        )
        dry = (
            pd.notna(row.get("precip_14d"))
            and float(row["precip_14d"]) <= DRY_14D_MM
        )
        hot = pd.notna(row.get("temp_7d")) and float(row["temp_7d"]) >= HOT_7D_C
        cold = pd.notna(row.get("temp_7d")) and float(row["temp_7d"]) <= COLD_7D_C
        sensor_conflict = (
            pd.notna(row.get("sensor_spread"))
            and float(row["sensor_spread"]) >= SENSOR_SPREAD_WARNING
        )

        if sensor_conflict:
            code = CAUSE_SENSOR_CONFLICT
            confidence = 0.35
            reason = (
                "Сенсоры заметно расходятся: сначала нужна проверка снимка "
                "на облака, тени и разницу пространственного разрешения"
            )
        elif harvest and (dry or hot):
            code = CAUSE_MIXED
            confidence = 0.55
            reason = (
                "Снижение совпало с окном уборки и неблагоприятной погодой: "
                "нужно отличить агротехническое событие от стресса"
            )
        elif dry and hot:
            code = CAUSE_HEAT_DROUGHT
            confidence = 0.75
            reason = "Вероятный тепловой стресс и засуха: мало осадков при высокой температуре"
        elif dry:
            code = CAUSE_DROUGHT
            confidence = 0.65
            reason = "Вероятный дефицит влаги: осадки ниже сезонной нормы"
        elif hot:
            code = CAUSE_HEAT
            confidence = 0.60
            reason = "Вероятный тепловой стресс: средняя температура за 7 дней очень высокая"
        elif cold:
            code = CAUSE_COLD
            confidence = 0.60
            reason = "Вероятный холодовой стресс: низкая средняя температура за 7 дней"
        elif harvest:
            code = CAUSE_HARVEST
            confidence = 0.65
            reason = "Резкое сезонное снижение: возможна уборка урожая, требуется проверка"
        elif row.get("n_reference_years", 0) < 3:
            code = CAUSE_UNKNOWN
            confidence = 0.20
            reason = "Низкая надёжность климатологии: недостаточно исторических лет"
        else:
            code = CAUSE_UNKNOWN
            confidence = 0.30
            reason = "Погодная причина не подтверждена: возможны болезни, вредители или агротехника"

        reasons.append(reason)
        cause_codes.append(code)
        cause_confidences.append(confidence)
        evidence_texts.append(_evidence_text(row) or None)
        review_flags.append(
            code in {CAUSE_SENSOR_CONFLICT, CAUSE_MIXED, CAUSE_HARVEST, CAUSE_UNKNOWN}
        )

    result["anomaly_reason"] = reasons
    result["anomaly_cause"] = cause_codes
    result["cause_confidence"] = cause_confidences
    result["cause_evidence"] = evidence_texts
    result["requires_review"] = review_flags
    return result.drop(columns=["_month"])


def detect_anomaly_periods(
    df: pd.DataFrame,
    max_gap_days: int = 20,
    min_observations: int = 2,
) -> pd.DataFrame:
    """Объединяет отдельные аномальные точки в устойчивые периоды."""
    data = df.copy()
    if "anomaly_status" not in data:
        data = add_anomaly_status(data)
    if "anomaly_reason" not in data:
        data = add_interpretation(data)
    # Обратная совместимость с уже подготовленными таблицами, где была только
    # текстовая причина без структурированных полей новой версии.
    if "anomaly_cause" not in data:
        data["anomaly_cause"] = np.where(
            data["anomaly_reason"].notna(), "legacy_reason", None
        )
    if "cause_confidence" not in data:
        data["cause_confidence"] = data.get("anomaly_confidence", 0.0)
    if "requires_review" not in data:
        data["requires_review"] = False
    data[DATE_COL] = pd.to_datetime(data[DATE_COL])
    data = data[data["anomaly_status"].isin([MODERATE, CRITICAL])]
    if "value_kind" in data:
        # Reconstructed points may connect the visual curve, but an alert must
        # be anchored in real satellite evidence.
        data = data[data["value_kind"].eq("measured")]

    periods: list[dict] = []
    for polygon_id, group in data.groupby(ID_COL):
        group = group.sort_values(DATE_COL).copy()
        if group.empty:
            continue
        group["_period"] = (
            group[DATE_COL].diff().dt.days.fillna(max_gap_days + 1) > max_gap_days
        ).cumsum()
        for _, period in group.groupby("_period"):
            is_critical = (period["anomaly_status"] == CRITICAL).any()
            if len(period) < min_observations and not is_critical:
                continue
            # Выбираем причину всем периодом, а не случайным порядком строк при
            # равенстве mode(). Голос каждой точки взвешен уверенностью причины.
            cause_rows = period.dropna(subset=["anomaly_cause"])
            selected_cause = None
            selected_reason = None
            selected_cause_confidence = None
            if not cause_rows.empty:
                scores = cause_rows.groupby("anomaly_cause")["cause_confidence"].sum()
                selected_cause = str(scores.idxmax())
                candidates = cause_rows[cause_rows["anomaly_cause"].eq(selected_cause)]
                selected = candidates.sort_values(
                    ["cause_confidence", "z_score"], ascending=[False, True]
                ).iloc[0]
                selected_reason = selected["anomaly_reason"]
                selected_cause_confidence = round(
                    float(candidates["cause_confidence"].mean()), 2
                )
            periods.append(
                {
                    ID_COL: polygon_id,
                    "date_from": period[DATE_COL].min().strftime("%Y-%m-%d"),
                    "date_to": period[DATE_COL].max().strftime("%Y-%m-%d"),
                    "severity": CRITICAL if is_critical else MODERATE,
                    "min_z_score": round(float(period["z_score"].min()), 3),
                    "observations": int(len(period)),
                    "confidence": round(
                        float(period["anomaly_confidence"].dropna().mean()), 2
                    ),
                    "cause": selected_cause,
                    "cause_confidence": selected_cause_confidence,
                    "requires_review": bool(period["requires_review"].any()),
                    "reason": selected_reason,
                }
            )
    return pd.DataFrame(periods)


def validate_against_reference(train: pd.DataFrame) -> dict[str, float]:
    checked = add_anomaly_status(train)
    labeled = train["status"].notna() if "status" in train else pd.Series(False, index=train.index)
    result: dict[str, float] = {}
    if "ndvi_zscore" in train:
        result["max_zscore_difference"] = float(
            (checked["z_score"] - train["ndvi_zscore"]).abs().max()
        )
    if labeled.any():
        result["status_accuracy_on_labeled"] = float(
            (checked.loc[labeled, "anomaly_status"] == train.loc[labeled, "status"]).mean()
        )
    return result
