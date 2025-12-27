# Create a table storing appoinment requests with a simple status workflow

import sqlite3
from pathlib import Path

DB_PATH = Path("data.sqlite3")

def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

def init_db() -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS appointment_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                contact TEXT NOT NULL,
                preferred_times TEXT NOT NULL,
                service TEXT NOT NULL,
                note TEXT,
                status TEXT NOT NULL DEFAULT 'new',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """)
    conn.commit()
    conn.close()
