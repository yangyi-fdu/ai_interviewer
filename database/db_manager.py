import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "interview_records.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS reports (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     TEXT NOT NULL,
    knowledge   INTEGER,
    logic       INTEGER,
    clarity     INTEGER,
    overall     INTEGER,
    report_text TEXT NOT NULL,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""


@contextmanager
def connect(db_path: Path = DB_PATH):
    """Open a connection, commit on success, and always close it."""
    conn = sqlite3.connect(db_path)
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def init_db(db_path: Path = DB_PATH) -> None:
    with connect(db_path) as conn:
        conn.execute(SCHEMA)


def save_report(user_id: str, report_text: str, scores=None, db_path: Path = DB_PATH) -> None:
    """Store the full report plus the parsed scores (NULL if a score could not be parsed)."""
    values = (scores.knowledge, scores.logic, scores.clarity, scores.overall) if scores else (None,) * 4
    with connect(db_path) as conn:
        conn.execute(
            "INSERT INTO reports (user_id, knowledge, logic, clarity, overall, report_text) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, *values, report_text),
        )


if __name__ == "__main__":
    init_db()
    print(f"Initialised {DB_PATH}")
