# kosmohack_app

Flutter-клиент (веб + мобилка, один код): карта с полигонами полей,
рисование своего контура, график `primary_ndvi` (исходные vs
восстановленные точки) против климатической нормы, список аномалий по
Z-score. Контекст задачи — [`../tasks/frontend.md`](../tasks/frontend.md) и
[`../tasks/backend.md`](../tasks/backend.md) (контракт API).

## Запуск

```bash
flutter pub get

# на моковых данных (по умолчанию)
flutter run -d chrome
# или для тестового сервера, доступного по сети:
flutter build web --release
python3 -m http.server 2030 --directory build/web --bind 0.0.0.0

# на реальном бэкенде, когда он будет готов
flutter run -d chrome --dart-define=API_BASE_URL=http://localhost:8000
```

`flutter run -d web-server` в debug-режиме требует Dart Debug Chrome
Extension, иначе страница остаётся белой — для демо без плагинов
использовать `flutter build web --release` + любой статик-сервер (см. выше).

## Тесты и анализ

```bash
flutter analyze
flutter test
```
