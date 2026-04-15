import logging
import os
import threading
import time
from contextlib import contextmanager
from typing import Generator

import psycopg2
from psycopg2 import pool
from psycopg2.pool import PoolError
from psycopg2.extensions import connection
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

_pool: pool.ThreadedConnectionPool | None = None
_pool_lock = threading.Lock()

_MAX_CONN = int(os.getenv("DB_POOL_MAX_CONN", "10"))
_RETRY_ATTEMPTS = 3
_RETRY_BASE_DELAY = 1.0
_RETRYABLE_DB_ERRORS = (
    psycopg2.OperationalError,
    psycopg2.InterfaceError,
    PoolError,
)


def _get_pool() -> pool.ThreadedConnectionPool:
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                db_url = os.getenv("SUPABASE_DB_TRANSACTION_POOLER_URL")
                if not db_url:
                    raise ValueError("SUPABASE_DB_TRANSACTION_POOLER_URL not set")
                _pool = pool.ThreadedConnectionPool(minconn=1, maxconn=_MAX_CONN, dsn=db_url)
    return _pool


def _ping_connection(conn: connection) -> None:
    with conn.cursor() as cur:
        cur.execute("SELECT 1")


def _discard_connection(conn: connection) -> None:
    try:
        _get_pool().putconn(conn, close=True)
    except Exception:
        try:
            conn.close()
        except Exception:
            logger.debug("Failed to close broken DB connection", exc_info=True)


def _getconn_with_retry() -> connection:
    for attempt in range(_RETRY_ATTEMPTS):
        conn: connection | None = None
        try:
            conn = _get_pool().getconn()
            _ping_connection(conn)
            return conn
        except _RETRYABLE_DB_ERRORS as e:
            if conn is not None:
                _discard_connection(conn)
            if attempt == _RETRY_ATTEMPTS - 1:
                raise
            delay = _RETRY_BASE_DELAY * (2 ** attempt)
            logger.warning("DB connect failed (attempt %d/%d), retrying in %.1fs: %s",
                           attempt + 1, _RETRY_ATTEMPTS, delay, e)
            time.sleep(delay)
        except Exception:
            if conn is not None:
                _discard_connection(conn)
            raise
    raise psycopg2.OperationalError("unreachable")


@contextmanager
def get_connection() -> Generator[connection, None, None]:
    conn = _getconn_with_retry()
    try:
        yield conn
    except BaseException:
        try:
            conn.rollback()
        except Exception as rollback_error:
            logger.warning("DB rollback failed; keeping original exception: %s", rollback_error)
        raise
    finally:
        closed = getattr(conn, "closed", 0)
        try:
            _get_pool().putconn(conn, close=(closed != 0))
        except Exception as put_error:
            logger.warning("Failed to return DB connection to pool: %s", put_error)
            try:
                conn.close()
            except Exception:
                logger.debug("Failed to close DB connection after putconn failure", exc_info=True)


def close_pool() -> None:
    global _pool
    if _pool:
        _pool.closeall()
        _pool = None