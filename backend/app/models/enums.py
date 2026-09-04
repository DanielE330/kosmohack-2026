import enum


class NdviStatus(str, enum.Enum):
    """Статус вегетации по Z-score. Пороги зафиксированы в ТЗ и продублированы
    во Flutter (`frontend/lib/models/ndvi_point.dart`, `ndviStatusForZ`) —
    менять только синхронно с фронтендом."""

    normal = "normal"
    suppression = "suppression"
    critical = "critical"
