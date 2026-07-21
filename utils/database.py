import os
import sqlite3
from pathlib import Path
from typing import Optional

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
      


def save_to_sql(doc_id: str, file_link: str, email: str ) -> None:
    sql = "INSERT INTO resumes (doc_id, file_link, email ) VALUES (?, ?, ?)"
    with get_connection() as conn:
        conn.execute(sql, (doc_id, file_link, email))
        
    
def get_file_link(email: str) -> Optional[str]:
    sql = "SELECT file_link FROM resumes WHERE email = ? LIMIT 1"
    with get_connection() as conn:
        cursor = conn.execute(sql, (email,))
        row = cursor.fetchone()

    if row is None:
        return None

    return row[0]

def update_resume_record(doc_id: str, file_link: str, email: str) -> None:
    sql = "UPDATE resumes SET file_link = ?, doc_id = ? WHERE email = ?"
    with get_connection() as conn:
        cursor = conn.execute(sql, (file_link, doc_id, email))
        if cursor.rowcount == 0:
            raise RuntimeError(f"No resume record found for email: {email}")
