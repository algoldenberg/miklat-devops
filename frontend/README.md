# miklat-devops — frontend

React + Vite + Leaflet. Публичный клиент для miklat-devops (Фаза 1, шаг 8) —
карта укрытий, список, комментарии/рейтинги, фото, построение пешего
маршрута, форма жалобы и форма добавления нового укрытия. Обращается
исключительно к `miklat-gateway` (см. `../services/miklat-gateway/`) через
префикс `/api/*` — никогда напрямую к остальным сервисам.

Подробное описание проекта, эндпоинтов и запуска через docker-compose — в
корневом [README.md](../README.md#frontend).

## Быстрый старт (без Docker)

```bash
npm install
cp .env.example .env   # при необходимости — см. .env.example
npm run dev
```

Откроется на http://localhost:5173. Требует уже запущенный `miklat-gateway`
(по умолчанию ожидается на http://localhost:8000 — см. `VITE_GATEWAY_URL` в
`.env.example`).

## Через docker-compose (весь стек)

См. корневой README — `docker compose up -d --build`, фронтенд поднимется
на http://localhost:3000 (см. `docker-compose.yml`) и сам обратится к
`miklat-gateway` внутри docker-сети (адрес зашит в `nginx.conf`).

## Сборка

```bash
npm run build   # -> dist/
npm run lint    # oxlint
```
