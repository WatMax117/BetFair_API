"""Read-only PostgreSQL connection for Risk Analytics API."""
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager

POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.environ.get("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.environ.get("POSTGRES_DB", "netbet")
POSTGRES_USER = os.environ.get("POSTGRES_USER", "netbet")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "")


def get_conn_kwargs():
    return {
        "host": POSTGRES_HOST,
        "port": POSTGRES_PORT,
        "dbname": POSTGRES_DB,
        "user": POSTGRES_USER,
        "password": POSTGRES_PASSWORD,
        "connect_timeout": 10,
    }


@contextmanager
def cursor():
    conn = psycopg2.connect(**get_conn_kwargs(), cursor_factory=RealDictCursor)
    try:
        yield conn.cursor()
        conn.commit()
    finally:
        conn.close()
