# SkyTime — мониторинг вегетационной динамики

Проект для хакатона «КОСМОХАКАТОН» 2026: сервис для мониторинга состояния растительности
сельскохозяйственных полигонов по спутниковым временным рядам NDVI —
восстановление пропусков и детекция аномалий (Z-score).

**Демо**: https://skytime.daniel.crazedns.ru

- Полное ТЗ — [`docs/tz.pdf`](docs/tz.pdf)
- Критерии оценки (100 баллов) — [`docs/criteria.pdf`](docs/criteria.pdf)
- **База знаний проекта** (сводка ТЗ, критериев, реальных данных,
  архитектуры и открытых вопросов) — [`docs/KNOWLEDGE_BASE.md`](docs/KNOWLEDGE_BASE.md)

## Структура репозитория

```
.
├── frontend/   # Flutter-приложение (веб + мобилка, один код): карта,
│               # полигоны, график NDVI, аномалии, аналитика, отчёты
├── backend/    # FastAPI + PostgreSQL: авторизация, CRUD полигонов,
│               # временные ряды, детекция аномалий, автопоиск контуров (OSM)
├── ml/         # обучение модели восстановления пропусков и интерпретации
│               # причин аномалий; отдельная точка входа для batch-инференса
├── infra/      # Caddy: реверс-прокси веб-билда + /api/* → backend
├── data/       # датасеты соревнования (train_dataset.csv и т.п.)
├── docs/       # официальные материалы хакатона (ТЗ, критерии, база знаний)
└── tasks/      # бэклог по областям — что сделано и что осталось
```

## Запуск

Бэкенд (FastAPI + PostgreSQL, через Docker Compose):

```bash
cd backend
cp .env.example .env
docker compose up --build -d
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.ingestion.load_train_dataset --csv /data/train_dataset.csv
# API: http://localhost:8000, Swagger: http://localhost:8000/docs
```

Подробнее (переменные окружения, локальный запуск без Docker, тесты,
batch-инференс) — [`backend/README.md`](backend/README.md).

Фронтенд можно запускать на моковых данных (без бэкенда) или подключить
к поднятому бэкенду через `--dart-define=API_BASE_URL`:

```bash
# 1. Backend (API + PostgreSQL), поднимается в Docker
cd backend
cp .env.example .env
docker compose up --build -d
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.ingestion.load_train_dataset --csv /data/train_dataset.csv
# API: http://localhost:8000 (Swagger — /docs)

# 2. Frontend (Flutter web), собирается и раздаётся статикой
cd ../frontend
flutter pub get
flutter build web --release --dart-define=API_BASE_URL=http://localhost:8000
python3 -m http.server 2030 --directory build/web --bind 0.0.0.0
# Открыть http://localhost:2030
```

Подробнее — [`frontend/README.md`](frontend/README.md). Фронт+бэк одним
портом через Caddy — [`infra/README.md`](infra/README.md).

## С чего начать

- Что делать бэкенду/ML — [`tasks/backend.md`](tasks/backend.md) (контракт
  API, реальная схема данных, формат `submission.csv`, метрика).
- Статус ML-решения — [`tasks/ml.md`](tasks/ml.md).
- Что осталось во фронтенде — [`tasks/frontend.md`](tasks/frontend.md).
