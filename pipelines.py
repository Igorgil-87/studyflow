"""
pipelines.py — pipelines de execução (Curso, Youtuber, Tendências).

Portados do app.py original. Mudanças:
  - emitem progresso via infra.bus (não mais queue.Queue por job);
  - gravam resultados via infra.jobs (não mais no dict global JOBS);
  - chamadas de LLM passam por infra.resilience.guard (timeout + breaker);
  - o pipeline de tendências degrada de forma graciosa (fail-open) se a
    síntese (Claude Sonnet) falhar — ainda retorna ranking + insights.

Este módulo é importado tanto pelo app (modo inline) quanto pelo worker RQ
(modo redis), então carrega o próprio ambiente.
"""

from __future__ import annotations

import gc
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from dotenv import load_dotenv

from infra import bus, jobs
from cache import llm_cache
from obs import db as obs_db
from obs import judge as obs_judge
from obs import tracing as obs_tracing
from tools import (
    AudioExtractorTool,
    HighlightExtractorTool,
    LessonSegmenterTool,
    QuizGeneratorTool,
    RoadmapGeneratorTool,
    TranscriberTool,
    VideoDownloaderTool,
    VideoSplitterTool,
    YouTubeSearchTool,
    GlobalTrendIntelligence,
)

load_dotenv()

LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "output/quizzes")
COOKIES_BROWSER = os.getenv("COOKIES_BROWSER", "").strip()

from tools.cookies_config import get_cookies_file  # noqa: E402
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
CLAUDE_FAST_MODEL = os.getenv("CLAUDE_FAST_MODEL", "claude-haiku-4-5-20251001")

# Timeouts (segundos) para chamadas de LLM.
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "180"))
# Abaixo deste nº de palavras/min, o vídeo é tratado como pouca-fala (música).
LOW_SPEECH_WPM = int(os.getenv("LOW_SPEECH_WPM", "25"))
# Janela de cache das tendências (segundos) — economiza chamadas de IA.
TRENDS_CACHE_TTL = int(os.getenv("TRENDS_CACHE_TTL", "3600"))


def _make_thumbnails(clips, content_type, emit=None) -> None:
    """Gera uma thumbnail pronta para cada corte. Fail-open."""
    try:
        from tools.thumbnail import generate
    except Exception as e:
        print(f"[thumbnail] indisponível: {e}")
        return
    made = 0
    for clip in clips:
        arq = clip.get("arquivo")
        if not arq:
            continue
        title = clip.get("thumb_texto") or clip.get("hook") or clip.get("titulo") or ""
        out_rel = arq.rsplit(".", 1)[0] + "_thumb.jpg"
        if generate(f"static/{arq}", title, f"static/{out_rel}", content_type):
            clip["thumbnail"] = out_rel
            made += 1
    if emit and made:
        emit("thumb", "done", f"{made} thumbnail(s) gerada(s).")


def _maybe_index_trends(all_results: dict) -> None:
    """Indexa as tendências na base vetorial (pgvector), se o RAG estiver ligado."""
    try:
        from rag import config as rag_config
        if not rag_config.RAG_ENABLED:
            return
        from rag.store import get_store
        from rag.index import index_trends
        from cache.embeddings import embed
        store = get_store()
        if store is None:
            return
        n = index_trends(all_results, embed, store)
        if n:
            print(f"[rag] {n} tendências indexadas na base vetorial.")
    except Exception as e:
        print(f"[rag] indexação de trends ignorada (seguindo): {e}")


def _maybe_index_rag(video_id: str, segments_path: str, emit=None) -> None:
    """Indexa a transcrição na base vetorial (pgvector), se o RAG estiver ligado.
    Fail-open: qualquer problema apenas registra e segue."""
    try:
        from rag import config as rag_config
        if not rag_config.RAG_ENABLED:
            return
        import json as _json
        from rag.store import get_store
        from rag.index import index_transcript
        from cache.embeddings import embed
        store = get_store()
        if store is None or not os.path.exists(segments_path):
            return
        with open(segments_path, encoding="utf-8") as f:
            segments = _json.load(f)
        n = index_transcript(video_id, segments, embed, store)
        if emit and n:
            emit("rag", "done", f"{n} trechos indexados na base vetorial.")
    except Exception as e:
        print(f"[rag] indexação ignorada (seguindo): {e}")

# Avaliação automática do quiz (LLM-as-Judge) após gerar — opt-in (custa 1 call).
EVAL_ENABLED = os.getenv("EVAL_ENABLED", "0") == "1"

# Garante o schema de observabilidade ao carregar (idempotente).
obs_db.init()


# ── Pipeline Curso ───────────────────────────────────────────────────────────
def run_curso_pipeline(
    job_id: str, topic: str, num_flashcards: int, num_questions: int
):
    def emit(step: str, status: str, detail: str = ""):
        bus.publish(job_id, "progress",
                    {"step": step, "status": status, "detail": detail})

    try:
        emit("search", "running", f"Buscando vídeos sobre '{topic}'...")
        raw = YouTubeSearchTool()._run(query=topic, max_results=3)
        videos = json.loads(raw)
        if isinstance(videos, dict) and videos.get("erro"):
            raise RuntimeError(f"Busca falhou: {videos['erro']}")
        if not videos:
            raise RuntimeError("Nenhum vídeo encontrado.")
        chosen = next(
            (v for v in videos if 3 <= v.get("duracao_minutos", 0) <= 25),
            videos[0],
        )
        emit("search", "done", f"Vídeo: {chosen['titulo']}")
        bus.publish(job_id, "video", chosen)

        emit("download", "running", "Baixando áudio e vídeo em paralelo...")
        audio_tool = AudioExtractorTool(
            output_dir="output", cookies_browser=COOKIES_BROWSER,
            cookies_file=get_cookies_file(),
        )
        video_tool = VideoDownloaderTool(
            output_dir="static/videos", cookies_browser=COOKIES_BROWSER,
            cookies_file=get_cookies_file(),
        )
        with ThreadPoolExecutor(max_workers=2) as dl_ex:
            audio_fut = dl_ex.submit(audio_tool._run, url=chosen["url"], max_minutes=10, job_id=job_id)
            video_fut = dl_ex.submit(video_tool._run, url=chosen["url"], job_id=job_id)
            audio_path = audio_fut.result()
            video_rel = video_fut.result()

        if audio_path.startswith("ERRO"):
            raise RuntimeError(audio_path)
        emit("download", "done", "Áudio extraído.")

        if video_rel.startswith("ERRO"):
            video_rel = None
            emit("video_dl", "done", "Vídeo indisponível.")
        else:
            jobs.set(job_id, "video_file", video_rel)
            emit("video_dl", "done", "Vídeo pronto.")

        emit("transcribe", "running",
             f"Transcrevendo com Whisper '{WHISPER_MODEL}'...")
        transcript = TranscriberTool(whisper_model=WHISPER_MODEL)._run(
            audio_path=audio_path)
        if transcript.startswith("ERRO"):
            raise RuntimeError(transcript)
        emit("transcribe", "done", f"{len(transcript)} chars transcritos.")

        emit("quiz", "running", "Gerando quiz com LLM...")
        quiz_path = llm_cache.smart_call(
            "openai", "quiz", LLM_MODEL,
            QuizGeneratorTool(llm_model=LLM_MODEL, output_dir=OUTPUT_DIR)._run,
            cache_key=f"quiz|{topic}|{num_flashcards}|{num_questions}|{transcript}",
            result_kind="file", file_dir=OUTPUT_DIR,
            trace_id=job_id, input_text=transcript, timeout=LLM_TIMEOUT,
            transcript=transcript, topic=topic,
            num_flashcards=num_flashcards, num_questions=num_questions,
        )
        if quiz_path.startswith("ERRO"):
            raise RuntimeError(quiz_path)
        with open(quiz_path, encoding="utf-8") as f:
            quiz_data = json.load(f)
        jobs.set(job_id, "quiz", quiz_data)
        emit("quiz", "done", "Quiz gerado!")

        # LLM-as-Judge: avalia a qualidade do quiz (opt-in via EVAL_ENABLED).
        if EVAL_ENABLED:
            emit("eval", "running", "Avaliando qualidade do quiz (LLM-as-Judge)...")
            verdict = obs_judge.run_quiz_eval(job_id, transcript, quiz_data)
            if verdict.get("ok"):
                emit("eval", "done",
                     f"Score do quiz: {verdict['judge_score']:.2f}")
            else:
                emit("eval", "done", "Avaliação indisponível.")

        emit("roadmap", "running", "Montando roteiro...")
        roadmap_path = llm_cache.smart_call(
            "openai", "roadmap", LLM_MODEL,
            RoadmapGeneratorTool(llm_model=LLM_MODEL, output_dir="output/roadmaps")._run,
            cache_key=f"roadmap|{topic}|4|{transcript}",
            result_kind="file", file_dir="output/roadmaps",
            trace_id=job_id, input_text=transcript, timeout=LLM_TIMEOUT,
            transcript=transcript, topic=topic, num_modules=4,
        )
        if roadmap_path.startswith("ERRO"):
            raise RuntimeError(roadmap_path)
        with open(roadmap_path, encoding="utf-8") as f:
            roadmap_data = json.load(f)
        jobs.set(job_id, "roadmap", roadmap_data)
        emit("roadmap", "done", "Roteiro pronto!")

        emit("segment", "running", "Identificando blocos de aulas...")
        segments_path = audio_path.replace(".mp3", "_segments.json")
        aulas_json = obs_tracing.traced_llm(
            "openai", "segment", LLM_MODEL,
            LessonSegmenterTool(llm_model=LLM_MODEL)._run,
            trace_id=job_id, input_text=topic, timeout=LLM_TIMEOUT,
            segments_path=segments_path, topic=topic,
        )
        if aulas_json.startswith("ERRO"):
            raise RuntimeError(aulas_json)
        n_aulas = len(json.loads(aulas_json).get("aulas", []))
        emit("segment", "done", f"{n_aulas} aulas identificadas.")

        clips_result = None
        if video_rel:
            emit("cut", "running", "Cortando vídeo em aulas...")
            clips_json = VideoSplitterTool()._run(
                video_path=f"static/{video_rel}",
                aulas_json=aulas_json,
                output_dir="static/videos/clips",
                progress_callback=lambda msg: emit("cut", "running", msg),
            )
            if clips_json.startswith("ERRO"):
                emit("cut", "done", "Corte indisponível.")
            else:
                clips_result = json.loads(clips_json).get("clips", [])
                jobs.set(job_id, "clips", clips_result)
                emit("cut", "done", f"{len(clips_result)} aulas criadas!")
        else:
            emit("cut", "done", "Vídeo indisponível para corte.")

        bus.publish(job_id, "complete", {
            "quiz": quiz_data,
            "roadmap": roadmap_data,
            "video": chosen,
            "video_file": (jobs.get(job_id) or {}).get("video_file"),
            "clips": clips_result,
        })

    except Exception as e:
        jobs.set(job_id, "error", str(e))
        bus.publish(job_id, "pipeline_error", {"message": str(e)})
    finally:
        jobs.set(job_id, "done", True)
        bus.end(job_id)


# ── Pipeline Youtuber ────────────────────────────────────────────────────────
def run_youtuber_pipeline(
    job_id: str, niche: str, video_url: str, content_type: str = "shorts",
    num_clips: int | None = None, gerar_legenda: bool = True,
    idioma_legenda: str | None = None, adicionar_fechamento: bool = True,
):
    def emit(step: str, status: str, detail: str = ""):
        bus.publish(job_id, "progress",
                    {"step": step, "status": status, "detail": detail})

    try:
        emit("download", "running", "Baixando áudio e vídeo em paralelo...")
        audio_tool = AudioExtractorTool(
            output_dir="output", cookies_browser=COOKIES_BROWSER,
            cookies_file=get_cookies_file(),
        )
        video_tool = VideoDownloaderTool(
            output_dir="static/videos", cookies_browser=COOKIES_BROWSER,
            cookies_file=get_cookies_file(),
        )
        with ThreadPoolExecutor(max_workers=2) as dl_ex:
            audio_fut = dl_ex.submit(
                audio_tool._run, url=video_url, max_minutes=20, job_id=job_id,
                progress_callback=lambda msg: emit("download", "running", f"Áudio: {msg}"))
            video_fut = dl_ex.submit(
                video_tool._run, url=video_url, job_id=job_id,
                progress_callback=lambda msg: emit("download", "running", f"Vídeo: {msg}"))
            audio_path = audio_fut.result()
            video_rel = video_fut.result()

        if audio_path.startswith("ERRO"):
            raise RuntimeError(audio_path)
        emit("download", "done", "Áudio extraído.")

        if video_rel.startswith("ERRO"):
            video_rel = None
            emit("video_dl", "done", "Vídeo indisponível.")
        else:
            jobs.set(job_id, "video_file", video_rel)
            emit("video_dl", "done", "Vídeo pronto.")

        emit("transcribe", "running",
             f"Transcrevendo com Whisper '{WHISPER_MODEL}'...")
        transcript = TranscriberTool(whisper_model=WHISPER_MODEL)._run(
            audio_path=audio_path)
        if transcript.startswith("ERRO"):
            raise RuntimeError(transcript)
        emit("transcribe", "done", f"{len(transcript)} chars transcritos.")

        # Libera o modelo Whisper da RAM assim que a transcrição termina —
        # não é mais usado no resto deste pipeline, e as etapas seguintes
        # (corte de vídeo + ffmpeg do vertical/legenda) são as que mais
        # precisam de memória livre. Custo: o PRÓXIMO vídeo processado
        # recarrega o modelo (alguns segundos a mais) — troca que vale a
        # pena numa máquina com RAM apertada.
        from tools.transcriber import release_whisper_model
        release_whisper_model(WHISPER_MODEL)

        # Indexa a transcrição na base vetorial (pgvector), se o RAG estiver ligado.
        _maybe_index_rag(video_url, audio_path.replace(".mp3", "_segments.json"), emit)

        emit("highlights", "running", "Identificando momentos virais...")
        segments_path = audio_path.replace(".mp3", "_segments.json")
        seg_content = ""
        try:
            if os.path.exists(segments_path):
                with open(segments_path, encoding="utf-8") as f:
                    seg_content = f.read()
        except Exception:
            pass

        # ── Validação de consistência: duração, densidade de fala e nº de cortes ──
        from tools.clip_rules import (
            clip_bounds, max_clips_for_duration, speech_wpm, is_low_speech,
        )
        min_seg, _max_seg = clip_bounds(content_type)
        duration = 0.0
        try:
            segs = json.loads(seg_content) if seg_content else []
            if segs:
                duration = float(segs[-1].get("end", 0) or 0)
        except Exception:
            segs = []

        # ── Tradução da transcrição INTEIRA, uma vez só (não por clip) ──
        # Traduzir clip a clip era frágil: cada clip virava uma chamada de
        # API independente, e qualquer falha pontual (rate limit, erro
        # transitório) caía no fail-open só PRA AQUELE clip — resultado:
        # "alguns em português, outros não", inconsistente. Traduzindo a
        # transcrição inteira uma vez, todo clip usa a MESMA fonte já
        # traduzida — ou funciona pra todo mundo, ou falha uma vez só (e
        # aí todo mundo cai no idioma original de forma consistente).
        segs_para_legenda = segs
        if gerar_legenda and idioma_legenda and segs:
            emit("transcribe", "running",
                 f"Traduzindo transcrição pra {idioma_legenda}...")
            try:
                from tools.caption_translator import translate_segments
                segs_para_legenda = translate_segments(segs, idioma_legenda)
                emit("transcribe", "done",
                     f"Transcrição traduzida pra {idioma_legenda} "
                     f"({len(segs_para_legenda)} segmentos).")
            except Exception as e:
                print(f"[pipeline] Tradução da transcrição falhou, "
                      f"legenda sai no idioma original: {e}")
                emit("transcribe", "done",
                     f"⚠ Tradução pra {idioma_legenda} falhou ({e}) — "
                     f"legenda vai sair no idioma original do vídeo.")
                segs_para_legenda = segs

        # Detecta vídeo com pouca fala (música/instrumental) → corte tende a ser fraco
        word_count = len(transcript.split())
        wpm = speech_wpm(word_count, duration)
        if is_low_speech(wpm, LOW_SPEECH_WPM):
            emit("highlights", "running",
                 f"⚠ Pouca fala detectada (~{wpm:.0f} palavras/min). "
                 "Parece música/instrumental — os cortes podem ficar fracos.")

        # Quantidade pedida vs. máximo possível pela duração
        effective_num = num_clips
        if num_clips and duration > 0:
            max_possible = max_clips_for_duration(duration, min_seg)
            if num_clips > max_possible:
                effective_num = max_possible
                emit("highlights", "running",
                     f"⚠ Vídeo de {duration:.0f}s só comporta ~{max_possible} "
                     f"corte(s) de {min_seg}s. Ajustei de {num_clips} para "
                     f"{max_possible}.")

        highlights_json = llm_cache.smart_call(
            "openai", "highlights", LLM_MODEL,
            HighlightExtractorTool(llm_model=LLM_MODEL)._run,
            cache_key=f"highlights|{niche}|{content_type}|{effective_num}|{seg_content}",
            result_kind="text",
            trace_id=job_id, input_text=niche, timeout=LLM_TIMEOUT,
            segments_path=segments_path, niche=niche, content_type=content_type,
            num_highlights=effective_num,
        )
        if highlights_json.startswith("ERRO"):
            raise RuntimeError(highlights_json)
        highlights_data = json.loads(highlights_json)
        hl_list = highlights_data.get("highlights", [])

        # ── Regra vira lei: força cada corte a respeitar a faixa de duração ──
        from tools.clip_rules import enforce_durations
        hl_list, n_adj, n_drop = enforce_durations(
            hl_list, min_seg, _max_seg, duration)
        if n_adj or n_drop:
            emit("highlights", "running",
                 f"Ajustei {n_adj} corte(s) para a faixa {min_seg}-{_max_seg}s"
                 + (f" e descartei {n_drop} inválido(s)." if n_drop else "."))

        emit("highlights", "done", f"{len(hl_list)} highlights identificados.")

        clips_result = None
        if video_rel:
            emit("cut", "running", "Cortando os highlights...")
            aulas_fmt = {
                "aulas": [
                    {
                        "titulo": h["titulo"],
                        "inicio": h["inicio"],
                        "fim": h["fim"],
                        "resumo": h.get("motivo", ""),
                    }
                    for h in hl_list
                ]
            }
            clips_json = VideoSplitterTool()._run(
                video_path=f"static/{video_rel}",
                aulas_json=json.dumps(aulas_fmt),
                output_dir="static/videos/highlights",
                progress_callback=lambda msg: emit("cut", "running", msg),
            )
            if clips_json.startswith("ERRO"):
                emit("cut", "done", "Corte indisponível.")
            else:
                clips_result = json.loads(clips_json).get("clips", [])
                for i, clip in enumerate(clips_result):
                    if i < len(hl_list):
                        hl = hl_list[i]
                        # leva TODOS os campos virais para o clip (tier, títulos,
                        # conceito de thumbnail, hook otimizado, sub-scores, etc.)
                        for k, v in hl.items():
                            if k not in ("inicio", "fim", "arquivo"):
                                clip[k] = v
                    # garante um título de chamada (nunca "Clip sem título")
                    t = (clip.get("titulo") or "").strip()
                    if not t or t.lower() == "clip sem título":
                        alts = clip.get("titulos_alt") or []
                        clip["titulo"] = (alts[0] if alts else "") \
                            or clip.get("hook_otimizado") \
                            or clip.get("thumb_texto") or "Corte viral"
                _make_thumbnails(clips_result, content_type, emit)

                # Libera qualquer memória do moviepy/corte que ainda esteja
                # solta antes de começar o ffmpeg (etapa mais pesada em RAM
                # daqui pra frente).
                gc.collect()

                # ── Vertical + legenda queimada — SÓ pra Shorts ──
                # "Cortes" (corte_120/300/600/900, 2 a 15 MINUTOS cada) não
                # são formato de Shorts/Reels/TikTok — são unidade de
                # conhecimento pra YouTube normal, em paisagem. Forçar um
                # corte de 15 minutos pelo mesmo pipeline de reenquadrar em
                # vertical + queimar legenda era o gargalo real: o tempo de
                # encode do ffmpeg escala com a duração do clip, então um
                # corte longo demorava ordens de magnitude mais que um
                # short de 30s no mesmo processo — sem nem fazer sentido
                # pro formato final. Pulando isso pra Cortes, o tempo do
                # pipeline cai para o que realmente importa: cortar +
                # transcrever, sem o encode pesado que ninguém ia usar.
                is_corte_longo = content_type.startswith("corte") or content_type in ("cortes_medio", "cortes_longo")

                # ── Vídeo de fechamento/identidade (opcional, ligado por
                # padrão) — cola static/video/fechamento.mp4 no final de
                # QUALQUER clip, Short ou Corte. Ajusta a resolução do
                # fechamento sozinho pra bater com a do clip (letterbox,
                # sem distorcer) — mesmo arquivo funciona pra vertical e
                # pra horizontal.
                FECHAMENTO_PATH = "static/video/fechamento.mp4"

                def _colar_fechamento(clip_rel_path: str) -> str:
                    """Recebe o caminho relativo (a partir de static/) de
                    um clip pronto, cola o fechamento nele, e retorna o
                    novo caminho relativo. Fail-open: se der qualquer
                    problema, devolve o caminho ORIGINAL sem fechamento —
                    nunca trava o clip por causa disso."""
                    if not adicionar_fechamento or not os.path.exists(FECHAMENTO_PATH):
                        return clip_rel_path
                    from tools.video_concat import append_outro, check_ffmpeg
                    if not check_ffmpeg():
                        return clip_rel_path
                    src_abs = os.path.join("static", clip_rel_path)
                    base, ext = os.path.splitext(clip_rel_path)
                    out_rel = f"{base}_fechado{ext}"
                    out_abs = os.path.join("static", out_rel)
                    resultado = append_outro(src_abs, FECHAMENTO_PATH, out_abs)
                    if resultado.get("ok"):
                        return out_rel
                    print(f"[pipeline] Falha ao colar fechamento em {clip_rel_path}: {resultado.get('erro')}")
                    return clip_rel_path

                if is_corte_longo:
                    for clip in clips_result:
                        if clip.get("arquivo"):
                            clip["arquivo"] = _colar_fechamento(clip["arquivo"])
                    emit("vertical", "done",
                         "Corte longo (formato paisagem, YouTube) — pulando reenquadre "
                         "vertical/legenda, que é só pra Shorts. Isso é o que deixa o "
                         "processamento rápido pra cortes longos."
                         + (" Fechamento adicionado." if adicionar_fechamento else ""))
                elif not clips_result:
                    pass
                else:
                    # ── Vertical automático + legenda queimada (Shorts) ──
                    # "arquivo" passa a apontar direto pro vertical já com
                    # legenda; o horizontal original fica salvo em
                    # "arquivo_original" pra quem precisar dele.
                    from tools.vertical_export import export_vertical, check_ffmpeg
                    from tools.captions import write_srt_file, CaptionsError

                    if check_ffmpeg():
                        total_to_process = sum(1 for c in clips_result if c.get("arquivo"))
                        emit("vertical", "running",
                             f"Gerando vertical 9:16 + legenda de {total_to_process} clip(s)...")

                        def _process_one(clip):
                            src_abs = os.path.join("static", clip["arquivo"])
                            base, _ = os.path.splitext(clip["arquivo"])
                            out_rel = f"{base}_9x16.mp4"
                            out_abs = os.path.join("static", out_rel)
                            os.makedirs(os.path.dirname(out_abs), exist_ok=True)

                            srt_path = None
                            if gerar_legenda:
                                try:
                                    candidate = out_abs.replace(".mp4", ".srt")
                                    # segs_para_legenda já está traduzido (se
                                    # pedido) — não passa mais translate_to
                                    # aqui, senão traduziria de novo, clip a
                                    # clip, voltando pro problema antigo.
                                    write_srt_file(segs_para_legenda, clip["inicio"], clip["fim"], candidate)
                                    srt_path = candidate
                                except Exception:
                                    srt_path = None  # sem legenda só nesse clip — não trava o resto

                            # preset "fast" (não "medium"): roda vários clips em
                            # paralelo, então cada um precisa ser mais rápido —
                            # a perda de qualidade é imperceptível pra Shorts/Reels
                            result = export_vertical(src_abs, out_abs, mode="blur",
                                                      subtitle_path=srt_path, preset="fast")
                            return clip, out_rel, srt_path, result

                        n_vertical_ok = 0
                        n_done = 0
                        to_process = [c for c in clips_result if c.get("arquivo")]
                        # sequencial (max_workers=1), não paralelo: testado e
                        # ajustado em 30/07/2026 — no hardware de 8GB RAM do
                        # usuário, rodar ffmpeg em paralelo causava troca de
                        # memória pro disco (swap), deixando TUDO mais lento,
                        # não só essa etapa. Se um dia rodar em máquina com mais
                        # RAM de sobra, subir esse número acelera de verdade.
                        with ThreadPoolExecutor(max_workers=1) as vx:
                            futures = [vx.submit(_process_one, c) for c in to_process]
                            for fut in futures:
                                clip, out_rel, srt_path, result = fut.result()
                                n_done += 1
                                if result.get("ok"):
                                    clip["arquivo_original"] = clip["arquivo"]
                                    clip["arquivo"] = _colar_fechamento(out_rel)
                                    clip["legenda_queimada"] = bool(srt_path)
                                    n_vertical_ok += 1
                                else:
                                    clip["vertical_erro"] = result.get("erro")
                                emit("vertical", "running",
                                     f"{n_done}/{total_to_process} clip(s) processado(s)"
                                     + (f" — '{clip.get('titulo','')[:40]}' pronto" if result.get("ok") else ""))

                        emit("vertical", "done",
                             f"{n_vertical_ok}/{total_to_process} clip(s) em 9:16 com legenda.")
                    else:
                        emit("vertical", "done",
                             "ffmpeg indisponível — clips ficaram no formato original, sem vertical/legenda.")

                jobs.set(job_id, "clips", clips_result)
                emit("cut", "done", f"{len(clips_result)} clips criados!")
        else:
            emit("cut", "done", "Vídeo indisponível para corte.")

        bus.publish(job_id, "complete", {
            "clips": clips_result,
            "video_file": (jobs.get(job_id) or {}).get("video_file"),
        })

    except Exception as e:
        jobs.set(job_id, "error", str(e))
        bus.publish(job_id, "pipeline_error", {"message": str(e)})
    finally:
        jobs.set(job_id, "done", True)
        bus.end(job_id)


# ── Pipeline Tendências Globais ──────────────────────────────────────────────
def run_global_trends_pipeline(job_id: str, categories: list[str], urls: list[str] | None = None):
    urls = urls or []

    def emit(event: str, data: dict):
        bus.publish(job_id, event, data)

    try:
        from cache import ttl_cache
        cache_key = "trends_analyze|" + json.dumps(
            {"categories": sorted(categories), "urls": sorted(urls)},
            ensure_ascii=False,
        )
        cached = ttl_cache.get(cache_key)
        if cached:
            mins = int(ttl_cache.ttl_left(cache_key) // 60)
            emit("progress", {
                "step": "coleta", "status": "done",
                "detail": f"♻ Resultado em cache (válido +{mins}min) — "
                          "economizou as chamadas de IA.",
            })
            emit("complete", cached)
            jobs.set(job_id, "trends_result", cached.get("categories", {}))
            return

        intel = GlobalTrendIntelligence(
            openai_model=LLM_MODEL,
            claude_model=CLAUDE_MODEL,
            claude_fast_model=CLAUDE_FAST_MODEL,
            cookies_browser=COOKIES_BROWSER,
            cookies_file=get_cookies_file(),
        )

        # Stage 1: coleta paralela de 4 fontes.
        emit("progress", {
            "step": "coleta", "status": "running",
            "detail": "Coletando Reddit · HackerNews · Wikipedia · YouTube...",
        })
        raw_data = intel.collect_all_data(categories)
        emit("progress", {
            "step": "coleta", "status": "done",
            "detail": f"{len(categories)} categorias coletadas",
        })

        # Stage 1.4 (automático, sempre roda): camada de lote — pega os
        # links de maior score que a própria coleta já descobriu (Reddit/
        # HackerNews trazem URL real de cada post) e varre o conteúdo
        # completo das páginas, SEM precisar de URL colada manualmente.
        # "Sempre alimenta o LLM" com o texto de verdade da matéria/post,
        # não só o título — isso é o que realmente diferencia um insight
        # raso de um bem embasado. Fail-open: se o Crawl4AI estiver fora
        # do ar, só pula essa etapa e segue com o resto normal.
        try:
            from tools.crawler_client import crawl_urls, CrawlerError

            MAX_LINKS_PER_CATEGORY = 2
            url_to_cats: dict[str, list[str]] = {}
            for cat in categories:
                top_links = (raw_data.get(cat, {}).get("links") or [])[:MAX_LINKS_PER_CATEGORY]
                for link in top_links:
                    u = link.get("url", "")
                    if u:
                        url_to_cats.setdefault(u, []).append(cat)

            if url_to_cats:
                emit("progress", {
                    "step": "coleta", "status": "running",
                    "detail": f"Varrendo {len(url_to_cats)} link(s) de maior destaque (auto)...",
                })
                crawled = crawl_urls(list(url_to_cats.keys()))
                n_ok = 0
                for u, cats_for_url in url_to_cats.items():
                    md = crawled.get(u, "")
                    if not md:
                        continue
                    n_ok += 1
                    piece = f"[Matéria completa de {u}]\n{md[:3000]}"
                    for cat in cats_for_url:
                        existing = raw_data.get(cat, {}).get("context", "")
                        raw_data.setdefault(cat, {})["context"] = (
                            f"{existing}\n\n{piece}".strip() if existing else piece
                        )
                emit("progress", {
                    "step": "coleta", "status": "done",
                    "detail": f"{n_ok}/{len(url_to_cats)} link(s) de destaque varrido(s) automaticamente",
                })
        except CrawlerError as e:
            emit("progress", {
                "step": "coleta", "status": "done",
                "detail": f"Crawl4AI indisponível pro lote automático ({e}) — seguindo só com títulos/resumos",
            })

        # Stage 1.5 (opcional): varre URLs de referência extra QUE VOCÊ
        # colou manualmente (Crawl4AI) e injeta como contexto adicional
        # pra TODAS as categorias — mesmo campo "context" que o
        # GlobalTrendIntelligence já usa internamente (fontes tipo
        # Perplexity/X), então não precisa mexer na classe.
        if urls:
            emit("progress", {
                "step": "coleta", "status": "running",
                "detail": f"Varrendo {len(urls)} URL(s) de referência...",
            })
            try:
                from tools.crawler_client import crawl_urls, CrawlerError
                crawled = crawl_urls(urls)
                extra_context = "\n\n".join(
                    f"[Fonte: {u}]\n{md[:3000]}" for u, md in crawled.items() if md
                )
                if extra_context:
                    for cat in categories:
                        existing = raw_data.get(cat, {}).get("context", "")
                        raw_data.setdefault(cat, {})["context"] = (
                            f"{existing}\n\n{extra_context}".strip() if existing else extra_context
                        )
                    emit("progress", {
                        "step": "coleta", "status": "done",
                        "detail": f"{sum(1 for m in crawled.values() if m)}/{len(urls)} URL(s) varrida(s) com sucesso",
                    })
                else:
                    emit("progress", {
                        "step": "coleta", "status": "done",
                        "detail": "Nenhuma URL retornou conteúdo — seguindo sem contexto extra",
                    })
            except CrawlerError as e:
                emit("progress", {
                    "step": "coleta", "status": "done",
                    "detail": f"Crawl4AI indisponível ({e}) — seguindo sem contexto extra",
                })

        # Stage 2: Chain 1 (GPT) + Chain 2 (Claude Haiku) por categoria.
        emit("progress", {
            "step": "analise", "status": "running",
            "detail": "Chain 1 GPT-4o-mini → rank · Chain 2 Claude Haiku → insights...",
        })
        all_results: dict[str, list] = {}
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(
                    intel.analyze_category, cat, raw_data.get(cat, {})
                ): cat
                for cat in categories
            }
            for future in as_completed(futures):
                cat = futures[future]
                try:
                    result = future.result()
                    all_results[cat] = result
                    emit("category_ready", {"category": cat, "trends": result})
                except Exception as e:
                    print(f"[trends pipeline] {cat}: {e}")
                    all_results[cat] = []

        emit("progress", {
            "step": "analise", "status": "done",
            "detail": f"{sum(len(v) for v in all_results.values())} trends analisadas",
        })

        # Stage 3: Chain 3 (Claude Sonnet) síntese — FAIL-OPEN.
        # Se a síntese falhar, ainda entregamos ranking + insights (degrade).
        emit("progress", {
            "step": "sintese", "status": "running",
            "detail": "Chain 3 Claude Sonnet → padrões globais + editorial...",
        })
        synthesis = llm_cache.smart_call(
            "anthropic", "trends_synthesize", CLAUDE_MODEL,
            intel.synthesize_global, all_results,
            cache_key="trends_synthesize|" + json.dumps(
                all_results, ensure_ascii=False, sort_keys=True),
            result_kind="json",
            trace_id=job_id,
            input_text=json.dumps(all_results, ensure_ascii=False),
            timeout=LLM_TIMEOUT, fallback={},  # degrade gracioso
        )
        if synthesis:
            emit("progress", {"step": "sintese", "status": "done"})
        else:
            emit("progress", {
                "step": "sintese", "status": "done",
                "detail": "Síntese indisponível — entregando ranking + insights.",
            })

        jobs.set(job_id, "trends_result", all_results)
        payload = {
            "categories": all_results,
            "cross_themes": synthesis.get("temas_cruzados", []),
            "summary": synthesis.get("resumo_editorial", ""),
        }
        # Guarda no cache (TTL) para economizar IA nas próximas buscas iguais.
        ttl_cache.set(cache_key, payload, TRENDS_CACHE_TTL)
        # Indexa as tendências na base vetorial (se o RAG estiver ligado).
        _maybe_index_trends(all_results)
        emit("complete", payload)

    except Exception as e:
        jobs.set(job_id, "error", str(e))
        emit("pipeline_error", {"message": str(e)})
    finally:
        jobs.set(job_id, "done", True)
        bus.end(job_id)


# ═══ MÓDULO ESTÚDIO (MoneyPrinterTurbo) — aditivo ═══
def run_estudio_pipeline(job_id: str, subject: str, options: dict | None = None):
    """Gera vídeo completo (roteiro + footage + narração + legendas + BGM)
    a partir de um tema, usando o MoneyPrinterTurbo como serviço sidecar."""
    from tools import mpt_client

    options = options or {}

    def emit(step: str, status: str, detail: str = ""):
        bus.publish(job_id, "progress",
                    {"step": step, "status": status, "detail": detail})

    try:
        # ── 1. Health-check do serviço (fail-fast, mensagem clara) ────
        emit("mpt", "running", "Verificando MoneyPrinterTurbo...")
        if not mpt_client.is_alive():
            raise RuntimeError(
                f"MoneyPrinterTurbo indisponível em {mpt_client.MPT_API_URL}. "
                "Suba o serviço (docker compose up mpt-api ou "
                "'uv run python main.py' na pasta do MPT) e tente de novo."
            )
        emit("mpt", "done", "Serviço online.")

        # ── 2. Criar tarefa (roteiro é gerado pelo LLM se não vier) ───
        emit("create", "running", "Criando roteiro e tarefa de produção...")
        task_id = mpt_client.create_video_task(
            subject,
            script=options.get("script", ""),
            language=options.get("language", "pt-BR"),
            aspect=options.get("aspect", "9:16"),
            voice_name=options.get("voice", "pt-BR-AntonioNeural-Male"),
            count=int(options.get("count", 1)),
        )
        jobs.set(job_id, "mpt_task_id", task_id)
        emit("create", "done", f"Tarefa {task_id[:8]}… criada.")

        # ── 3. Produção (footage → TTS → legendas → render) ───────────
        emit("generate", "running", "Produzindo: footage, narração, legendas...")

        def on_progress(percent: int, _detail: str):
            emit("generate", "running", f"{percent}% concluído")

        video_urls = mpt_client.wait_for_video(task_id, on_progress=on_progress)
        emit("generate", "done", f"{len(video_urls)} vídeo(s) renderizado(s).")

        # ── 4. Download para o storage do StudyFlow ───────────────────
        emit("download", "running", "Trazendo para static/videos...")
        saved = []
        for i, url in enumerate(video_urls, start=1):
            fname = f"estudio_{job_id[:12]}_{i}.mp4"
            mpt_client.download_video(url, "static/videos", fname)
            saved.append(f"/static/videos/{fname}")
        jobs.set(job_id, "videos", saved)
        emit("download", "done", f"{len(saved)} arquivo(s) salvos.")

        # ── 5. Complete (mesmo padrão dos outros módulos) ─────────────
        bus.publish(job_id, "complete", {
            "subject": subject,
            "aspect": options.get("aspect", "9:16"),
            "videos": saved,
            "mpt_task_id": task_id,
        })

        # Gancho futuro — publicar direto com o publish/ existente:
        # if options.get("auto_publish"):
        #     from publish.youtube_uploader import upload_video
        #     upload_video(saved[0].lstrip("/"), title=subject, ...)

    except Exception as e:
        jobs.set(job_id, "error", str(e))
        bus.publish(job_id, "pipeline_error", {"message": str(e)})
    finally:
        jobs.set(job_id, "done", True)
        bus.end(job_id)


# ═══════════ MÓDULO CRIADOR · IMAGENS (Fooocus-API) — aditivo ═══════════
def run_imagem_pipeline(job_id: str, prompt: str, options: dict | None = None):
    """Gera imagens (thumbnail, carrossel de Instagram ou capa de curso).
    Dois motores possíveis, escolhidos por options['engine']:
      - "fooocus" (padrão): Fooocus-API local, sidecar NATIVO no host (GPU
        via MPS) — grátis, mas pode ser lento em Macs com pouca memória
        compartilhada.
      - "openai": API da OpenAI (gpt-image-1-mini) na nuvem — rápido,
        sem depender da GPU local, com custo baixo por imagem.

    Dois recursos adicionais, aditivos e opcionais:
      - options['reference_images_b64']: lista de imagens-guia (image-to-
        image, até 16, só motor "openai") pra manter identidade entre
        posts diferentes — com mais de uma, a OpenAI combina o estilo
        das várias referências no resultado.
      - options['ai_copy']: se True, gera automaticamente o texto de cada
        slide via Claude (options['pilar'] + options['topic']) e aplica
        com tipografia real por cima do fundo gerado — resolve o
        problema de texto deformado quando a própria IA de imagem tenta
        "escrever". Só faz sentido pro preset "carrossel"."""
    from tools import fooocus_client

    options = options or {}
    preset = options.get("preset", "thumbnail")
    engine = options.get("engine", "fooocus")
    ai_copy = bool(options.get("ai_copy"))
    reference_images_b64 = options.get("reference_images_b64") or None

    def emit(step: str, status: str, detail: str = ""):
        bus.publish(job_id, "progress",
                    {"step": step, "status": status, "detail": detail})

    try:
        if engine == "openai":
            from tools import openai_image_client as client
            engine_label = "OpenAI (nuvem)"
        else:
            client = fooocus_client
            engine_label = "Fooocus-API (local)"
            if reference_images_b64:
                raise RuntimeError(
                    "Imagem de referência só é suportada com o motor OpenAI "
                    "por enquanto."
                )

        emit("service", "running", f"Verificando {engine_label}...")
        if not client.is_alive():
            if engine == "openai":
                raise RuntimeError(
                    "OPENAI_API_KEY não configurada. Adicione no .env do "
                    "StudyFlow e tente de novo."
                )
            raise RuntimeError(
                f"Fooocus-API indisponível em {fooocus_client.FOOOCUS_API_URL}. "
                "Suba o serviço nativo no host (python3 main.py --host 0.0.0.0 "
                "--port 8888 na pasta do Fooocus-API) e tente de novo."
            )
        emit("service", "done", "Serviço online.")

        if ai_copy:
            from tools import claude_copy_client
            if not claude_copy_client.is_alive():
                raise RuntimeError(
                    "ANTHROPIC_API_KEY não configurada — necessária pra gerar "
                    "o texto de impacto automaticamente. Adicione no .env."
                )

        cfg_label = client.PRESETS.get(preset, client.PRESETS["thumbnail"])["label"]
        emit("generate", "running", f"Gerando {cfg_label.lower()} ({engine_label})...")
        generate_kwargs = {
            "preset": preset,
            "negative_prompt": options.get("negative_prompt", ""),
        }
        if reference_images_b64 and engine == "openai":
            generate_kwargs["reference_images_b64"] = reference_images_b64
        results = client.generate_images(prompt, **generate_kwargs)
        emit("generate", "done", f"{len(results)} imagem(ns) gerada(s).")

        emit("save", "running", "Salvando em static/images...")
        # save_images() é a mesma função para os dois motores — os dois
        # clientes devolvem o resultado no mesmo formato (lista de dicts
        # com "base64").
        urls = fooocus_client.save_images(results, "static/images", f"img_{job_id[:10]}")
        emit("save", "done", f"{len(urls)} arquivo(s) salvos.")

        caption = None
        if ai_copy:
            emit("copy", "running", "Buscando contexto no RAG do projeto...")
            from tools import rag_context
            context = rag_context.get_context_for_topic(options.get("topic") or prompt)

            emit("copy", "running", "Gerando texto de impacto com Claude...")
            pilar = options.get("pilar", "Cloud + IA")
            topic = options.get("topic", prompt)
            slides_copy = claude_copy_client.generate_carousel_copy(
                pilar, topic, slide_count=len(urls), rag_context=context
            )
            caption = claude_copy_client.generate_caption(pilar, topic, slides_copy)
            emit("copy", "done", f"{len(slides_copy)} textos gerados"
                 + (" (com contexto do RAG)." if context else "."))

            emit("compose", "running", "Aplicando texto sobre as imagens...")
            from tools import carousel_composer
            # urls vêm como "/static/images/xxx.png" — resolve pro caminho
            # real em disco (mesmo padrão usado em run_instagram_publish_pipeline)
            local_paths = [u.lstrip("/") for u in urls]
            final_paths = carousel_composer.compose_carousel(
                local_paths, slides_copy,
                out_dir="static/images", out_prefix=f"img_{job_id[:10]}_final",
            )
            # devolve como URLs relativas, igual ao formato original
            urls = ["/" + p for p in final_paths]
            emit("compose", "done", f"{len(urls)} slide(s) finalizados.")

        jobs.set(job_id, "images", urls)
        if caption:
            jobs.set(job_id, "caption", caption)

        bus.publish(job_id, "complete", {
            "prompt": prompt,
            "preset": preset,
            "engine": engine,
            "images": urls,
            "caption": caption,
        })

    except Exception as e:
        jobs.set(job_id, "error", str(e))
        bus.publish(job_id, "pipeline_error", {"message": str(e)})
    finally:
        jobs.set(job_id, "done", True)
        bus.end(job_id)


# ═══════════ Publicar carrossel no Instagram — aditivo ═══════════
def run_instagram_publish_pipeline(job_id: str, image_paths: list[str], caption: str = ""):
    """Publica um carrossel (ou imagem única) no Instagram a partir de
    imagens JÁ GERADAS pelo Módulo Criador (caminhos locais em
    static/images/...). Duas etapas: sobe cada imagem pro Cloudinary
    (pra virar URL pública, que a Graph API do Instagram exige) e
    depois publica via instagram_client."""
    from tools import cloudinary_client, instagram_client
    from pathlib import Path

    def emit(step: str, status: str, detail: str = ""):
        bus.publish(job_id, "progress",
                    {"step": step, "status": status, "detail": detail})

    try:
        emit("service", "running", "Verificando Cloudinary e Instagram...")
        if not cloudinary_client.is_alive():
            raise RuntimeError(
                "Cloudinary não configurado. Defina CLOUDINARY_CLOUD_NAME, "
                "CLOUDINARY_API_KEY e CLOUDINARY_API_SECRET no .env "
                "(conta grátis em cloudinary.com)."
            )
        if not instagram_client.is_alive():
            raise RuntimeError(
                "Instagram não configurado. Defina IG_BUSINESS_ACCOUNT_ID e "
                "IG_ACCESS_TOKEN no .env — veja o guia em COMO_RODAR_CRIADOR.md."
            )
        emit("service", "done", "Serviços online.")

        emit("upload", "running", f"Subindo {len(image_paths)} imagem(ns) pro Cloudinary...")
        # image_paths vêm como URLs relativas (/static/images/xxx.png) —
        # resolve pro caminho real em disco antes de subir.
        local_paths = [p.lstrip("/") for p in image_paths]
        public_urls = cloudinary_client.upload_images(local_paths)
        emit("upload", "done", f"{len(public_urls)} imagem(ns) com URL pública.")

        emit("publish", "running", "Publicando no Instagram...")
        media_id = instagram_client.publish_carousel(public_urls, caption)
        jobs.set(job_id, "instagram_media_id", media_id)
        emit("publish", "done", "Publicado!")

        bus.publish(job_id, "complete", {
            "media_id": media_id,
            "image_count": len(public_urls),
        })

    except Exception as e:
        jobs.set(job_id, "error", str(e))
        bus.publish(job_id, "pipeline_error", {"message": str(e)})
    finally:
        jobs.set(job_id, "done", True)
        bus.end(job_id)
