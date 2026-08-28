"""
Конфигурация miklat-comments — только через переменные окружения.
Те же имена переменных, что и в miklat-service (DATABASE_URL, ADMIN_API_KEY) —
единая конвенция для всех сервисов, чтобы дальше Ansible/K8s Secrets не
плодили разные названия под одно и то же.
"""

import os

DATABASE_URL: str = os.environ.get(
    "DATABASE_URL",
    "postgresql://miklat:miklat_dev_password@localhost:5432/miklat",
)

ADMIN_API_KEY: str = os.environ.get("ADMIN_API_KEY", "")

DEFAULT_LIST_LIMIT = 50
MAX_LIST_LIMIT = 200
