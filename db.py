import os
import mysql.connector
from mysql.connector import pooling, Error

# ---------------------------------------------------------------------------
# Database configuration — reads from environment variables with fallbacks.
# Set these in your shell / .env before running:
#   export DB_HOST=localhost
#   export DB_USER=root
#   export DB_PASSWORD=your_password
#   export DB_NAME=hostel_management
# ---------------------------------------------------------------------------

DB_CONFIG = {
    "host":     os.environ.get("DB_HOST",     "localhost"),
    "user":     os.environ.get("DB_USER",     "root"),
    "password": os.environ.get("DB_PASSWORD", "NCT127@dream"),
    "database": os.environ.get("DB_NAME",     "hostel_management"),
}

_pool = None

def _get_pool():
    global _pool
    if _pool is None:
        _pool = pooling.MySQLConnectionPool(
            pool_name="hostel_pool",
            pool_size=5,
            **DB_CONFIG
        )
    return _pool


def get_db_connection():
    """Return a pooled database connection.

    Usage:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        ...
        cursor.close()
        conn.close()   # returns connection to pool

    Raises:
        RuntimeError: if the database cannot be reached.
    """
    try:
        return _get_pool().get_connection()
    except Error as e:
        raise RuntimeError(
            f"Cannot connect to database. "
            f"Check DB_HOST / DB_USER / DB_PASSWORD / DB_NAME env vars. "
            f"Original error: {e}"
        )
