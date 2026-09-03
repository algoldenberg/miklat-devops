from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import metrics
from app.database import check_connection, close_pool, init_pool
from app.osrm_client import check_osrm
from app.routers import routes
from app.schemas import HealthOut, ReadyOut


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_pool()
    yield
    close_pool()


app = FastAPI(
    title="miklat-walking-routes",
    description="Пеший маршрут от пользователя до укрытия (OSRM, профиль foot)",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(routes.router)

metrics.instrument(app, app.version)


@app.get("/health", response_model=HealthOut, tags=["meta"])
def health():
    return {"status": "ok"}


@app.get("/ready", response_model=ReadyOut, tags=["meta"])
def ready():
    db_ok = check_connection()
    osrm_ok = check_osrm()
    overall = "ok" if (db_ok and osrm_ok) else "degraded"
    return {"status": overall, "database": "up" if db_ok else "down", "osrm": "up" if osrm_ok else "down"}
