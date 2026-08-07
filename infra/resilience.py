"""
infra/resilience.py — resiliência para chamadas de IA/integrações externas.

Três mecanismos, sem dependência externa:
  - timeout: uma chamada pendurada não trava o pipeline para sempre.
  - circuit breaker por provider: depois de N falhas seguidas, "abre" e falha
    rápido por um tempo, em vez de martelar um serviço que já está caindo.
  - fail-open: opcionalmente retorna um fallback em vez de propagar a exceção,
    para que uma sub-parte de IA não derrube o app inteiro.

Uso típico:
    guard("openai", fn, *args, timeout=60)                  # erro propaga
    guard("anthropic", fn, *args, timeout=60, fallback=[])  # fail-open p/ []
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import Any, Callable

# Sentinela: distingue "sem fallback" (propaga erro) de "fallback=None".
_RAISE = object()


class CircuitOpenError(RuntimeError):
    """Levantado quando o breaker está aberto e a chamada é curto-circuitada."""


class CircuitBreaker:
    def __init__(self, name: str, fail_max: int = 5, reset_timeout: float = 30.0):
        self.name = name
        self.fail_max = fail_max
        self.reset_timeout = reset_timeout
        self._lock = threading.Lock()
        self._fails = 0
        self._opened_at = 0.0
        self._state = "closed"  # closed | open | half_open

    @property
    def state(self) -> str:
        with self._lock:
            if self._state == "open" and \
               (time.monotonic() - self._opened_at) >= self.reset_timeout:
                self._state = "half_open"
            return self._state

    def _on_success(self) -> None:
        with self._lock:
            self._fails = 0
            self._state = "closed"

    def _on_failure(self) -> None:
        with self._lock:
            self._fails += 1
            if self._fails >= self.fail_max:
                self._state = "open"
                self._opened_at = time.monotonic()

    def call(self, fn: Callable, *args, timeout: float | None = None, **kwargs) -> Any:
        if self.state == "open":
            raise CircuitOpenError(f"circuit '{self.name}' aberto")
        try:
            if timeout:
                with ThreadPoolExecutor(max_workers=1) as ex:
                    result = ex.submit(fn, *args, **kwargs).result(timeout=timeout)
            else:
                result = fn(*args, **kwargs)
        except Exception:
            self._on_failure()
            raise
        self._on_success()
        return result


# Um breaker por provider (compartilhado entre chamadas).
_breakers: dict[str, CircuitBreaker] = {}
_breakers_lock = threading.Lock()


def breaker(name: str) -> CircuitBreaker:
    with _breakers_lock:
        if name not in _breakers:
            _breakers[name] = CircuitBreaker(name)
        return _breakers[name]


def guard(
    name: str,
    fn: Callable,
    *args,
    timeout: float | None = 60.0,
    fallback: Any = _RAISE,
    **kwargs,
) -> Any:
    """
    Executa fn com timeout + circuit breaker do provider `name`.

    fallback=_RAISE (padrão): erros propagam (use para etapas críticas).
    fallback=<valor>: fail-open — em qualquer falha, retorna <valor> e segue.
    """
    try:
        return breaker(name).call(fn, *args, timeout=timeout, **kwargs)
    except (Exception, FuturesTimeout):
        if fallback is _RAISE:
            raise
        return fallback
