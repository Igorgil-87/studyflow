"""
tools/mpt_client.py — cliente HTTP do MoneyPrinterTurbo (módulo Estúdio).

O MPT roda como serviço ao lado (Docker ou processo local, porta 8080).
Este cliente cobre o ciclo completo: criar tarefa → acompanhar progresso →
baixar o vídeo final para static/videos/.

Env:
    MPT_API_URL   (default: http://localhost:8080)  — no Compose: http://mpt-api:8080
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Callable, Optional

import requests

MPT_API_URL = os.getenv("MPT_API_URL", "http://localhost:8080").rstrip("/")
_TIMEOUT = 30  # timeout por request HTTP; a geração em si é acompanhada por polling


class MPTError(RuntimeError):
    """Erro na comunicação ou na tarefa do MoneyPrinterTurbo."""


def is_alive() -> bool:
    """Health-check rápido — usado pelo pipeline antes de despachar.

    Usa /openapi.json em vez de /ping: nesta versão do MoneyPrinterTurbo
    (v1.3.2) o router de /ping existe no código mas nunca é registrado em
    app/router.py (só video.router e llm.router são incluídos), então
    /ping sempre responde 404 mesmo com o serviço saudável. /openapi.json
    é gerado automaticamente por qualquer app FastAPI padrão.
    """
    try:
        r = requests.get(f"{MPT_API_URL}/openapi.json", timeout=5)
        return r.ok
    except requests.RequestException:
        return False


def create_video_task(
    subject: str,
    *,
    script: str = "",
    language: str = "pt-BR",
    aspect: str = "9:16",              # "9:16" (Shorts/Reels) ou "16:9"
    voice_name: str = "pt-BR-AntonioNeural-Male",  # Edge TTS gratuito, voz masculina
    clip_duration: int = 4,
    count: int = 1,
    subtitle_enabled: bool = True,
    paragraph_number: int = 1,
) -> str:
    """Cria a tarefa de geração e retorna o task_id."""
    payload = {
        "video_subject": subject,
        "video_script": script,            # vazio → o LLM do MPT gera o roteiro
        "video_language": language,
        "video_aspect": aspect,
        "video_clip_duration": clip_duration,
        "video_count": count,
        "voice_name": voice_name,
        "subtitle_enabled": subtitle_enabled,
        "paragraph_number": paragraph_number,
    }
    try:
        r = requests.post(f"{MPT_API_URL}/api/v1/videos", json=payload, timeout=_TIMEOUT)
        r.raise_for_status()
    except requests.RequestException as exc:
        raise MPTError(f"Falha ao criar tarefa no MPT: {exc}") from exc

    data = r.json().get("data") or {}
    task_id = data.get("task_id")
    if not task_id:
        raise MPTError(f"Resposta sem task_id: {r.text[:300]}")
    return task_id


def get_task(task_id: str) -> dict:
    try:
        r = requests.get(f"{MPT_API_URL}/api/v1/tasks/{task_id}", timeout=_TIMEOUT)
        r.raise_for_status()
    except requests.RequestException as exc:
        raise MPTError(f"Falha ao consultar tarefa {task_id}: {exc}") from exc
    return r.json().get("data") or {}


def wait_for_video(
    task_id: str,
    *,
    on_progress: Optional[Callable[[int, str], None]] = None,
    poll_seconds: float = 3.0,
    timeout_seconds: int = 1800,
) -> list[str]:
    """
    Faz polling até a tarefa concluir. Retorna as URLs dos vídeos gerados.

    on_progress(percent, detail) — plugue aqui o emit() do pipeline para o
    progresso cair direto no SSE do StudyFlow.

    Estados do MPT: 1 = na fila, 4 = processando, -1 = falhou, 5+ = concluído
    (na prática: progress == 100 e lista `videos` preenchida).
    """
    deadline = time.monotonic() + timeout_seconds
    last_progress = -1

    while time.monotonic() < deadline:
        data = get_task(task_id)
        state = data.get("state")
        progress = int(data.get("progress", 0) or 0)

        if progress != last_progress and on_progress:
            on_progress(progress, f"estado={state}")
            last_progress = progress

        if state == -1:
            raise MPTError(f"Tarefa {task_id} falhou no MPT: {data.get('error', 'sem detalhe')}")

        videos = data.get("videos") or []
        if progress >= 100 and videos:
            return videos

        time.sleep(poll_seconds)

    raise MPTError(f"Timeout ({timeout_seconds}s) aguardando a tarefa {task_id}")


def download_video(url: str, dest_dir: str | Path, filename: str) -> Path:
    """Baixa o vídeo final para static/videos/ (ou onde o StudyFlow servir)."""
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / filename

    # URLs relativas viram absolutas no host do MPT
    if url.startswith("/"):
        url = f"{MPT_API_URL}{url}"

    try:
        with requests.get(url, stream=True, timeout=_TIMEOUT) as r:
            r.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 20):
                    f.write(chunk)
    except requests.RequestException as exc:
        raise MPTError(f"Falha ao baixar vídeo {url}: {exc}") from exc

    return dest
