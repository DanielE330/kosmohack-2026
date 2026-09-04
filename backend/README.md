# Backend

Пока пусто — сервис ещё не начат (см. [`../tasks/backend.md`](../tasks/backend.md)
для полного контекста: контракт API, схема данных, формат `submission.csv`).

## Ожидаемая структура

Конкретный стек не зафиксирован (ТЗ разрешает любой), но контракт с
фронтендом уже описан в `../tasks/backend.md` — ориентируйтесь на него.
Предполагается что-то в духе:

```
backend/
├── app/                 # код сервиса (FastAPI или аналог)
│   ├── api/              # роуты: /polygons, /polygons/custom, /timeseries, /anomalies
│   ├── ingestion/         # приём/гармонизация Sentinel-2/Landsat/MODIS + ERA5
│   ├── anomalies/         # Z-score детекция и интерпретация
│   └── gapfill/           # восстановление primary_ndvi (Задача 1)
├── inference/            # отдельный technical batch-инференс:
│                          #   private_features.csv -> submission.csv
├── requirements.txt / pyproject.toml
├── Dockerfile
└── README.md              # эта команда — обновить под факт. реализацию
```

Веб-сервис и batch-инференс — это **две разные точки входа**, не
завязывать одно на другое (см. п.5 в `../tasks/backend.md`).

## Локальные данные

`../data/train_dataset.csv` уже в репозитории. `private_features.csv` пока
не найден.
