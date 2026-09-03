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

CREATE TABLE IF NOT EXISTS context_snapshots (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    trace_id           TEXT,
    ts                 REAL,
    operation          TEXT,
    provider           TEXT,
    model              TEXT,
    context_limit      INTEGER,
    used_tokens        INTEGER,
    system_tokens      INTEGER,
    tool_tokens        INTEGER,
    skill_tokens       INTEGER,
    memory_tokens      INTEGER,
    conversation_tokens INTEGER,
    retrieved_tokens   INTEGER,
    unattributed_tokens INTEGER,
    reserve_tokens     INTEGER,
    input_hash         TEXT,
    status             TEXT,
    cost_usd           REAL
);
CREATE INDEX IF NOT EXISTS ix_context_ts ON context_snapshots(ts);
CREATE INDEX IF NOT EXISTS ix_context_trace ON context_snapshots(trace_id);
CREATE INDEX IF NOT EXISTS ix_context_hash ON context_snapshots(input_hash);

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
    coherence       REAL,
    source_fidelity REAL,
    completeness    REAL,
    hallucination   INTEGER,
    judge_score     REAL,
    model           TEXT,
    prompt_version  TEXT,
    rationale       TEXT
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

CREATE TABLE IF NOT EXISTS benchmark_runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ts              REAL,
    suite           TEXT,
    case_id         TEXT,
    label           TEXT,
    target          TEXT,
    trace_id        TEXT,
    judge_model     TEXT,
    prompt_version  TEXT,
    groundedness    REAL,
    relevance       REAL,
    source_fidelity REAL,
    completeness    REAL,
    judge_score     REAL,
    hallucination   INTEGER,
    gate_status     TEXT,
    gate_failures   TEXT
);
CREATE INDEX IF NOT EXISTS ix_benchmark_ts ON benchmark_runs(ts);
CREATE INDEX IF NOT EXISTS ix_benchmark_suite ON benchmark_runs(suite);

CREATE TABLE IF NOT EXISTS security_events (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ts            REAL,
    event_type    TEXT,
    action        TEXT,
    user_key      TEXT,
    target        TEXT,
    trace_id      TEXT,
    risk          TEXT,
    reasons_json  TEXT,
    metadata_json TEXT
);
CREATE INDEX IF NOT EXISTS ix_security_events_ts ON security_events(ts);
CREATE INDEX IF NOT EXISTS ix_security_events_action ON security_events(action);

CREATE TABLE IF NOT EXISTS pipeline_stages (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id       TEXT,
    pipeline     TEXT,
    stage        TEXT,
    ts           REAL,
    duration_ms  REAL,
    peak_rss_mb         REAL,
    min_available_mb    REAL,
    peak_system_mem_pct REAL,
    avg_cpu_pct         REAL,
    peak_cpu_pct        REAL,
    measurement_version INTEGER DEFAULT 2,
    status              TEXT,
    detail       TEXT
);
CREATE INDEX IF NOT EXISTS ix_pipeline_stages_job ON pipeline_stages(job_id);
CREATE INDEX IF NOT EXISTS ix_pipeline_stages_pipeline_stage ON pipeline_stages(pipeline, stage);
CREATE INDEX IF NOT EXISTS ix_pipeline_stages_ts ON pipeline_stages(ts);

CREATE TABLE IF NOT EXISTS model_comparisons (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ts            REAL,
    comparison_id TEXT,
    provider      TEXT,
    model         TEXT,
    latency_ms    REAL,
    status        TEXT,
    response_text TEXT,
    error         TEXT,
    judge_score   REAL,
    groundedness  REAL,
    relevance     REAL
);
CREATE INDEX IF NOT EXISTS ix_model_comparison_id ON model_comparisons(comparison_id);
CREATE INDEX IF NOT EXISTS ix_model_comparison_ts ON model_comparisons(ts);

CREATE TABLE IF NOT EXISTS ux_events (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    ts       REAL,
    event    TEXT,
    page     TEXT,
    user_key TEXT
);
CREATE INDEX IF NOT EXISTS ix_ux_events_ts ON ux_events(ts);
CREATE INDEX IF NOT EXISTS ix_ux_events_event ON ux_events(event);
"""


def _connect() -> sqlite3.Connection:
    Path(OBS_DB).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(OBS_DB, check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def _ensure_pipeline_stage_columns(conn: sqlite3.Connection) -> None:
    """Migração aditiva das métricas de performance.

    Versões anteriores mediam apenas duration_ms + RSS do processo Python.
    Agora medimos process-tree RSS (inclui ffmpeg), memória disponível do host
    e CPU global, sem exigir apagar o banco existente.
    """
    existing = {r[1] for r in conn.execute("PRAGMA table_info(pipeline_stages)").fetchall()}
    additions = {
        "min_available_mb": "REAL",
        "peak_system_mem_pct": "REAL",
        "avg_cpu_pct": "REAL",
        "peak_cpu_pct": "REAL",
        # Linhas históricas anteriores à telemetria process-tree são v1.
        # DEFAULT 1 no ALTER garante que não misturemos RAM antiga (só Python)
        # com RAM v2 (Python + ffmpeg) nas médias.
        "measurement_version": "INTEGER DEFAULT 1",
    }
    for name, sql_type in additions.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE pipeline_stages ADD COLUMN {name} {sql_type}")


def _ensure_eval_columns(conn: sqlite3.Connection) -> None:
    """Migração aditiva para bancos de observabilidade já existentes.

    SQLite não aplica novas colunas de um CREATE TABLE IF NOT EXISTS em tabelas
    antigas. Mantemos a migração aqui para que upgrades não exijam apagar
    output/observability.db nem interrompam o StudyFlow.
    """
    existing = {r[1] for r in conn.execute("PRAGMA table_info(evals)").fetchall()}
    additions = {
        "source_fidelity": "REAL",
        "completeness": "REAL",
        "prompt_version": "TEXT",
    }
    for name, sql_type in additions.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE evals ADD COLUMN {name} {sql_type}")


def init() -> None:
    try:
        conn = _connect()
        conn.executescript(_SCHEMA)
        _ensure_eval_columns(conn)
        _ensure_pipeline_stage_columns(conn)
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


def insert_pipeline_stage(row: dict) -> None:
    """Duração + pico de RAM de UMA etapa de um pipeline de vídeo
    (download/transcrição/highlights/corte/vertical etc) — separado de
    traces (que é especificamente sobre chamada de LLM: provider,
    tokens, custo — nada disso se aplica a uma etapa de ffmpeg). Ver
    obs/stage_timer.py pra quem grava isso."""
    try:
        conn = _connect()
        conn.execute(
            """INSERT INTO pipeline_stages
               (job_id, pipeline, stage, ts, duration_ms, peak_rss_mb,
                min_available_mb, peak_system_mem_pct, avg_cpu_pct, peak_cpu_pct,
                measurement_version, status, detail)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (row.get("job_id"), row.get("pipeline"), row.get("stage"),
             row.get("ts", time.time()), row.get("duration_ms"),
             row.get("peak_rss_mb"), row.get("min_available_mb"),
             row.get("peak_system_mem_pct"), row.get("avg_cpu_pct"),
             row.get("peak_cpu_pct"), row.get("measurement_version", 2),
             row.get("status"), row.get("detail")),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[obs.db] insert_pipeline_stage falhou: {e}")


def resumo_por_etapa(pipeline: str | None = None, dias: int = 30) -> list[dict]:
    """Agrega pipeline_stages por (pipeline, stage): quantas execuções,
    duração média/máxima, pico de RAM médio/máximo, taxa de erro. É a
    base pra responder "qual etapa realmente consome mais tempo?" e
    "vale a pena paralelizar isso?" com dado real em vez de suposição
    (ver auditoria-performance-clips.md)."""
    try:
        conn = _connect()
        corte_ts = time.time() - dias * 86400
        sql = """
            SELECT
                pipeline, stage,
                COUNT(*) AS n,
                AVG(duration_ms) AS media_duration_ms,
                MAX(duration_ms) AS max_duration_ms,
                AVG(CASE WHEN COALESCE(measurement_version, 1) >= 2 THEN peak_rss_mb END) AS media_peak_rss_mb,
                MAX(CASE WHEN COALESCE(measurement_version, 1) >= 2 THEN peak_rss_mb END) AS max_peak_rss_mb,
                SUM(CASE WHEN COALESCE(measurement_version, 1) >= 2 THEN 1 ELSE 0 END) AS n_metricas_v2,
                MIN(min_available_mb) AS min_available_mb,
                AVG(peak_system_mem_pct) AS media_peak_system_mem_pct,
                MAX(peak_system_mem_pct) AS max_peak_system_mem_pct,
                AVG(avg_cpu_pct) AS media_cpu_pct,
                MAX(peak_cpu_pct) AS max_peak_cpu_pct,
                SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) AS n_erros
            FROM pipeline_stages
            WHERE ts >= ?
        """
        params: list = [corte_ts]
        if pipeline:
            sql += " AND pipeline = ?"
            params.append(pipeline)
        sql += " GROUP BY pipeline, stage ORDER BY media_duration_ms DESC"
        rows = conn.execute(sql, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"[obs.db] resumo_por_etapa falhou: {e}")
        return []


def etapas_recentes(pipeline: str | None = None, limit: int = 80) -> list[dict]:
    """Linhas recentes sem agregação, para comparar execuções reais por job.
    Não retorna conteúdo do vídeo, prompt ou transcript — só metadados de performance.
    """
    try:
        conn = _connect()
        sql = """
            SELECT job_id, pipeline, stage, ts, duration_ms, peak_rss_mb,
                   min_available_mb, peak_system_mem_pct, avg_cpu_pct,
                   peak_cpu_pct, measurement_version, status, detail
            FROM pipeline_stages
        """
        params: list = []
        if pipeline:
            sql += " WHERE pipeline = ?"
            params.append(pipeline)
        sql += " ORDER BY ts DESC LIMIT ?"
        params.append(max(1, min(int(limit), 500)))
        rows = conn.execute(sql, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"[obs.db] etapas_recentes falhou: {e}")
        return []


def jobs_recentes(pipeline: str | None = None, limit: int = 12) -> list[dict]:
    """Lista execuções recentes agrupadas por job_id.

    Usado no /obs para comparar uma execução específica sem misturar vídeos
    de durações diferentes nas médias históricas.
    """
    try:
        conn = _connect()
        sql = """
            SELECT
                job_id,
                pipeline,
                MIN(ts) AS inicio_ts,
                MAX(ts) AS fim_ts,
                MAX(CASE WHEN stage = 'total' THEN duration_ms END) AS total_duration_ms,
                MAX(CASE WHEN stage = 'total' THEN status END) AS status,
                COUNT(*) AS n_metricas
            FROM pipeline_stages
            WHERE job_id IS NOT NULL AND job_id <> ''
        """
        params: list = []
        if pipeline:
            sql += " AND pipeline = ?"
            params.append(pipeline)
        sql += " GROUP BY job_id, pipeline ORDER BY fim_ts DESC LIMIT ?"
        params.append(max(1, min(int(limit), 50)))
        rows = conn.execute(sql, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"[obs.db] jobs_recentes falhou: {e}")
        return []


def resumo_por_job(job_id: str, pipeline: str | None = None) -> list[dict]:
    """Agrega as métricas de um único job por etapa.

    Etapas como ``vertical_encode`` aparecem uma vez por Short; por isso o
    ``total_duration_ms`` é SUM e ``n`` mostra quantos itens contribuíram.
    Etapas aninhadas (ex.: vertical e vertical_encode) não devem ser somadas
    entre si; o painel deixa isso explícito.
    """
    if not job_id:
        return []
    try:
        conn = _connect()
        sql = """
            SELECT
                pipeline,
                stage,
                COUNT(*) AS n,
                SUM(duration_ms) AS total_duration_ms,
                AVG(duration_ms) AS media_duration_ms,
                MAX(duration_ms) AS max_duration_ms,
                AVG(CASE WHEN COALESCE(measurement_version, 1) >= 2 THEN peak_rss_mb END) AS media_peak_rss_mb,
                MAX(CASE WHEN COALESCE(measurement_version, 1) >= 2 THEN peak_rss_mb END) AS max_peak_rss_mb,
                MIN(min_available_mb) AS min_available_mb,
                AVG(avg_cpu_pct) AS media_cpu_pct,
                MAX(peak_cpu_pct) AS max_peak_cpu_pct,
                SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) AS n_erros
            FROM pipeline_stages
            WHERE job_id = ?
        """
        params: list = [job_id]
        if pipeline:
            sql += " AND pipeline = ?"
            params.append(pipeline)
        sql += " GROUP BY pipeline, stage ORDER BY CASE WHEN stage='total' THEN 0 ELSE 1 END, total_duration_ms DESC"
        rows = conn.execute(sql, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"[obs.db] resumo_por_job falhou: {e}")
        return []


def etapas_do_job(job_id: str, pipeline: str | None = None, limit: int = 200) -> list[dict]:
    """Linhas de telemetria de um job específico em ordem cronológica."""
    if not job_id:
        return []
    try:
        conn = _connect()
        sql = """
            SELECT job_id, pipeline, stage, ts, duration_ms, peak_rss_mb,
                   min_available_mb, peak_system_mem_pct, avg_cpu_pct,
                   peak_cpu_pct, measurement_version, status, detail
            FROM pipeline_stages
            WHERE job_id = ?
        """
        params: list = [job_id]
        if pipeline:
            sql += " AND pipeline = ?"
            params.append(pipeline)
        sql += " ORDER BY ts ASC LIMIT ?"
        params.append(max(1, min(int(limit), 500)))
        rows = conn.execute(sql, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"[obs.db] etapas_do_job falhou: {e}")
        return []

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
                source_fidelity, completeness, hallucination, judge_score,
                model, prompt_version, rationale)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (row.get("trace_id"), row.get("ts", time.time()), row.get("target"),
             row.get("groundedness"), row.get("relevance"), row.get("coherence"),
             row.get("source_fidelity"), row.get("completeness"),
             int(bool(row.get("hallucination"))), row.get("judge_score"),
             row.get("model"), row.get("prompt_version"), row.get("rationale")),
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


def insert_benchmark(row: dict) -> None:
    try:
        import json
        conn = _connect()
        conn.execute(
            """INSERT INTO benchmark_runs
               (ts, suite, case_id, label, target, trace_id, judge_model,
                prompt_version, groundedness, relevance, source_fidelity,
                completeness, judge_score, hallucination, gate_status, gate_failures)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (row.get("ts", time.time()), row.get("suite"), row.get("case_id"),
             row.get("label"), row.get("target"), row.get("trace_id"),
             row.get("judge_model"), row.get("prompt_version"),
             row.get("groundedness"), row.get("relevance"),
             row.get("source_fidelity"), row.get("completeness"),
             row.get("judge_score"), int(bool(row.get("hallucination"))),
             row.get("gate_status"), json.dumps(row.get("gate_failures") or [], ensure_ascii=False)),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[obs.db] insert_benchmark falhou: {e}")


def insert_security_event(row: dict) -> None:
    try:
        import json
        conn = _connect()
        conn.execute(
            """INSERT INTO security_events
               (ts,event_type,action,user_key,target,trace_id,risk,reasons_json,metadata_json)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (row.get("ts", time.time()), row.get("event_type"), row.get("action"),
             row.get("user_key"), row.get("target"), row.get("trace_id"), row.get("risk"),
             json.dumps(row.get("reasons") or [], ensure_ascii=False),
             json.dumps(row.get("metadata") or {}, ensure_ascii=False)),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[obs.db] insert_security_event falhou: {e}")



def ux_analytics(days: int = 30) -> dict:
    """Agrega telemetria UX mínima sem expor identidade ou conteúdo do usuário."""
    days = max(1, min(365, int(days or 30)))
    since = time.time() - (days * 86400)
    try:
        conn = _connect()
        rows = conn.execute(
            "SELECT event, page, COUNT(*) AS total, COUNT(DISTINCT user_key) AS users "
            "FROM ux_events WHERE ts >= ? GROUP BY event, page ORDER BY total DESC",
            (since,),
        ).fetchall()
        conn.close()
    except Exception as e:
        print(f"[obs.db] ux_analytics falhou: {e}")
        return {"days": days, "events": [], "funnels": {}}

    events = [dict(r) for r in rows]
    by_event = {r["event"]: r for r in events}
    def users(name): return int((by_event.get(name) or {}).get("users") or 0)
    def rate(num, den): return round((num / den) * 100, 1) if den else None

    home = users("home_view")
    home_actions = len(set())
    # A soma de usuários por evento pode duplicar pessoas; para o funil usamos
    # consultas por conjuntos, preservando a métrica sem armazenar conteúdo.
    try:
        conn = _connect()
        def user_set(names):
            q = ",".join("?" for _ in names)
            rs = conn.execute(
                f"SELECT DISTINCT user_key FROM ux_events WHERE ts >= ? AND event IN ({q}) AND user_key != ''",
                (since, *names),
            ).fetchall()
            return {r[0] for r in rs}
        home_users = user_set(["home_view"])
        action_users = user_set(["continue_learning_click","learn_click","create_click","trends_click"])
        trends_users = user_set(["trends_view"])
        opened_users = user_set(["trend_opened"])
        create_users = user_set(["trend_create_content_clicked"])
        completed_users = user_set(["trend_analysis_completed"])
        failed_users = user_set(["trend_analysis_failed"])
        conn.close()
    except Exception:
        home_users=action_users=trends_users=opened_users=create_users=completed_users=failed_users=set()

    return {
        "days": days,
        "events": events,
        "funnels": {
            "home": {"views": len(home_users), "acted": len(home_users & action_users), "action_rate": rate(len(home_users & action_users), len(home_users))},
            "trends": {
                "views": len(trends_users),
                "analysis_completed": len(trends_users & completed_users),
                "opened": len(trends_users & opened_users),
                "create_clicked": len(trends_users & create_users),
                "open_rate": rate(len(trends_users & opened_users), len(trends_users)),
                "create_rate": rate(len(trends_users & create_users), len(trends_users)),
                "analysis_failed": len(failed_users),
            },
        },
        "privacy": {"content_collected": False, "raw_identity_exposed": False},
    }


def insert_ux_event(event: str, page: str = "", user_key: str = "") -> None:
    """Persiste eventos UX allow-listed sem payload de conteúdo do usuário."""
    try:
        conn = _connect()
        conn.execute(
            "INSERT INTO ux_events (ts,event,page,user_key) VALUES (?,?,?,?)",
            (time.time(), event, page, user_key),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[obs.db] insert_ux_event falhou: {e}")

def insert_model_comparison(row: dict) -> None:
    try:
        conn = _connect()
        conn.execute(
            """INSERT INTO model_comparisons
               (ts,comparison_id,provider,model,latency_ms,status,response_text,error,
                judge_score,groundedness,relevance)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (row.get("ts", time.time()), row.get("comparison_id"),
             row.get("provider"), row.get("model"), row.get("latency_ms"),
             row.get("status"), row.get("response_text"), row.get("error"),
             row.get("judge_score"), row.get("groundedness"), row.get("relevance")),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[obs.db] insert_model_comparison falhou: {e}")


def insert_context_snapshot(row: dict) -> None:
    """Persiste SOMENTE contagens/metadata do contexto; nunca o prompt em claro."""
    try:
        conn = _connect()
        conn.execute(
            """INSERT INTO context_snapshots
               (trace_id, ts, operation, provider, model, context_limit, used_tokens,
                system_tokens, tool_tokens, skill_tokens, memory_tokens,
                conversation_tokens, retrieved_tokens, unattributed_tokens,
                reserve_tokens, input_hash, status, cost_usd)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (row.get("trace_id"), row.get("ts", time.time()), row.get("operation"),
             row.get("provider"), row.get("model"), row.get("context_limit"),
             row.get("used_tokens"), row.get("system_tokens"), row.get("tool_tokens"),
             row.get("skill_tokens"), row.get("memory_tokens"),
             row.get("conversation_tokens"), row.get("retrieved_tokens"),
             row.get("unattributed_tokens"), row.get("reserve_tokens"),
             row.get("input_hash"), row.get("status"), row.get("cost_usd")),
        )
        conn.commit(); conn.close()
    except Exception as e:
        print(f"[obs.db] insert_context_snapshot falhou: {e}")


def recent_context_snapshots(limit: int = 30) -> list[dict]:
    try:
        conn = _connect()
        rows = conn.execute(
            """SELECT id, trace_id, ts, operation, provider, model, context_limit, used_tokens,
                      system_tokens, tool_tokens, skill_tokens, memory_tokens,
                      conversation_tokens, retrieved_tokens, unattributed_tokens,
                      reserve_tokens, input_hash, status, cost_usd
                 FROM context_snapshots ORDER BY ts DESC LIMIT ?""",
            (max(1, min(int(limit), 200)),),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"[obs.db] recent_context_snapshots falhou: {e}")
        return []


def duplicate_context_count(input_hash: str | None, days: int = 7) -> int:
    if not input_hash:
        return 0
    try:
        conn = _connect()
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM context_snapshots WHERE input_hash=? AND ts>=?",
            (input_hash, time.time() - days * 86400),
        ).fetchone()
        conn.close()
        return int(row["n"] or 0)
    except Exception:
        return 0
