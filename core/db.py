import sqlite3
import json
from datetime import datetime, timezone
from pathlib import Path
from core.config import DB_PATH


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id          TEXT PRIMARY KEY,
                started_at  TEXT NOT NULL,
                ended_at    TEXT,
                model       TEXT,
                source      TEXT DEFAULT 'unknown',
                total_input_tokens  INTEGER DEFAULT 0,
                total_output_tokens INTEGER DEFAULT 0,
                total_cost          REAL    DEFAULT 0.0
            );

            CREATE TABLE IF NOT EXISTS interactions (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id       TEXT,
                timestamp        TEXT NOT NULL,
                prompt           TEXT NOT NULL,
                response         TEXT,
                input_tokens     INTEGER DEFAULT 0,
                output_tokens    INTEGER DEFAULT 0,
                model            TEXT,
                cost             REAL DEFAULT 0.0,
                category         TEXT DEFAULT 'other',
                optimization_score INTEGER DEFAULT 100,
                suggestions      TEXT DEFAULT '[]',
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            );

            CREATE TABLE IF NOT EXISTS daily_stats (
                date            TEXT PRIMARY KEY,
                input_tokens    INTEGER DEFAULT 0,
                output_tokens   INTEGER DEFAULT 0,
                cost            REAL    DEFAULT 0.0,
                interaction_count INTEGER DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_interactions_session
                ON interactions(session_id);
            CREATE INDEX IF NOT EXISTS idx_interactions_timestamp
                ON interactions(timestamp);
        """)


def insert_session(session_id: str, model: str, source: str = "claude-code") -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO sessions (id, started_at, model, source) VALUES (?,?,?,?)",
            (session_id, _now(), model, source),
        )


def close_session(session_id: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE sessions SET ended_at=? WHERE id=?",
            (_now(), session_id),
        )


def insert_interaction(
    session_id: str,
    prompt: str,
    response: str,
    input_tokens: int,
    output_tokens: int,
    model: str,
    cost: float,
    category: str,
    optimization_score: int,
    suggestions: list,
) -> int:
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO interactions
               (session_id, timestamp, prompt, response,
                input_tokens, output_tokens, model, cost,
                category, optimization_score, suggestions)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                session_id, _now(), prompt, response,
                input_tokens, output_tokens, model, cost,
                category, optimization_score, json.dumps(suggestions),
            ),
        )
        conn.execute(
            """INSERT INTO daily_stats (date, input_tokens, output_tokens, cost, interaction_count)
               VALUES (?,?,?,?,1)
               ON CONFLICT(date) DO UPDATE SET
                   input_tokens    = input_tokens    + excluded.input_tokens,
                   output_tokens   = output_tokens   + excluded.output_tokens,
                   cost            = cost            + excluded.cost,
                   interaction_count = interaction_count + 1""",
            (date, input_tokens, output_tokens, cost),
        )
        conn.execute(
            """UPDATE sessions SET
                   total_input_tokens  = total_input_tokens  + ?,
                   total_output_tokens = total_output_tokens + ?,
                   total_cost          = total_cost          + ?
               WHERE id = ?""",
            (input_tokens, output_tokens, cost, session_id),
        )
        return cur.lastrowid


def get_recent_interactions(limit: int = 20) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM interactions ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_daily_stats(days: int = 30) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT * FROM daily_stats
               ORDER BY date DESC LIMIT ?""",
            (days,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_summary_stats() -> dict:
    with get_conn() as conn:
        row = conn.execute(
            """SELECT
                   COUNT(*)           AS total_interactions,
                   SUM(input_tokens)  AS total_input,
                   SUM(output_tokens) AS total_output,
                   SUM(cost)          AS total_cost,
                   AVG(optimization_score) AS avg_score
               FROM interactions"""
        ).fetchone()
        categories = conn.execute(
            "SELECT category, COUNT(*) as cnt FROM interactions GROUP BY category ORDER BY cnt DESC"
        ).fetchall()
    return {
        "total_interactions": row["total_interactions"] or 0,
        "total_input_tokens": row["total_input"] or 0,
        "total_output_tokens": row["total_output"] or 0,
        "total_cost": round(row["total_cost"] or 0, 6),
        "avg_optimization_score": round(row["avg_score"] or 100, 1),
        "categories": [dict(r) for r in categories],
    }


def get_top_expensive(limit: int = 10) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM interactions ORDER BY cost DESC LIMIT ?", (limit,)
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    if "suggestions" in d and isinstance(d["suggestions"], str):
        try:
            d["suggestions"] = json.loads(d["suggestions"])
        except Exception:
            d["suggestions"] = []
    return d
