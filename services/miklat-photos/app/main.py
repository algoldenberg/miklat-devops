import logging
from contextlib import asynccontextmanager

from botocore.exceptions import ClientError, EndpointConnectionError, NoCredentialsError
from fastapi import FastAPI

from app import aws_client
from app.config import S3_BUCKET_NAME
from app.database import check_connection, close_pool, init_pool
from app.routers import admin, photos
from app.schemas import HealthOut, ReadyOut

# Фаза 4, шаг 4.5: канареечный комментарий — реального изменения нет, коммит
# нужен только чтобы "Detect changed services" увидел miklat-photos и мы
# впервые реально прогнали стадию Build & push (kaniko): auth в GHCR через
# credentials-binding, генерация /kaniko/.docker/config.json, push образа.
# Можно удалить эту строку в любой следующей правке.

logger = logging.getLogger("miklat-photos")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_pool()
    yield
    close_pool()


app = FastAPI(
    title="miklat-photos",
    description="Загрузка фото укрытий (S3) и модерация через SNS-уведомления (miklat-devops)",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(photos.router)
app.include_router(admin.router)


@app.get("/health", response_model=HealthOut, tags=["meta"])
def health():
    return {"status": "ok"}


@app.get("/ready", response_model=ReadyOut, tags=["meta"])
def ready():
    db_ok = check_connection()

    if not S3_BUCKET_NAME:
        s3_status = "not configured"
    else:
        try:
            aws_client._s3().head_bucket(Bucket=S3_BUCKET_NAME)
            s3_status = "up"
        except (ClientError, EndpointConnectionError, NoCredentialsError) as exc:
            logger.warning("S3 readiness check failed: %s", exc)
            s3_status = "down"

    overall_ok = db_ok and s3_status == "up"
    return {
        "status": "ok" if overall_ok else "degraded",
        "database": "up" if db_ok else "down",
        "s3": s3_status,
    }# canary: phase4 step6 e2e test 2026-09-02T15:21:40Z
