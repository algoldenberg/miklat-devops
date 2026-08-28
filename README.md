# miklat-devops

Учебный DevOps-капстоун: поиск укрытий (миклатов) и построение маршрутов между ними — написан с нуля как основа для заданий "DevOps on AWS" (Terraform+Ansible → Kubernetes → Jenkins CI/CD).

Прод-приложение [ShelterNearYou](https://shelternearyou.online) ([shelter-route-planner](https://github.com/algoldenberg/shelter-route-planner)) используется только как функциональный референс — этот репозиторий с ним не связан и не модифицирует его.

## Статус

Проект в разработке. Структура и прогресс по фазам ведутся в отдельном рабочем плане (не в этом репозитории).

## Структура репозитория

```
miklat-devops/
├── frontend/                  # React + Vite + Leaflet
├── services/
│   ├── miklat-gateway/        # API Gateway (FastAPI)
│   ├── miklat-service/        # CRUD + админка укрытий (Postgres/PostGIS)
│   ├── miklat-comments/       # рейтинги/отзывы
│   ├── miklat-routes/         # маршрут через несколько укрытий (OSRM)
│   ├── miklat-walking-routes/ # пеший маршрут (OSRM)
│   └── miklat-photos/         # загрузка фото → S3, SNS-уведомления
├── db/                        # SQL-схема (PostGIS)
├── docker-compose.yml         # локальная разработка
├── terraform/                 # инфраструктура AWS (EC2, RDS, S3, SNS)
├── ansible/                   # конфигурация серверов и деплой
├── k8s/                       # Kubernetes-манифесты (k3s)
├── jenkins/                   # Jenkins CI/CD (Helm values, JCasC, Jenkinsfile-ci/cd)
├── docs/                      # архитектурные диаграммы, evidence-скриншоты
└── .env.example
```

## База данных

Схема — PostgreSQL + PostGIS, 5 таблиц: `miklats`, `miklat_comments`, `miklat_reports`,
`miklat_submissions`, `miklat_photos`. Спроектирована на основе реальных данных
прод-приложения (см. `db/001_init.sql` и `db/seed/README.md`).

### Локальный запуск и проверка

> Команда Python в примерах ниже — `python3`. На части Windows-систем (Git Bash)
> установщик python.org регистрирует команду как `python` (без `3`) — если
> `python3` не находится, замените на `python` (`python --version` покажет,
> что стоит).

```bash
# 1. поднять Postgres+PostGIS, схема применится автоматически при первом старте
docker compose up -d postgres

# 2. загрузить seed-данные (12 640 укрытий + реальные комментарии/жалобы/заявки)
cd db
python3 -m venv .venv && source .venv/Scripts/activate   # Windows Git Bash; на Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL="postgresql://miklat:miklat_dev_password@localhost:5432/miklat"
python3 import_seed.py
cd ..

# 3. проверить, что данные на месте
docker exec -it miklat-postgres psql -U miklat -d miklat -c "SELECT count(*) FROM miklats;"
docker exec -it miklat-postgres psql -U miklat -d miklat -c \
  "SELECT name, city, ST_AsText(geom::geometry) FROM miklats WHERE city IS NOT NULL LIMIT 5;"
```

Пример гео-запроса "ближайшее укрытие" (PostGIS), который дальше будет использовать `miklat-service`:

```sql
SELECT id, name, address, city,
       ST_Distance(geom, ST_SetSRID(ST_MakePoint(34.7818, 32.0853), 4326)::geography) AS distance_m
FROM miklats
ORDER BY geom <-> ST_SetSRID(ST_MakePoint(34.7818, 32.0853), 4326)::geography
LIMIT 5;
```

## Сервисы

### miklat-service

CRUD укрытий, поиск ближайшего укрытия (PostGIS), модерация заявок на новое укрытие
(`miklat_submissions`). FastAPI + psycopg2 (без ORM), порт `8000` внутри контейнера
(наружу через docker-compose — `8001`).

Публичные эндпоинты (без авторизации):

| Метод | Путь | Описание |
|---|---|---|
| GET | `/health` | liveness, к БД не обращается |
| GET | `/ready` | readiness, реальный `SELECT 1` в БД |
| GET | `/miklats` | список (фильтры `city`, `type`, пагинация `limit`/`offset`) |
| GET | `/miklats/{id}` | одно укрытие |
| GET | `/miklats/nearest` | ближайшие к точке (`lon`, `lat`, `limit`, `max_distance_m`) |

Admin-эндпоинты (заголовок `X-Admin-Key: <ADMIN_API_KEY>`, см. `.env.example`):

| Метод | Путь | Описание |
|---|---|---|
| POST | `/admin/miklats` | создать укрытие напрямую |
| PATCH | `/admin/miklats/{id}` | частичное обновление |
| DELETE | `/admin/miklats/{id}` | удалить |
| GET | `/admin/submissions` | список заявок (фильтр `status`, по умолчанию `pending`) |
| POST | `/admin/submissions/{id}/approve` | одобрить → создаёт новое укрытие |
| POST | `/admin/submissions/{id}/reject` | отклонить (обязателен `rejection_reason`) |

Полная интерактивная документация — `/docs` (Swagger UI) после запуска сервиса.

Локальный запуск и проверка (Postgres из шага выше уже должен быть поднят и заполнен):

```bash
cd services/miklat-service
python3 -m venv .venv && source .venv/Scripts/activate   # Windows Git Bash; на Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt

cp .env.example .env   # и поменяйте ADMIN_API_KEY на что-то своё
export DATABASE_URL="postgresql://miklat:miklat_dev_password@localhost:5432/miklat"
export ADMIN_API_KEY="dev-secret-123"

# юнит-тесты (не требуют БД)
python3 -m pytest tests/ -v

# сам сервис
uvicorn app.main:app --reload --port 8000
```

Проверка вручную (в отдельном терминале, сервис уже запущен):

```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready
curl "http://localhost:8000/miklats?limit=3"
curl "http://localhost:8000/miklats/nearest?lon=34.7818&lat=32.0853&limit=3"

# admin — без ключа должно быть 401
curl -i -X POST http://localhost:8000/admin/miklats -H "Content-Type: application/json" -d '{"lon":34.78,"lat":32.08}'

# admin — с ключом
curl -X POST http://localhost:8000/admin/miklats \
  -H "X-Admin-Key: dev-secret-123" -H "Content-Type: application/json" \
  -d '{"name":"Test Shelter","city":"Tel Aviv","lon":34.78,"lat":32.08,"capacity":10}'
```

Через docker-compose (соберёт образ сам, порт наружу — `8001`):

```bash
docker compose up -d --build
curl http://localhost:8001/health
```

Тестов пока минимум (smoke-тест `/health`) — полноценный прогон тестов на каждый коммит
появится в Фазе 4 (Jenkinsfile-ci).

### miklat-comments

Комментарии и рейтинги укрытий, привязка к `miklat_id`. Аккаунтов пользователей в
приложении нет (как и в проде) — создание и чтение комментариев публичны,
`username` — произвольная строка (по умолчанию `Anonymous`). Правка/удаление
(модерация спама) — под тем же `X-Admin-Key`, что и у `miklat-service`.
FastAPI + psycopg2, порт `8000` внутри контейнера (наружу через docker-compose — `8002`).

Публичные эндпоинты:

| Метод | Путь | Описание |
|---|---|---|
| GET | `/health` | liveness |
| GET | `/ready` | readiness (проверка БД) |
| GET | `/miklats/{miklat_id}/comments` | список комментариев (пагинация `limit`/`offset`) |
| POST | `/miklats/{miklat_id}/comments` | добавить комментарий (`username?`, `comment`, `rating?` 1–5) |
| GET | `/miklats/{miklat_id}/rating-summary` | `comments_count`, `ratings_count`, `average_rating` |

Admin-эндпоинты (заголовок `X-Admin-Key`):

| Метод | Путь | Описание |
|---|---|---|
| PATCH | `/admin/comments/{id}` | правка (модерация) |
| DELETE | `/admin/comments/{id}` | удаление (спам/абьюз) |

Локальный запуск — аналогично `miklat-service` (Postgres уже поднят и заполнен):

```bash
cd services/miklat-comments
python3 -m venv .venv && source .venv/Scripts/activate   # Windows Git Bash; на Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt

cp .env.example .env   # тот же ADMIN_API_KEY, что и в miklat-service, если хотите единый ключ
export DATABASE_URL="postgresql://miklat:miklat_dev_password@localhost:5432/miklat"
export ADMIN_API_KEY="dev-secret-123"

python3 -m pytest tests/ -v
uvicorn app.main:app --reload --port 8000
```

Проверка вручную:

```bash
curl http://localhost:8000/health
curl -X POST http://localhost:8000/miklats/1/comments -H "Content-Type: application/json" \
  -d '{"username":"Alex","comment":"Чисто, доступно","rating":4}'
curl http://localhost:8000/miklats/1/comments
curl http://localhost:8000/miklats/1/rating-summary

# модерация
curl -X DELETE http://localhost:8000/admin/comments/1 -H "X-Admin-Key: dev-secret-123"
```

Через docker-compose (порт наружу — `8002`):

```bash
docker compose up -d --build
curl http://localhost:8002/health
```

### OSRM + miklat-routes / miklat-walking-routes

Пеший маршрутизатор (OSRM, только профиль `foot` — см. `osrm/README.md` про то,
почему не `car`). Два сервиса дёргают один и тот же контейнер `osrm` по HTTP:

- **miklat-walking-routes** — маршрут от точки пользователя до одного укрытия
  (основной сценарий приложения).
- **miklat-routes** — маршрут через несколько укрытий по списку `miklat_id`,
  в заданном порядке (без оптимизации порядка — TSP не решаем).

**Важно:** прежде чем поднимать эти сервисы, один раз подготовьте данные OSRM
(скачивание карты + построение графа, несколько минут):

```bash
bash osrm/prepare-data.sh
```

Подробности — `osrm/README.md`. Без этого шага контейнер `osrm` не запустится
(нет файлов графа), и оба сервиса маршрутов будут в состоянии `degraded`
(`/ready` покажет `"osrm":"down"`).

#### miklat-walking-routes

| Метод | Путь | Описание |
|---|---|---|
| GET | `/health` / `/ready` | liveness / readiness (БД + OSRM) |
| POST | `/route` | маршрут между двумя точками: `{"from":{"lon","lat"},"to":{"lon","lat"}}` |
| GET | `/route-to-miklat/{id}?from_lon=&from_lat=` | маршрут от пользователя до укрытия по его id |

#### miklat-routes

| Метод | Путь | Описание |
|---|---|---|
| GET | `/health` / `/ready` | liveness / readiness (БД + OSRM) |
| POST | `/route` | маршрут по произвольным точкам: `{"waypoints":[{"lon","lat"},...]}` (2–15) |
| POST | `/route-through-miklats` | `{"miklat_ids":[...],"start":{"lon","lat"}?}` — маршрут через укрытия по id |

Оба сервиса отвечают `{distance_m, duration_s, geometry (GeoJSON LineString), profile:"foot"}`
(`miklat-routes` — ещё `legs` с разбивкой по перегонам и `total_*` вместо голых
`distance_m`/`duration_s`).

Локальный запуск (аналогично предыдущим сервисам; нужен и Postgres, и OSRM):

```bash
cd services/miklat-walking-routes   # или services/miklat-routes
python3 -m venv .venv && source .venv/Scripts/activate   # Windows Git Bash; на Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt

cp .env.example .env
export DATABASE_URL="postgresql://miklat:miklat_dev_password@localhost:5432/miklat"
export OSRM_BASE_URL="http://localhost:5001"

# юнит-тесты бизнес-логики — с "заглушкой" OSRM, реальный OSRM не нужен
python3 -m pytest tests/ -v

uvicorn app.main:app --reload --port 8000
```

Проверка через docker-compose (поднимет всё сразу — Postgres, OSRM, все сервисы):

```bash
docker compose up -d --build

curl http://localhost:8004/ready   # miklat-walking-routes
curl http://localhost:8003/ready   # miklat-routes

# пеший маршрут до конкретного укрытия (id и координаты подставьте свои,
# например id=12362 "Kindergarden Mamads" из seed-данных, координаты рядом)
curl "http://localhost:8004/route-to-miklat/12362?from_lon=34.78&from_lat=32.08"

# маршрут через несколько укрытий
curl -X POST http://localhost:8003/route-through-miklats \
  -H "Content-Type: application/json" \
  -d '{"miklat_ids":[12362,1],"start":{"lon":34.78,"lat":32.08}}'
```

Ожидаемо: `distance_m`/`duration_s` — разумные числа для пешехода в этом районе
Тель-Авива (не нулевые и не астрономические), `geometry` — непустой `LineString`
вдоль реальных улиц.

