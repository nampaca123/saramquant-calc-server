import os
from contextlib import contextmanager
from typing import Generator
import psycopg2
from psycopg2 import pool
from psycopg2.extensions import connection
from dotenv import load_dotenv

load_dotenv()

_pool: pool.ThreadedConnectionPool | None = None


def _get_pool() -> pool.ThreadedConnectionPool:
    global _pool
    if _pool is None:
        db_url = os.getenv("SUPABASE_DB_TRANSACTION_POOLER_URL")
        if not db_url:
            raise ValueError("SUPABASE_DB_TRANSACTION_POOLER_URL not set")
        _pool = pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=db_url,
        )
    return _pool


@contextmanager
def get_connection() -> Generator[connection, None, None]:
    """
    Context manager for database connections.
    Usage:
        with get_connection() as conn:
            # use conn
    """
    conn = _get_pool().getconn()
    try:
        yield conn
    finally:
        _get_pool().putconn(conn)


def close_pool() -> None:
    global _pool
    if _pool:
        _pool.closeall()
        _pool = None