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

## Инфраструктура: Terraform (Задание 2)

Весь код — в `terraform/`. Поднимает в AWS (регион `il-central-1`, тот же
аккаунт, что и ручной dev-S3/SNS из Фазы 1) сеть, 3 EC2-инстанса, RDS
PostgreSQL, S3-бакет для фото и SNS-топик уведомлений — с нуля, без единого
ручного шага в AWS-консоли.

### Файлы и что каждый создаёт

| Файл | Что содержит |
|---|---|
| `versions.tf` | Версии Terraform (`>= 1.5.0`) и провайдера AWS (`~> 5.0`) |
| `providers.tf` | Провайдер `aws` (регион/профиль из переменных), `data.aws_caller_identity` |
| `backend.tf` | Backend состояния — **local** (см. "State" ниже) |
| `variables.tf` | Все переменные окружения/аккаунта |
| `network.tf` | VPC, 2 публичные подсети (разные AZ), Internet Gateway, route table, `aws_db_subnet_group` |
| `security_groups.tf` | 4 security group — `frontend`/`backend`/`worker`/`rds`, минимальные правила (см. ниже) |
| `ec2.tf` | 3 инстанса (`frontend`/`backend`/`worker`), Key Pair из уже существующего публичного ключа, AMI Amazon Linux 2023 через SSM-параметр |
| `iam.tf` | IAM Role + инстанс-профиль для backend/worker (доступ к S3/SNS без статических ключей) |
| `rds.tf` | RDS PostgreSQL 16, `publicly_accessible = false`, `skip_final_snapshot = true` |
| `s3.tf` | S3-бакет для фото, публичный доступ полностью заблокирован, шифрование по умолчанию |
| `sns.tf` | SNS-топик уведомлений + email-подписка |
| `outputs.tf` | IP серверов, RDS endpoint, имя бакета, ARN топика — то, что дальше нужно Ansible |
| `terraform.tfvars.example` | Шаблон переменных без реальных значений (реальный `terraform.tfvars` — только локально, в `.gitignore`) |

### Ключевые решения

- **Деление на 3 роли** (frontend/backend/worker) — то же самое, что задаёт план и структура Ansible-плейбуков:
  frontend = nginx + статика; backend = `miklat-gateway` + `miklat-service` + `miklat-comments`; worker =
  `miklat-routes` + `miklat-walking-routes` + `miklat-photos` + OSRM. Security group каждой роли пускает
  только то, что реально нужно (frontend → 80/443 из интернета; backend → 8000 только от frontend; worker →
  8003/8004/8005 только от backend; RDS → 5432 только от backend и worker). SSH везде — только с одного
  доверенного IP (`var.ssh_allowed_cidr`, без дефолта, `0.0.0.0/0` для SSH недопустим).
- **Без NAT Gateway / приватных подсетей** — все три EC2 в публичных подсетях (дешевле и проще для
  однослойного учебного стенда), но реальная изоляция всё равно есть — через security groups и через
  `publicly_accessible = false` у RDS, а не через "подсеть без интернета".
- **State — локальный backend**, не S3+DynamoDB: проект соло, конкурентной записи в state нет, а поднимать
  отдельный бакет+таблицу только ради самого Terraform — лишняя инфраструктура. `terraform.tfstate`
  никогда не коммитится (в нём в открытом виде пароль RDS).
- **Доступ приложения к S3/SNS — через IAM Role + instance profile** на backend/worker (не статический
  IAM-пользователь с access key, как в ручном dev-варианте из Фазы 1) — AWS сам подставляет и ротирует
  временные credentials через instance metadata, ничего секретного не попадает ни в `.env`, ни в Ansible.
- **S3-бакет и SNS-топик — отдельные от ручных dev-ресурсов Фазы 1** (суффикс `-tf` в имени) — тот, ручной
  (`miklat-photos-dev-<account_id>` и топик `miklat-notifications`), остаётся и продолжает обслуживать
  локальную разработку через docker-compose; эти, новые — то, чем реально пользуется стенд на EC2.
- **`.terraform.lock.hcl` коммитится** (в отличие от того, что было изначально в `.gitignore` ещё с Фазы 0,
  до появления самого Terraform-кода) — фиксирует конкретную версию и хэши провайдера ради воспроизводимости.

### Как запустить

Понадобится: AWS CLI с настроенными credentials (тот же аккаунт/профиль, что и в Фазе 1), Terraform ≥ 1.5,
и SSH-ключ (публичный — Terraform загрузит его в AWS, приватный остаётся только у тебя):

```bash
# если пары ещё нет:
ssh-keygen -t ed25519 -f ~/.ssh/miklat-devops -C "miklat-devops"

cd terraform
cp terraform.tfvars.example terraform.tfvars
# отредактировать terraform.tfvars: ssh_allowed_cidr (свой внешний IP + /32),
# ssh_public_key_path, db_password, при необходимости aws_profile

terraform init
terraform plan    # проверить, что именно будет создано, ПЕРЕД apply
terraform apply
```

После `apply` — `terraform output` покажет IP всех трёх серверов, RDS endpoint, имя S3-бакета и ARN SNS-топика
(нужны следующему шагу — Ansible). Email-подписку SNS нужно подтвердить по ссылке из письма (тот же ручной
шаг, что и в Фазе 1, — Terraform не может кликнуть за тебя).

Удаление всего созданного:

```bash
terraform destroy
```

### Проверено

`terraform fmt`, `terraform init` и `terraform validate` прогнаны в песочнице Claude — конфигурация
синтаксически корректна, все ссылки между ресурсами резолвятся. `terraform plan` с заведомо фиктивными AWS
credentials дошёл до самого последнего шага (реальный вызов `sts:GetCallerIdentity` для проверки
identity) и корректно упал именно там с `InvalidClientTokenId` — то есть все переменные, файлы (включая
чтение публичного SSH-ключа) и весь граф ресурсов уже отрезолвились без ошибок, и единственное, чего не
хватает для реального `plan`/`apply`, — настоящих AWS-credentials, которых в изолированной песочнице
Claude нет и быть не может. Реальный `terraform init/plan/apply` на настоящем аккаунте — следующий шаг,
выполняется пользователем со своей машины (см. рабочее соглашение по git/AWS-доступу в `miklat-progress.md`).

**Обновление:** реальный `terraform apply` выполнен, все 26 ресурсов созданы (см. журнал в
`miklat-progress.md`) — IP серверов, RDS endpoint, S3-бакет и ARN SNS-топика зафиксированы там же.

## Конфигурация серверов: Ansible (Задание 2, продолжение)

Весь код — в `ansible/`. Настраивает три уже созданных Terraform'ом EC2 (frontend/backend/worker):
устанавливает нужные пакеты, разворачивает шесть python/uvicorn-сервисов и nginx как systemd-юниты,
поднимает OSRM.

### Ansible не запускается из-под нативного Windows

`ansible-playbook` официально не поддерживает Windows как control node. Вместо WSL используется Docker
(он и так уже нужен всему остальному проекту) — `ansible/Dockerfile` собирает образ с Ansible и SSH-клиентом,
внутрь монтируются код репозитория и SSH-ключ. Этот контейнер — чисто инструмент запуска, он никак не привязан
к тому, что настраивает: при любых будущих изменениях (домен, другой сервер) меняется только `inventory.ini`,
сам механизм запуска остаётся тем же.

### Файлы

| Файл/папка | Что содержит |
|---|---|
| `Dockerfile` | Образ control node — Python + Ansible + openssh-client + rsync |
| `ansible.cfg` | `host_key_checking = False` (стенд пересоздаётся через terraform apply/destroy, IP и host key каждый раз новые) |
| `inventory.ini.example` | Шаблон инвентаря — 3 хоста по группам frontend/backend/worker |
| `group_vars/all/vars.yml` | Несекретные настройки (порты, пути, имя БД) — коммитится |
| `group_vars/all/secrets.yml.example` | Шаблон секретов/значений из `terraform output` (пароль БД, ARN, приватные IP) |
| `playbooks/base.yml` | Все хосты: обновление пакетов, python3, системный пользователь `miklat`, swap-файл |
| `playbooks/nginx.yml` | Только frontend: nginx + сборка React/Vite прямо на сервере, reverse proxy `/api/*` |
| `playbooks/deploy-backend.yml` | `miklat-gateway` + `miklat-service` + `miklat-comments` — venv + systemd |
| `playbooks/deploy-worker.yml` | `miklat-routes` + `miklat-walking-routes` + `miklat-photos` (venv + systemd) + OSRM (Docker + systemd) |
| `templates/` | Jinja2-шаблоны: `.env` на каждый сервис, общий systemd-юнит для python-сервисов, отдельный — для OSRM, nginx-конфиг |

### Ключевые решения

- **Сервисы — как systemd-юниты поверх venv, не Docker** (кроме OSRM) — соответствует плану Задания 2
  буквально ("Python venv... systemd unit на каждый сервис"); Docker/контейнеризация всего стека — тема
  Задания 3 (K8s), здесь так специально не делаем, чтобы не смешивать содержательные части двух заданий.
- **OSRM — исключение, через Docker**: это готовый бинарник в официальном образе
  (`ghcr.io/project-osrm/osrm-backend`), а не свой python-код — устанавливать/собирать его "нативно" на
  EC2 намного сложнее и хрупче, чем один `docker run`. Запускается как systemd-юнит, обёрткой над `docker
  run` — ради единообразия со всеми остальными сервисами, без модулей `community.docker` (не нужен ещё и
  Docker SDK for Python на хосте).
- **Обработанный граф OSRM переносится, а не пересчитывается на сервере** — `osrm/data/*` из Фазы 1 (шаг 4)
  копируется rsync'ом с локальной машины. Пересчёт (`osrm-extract/partition/customize`) на t3.micro (1 ГБ
  RAM) для карты такого размера — рискованно по памяти и на порядок дольше, а результат уже есть и
  проверен.
- **`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` в `.env`-файлах сервисов НЕ прописываются** — на EC2
  credentials приходят через IAM instance profile (см. `terraform/iam.tf`), boto3 сам находит их через
  instance metadata. Явно прописать их пустой строкой было бы ошибкой — boto3 воспринял бы `""` как
  реальные (пустые/невалидные) credentials и не стал бы обращаться к metadata вообще.
- **gateway обращается к соседям по backend через `127.0.0.1`**, а к worker — по приватному IP: `miklat-
  service`/`miklat-comments` живут на том же хосте, что и `miklat-gateway`, `miklat-routes`/`miklat-walking-
  routes`/`miklat-photos` — на другом (см. `terraform/security_groups.tf`).
- **Swap-файл (1 ГБ) на всех трёх хостах** (`base.yml`) — подстраховка: t3.micro/db.t3.micro — это всего
  1 ГБ RAM, а на worker одновременно работают 3 python-сервиса и OSRM с графом в 2+ млн узлов. Если этого
  всё равно не хватит — самое простое лечение потом — поднять `instance_type` конкретно для worker через
  Terraform (сейчас у всех трёх ролей общая переменная), не переделывая Ansible.
- **Копирование кода — через `ansible.posix.synchronize` (rsync), не `ansible.builtin.copy`** — для
  фронтенда и особенно для данных OSRM (потенциально сотни МБ) обычный `copy` намного медленнее (модуль
  гоняет файлы через тот же канал, что и остальные ansible-команды, без rsync-дельт); плюс `synchronize`
  поддерживает `--exclude` (нужно исключить `node_modules`/`dist` у фронтенда, `venv`/`__pycache__` у
  python-сервисов).
- **Хосты в `inventory.ini` — просто IP-адреса**, не алиасы вроде "frontend" — иначе ansible ругается
  предупреждением "Found both group and host with same name" (группа `[frontend]` и единственный хост
  внутри неё назывались бы одинаково).

### Как запустить

```bash
# один раз — собрать образ control node:
docker build -t miklat-ansible ansible/

cd ansible
cp inventory.ini.example inventory.ini
# вписать в inventory.ini три публичных IP из `terraform output`
# (frontend_public_ip / backend_public_ip / worker_public_ip)

cp group_vars/all/secrets.yml.example group_vars/all/secrets.yml
# заполнить реальными значениями: db_host, db_password, admin_api_key,
# s3_bucket_name, sns_topic_arn, backend_private_ip, worker_private_ip
# (всё это тоже из `terraform output` / terraform.tfvars)

cd ..  # обратно в корень репозитория
docker run --rm -it \
  -v "$(pwd):/ansible" \
  -v "$HOME/.ssh:/root/.ssh:ro" \
  -w /ansible/ansible \
  miklat-ansible bash
```

Внутри контейнера (один раз за сессию — разблокировать SSH-ключ, если он с passphrase):

```bash
eval "$(ssh-agent -s)"
ssh-add /root/.ssh/miklat-devops

ansible-playbook playbooks/base.yml
ansible-playbook playbooks/nginx.yml
ansible-playbook playbooks/deploy-backend.yml
ansible-playbook playbooks/deploy-worker.yml
```

После всех четырёх — открыть `http://<frontend_public_ip>/` в браузере, должно показать то же самое
приложение, что и `docker compose up` в Фазе 1, только теперь на реальной AWS-инфраструктуре.

### Проверено

`ansible-playbook --syntax-check` для всех 4 плейбуков — без ошибок (сначала была одна ошибка —
предупреждение "Found both group and host with same name" из-за алиасов в inventory, исправлено на прямые
IP). Все Jinja2-шаблоны (`.env.j2`, systemd-юниты, nginx-конфиг) распарсены `jinja2.Environment().parse()`
без синтаксических ошибок. Реальный прогон плейбуков на настоящих EC2 — следующий шаг, у Claude нет SSH-
доступа к серверам пользователя (тот же принцип, что и с git push/terraform apply).

## Kubernetes (Задание 3)

Весь код — в `k8s/`. То же приложение, что и в Фазах 1-2, развёрнуто на **self-hosted k3s**
(единственная нода, VPS `mbdai`, namespace `miklat-app`) — не EKS, поэтому часть решений (IAM-доступ,
Ingress, single-node сторедж) продиктована именно этим ограничением и явно объясняется ниже.

`mbdai` — тот же физический сервер, на котором уже работает реальный продакшен `shelternearyou.online`
(отдельный Docker Compose стек). k3s установлен изолированно от него: свои порты (см. таблицу занятых
портов ниже), свой namespace, никакие ресурсы прод-стека не создаются/не изменяются кластером.

Диаграмма архитектуры (namespace/Deployment/Service/Ingress, границы public/private) — `docs/architecture-task3.md`
(mermaid, рендерится нативно на GitHub) или `docs/architecture-task3.png`.

### Файлы (`k8s/`)

| Файл | Что содержит |
|---|---|
| `00-namespace.yaml` | Namespace `miklat-app` |
| `01-configmap.yaml` | Несекретная конфигурация — `AWS_REGION`, URL'ы пяти сервисов, `OSRM_BASE_URL` |
| `02-secret.example.yaml` | Шаблон Secret'а (без значений) — реальный создаётся императивно, см. "Secrets" ниже |
| `03-ingress-nginx-controller.yaml` | Официальный bare-metal манифест ingress-nginx `controller-v1.15.1`, без изменений кроме явных `nodePort` |
| `04-ingress.yaml` | Единственное правило маршрутизации: `/` → `frontend:8080` |
| `05-serviceaccounts.yaml` | 3 ServiceAccount (по одному на группу сервисов) — см. "Security" ниже |
| `10-osrm.yaml` | Deployment+Service стороннего образа OSRM (пеший граф Израиля/Палестины) |
| `11-miklat-service.yaml` … `17-frontend.yaml` | По одному Deployment+Service на каждый из 7 собственных сервисов |

Нумерация файлов задаёт порядок применения (`00` → `01` → … → `17`) — зависимости (например, `osrm`
раньше `miklat-routes`/`miklat-walking-routes`) выдерживаются просто порядком имён.

### Образы: сборка и публикация (GHCR)

Все 7 Dockerfile'ов унаследованы из Фазы 1 без изменений — уже соответствовали требованиям задания:
фиксированные базовые образы без `latest` (`python:3.12-slim`, `nginx:1.27-alpine`), non-root пользователь
(`USER miklat`/`USER nginx`), `.dockerignore` исключает `.venv`/`.env`/`tests`/`__pycache__`.

```bash
# тег = короткий commit-SHA текущего HEAD, не latest
TAG=$(git rev-parse --short HEAD)
docker login ghcr.io -u <github-username>

for svc in frontend miklat-gateway miklat-service miklat-comments \
           miklat-routes miklat-walking-routes miklat-photos; do
  docker build -t ghcr.io/<github-username>/$svc:$TAG ./services/$svc   # frontend — из ./frontend
  docker push ghcr.io/<github-username>/$svc:$TAG
done
```

Пакеты в GHCR — **публичные** (Package settings → Danger Zone → Change visibility → Public) — осознанное
решение: Deployment'ам не нужны `imagePullSecrets`, что проще для self-hosted k3s без внешнего secret-
менеджера; Jenkins в Задании 4 при этом всё равно публикует туда через свой собственный токен.

### Развёртывание

```bash
# на mbdai, из корня репозитория
sudo k3s kubectl apply -f k8s/00-namespace.yaml -f k8s/01-configmap.yaml -f k8s/05-serviceaccounts.yaml

# Secret создаётся ИМПЕРАТИВНО, не из файла — см. "Secrets management" ниже
sudo k3s kubectl create secret generic miklat-secrets -n miklat-app \
  --from-literal=DATABASE_URL='postgresql://...' \
  --from-literal=ADMIN_API_KEY='...' \
  --from-literal=AWS_ACCESS_KEY_ID='...' \
  --from-literal=AWS_SECRET_ACCESS_KEY='...' \
  --from-literal=SNS_TOPIC_ARN='arn:aws:sns:...' \
  --from-literal=S3_BUCKET_NAME='...'

sudo k3s kubectl apply -f k8s/10-osrm.yaml \
  -f k8s/11-miklat-service.yaml -f k8s/12-miklat-comments.yaml \
  -f k8s/13-miklat-routes.yaml -f k8s/14-miklat-walking-routes.yaml \
  -f k8s/15-miklat-photos.yaml -f k8s/16-miklat-gateway.yaml \
  -f k8s/17-frontend.yaml

sudo k3s kubectl apply -f k8s/03-ingress-nginx-controller.yaml
sudo k3s kubectl apply -f k8s/04-ingress.yaml
```

Проверка:

```bash
sudo k3s kubectl get pods -n miklat-app          # все 8 — 1/1 Running
sudo k3s kubectl get pods -n ingress-nginx        # controller — 1/1 Running
sudo k3s kubectl get ingress -n miklat-app        # miklat-ingress, класс nginx

curl http://localhost:30080/                      # HTML фронтенда
curl "http://localhost:30080/api/miklats?limit=3" # реальные сид-данные через Ingress→frontend→gateway→service
```

Удаление:

```bash
sudo k3s kubectl delete namespace miklat-app ingress-nginx
```

### Подключение к RDS/S3/SNS

Приложение обращается к тем же самым AWS RDS/S3/SNS, которые созданы Terraform в Задании 2 (регион
`il-central-1`, ресурсы с суффиксом `-tf`) — никакой отдельной инфраструктуры под Kubernetes не заводилось.

RDS изначально создавался с `publicly_accessible = false` (Задание 2, приложение внутри VPC). Так как
`mbdai` — VPS вне VPC, для доступа снаружи пришлось (а) добавить в `aws_security_group.rds` отдельное
CIDR-правило на публичный IP `mbdai` и (б) переключить `publicly_accessible` на `true` — без этого DNS-имя
RDS резолвится только в приватный IP, физически недостижимый снаружи VPC никаким SG-правилом. Реальная
защита осталась на security group (сужена до конкретных SG изнутри VPC + один `/32` снаружи, не
`0.0.0.0/0`).

k3s работает вне AWS — значит, недоступен IRSA (IAM Roles for Service Accounts), которым в EKS обычно
решают доступ подов к S3/SNS без статических ключей. Вместо этого создан отдельный ограниченный
IAM-пользователь `miklat-k8s` (только `s3:PutObject/GetObject/DeleteObject/ListBucket` на бакет фото,
`sns:Publish/GetTopicAttributes` на топик уведомлений) со статическим access key — компромисс, прямо
предусмотренный заданием для не-EKS кластеров, задокументирован здесь и в `miklat-secrets` ниже.

### Security

#### Разделение прав / ServiceAccount (`05-serviceaccounts.yaml`)

Три ServiceAccount — по одному на логическую группу сервисов (`miklat-frontend-sa`, `miklat-backend-sa`,
`miklat-worker-sa`), та же группировка, что и в security groups Terraform Задания 2. Ни один из 8
workload'ов не привязан к `default` ServiceAccount namespace'а.

#### RBAC

Ни один из 8 сервисов проекта не обращается к Kubernetes API изнутри пода — все они обычные HTTP-сервисы
(FastAPI/nginx/OSRM), которые общаются друг с другом и с внешними AWS/RDS, а не с control plane кластера.
Поэтому «минимальные права» здесь означают буквально **ноль прав к API**, а не урезанный, но ненулевой
набор `verbs`/`resources`:

- на каждом ServiceAccount выставлен `automountServiceAccountToken: false` — под даже не получает токен
  для обращения к API-серверу (это сильнее, чем просто ограничить права токеном — сама возможность
  запроса исключена);
- ни один из трёх ServiceAccount не привязан ни к одной Role/ClusterRole — RoleBinding с реальными правами
  сознательно не создавались, т.к. создавать Role, права которой ничем не используются, противоречило бы
  самому принципу наименьших привилегий;
- `cluster-admin` или любая другая широкая роль нигде в проекте не используется.

Разделение на 3 ServiceAccount при этом остаётся осмысленным даже без явных прав — это чёткая идентичность
в `kubectl describe pod`/аудит-логах (видно принадлежность к группе не только по лейблу) и готовый задел:
если в будущем какой-то группе понадобится точечный доступ к API, у неё уже есть отдельная идентичность,
к которой можно привязать Role, не трогая остальные две группы.

#### Secrets management

Секреты (пароль RDS, `ADMIN_API_KEY`, access key/secret IAM-пользователя `miklat-k8s`, SNS ARN, имя S3-
бакета) хранятся как стандартный Kubernetes `Secret` (`Opaque`, 6 ключей), подставляются в переменные
окружения контейнеров точечно через `secretKeyRef` (не бланкетным `envFrom` — уже сама эта деталь сужает,
какие переменные видит каждый под). В Git — только `k8s/02-secret.example.yaml` с плейсхолдерами; реальный
Secret создаётся императивной командой `kubectl create secret generic --from-literal=...` прямо на
`mbdai` и никогда не существовал в виде файла на диске.

Это базовый уровень (K8s Secret), без внешнего secret-менеджера (бонус External Secrets Operator/AWS
Secrets Manager сознательно не делался — за пределами обязательного минимума задания).

#### Network security

Схема обращений: `frontend` (единственный, кто виден снаружи, через Ingress) → `miklat-gateway` →
{`miklat-service`, `miklat-comments`, `miklat-routes`, `miklat-walking-routes`, `miklat-photos`}; сервисы
worker-группы дополнительно обращаются к RDS/S3/SNS напрямую (не через шлюз); `miklat-routes`/
`miklat-walking-routes` — к `osrm`. Все Service, кроме `frontend`, — `ClusterIP` без внешнего доступа;
единственная внешняя точка входа в кластер — `Ingress` → `frontend:8080` на `NodePort 30080`/`30443`.

`NetworkPolicy` (бонус) сознательно не реализован в этой итерации: k3s по умолчанию ставится с CNI
`flannel`, который манифесты `NetworkPolicy` принимает, но **не enforce'ит** (не блокирует трафик по ним
реально) — для настоящего эффекта потребовалась бы замена CNI на Calico/Canal, это более крупное изменение
кластера, оставлено как возможное дальнейшее улучшение. Базовая сегрегация трафика на сегодня обеспечена
структурно — типом Service (`ClusterIP` vs единственный `Ingress`), а не netfilter-правилами.

#### Container security

У всех 8 подов: `allowPrivilegeEscalation: false` и `capabilities: drop: ["ALL"]` на уровне контейнера. У
7 собственных сервисов (не OSRM) — `runAsNonRoot: true` на уровне пода: 5 python-сервисов с явным
`runAsUser: 10001` (совпадает с `useradd --uid 10001` в их Dockerfile), `frontend` — с `runAsUser: 101`
(стандартный UID пользователя `nginx` во всех вариантах официального образа `nginx:*-alpine`, задан самим
образом). Единственное исключение — `osrm`: сторонний официальный образ `ghcr.io/project-osrm/osrm-backend`
работает от root и не предоставляет непривилегированного пользователя, Dockerfile не наш — задокументировано
как ограничение, а не забытая деталь. У всех 8 — `resources.requests/limits` и `readinessProbe`/
`livenessProbe`.

#### Image security

Собственные Dockerfile на все 7 сервисов (не сторонние базовые образы "как есть"), фиксированные теги —
короткий commit-SHA текущего HEAD, `latest` нигде не используется (в т.ч. и у `osrm`, где используется
тег по умолчанию, но не обновляется без явного пересмотра — образ сторонний и не пересобирается). Сканиро-
вание образов через Trivy (бонус) в этой итерации не делалось — оставлено как возможное дальнейшее
улучшение, самый простой способ добавить: `trivy image ghcr.io/<user>/<service>:<tag>` на каждый из 7
образов, вывод — в `docs/evidence/task3/`.

#### Ingress security

Ingress пока обслуживает только HTTP (без TLS) — домен ещё не выбран, cert-manager + Let's Encrypt (бонус)
осознанно отложены на финальный этап проекта, когда появится реальный поддомен (тот же принцип, что и
отложенное решение проблемы Geolocation API без HTTPS во фронтенде, см. журнал Фазы 2). Публикация — через
`NodePort 30080`/`30443` вместо стандартных `80`/`443`: эти два порта уже заняты продакшен-nginx на том же
физическом сервере `mbdai` — задокументированный компромисс, а не забытая деталь (аналог решения "без NAT
Gateway" в Terraform Задания 2). Разделение public/internal трафика: наружу открыт только `frontend` через
`Ingress`, все остальные 7 сервисов — только `ClusterIP`, недостижимы снаружи кластера в принципе.

### Известные компромиссы (trade-offs)

- **Self-hosted k3s, не EKS** — отсюда отсутствие IRSA (статический IAM-пользователь `miklat-k8s` вместо
  роли) и отсутствие облачного LoadBalancer (Ingress через `NodePort`).
- **Single-node кластер** — данные графа OSRM (~890 МБ) подключены через `hostPath`, а не сетевой
  `PersistentVolume`: под физически не может мигрировать на другую ноду, которой попросту нет.
- **ingress-nginx (`kubernetes/ingress-nginx`) заархивирован апстримом** 24.03.2026 (подтверждено веб-
  поиском) — выбран сознательно, пин на последний стабильный релиз `controller-v1.15.1`: задание требует
  лишь «nginx ingress controller», выпущенные артефакты остаются полностью рабочими.
- **`mbdai` — общий сервер с реальным продакшеном** `shelternearyou.online` (отдельный Docker Compose
  стек) — весь Kubernetes-стенд изолирован от него по портам/namespace и ни разу не затрагивал его
  ресурсы, включая при отдельном инфраструктурном инциденте с нехваткой памяти на хосте (см. `miklat-
  progress.md`), устранённом без какого-либо вмешательства в прод.
- **NetworkPolicy, Trivy-скан, cert-manager+TLS** — три официальных бонуса задания, сознательно не
  реализованы в этой итерации (см. обоснование в соответствующих Security-подразделах выше), оставлены
  как возможные дальнейшие улучшения.

## Jenkins CI/CD (Задание 4)

Jenkins развёрнут в том же k3s-кластере на `mbdai`, в отдельном namespace `jenkins` (не `miklat-app`). Весь Jenkins — как код: Helm chart с зафиксированной версией, JCasC и Job DSL создают контроллер, agent pod template'ы и оба job'а (`miklat-ci`/`miklat-cd`) без единой ручной настройки через UI.

Диаграммы (Deployment View + Pipeline Flow) — задел на шаг 8, здесь пока текстовое описание.

### Файлы (`jenkins/`)

| Файл | Что содержит |
|---|---|
| `values.yaml` | Helm values для чарта `jenkinsci/jenkins` (`5.9.29`): контроллер (образ, PVC, resources/probes, securityContext, JCasC), `agent.podTemplates` (`ci-agent`, `cd-agent`), `configScripts` (`basic-settings`, `seed-jobs` — Job DSL) |
| `cd-rbac.yaml` | `ServiceAccount jenkins-cd` (namespace `jenkins`) + `Role`/`RoleBinding` в namespace `miklat-app` |
| `network-policy.yaml` | 6 объектов `NetworkPolicy` для namespace `jenkins` (см. Security ниже) |
| `scripts/install-jenkins.sh` | `helm repo add/update` + идемпотентный `helm install`/`upgrade` |
| `scripts/configure-jenkins.sh` | создание `jenkins-admin-secret` (пароль нигде не пишется на диск/в лог) |
| `scripts/create-jobs.sh` | форс JCasC reload + проверка, что оба job'а реально созданы |
| `scripts/verify-jenkins.sh` | комплексная проверка: под/PVC, HTTP `/login`, оба job'а, pod-template'ы облака |

`Jenkinsfile-ci`/`Jenkinsfile-cd` лежат в корне репозитория — Job DSL ссылается на них через `scriptPath`, Jenkins подтягивает их из git заново при каждом запуске (правки не требуют переустановки чарта).

### Jenkins-контроллер

Namespace `jenkins`, официальный Helm chart `jenkinsci/jenkins`, версия чарта зафиксирована (`5.9.29`), образ контроллера — `jenkins/jenkins:2.555.3-lts-jdk21` (LTS, без `latest`-алиасов). PVC 8Gi (`local-path`), `runAsNonRoot`/`allowPrivilegeEscalation: false`, resources requests/limits, startup/liveness/readiness пробы на `/login`. `numExecutors: 0` — контроллер сам ничего не собирает, только диспетчер; вся реальная работа — на ephemeral agent-подах.

### Agent pod template'ы

- **`ci-agent`** — 4 контейнера: `git` (checkout), `python-tools`/`python:3.12-slim` (lint/тесты backend), `node-tools`/`node:22-slim` (lint/сборка frontend), `kaniko`/`gcr.io/kaniko-project/executor:v1.23.2-debug` (сборка и push образов без Docker socket, `privileged: false`).
- **`cd-agent`** — контейнер `kubectl-helm`/`dtzar/helm-kubectl:4.2.3`, работает под выделенным `ServiceAccount jenkins-cd` (в отличие от `ci-agent`, который использует дефолтный `jenkins` SA).

Оба template'а — `podRetention: Never` (ephemeral workspace, ничего не переживает между сборками).

### Jobs как код

Плагин `job-dsl` + JCasC-ключ `jobs:` (`configScripts.seed-jobs`) создают `miklat-ci` и `miklat-cd` автоматически при каждом старте/reload контроллера. `miklat-cd` параметризован тремя параметрами: `SERVICE_NAME` (`choiceParam`, выпадающий список из 7 сервисов — необходимое уточнение сверх буквальной формулировки задания, без него по одному только commit-SHA невозможно определить, какой именно `Deployment`/ключ `values.yaml` обновлять при параллельных изменениях нескольких сервисов), `IMAGE_TAG`, `IMAGE_DIGEST`.

### `Jenkinsfile-ci` — этапы

`Checkout` → `Validate` (структура сервисов + Dockerfile) → `Lint` (параллельно: `ruff` с запиненной версией + явным `--select`, `oxlint`) → `Tests` (параллельно: `pytest` по сервисам без живой БД, `npm run build`) → `Detect changed services` (`git diff` по префиксам путей) → `Build & push (kaniko)` (только изменившиеся сервисы, тег = commit-SHA, push в GHCR) → `Publish metadata` (архивирует тег+digest) → `Trigger CD` (запускает `miklat-cd` для каждого изменившегося сервиса, см. ниже).

Триггер — GitHub webhook (`githubPush()`), путь `/github-webhook/` через уже существующий публичный Ingress, с проверкой HMAC-подписи (`X-Hub-Signature-256`) по секрету `github-webhook-secret` — единственный путь Jenkins, открытый наружу (см. Security ниже).

### `Jenkinsfile-cd` — этапы

`Validate parameters` → `Validate manifests` (`helm lint` + `helm upgrade --install --dry-run=client`) → `Authenticate` (`kubectl auth can-i`) → `Deploy` (`helm upgrade --install --reuse-values --set <key>.imageTag=<TAG> --wait`) → `Rollout status` → `Verify Pods/Services` → `Smoke test` (реальный `curl` изнутри уже существующего контейнера `kubectl-helm`); `post { failure { helm rollback <RELEASE> 0 } }` — явный откат на предыдущую ревизию при любом сбое, проверенный намеренным прогоном с несуществующим тегом образа (см. `miklat-progress.md`, шаг 5).

Деплой идёт через `helm/miklat-app/` — существующие манифесты `k8s/` обёрнуты в настоящий Helm-чарт (архитектурное решение шага 5, согласовано с пользователем: буквальная формулировка задания требует `helm upgrade --install`, а исходное приложение из Задания 3 было развёрнуто плоскими `kubectl apply`-манифестами).

### Связка CI → CD

Стадия `Trigger CD` в `Jenkinsfile-ci` вызывает `build job: 'miklat-cd', parameters: [...], wait: false` — по одному вызову на каждый сервис из `CHANGED_SERVICES`, с параметрами `SERVICE_NAME`/`IMAGE_TAG=GIT_SHA`/`IMAGE_DIGEST`, считанными из того же файла, что уже публикует `Publish metadata`. `wait: false` — осознанное решение по принципу CI/CD separation (CI считает себя завершённым, как только образ собран и job деплоя поставлен в очередь; длительность и результат самого деплоя, включая возможный `helm rollback`, не должны влиять на длительность/статус CI). Плагин `pipeline-build-step` (даёт сам шаг `build`) не добавлялся отдельно — подтверждено как транзитивная зависимость уже установленного по умолчанию `workflow-aggregator`.

Реальный сквозной прогон подтверждён (см. `miklat-progress.md`, шаг 6): канареечный коммит в `services/miklat-photos/` → webhook → `miklat-ci` собрал и запушил образ, стадия `Trigger CD` поставила `miklat-cd` в очередь → `miklat-cd` запустился автоматически (`Started by upstream project "miklat-ci"`) с правильными параметрами → полный деплой с тем же самым тегом образа, что собрал CI, Smoke-test `HTTP 200`.

### Как развернуть

```bash
# на mbdai, из корня репозитория
./jenkins/scripts/configure-jenkins.sh   # один раз — создать jenkins-admin-secret
./jenkins/scripts/install-jenkins.sh     # helm install/upgrade jenkins (идемпотентно)
./jenkins/scripts/create-jobs.sh         # форс JCasC reload, если job'ы не создались сами
./jenkins/scripts/verify-jenkins.sh      # под/PVC/HTTP/job'ы/pod-template'ы одной командой
```

Доступ к UI — только через `kubectl port-forward -n jenkins svc/jenkins 8090:8080` (см. Security ниже, наружу Jenkins UI не публикуется). GitHub webhook настраивается на `https://<домен или IP mbdai>/github-webhook/` (репозиторий → Settings → Webhooks), секрет — тот же, что в Jenkins credential `github-webhook-secret`.

Удаление:

```bash
helm uninstall jenkins -n jenkins
kubectl delete namespace jenkins
```

### Security

#### RBAC

Два разных `ServiceAccount`, оба **без `cluster-admin`** и без единой `ClusterRole`:

- **`jenkins`** (дефолтный SA чарта, namespace `jenkins`) — используется и самим контроллером, и `ci-agent` (для `ci-agent` явно не переопределялся). Реально подтверждено на живом кластере (`kubectl auth can-i`, а не предположение):
  - `kubectl auth can-i create deployments --all-namespaces --as=system:serviceaccount:jenkins:jenkins` → `no`;
  - `kubectl auth can-i create deployments -n miklat-app --as=...` → `no`;
  - `--list` в **своём** namespace `jenkins` показывает реальные, но узкие права: `pods` (включая `exec`) и `persistentvolumeclaims` (полный CRUD — нужно самому Kubernetes-плагину, чтобы порождать/удалять agent-поды и их PVC), `configmaps`/`events`/`pods/log` (read-only) — ни `secrets`, ни `deployments`, ни `services` там нет;
  - `--list` в namespace `miklat-app` — пусто (только универсальные `selfsubject*`, которые есть у любого аутентифицированного субъекта).

  Итог: `miklat-ci` физически не может создать/изменить ни один `Deployment`/`Secret`/`Service` нигде в кластере — ни в своём namespace, ни тем более в `miklat-app`.

- **`jenkins-cd`** (`jenkins/cd-rbac.yaml`, шаг 5) — namespace `jenkins` (там же работает `cd-agent`), с `RoleBinding` в `miklat-app` (кросс-namespace, без `ClusterRole`). Реально подтверждено:
  - `--list` в `miklat-app` — полный CRUD ровно на то, чем управляет Helm-чарт приложения: `configmaps`/`events`/`secrets`/`serviceaccounts`/`services`/`deployments.apps`/`replicasets.apps`/`ingresses.networking.k8s.io`, плюс read-only `pods`/`pods/log`;
  - `--list` в **своём** namespace `jenkins` — пусто (только `selfsubject*`) — `jenkins-cd` физически живёт в `jenkins`, но не имеет там ни единого права, все его реальные права — исключительно кросс-namespace в `miklat-app`.

  `secrets` включены в правила вынужденно, не по недосмотру: Helm 3 хранит историю релизов как собственные `Secret` в ТОМ ЖЕ namespace, куда деплоит чарт — значит, любой `ServiceAccount`, способный выполнять `helm upgrade --install`, неизбежно может читать/писать любые `Secret` в `miklat-app`, включая `miklat-secrets` (пароль RDS, admin-ключ, AWS-креды приложения). Задокументированный компромисс, не расширение прав сверх необходимого.

#### Secrets и маскирование в логах

Три независимых механизма, ни один не пересекается с другими:

- **Jenkins Credentials** (`Manage Jenkins → Credentials`, реально проверено в UI — ровно 2 объекта, лишних нет): `ghcr-credentials` (Username with password — classic PAT с scope `write:packages`; fine-grained PAT не подошёл — GitHub на момент написания не поддерживает fine-grained-токены для push в GHCR-пакеты) — используется в `Jenkinsfile-ci` через `withCredentials` для аутентификации kaniko в registry; `github-webhook-secret` (Secret text) — используется плагином `github` для проверки `X-Hub-Signature-256` на входящих вебхуках. Маскирование подтверждено реальным Console Output: `Masking supported pattern matches of $REG_PASS` — Jenkins автоматически вычищает значение credential'а из любого вывода `sh`-шага, в который оно было передано через `withCredentials`.
- **Kubernetes Secrets** — `miklat-secrets` (namespace `miklat-app`, секреты ПРИЛОЖЕНИЯ: пароль RDS, `ADMIN_API_KEY`, AWS-креды, SNS ARN, S3 bucket — созданы ещё в Задании 3, `Jenkinsfile-cd` их не читает и не выводит, они попадают в поды приложения напрямую через `secretKeyRef` в Helm-чарте) и `jenkins-admin-secret` (namespace `jenkins`, логин/пароль администратора Jenkins UI — создан императивно, никогда не существовал как файл на диске и не является Jenkins Credential).
- **ServiceAccount token / kubeconfig** — `cd-agent` не использует и никогда не создавал отдельный файл kubeconfig: под работает под `ServiceAccount jenkins-cd`, токен которого `kubectl`/`helm` подхватывают автоматически через in-cluster config (стандартный механизм монтирования токена в `/var/run/secrets/kubernetes.io/serviceaccount/`) — нечего хранить и нечего утечь отдельным файлом.

Ни в `Jenkinsfile-ci`/`Jenkinsfile-cd`, ни в `jenkins/values.yaml` не встречается ни одного секретного значения в открытом виде — только имена/ID credential'ов и Secret'ов.

#### Jenkins UI/API не публикуется наружу

Реально подтверждено (не просто заявлено) прямым сравнением заголовков и `<title>` через тот же публичный вход (`NodePort 30080`), которым пользуется GitHub webhook:

```
curl -sI http://localhost:30080/login   → HTTP 200, БЕЗ заголовка X-Jenkins
curl -sI http://localhost:30080/manage  → HTTP 200, БЕЗ заголовка X-Jenkins
curl -s   http://localhost:30080/login  | title → "ShelterNearYou · miklat-devops" (фронтенд приложения, не Jenkins)
curl -sI http://localhost:30080/github-webhook/ → HTTP 405, X-Jenkins: 2.555.3
```

`/login` и `/manage` формально отвечают `200`, но это ответ SPA-фронтенда приложения (client-side routing отдаёт `index.html` на любой неизвестный путь) — оба Ingress-объекта (`jenkins-webhook-ingress` в `jenkins`, `miklat-ingress` в `miklat-app`) не задают `host`, поэтому nginx ingress controller сливает их правила в общий набор для одного и того же входа: путь `/github-webhook/` уходит в Jenkins, всё остальное — на `frontend`. Реально в Jenkins попадает (подтверждено заголовком `X-Jenkins`) только один путь. Единственный способ достучаться до настоящего Jenkins UI — `kubectl port-forward`, доступный лишь тому, у кого уже есть `kubectl`-доступ к кластеру (то есть уже прошедшему через RBAC/SSH-периметр сервера).

#### NetworkPolicy (`jenkins/network-policy.yaml`)

6 объектов `NetworkPolicy` на namespace `jenkins`, применены на кластере: `default-deny-all` (baseline — запрет всего ingress/egress по умолчанию для всех подов namespace), `allow-dns-egress` (все поды → CoreDNS в `kube-system`), `allow-controller-ingress` (к контроллеру — только из `ingress-nginx` на 8080, и от agent-подов на 50000/JNLP), `allow-controller-egress` (контроллер → k8s API-сервер на `6443` — нужно Kubernetes-плагину для управления agent-подами — и HTTPS-443 в интернет для Update Center), `allow-agent-egress-common` (любой agent-под → JNLP-туннель к контроллеру + HTTPS-443 в интернет — git/kaniko/npm/pip), `allow-cd-agent-egress` (только `cd-agent`, не `ci-agent` — доступ к k8s API-серверу и к namespace `miklat-app` на портах 8000/8080 для Smoke-test).

Прикладной эффект правил при реальном enforcement: `ci-agent` не имел бы сетевого маршрута ни к k8s API-серверу, ни к namespace `miklat-app` — второй, независимый от RBAC слой того же ограничения, что уже доказано выше через `kubectl auth can-i`.

**Важная оговорка, подтверждённая реально, а не предположенная:** k3s на `mbdai` работает на дефолтном CNI `flannel`, который **не enforce'ит** `NetworkPolicy` (тот же технический факт, что уже задокументирован в Задании 3 для namespace `miklat-app`) — манифесты применились на кластер без единой ошибки и без единого побочного эффекта (webhook/прод/поды — все проверены до и после apply), но физически ни один из описанных выше запретов сейчас не блокируется. Единственный реально работающий механизм ограничения на этом кластере — RBAC. Манифесты — готовая, синтаксически и семантически корректная основа: начнут реально применяться без единой правки, если CNI когда-нибудь заменят на Calico/Canal.

### Известные компромиссы (trade-offs)

- **`k8s/` обёрнут в Helm-чарт (`helm/miklat-app/`) специально ради `Jenkinsfile-cd`** — исходное приложение (Задание 3) было развёрнуто плоскими `kubectl apply`-манифестами; буквальная формулировка задания требует `helm upgrade --install`, поэтому существующие ресурсы мигрированы под управление Helm (`migrate-to-helm.sh`, аннотации/лейблы, без даунтайма) — решение согласовано с пользователем явным вопросом.
- **`Role miklat-cd-deployer` включает полный доступ к `secrets` в `miklat-app`** — не расширение прав, а неизбежное следствие того, что Helm 3 хранит историю релизов как собственные `Secret` в namespace деплоя (см. RBAC выше) — задокументированный, а не забытый компромисс.
- **`NetworkPolicy` написан и применён, но не enforce'ится** текущим CNI (`flannel`) — та же техническая причина, что и в Задании 3, только там пункт был помечен планом как бонус и сознательно отложен, а здесь (формально не бонус) манифест всё равно реализован — как готовая, но пока не действующая основа.
- **Classic PAT вместо fine-grained** для `ghcr-credentials` — на момент написания GitHub не поддерживает fine-grained-токены для push в GHCR-пакеты; scope сужен до `write:packages`, токен привязан к отдельному, не личному GitHub-аккаунту использования (тот же PAT, что и при ручной публикации образов в Задании 3).
- **Jenkins UI/API полностью закрыт снаружи**, доступ только через `kubectl port-forward` — сознательное решение до конца проекта (не промежуточный шаг): на том же физическом сервере `mbdai` работает реальный прод `shelternearyou.online`, публиковать ещё один административный интерфейс наружу без явной необходимости — не оправданный риск.

## Kubernetes: Мониторинг (Задание 5)

Prometheus + Grafana развёрнуты в том же k3s-кластере на `mbdai`, в отдельном namespace `observability` (не `miklat-app`, не `jenkins`) — чартом `kube-prometheus-stack` (`88.6.3`, appVersion `v0.93.1`, версия зафиксирована явно). Весь слой — как код: Helm values в Git, ServiceMonitor/PodMonitor/PrometheusRule/дашборды — манифесты, ничего не создавалось руками через UI Grafana/Prometheus.

Диаграмма (Prometheus/Grafana/Alertmanager, потоки discovery/scrape, интеграция с CD) — `docs/architecture-task5.md` (mermaid, рендерится нативно на GitHub) или `docs/task5-monitoring.png`.

### Файлы (`monitoring/`)

| Файл/папка | Что содержит |
|---|---|
| `values-kube-prometheus-stack.yaml` | Helm values чарта `kube-prometheus-stack`: Prometheus (PVC 5Gi, retention 7d, resources), Grafana (без персистентности — дашборды/датасорсы как код), Alertmanager (demo-receiver), `defaultRules.create: false`/`grafana.defaultDashboardsEnabled: false` (свои алерты/дашборды вместо чартовых), `*SelectorNilUsesHelmValues: false` (discovery ServiceMonitor/PodMonitor/PrometheusRule по всем namespace) |
| `service-monitors/miklat-app-services.yaml` | `ServiceMonitor` на 7 портов приложения — 6 backend (`targetPort: 8000`) + `frontend` (именованный порт `metrics`, добавлен 04.09.2026) (`namespace: miklat-app`, 15s interval) |
| `slo-recording-rules.yaml` | `PrometheusRule` (recording): 9 правил, 2 группы — availability и latency (см. SLI/SLO ниже) |
| `alerts/miklat-alerts.yaml` | `PrometheusRule` (alerting): 6 алертов, 4 группы (см. ниже) |
| `dashboards/application-overview.yaml`, `dashboards/kubernetes-cluster.yaml`, `dashboards/jenkins-delivery.yaml` | 3 обязательных дашборда — каждый `ConfigMap` (лейбл `grafana_dashboard: "1"`) с вложенным JSON |
| `network-policy.yaml` | 12 объектов `NetworkPolicy` для namespace `observability` (см. Security ниже) |
| `slo-queries.md` | Полная документация SLI/SLO: определения, пороги, PromQL, команды ручной проверки |

ServiceMonitor для самого Jenkins отдельным файлом не создавался — он создаётся автоматически самим Helm-чартом `jenkins/jenkins` при `controller.prometheus.enabled=true` (см. Задание 4, `jenkins/values.yaml`), с эндпоинтом `/prometheus`.

Дополнительно (интеграция с CI/CD, Задание 4 файлы обновлены, не пересозданы): `ci/validate_monitoring.py` (новый), `Jenkinsfile-ci` (новая стадия `Validate monitoring manifests`), `Jenkinsfile-cd` (новая стадия `Monitoring health gate`), `jenkins/network-policy.yaml` (добавлено правило egress для `cd-agent` → `observability`). А также `runbooks/*.md` — 6 файлов, по одному на каждый алерт (см. ниже).

Позже, при добавлении метрик frontend (04.09.2026): `helm/miklat-app/templates/frontend.yaml` (добавлен sidecar-контейнер `nginx-prometheus-exporter`), `Jenkinsfile-ci` (исправлена логика детектора изменившихся сервисов — см. находки ниже), `Jenkinsfile-cd` (health-gate расширен на `frontend`), `monitoring/network-policy.yaml` (добавлен порт `9113` в `allow-prometheus-egress` — см. находки ниже).

### Что мониторится

| Источник | Как собирается | Что видно |
|---|---|---|
| Приложение (7 сервисов) | `/metrics` (`prometheus-fastapi-instrumentator`) + `ServiceMonitor` | `http_requests_total`, `http_request_duration_seconds`/`_highr_seconds`, `app_info{version,git_sha,release}`, 5 доменных бизнес-метрик (`miklat_routes_calculated_total` и т.п. — по одной у 5 из 6 backend-сервисов, `miklat-gateway` как чистый API-gateway — без своей) |
| Kubernetes (k3s) | `kube-state-metrics`, `node-exporter`, kubelet/cAdvisor | ноды, поды, ресурсы (CPU/memory/throttling), рестарты, `Deployment` replicas desired vs available, PVC usage |
| Jenkins | плагин `prometheus` (`/prometheus`) | очередь сборок, executors/agents по label, health score и результат последнего билда по job, uptime |

`frontend` (nginx) — метрики добавлены отдельным шагом в конце Фазы 5 (04.09.2026, после основного объёма работ по Заданию 5): sidecar-контейнер `nginx-prometheus-exporter:1.5.1` в том же поде читает `stub_status` (`frontend/nginx.conf`, `location /nginx_status`, доступ только с `127.0.0.1` — тот же под) и отдаёт `/metrics` в формате Prometheus на порту `9113`; `ServiceMonitor` (в отличие от 6 backend-сервисов) ссылается на порт по имени (`port: metrics`), т.к. Service `frontend` — единственный, кто именует свои порты (у него их два: `http`/`metrics`). Ни SLI/SLO, ни один из 6 обязательных алертов, ни 2 из 3 дашбордов на frontend по-прежнему не завязаны (SLO строится на API backend-сервисов) — метрики frontend дают только базовую видимость (`up`, счётчики соединений/запросов nginx), без прикладной латентности (см. ограничение `nginx-prometheus-exporter` ниже).

### Дашборды (Grafana)

Все три — provisioning через ConfigMap + Grafana sidecar (`grafana.sidecar.dashboards`, `searchNamespace: ALL`), не ручной import:

| Дашборд | uid | Панелей |
|---|---|---|
| Application Overview | `miklat-application-overview` | 11 (request rate/error rate/availability %/latency p50-95-99/5 бизнес-метрик/`app_info`-таблица/CPU+memory по подам/2 SLO-compliance панели) |
| Kubernetes / Cluster | `miklat-kubernetes-cluster` | 11 (node ready/pending pods/OOMKilled/disk usage/CPU+memory ноды/CPU throttling по подам/pods by phase/pod restarts/deployment replicas desired vs available/PVC usage) |
| Jenkins & Delivery | `miklat-jenkins-delivery` | 11 (scrape health/uptime/очередь/health score по job/результат последнего билда/время с последнего билда/длительность сборки/время ожидания в очереди/executors/nodes online/тренд CI-CD outcome) |

### SLI/SLO

Полная формула и обоснование порогов — `monitoring/slo-queries.md`. Кратко: два SLI — **availability** (доля запросов без `5xx` за 5 минут) и **latency** (p95 за 5 минут), с порогами **>= 98%** и **< 400мс** соответственно, подобранными по реальным измеренным данным (p95 у большинства сервисов 22-25мс, у более тяжёлых `miklat-service`/`miklat-photos` — 93-98мс; порог 400мс сознательно взят с запасом на случай замедления под нагрузкой). Обе метрики — `PrometheusRule` recording rules (`monitoring/slo-recording-rules.yaml`, группы `miklat.slo.availability`/`miklat.slo.latency`), а не сырой PromQL, продублированный в каждом дашборде/алерте/health-gate по отдельности — один источник истины, три потребителя (дашборд Application Overview, оба алерта `HighErrorRate`/`HighLatencyP95`, CD health-gate).

Отдельный технический нюанс, зафиксированный в комментариях файла: `sum(rate(http_requests_total{status="5xx"}[5m]))` возвращает **пустой** вектор (не `0`) при отсутствии ошибок — без явного `or (0 * ...)`-фолбэка job с нулём ошибок пропадал бы из availability-расчёта вместо честного отображения 100%.

### Алерты и runbook'и

6 алертов (`monitoring/alerts/miklat-alerts.yaml`, `PrometheusRule`, 4 группы), каждый — с `severity`, `summary`, `description` и `runbook_url` на реальный файл в `runbooks/`:

| Алерт | severity | Группа | Условие | Runbook |
|---|---|---|---|---|
| `HighErrorRate` | critical | application | availability < 98% на 5+ мин | `runbooks/high-error-rate.md` |
| `HighLatencyP95` | warning | application | p95 > 400мс на 5+ мин | `runbooks/high-latency-p95.md` |
| `ReplicasMismatch` | warning | kubernetes | available < desired реплик на 10+ мин | `runbooks/replicas-mismatch.md` |
| `NodeNotReadyOrPressure` | critical | kubernetes | нода не Ready или под ресурсным давлением 5+ мин | `runbooks/node-not-ready-or-pressure.md` |
| `JenkinsQueueStuck` | warning | jenkins | очередь сборок застряла/заблокирована 10+ мин | `runbooks/jenkins-queue-stuck.md` |
| `PrometheusTargetDown` | critical | monitoring | `up == 0` у любого из собственных компонентов 5+ мин | `runbooks/prometheus-target-down.md` |

Каждый `runbooks/*.md` — симптом → диагностика (реальные команды) → вероятные причины (специфичные для истории этого кластера) → устранение → ссылка на evidence будущих учений отказа (п.8, `docs/evidence/task5/`).

### CI/CD-интеграция

- **CI** (`Jenkinsfile-ci`, стадия `Validate monitoring manifests`, сразу после `Validate`): `ci/validate_monitoring.py` — статическая проверка схемы (без обращения к кластеру) `PrometheusRule`/`ServiceMonitor`/dashboard-`ConfigMap` — падает с понятной ошибкой на отсутствующем `runbook_url`, пустых `panels` и т.п. Сам деплой дашбордов/правил через CI не делается (Observability as Code — только `git → kubectl apply` вручную/на сервере).
- **CD** (`Jenkinsfile-cd`, стадия `Monitoring health gate`, после `Smoke test`): пауза 30с (2 цикла scrape), затем через Prometheus API проверяются `up{job=<service>}==1`, `job:http_request_availability:ratio5m >= 0.98`, `job:http_request_duration_highr_seconds:p95_5m < 0.4` — те же recording rules из SLI/SLO, без дублирования формул. Провал любой проверки — `error()`, автоматически запускающий уже существующий `post{failure}` `helm rollback` (новой rollback-логики не потребовалось). Для `frontend` (04.09.2026) стадия не пропускается, а сокращена: проверяется только `up{job="frontend"}==1` — recording rules availability/latency построены на гистограмме `http_request_duration_seconds` из `prometheus-fastapi-instrumentator`, которой у nginx-экспортёра нет (он отдаёт только счётчики соединений/запросов, без прикладной латентности запроса).

Реальный сквозной прогон подтверждён (`docs/evidence/task5/cd-health-gate-successful-run.txt`): билд `miklat-cd` для `miklat-gateway` прошёл health-gate с `up=1`, `availability=1` (100%), `p95≈23мс` — пайплайн завершился `SUCCESS`.

### Security

#### Exposure

Ни Prometheus, ни Grafana, ни Alertmanager не публикуются через Ingress — единственный доступ к UI/API всех трёх (в т.ч. для всех проверок в этом разделе) — `kubectl port-forward`, доступный только тому, у кого уже есть `kubectl`-доступ к кластеру. Это исключительно ручной инструмент для проверки/просмотра человеком — ни scrape, ни provisioning дашбордов, ни обработка алертов от него не зависят.

#### RBAC

Собственные `ServiceAccount` у компонентов стека, без `cluster-admin`. Prometheus Operator — единственный компонент, которому реально нужен доступ на чтение объектов кластера (для discovery `ServiceMonitor`/`PodMonitor`/`PrometheusRule` и управления `Alertmanager`/`Prometheus` CRD) — это осознанное отличие от Задания 3 (там RBAC у приложения был буквально нулевым), но по-прежнему без cluster-wide прав на запись за пределами своих CRD.

#### Secrets

Пароль администратора Grafana — Kubernetes `Secret` `grafana-admin-secret` (namespace `observability`, ключи `admin-user`/`admin-password`), подключён через `grafana.admin.existingSecret` в values — в Git не попадает, тот же паттерн, что и `jenkins-admin-secret` в Задании 4. Receiver Alertmanager — безопасный demo-вебхук (`https://httpbin.org/post`, просто логирует тело), не реальный продовый канал — сознательно, чтобы не заводить в репозитории реальные секреты нотификаций ради демонстрации самого механизма роутинга.

#### NetworkPolicy (`monitoring/network-policy.yaml`)

12 объектов на namespace `observability`: `default-deny-all` (baseline) + `allow-dns-egress` + отдельные ingress/egress-пары для `prometheus`/`alertmanager`/`grafana`/`kube-state-metrics`/`operator`, каждое правило — под один реально подтверждённый поток (включая admission webhook Prometheus Operator на 10250, отдельно протестированный созданием и удалением тестового `PrometheusRule`). Симметрично дополнен `jenkins/network-policy.yaml` (Задание 4) — egress `cd-agent → observability:9090` для CD health-gate.

В отличие от формулировки в разделе Security Задания 3/4 (там зафиксировано, что дефолтный CNI `flannel` NetworkPolicy не enforce'ит) — начиная с Фазы 5 подтверждено, что k3s на этом кластере реально enforce'ит `NetworkPolicy` через собственный встроенный контроллер (если явно не передан флаг `--disable-network-policy`; см. также инцидент с JNLP-портом Jenkins в Задании 4, где это было впервые обнаружено). Обе оговорки в предыдущих разделах README про "flannel не enforce'ит" на момент их написания были честной, но впоследствии опровергнутой находкой — актуальное состояние отражено здесь и будет приведено в соответствие в остальных разделах при переводе README (Фаза 6).

### Находки при внедрении метрик frontend (04.09.2026)

Обе находки — реальные, обнаруженные не при планировании, а по факту сбоя, с диагностикой и исправлением, применённым на кластере.

**1. Баг детектора изменившихся сервисов в CI при многокоммитных пушах (`Jenkinsfile-ci`).** Стадия `Detect changed services` сравнивала `git diff --name-only HEAD~1 HEAD` — то есть только последний коммит пуша со своим непосредственным родителем. При пуше из нескольких коммитов это могло молча пропустить сервис, если путь к нему менялся в одном из более ранних коммитов пуша, а не в последнем — ровно так был потерян билд `frontend/nginx.conf` в рамках этой же работы. Исправлено: базой для diff теперь служит `env.GIT_PREVIOUS_SUCCESSFUL_COMMIT` (переменная плагина Jenkins Git — SHA последнего успешного билда этого job'а), с фолбэком на `HEAD~1` (самый первый билд) и далее на «собрать все сервисы», если базовый коммит недостижим при shallow-клоне.

**2. `NetworkPolicy` в кластере реально enforce'ится — ещё одно, второе по счёту подтверждение (после инцидента с JNLP-портом Jenkins, Задание 4).** После деплоя sidecar-экспортёра `up{job="frontend"}` стабильно возвращал `0` с `lastError: connection refused`, хотя под, эндпоинт и `curl` изнутри того же namespace и из `observability` через debug-под — всё работало. Причина: `allow-prometheus-egress` в `monitoring/network-policy.yaml` разрешал egress из `observability` в `miklat-app` только на порт `8000` (под 6 существующих backend-сервисов) — порт `9113` нового экспортёра был не указан и потому блокировался. Исправлено добавлением `port: 9113` в то же правило, применено `kubectl apply -f monitoring/network-policy.yaml`, после чего `up{job="frontend"}` стал `1`. Формулировки про «flannel не enforce'ит NetworkPolicy» в разделах Security Заданий 3 и 4 остаются как есть до перевода README в Фазе 6 (см. оговорку выше) — эта находка лишь ещё раз подтверждает то же исправление понимания, что уже отражено в этом разделе.

### Известные компромиссы (trade-offs) и открытые пункты

- **Метрики `frontend` (nginx)** — реализованы (см. выше) в упрощённом виде: только `up` и nginx-счётчики соединений/запросов, без прикладной латентности (нет `http_request_duration_seconds` — это метрика `prometheus-fastapi-instrumentator`, которой во frontend нет и не может быть без переписывания статики на приложение); ни один обязательный SLI/SLO/алерт/дашборд от этого не зависит — они и так были рассчитаны только на backend.
- **Alertmanager receiver — demo-вебхук**, не реальный Slack/PagerDuty — осознанно, чтобы не заводить в репозитории реальные секреты нотификаций.
- **Учения отказа (п.8, 4 сценария)** и соответствующий evidence в `docs/evidence/task5/` — в процессе; секции "Evidence" в `runbooks/*.md` пока содержат плейсхолдеры, будут дополнены реальными командами/выводом по мере прогона каждого сценария.