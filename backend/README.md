# Backend

FastAPI + PostgreSQL (SQLAlchemy 2.0 async) сервис для мониторинга
вегетационной динамики. Контракт API согласован с Flutter-клиентом — см.
[`../tasks/backend.md`](../tasks/backend.md) для полной постановки задачи.

## Структура

```
backend/
├── app/
│   ├── main.py                  # FastAPI-приложение, роутеры, CORS
│   ├── config.py                # настройки (DSN, JWT, CORS) из env/.env
│   ├── database.py              # async engine/session, Base
│   ├── security.py              # хэши паролей, JWT
│   ├── models/                  # ORM: User, Polygon, NdviObservation, AnomalyPeriod
│   ├── schemas/                 # Pydantic-схемы запросов/ответов
│   ├── api/routes/               # auth, polygons, timeseries, anomalies
│   ├── services/
│   │   ├── gapfill.py            # восстановление primary_ndvi (baseline, заменяемый)
│   │   ├── anomaly_detection.py  # Z-score группировка + explanation (baseline, заменяемый)
│   │   └── region_search.py      # автопоиск контуров по region= (OSM Overpass/Nominatim)
│   └── ingestion/
│       └── load_train_dataset.py # разовая загрузка data/train_dataset.csv
├── inference/
│   └── run_inference.py         # CLI: private_features.csv -> submission.csv
├── alembic/                     # миграции схемы БД
├── tests/
├── requirements.txt
├── Dockerfile
└── docker-compose.yml           # backend + postgres
```

Веб-сервис и `inference/run_inference.py` — две независимые точки входа
(см. `tasks/backend.md`, п.5): batch-инференс не поднимает FastAPI и не
трогает БД, только читает/пишет CSV.

## Быстрый старт (Docker)

```bash
cd backend
cp .env.example .env
docker compose up --build -d
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.ingestion.load_train_dataset --csv /data/train_dataset.csv
```

API поднимется на `http://localhost:8000`, документация — на
`http://localhost:8000/docs` (Swagger) и `/redoc`.

## Локальный запуск без Docker

Нужен Python 3.11+ и локальный/удалённый PostgreSQL.

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env   # поправить DATABASE_URL при необходимости

alembic upgrade head
python -m app.ingestion.load_train_dataset   # грузит ../data/train_dataset.csv

uvicorn app.main:app --reload
```

## Тесты

Юнит-тесты (`test_gapfill.py`) не требуют БД и запускаются как есть.
Тесты эндпоинтов (`test_auth.py`, `test_polygons.py`) идут через ASGI
напрямую в FastAPI-приложение, но им нужен настоящий Postgres — они сами
создают отдельную БД `vegmon_test` на том же сервере, что и dev (`vegmon`),
и никогда не трогают уже загруженные в `vegmon` реальные данные
(`create_all`/`drop_all` только в `vegmon_test`).

```bash
docker compose up -d db          # только БД, порт backend не нужен
docker compose run --rm backend pytest
docker compose down
```

Локально без Docker — нужен доступный Postgres, `DATABASE_URL`/
`TEST_DATABASE_URL` в `.env`, дальше просто `pytest`.

Покрыто: восстановление пропусков (baseline), регистрация → подтверждение
почты → вход (включая отказ входа до подтверждения и повторное
использование токена), CRUD своих полигонов (создание требует токен,
изменять/удалять может только владелец, чужой — 403).

## Batch-инференс (отдельная точка входа для проверки на платформе)

```bash
python -m inference.run_inference --input private_features.csv --output submission.csv
```

Не требует поднятого веб-сервиса/БД. Использует ту же baseline-функцию
восстановления, что и веб-API (`app/services/gapfill.interpolate`) — при
подключении реальной ML-модели меняется только эта функция, а не сам скрипт
и не веб-сервис.

## Что здесь mock/baseline и куда встраивать реальную модель

- **`app/services/gapfill.interpolate`** — линейная интерполяция между
  ближайшими известными наблюдениями. Сигнатура `(dates, values) ->
  predicted` используется и веб-API, и `inference/run_inference.py` —
  замените реализацию на Savitzky-Golay/Whittaker/ML, вызывающий код не
  меняется.
- **`app/services/anomaly_detection.explain_anomaly`** — эвристика по
  ERA5 (осадки/температура) для текстового поля `explanation`. Пороги
  Z-score (`status_for_zscore`) зафиксированы в ТЗ и продублированы во
  Flutter — их менять нельзя без синхронизации фронта.
- **Координаты AOI датасета соревнования** (`AOI-0002`…) в
  `train_dataset.csv` отсутствуют — `app/ingestion/load_train_dataset.py`
  генерирует детерминированный синтетический контур
  (`_placeholder_points`) только для отображения на карте. Замените на
  реальную геометрию, когда она появится (см. `tasks/backend.md`, п.0).

## Пользователи и авторизация

В официальном ТЗ и в контракте, который уже реализует Flutter, авторизации
нет. Добавлена как учебное расширение — привязка нарисованных
пользователем полигонов (`is_custom=true`) к владельцу. Просмотр
`/polygons`, `/timeseries/*`, `/anomalies` не требует токена;
создавать/менять/удалять свои полигоны — да.

Регистрация требует подтверждения почты, прежде чем можно будет войти:

1. `POST /auth/register` — создаёт пользователя (`is_email_confirmed=false`)
   и возвращает `email_confirmation_token` **прямо в ответе**. Это временная
   замена реальной отправки письма — почтовый сервис ещё не подключён (см.
   `tasks/backend.md`). Когда подключим — токен перестанет отдаваться
   в ответе и будет только приходить на почту.
2. `POST /auth/confirm-email {"token": "..."}` — подтверждает почту и сразу
   возвращает JWT.
3. `POST /auth/login` — обычный вход; вернёт `403`, если почта ещё не
   подтверждена.

## Переменные окружения

См. [`.env.example`](.env.example): `DATABASE_URL`, `JWT_SECRET_KEY`,
`JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `CORS_ORIGINS`, `SQL_ECHO`.
