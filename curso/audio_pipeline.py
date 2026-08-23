"""
curso/audio_pipeline.py — pipelines ASSÍNCRONOS de áudio, POR AULA
(Fase 4 do AI Course Generation Engine). Mesmo padrão de
curso/video_pipeline.py (Fase 3): progresso via infra.bus, resultado via
infra.jobs, dispatch via infra/dispatch.py.

Dois pipelines, porque são dois produtos diferentes:
  run_audio_licao_pipeline    -> "Ouvir aula" (1 voz, narração direta)
  run_podcast_licao_pipeline  -> Podcast Mode (2 vozes, diálogo)
"""

from __future__ import annotations

from infra import bus, jobs


def run_audio_licao_pipeline(job_id: str, course_id: str, lesson_id: str, user_key: str):
    def emit(step: str, status: str, detail: str = ""):
        bus.publish(job_id, "progress", {"step": step, "status": status, "detail": detail})

    from curso.audio_render import AudioRenderError, gerar_audio_aula
    from curso.store import get_curso, get_lesson, get_lesson_content, set_lesson_status, CursoStoreError

    try:
        curso = get_curso(course_id, user_key)
        if not curso:
            raise RuntimeError("curso não encontrado")
        lesson = get_lesson(lesson_id, user_key)
        if not lesson or str(lesson["course_id"]) != course_id:
            raise RuntimeError("aula não encontrada")

        conteudo = get_lesson_content(lesson_id)
        if not conteudo or not conteudo.get("explicacao"):
            raise RuntimeError(
                "esta aula ainda não tem conteúdo textual gerado — "
                "gere o conteúdo (Fase 1) antes do áudio."
            )

        set_lesson_status(lesson_id, "gerando")
        emit("audio", "running", "Gerando narração...")

        audio_path = gerar_audio_aula(
            lesson["titulo"], conteudo["explicacao"], out_dir="static/audios/curso2",
        )
        audio_rel = audio_path.split("static/", 1)[-1] if "static/" in audio_path else audio_path
        set_lesson_status(lesson_id, "concluido", audio_url=audio_rel)
        jobs.set(job_id, "audio_url", audio_rel)

        emit("audio", "done", "Áudio pronto.")
        bus.publish(job_id, "complete", {"audio_url": audio_rel})

    except (AudioRenderError, CursoStoreError, RuntimeError) as e:
        _falhar(lesson_id, job_id, e)
    finally:
        jobs.set(job_id, "done", True)
        bus.end(job_id)


def run_podcast_licao_pipeline(job_id: str, course_id: str, lesson_id: str, user_key: str):
    def emit(step: str, status: str, detail: str = ""):
        bus.publish(job_id, "progress", {"step": step, "status": status, "detail": detail})

    from curso.audio_render import AudioRenderError, gerar_podcast_aula
    from curso.podcast_agent import PodcastAgentError, gerar_podcast_script
    from curso.store import (get_curso, get_lesson, get_lesson_content, save_podcast,
                              CursoStoreError)

    try:
        curso = get_curso(course_id, user_key)
        if not curso:
            raise RuntimeError("curso não encontrado")
        lesson = get_lesson(lesson_id, user_key)
        if not lesson or str(lesson["course_id"]) != course_id:
            raise RuntimeError("aula não encontrada")

        conteudo = get_lesson_content(lesson_id)
        if not conteudo or not conteudo.get("explicacao"):
            raise RuntimeError(
                "esta aula ainda não tem conteúdo textual gerado — "
                "gere o conteúdo (Fase 1) antes do podcast."
            )

        emit("roteiro", "running", "Roteirizando a conversa...")
        script = gerar_podcast_script(
            lesson["titulo"], conteudo["explicacao"], conteudo.get("key_takeaways_json") or [],
        )
        emit("roteiro", "done", f"{len(script['turns'])} falas roteirizadas.")

        def progresso_falas(i, total):
            emit("audio", "running", f"Narrando fala {i + 1}/{total}...")

        emit("audio", "running", "Iniciando narração...")
        podcast_path = gerar_podcast_aula(
            lesson["titulo"], script, out_dir="static/audios/curso2",
            progress_callback=progresso_falas,
        )
        podcast_rel = podcast_path.split("static/", 1)[-1] if "static/" in podcast_path else podcast_path
        save_podcast(lesson_id, script, podcast_rel)
        jobs.set(job_id, "podcast_url", podcast_rel)

        emit("audio", "done", "Podcast pronto.")
        bus.publish(job_id, "complete", {"podcast_url": podcast_rel})

    except (PodcastAgentError, AudioRenderError, CursoStoreError, RuntimeError) as e:
        jobs.set(job_id, "error", str(e))
        bus.publish(job_id, "pipeline_error", {"message": str(e)})
    finally:
        jobs.set(job_id, "done", True)
        bus.end(job_id)


def _falhar(lesson_id: str, job_id: str, e: Exception) -> None:
    from curso.store import set_lesson_status
    try:
        set_lesson_status(lesson_id, "erro")
    except Exception:
        pass  # não deixa um erro secundário mascarar o erro original
    jobs.set(job_id, "error", str(e))
    bus.publish(job_id, "pipeline_error", {"message": str(e)})
