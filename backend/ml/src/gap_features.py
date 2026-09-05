"""Признаки для восстановления искусственно скрытых значений primary_ndvi.

Главное правило модуля: признаки контрольной строки никогда не используются.
Все значения берутся только из видимых наблюдений до/после пропуска, из истории
полигона или из других полигонов на ту же дату.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
import warnings

import numpy as np
import pandas as pd

from config import DATE_COL, ID_COL, TARGET_COL


warnings.filterwarnings("ignore", category=pd.errors.PerformanceWarning)


SENSOR_COLS = [
    "s2_ndvi",
    "landsat_ndvi",
    "modis_ndvi",
    "s2_evi",
    "landsat_evi",
    "modis_evi",
    "s2_ndwi",
    "landsat_ndwi",
]

# В private_features все эти значения скрыты в контрольной строке.
DYNAMIC_COLS = [
    *SENSOR_COLS,
    "era5_temp_c",
    "era5_precip_mm",
    "year",
    TARGET_COL,
    "doy",
    "ndvi_climatology_mean",
    "ndvi_climatology_std",
    "n_reference_years",
    "ndvi_zscore",
    "status",
]


# Справочные агрономические значения по культурам — приближённые, взяты из
# общей агрономической литературы (FAO crop coefficient tables и типичные
# диапазоны для южной степной зоны), НЕ вычислены из train_dataset.csv —
# иначе это была бы утечка целевой переменной в признаки. Именно поэтому
# они константы "среднего справочника", а не подогнанные под наш датасет
# числа: цель — дать модели физический prior, а не переоткрыть его из
# тех же 39 полигонов, на которых и так мало данных для надёжного вывода
# сложных взаимодействий "культура × температура/влага".
#   optimal_temp_c   — примерная оптимальная средняя суточная t° в период
#                       активной вегетации;
#   water_need_mm_day — примерная суточная потребность во влаге в пике
#                       вегетации (испарение + транспирация), мм/сутки;
#   root_depth_m      — эффективная глубина корневой системы, м (глубже
#                       корни — лучше буфер против краткосрочного дефицита
#                       осадков, поэтому используется как делитель ниже).
CROP_AGRONOMY = {
    "озимая пшеница": {"optimal_temp_c": 18.0, "water_need_mm_day": 4.5, "root_depth_m": 1.2},
    "подсолнечник": {"optimal_temp_c": 24.0, "water_need_mm_day": 5.5, "root_depth_m": 2.0},
    "зерновые": {"optimal_temp_c": 18.0, "water_need_mm_day": 4.2, "root_depth_m": 1.1},
    "пастбища/зерновые": {"optimal_temp_c": 20.0, "water_need_mm_day": 3.5, "root_depth_m": 0.4},
}
_DEFAULT_AGRONOMY = {"optimal_temp_c": 19.0, "water_need_mm_day": 4.3, "root_depth_m": 1.0}


def _add_crop_agronomy_features(features: pd.DataFrame, crop: pd.Series) -> None:
    """Признаки-отклонения от агрономических норм культуры — не сырые
    константы (те были бы почти дублем `crop_*` dummy), а взаимодействие
    константы культуры с уже интерполированной по соседям погодой
    (`era5_temp_c_linear`/`era5_precip_mm_linear` — сырые значения в
    query-строках скрыты, как и целевая переменная, поэтому используем
    те же leakage-safe признаки, что уже посчитаны выше). [crop] — та же
    заполненная ("unknown" вместо NaN) серия, что идёт на `crop_*` dummy."""
    row_ids = crop.index

    optimal_temp = crop.map(lambda c: CROP_AGRONOMY.get(c, _DEFAULT_AGRONOMY)["optimal_temp_c"])
    water_need = crop.map(lambda c: CROP_AGRONOMY.get(c, _DEFAULT_AGRONOMY)["water_need_mm_day"])
    root_depth = crop.map(lambda c: CROP_AGRONOMY.get(c, _DEFAULT_AGRONOMY)["root_depth_m"])

    temp_proxy = features.loc[row_ids, "era5_temp_c_linear"] if "era5_temp_c_linear" in features else np.nan
    precip_proxy = (
        features.loc[row_ids, "era5_precip_mm_linear"] if "era5_precip_mm_linear" in features else np.nan
    )

    temp_deviation = temp_proxy - optimal_temp
    water_deficit = water_need - precip_proxy

    features.loc[row_ids, "crop_optimal_temp_c"] = optimal_temp
    features.loc[row_ids, "crop_water_need_mm_day"] = water_need
    features.loc[row_ids, "crop_root_depth_m"] = root_depth
    features.loc[row_ids, "crop_temp_deviation"] = temp_deviation
    features.loc[row_ids, "crop_heat_stress"] = temp_deviation.clip(lower=0)
    features.loc[row_ids, "crop_cold_stress"] = (-temp_deviation).clip(lower=0)
    features.loc[row_ids, "crop_water_deficit"] = water_deficit
    # Глубже корни — меньше эффект краткосрочного дефицита осадков.
    features.loc[row_ids, "crop_water_deficit_root_adjusted"] = water_deficit / root_depth


@dataclass
class GapFeatureResult:
    """Матрица признаков и метаданные строк, для которых строился прогноз."""

    features: pd.DataFrame
    meta: pd.DataFrame


def make_synthetic_mask(
    df: pd.DataFrame,
    rate: float = 0.15,
    seed: int = 42,
) -> pd.Series:
    """Маскирует долю известных target внутри каждого полигона и года.

    В private_features скрыто примерно 15% исходно известных наблюдений. Такое
    маскирование значительно ближе к протоколу соревнования, чем случайный split
    строк уже построенной таблицы признаков.
    """
    work = df.copy()
    dates = pd.to_datetime(work[DATE_COL])
    years = dates.dt.year
    candidates = work[TARGET_COL].notna()
    rng = np.random.default_rng(seed)
    mask = pd.Series(False, index=work.index)

    groups = work.loc[candidates].groupby([ID_COL, years[candidates]]).groups
    for indices in groups.values():
        indices = np.asarray(list(indices))
        if len(indices) < 4:
            continue
        n_hidden = max(1, int(round(len(indices) * rate)))
        n_hidden = min(n_hidden, len(indices) - 2)
        chosen = rng.choice(indices, size=n_hidden, replace=False)
        mask.loc[chosen] = True
    return mask


def _as_day_number(values: pd.Series | np.ndarray) -> np.ndarray:
    return np.asarray(values, dtype="datetime64[D]").astype("int64").astype(float)


def _take_neighbor(
    positions: np.ndarray,
    known_times: np.ndarray,
    known_values: np.ndarray,
    query_times: np.ndarray,
    offset: int,
    side: str,
) -> tuple[np.ndarray, np.ndarray]:
    if side == "prev":
        indices = positions - offset
        valid = indices >= 0
    else:
        indices = positions + offset - 1
        valid = indices < len(known_times)

    values = np.full(len(query_times), np.nan)
    distances = np.full(len(query_times), np.nan)
    if valid.any():
        safe = indices[valid]
        values[valid] = known_values[safe]
        if side == "prev":
            distances[valid] = query_times[valid] - known_times[safe]
        else:
            distances[valid] = known_times[safe] - query_times[valid]
    return values, distances


def _add_neighbor_features(
    features: pd.DataFrame,
    work: pd.DataFrame,
    value_col: str,
    prefix: str,
    depth: int,
) -> None:
    """Добавляет значения/расстояния до соседних известных наблюдений."""
    if value_col not in work.columns:
        return

    for _, group in work.groupby(ID_COL, sort=False):
        query = group["_is_query"].to_numpy()
        if not query.any():
            continue

        known = group[value_col].notna().to_numpy() & ~query
        query_rows = group.loc[query]
        query_ids = query_rows["_row_id"].to_numpy()
        query_times = _as_day_number(query_rows[DATE_COL])

        known_rows = group.loc[known]
        if known_rows.empty:
            continue
        known_times = _as_day_number(known_rows[DATE_COL])
        known_values = known_rows[value_col].astype(float).to_numpy()
        positions = np.searchsorted(known_times, query_times)

        stored: dict[str, np.ndarray] = {}
        for k in range(1, depth + 1):
            for side in ("prev", "next"):
                vals, dist = _take_neighbor(
                    positions, known_times, known_values, query_times, k, side
                )
                stored[f"{prefix}_{side}{k}"] = vals
                stored[f"{prefix}_days_{side}{k}"] = dist
                features.loc[query_ids, f"{prefix}_{side}{k}"] = vals
                features.loc[query_ids, f"{prefix}_days_{side}{k}"] = dist

        prev = stored[f"{prefix}_prev1"]
        nxt = stored[f"{prefix}_next1"]
        dprev = stored[f"{prefix}_days_prev1"]
        dnext = stored[f"{prefix}_days_next1"]
        both = np.isfinite(prev) & np.isfinite(nxt)
        only_prev = np.isfinite(prev) & ~np.isfinite(nxt)
        only_next = ~np.isfinite(prev) & np.isfinite(nxt)

        linear = np.full(len(query_ids), np.nan)
        mean = np.full(len(query_ids), np.nan)
        nearest = np.full(len(query_ids), np.nan)
        linear[both] = (
            prev[both] * dnext[both] + nxt[both] * dprev[both]
        ) / (dprev[both] + dnext[both])
        mean[both] = (prev[both] + nxt[both]) / 2
        nearest[both] = np.where(dprev[both] <= dnext[both], prev[both], nxt[both])
        linear[only_prev] = mean[only_prev] = nearest[only_prev] = prev[only_prev]
        linear[only_next] = mean[only_next] = nearest[only_next] = nxt[only_next]

        features.loc[query_ids, f"{prefix}_linear"] = linear
        features.loc[query_ids, f"{prefix}_mean"] = mean
        features.loc[query_ids, f"{prefix}_nearest"] = nearest
        features.loc[query_ids, f"{prefix}_span_days"] = dprev + dnext
        features.loc[query_ids, f"{prefix}_neighbor_delta"] = nxt - prev

        if depth >= 2:
            prev2 = stored[f"{prefix}_prev2"]
            next2 = stored[f"{prefix}_next2"]
            dprev2 = stored[f"{prefix}_days_prev2"]
            dnext2 = stored[f"{prefix}_days_next2"]
            features.loc[query_ids, f"{prefix}_slope_before"] = (
                prev - prev2
            ) / (dprev2 - dprev)
            features.loc[query_ids, f"{prefix}_slope_after"] = (
                next2 - nxt
            ) / (dnext2 - dnext)


def _add_historical_features(features: pd.DataFrame, work: pd.DataFrame) -> None:
    """Статистика того же периода сезона в другие годы данного полигона."""
    for _, group in work.groupby(ID_COL, sort=False):
        query_rows = group[group["_is_query"]]
        visible = group[group[TARGET_COL].notna() & ~group["_is_query"]]
        if query_rows.empty or visible.empty:
            continue

        vis_doy = visible["_doy"].to_numpy()
        vis_year = visible["_year"].to_numpy()
        vis_target = visible[TARGET_COL].to_numpy(dtype=float)
        if "ndvi_climatology_mean" in visible:
            vis_residual = (
                visible[TARGET_COL] - visible["ndvi_climatology_mean"]
            ).to_numpy(dtype=float)
        else:
            vis_residual = np.full(len(visible), np.nan)

        for row_id, query_doy, query_year in query_rows[
            ["_row_id", "_doy", "_year"]
        ].itertuples(index=False, name=None):
            delta = np.abs(vis_doy - query_doy)
            delta = np.minimum(delta, 365 - delta)
            same_season = (delta <= 10) & (vis_year != query_year)
            vals = vis_target[same_season]
            vals = vals[np.isfinite(vals)]
            if len(vals):
                features.loc[row_id, "hist_doy_median"] = np.median(vals)
                features.loc[row_id, "hist_doy_mean"] = np.mean(vals)
                features.loc[row_id, "hist_doy_std"] = np.std(vals)
                features.loc[row_id, "hist_doy_count"] = len(vals)

            residuals = vis_residual[same_season]
            residuals = residuals[np.isfinite(residuals)]
            if len(residuals):
                features.loc[row_id, "hist_residual_mean"] = np.mean(residuals)


def _add_date_context(features: pd.DataFrame, work: pd.DataFrame) -> None:
    """Добавляет агрегаты видимых полигонов на ту же календарную дату."""
    query_rows = work[work["_is_query"]]
    visible = work[~work["_is_query"]]
    query_dates = query_rows.set_index("_row_id")[DATE_COL]

    target_stats = visible.groupby(DATE_COL)[TARGET_COL].agg(["median", "mean", "count"])
    for stat in target_stats.columns:
        features.loc[query_dates.index, f"date_target_{stat}"] = query_dates.map(
            target_stats[stat]
        )

    crop_stats = (
        visible.dropna(subset=[TARGET_COL])
        .groupby([DATE_COL, "crop_type"])[TARGET_COL]
        .median()
    )
    crop_lookup = crop_stats.to_dict()
    features.loc[query_dates.index, "date_crop_target_median"] = [
        crop_lookup.get((date, crop_type), np.nan)
        for _, date, crop_type in query_rows[
            ["_row_id", DATE_COL, "crop_type"]
        ].itertuples(index=False, name=None)
    ]

    for sensor in ("s2_ndvi", "landsat_ndvi", "modis_ndvi"):
        if sensor not in visible:
            continue
        availability = visible.assign(_available=visible[sensor].notna()).groupby(DATE_COL)[
            "_available"
        ].mean()
        medians = visible.groupby(DATE_COL)[sensor].median()
        features.loc[query_dates.index, f"date_{sensor}_availability"] = query_dates.map(
            availability
        )
        features.loc[query_dates.index, f"date_{sensor}_median"] = query_dates.map(medians)


def _neighbor_feature_names(prefix: str, depth: int) -> list[str]:
    names: list[str] = []
    for k in range(1, depth + 1):
        for side in ("prev", "next"):
            names.extend([f"{prefix}_{side}{k}", f"{prefix}_days_{side}{k}"])
    names.extend(
        [
            f"{prefix}_linear",
            f"{prefix}_mean",
            f"{prefix}_nearest",
            f"{prefix}_span_days",
            f"{prefix}_neighbor_delta",
        ]
    )
    if depth >= 2:
        names.extend([f"{prefix}_slope_before", f"{prefix}_slope_after"])
    return names


def build_gap_features(df: pd.DataFrame, query_mask: Iterable[bool]) -> GapFeatureResult:
    """Строит leakage-safe признаки для строк, отмеченных ``query_mask``."""
    work = df.copy().reset_index(drop=True)
    mask = np.asarray(list(query_mask), dtype=bool)
    if len(mask) != len(work):
        raise ValueError("query_mask должен иметь ту же длину, что и dataframe")
    if not mask.any():
        raise ValueError("В query_mask нет ни одной строки для прогноза")

    work[DATE_COL] = pd.to_datetime(work[DATE_COL])
    work["_row_id"] = np.arange(len(work))
    work["_is_query"] = mask
    work["_year"] = work[DATE_COL].dt.year.astype(float)
    work["_doy"] = work[DATE_COL].dt.dayofyear.astype(float)

    # Воспроизводим реальный private_features: текущая контрольная строка пуста.
    hidden_cols = [c for c in DYNAMIC_COLS if c in work.columns]
    work.loc[work["_is_query"], hidden_cols] = np.nan

    work = work.sort_values([ID_COL, DATE_COL, "_row_id"]).reset_index(drop=True)
    query_rows = work[work["_is_query"]]
    neighbor_specs = [
        (TARGET_COL, "target", 3),
        ("s2_ndvi", "s2_ndvi", 2),
        ("landsat_ndvi", "landsat_ndvi", 2),
        ("modis_ndvi", "modis_ndvi", 2),
        ("s2_evi", "s2_evi", 1),
        ("landsat_evi", "landsat_evi", 1),
        ("modis_evi", "modis_evi", 1),
        ("s2_ndwi", "s2_ndwi", 1),
        ("landsat_ndwi", "landsat_ndwi", 1),
        ("ndvi_climatology_mean", "ndvi_climatology_mean", 1),
        ("ndvi_climatology_std", "ndvi_climatology_std", 1),
        ("era5_temp_c", "era5_temp_c", 1),
        ("era5_precip_mm", "era5_precip_mm", 1),
        ("n_reference_years", "n_reference_years", 1),
        ("_target_minus_climatology", "target_clim_residual", 2),
    ]
    feature_names = ["year", "doy", "doy_sin", "doy_cos"]
    for _, prefix, depth in neighbor_specs:
        feature_names.extend(_neighbor_feature_names(prefix, depth))
    feature_names.extend(
        [
            "climatology_plus_residual",
            "hist_doy_median",
            "hist_doy_mean",
            "hist_doy_std",
            "hist_doy_count",
            "hist_residual_mean",
            "date_target_median",
            "date_target_mean",
            "date_target_count",
            "date_crop_target_median",
            "date_s2_ndvi_availability",
            "date_s2_ndvi_median",
            "date_landsat_ndvi_availability",
            "date_landsat_ndvi_median",
            "date_modis_ndvi_availability",
            "date_modis_ndvi_median",
        ]
    )
    features = pd.DataFrame(
        np.nan,
        index=query_rows["_row_id"].to_numpy(),
        columns=list(dict.fromkeys(feature_names)),
    )

    features["year"] = query_rows.set_index("_row_id")["_year"]
    features["doy"] = query_rows.set_index("_row_id")["_doy"]
    features["doy_sin"] = np.sin(2 * np.pi * features["doy"] / 365.25)
    features["doy_cos"] = np.cos(2 * np.pi * features["doy"] / 365.25)

    # Отклонение от климатологии интерполируется отдельно от сезонной кривой.
    if "ndvi_climatology_mean" in work:
        work["_target_minus_climatology"] = (
            work[TARGET_COL] - work["ndvi_climatology_mean"]
        )

    for value_col, prefix, depth in neighbor_specs:
        _add_neighbor_features(features, work, value_col, prefix, depth=depth)

    if "ndvi_climatology_mean" in work:
        clim = features.get("ndvi_climatology_mean_linear")
        residual = features.get("target_clim_residual_linear")
        if clim is not None and residual is not None:
            features["climatology_plus_residual"] = clim + residual

    _add_historical_features(features, work)
    _add_date_context(features, work)

    crop = query_rows.set_index("_row_id")["crop_type"].fillna("unknown").astype(str)
    crop_dummies = pd.get_dummies(crop, prefix="crop", dtype=float)
    features = features.join(crop_dummies)
    _add_crop_agronomy_features(features, crop)
    features = features.copy()  # дефрагментация после поэтапного добавления колонок

    meta = query_rows.set_index("_row_id")[[ID_COL, DATE_COL, "crop_type"]].copy()
    meta["baseline_mean"] = features["target_mean"]
    meta["baseline_linear"] = features["target_linear"]
    meta["baseline_climatology"] = features.get("ndvi_climatology_mean_linear")
    meta["baseline"] = (
        0.80 * meta["baseline_mean"]
        + 0.15 * meta["baseline_linear"]
        + 0.05 * meta["baseline_climatology"].fillna(meta["baseline_mean"])
    )
    meta["baseline"] = meta["baseline"].fillna(meta["baseline_linear"])
    meta["baseline"] = meta["baseline"].fillna(meta["baseline_climatology"])

    order = query_rows.sort_values("_row_id")["_row_id"]
    return GapFeatureResult(features=features.loc[order], meta=meta.loc[order])


def align_feature_columns(features: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Приводит inference-признаки к набору и порядку обучающих признаков."""
    aligned = features.copy()
    for col in columns:
        if col not in aligned:
            aligned[col] = 0.0 if col.startswith("crop_") else np.nan
    return aligned.reindex(columns=columns)
