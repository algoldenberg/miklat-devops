"""
Конфигурация miklat-service — только через переменные окружения.
Никаких секретов/хардкода здесь: реальные значения приходят через .env
(локально, см. .env.example) или через Kubernetes Secret / Ansible-шаблон
в последующих фазах.
"""

import os

DATABASE_URL: str = os.environ.get(
    "DATABASE_URL",
    "postgresql://miklat:miklat_dev_password@localhost:5432/miklat",
)

# Ключ для защиты /admin/* эндпоинтов (заголовок X-Admin-Key).
# Намеренно НЕТ дефолтного значения — если ключ не задан, admin-эндпоинты
# должны быть недоступны (см. app/auth.py), а не открыты по пустому ключу.
ADMIN_API_KEY: str = os.environ.get("ADMIN_API_KEY", "")

# SNS-триггер #2 (жалоба на укрытие) — тот же Topic "miklat-notifications",
# что и в miklat-photos (см. work-plan, Фаза 1 шаг 9 — разовая ручная
# настройка dev S3/SNS). Пустое значение по умолчанию: без него /report
# просто не сможет опубликовать уведомление (жалоба всё равно сохранится в
# БД — см. app/crud.py, публикация в SNS обёрнута как best-effort).
AWS_REGION: str = os.environ.get("AWS_REGION", "eu-central-1")
SNS_TOPIC_ARN: str = os.environ.get("SNS_TOPIC_ARN", "")

DEFAULT_LIST_LIMIT = 50
MAX_LIST_LIMIT = 200

DEFAULT_NEAREST_LIMIT = 5
MAX_NEAREST_LIMIT = 50
