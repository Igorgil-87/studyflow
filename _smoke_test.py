"""Smoke test da camada infra em modo inline (sem Redis, sem tools reais)."""
import os, time
os.environ["RUN_MODE"] = "inline"

from infra import bus, jobs
from infra.dispatch import dispatch
from infra.resilience import guard, breaker, CircuitOpenError

# pipeline falso que usa o mesmo contrato dos reais
def fake_pipeline(job_id, topic):
    bus.publish(job_id, "progress", {"step": "search", "status": "running", "detail": topic})
    time.sleep(0.05)
    bus.publish(job_id, "progress", {"step": "search", "status": "done"})
    jobs.set(job_id, "quiz", {"tema": topic, "ok": True})
    bus.publish(job_id, "complete", {"quiz": {"tema": topic}})
    jobs.set(job_id, "done", True)
    bus.end(job_id)

import sys, types
mod = types.ModuleType("fakemod")
mod.fake_pipeline = fake_pipeline
sys.modules["fakemod"] = mod

print("── Teste 1: fluxo normal + assinante que conecta no início ──")
job_id = "job-abc"
jobs.create(job_id, "curso")
assert jobs.exists(job_id)
dispatch("fakemod.fake_pipeline", job_id, "redes neurais")
events = []
for event, data in bus.subscribe(job_id):
    events.append(event)
    if event == "__end__":
        break
print("   eventos recebidos:", events)
assert events == ["progress", "progress", "complete", "__end__"], events
assert jobs.get(job_id)["quiz"]["tema"] == "redes neurais"
assert jobs.get(job_id)["done"] is True
print("   OK")

print("── Teste 2: assinante ATRASADO recebe replay completo (não perde eventos) ──")
job2 = "job-late"
jobs.create(job2, "curso")
dispatch("fakemod.fake_pipeline", job2, "vikings")
time.sleep(0.3)  # deixa o pipeline TERMINAR antes de assinar
late = [ev for ev, _ in bus.subscribe(job2)]
print("   eventos recebidos no replay:", late)
assert late == ["progress", "progress", "complete", "__end__"], late
print("   OK — replay funcionou (o bug do consumidor único do original some)")

print("── Teste 3: circuit breaker abre após N falhas e falha rápido ──")
def sempre_falha():
    raise RuntimeError("provider caiu")
b = breaker("teste_provider")
b.fail_max = 3
opened = False
for i in range(5):
    try:
        guard("teste_provider", sempre_falha, timeout=2)
    except CircuitOpenError:
        opened = True
        print(f"   chamada {i+1}: CIRCUITO ABERTO (falha rápida)")
    except RuntimeError:
        print(f"   chamada {i+1}: falha normal (breaker ainda fechado)")
assert opened, "breaker deveria ter aberto"
print("   OK")

print("── Teste 4: fail-open retorna fallback em vez de propagar ──")
out = guard("outro_provider", sempre_falha, timeout=2, fallback={"degraded": True})
assert out == {"degraded": True}, out
print("   retorno degradado:", out)
print("   OK")

print("\nTODOS OS TESTES PASSARAM ✅")
