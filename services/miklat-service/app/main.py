from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import check_connection, close_pool, init_pool
from app.routers import admin, miklats
from app.schemas import HealthOut, ReadyOut


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
app.include_router(admin.router)


@app.get("/health", response_model=HealthOut, tags=["meta"])
def health():
    """Liveness — сервис поднят, к БД не обращаемся."""
    return {"status": "ok"}


@app.get("/ready", response_model=ReadyOut, tags=["meta"])
def ready():
    """Readiness — реальная проверка соединения с БД (для k8s readinessProbe)."""
    db_ok = check_connection()
    return {"status": "ok" if db_ok else "degraded", "database": "up" if db_ok else "down"}
