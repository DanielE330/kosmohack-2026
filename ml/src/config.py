"""Единая конфигурация воспроизводимого ML-пайплайна."""
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
MODELS_DIR = ROOT_DIR / "models"
REPORTS_DIR = ROOT_DIR / "reports"

TRAIN_PATH = DATA_DIR / "train_dataset.csv"
TEST_PATH = DATA_DIR / "private_features.csv"
SUBMISSION_PATH = ROOT_DIR / "submission.csv"
MODEL_PATH = MODELS_DIR / "gap_model.joblib"
METRICS_PATH = REPORTS_DIR / "validation_metrics.json"
OOF_PATH = REPORTS_DIR / "oof_predictions.csv"

ID_COL = "anon_polygon_id"
DATE_COL = "date"
TARGET_COL = "primary_ndvi"
GAP_FLAG_COL = "is_synthetic_gap"

SENSOR_NDVI_COLS = ["s2_ndvi", "landsat_ndvi", "modis_ndvi"]
SENSOR_EVI_COLS = ["s2_evi", "landsat_evi", "modis_evi"]
WEATHER_COLS = ["era5_temp_c", "era5_precip_mm"]
CATEGORICAL_COLS = ["crop_type"]

TRAIN_ONLY_LEAK_COLS = ["ndvi_zscore", "status"]
GAPSCORE_RMSE_THRESHOLD = 0.10

Z_THRESHOLD_MODERATE = -1.0
Z_THRESHOLD_CRITICAL = -2.0
LOW_PRECIP_PERCENTILE = 0.25
HIGH_TEMP_PERCENTILE = 0.75

# Интерпретация причины аномалии. ERA5-Land возвращает среднюю суточную
# температуру, поэтому 27 °C в среднем за неделю — уже сильная жара, а не
# просто тёплый день. Порог осадков относится к накоплению за 14 суток.
DRY_14D_MM = 5.0
HOT_7D_C = 27.0
COLD_7D_C = 2.0
SENSOR_SPREAD_WARNING = 0.15
HARVEST_DROP_PER_DAY = -0.01

# Протокол synthetic-gap валидации. В private скрыто около 15% исходно
# известных наблюдений; несколько seeds уменьшают зависимость от одной маски.
SYNTHETIC_MASK_RATE = 0.15
SYNTHETIC_SEEDS = (13, 42, 87)
RANDOM_SEED = 42
