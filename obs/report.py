"""
obs/report.py — agregações para o dashboard de observabilidade.

Lê o store e devolve um resumo: custo total e por modelo, latência p50/p95 por
operação, volume de chamadas, taxa de erro, feedback 👍/👎 e médias dos evals.
"""

from __future__ import annotations

from . import db


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    k = (len(values) - 1) * pct
    lo = int(k)
    hi = min(lo + 1, len(values) - 1)
    return round(values[lo] + (values[hi] - values[lo]) * (k - lo), 2)


def summary() -> dict:
    traces = db.query("SELECT * FROM traces ORDER BY ts DESC LIMIT 5000")

    total_calls = len(traces)
    total_cost = round(sum(t["cost_usd"] or 0 for t in traces), 6)
    errors = sum(1 for t in traces if t["status"] != "ok")
    error_rate = round(errors / total_calls, 4) if total_calls else 0.0

    # custo por modelo
    by_model: dict[str, dict] = {}
    for t in traces:
        m = t["model"] or "?"
        b = by_model.setdefault(m, {"calls": 0, "cost_usd": 0.0,
                                    "in_tokens": 0, "out_tokens": 0})
        b["calls"] += 1
        b["cost_usd"] = round(b["cost_usd"] + (t["cost_usd"] or 0), 6)
        b["in_tokens"] += t["input_tokens"] or 0
        b["out_tokens"] += t["output_tokens"] or 0

    # latência por operação (p50/p95)
    lat: dict[str, list] = {}
    for t in traces:
        lat.setdefault(t["operation"] or "?", []).append(t["latency_ms"] or 0)
    by_op = {
        op: {
            "calls": len(v),
            "p50_ms": _percentile(v, 0.50),
            "p95_ms": _percentile(v, 0.95),
        }
        for op, v in lat.items()
    }

    # feedback
    fb = db.query("SELECT vote, COUNT(*) n FROM feedback GROUP BY vote")
    up = next((r["n"] for r in fb if r["vote"] == 1), 0)
    down = next((r["n"] for r in fb if r["vote"] == -1), 0)

    # evals
    ev = db.query(
        "SELECT AVG(groundedness) g, AVG(relevance) r, AVG(coherence) c, "
        "AVG(judge_score) s, AVG(hallucination) h, COUNT(*) n FROM evals"
    )
    ev = ev[0] if ev else {}

    # cache semântico: acertos viram traces status='cache_hit' (custo 0).
    hits = sum(1 for t in traces if t["status"] == "cache_hit")
    # custo médio real por operação (apenas chamadas 'ok') p/ estimar economia.
    avg_cost: dict[str, float] = {}
    cnt: dict[str, int] = {}
    for t in traces:
        if t["status"] == "ok":
            op = t["operation"] or "?"
            avg_cost[op] = avg_cost.get(op, 0.0) + (t["cost_usd"] or 0)
            cnt[op] = cnt.get(op, 0) + 1
    for op in avg_cost:
        avg_cost[op] = avg_cost[op] / cnt[op] if cnt[op] else 0.0
    saved = round(sum(
        avg_cost.get(t["operation"] or "?", 0.0)
        for t in traces if t["status"] == "cache_hit"
    ), 6)
    real_calls = sum(1 for t in traces if t["status"] in ("ok", "error"))
    entries = db.query("SELECT COUNT(*) c FROM llm_cache")
    cache_entries = entries[0]["c"] if entries else 0

    # ── FinOps: tokens, custo por operação e gasto por dia ──
    import datetime
    total_in = sum(t["input_tokens"] or 0 for t in traces)
    total_out = sum(t["output_tokens"] or 0 for t in traces)
    cost_by_op: dict[str, dict] = {}
    for t in traces:
        op = t["operation"] or "?"
        b = cost_by_op.setdefault(op, {"calls": 0, "cost_usd": 0.0,
                                       "in_tokens": 0, "out_tokens": 0})
        b["calls"] += 1
        b["cost_usd"] = round(b["cost_usd"] + (t["cost_usd"] or 0), 6)
        b["in_tokens"] += t["input_tokens"] or 0
        b["out_tokens"] += t["output_tokens"] or 0

    spend_by_day: dict[str, float] = {}
    for t in traces:
        if not t["ts"]:
            continue
        day = datetime.date.fromtimestamp(t["ts"]).isoformat()
        spend_by_day[day] = round(spend_by_day.get(day, 0.0) + (t["cost_usd"] or 0), 6)
    days_active = len(spend_by_day) or 1
    projected_month = round((total_cost / days_active) * 30, 4)

    # ── RAG: chamadas de relevância e de resposta ancorada ──
    rag_ops = ("rag_answer", "topic_relevance")
    rag_traces = [t for t in traces if (t["operation"] or "") in rag_ops]
    rag_lat = [t["latency_ms"] or 0 for t in rag_traces if t["status"] == "ok"]
    rag = {
        "queries": sum(1 for t in rag_traces if t["operation"] == "rag_answer"),
        "relevance_calls": sum(1 for t in rag_traces if t["operation"] == "topic_relevance"),
        "cost_usd": round(sum(t["cost_usd"] or 0 for t in rag_traces), 6),
        "p50_ms": _percentile(rag_lat, 0.50),
        "p95_ms": _percentile(rag_lat, 0.95),
        "indexed_chunks": None,   # preenchido pelo endpoint (best-effort)
    }

    return {
        "totals": {
            "calls": total_calls,
            "cost_usd": total_cost,
            "errors": errors,
            "error_rate": error_rate,
        },
        "cache": {
            "hits": hits,
            "entries": cache_entries,
            "hit_rate": round(hits / (hits + real_calls), 3) if (hits + real_calls) else 0.0,
            "estimated_saved_usd": saved,
        },
        "by_model": by_model,
        "by_operation": by_op,
        "feedback": {"up": up, "down": down,
                     "ratio": round(up / (up + down), 3) if (up + down) else None},
        "evals": {
            "count": ev.get("n") or 0,
            "avg_groundedness": round(ev.get("g") or 0, 3),
            "avg_relevance": round(ev.get("r") or 0, 3),
            "avg_coherence": round(ev.get("c") or 0, 3),
            "avg_judge_score": round(ev.get("s") or 0, 3),
            "hallucination_rate": round(ev.get("h") or 0, 3),
        },
        "finops": {
            "total_cost_usd": total_cost,
            "total_in_tokens": total_in,
            "total_out_tokens": total_out,
            "total_tokens": total_in + total_out,
            "projected_month_usd": projected_month,
            "days_active": days_active,
            "by_operation": cost_by_op,
            "spend_by_day": dict(sorted(spend_by_day.items())),
        },
        "rag": rag,
    }


def recent_logs(limit: int = 100) -> list[dict]:
    """Log bruto: cada chamada de IA, com tudo (para a aba de eventos)."""
    return db.query(
        "SELECT ts, operation, provider, model, status, latency_ms, "
        "input_tokens, output_tokens, cost_usd, error, trace_id "
        "FROM traces ORDER BY ts DESC LIMIT ?", (limit,)
    )


def recent_evals(limit: int = 20) -> list[dict]:
    """Avaliações recentes do LLM-as-Judge, com o racional."""
    return db.query(
        "SELECT ts, target, groundedness, relevance, coherence, judge_score, "
        "hallucination, model, rationale FROM evals ORDER BY ts DESC LIMIT ?",
        (limit,)
    )


def errors_recent(limit: int = 50) -> list[dict]:
    """Apenas eventos com erro — para diagnóstico rápido."""
    return db.query(
        "SELECT ts, operation, model, status, error, trace_id FROM traces "
        "WHERE status != 'ok' AND status != 'cache_hit' "
        "ORDER BY ts DESC LIMIT ?", (limit,)
    )
