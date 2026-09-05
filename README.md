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

## Как это работает

1. Пользователь выбирает регион на карте (или указывает bbox/название) —
   сервис автоматически находит открытые сельхозконтуры (OSM Overpass) или
   пользователь рисует свой полигон вручную.
2. Backend строит временной ряд `primary_ndvi` по полигону и восстанавливает
   пропуски обученной ML-моделью (`ml/`, градиентный бустинг поверх
   интерполяционного baseline).
3. Аномалии детектируются по Z-score (`Z≥−1` — штатно, `−2≤Z<−1` —
   угнетение биомассы, `Z<−2` — критическая аномалия) и получают текстовое
   объяснение вероятной причины (ML-классификация: засуха, тепловой/
   холодовой стресс, уборка урожая и т.д.).
4. Личный кабинет — свои полигоны, аналитика по всему набору, лента
   уведомлений об аномалиях, табличный отчёт, настройки (тема, смена
   почты/пароля).

## Запуск целиком (frontend + backend + ML)

Нужны Docker и Docker Compose, Flutter SDK 3.x и Python 3.11+.

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

Без `--dart-define=API_BASE_URL=...` фронтенд запускается полностью на
встроенных моковых данных (без backend) — годится для быстрого просмотра
UI, но не сохраняет полигоны на сервере. Подробнее —
[`frontend/README.md`](frontend/README.md) и [`backend/README.md`](backend/README.md).

ML-пайплайн (обучение модели, метрики, batch-инференс для отдельной
проверки) — [`ml/README.md`](ml/README.md).

## Тесты

```bash
cd backend && docker compose up -d db && docker compose run --rm backend pytest && docker compose down
cd frontend && flutter test
cd ml && python -m unittest discover -s tests -v
```

## С чего начать

- Что делать бэкенду/ML — [`tasks/backend.md`](tasks/backend.md) (контракт
  API, реальная схема данных, формат `submission.csv`, метрика).
- Статус ML-решения — [`tasks/ml.md`](tasks/ml.md).
- Что осталось во фронтенде — [`tasks/frontend.md`](tasks/frontend.md).
- Локальный прокси фронт+бэк одним портом — [`infra/README.md`](infra/README.md).
