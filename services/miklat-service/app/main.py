import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import aws_client, metrics
from app.config import SNS_TOPIC_ARN
from app.database import check_connection, close_pool, init_pool
from app.routers import admin, miklats, reports, submissions
from app.schemas import HealthOut, ReadyOut

logger = logging.getLogger("miklat-service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_pool()
    yield
    close_pool()


app = FastAPI(
    title="miklat-service",
    description="CRUD укрытий, поиск ближайшего укрытия, модерация заявок (miklat-devops)",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(miklats.router)
app.include_router(reports.router)
app.include_router(submissions.router)
app.include_router(admin.router)

# Задание 5: /metrics + app_info. Вызвано ДО регистрации любых дальнейших
# маршрутов ниже (их тут больше нет, но порядок важен в сервисах с
# catch-all роутом — см. miklat-gateway) — сработает даже если такой роут
# появится позже.
metrics.instrument(app, app.version)


@app.get("/health", response_model=HealthOut, tags=["meta"])
def health():
    """Liveness — сервис поднят, к БД не обращаемся."""
    return {"status": "ok"}


@app.get("/ready", response_model=ReadyOut, tags=["meta"])
def ready():
    """Readiness — реальная проверка БД + доступности SNS-топика (для k8s readinessProbe)."""
    db_ok = check_connection()

    if not SNS_TOPIC_ARN:
        sns_status = "not configured"
    else:
        sns_status = "up" if aws_client.check_topic_reachable(SNS_TOPIC_ARN) else "down"

    overall_ok = db_ok and sns_status == "up"
    return {
        "status": "ok" if overall_ok else "degraded",
        "database": "up" if db_ok else "down",
        "sns": sns_status,
    }
