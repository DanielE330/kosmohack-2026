from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import anomalies, auth, polygons, timeseries
from app.config import settings

app = FastAPI(
    title="Мониторинг вегетационной динамики — API",
    description=(
        "REST API для оценки состояния растительного покрова и выявления "
        "аномалий вегетации по временным рядам ДЗЗ (Sentinel-2/Landsat/MODIS "
        "+ ERA5). Разработано для КОСМОХАКАТОН 2026, клиент — Flutter."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(polygons.router)
app.include_router(timeseries.router)
app.include_router(anomalies.router)


@app.get("/health", tags=["service"], summary="Проверка живости сервиса")
async def health() -> dict[str, str]:
    return {"status": "ok"}
