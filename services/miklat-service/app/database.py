"""
Пул соединений с PostgreSQL (psycopg2), без ORM — сервис маленький,
все запросы явные и живут в app/crud.py, так их легко ревьюить и
показывать в evidence для задания.
"""

from contextlib import contextmanager

import psycopg2
from psycopg2 import pool as pg_pool
from psycopg2.extras import RealDictCursor

from app.config import DATABASE_URL

_pool: pg_pool.SimpleConnectionPool | None = None


def init_pool(minconn: int = 1, maxconn: int = 10) -> None:
    """
    Пробуем поднять пул при старте приложения, но НЕ валим процесс, если
    БД сейчас недоступна — /health должен отвечать даже тогда (liveness
    не равно readiness), а /ready — честно показать, что БД не готова.
    Пул при этом просто создастся лениво при первом реальном запросе.
    """
    global _pool
    if _pool is not None:
        return
    try:
        _pool = pg_pool.SimpleConnectionPool(minconn, maxconn, dsn=DATABASE_URL)
    except psycopg2.OperationalError:
        _pool = None


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.closeall()
        _pool = None


def _ensure_pool() -> pg_pool.SimpleConnectionPool:
    global _pool
    if _pool is None:
        _pool = pg_pool.SimpleConnectionPool(1, 10, dsn=DATABASE_URL)
    return _pool


@contextmanager
def get_cursor(commit: bool = False):
    """
    Выдаёт RealDictCursor (строки как dict) на соединении из пула.
    commit=True — закоммитить транзакцию при успешном выходе из блока.
    Пул создаётся лениво, если старт приложения прошёл без доступной БД.
    """
    active_pool = _ensure_pool()
    conn = active_pool.getconn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            yield cur
        if commit:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        active_pool.putconn(conn)


def check_connection() -> bool:
    """Для /ready — реальный SELECT 1, а не просто наличие пула."""
    try:
        with get_cursor() as cur:
            cur.execute("SELECT 1;")
            cur.fetchone()
        return True
    except Exception:
        return False
