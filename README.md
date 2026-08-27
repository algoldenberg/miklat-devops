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
