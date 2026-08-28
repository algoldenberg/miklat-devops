"""
Конфигурация miklat-photos — только через переменные окружения.

DATABASE_URL / ADMIN_API_KEY — та же конвенция, что и в остальных сервисах.
AWS_* — доступ к тестовому (dev) S3-бакету и SNS-топику (см. Фаза 1, шаг 9
work-plan: они создаются один раз вручную в AWS-консоли; в Terraform те же
ресурсы дальше создаются кодом). Для docker-compose передаются как обычные
env vars — то же самое ограниченное IAM-пользователь (только
s3:PutObject/GetObject и sns:Publish), что запланировано и для K8s Secret
в Фазе 3.
"""

import os

DATABASE_URL: str = os.environ.get(
    "DATABASE_URL",
    "postgresql://miklat:miklat_dev_password@localhost:5432/miklat",
)

ADMIN_API_KEY: str = os.environ.get("ADMIN_API_KEY", "")

# boto3 сам читает AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_DEFAULT_REGION
# из окружения — их не нужно явно прокидывать в код. AWS_REGION здесь — то,
# что явно передаём в boto3.client(region_name=...), с тем же именем
# переменной, что чаще встречается в примерах/документации.
AWS_REGION: str = os.environ.get("AWS_REGION", "eu-central-1")
S3_BUCKET_NAME: str = os.environ.get("S3_BUCKET_NAME", "")
SNS_TOPIC_ARN: str = os.environ.get("SNS_TOPIC_ARN", "")

# Сколько секунд действует presigned URL, который отдаём клиенту для показа
# фото (без публичного bucket policy — см. app/aws_client.py).
PHOTO_URL_EXPIRY_SECONDS: int = int(os.environ.get("PHOTO_URL_EXPIRY_SECONDS", "3600"))

# Разрешённые типы файлов и лимит размера — защита от случайного/умышленного
# заливания произвольных файлов в S3 под видом фото укрытия.
ALLOWED_CONTENT_TYPES: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
MAX_PHOTO_SIZE_BYTES: int = int(os.environ.get("MAX_PHOTO_SIZE_BYTES", str(8 * 1024 * 1024)))  # 8 MB

DEFAULT_LIST_LIMIT = 50
MAX_LIST_LIMIT = 200
