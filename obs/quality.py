"""obs/quality.py — Quality Gates para IA generativa.

Transforma métricas do LLM-as-Judge em critérios objetivos de aceite. Os
limiares são configuráveis por ambiente e podem ser usados tanto para uma
resposta individual quanto para uma janela agregada de avaliações.

Importante: gate sem amostra suficiente fica como ``insufficient_data`` em vez
de fingir aprovação. Isso deixa a evidência do case tecnicamente defensável.
"""

from __future__ import annotations

import os

from . import db

MIN_GROUNDEDNESS = float(os.getenv("QUALITY_MIN_GROUNDEDNESS", "0.85"))
MIN_RELEVANCE = float(os.getenv("QUALITY_MIN_RELEVANCE", "0.85"))
MIN_SOURCE_FIDELITY = float(os.getenv("QUALITY_MIN_SOURCE_FIDELITY", "0.90"))
MIN_COMPLETENESS = float(os.getenv("QUALITY_MIN_COMPLETENESS", "0.80"))
MIN_JUDGE_SCORE = float(os.getenv("QUALITY_MIN_JUDGE_SCORE", "0.85"))
MAX_HALLUCINATION_RATE = float(os.getenv("QUALITY_MAX_HALLUCINATION_RATE", "0.05"))
MIN_SAMPLES = int(os.getenv("QUALITY_MIN_SAMPLES", "3"))


def thresholds() -> dict:
    return {
        "groundedness": MIN_GROUNDEDNESS,
        "relevance": MIN_RELEVANCE,
        "source_fidelity": MIN_SOURCE_FIDELITY,
        "completeness": MIN_COMPLETENESS,
        "judge_score": MIN_JUDGE_SCORE,
        "hallucination_rate": MAX_HALLUCINATION_RATE,
        "min_samples": MIN_SAMPLES,
    }


def evaluate_verdict(verdict: dict) -> dict:
    """Aplica gates a um único veredito já produzido pelo judge."""
    checks = {
        "groundedness": (verdict.get("groundedness") or 0) >= MIN_GROUNDEDNESS,
        "relevance": (verdict.get("relevance") or 0) >= MIN_RELEVANCE,
        "source_fidelity": (verdict.get("source_fidelity") or 0) >= MIN_SOURCE_FIDELITY,
        "completeness": (verdict.get("completeness") or 0) >= MIN_COMPLETENESS,
        "judge_score": (verdict.get("judge_score") or 0) >= MIN_JUDGE_SCORE,
        "hallucination": not bool(verdict.get("hallucination")),
    }
    failures = [name for name, ok in checks.items() if not ok]
    return {
        "status": "pass" if not failures else "fail",
        "passed": not failures,
        "checks": checks,
        "failures": failures,
        "thresholds": thresholds(),
    }


def aggregate(target: str | None = None, limit: int = 200) -> dict:
    """Calcula o quality gate agregado nas avaliações mais recentes."""
    params: tuple = ()
    where = ""
    if target:
        where = "WHERE target=?"
        params = (target,)
    rows = db.query(
        f"SELECT groundedness, relevance, source_fidelity, completeness, "
        f"judge_score, hallucination FROM evals {where} ORDER BY ts DESC LIMIT ?",
        params + (max(1, min(int(limit), 2000)),),
    )
    n = len(rows)
    if not rows:
        return {
            "status": "insufficient_data", "passed": False, "samples": 0,
            "metrics": {}, "checks": {}, "failures": [],
            "thresholds": thresholds(),
        }

    def avg(key: str) -> float:
        vals = [float(r[key]) for r in rows if r.get(key) is not None]
        return round(sum(vals) / len(vals), 4) if vals else 0.0

    metrics = {
        "groundedness": avg("groundedness"),
        "relevance": avg("relevance"),
        "source_fidelity": avg("source_fidelity"),
        "completeness": avg("completeness"),
        "judge_score": avg("judge_score"),
        "hallucination_rate": round(sum(1 for r in rows if r.get("hallucination")) / n, 4),
    }
    checks = {
        "groundedness": metrics["groundedness"] >= MIN_GROUNDEDNESS,
        "relevance": metrics["relevance"] >= MIN_RELEVANCE,
        "source_fidelity": metrics["source_fidelity"] >= MIN_SOURCE_FIDELITY,
        "completeness": metrics["completeness"] >= MIN_COMPLETENESS,
        "judge_score": metrics["judge_score"] >= MIN_JUDGE_SCORE,
        "hallucination_rate": metrics["hallucination_rate"] <= MAX_HALLUCINATION_RATE,
    }
    failures = [name for name, ok in checks.items() if not ok]
    enough = n >= MIN_SAMPLES
    status = "insufficient_data" if not enough else ("pass" if not failures else "fail")
    return {
        "status": status,
        "passed": enough and not failures,
        "samples": n,
        "metrics": metrics,
        "checks": checks,
        "failures": failures,
        "thresholds": thresholds(),
    }
