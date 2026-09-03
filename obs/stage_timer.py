"""
obs/stage_timer.py — telemetria leve de performance por etapa.

Mede wall-clock, memória do PROCESS TREE (Python + filhos como ffmpeg),
memória disponível do host e CPU global enquanto a etapa roda.

Por que process tree? MoviePy/ffmpeg fazem o trabalho pesado em subprocessos.
Medir apenas o RSS do processo Python subestima justamente as etapas que mais
importam para decidir paralelismo (corte/vertical).

Fail-open: telemetria nunca pode quebrar o pipeline principal.
"""

from __future__ import annotations

import threading
import time
from contextlib import contextmanager

try:
    import psutil
    _PSUTIL_OK = True
except ImportError:  # pragma: no cover
    _PSUTIL_OK = False


class _AmostradorRecursos:
    """Amostra recursos do processo e do host durante uma etapa.

    - tree_rss: soma RSS do processo atual + todos os filhos vivos (ffmpeg etc.)
    - available: menor memória disponível observada no host
    - system_mem_pct: maior pressão de memória observada no host
    - cpu_pct: CPU global; útil porque no Hetzner há outros serviços concorrendo
      pelos mesmos vCPUs e olhar só o processo do worker seria enganoso.
    """

    def __init__(self, intervalo_s: float = 0.25):
        self.intervalo_s = intervalo_s
        self.peak_tree_rss_mb = 0.0
        self.min_available_mb = None
        self.peak_system_mem_pct = 0.0
        self.peak_cpu_pct = 0.0
        self._cpu_sum = 0.0
        self._cpu_samples = 0
        self._parar = threading.Event()
        self._thread = None
        self._processo = psutil.Process() if _PSUTIL_OK else None

    def _tree_rss_mb(self) -> float:
        if not self._processo:
            return 0.0
        total = 0
        processos = [self._processo]
        try:
            processos.extend(self._processo.children(recursive=True))
        except Exception:
            pass
        for proc in processos:
            try:
                total += proc.memory_info().rss
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
            except Exception:
                continue
        return total / (1024 * 1024)

    def _sample(self):
        try:
            rss_mb = self._tree_rss_mb()
            if rss_mb > self.peak_tree_rss_mb:
                self.peak_tree_rss_mb = rss_mb
        except Exception:
            pass

        try:
            vm = psutil.virtual_memory()
            available_mb = vm.available / (1024 * 1024)
            if self.min_available_mb is None or available_mb < self.min_available_mb:
                self.min_available_mb = available_mb
            if vm.percent > self.peak_system_mem_pct:
                self.peak_system_mem_pct = float(vm.percent)
        except Exception:
            pass

        try:
            cpu = float(psutil.cpu_percent(interval=None))
            self._cpu_sum += cpu
            self._cpu_samples += 1
            if cpu > self.peak_cpu_pct:
                self.peak_cpu_pct = cpu
        except Exception:
            pass

    def _loop(self):
        # Faz uma amostra imediatamente para etapas curtas não ficarem sem dado.
        self._sample()
        while not self._parar.wait(self.intervalo_s):
            self._sample()

    def iniciar(self):
        if not _PSUTIL_OK:
            return
        # Inicializa o contador de cpu_percent antes da thread de amostragem.
        try:
            psutil.cpu_percent(interval=None)
        except Exception:
            pass
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def parar(self) -> dict:
        if not _PSUTIL_OK:
            return {
                "peak_rss_mb": None,
                "min_available_mb": None,
                "peak_system_mem_pct": None,
                "avg_cpu_pct": None,
                "peak_cpu_pct": None,
            }
        # Amostra final para capturar etapas muito curtas ou pico próximo do fim.
        self._sample()
        self._parar.set()
        if self._thread:
            self._thread.join(timeout=1.0)
        avg_cpu = self._cpu_sum / self._cpu_samples if self._cpu_samples else None
        return {
            # Mantemos o nome peak_rss_mb por compatibilidade com schema/UI,
            # mas a semântica agora é PROCESS TREE RSS (mais correta para ffmpeg).
            "peak_rss_mb": round(self.peak_tree_rss_mb, 1),
            "min_available_mb": round(self.min_available_mb, 1) if self.min_available_mb is not None else None,
            "peak_system_mem_pct": round(self.peak_system_mem_pct, 1),
            "avg_cpu_pct": round(avg_cpu, 1) if avg_cpu is not None else None,
            "peak_cpu_pct": round(self.peak_cpu_pct, 1),
        }


class MedicaoEtapa:
    """Medição manual, útil para abranger um pipeline inteiro sem reindentar
    toda a função. `finalizar()` é idempotente."""

    def __init__(self, job_id: str, pipeline: str, stage: str, detail: str = ""):
        self.job_id = job_id
        self.pipeline = pipeline
        self.stage = stage
        self.detail = detail
        self._inicio = time.monotonic()
        self._amostrador = _AmostradorRecursos()
        self._amostrador.iniciar()
        self._finalizado = False

    def finalizar(self, status: str = "ok", detail: str | None = None) -> None:
        if self._finalizado:
            return
        self._finalizado = True
        duration_ms = round((time.monotonic() - self._inicio) * 1000, 1)
        recursos = self._amostrador.parar()
        try:
            from obs import db as obs_db
            obs_db.insert_pipeline_stage({
                "job_id": self.job_id,
                "pipeline": self.pipeline,
                "stage": self.stage,
                "duration_ms": duration_ms,
                "status": status,
                "measurement_version": 2,
                "detail": self.detail if detail is None else detail,
                **recursos,
            })
        except Exception as e:
            print(f"[stage_timer] falha ao gravar métrica de '{self.stage}' (não afeta o pipeline): {e}")


def iniciar_medicao(job_id: str, pipeline: str, stage: str, detail: str = "") -> MedicaoEtapa:
    return MedicaoEtapa(job_id, pipeline, stage, detail)


@contextmanager
def medir_etapa(job_id: str, pipeline: str, stage: str, detail: str = ""):
    """Context manager para medir uma etapa. Exceções continuam propagando."""
    medicao = MedicaoEtapa(job_id, pipeline, stage, detail)
    status = "ok"
    try:
        yield
    except Exception:
        status = "error"
        raise
    finally:
        medicao.finalizar(status=status)
