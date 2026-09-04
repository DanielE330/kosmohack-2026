# Infra

Reverse proxy (Caddy) that serves the built Flutter web app and forwards
`/api/*` to the backend, so both live behind one origin/port for the demo.

## Использование

```bash
# 1. собрать веб-версию фронта так, чтобы она ходила на бэкенд через /api
cd frontend
flutter build web --release --dart-define=API_BASE_URL=/api
cd ..

# 2. поднять бэкенд отдельно (см. backend/README.md), например на :8000

# 3. поднять caddy
BACKEND_UPSTREAM=localhost:8000 caddy run --config infra/caddy/Caddyfile --adapter caddyfile
```

По умолчанию слушает `localhost:2030` (тот же порт, что использовался для
локального теста веб-версии без прокси) и проксирует backend на
`localhost:8000` — оба переопределяются переменными окружения
`CADDY_ADDR` / `BACKEND_UPSTREAM`, см. комментарии в `caddy/Caddyfile`.

## На будущее

Когда появится Dockerfile для `backend/`, естественный следующий шаг —
`docker-compose.yml` здесь же, поднимающий `backend` + `caddy` (+ сборку
`frontend`) одной командой — это и требование ТЗ по воспроизводимости
(см. `../tasks/backend.md`, раздел про README/окружение). Не добавлял
сейчас, чтобы не класть в репозиторий compose-файл, ссылающийся на ещё не
существующий `backend/Dockerfile`.
