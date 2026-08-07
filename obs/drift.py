"""
obs/drift.py — detecção de drift de IA.

Compara uma janela RECENTE com uma janela BASELINE (anterior) sobre a série
temporal que já gravamos em `traces` e `evals`, e dispara alertas quando uma
métrica de qualidade/operação piora além do limiar.

Métricas comparadas por janela:
  - latência média e p95 (traces)
  - taxa de erro (traces)
  - custo médio por chamada (traces)
  - judge_score médio (evals)
  - taxa de alucinação (evals)
  - taxa de acerto de cache (traces)

Direção do "ruim": latência↑, erro↑, custo↑, judge↓, alucinação↑.
Tudo configurável por env. Não chama LLM — só lê o que já existe.
"""

from __future__ import annotations

import json
import os
import time

from . import db

# Janelas (horas)
RECENT_H = float(os.getenv("DRIFT_RECENT_HOURS", "24"))
BASELINE_H = float(os.getenv("DRIFT_BASELINE_HOURS", "168"))  # 7 dias antes

# Limiares de alerta
TH_LATENCY_PCT = float(os.getenv("DRIFT_LATENCY_PCT", "0.30"))      # +30% p95
TH_ERROR_ABS = float(os.getenv("DRIFT_ERROR_ABS", "0.05"))         # +5 p.p.
TH_COST_PCT = float(os.getenv("DRIFT_COST_PCT", "0.50"))           # +50%
TH_JUDGE_DROP = float(os.getenv("DRIFT_JUDGE_DROP_ABS", "0.10"))   # -0.10
TH_HALLUC_ABS = float(os.getenv("DRIFT_HALLUC_ABS", "0.10"))       # +10 p.p.

MIN_SAMPLES = int(os.getenv("DRIFT_MIN_SAMPLES", "5"))


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    k = (len(values) - 1) * 0.95
    lo = int(k)
    hi = min(lo + 1, len(values) - 1)
    return round(values[lo] + (values[hi] - values[lo]) * (k - lo), 2)


def _window_metrics(ts_from: float, ts_to: float) -> dict:
    traces = db.query(
        "SELECT status, latency_ms, cost_usd FROM traces WHERE ts>=? AND ts<?",
        (ts_from, ts_to),
    )
    evals = db.query(
        "SELECT judge_score, hallucination FROM evals WHERE ts>=? AND ts<?",
        (ts_from, ts_to),
    )

    n = len(traces)
    real = [t for t in traces if t["status"] in ("ok", "error", "circuit_open")]
    errors = sum(1 for t in traces if t["status"] in ("error", "circuit_open"))
    hits = sum(1 for t in traces if t["status"] == "cache_hit")
    lat = [t["latency_ms"] or 0 for t in traces if t["status"] == "ok"]
    costs = [t["cost_usd"] or 0 for t in real]

    return {
        "calls": n,
        "samples": len(real),
        "error_rate": round(errors / len(real), 4) if real else 0.0,
        "avg_latency_ms": round(sum(lat) / len(lat), 2) if lat else 0.0,
        "p95_latency_ms": _p95(lat),
        "avg_cost_usd": round(sum(costs) / len(costs), 6) if costs else 0.0,
        "cache_hit_rate": round(hits / n, 4) if n else 0.0,
        "avg_judge_score": round(
            sum(e["judge_score"] or 0 for e in evals) / len(evals), 4
        ) if evals else None,
        "hallucination_rate": round(
            sum(1 for e in evals if e["hallucination"]) / len(evals), 4
        ) if evals else None,
        "n_evals": len(evals),
    }


def _pct_change(base: float, recent: float) -> float | None:
    if base in (0, None):
        return None
    return round((recent - base) / base, 4)


def compute(recent_h: float = RECENT_H, baseline_h: float = BASELINE_H) -> dict:
    now = time.time()
    recent_from = now - recent_h * 3600
    base_from = recent_from - baseline_h * 3600

    recent = _window_metrics(recent_from, now)
    baseline = _window_metrics(base_from, recent_from)

    alerts: list[dict] = []

    def alert(metric, severity, msg, b, r):
        alerts.append({"metric": metric, "severity": severity,
                       "message": msg, "baseline": b, "recent": r})

    enough = (baseline["samples"] >= MIN_SAMPLES and
              recent["samples"] >= MIN_SAMPLES)

    if enough:
        # latência p95
        ch = _pct_change(baseline["p95_latency_ms"], recent["p95_latency_ms"])
        if ch is not None and ch > TH_LATENCY_PCT:
            alert("p95_latency_ms", "warning",
                  f"Latência p95 subiu {ch*100:.0f}%",
                  baseline["p95_latency_ms"], recent["p95_latency_ms"])
        # erro
        de = recent["error_rate"] - baseline["error_rate"]
        if de > TH_ERROR_ABS:
            alert("error_rate", "critical",
                  f"Taxa de erro subiu {de*100:.1f} p.p.",
                  baseline["error_rate"], recent["error_rate"])
        # custo
        cc = _pct_change(baseline["avg_cost_usd"], recent["avg_cost_usd"])
        if cc is not None and cc > TH_COST_PCT:
            alert("avg_cost_usd", "warning",
                  f"Custo médio/chamada subiu {cc*100:.0f}%",
                  baseline["avg_cost_usd"], recent["avg_cost_usd"])

    # qualidade (evals) — só se houver evals nas duas janelas
    if (baseline["avg_judge_score"] is not None and
            recent["avg_judge_score"] is not None):
        dj = baseline["avg_judge_score"] - recent["avg_judge_score"]
        if dj > TH_JUDGE_DROP:
            alert("avg_judge_score", "critical",
                  f"Qualidade (judge) caiu {dj:.2f}",
                  baseline["avg_judge_score"], recent["avg_judge_score"])
    if (baseline["hallucination_rate"] is not None and
            recent["hallucination_rate"] is not None):
        dh = recent["hallucination_rate"] - baseline["hallucination_rate"]
        if dh > TH_HALLUC_ABS:
            alert("hallucination_rate", "critical",
                  f"Alucinação subiu {dh*100:.1f} p.p.",
                  baseline["hallucination_rate"], recent["hallucination_rate"])

    return {
        "ts": now,
        "window": {"recent_h": recent_h, "baseline_h": baseline_h},
        "baseline": baseline,
        "recent": recent,
        "enough_data": enough,
        "status": "alert" if alerts else "ok",
        "alerts": alerts,
    }


def run_check(recent_h: float = RECENT_H, baseline_h: float = BASELINE_H) -> dict:
    """Computa e PERSISTE um snapshot de drift (histórico em drift_runs)."""
    report = compute(recent_h, baseline_h)
    db.execute(
        """INSERT INTO drift_runs
           (ts, recent_h, baseline_h, status, n_alerts, metrics_json, alerts_json)
           VALUES (?,?,?,?,?,?,?)""",
        (report["ts"], recent_h, baseline_h, report["status"],
         len(report["alerts"]),
         json.dumps({"baseline": report["baseline"], "recent": report["recent"]},
                    ensure_ascii=False),
         json.dumps(report["alerts"], ensure_ascii=False)),
    )
    return report


def history(limit: int = 20) -> list[dict]:
    rows = db.query(
        "SELECT ts, status, n_alerts, recent_h, baseline_h "
        "FROM drift_runs ORDER BY ts DESC LIMIT ?",
        (limit,),
    )
    return rows
