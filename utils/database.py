import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

DATABASE_PATH = Path("hireflow.db")

def get_connection() -> sqlite3.Connection:
    return sqlite3.connect(DATABASE_PATH)




def create_database() -> None:     
    sql = """
        CREATE TABLE IF NOT EXISTS resumes (
           doc_id TEXT PRIMARY KEY,
           file_link TEXT NOT NULL,
           email TEXT NOT NULL
         )
     """
    with get_connection() as conn:
        conn.execute(sql)
      


@contextmanager
def transaction() -> Iterator[sqlite3.Connection]:
    """Yield a connection whose writes commit only if the block exits cleanly.

    Pass the yielded connection as `conn` to save_to_sql / update_resume_record
    to make them part of the transaction instead of committing on their own.
    """
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def save_to_sql(
    doc_id: str,
    file_link: str,
    email: str,
    conn: Optional[sqlite3.Connection] = None,
) -> None:
    sql = "INSERT INTO resumes (doc_id, file_link, email ) VALUES (?, ?, ?)"
    if conn is not None:
        # Caller owns the transaction; don't commit here.
        conn.execute(sql, (doc_id, file_link, email))
        return
    with get_connection() as own_conn:
        own_conn.execute(sql, (doc_id, file_link, email))

    
def get_file_link(email: str) -> Optional[str]:
    sql = "SELECT file_link FROM resumes WHERE email = ? LIMIT 1"
    with get_connection() as conn:
        cursor = conn.execute(sql, (email,))
        row = cursor.fetchone()

    if row is None:
        return None

    return row[0]

def update_resume_record(
    doc_id: str,
    file_link: str,
    email: str,
    conn: Optional[sqlite3.Connection] = None,
) -> None:
    sql = "UPDATE resumes SET file_link = ?, doc_id = ? WHERE email = ?"
    if conn is not None:
        # Caller owns the transaction; don't commit here.
        cursor = conn.execute(sql, (file_link, doc_id, email))
        if cursor.rowcount == 0:
            raise RuntimeError(f"No resume record found for email: {email}")
        return
    with get_connection() as own_conn:
        cursor = own_conn.execute(sql, (file_link, doc_id, email))
        if cursor.rowcount == 0:
            raise RuntimeError(f"No resume record found for email: {email}")
