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
(`miklat_submissions`), приём и модерация жалоб на существующее укрытие
(`miklat_reports`, SNS-триггер #2 — см. ниже). FastAPI + psycopg2 (без ORM) + boto3,
порт `8000` внутри контейнера (наружу через docker-compose — `8001`).

Публичные эндпоинты (без авторизации):

| Метод | Путь | Описание |
|---|---|---|
| GET | `/health` | liveness, к БД не обращается |
| GET | `/ready` | readiness (БД + доступность SNS-топика) |
| GET | `/miklats` | список (фильтры `city`, `type`, пагинация `limit`/`offset`) |
| GET | `/miklats/{id}` | одно укрытие |
| GET | `/miklats/nearest` | ближайшие к точке (`lon`, `lat`, `limit`, `max_distance_m`) |
| POST | `/miklats/{id}/reports` | пожаловаться на укрытие (`issue_type`: `closed`\|`wrong_address`\|`other`, `comment?`, `contact?`) |
| POST | `/submissions` | заявка на новое укрытие (форма "добавить укрытие" на фронтенде, SNS-триггер #1a) — `name?`, `address?`, `lon`, `lat`, `type?`, `capacity?`, `comment?`; попадает в очередь модерации, `miklats` напрямую не создаёт |

Admin-эндпоинты (заголовок `X-Admin-Key: <ADMIN_API_KEY>`, см. `.env.example`):

| Метод | Путь | Описание |
|---|---|---|
| POST | `/admin/miklats` | создать укрытие напрямую |
| PATCH | `/admin/miklats/{id}` | частичное обновление |
| DELETE | `/admin/miklats/{id}` | удалить |
| GET | `/admin/submissions` | список заявок (фильтр `status`, по умолчанию `pending`) |
| POST | `/admin/submissions/{id}/approve` | одобрить → создаёт новое укрытие |
| POST | `/admin/submissions/{id}/reject` | отклонить (обязателен `rejection_reason`) |
| GET | `/admin/reports` | список жалоб (фильтр `status`, по умолчанию `pending`) |
| POST | `/admin/reports/{id}/resolve` | отметить жалобу решённой |
| POST | `/admin/reports/{id}/invalid` | отметить жалобу необоснованной |

Если публикация в SNS не удалась — жалоба/заявка (как и фото в miklat-photos)
всё равно считается сохранённой; ошибка публикации только логируется на сервере.

`POST /submissions` — тот самый SNS-триггер #1a, который был описан ещё в
комментарии к таблице `miklat_submissions` в `db/001_init.sql` (Фаза 1 шаг 1),
но публичного эндпоинта для него не было до Фазы 1 шага 8 (фронтенду нужна
была форма "добавить укрытие", и без него её не на что было вешать). Ничего
не создаёт в `miklats` напрямую — только заявку со статусом `pending`,
дальше `POST /admin/submissions/{id}/approve`/`reject`, как и раньше.

**Тот же единственный ручной AWS-шаг**, что описан у `miklat-photos` ниже — один
SNS topic `miklat-notifications` на оба сервиса (уведомления о фото и о жалобах
различаются только полем `event` в теле сообщения). Без `SNS_TOPIC_ARN` в
окружении сервис поднимется нормально, `/report` просто не отправит уведомление,
`/ready` покажет `"sns":"not configured"`.

Полная интерактивная документация — `/docs` (Swagger UI) после запуска сервиса.

Локальный запуск и проверка (Postgres из шага выше уже должен быть поднят и заполнен):

```bash
cd services/miklat-service
python3 -m venv .venv && source .venv/Scripts/activate   # Windows Git Bash; на Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt

cp .env.example .env   # поменяйте ADMIN_API_KEY и заполните AWS_*/SNS_TOPIC_ARN
export DATABASE_URL="postgresql://miklat:miklat_dev_password@localhost:5432/miklat"
export ADMIN_API_KEY="dev-secret-123"
export SNS_TOPIC_ARN="arn:aws:sns:eu-central-1:<account-id>:miklat-notifications"

# тесты — реальная БД, но SNS через monkeypatch (см. tests/test_reports.py)
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

# жалоба на укрытие (публично, без ключа)
curl -X POST http://localhost:8000/miklats/1/reports -H "Content-Type: application/json" \
  -d '{"issue_type":"wrong_address","comment":"Координаты указывают на соседний двор"}'

# заявка на новое укрытие (публично, без ключа)
curl -X POST http://localhost:8000/submissions -H "Content-Type: application/json" \
  -d '{"name":"Новое укрытие во дворе","lon":34.79,"lat":32.09,"capacity":15}'

# admin — без ключа должно быть 401
curl -i -X POST http://localhost:8000/admin/miklats -H "Content-Type: application/json" -d '{"lon":34.78,"lat":32.08}'

# admin — с ключом
curl -X POST http://localhost:8000/admin/miklats \
  -H "X-Admin-Key: dev-secret-123" -H "Content-Type: application/json" \
  -d '{"name":"Test Shelter","city":"Tel Aviv","lon":34.78,"lat":32.08,"capacity":10}'

# admin — модерация жалоб
curl "http://localhost:8000/admin/reports?status=pending" -H "X-Admin-Key: dev-secret-123"
curl -X POST http://localhost:8000/admin/reports/1/resolve -H "X-Admin-Key: dev-secret-123"
```

Через docker-compose (соберёт образ сам, порт наружу — `8001`):

```bash
docker compose up -d --build
curl http://localhost:8001/health
```

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

### miklat-photos

Загрузка фото существующего укрытия (`miklat_id` должен уже существовать):
файл → S3 (dev-бакет) → запись в `miklat_photos` (`status='pending'`) →
SNS-уведомление админу о новом фото на модерации. FastAPI + psycopg2 + boto3,
порт `8000` внутри контейнера (наружу через docker-compose — `8005`).

Доступ к самим файлам — через **presigned S3 URL** (ссылка с ограниченным
сроком жизни, по умолчанию 1 час), а не через публичный bucket policy: IAM-
пользователь приложения по плану имеет только `s3:PutObject`/`s3:GetObject`,
без анонимного публичного доступа к бакету.

Публичные эндпоинты:

| Метод | Путь | Описание |
|---|---|---|
| GET | `/health` | liveness |
| GET | `/ready` | readiness (БД + `head_bucket` на S3) |
| POST | `/miklats/{miklat_id}/photos` | загрузить фото (`multipart/form-data`, поле `file`; jpeg/png/webp, ≤8 МБ) |
| GET | `/miklats/{miklat_id}/photos` | список **одобренных** фото (с presigned `url`) |

Admin-эндпоинты (заголовок `X-Admin-Key`):

| Метод | Путь | Описание |
|---|---|---|
| GET | `/admin/photos?status=pending\|approved\|rejected` | список фото (любой статус, с presigned `url`) |
| POST | `/admin/photos/{id}/approve` | одобрить — становится видно в публичном списке |
| POST | `/admin/photos/{id}/reject` | отклонить — остаётся скрыто |
| DELETE | `/admin/photos/{id}` | удалить запись и сам файл из S3 |

Если публикация в SNS не удалась (топик недоступен, нет прав и т.п.) —
аплоуд всё равно считается успешным (фото сохранено, статус `pending`),
ошибка только логируется на сервере: сбой уведомления не должен блокировать
основную функцию (сохранение фото).

**Единственный ручной AWS-шаг во всём проекте** (см. `miklat-work-plan.md`,
Фаза 1 шаг 9) — нужно один раз вручную создать dev-ресурсы, прежде чем этот
сервис сможет реально работать (без них он поднимется и ответит на
`/health`, но `/ready` и сама загрузка фото будут падать):

1. S3 bucket (например `miklat-photos-dev-<ваш суффикс>`), в том же регионе,
   что укажете в `AWS_REGION`.
2. SNS topic `miklat-notifications` + Email Subscription на свою почту
   (подтвердить подписку по ссылке из письма от AWS).
3. IAM-пользователь только с правами `s3:PutObject`/`s3:GetObject`/`s3:DeleteObject`
   на этот бакет и `sns:Publish` на этот topic — access key/secret от него
   пойдут в `.env`/окружение. (Тот же самый бакет и topic дальше в Фазе 2
   будут создаваться из Terraform кодом — это разовый dev-шаг, не замена.)

Локальный запуск:

```bash
cd services/miklat-photos
python3 -m venv .venv && source .venv/Scripts/activate   # Windows Git Bash; на Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt

cp .env.example .env   # заполнить AWS_* реальными dev-значениями (см. выше)
export DATABASE_URL="postgresql://miklat:miklat_dev_password@localhost:5432/miklat"
export ADMIN_API_KEY="dev-secret-123"
export AWS_REGION="eu-central-1"
export AWS_ACCESS_KEY_ID="..."
export AWS_SECRET_ACCESS_KEY="..."
export S3_BUCKET_NAME="miklat-photos-dev-..."
export SNS_TOPIC_ARN="arn:aws:sns:eu-central-1:<account-id>:miklat-notifications"

# юнит/функциональные тесты — реальная БД, но S3/SNS через monkeypatch
# (в песочнице/CI без реального AWS-доступа не запускаем настоящие вызовы)
python3 -m pytest tests/ -v

uvicorn app.main:app --reload --port 8000
```

Проверка вручную (нужны реальные AWS-креды в окружении):

```bash
curl http://localhost:8000/ready   # {"status":"ok","database":"up","s3":"up"}

curl -X POST http://localhost:8000/miklats/1/photos -F "file=@/path/to/photo.jpg"

curl http://localhost:8000/miklats/1/photos   # пока пусто — фото ещё pending

# админ одобряет
curl -X POST http://localhost:8000/admin/photos/1/approve -H "X-Admin-Key: dev-secret-123"

curl http://localhost:8000/miklats/1/photos   # теперь фото видно, с presigned url
```

Через docker-compose (порт наружу — `8005`; создайте `.env` в корне
репозитория с `AWS_*`/`S3_BUCKET_NAME`/`SNS_TOPIC_ARN` — docker-compose
подхватит его автоматически, `.env` в `.gitignore`):

```bash
docker compose up -d --build
curl http://localhost:8005/ready
```

### miklat-gateway

Единая точка входа: маршрутизирует запрос к нужному сервису по пути, без
собственного состояния/БД. На фронтенде (см. `combined-project-overview.md`)
nginx будет проксировать `/api/*` сюда, снимая префикс `/api` — сам gateway
работает с теми же "голыми" путями, что и сами backend-сервисы (см. таблицу
ниже), поэтому им самим менять ничего не пришлось.

| Путь (пример) | Куда уходит |
|---|---|
| `GET/PATCH/DELETE /miklats`, `/miklats/{id}`, `/miklats/nearest` | `miklat-service` |
| `GET/POST /miklats/{id}/comments`, `GET /miklats/{id}/rating-summary` | `miklat-comments` |
| `GET/POST /miklats/{id}/photos` | `miklat-photos` |
| `POST /miklats/{id}/reports` | `miklat-service` |
| `POST /submissions` | `miklat-service` |
| `POST /route` (две точки) | `miklat-walking-routes` |
| `GET /route-to-miklat/{id}` | `miklat-walking-routes` |
| `POST /route-through-miklats` | `miklat-routes` |
| `/admin/miklats*`, `/admin/submissions*`, `/admin/reports*` | `miklat-service` |
| `/admin/comments*` | `miklat-comments` |
| `/admin/photos*` | `miklat-photos` |

Собственный generic `POST /route` сервиса `miklat-routes` (произвольный
список из 2–15 точек) наружу через gateway не выставлен — он избыточен по
отношению к `/route-through-miklats` и двухточечному `/route` от
`miklat-walking-routes`; коллизия путей между двумя сервисами на `/route`
разрешена в пользу последнего (см. `app/routing.py`).

`X-Admin-Key` gateway не проверяет и никак не трогает — просто пересылает
заголовок как есть, аутентификацию по-прежнему делает конкретный backend.
Тело запроса (в т.ч. `multipart/form-data` при загрузке фото) пересылается
байт-в-байт, без разбора.

`GET /ready` — не просто проверка себя, а реальный пинг `/health` всех
пяти сервисов сразу; в ответе видно, какие именно недоступны:

```json
{"status":"degraded","services":{"miklat-service":"up","miklat-comments":"down", "...": "..."}}
```

Локальный запуск (нужны уже поднятые остальные сервисы — проще всего через
docker-compose, см. ниже; для запуска вне docker-compose gateway достаточно
знать их адреса через `.env`):

```bash
cd services/miklat-gateway
python3 -m venv .venv && source .venv/Scripts/activate   # Windows Git Bash; на Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt

# юнит-тесты (таблица маршрутизации + сам прокси на ASGI-заглушке — реальная сеть не нужна)
python3 -m pytest tests/ -v

cp .env.example .env   # если сервисы уже подняты через docker-compose, подставьте их localhost-порты
uvicorn app.main:app --reload --port 8000
```

Проверка через docker-compose (порт наружу — `8000`, поднимет вообще всё):

```bash
docker compose up -d --build

curl http://localhost:8000/health
curl http://localhost:8000/ready                       # агрегированная готовность всех сервисов
curl http://localhost:8000/miklats                      # -> miklat-service, как будто напрямую
curl "http://localhost:8000/route-to-miklat/12362?from_lon=34.78&from_lat=32.08"   # -> miklat-walking-routes
```

### Frontend

React + Vite + Leaflet (Фаза 1, шаг 8) — публичный клиент: карта укрытий,
список с фильтрами (город/тип), детальная карточка укрытия (комментарии и
рейтинг, одобренные фото + загрузка новых), построение пешего маршрута от
геолокации пользователя до выбранного укрытия, форма жалобы и форма
"добавить укрытие" (координаты выбираются кликом по карте). Обращается
только к `miklat-gateway`, через единый префикс `/api/*` — сам фронтенд
никогда не знает адресов остальных пяти сервисов.

Собран в статику (`vite build`) и отдаётся через nginx (`frontend/Dockerfile`,
`frontend/nginx.conf`) — nginx же проксирует `/api/*` на `miklat-gateway`
внутри docker-сети (тот же reverse-proxy приём, что запланирован для
настоящего EC2-frontend в Ansible `playbooks/nginx.yml`, Фаза 2). Порт внутри
контейнера — `8080` (non-root nginx), наружу через docker-compose — `3000`.

Локальный запуск без Docker (нужен уже поднятый `miklat-gateway`, порт 8000):

```bash
cd frontend
npm install
npm run dev   # http://localhost:5173, "/api/*" проксируется на localhost:8000 (см. vite.config.js)
```

Через docker-compose (поднимет весь стек, порт наружу — `3000`):

```bash
docker compose up -d --build
# открыть в браузере http://localhost:3000
```

Проверено (headless-браузер в песочнице Claude, реальный шлюз подменён
минимальной заглушкой на fetch-уровне — DOM/сеть настоящие, только backend
не настоящий AWS/Postgres): рендер карты и списка укрытий, выбор укрытия по
клику на карте и в списке, геолокация подставляется в "ближайшие укрытия",
построение маршрута и отрисовка линии на карте, отправка комментария и
немедленное обновление списка, отправка жалобы, форма "добавить укрытие" с
выбором точки по клику на карте. По ходу проверки найден и исправлен один
реальный баг: модальное окно формы "добавить укрытие" перекрывало карту
на весь экран, из-за чего клик "указать точку на карте" физически не мог
долететь до самой карты — исправлено скрытием модалки на время выбора точки
(остаётся только баннер-подсказка поверх карты).

