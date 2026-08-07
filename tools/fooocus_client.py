"""
tools/fooocus_client.py — cliente HTTP do Fooocus-API (Módulo Criador · Imagens).

O Fooocus-API roda como serviço ao lado, NATIVO no host (não em Docker),
porque geração de imagem precisa de GPU e o Docker Desktop no Mac não
repassa acesso a GPU (nem Nvidia nem Apple Silicon/MPS) pros containers.

    python3 main.py --host 0.0.0.0 --port 8888     (na pasta do Fooocus-API)

Dentro dos containers do StudyFlow, alcança via:
    FOOOCUS_API_URL=http://host.docker.internal:8888

Endpoint confirmado no código-fonte real (fooocusapi/routes/query.py e
fooocusapi/routes/generate_v1.py) — não só na documentação:
    GET  /ping                              → "pong"
    POST /v1/generation/text-to-image       → List[GeneratedImageResult]
         (síncrono quando async_process=False; cada resultado tem
          base64/url/seed/finish_reason)
"""

from __future__ import annotations

import base64
import os
import time
from pathlib import Path
from typing import Optional

import requests

FOOOCUS_API_URL = os.getenv("FOOOCUS_API_URL", "http://127.0.0.1:8888").rstrip("/")
_TIMEOUT = 600  # 10 min — em Macs com memória compartilhada baixa (8GB),
# o SDXL cai pro modo "sub quadratic attention" (mais lento, mas cabe na
# memória) e uma imagem pode passar de 3 minutos tranquilamente.


class FooocusError(RuntimeError):
    """Erro na comunicação ou na geração de imagem do Fooocus-API."""


# Presets dos 3 casos de uso do Módulo Criador · Imagens.
# Proporções são valores REAIS aceitos pela API (lidos do código-fonte,
# em repositories/Fooocus/modules/flags.py — sdxl_aspect_ratios).
PRESETS = {
    "thumbnail": {
        "aspect_ratios_selection": "1344*768",   # ~16:9, padrão de thumbnail de vídeo
        "label": "Thumbnail (16:9)",
        "image_number": 1,
    },
    "carrossel": {
        "aspect_ratios_selection": "1024*1024",  # quadrado — post de feed do Instagram
        "label": "Carrossel Instagram (1:1)",
        "image_number": 4,                       # 4 slides por padrão
    },
    "capa": {
        "aspect_ratios_selection": "1152*832",   # paisagem, distinto do thumbnail
        "label": "Capa de curso",
        "image_number": 1,
    },
}


def is_alive() -> bool:
    """Health-check — usado pelo pipeline antes de despachar."""
    try:
        r = requests.get(f"{FOOOCUS_API_URL}/ping", timeout=5)
        return r.ok
    except requests.RequestException:
        return False


def generate_images(
    prompt: str,
    *,
    preset: str = "thumbnail",
    negative_prompt: str = "",
    style_selections: Optional[list[str]] = None,
    image_number: Optional[int] = None,
) -> list[dict]:
    """
    Gera imagens de forma síncrona (async_process=False) e retorna a lista
    de resultados já com os bytes da imagem em base64.

    Levanta FooocusError se o serviço não responder ou a geração falhar.
    """
    cfg = PRESETS.get(preset, PRESETS["thumbnail"])
    payload = {
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "style_selections": style_selections or ["Fooocus V2", "Fooocus Enhance", "Fooocus Sharp"],
        # "Lightning" = 4 passos (vs 8 do "Extreme Speed", vs 30 do "Speed").
        # O Fooocus ajusta sampler/CFG/etc sozinho quando detecta esse preset
        # (set_lightning_defaults, em modules/async_worker.py) — não precisa
        # de nenhum parâmetro extra aqui. 1ª geração baixa mais um LoRA
        # (sdxl_lightning_4step_lora.safetensors, pequeno) — só uma vez.
        # Troque para "Hyper-SD" se quiser comparar qualidade (mesmo custo).
        "performance_selection": "Lightning",
        "aspect_ratios_selection": cfg["aspect_ratios_selection"],
        "image_number": image_number or cfg["image_number"],
        "require_base64": True,
        "save_meta": False,
        "async_process": False,
    }
    try:
        r = requests.post(
            f"{FOOOCUS_API_URL}/v1/generation/text-to-image",
            json=payload,
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
    except requests.RequestException as exc:
        raise FooocusError(f"Falha ao gerar imagem no Fooocus-API: {exc}") from exc

    results = r.json()
    if not isinstance(results, list):
        raise FooocusError(f"Resposta inesperada do Fooocus-API: {str(results)[:300]}")

    # GenerationFinishReason.success = 'SUCCESS' (confirmado no código-fonte,
    # fooocusapi/models/common/task.py) — só aceita resultados com esse valor.
    ok = [x for x in results if x.get("finish_reason") == "SUCCESS" and x.get("base64")]
    if not ok:
        raise FooocusError(f"Nenhuma imagem gerada com sucesso. Resposta: {str(results)[:300]}")
    return ok


def save_images(results: list[dict], dest_dir: str | Path, prefix: str) -> list[str]:
    """Decodifica o base64 e salva em static/images/ (ou onde o StudyFlow servir).
    Retorna as URLs relativas (/static/images/arquivo.png) para o front usar."""
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    saved_urls = []
    for i, item in enumerate(results, start=1):
        b64 = item.get("base64")
        if not b64:
            continue
        raw = base64.b64decode(b64)
        fname = f"{prefix}_{i}.png"
        (dest_dir / fname).write_bytes(raw)
        saved_urls.append(f"/static/images/{fname}")
    return saved_urls
