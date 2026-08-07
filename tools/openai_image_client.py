"""
tools/openai_image_client.py — gera imagens na nuvem via API da OpenAI
(gpt-image-1-mini), como alternativa RÁPIDA ao Fooocus local.

Por que existir: no hardware da Vanessa (Mac com 8GB compartilhados),
o Fooocus local ficou lento demais mesmo depois de "Lightning" (4 passos)
+ caffeinate. Delega o trabalho pesado pra infraestrutura da OpenAI —
sem GPU local, sem espera de minutos, mas com custo por imagem (baixo).

Confirmado na documentação oficial (developers.openai.com/api/docs/guides/
image-generation) em 21/07/2026 — não por memória, o ecossistema mudou
bastante (GPT Image 2/1.5/1-mini; DALL-E foi removido da API em mai/2026):
    POST https://api.openai.com/v1/images/generations
    model="gpt-image-1-mini"  (o mais barato: ~$0,005/imagem em "low")
    size: "1024x1024" | "1536x1024" | "1024x1536"
    n: gera várias imagens numa chamada só (usado no preset carrossel)

Mesmo "formato de saída" que tools/fooocus_client.py (lista de dicts com
"base64") — dá pra reusar fooocus_client.save_images() para as duas.
"""

from __future__ import annotations

import base64
import io
import os
from typing import Optional

from openai import OpenAI, OpenAIError

# Mesmos 3 presets do Fooocus, mapeados pros tamanhos que a API aceita.
PRESETS = {
    "thumbnail": {"size": "1536x1024", "label": "Thumbnail (16:9)", "n": 1},
    "carrossel": {"size": "1024x1024", "label": "Carrossel Instagram (1:1)", "n": 4},
    "capa": {"size": "1536x1024", "label": "Capa de curso", "n": 1},
}

MODEL = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1-mini")
QUALITY = os.getenv("OPENAI_IMAGE_QUALITY", "low")


class OpenAIImageError(RuntimeError):
    """Erro na geração de imagem via API da OpenAI."""


def is_alive() -> bool:
    """Não há endpoint de health-check — só confirma que a chave existe."""
    return bool(os.getenv("OPENAI_API_KEY"))


def _build_reference_collage(images_b64: list[str]) -> io.BytesIO:
    """Monta um mosaico horizontal com várias imagens de referência numa
    única imagem — contorna a limitação do SDK openai==1.51.0, que só
    aceita UMA imagem em images.edit() (suporte a lista de imagens só
    existe em versões mais novas da lib, que não estão instaladas aqui).
    Todas as imagens são redimensionadas pra mesma altura antes de
    juntar, lado a lado, sem cortar nada."""
    from PIL import Image as PILImage

    pil_images = [PILImage.open(io.BytesIO(base64.b64decode(b))).convert("RGB") for b in images_b64]
    target_h = 1024
    resized = []
    for img in pil_images:
        w, h = img.size
        new_w = int(w * (target_h / h))
        resized.append(img.resize((new_w, target_h)))

    total_w = sum(img.width for img in resized)
    collage = PILImage.new("RGB", (total_w, target_h), (0, 0, 0))
    x = 0
    for img in resized:
        collage.paste(img, (x, 0))
        x += img.width

    buf = io.BytesIO()
    collage.save(buf, format="PNG")
    buf.seek(0)
    buf.name = "reference_collage.png"
    return buf


def generate_images(
    prompt: str,
    *,
    preset: str = "thumbnail",
    negative_prompt: str = "",  # aceito por simetria com fooocus_client; a
                                 # API da OpenAI não tem negative_prompt —
                                 # incorporamos como instrução no próprio prompt.
    image_number: Optional[int] = None,
    reference_images_b64: Optional[list[str]] = None,
) -> list[dict]:
    """Gera imagens na nuvem e retorna no MESMO formato do fooocus_client
    (lista de dicts com 'base64'), pra reusar save_images() sem duplicar código.

    Se reference_images_b64 for passado (lista de strings base64 de PNG/JPG,
    até 16 — limite da própria OpenAI), usa o endpoint de EDIÇÃO em vez de
    geração do zero. Com mais de uma imagem, o modelo combina estilo/
    composição das referências — útil pra manter identidade visual
    consistente entre vários posts ao mesmo tempo (ex: 2-3 posts antigos
    como referência de estilo pro post novo)."""
    if not os.getenv("OPENAI_API_KEY"):
        raise OpenAIImageError("OPENAI_API_KEY não configurada no .env")
    if reference_images_b64 and len(reference_images_b64) > 16:
        raise OpenAIImageError("Máximo de 16 imagens de referência (limite da OpenAI).")

    cfg = PRESETS.get(preset, PRESETS["thumbnail"])
    final_prompt = prompt
    if negative_prompt:
        final_prompt = f"{prompt}. Evite: {negative_prompt}."
    if reference_images_b64 and len(reference_images_b64) > 1:
        final_prompt = (
            f"{final_prompt} (A imagem de referência anexa é um mosaico com "
            f"{len(reference_images_b64)} imagens diferentes lado a lado — "
            f"use o conjunto delas como referência de estilo/composição, não "
            f"como uma imagem única.)"
        )

    client = OpenAI()
    n = image_number or cfg["n"]
    try:
        if reference_images_b64:
            if len(reference_images_b64) == 1:
                f = io.BytesIO(base64.b64decode(reference_images_b64[0]))
                f.name = "reference.png"
                image_input = f
            else:
                # SDK openai==1.51.0 não aceita lista em images.edit() —
                # combina todas as referências num mosaico único primeiro.
                image_input = _build_reference_collage(reference_images_b64)
            # NOTA: images.edit() no SDK openai==1.51.0 NÃO aceita o parâmetro
            # "quality" (aceita só em versões mais novas da lib, mesmo a API
            # REST aceitando) — passar isso aqui quebra com
            # "TypeError: Images.edit() got an unexpected keyword argument
            # 'quality'". Por isso ele fica de fora só nesta chamada.
            result = client.images.edit(
                model=MODEL,
                image=image_input,
                prompt=final_prompt,
                size=cfg["size"],
                n=n,
            )
        else:
            result = client.images.generate(
                model=MODEL,
                prompt=final_prompt,
                size=cfg["size"],
                quality=QUALITY,
                n=n,
            )
    except OpenAIError as exc:
        raise OpenAIImageError(f"Falha ao gerar imagem na OpenAI: {exc}") from exc

    if not result.data:
        raise OpenAIImageError("A OpenAI não retornou nenhuma imagem.")

    return [{"base64": item.b64_json} for item in result.data if item.b64_json]
