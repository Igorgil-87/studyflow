"""
seed_demo.py — popula dados SINTÉTICOS de observabilidade para demonstração.

Cria duas janelas na série temporal:
  - BASELINE (saudável): ~5 dias atrás — latência baixa, pouco erro, judge alto.
  - RECENTE (degradada): últimas horas — latência alta, mais erro, judge baixo,
    mais alucinação.

Assim a tela /obs mostra o DRIFT disparando alertas durante a apresentação,
sem precisar esperar dados reais acumularem.

⚠️  São dados FICTÍCIOS, só para demonstrar o funcionamento. Use --reset para
limpá-los antes de medir dados reais.

    python seed_demo.py            # popula
    python seed_demo.py --reset    # limpa tudo (traces/evals/feedback/drift)
"""

import random
import sys
import time

from dotenv import load_dotenv

load_dotenv()

from obs import db  # noqa: E402

OPS = [("quiz", "openai", "gpt-4o-mini"),
       ("roadmap", "openai", "gpt-4o-mini"),
       ("highlights", "openai", "gpt-4o-mini"),
       ("trends_synthesize", "anthropic", "claude-sonnet-4-6")]

HOUR = 3600


def _trace(ts, op, provider, model, latency, status, cost):
    db.insert_trace({
        "trace_id": f"demo-{int(ts)}-{random.randint(0,9999)}",
        "ts": ts, "operation": op, "provider": provider, "model": model,
        "latency_ms": latency, "status": status,
        "input_tokens": random.randint(800, 3000),
        "output_tokens": random.randint(200, 900),
        "cost_usd": cost, "error": None if status == "ok" else "demo",
    })


def _seed_window(center_ts, span_h, n, *, latency, err_rate, cost,
                 judge, halluc, hit_rate):
    for _ in range(n):
        ts = center_ts + random.uniform(-span_h * HOUR / 2, span_h * HOUR / 2)
        op, provider, model = random.choice(OPS)
        r = random.random()
        if r < hit_rate:
            _trace(ts, op, provider, model, 0.0, "cache_hit", 0.0)
            continue
        status = "error" if random.random() < err_rate else "ok"
        lat = max(50, random.gauss(latency, latency * 0.25))
        c = max(0.0, random.gauss(cost, cost * 0.3))
        _trace(ts, op, provider, model, round(lat, 1), status,
               round(c, 6) if status == "ok" else 0.0)
        # eval para parte das gerações de quiz
        if op == "quiz" and status == "ok":
            db.insert_eval({
                "trace_id": "demo", "ts": ts, "target": "quiz",
                "groundedness": min(1, max(0, random.gauss(judge, 0.06))),
                "relevance": min(1, max(0, random.gauss(judge, 0.06))),
                "coherence": min(1, max(0, random.gauss(judge, 0.06))),
                "hallucination": random.random() < halluc,
                "judge_score": min(1, max(0, random.gauss(judge, 0.05))),
                "model": model, "rationale": "demo",
            })


def reset():
    for t in ("traces", "feedback", "evals", "drift_runs"):
        db.execute(f"DELETE FROM {t}")
    print("dados de observabilidade limpos.")


def main():
    db.init()
    if "--reset" in sys.argv:
        reset()
        return

    now = time.time()
    # BASELINE saudável (~5 dias atrás)
    _seed_window(now - 5 * 24 * HOUR, span_h=24, n=120,
                 latency=780, err_rate=0.015, cost=0.0009,
                 judge=0.90, halluc=0.04, hit_rate=0.15)
    # RECENTE degradada (últimas ~12h) — separação ampla e inequívoca
    _seed_window(now - 6 * HOUR, span_h=12, n=90,
                 latency=3000, err_rate=0.16, cost=0.0020,
                 judge=0.65, halluc=0.30, hit_rate=0.10)

    print("Dados de DEMONSTRAÇÃO inseridos (baseline saudável + recente degradada).")
    print("Abra /obs e use 'Rodar verificação de drift' para ver os alertas.")
    print("Para limpar: python seed_demo.py --reset")


if __name__ == "__main__":
    main()
