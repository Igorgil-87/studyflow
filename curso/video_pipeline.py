"""
curso/video_pipeline.py — pipeline ASSÍNCRONO de geração de vídeo, POR
AULA (Fase 3 do AI Course Generation Engine, ver
ai-course-engine-diagnostico.md, seções 8 e 12).

Segue o mesmo padrão de pipelines.py: progresso via infra.bus (SSE),
resultado/erro via infra.jobs. Roda no worker (RQ, modo redis em produção)
ou numa thread (modo inline, dev) — infra/dispatch.py já abstrai isso,
não precisa de nada novo aqui.

Por que um pipeline por AULA, não por curso inteiro: é a peça que
satisfaz o requisito "operações caras devem poder ser retomadas sem
reiniciar o curso inteiro" — se o vídeo de uma aula falhar (ex: TTS fora
do ar), só ela fica com status='erro'; as outras aulas do curso não são
afetadas nem precisam ser refeitas.
"""

from __future__ import annotations

from infra import bus, jobs


def run_video_licao_pipeline(job_id: str, course_id: str, lesson_id: str, user_key: str):
    def emit(step: str, status: str, detail: str = ""):
        bus.publish(job_id, "progress", {"step": step, "status": status, "detail": detail})

    from curso.store import (get_curso, get_lesson, get_lesson_content, save_storyboard,
                              set_lesson_status, CursoStoreError)
    from curso.storyboard_agent import gerar_storyboard, StoryboardAgentError
    from curso.video_render import gerar_video_aula, VideoRenderError

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
                "gere o conteúdo (Fase 1) antes do vídeo."
            )

        set_lesson_status(lesson_id, "gerando")

        emit("storyboard", "running", "Roteirizando as cenas...")
        storyboard = gerar_storyboard(
            lesson["titulo"], conteudo["explicacao"], conteudo.get("key_takeaways_json") or [],
        )
        save_storyboard(lesson_id, storyboard)
        emit("storyboard", "done", f"{len(storyboard['scenes'])} cenas roteirizadas.")

        def progresso_cenas(i, total):
            emit("render", "running", f"Renderizando cena {i + 1}/{total}...")

        emit("render", "running", "Iniciando renderização...")
        video_path = gerar_video_aula(
            lesson["titulo"], storyboard, out_dir="static/videos/curso2",
            progress_callback=progresso_cenas,
        )
        emit("render", "done", "Vídeo montado.")

        # caminho relativo à pasta static/, mesmo padrão usado pro vídeo
        # do Youtuber (video_rel em pipelines.run_curso_pipeline)
        video_rel = video_path.split("static/", 1)[-1] if "static/" in video_path else video_path
        set_lesson_status(lesson_id, "concluido", video_url=video_rel)
        jobs.set(job_id, "video_url", video_rel)

        bus.publish(job_id, "complete", {"video_url": video_rel})

    except (StoryboardAgentError, VideoRenderError, CursoStoreError, RuntimeError) as e:
        from curso.store import set_lesson_status as _set_status
        try:
            _set_status(lesson_id, "erro")
        except Exception:
            pass  # não deixa um erro secundário mascarar o erro original
        jobs.set(job_id, "error", str(e))
        bus.publish(job_id, "pipeline_error", {"message": str(e)})
    finally:
        jobs.set(job_id, "done", True)
        bus.end(job_id)
