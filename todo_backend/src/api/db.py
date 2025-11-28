import os
import sqlite3
from contextlib import contextmanager
from typing import Generator, Optional, Tuple, Any, List, Dict


DB_ENV_VAR = "DB_PATH"
DATABASE_CONN_FILE = os.path.abspath(
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "..",
        "simple-to-do-list-179040-179051",
        "database",
        "db_connection.txt",
    )
)


def _parse_db_path_from_file(contents: str) -> Optional[str]:
    """
    Parse db_connection.txt to extract the absolute SQLite file path.

    The file typically contains lines like:
    - "# File path: /abs/path/to/myapp.db"
    - "# Connection string: sqlite:////abs/path/to/myapp.db"
    - "# Python: sqlite3.connect('/abs/path/to/myapp.db')"
    """
    for raw in contents.splitlines():
        line = raw.strip()
        low = line.lower()
        if low.startswith("# file path:"):
            path = line.split(":", 1)[1].strip()
            if path:
                return path
        if low.startswith("# connection string:"):
            # Normalize sqlite:///<abs> to absolute file path
            val = line.split(":", 1)[1].strip()
            # Expect formats like sqlite:////abs/path.db or sqlite:///C:/path.db
            if "sqlite:" in val:
                # Remove scheme
                val = val.split("sqlite:", 1)[1]
                # Remove leading slashes smartly
                while val.startswith("/"):
                    val = val[1:]
                # Now val should be abs path without leading slash; re-add one
                if val:
                    return "/" + val
        if "sqlite3.connect(" in line and ".db" in line:
            # Extract quoted path
            parts = line.split("sqlite3.connect(", 1)[1]
            quote = "'" if "'" in parts else '"'
            try:
                inner = parts.split(quote, 2)[1]
                return os.path.abspath(inner)
            except Exception:
                continue
    return None


# PUBLIC_INTERFACE
def resolve_db_path() -> Tuple[str, str]:
    """Resolve the absolute SQLite database file path and the source used.

    Resolution priority:
    1. Environment variable DB_PATH (absolute path to .db file)
    2. database/db_connection.txt (from the sibling 'database' container)
    3. Fallback to database/myapp.db in the database container directory

    Returns:
        A tuple of (db_path, source)
        - db_path: absolute path to SQLite database file
        - source: one of 'env', 'conn_file', 'fallback'
    """
    # 1) Env override
    env_path = os.getenv(DB_ENV_VAR)
    if env_path:
        return (os.path.abspath(env_path), "env")

    # 2) db_connection.txt
    conn_file = DATABASE_CONN_FILE
    try:
        if os.path.exists(conn_file):
            with open(conn_file, "r") as f:
                contents = f.read()
            parsed = _parse_db_path_from_file(contents)
            if parsed:
                return (os.path.abspath(parsed), "conn_file")
    except Exception:
        # Ignore and fallback
        pass

    # 3) Fallback near the database container
    fallback = os.path.abspath(
        os.path.join(
            os.path.dirname(conn_file) if conn_file else ".",
            "myapp.db",
        )
    )
    return (fallback, "fallback")


@contextmanager
def get_connection() -> Generator[sqlite3.Connection, None, None]:
    """Context manager to provide a SQLite connection with row factory."""
    db_path, _ = resolve_db_path()
    conn = sqlite3.connect(db_path)
    try:
        conn.row_factory = sqlite3.Row  # allows dict-like access
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    """Convert sqlite3.Row to a plain dict."""
    return {k: row[k] for k in row.keys()}


# PUBLIC_INTERFACE
def list_todos() -> List[Dict[str, Any]]:
    """Return all todos ordered by created_at descending."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, title, description, completed, created_at, updated_at
            FROM todos
            ORDER BY created_at DESC, id DESC
            """
        )
        rows = cur.fetchall()
        return [_row_to_dict(r) for r in rows]


# PUBLIC_INTERFACE
def create_todo(title: str, description: Optional[str]) -> Dict[str, Any]:
    """Create a new todo and return it."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO todos (title, description, completed)
            VALUES (?, ?, 0)
            """,
            (title, description),
        )
        new_id = cur.lastrowid
        cur.execute(
            """
            SELECT id, title, description, completed, created_at, updated_at
            FROM todos WHERE id = ?
            """,
            (new_id,),
        )
        row = cur.fetchone()
        return _row_to_dict(row) if row else {}


# PUBLIC_INTERFACE
def update_todo(todo_id: int, title: str, description: Optional[str], completed: Optional[bool]) -> Optional[Dict[str, Any]]:
    """Update fields of a todo. Returns updated row or None if not found."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM todos WHERE id = ?", (todo_id,))
        if not cur.fetchone():
            return None

        # Build dynamic update
        fields = []
        params: list[Any] = []
        if title is not None:
            fields.append("title = ?")
            params.append(title)
        if description is not None:
            fields.append("description = ?")
            params.append(description)
        if completed is not None:
            fields.append("completed = ?")
            params.append(1 if completed else 0)

        if fields:
            set_clause = ", ".join(fields)
            params.append(todo_id)
            cur.execute(f"UPDATE todos SET {set_clause} WHERE id = ?", tuple(params))

        cur.execute(
            "SELECT id, title, description, completed, created_at, updated_at FROM todos WHERE id = ?",
            (todo_id,),
        )
        row = cur.fetchone()
        return _row_to_dict(row) if row else None


# PUBLIC_INTERFACE
def toggle_todo(todo_id: int) -> Optional[Dict[str, Any]]:
    """Flip the completed status of a todo. Returns updated row or None if not found."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT completed FROM todos WHERE id = ?", (todo_id,))
        row = cur.fetchone()
        if not row:
            return None
        new_val = 0 if int(row["completed"]) == 1 else 1
        cur.execute("UPDATE todos SET completed = ? WHERE id = ?", (new_val, todo_id))
        cur.execute(
            "SELECT id, title, description, completed, created_at, updated_at FROM todos WHERE id = ?",
            (todo_id,),
        )
        updated = cur.fetchone()
        return _row_to_dict(updated) if updated else None


# PUBLIC_INTERFACE
def delete_todo(todo_id: int) -> bool:
    """Delete a todo by id. Returns True if a row was deleted."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
        return cur.rowcount > 0
