import sqlite3
from pathlib import Path
from datetime import datetime, timezone

# Columns added to observability_logs after its initial release. CREATE TABLE IF NOT EXISTS
# is a no-op on an existing table, so these are added via ALTER TABLE in _migrate_observability_logs().
_OBSERVABILITY_LOG_ADDITIVE_COLUMNS = {
    "student_name": "TEXT DEFAULT ''",
    "user_message": "TEXT DEFAULT ''",
    "evaluation_model": "TEXT DEFAULT ''",
    "guardrail_risk_level": "TEXT DEFAULT ''",
    "quality_badge": "TEXT DEFAULT ''",
    "evaluation_scores": "TEXT DEFAULT '{}'",
    "prompt_versions": "TEXT DEFAULT '{}'",
    "helpful": "INTEGER DEFAULT NULL",
    "feedback_text": "TEXT DEFAULT NULL",
    "input_guardrail_flags": "TEXT DEFAULT '[]'",
    "revision_attempted": "INTEGER DEFAULT 0",
    "token_usage_by_model": "TEXT DEFAULT '{}'",
}


class SQLiteClient:
    """
    Manages the sqlite3 connection, schema creation, and query execution.
    Only layer in the codebase that imports sqlite3.
    All callers use execute() / insert() — never raw sqlite3 directly.
    """

    def __init__(self, db_path: str = "data/memory.db"):
        self._db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> None:
        if self._conn is None:
            self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys = ON")
            self._conn.execute("PRAGMA journal_mode = WAL")

    def create_tables(self) -> None:
        """Create all application tables if they do not already exist."""
        self.connect()
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS students (
                student_id    INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT    NOT NULL,
                created_at    TEXT    NOT NULL,
                last_seen_at  TEXT    NOT NULL,
                session_count INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS profiles (
                student_id   INTEGER PRIMARY KEY,
                profile_json TEXT    NOT NULL DEFAULT '{}',
                updated_at   TEXT    NOT NULL,
                FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS messages (
                message_id     INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id     INTEGER NOT NULL,
                session_number INTEGER NOT NULL DEFAULT 1,
                role           TEXT    NOT NULL CHECK(role IN ('user', 'assistant')),
                content        TEXT    NOT NULL,
                timestamp      TEXT    NOT NULL,
                FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS conversation_summaries (
                summary_id     INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id     INTEGER NOT NULL,
                session_number INTEGER NOT NULL,
                summary_text   TEXT    NOT NULL,
                created_at     TEXT    NOT NULL,
                FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS observability_logs (
                log_id              INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id          INTEGER,
                timestamp           TEXT    NOT NULL,
                agent               TEXT    NOT NULL DEFAULT '',
                model               TEXT    DEFAULT '',
                embedding_model     TEXT    DEFAULT '',
                prompt_tokens       INTEGER DEFAULT 0,
                completion_tokens   INTEGER DEFAULT 0,
                estimated_cost_usd  REAL    DEFAULT 0.0,
                latency_ms          INTEGER DEFAULT 0,
                retrieved_doc_count INTEGER DEFAULT 0,
                guardrail_flags     TEXT    DEFAULT '[]',
                eval_score          INTEGER DEFAULT 0,
                error               TEXT    DEFAULT ''
            );
        """)
        self._conn.commit()
        self._migrate_observability_logs()

    def _migrate_observability_logs(self) -> None:
        """Additive-only migration: adds any columns introduced after the table's initial release."""
        existing = {row["name"] for row in self.execute("PRAGMA table_info(observability_logs)")}
        for column, definition in _OBSERVABILITY_LOG_ADDITIVE_COLUMNS.items():
            if column not in existing:
                self._conn.execute(f"ALTER TABLE observability_logs ADD COLUMN {column} {definition}")
        self._conn.commit()

    def execute(self, sql: str, params: tuple = ()) -> list[dict]:
        """
        Execute a SQL statement and return all result rows as dicts.
        Returns an empty list for INSERT / UPDATE / DELETE.
        """
        self.connect()
        cursor = self._conn.execute(sql, params)
        self._conn.commit()
        if cursor.description is not None:
            return [dict(row) for row in cursor.fetchall()]
        return []

    def insert(self, sql: str, params: tuple = ()) -> int:
        """Execute an INSERT statement and return the new row's id."""
        self.connect()
        cursor = self._conn.execute(sql, params)
        self._conn.commit()
        return cursor.lastrowid

    def execute_many(self, sql: str, rows: list[tuple]) -> None:
        """Batch-execute a parameterized statement."""
        self.connect()
        self._conn.executemany(sql, rows)
        self._conn.commit()
