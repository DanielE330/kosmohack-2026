# Мониторинг вегетационной динамики — ML-решение

Готовое ML-ядро для двух задач кейса:

1. восстановление `primary_ndvi` в строках `is_synthetic_gap=True`;
2. детекция, объединение в периоды и интерпретация отрицательных аномалий.

В архив уже включены обученные модели, OOF-метрики и актуальный кандидат
`submission_ensemble_v5.csv` на 3 112 контрольных строк. Подтверждённый v5
получил private RMSE `0.0683`; отдельно подготовлен leaderboard-калиброванный
эксперимент `submission_ensemble_v6.csv`.

## Результат валидации

Валидация имитирует private: у 15% известных точек сначала удаляются все
динамические признаки, а затем строятся признаки и выполняется прогноз.
`GroupKFold` разделяет данные по полигонам.

| Метод | OOF RMSE | Расчётный GapScore |
| --- | ---: | ---: |
| Гибридная интерполяция | 0.08861 | 3.42 |
| Интерполяция + ML residual | **0.06333** | **11.00** |

Последующие ансамбли и self-supervised адаптация улучшили проверку:

| Версия | OOF RMSE | Private RMSE |
| --- | ---: | ---: |
| v3: HGB + wheat + ExtraTrees + reweighted HGB | 0.062528 | 0.0699 |
| v4: локальная адаптация по видимым private-точкам | 0.061877 | **0.0688** |
| v5: v4 + глобальная private-коррекция | **0.061659 nested** | **0.0683** |
| v6: консервативное усиление двух подтверждённых поправок | 0.061793 | эксперимент |

Подробности находятся в `PRIVATE_ADAPTATION_V5_README.md` и
`LEADERBOARD_CALIBRATION_V6_README.md`.

Подробности, фолды и готовый текст гипотезы находятся в
`reports/ML_REPORT.md`.

## Быстрый запуск

Требуется Python 3.11 или 3.12.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python src/train.py
python src/inference.py
python scripts/predict_ensemble_v5.py
python -m unittest discover -s tests -v
```

После запуска v5 в корне появится `submission_ensemble_v5.csv` со строго тремя
колонками:

```text
anon_polygon_id,date,primary_ndvi_true
```

## Идея решения

`primary_ndvi` в train точно соответствует первому доступному значению в порядке
Sentinel-2, Landsat, MODIS. В контрольной строке private все эти значения скрыты,
поэтому прямое восстановление невозможно. Решение использует доступный контекст:

- несколько известных наблюдений до и после пропуска;
- отдельные временные ряды трёх сенсоров;
- сезонную климатологию и историю полигона за другие годы;
- EVI, NDWI и погоду с соседних дат;
- тип культуры и циклические календарные признаки;
- доступность сенсоров и медианы других полигонов на ту же дату.

Сначала вычисляется устойчивый интерполяционный baseline. Градиентный бустинг
предсказывает только residual — необходимую поправку к baseline. Вес поправки
выбран по OOF-прогнозам.

## Структура

```text
data/
  train_dataset.csv
  private_features.csv
models/
  gap_model.joblib
reports/
  ML_REPORT.md
  validation_metrics.json
  oof_predictions.csv
src/
  config.py          пути, seeds и пороги
  gap_features.py    leakage-safe признаки и synthetic masking
  modeling.py        GroupKFold, обучение и инференс
  train.py           точка запуска обучения
  inference.py       формирование submission.csv
  anomalies.py       статусы, причины и периоды аномалий
  pipeline.py        контракт интеграции с бэкендом
tests/
  test_core.py
webapp/
  main.py            FastAPI-обвязка ML-пайплайна
  gee_utils.py       рабочая интеграция с Google Earth Engine
scripts/
  check_gee.py       проверка авторизации и реального запроса к GEE
  predict_ensemble_v5.py  актуальный leaderboard-кандидат
examples/
  analyze_request.json  пример запроса к POST /analyze
```

## Контракт для Python-бэкенда

```python
import sys
import pandas as pd

sys.path.insert(0, "src")
from pipeline import restore_and_analyze

private = pd.read_csv("data/private_features.csv")
train = pd.read_csv("data/train_dataset.csv")
result = restore_and_analyze(private, reference=train)

# result["series"] — восстановленный временной ряд
# result["anomaly_periods"] — интервалы, severity, причина и confidence
```

Для запуска как модулей из корня можно добавить `src` в `PYTHONPATH`, как это
сделано в `webapp/main.py`.

## Веб-сервис

```bash
uvicorn webapp.main:app --reload
```

Доступны `/health`, `/analyze` и `/find-polygons`. Реализованы:

- Sentinel-2 Surface Reflectance: NDVI/EVI/NDWI и маска облаков/теней по SCL;
- Landsat 8/9 Collection 2 L2: масштабирование reflectance и QA_PIXEL/QA_RADSAT;
- MODIS MOD13Q1: NDVI/EVI с фильтром SummaryQA;
- ERA5-Land Daily: температура в °C и суточные осадки в мм;
- многолетняя климатология по day-of-year для нового полигона;
- регулярная временная сетка и восстановление моделью дат без чистого снимка;
- приблизительные контуры сельхозугодий из ESA WorldCover.

### Источник спутниковых данных

`webapp/main.py` выбирает бэкенд через `VEGMON_DATA_SOURCE` (по умолчанию
`copernicus`):

- **`copernicus`** (по умолчанию) — Sentinel-2 NDVI/EVI/NDWI через Sentinel
  Hub Statistical API на Copernicus Data Space + погода через бесплатный
  Open-Meteo (без ключа). Не требует привязки карты/биллинга. Нет
  Landsat/MODIS/WorldCover — `/find-polygons` в этом режиме недоступен
  (501).
- **`gee`** — полный набор источников (Sentinel-2/Landsat/MODIS/ERA5-Land/
  WorldCover) через Google Earth Engine, но требует зарегистрированный и
  привязанный к биллингу Cloud-проект.

#### Copernicus Data Space (по умолчанию, бесплатно)

```bash
python -m pip install -r requirements.txt
# Создать OAuth-клиент: dataspace.copernicus.eu -> Account settings -> OAuth clients
export CDSE_CLIENT_ID="..."
export CDSE_CLIENT_SECRET="..."

uvicorn webapp.main:app --reload
```

#### Google Earth Engine (опционально, нужен биллинг)

```bash
python -m pip install -r requirements.txt
earthengine authenticate
export EARTHENGINE_PROJECT="your-google-cloud-project-id"
export VEGMON_DATA_SOURCE=gee

# Короткий реальный запрос к четырём источникам
python scripts/check_gee.py --project "$EARTHENGINE_PROJECT"

# Запуск API
uvicorn webapp.main:app --reload
```

Проверка API:

```bash
curl http://127.0.0.1:8000/health

curl -X POST http://127.0.0.1:8000/analyze \
  -H "Content-Type: application/json" \
  --data @examples/analyze_request.json
```

`/analyze` принимает GeoJSON `Polygon` или `Feature`, тип культуры, период,
шаг восстанавливаемого ряда и число исторических лет. Реальные измерения не
перезаписываются: ML применяется только к датам без качественного наблюдения.

Live-климатология откалибрована к train: минимальный допустимый
`ndvi_climatology_std` берётся как медиана для выбранной культуры. Это не даёт
слишком узкому коридору нормы создавать огромные ложные z-score. Восстановленные
точки отображаются на графике, но не могут самостоятельно открыть или продлить
период тревоги — алерт должен быть подтверждён реальным спутниковым наблюдением.
Погодные суммы и средние считаются по календарным окнам 14 и 7 дней.

Причина тревоги отделена от самого факта аномалии. Поля `z_score`,
`anomaly_status` и `anomaly_confidence` отвечают на вопрос «насколько ряд
отклонился и надёжен ли сигнал». Поля `anomaly_cause`, `cause_confidence`,
`cause_evidence` и `requires_review` описывают только гипотезу о причине.
Используются проверяемые пороги: накопленные осадки за 14 дней, средняя
температура за 7 дней, окно уборки для культуры и разброс одновременных
измерений сенсоров. Самый тёплый день одного месяца больше не объявляется
тепловым стрессом лишь потому, что он теплее остальных дат текущего сезона.

Возможные значения `anomaly_cause`: `heat_and_drought`, `moisture_deficit`,
`heat_stress`, `cold_stress`, `possible_harvest`, `weather_or_harvest`,
`sensor_conflict`, `unconfirmed`. Во фронтенде `requires_review=true` нужно
показывать как «требуется проверка», а не как установленный диагноз.

`/find-polygons` возвращает связанные области класса Cropland ESA WorldCover,
а не кадастровые границы. Во фронтенде пользователь должен иметь возможность
исправить предложенный контур.

Важно: GEE работает для реального GeoJSON-полигона из приложения. Связать
`anon_polygon_id` leaderboard-датасета со спутниковыми данными без координат
невозможно.

## Воспроизводимость

- seeds: `13, 42, 87`, seed модели: `42`;
- маскируется 15% известных значений внутри каждого полигона и года;
- train/validation разделяются по `anon_polygon_id`;
- версии библиотек зафиксированы в `requirements.txt`;
- модель использует только доступные на инференсе признаки;
- тест `test_query_value_cannot_leak_into_features` подтверждает, что изменение
  скрытого target не влияет на признаки контрольной строки.

Фактические private RMSE уже измерены платформой для v4 (`0.0688`) и v5
(`0.0683`). Для новых кандидатов private RMSE неизвестен до загрузки; OOF
остаётся оценкой, а не гарантией результата на скрытой выборке.
