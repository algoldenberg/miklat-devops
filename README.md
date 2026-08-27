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

## Локальный запуск

_Будет заполнено на шаге, где появится `docker-compose.yml` и первые сервисы._
