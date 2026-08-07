"""
tools/transcriber.py
Transcreve um arquivo de áudio usando faster-whisper (local).
faster-whisper roda em Python 3.12 sem precisar de build/torch pesado.
"""

import json
import os
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from faster_whisper import WhisperModel

# Modelo mantido em memória entre requests — evita reload do disco a cada chamada
_MODEL_CACHE: dict[str, WhisperModel] = {}


def _get_whisper(model_name: str) -> WhisperModel:
    if model_name not in _MODEL_CACHE:
        print(f"[transcriber] Carregando modelo Whisper '{model_name}' pela primeira vez...")
        _MODEL_CACHE[model_name] = WhisperModel(model_name, device="cpu", compute_type="int8")
        print(f"[transcriber] Modelo '{model_name}' em cache.")
    return _MODEL_CACHE[model_name]


def release_whisper_model(model_name: str | None = None) -> None:
    """Libera o(s) modelo(s) Whisper carregado(s) da memória. Pensado pra
    ser chamado logo depois que a transcrição termina — por padrão o
    modelo fica em cache o tempo todo (bom pra não recarregar entre
    vídeos diferentes), mas numa máquina com RAM apertada é melhor abrir
    mão desse cache bem na hora em que o corte de vídeo + ffmpeg (as
    etapas mais pesadas em RAM do pipeline) mais precisam de espaço.
    Custo: o próximo vídeo processado recarrega o modelo do zero (alguns
    segundos a mais) — bem mais barato que o sistema trocar memória pro
    disco (swap), que é o que realmente destrói a performance."""
    import gc

    if model_name:
        _MODEL_CACHE.pop(model_name, None)
    else:
        _MODEL_CACHE.clear()
    gc.collect()


class TranscriberInput(BaseModel):
    audio_path: str = Field(
        description="Caminho para o arquivo de áudio .mp3"
    )


class TranscriberTool(BaseTool):
    name: str = "transcriber"
    description: str = (
        "Transcreve um arquivo de áudio para texto usando Whisper. "
        "Retorna a transcrição completa do conteúdo falado. "
        "Use após extrair o áudio do vídeo."
    )
    args_schema: type[BaseModel] = TranscriberInput
    whisper_model: str = "base"

    def _run(self, audio_path: str) -> str:
        if not os.path.exists(audio_path):
            return f"ERRO: arquivo não encontrado em '{audio_path}'"

        try:
            model = _get_whisper(self.whisper_model)

            print("[transcriber] Transcrevendo áudio...")
            # word_timestamps=False (padrão): ligar isso deixa a transcrição
            # bem mais lenta (calcula o timing de CADA palavra). Testado e
            # revertido em 30/07/2026 — no hardware de 8GB RAM do usuário
            # isso tornava o pipeline inteiro "mega lento". A legenda
            # queimada (tools/captions.py) continua funcionando sem isso —
            # cai no fallback de interpolação linear (distribui as palavras
            # proporcionalmente dentro do tempo do segmento), um pouco menos
            # precisa no sincronismo, mas praticamente imperceptível pra
            # clipe curto de Shorts/Reels.
            #
            # vad_filter=True: pula trechos de SILÊNCIO em vez de mandar
            # tudo pro modelo. Ganho real em vídeo longo (podcast/entrevista
            # tem muita pausa) — menos áudio processado = mais rápido — E
            # de quebra reduz "alucinação" do Whisper (o modelo às vezes
            # inventa texto repetido em trechos sem fala). Recomendação
            # oficial do faster-whisper especificamente pra áudio longo.
            segments_gen, info = model.transcribe(
                audio_path, beam_size=1, vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 500},
            )

            # Coleta todos os segmentos (gerador → lista) para timestamps
            segments_list = []
            for seg in segments_gen:
                segments_list.append({
                    "text": seg.text.strip(),
                    "start": round(seg.start, 2),
                    "end": round(seg.end, 2),
                })

            transcript = " ".join(
                s["text"] for s in segments_list
            ).strip()

            if not transcript:
                return (
                    "ERRO: transcrição vazia. "
                    "Verifique se o áudio tem conteúdo."
                )

            # Salva transcrição em texto para debug
            txt_path = audio_path.replace(".mp3", "_transcript.txt")
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(transcript)

            # Salva segmentos com timestamps para o LessonSegmenter
            segments_path = audio_path.replace(
                ".mp3", "_segments.json"
            )
            with open(segments_path, "w", encoding="utf-8") as f:
                json.dump(segments_list, f, ensure_ascii=False, indent=2)

            print(
                f"[transcriber] Transcrição salva em {txt_path} "
                f"(idioma: {info.language})"
            )
            print(
                f"[transcriber] Segmentos salvos em {segments_path}"
            )

            return transcript

        except Exception as e:
            return f"ERRO na transcrição: {e}"

    async def _arun(self, audio_path: str) -> str:
        return self._run(audio_path)
