# ML — статус и распределение (2026-09-05)

Полный ML-пайплайн живёт в `../ml/` (актуальная версия в корне репозитория)
и его более ранний снапшот в `../backend/ml/` (то, что реально подключено
к веб-сервису прямо сейчас — см. `backend.md`, раздел про `ml_bridge.py`).
Подробное описание решения, метрик и структуры — `../ml/README.md`,
не дублируется здесь.

## ✅ Готово

- **Восстановление пропусков `primary_ndvi`** — обученная модель
  (градиентный бустинг поверх интерполяционного baseline), private RMSE
  улучшался по версиям вплоть до v9/v10 (см. `../ml/README.md`, таблица
  результатов). Подключена к веб-сервису через `backend/app/services/
  ml_bridge.py` — используется на реальных данных `data/train_dataset.csv`
  на живом бэкенде.
- **Детекция и интерпретация причин аномалий** (`../ml/src/anomalies.py`)
  — реальные категории причин (heat_and_drought/moisture_deficit/
  heat_stress/cold_stress/possible_harvest/weather_or_harvest/
  sensor_conflict/unconfirmed) с confidence и `requires_review`, вместо
  прежней грубой ERA5-эвристики (осадки+температура за весь период) —
  тоже подключено и проверено на живом бэкенде.
- **Batch-инференс для сдачи** (`../ml/src/inference.py`,
  `python -m src.inference` из `ml/`) — отдельная точка входа, не завязана
  на веб-сервис, как того требует ТЗ.
- **FastAPI-обвязка с интеграцией Google Earth Engine написана**
  (`../ml/webapp/main.py`, `../ml/webapp/gee_utils.py`) — эндпоинты
  `/analyze` (live-анализ произвольного GeoJSON-полигона: Sentinel-2/
  Landsat/MODIS/ERA5, климатология, восстановление пропусков и
  интерпретация причин для реальных координат) и `/find-polygons`
  (контуры сельхозугодий класса Cropland из ESA WorldCover). **Код готов,
  но не запущен и не подключён к основному бэкенду** — см. блокер ниже.
- Тесты: `../ml/tests/` (`test_core.py`, `test_gee_utils.py`,
  `test_private_adaptation.py`).
- Воспроизводимость зафиксирована: seeds (13/42/87), версии зависимостей
  в `../ml/requirements.txt`, leakage-safe признаки — подробности в
  `../ml/README.md`, раздел "Воспроизводимость".

## ✅ GEE подключён (2026-09-05)

Кто-то из команды достал рабочие credentials (не-РФ Google-аккаунт).
Подключено через `backend/app/services/gee_bridge.py` (тот же паттерн
абсолютного пути, что `ml_bridge.py`) + `GET /polygons/{id}/
live-sources?date_from=&date_to=` в основном веб-сервисе — реальные
Sentinel-2/Landsat/MODIS NDVI и ERA5-погода за период. Проверено вручную
живым запросом с реальными кредами (реальные значения за май 2024).
`ml/webapp/main.py` (полноценные `/analyze`/`/find-polygons`) как
отдельный сервис пока не поднят — используется только сам `gee_utils.py`
напрямую из основного бэкенда, этого достаточно для критерия «несколько
источников данных». Credentials — секрет, не в репозитории; на проде
ещё не размещены (см. `backend.md`, открытые пункты).

Copernicus Data Space Ecosystem как альтернатива больше не актуален —
GEE уже работает.

## ⚠️ Технический долг

- **Две версии `ml/`** в репозитории: `../ml/` (актуальная, до v10) и
  `../backend/ml/` (снапшот, к которому реально подключён
  `ml_bridge.py`, версия примерно на уровне v5 — база модели
  `gap_model.joblib` идентична по содержимому, различия только в
  экспериментальных ensemble/калибровочных версиях для лидерборда).
  Если понадобится обновить подключённую к бэкенду модель на более свежую
  калибровку — свериться, какая версия реально нужна веб-сервису
  (учитывая, что улучшения v6-v10 — это в основном калибровка под
  приватный лидерборд соревнования, а не изменения базовой модели
  восстановления пропусков, которая идентична).
- **`backend/inference/run_inference.py`** (написан бэкенд-командой до
  мержа ML) не использует реальную модель — см. `backend.md`.

## Как проверить локально

```bash
cd ml
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python src/train.py
python src/inference.py
python -m unittest discover -s tests -v
```

Веб-обвязка с GEE (нужен `EARTHENGINE_PROJECT` в `.env`, см. `.env.example`):

```bash
cd ml
python scripts/check_gee.py --project "$EARTHENGINE_PROJECT"
uvicorn webapp.main:app --reload
```
