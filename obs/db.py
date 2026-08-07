"""
obs/db.py — armazenamento SQLite para traces, feedback e evals.

Conexão por operação (check_same_thread=False) para ser seguro entre as threads
dos pipelines e o worker. Toda escrita é best-effort: falha de observabilidade
é logada, nunca propagada.
"""

from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path

OBS_DB = os.getenv("OBS_DB", "output/observability.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS traces (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    trace_id      TEXT,
    ts            REAL,
    operation     TEXT,
    provider      TEXT,
    model         TEXT,
    latency_ms    REAL,
    status        TEXT,
    input_tokens  INTEGER,
    output_tokens INTEGER,
    cost_usd      REAL,
    error         TEXT
);
CREATE INDEX IF NOT EXISTS ix_traces_trace ON traces(trace_id);
CREATE INDEX IF NOT EXISTS ix_traces_ts ON traces(ts);

CREATE TABLE IF NOT EXISTS feedback (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    trace_id  TEXT,
    ts        REAL,
    target    TEXT,
    vote      INTEGER,
    comment   TEXT
);
CREATE INDEX IF NOT EXISTS ix_feedback_trace ON feedback(trace_id);

CREATE TABLE IF NOT EXISTS evals (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    trace_id      TEXT,
    ts            REAL,
    target        TEXT,
    groundedness  REAL,
    relevance     REAL,
    coherence     REAL,
    hallucination INTEGER,
    judge_score   REAL,
    model         TEXT,
    rationale     TEXT
);
CREATE INDEX IF NOT EXISTS ix_evals_trace ON evals(trace_id);
CREATE INDEX IF NOT EXISTS ix_evals_ts ON evals(ts);

CREATE TABLE IF NOT EXISTS drift_runs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ts           REAL,
    recent_h     REAL,
    baseline_h   REAL,
    status       TEXT,
    n_alerts     INTEGER,
    metrics_json TEXT,
    alerts_json  TEXT
);
CREATE INDEX IF NOT EXISTS ix_drift_ts ON drift_runs(ts);
"""


def _connect() -> sqlite3.Connection:
    Path(OBS_DB).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(OBS_DB, check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init() -> None:
    try:
        conn = _connect()
        conn.executescript(_SCHEMA)
        conn.commit()
        conn.close()
    except Exception as e:  # pragma: no cover
        print(f"[obs.db] init falhou (seguindo sem obs): {e}")


def insert_trace(row: dict) -> None:
    try:
        conn = _connect()
        conn.execute(
            """INSERT INTO traces
               (trace_id, ts, operation, provider, model, latency_ms, status,
                input_tokens, output_tokens, cost_usd, error)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (row.get("trace_id"), row.get("ts", time.time()),
             row.get("operation"), row.get("provider"), row.get("model"),
             row.get("latency_ms"), row.get("status"),
             row.get("input_tokens"), row.get("output_tokens"),
             row.get("cost_usd"), row.get("error")),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[obs.db] insert_trace falhou: {e}")


def insert_feedback(trace_id: str, target: str, vote: int, comment: str = "") -> None:
    try:
        conn = _connect()
        conn.execute(
            "INSERT INTO feedback (trace_id, ts, target, vote, comment) "
            "VALUES (?,?,?,?,?)",
            (trace_id, time.time(), target, vote, comment),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[obs.db] insert_feedback falhou: {e}")


def insert_eval(row: dict) -> None:
    try:
        conn = _connect()
        conn.execute(
            """INSERT INTO evals
               (trace_id, ts, target, groundedness, relevance, coherence,
                hallucination, judge_score, model, rationale)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (row.get("trace_id"), row.get("ts", time.time()), row.get("target"),
             row.get("groundedness"), row.get("relevance"), row.get("coherence"),
             int(bool(row.get("hallucination"))), row.get("judge_score"),
             row.get("model"), row.get("rationale")),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[obs.db] insert_eval falhou: {e}")


def query(sql: str, params: tuple = ()) -> list[dict]:
    try:
        conn = _connect()
        rows = conn.execute(sql, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"[obs.db] query falhou: {e}")
        return []


def execute(sql: str, params: tuple = ()) -> None:
    """Escrita best-effort (INSERT/UPDATE). Nunca propaga erro."""
    try:
        conn = _connect()
        conn.execute(sql, params)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[obs.db] execute falhou: {e}")
