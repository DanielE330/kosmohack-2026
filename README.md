# SkyTime — мониторинг вегетационной динамики

Проект для хакатона «КОСМОХАКАТОН» 2026: сервис для мониторинга состояния растительности
сельскохозяйственных полигонов по спутниковым временным рядам NDVI —
восстановление пропусков и детекция аномалий (Z-score).

- Полное ТЗ — [`docs/tz.pdf`](docs/tz.pdf)
- Критерии оценки (100 баллов) — [`docs/criteria.pdf`](docs/criteria.pdf)
- **База знаний проекта** (сводка ТЗ, критериев, реальных данных,
  архитектуры и открытых вопросов — один файл, чтобы не читать всё
  остальное с нуля) — [`docs/KNOWLEDGE_BASE.md`](docs/KNOWLEDGE_BASE.md)

## Структура репозитория

```
.
├── frontend/   # Flutter-приложение (веб + мобилка, один код)
├── backend/    # API (FastAPI + PostgreSQL) + пайплайн обработки данных
├── infra/      # инфраструктура для локального/демо-развёртывания (Caddy)
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
cd frontend
flutter pub get
flutter build web --release --dart-define=API_BASE_URL=http://localhost:8000
python3 -m http.server 2030 --directory build/web --bind 0.0.0.0
# открыть http://localhost:2030
```

Подробнее — [`frontend/README.md`](frontend/README.md). Фронт+бэк одним
портом через Caddy — [`infra/README.md`](infra/README.md).

## С чего начать

- Что делать бэкенду/ML — [`tasks/backend.md`](tasks/backend.md) (контракт
  API, реальная схема данных, формат `submission.csv`, метрика).
- Что осталось во фронтенде — [`tasks/frontend.md`](tasks/frontend.md).
