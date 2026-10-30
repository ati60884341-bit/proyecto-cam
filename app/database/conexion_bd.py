import pyodbc
from app.config import CONNECTION_STRING


def get_connection():
    conn = pyodbc.connect(CONNECTION_STRING, autocommit=True)
    return conn


def query(sql, params=()):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        columns = [c[0] for c in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        return rows


def query_one(sql, params=()):
    rows = query(sql, params)
    return rows[0] if rows else None


def execute(sql, params=(), return_id=False):
    """Runs an INSERT/UPDATE/DELETE. Propagates pyodbc.Error (e.g. a trigger RAISERROR).

    return_id=True: the caller's INSERT must include an
    "OUTPUT INSERTED.<columna>" clause (right before VALUES) and this
    returns that value. A separate "SELECT SCOPE_IDENTITY()" call is NOT
    reliable with this ODBC driver - it intermittently comes back NULL even
    right after a successful insert, because pyodbc can execute parameterized
    statements in a way that resets the identity scope between calls."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        if return_id:
            return cursor.fetchval()
        return None
