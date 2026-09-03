"""
curso/store.py — persistência do Course Manifest (Fase 1 do AI Course
Generation Engine, ver ai-course-engine-diagnostico.md).

Mesmo padrão de analytics/store.py, rag/store.py e planning/store.py:
Postgres via psycopg2, schema criado sozinho (CREATE TABLE IF NOT EXISTS)
na primeira conexão, sem migração manual.

Isto é ADITIVO — não toca em nenhuma tabela existente (publicacoes,
user_prefs, rag_*). O run_curso_pipeline() (Opção 1 · YouTube) continua
funcionando exatamente como hoje; este módulo é a camada nova que
persiste o resultado como uma entidade de verdade em vez de só um job
efêmero + um resumo achatado em auth/prefs.py.
"""

from __future__ import annotations

import json
import os
import uuid

import psycopg2
import psycopg2.extras

ORIGENS = ["youtube", "documento"]
STATUS_CURSO = ["rascunho", "aguardando_aprovacao", "aprovado", "gerando", "concluido", "erro"]
STATUS_LESSON = ["pendente", "gerando", "concluido", "erro"]


class CursoStoreError(RuntimeError):
    """Erro no módulo de persistência do Course Manifest."""


def _connect():
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        raise CursoStoreError("DATABASE_URL não configurada no .env")
    return psycopg2.connect(dsn)


def _ensure_schema(conn) -> None:
    with conn.cursor() as c:
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS courses (
                id             uuid PRIMARY KEY,
                user_key       text NOT NULL,
                origem         text NOT NULL,
                status         text NOT NULL DEFAULT 'rascunho',
                manifest_json  jsonb NOT NULL,
                criado_em      timestamptz NOT NULL DEFAULT now(),
                atualizado_em  timestamptz NOT NULL DEFAULT now()
            );
            CREATE INDEX IF NOT EXISTS ix_courses_user_key ON courses (user_key);

            CREATE TABLE IF NOT EXISTS modules (
                id         uuid PRIMARY KEY,
                course_id  uuid NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
                titulo     text NOT NULL,
                objetivo   text DEFAULT '',
                ordem      int  NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS ix_modules_course_id ON modules (course_id);

            CREATE TABLE IF NOT EXISTS lessons (
                id                uuid PRIMARY KEY,
                module_id         uuid NOT NULL REFERENCES modules(id) ON DELETE CASCADE,
                titulo            text NOT NULL,
                objetivo          text DEFAULT '',
                ordem             int  NOT NULL DEFAULT 0,
                duracao_min       int  DEFAULT 0,
                dificuldade_estimada int DEFAULT 50,
                video_required    boolean NOT NULL DEFAULT false,
                audio_required    boolean NOT NULL DEFAULT false,
                quiz_required     boolean NOT NULL DEFAULT true,
                exercise_required boolean NOT NULL DEFAULT false,
                status            text NOT NULL DEFAULT 'pendente',
                video_url         text,
                audio_url         text
            );
            ALTER TABLE lessons ADD COLUMN IF NOT EXISTS dificuldade_estimada int DEFAULT 50;
            CREATE INDEX IF NOT EXISTS ix_lessons_module_id ON lessons (module_id);

            CREATE TABLE IF NOT EXISTS concepts (
                id                    uuid PRIMARY KEY,
                course_id             uuid NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
                nome                  text NOT NULL,
                nivel_dificuldade     text DEFAULT '',
                eh_pre_requisito_de   uuid REFERENCES concepts(id) ON DELETE SET NULL
            );
            ALTER TABLE concepts ADD COLUMN IF NOT EXISTS definicao text DEFAULT '';
            CREATE INDEX IF NOT EXISTS ix_concepts_course_id ON concepts (course_id);

            CREATE TABLE IF NOT EXISTS lesson_concepts (
                lesson_id   uuid NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
                concept_id  uuid NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
                PRIMARY KEY (lesson_id, concept_id)
            );

            CREATE TABLE IF NOT EXISTS lesson_content (
                lesson_id          uuid PRIMARY KEY REFERENCES lessons(id) ON DELETE CASCADE,
                explicacao         text DEFAULT '',
                resumo             text DEFAULT '',
                key_takeaways_json jsonb DEFAULT '[]'::jsonb,
                transcricao        text DEFAULT ''
            );
            ALTER TABLE lesson_content ADD COLUMN IF NOT EXISTS quiz_json jsonb DEFAULT '[]'::jsonb;
            ALTER TABLE lesson_content ADD COLUMN IF NOT EXISTS flashcards_json jsonb DEFAULT '[]'::jsonb;
            ALTER TABLE lesson_content ADD COLUMN IF NOT EXISTS storyboard_json jsonb;
            ALTER TABLE lesson_content ADD COLUMN IF NOT EXISTS podcast_script_json jsonb;
            ALTER TABLE lesson_content ADD COLUMN IF NOT EXISTS podcast_url text;
            ALTER TABLE lesson_content ADD COLUMN IF NOT EXISTS podcast_script_json jsonb;

            CREATE TABLE IF NOT EXISTS exercises (
                id                  uuid PRIMARY KEY,
                lesson_id           uuid NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
                tipo                text NOT NULL,
                enunciado           text NOT NULL,
                resposta_esperada   text DEFAULT '',
                avaliacao_criteria  text DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS ix_exercises_lesson_id ON exercises (lesson_id);

            CREATE TABLE IF NOT EXISTS provenance_claims (
                id          uuid PRIMARY KEY,
                lesson_id   uuid NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
                claim_text  text NOT NULL,
                tipo        text NOT NULL DEFAULT 'fonte',
                doc_id      text,
                chunk_id    text,
                page        int,
                section     text,
                source_name text,
                score       double precision
            );
            ALTER TABLE provenance_claims ADD COLUMN IF NOT EXISTS source_name text;
            ALTER TABLE provenance_claims ADD COLUMN IF NOT EXISTS score double precision;
            CREATE INDEX IF NOT EXISTS ix_provenance_lesson_id ON provenance_claims (lesson_id);

            CREATE TABLE IF NOT EXISTS knowledge_profile (
                user_key      text NOT NULL,
                concept_id    uuid NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
                score_pct     numeric NOT NULL DEFAULT 0,
                atualizado_em timestamptz NOT NULL DEFAULT now(),
                PRIMARY KEY (user_key, concept_id)
            );

            CREATE TABLE IF NOT EXISTS tutor_messages (
                id         uuid PRIMARY KEY,
                lesson_id  uuid NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
                user_key   text NOT NULL,
                role       text NOT NULL,  -- 'aluno' | 'tutor'
                content    text NOT NULL,
                criado_em  timestamptz NOT NULL DEFAULT now()
            );
            CREATE INDEX IF NOT EXISTS ix_tutor_messages_lesson_user
                ON tutor_messages (lesson_id, user_key, criado_em);

            CREATE TABLE IF NOT EXISTS exercise_attempts (
                id                 uuid PRIMARY KEY,
                exercise_id        uuid NOT NULL REFERENCES exercises(id) ON DELETE CASCADE,
                user_key           text NOT NULL,
                resposta_aluno     text NOT NULL,
                nota_pct           int,
                feedback           text,
                pontos_fortes_json jsonb DEFAULT '[]'::jsonb,
                pontos_a_melhorar_json jsonb DEFAULT '[]'::jsonb,
                criado_em          timestamptz NOT NULL DEFAULT now()
            );
            CREATE INDEX IF NOT EXISTS ix_exercise_attempts_exercise
                ON exercise_attempts (exercise_id, user_key);

            CREATE TABLE IF NOT EXISTS quiz_attempts (
                id               uuid PRIMARY KEY,
                lesson_id        uuid NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
                user_key         text NOT NULL,
                total_perguntas  int NOT NULL,
                acertos          int NOT NULL,
                criado_em        timestamptz NOT NULL DEFAULT now()
            );
            CREATE INDEX IF NOT EXISTS ix_quiz_attempts_lesson_user
                ON quiz_attempts (lesson_id, user_key, criado_em);

            CREATE TABLE IF NOT EXISTS lesson_inclusions (
                lesson_id        uuid PRIMARY KEY REFERENCES lessons(id) ON DELETE CASCADE,
                include_text     boolean,
                include_video    boolean,
                include_audio    boolean,
                include_podcast  boolean,
                include_quiz     boolean,
                include_exercise boolean,
                tutor_notes_json jsonb NOT NULL DEFAULT '[]'::jsonb,
                atualizado_em    timestamptz NOT NULL DEFAULT now()
            );
            """
        )
    conn.commit()


# ── Cursos ────────────────────────────────────────────────────────────────

def criar_curso(user_key: str, origem: str, manifest: dict) -> dict:
    """Cria o curso a partir de um manifest já montado (pelo CurriculumAgent).
    Status inicial 'aguardando_aprovacao' — o usuário revisa antes de
    disparar a geração pesada (vídeo/áudio), conforme requisito do pedido."""
    if origem not in ORIGENS:
        raise CursoStoreError(f"origem inválida: {origem!r} (use {ORIGENS})")

    course_id = uuid.uuid4()
    manifest = dict(manifest)
    manifest["course_id"] = str(course_id)
    manifest.setdefault("status", "aguardando_aprovacao")

    conn = _connect()
    try:
        _ensure_schema(conn)
        with conn.cursor() as c:
            c.execute(
                """INSERT INTO courses (id, user_key, origem, status, manifest_json)
                   VALUES (%s, %s, %s, %s, %s)""",
                (str(course_id), user_key, origem, manifest["status"], json.dumps(manifest)),
            )
            _gravar_estrutura(c, course_id, manifest)
        conn.commit()
        return manifest
    finally:
        conn.close()


def _gravar_estrutura(cursor, course_id, manifest: dict) -> None:
    """Espelha o manifest_json em tabelas relacionais (modules/lessons/
    concepts), pra permitir consulta/filtro sem precisar parsear JSON toda
    vez. O manifest_json na tabela courses continua sendo a fonte de
    verdade única — isto é só um índice consultável dele."""
    concept_ids: dict[str, str] = {}
    for nome_conceito in _coletar_conceitos(manifest):
        cid = str(uuid.uuid4())
        concept_ids[nome_conceito] = cid
        cursor.execute(
            """INSERT INTO concepts (id, course_id, nome) VALUES (%s, %s, %s)""",
            (cid, str(course_id), nome_conceito),
        )

    for m_ordem, modulo in enumerate(manifest.get("modules", [])):
        module_id = uuid.uuid4()
        cursor.execute(
            """INSERT INTO modules (id, course_id, titulo, objetivo, ordem)
               VALUES (%s, %s, %s, %s, %s)""",
            (str(module_id), str(course_id), modulo.get("title", ""),
             modulo.get("objective", ""), m_ordem),
        )
        for l_ordem, aula in enumerate(modulo.get("lessons", [])):
            lesson_id = uuid.uuid4()
            cursor.execute(
                """INSERT INTO lessons (id, module_id, titulo, objetivo, ordem,
                       duracao_min, dificuldade_estimada, video_required, audio_required,
                       quiz_required, exercise_required, status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (str(lesson_id), str(module_id), aula.get("title", ""),
                 aula.get("objective", ""), l_ordem,
                 aula.get("duration_min", 0),
                 aula.get("dificuldade_estimada", 50),
                 bool(aula.get("video_required", False)),
                 bool(aula.get("audio_required", False)),
                 bool(aula.get("quiz_required", True)),
                 bool(aula.get("exercise_required", False)),
                 aula.get("status", "pendente")),
            )
            for nome_conceito in aula.get("concepts", []):
                cid = concept_ids.get(nome_conceito)
                if cid:
                    cursor.execute(
                        """INSERT INTO lesson_concepts (lesson_id, concept_id)
                           VALUES (%s, %s) ON CONFLICT DO NOTHING""",
                        (str(lesson_id), cid),
                    )


def _coletar_conceitos(manifest: dict) -> list[str]:
    vistos, ordem = set(), []
    for modulo in manifest.get("modules", []):
        for aula in modulo.get("lessons", []):
            for nome in aula.get("concepts", []):
                if nome not in vistos:
                    vistos.add(nome)
                    ordem.append(nome)
    return ordem


def get_curso(course_id: str, user_key: str | None = None) -> dict | None:
    conn = _connect()
    try:
        _ensure_schema(conn)
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as c:
            if user_key:
                c.execute(
                    "SELECT * FROM courses WHERE id = %s AND user_key = %s",
                    (course_id, user_key),
                )
            else:
                c.execute("SELECT * FROM courses WHERE id = %s", (course_id,))
            row = c.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_cursos(user_key: str, limit: int = 50) -> list[dict]:
    conn = _connect()
    try:
        _ensure_schema(conn)
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as c:
            c.execute(
                """SELECT id, origem, status, manifest_json, criado_em, atualizado_em
                   FROM courses WHERE user_key = %s
                   ORDER BY criado_em DESC LIMIT %s""",
                (user_key, limit),
            )
            rows = c.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def atualizar_manifesto(course_id: str, user_key: str, manifest: dict) -> dict:
    """Reescreve o manifest inteiro (edição do usuário na tela de revisão)
    e re-espelha modules/lessons/concepts. Só permitido antes da geração
    pesada (status != 'gerando'/'concluido') — editar depois de gerar
    vídeo/áudio deixaria lesson.video_url órfão do manifest."""
    conn = _connect()
    try:
        _ensure_schema(conn)
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as c:
            c.execute(
                "SELECT status FROM courses WHERE id = %s AND user_key = %s",
                (course_id, user_key),
            )
            row = c.fetchone()
            if not row:
                raise CursoStoreError("curso não encontrado")
            if row["status"] in ("aprovado", "gerando", "concluido"):
                raise CursoStoreError(
                    f"curso em status '{row['status']}' não pode mais ser editado"
                )

            manifest = dict(manifest)
            manifest["course_id"] = course_id
            manifest.setdefault("status", row["status"])

            c.execute(
                """UPDATE courses SET manifest_json = %s, status = %s, atualizado_em = now()
                   WHERE id = %s""",
                (json.dumps(manifest), manifest["status"], course_id),
            )
            # apaga e regrava a estrutura relacional (mais simples e seguro
            # que fazer diff de edição parcial; o manifest_json é a fonte
            # de verdade, isto é só o índice consultável dele)
            c.execute("DELETE FROM modules WHERE course_id = %s", (course_id,))
            c.execute("DELETE FROM concepts WHERE course_id = %s", (course_id,))
            _gravar_estrutura(c, course_id, manifest)
        conn.commit()
        return manifest
    finally:
        conn.close()


def aprovar_curso(course_id: str, user_key: str) -> dict:
    """Marca o curso como aprovado — só a partir daqui a geração pesada
    (vídeo/áudio, Fase 3/4) pode ser disparada. Ponto de checkpoint
    explícito pedido: evita custo de geração de vídeo antes do usuário
    validar a estrutura pedagógica."""
    conn = _connect()
    try:
        _ensure_schema(conn)
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as c:
            c.execute(
                "SELECT manifest_json FROM courses WHERE id = %s AND user_key = %s",
                (course_id, user_key),
            )
            row = c.fetchone()
            if not row:
                raise CursoStoreError("curso não encontrado")
            manifest = row["manifest_json"]
            manifest["status"] = "aprovado"
            c.execute(
                """UPDATE courses SET status = 'aprovado', manifest_json = %s,
                       atualizado_em = now() WHERE id = %s""",
                (json.dumps(manifest), course_id),
            )
        conn.commit()
        return manifest
    finally:
        conn.close()


def set_lesson_status(lesson_id: str, status: str, **campos) -> None:
    """Atualiza o status de UMA aula (e opcionalmente video_url/audio_url).
    É o que permite retomar geração aula-a-aula sem reiniciar o curso
    inteiro (requisito 13 do pedido) — cada job de vídeo/áudio por aula
    (Fase 3/4) atualiza só a própria linha, nunca o curso inteiro."""
    if status not in STATUS_LESSON:
        raise CursoStoreError(f"status inválido: {status!r} (use {STATUS_LESSON})")
    sets = ["status = %s"]
    valores = [status]
    for campo in ("video_url", "audio_url"):
        if campo in campos:
            sets.append(f"{campo} = %s")
            valores.append(campos[campo])
    valores.append(lesson_id)

    conn = _connect()
    try:
        _ensure_schema(conn)
        with conn.cursor() as c:
            c.execute(f"UPDATE lessons SET {', '.join(sets)} WHERE id = %s", valores)
        conn.commit()
    finally:
        conn.close()


def list_lessons_pendentes(course_id: str) -> list[dict]:
    """Aulas que ainda não geraram (qualquer status != concluido) — é o
    que um worker de retomada consulta pra saber o que falta processar."""
    conn = _connect()
    try:
        _ensure_schema(conn)
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as c:
            c.execute(
                """SELECT l.* FROM lessons l
                   JOIN modules m ON m.id = l.module_id
                   WHERE m.course_id = %s AND l.status != 'concluido'
                   ORDER BY m.ordem, l.ordem""",
                (course_id,),
            )
            rows = c.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ── Aula individual ──────────────────────────────────────────────────────

def get_lesson(lesson_id: str, user_key: str) -> dict | None:
    """Busca a aula JÁ validando que ela pertence a um curso do usuário
    (join até courses) — nenhuma rota precisa reimplementar esse check."""
    conn = _connect()
    try:
        _ensure_schema(conn)
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as c:
            c.execute(
                """SELECT l.*, m.course_id, c.user_key FROM lessons l
                   JOIN modules m ON m.id = l.module_id
                   JOIN courses c ON c.id = m.course_id
                   WHERE l.id = %s AND c.user_key = %s""",
                (lesson_id, user_key),
            )
            row = c.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def save_lesson_content(lesson_id: str, *, explicacao: str = "", resumo: str = "",
                         key_takeaways: list[str] | None = None, transcricao: str = "") -> None:
    """Grava (ou substitui) o conteúdo textual de uma aula — saída do
    LessonContentAgent. UPSERT: uma aula tem no máximo uma linha aqui."""
    conn = _connect()
    try:
        _ensure_schema(conn)
        with conn.cursor() as c:
            c.execute(
                """INSERT INTO lesson_content (lesson_id, explicacao, resumo, key_takeaways_json, transcricao)
                   VALUES (%s, %s, %s, %s, %s)
                   ON CONFLICT (lesson_id) DO UPDATE SET
                       explicacao = EXCLUDED.explicacao,
                       resumo = EXCLUDED.resumo,
                       key_takeaways_json = EXCLUDED.key_takeaways_json,
                       transcricao = EXCLUDED.transcricao""",
                (lesson_id, explicacao, resumo, json.dumps(key_takeaways or []), transcricao),
            )
        conn.commit()
    finally:
        conn.close()


def save_lesson_quiz(lesson_id: str, quiz: list[dict], flashcards: list[dict]) -> None:
    """Grava quiz+flashcards de uma aula (saída de tools/quiz_generator.py,
    reaproveitado por curso/lesson_agent.py). UPSERT igual save_lesson_content
    — se a linha de conteúdo ainda não existe, cria vazia primeiro."""
    conn = _connect()
    try:
        _ensure_schema(conn)
        with conn.cursor() as c:
            c.execute(
                """INSERT INTO lesson_content (lesson_id, quiz_json, flashcards_json)
                   VALUES (%s, %s, %s)
                   ON CONFLICT (lesson_id) DO UPDATE SET
                       quiz_json = EXCLUDED.quiz_json,
                       flashcards_json = EXCLUDED.flashcards_json""",
                (lesson_id, json.dumps(quiz), json.dumps(flashcards)),
            )
        conn.commit()
    finally:
        conn.close()


def get_lesson_content(lesson_id: str) -> dict | None:
    conn = _connect()
    try:
        _ensure_schema(conn)
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as c:
            c.execute("SELECT * FROM lesson_content WHERE lesson_id = %s", (lesson_id,))
            row = c.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def save_storyboard(lesson_id: str, storyboard: dict) -> None:
    """UPSERT do storyboard — precisa que lesson_content já exista (o
    conteúdo textual, Fase 1, é pré-requisito de qualquer coisa audiovisual,
    por isso essa ordem nunca é violada nas rotas)."""
    conn = _connect()
    try:
        _ensure_schema(conn)
        with conn.cursor() as c:
            c.execute(
                "UPDATE lesson_content SET storyboard_json = %s WHERE lesson_id = %s",
                (json.dumps(storyboard), lesson_id),
            )
        conn.commit()
    finally:
        conn.close()


def save_podcast(lesson_id: str, script: dict, podcast_url: str) -> None:
    """UPSERT do roteiro+áudio do Podcast Mode (Fase 4) — mesma
    pré-condição de save_storyboard (lesson_content já existe)."""
    conn = _connect()
    try:
        _ensure_schema(conn)
        with conn.cursor() as c:
            c.execute(
                """UPDATE lesson_content SET podcast_script_json = %s, podcast_url = %s
                   WHERE lesson_id = %s""",
                (json.dumps(script), podcast_url, lesson_id),
            )
        conn.commit()
    finally:
        conn.close()


# ── Tutor IA (Fase 5) ────────────────────────────────────────────────────

def save_tutor_message(lesson_id: str, user_key: str, role: str, content: str) -> None:
    if role not in ("aluno", "tutor"):
        raise CursoStoreError(f"role inválido: {role!r} (use 'aluno' ou 'tutor')")
    conn = _connect()
    try:
        _ensure_schema(conn)
        with conn.cursor() as c:
            c.execute(
                """INSERT INTO tutor_messages (id, lesson_id, user_key, role, content)
                   VALUES (%s, %s, %s, %s, %s)""",
                (str(uuid.uuid4()), lesson_id, user_key, role, content),
            )
        conn.commit()
    finally:
        conn.close()


def get_tutor_history(lesson_id: str, user_key: str, limit: int = 20) -> list[dict]:
    """Mais antigo primeiro (ordem de conversa) — 'limit' pega as N mais
    recentes e depois inverte, então nunca corta o meio de uma conversa."""
    conn = _connect()
    try:
        _ensure_schema(conn)
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as c:
            c.execute(
                """SELECT role, content, criado_em FROM tutor_messages
                   WHERE lesson_id = %s AND user_key = %s
                   ORDER BY criado_em DESC LIMIT %s""",
                (lesson_id, user_key, limit),
            )
            rows = c.fetchall()
        return [dict(r) for r in reversed(rows)]
    finally:
        conn.close()


# ── Exercícios (Fase 5) ──────────────────────────────────────────────────

def save_exercise(lesson_id: str, exercicio: dict) -> str:
    exercise_id = str(uuid.uuid4())
    conn = _connect()
    try:
        _ensure_schema(conn)
        with conn.cursor() as c:
            c.execute(
                """INSERT INTO exercises (id, lesson_id, tipo, enunciado,
                       resposta_esperada, avaliacao_criteria)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (exercise_id, lesson_id, exercicio["tipo"], exercicio["enunciado"],
                 exercicio.get("resposta_esperada", ""), exercicio.get("avaliacao_criteria", "")),
            )
        conn.commit()
        return exercise_id
    finally:
        conn.close()


def get_exercises(lesson_id: str) -> list[dict]:
    conn = _connect()
    try:
        _ensure_schema(conn)
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as c:
            c.execute("SELECT * FROM exercises WHERE lesson_id = %s ORDER BY id", (lesson_id,))
            rows = c.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_exercise(exercise_id: str) -> dict | None:
    conn = _connect()
    try:
        _ensure_schema(conn)
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as c:
            c.execute("SELECT * FROM exercises WHERE id = %s", (exercise_id,))
            row = c.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def save_exercise_attempt(exercise_id: str, user_key: str, resposta_aluno: str, avaliacao: dict) -> str:
    attempt_id = str(uuid.uuid4())
    conn = _connect()
    try:
        _ensure_schema(conn)
        with conn.cursor() as c:
            c.execute(
                """INSERT INTO exercise_attempts
                       (id, exercise_id, user_key, resposta_aluno, nota_pct, feedback,
                        pontos_fortes_json, pontos_a_melhorar_json)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (attempt_id, exercise_id, user_key, resposta_aluno,
                 avaliacao.get("nota_pct"), avaliacao.get("feedback", ""),
                 json.dumps(avaliacao.get("pontos_fortes", [])),
                 json.dumps(avaliacao.get("pontos_a_melhorar", []))),
            )
        conn.commit()
        return attempt_id
    finally:
        conn.close()


def get_exercise_attempts(exercise_id: str, user_key: str) -> list[dict]:
    conn = _connect()
    try:
        _ensure_schema(conn)
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as c:
            c.execute(
                """SELECT * FROM exercise_attempts WHERE exercise_id = %s AND user_key = %s
                   ORDER BY criado_em""",
                (exercise_id, user_key),
            )
            rows = c.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ── Calibração previsão-vs-realidade (Sprint B) ──────────────────────────
# Mesmo espírito do resumo_por_tier do Growth (analytics/store.py): nada
# de tabela extra de "previsão" — cada consulta agrega o que já existe
# na hora, na consulta em si.

def registrar_tentativa_quiz(lesson_id: str, user_key: str, total_perguntas: int, acertos: int) -> str:
    """Registra o resultado de um quiz/checkpoint respondido — é a
    ÚNICA gravação de resultado de quiz que existe no produto inteiro
    (nem o Modo YouTube original salvava isso). Usada como sinal de
    'realidade' pra calibrar o ExerciseAgent (Sprint B2)."""
    if acertos > total_perguntas or acertos < 0 or total_perguntas <= 0:
        raise CursoStoreError(
            f"acertos ({acertos}) precisa estar entre 0 e total_perguntas ({total_perguntas})"
        )
    attempt_id = str(uuid.uuid4())
    conn = _connect()
    try:
        _ensure_schema(conn)
        with conn.cursor() as c:
            c.execute(
                """INSERT INTO quiz_attempts (id, lesson_id, user_key, total_perguntas, acertos)
                   VALUES (%s, %s, %s, %s, %s)""",
                (attempt_id, lesson_id, user_key, total_perguntas, acertos),
            )
        conn.commit()
        return attempt_id
    finally:
        conn.close()


def calibracao_exercicios(course_id: str | None = None) -> list[dict]:
    """A nota que o ExerciseAgent deu pra resposta do aluno (previsto)
    bate com o desempenho real do MESMO aluno no quiz da MESMA aula,
    depois? Agrupa em faixas de nota prevista (0-40/40-70/70-100) e
    compara com a taxa de acerto média real de quem tirou aquela nota.
    Só considera quiz respondido DEPOIS do exercício (senão não é
    'resultado depois', é só coincidência de tempo)."""
    conn = _connect()
    try:
        _ensure_schema(conn)
        sql = """
            WITH pares AS (
                SELECT
                    ea.nota_pct AS nota_prevista,
                    (qa.acertos::numeric / NULLIF(qa.total_perguntas, 0) * 100) AS taxa_acerto_real
                FROM exercise_attempts ea
                JOIN exercises ex ON ex.id = ea.exercise_id
                JOIN lessons l ON l.id = ex.lesson_id
                JOIN modules m ON m.id = l.module_id
                JOIN quiz_attempts qa
                    ON qa.lesson_id = ex.lesson_id
                   AND qa.user_key = ea.user_key
                   AND qa.criado_em > ea.criado_em
                WHERE ea.nota_pct IS NOT NULL
        """
        params: list = []
        if course_id:
            sql += " AND m.course_id = %s"
            params.append(course_id)
        sql += """
            )
            SELECT
                CASE
                    WHEN nota_prevista < 40 THEN 'baixa (0-40)'
                    WHEN nota_prevista < 70 THEN 'média (40-70)'
                    ELSE 'alta (70-100)'
                END AS faixa_prevista,
                COUNT(*) AS n,
                AVG(nota_prevista) AS media_prevista,
                AVG(taxa_acerto_real) AS media_real
            FROM pares
            GROUP BY faixa_prevista
            ORDER BY media_prevista
        """
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as c:
            c.execute(sql, params)
            return [dict(r) for r in c.fetchall()]
    finally:
        conn.close()


def calibracao_tutor(course_id: str | None = None, janela_minutos: int = 20) -> dict:
    """O Tutor IA está ajudando de verdade? Heurística: se o aluno NÃO
    fez outra pergunta na MESMA aula dentro de `janela_minutos` depois
    de uma resposta do tutor, conta como 'resolvido' — é uma aproximação
    (não sabemos de verdade se entendeu), documentado como tal. Não
    precisa de tabela nova, usa tutor_messages que já existe (Fase 5)."""
    conn = _connect()
    try:
        _ensure_schema(conn)
        sql = """
            WITH perguntas AS (
                SELECT tm.id, tm.lesson_id, tm.user_key, tm.criado_em,
                       LEAD(tm.criado_em) OVER (
                           PARTITION BY tm.lesson_id, tm.user_key ORDER BY tm.criado_em
                       ) AS proxima_pergunta_em
                FROM tutor_messages tm
                JOIN lessons l ON l.id = tm.lesson_id
                JOIN modules m ON m.id = l.module_id
                WHERE tm.role = 'aluno'
        """
        params: list = []
        if course_id:
            sql += " AND m.course_id = %s"
            params.append(course_id)
        sql += """
            )
            SELECT
                COUNT(*) AS total_perguntas,
                COUNT(*) FILTER (
                    WHERE proxima_pergunta_em IS NULL
                       OR proxima_pergunta_em > criado_em + (%s || ' minutes')::interval
                ) AS resolvidas_sem_nova_pergunta
            FROM perguntas
        """
        params.append(janela_minutos)
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as c:
            c.execute(sql, params)
            row = dict(c.fetchone())
        total = row["total_perguntas"] or 0
        resolvidas = row["resolvidas_sem_nova_pergunta"] or 0
        row["taxa_resolucao_pct"] = round(resolvidas / total * 100, 1) if total else None
        return row
    finally:
        conn.close()


def calibracao_dificuldade(course_id: str | None = None) -> list[dict]:
    """A dificuldade que o CurriculumAgent estimou pra aula (previsto)
    bate com a realidade? Relação esperada é INVERSA: aula prevista como
    mais difícil deveria ter taxa de acerto REAL menor no quiz. Agrupa
    por faixa de dificuldade prevista e mostra a taxa de acerto média
    real de cada faixa — se a calibração estiver certa, 'alta' deveria
    ter a menor taxa de acerto, 'baixa' a maior."""
    conn = _connect()
    try:
        _ensure_schema(conn)
        sql = """
            SELECT
                CASE
                    WHEN l.dificuldade_estimada < 40 THEN 'baixa (0-40)'
                    WHEN l.dificuldade_estimada < 70 THEN 'média (40-70)'
                    ELSE 'alta (70-100)'
                END AS faixa_prevista,
                COUNT(DISTINCT l.id) AS n_aulas,
                COUNT(qa.id) AS n_tentativas_quiz,
                AVG(l.dificuldade_estimada) AS media_dificuldade_prevista,
                AVG(qa.acertos::numeric / NULLIF(qa.total_perguntas, 0) * 100) AS media_acerto_real
            FROM lessons l
            JOIN modules m ON m.id = l.module_id
            LEFT JOIN quiz_attempts qa ON qa.lesson_id = l.id
            WHERE l.dificuldade_estimada IS NOT NULL
        """
        params: list = []
        if course_id:
            sql += " AND m.course_id = %s"
            params.append(course_id)
        sql += """
            GROUP BY faixa_prevista
            ORDER BY media_dificuldade_prevista
        """
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as c:
            c.execute(sql, params)
            return [dict(r) for r in c.fetchall()]
    finally:
        conn.close()


def save_podcast_script(lesson_id: str, script: dict) -> None:
    """UPSERT do roteiro de podcast (Fase 4) — mesmo padrão de
    save_storyboard, mesma pré-condição (lesson_content já existir)."""
    conn = _connect()
    try:
        _ensure_schema(conn)
        with conn.cursor() as c:
            c.execute(
                "UPDATE lesson_content SET podcast_script_json = %s WHERE lesson_id = %s",
                (json.dumps(script), lesson_id),
            )
        conn.commit()
    finally:
        conn.close()


def list_lessons(course_id: str) -> list[dict]:
    """TODAS as aulas do curso (qualquer status) — usado pelo Mapa Mental
    e por qualquer tela que precise navegar pelo curso inteiro, diferente
    de list_lessons_pendentes (que só traz o que falta gerar)."""
    conn = _connect()
    try:
        _ensure_schema(conn)
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as c:
            c.execute(
                """SELECT l.*, m.course_id, m.titulo AS modulo_titulo, m.ordem AS modulo_ordem
                   FROM lessons l
                   JOIN modules m ON m.id = l.module_id
                   WHERE m.course_id = %s
                   ORDER BY m.ordem, l.ordem""",
                (course_id,),
            )
            rows = c.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ── Provenance (Fase 2) ──────────────────────────────────────────────────

def save_provenance(lesson_id: str, claims: list[dict]) -> None:
    """Grava as afirmações/trechos usados pra gerar o conteúdo de uma aula.
    SUBSTITUI as claims anteriores dessa aula (uma regeneração de conteúdo
    invalida a proveniência antiga). Cada claim: {claim_text, tipo
    ('fonte'|'complementar'), doc_id, chunk_id, page, section}."""
    conn = _connect()
    try:
        _ensure_schema(conn)
        with conn.cursor() as c:
            c.execute("DELETE FROM provenance_claims WHERE lesson_id = %s", (lesson_id,))
            for claim in claims:
                c.execute(
                    """INSERT INTO provenance_claims
                       (id, lesson_id, claim_text, tipo, doc_id, chunk_id, page, section, source_name, score)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (str(uuid.uuid4()), lesson_id, claim.get("claim_text", ""),
                     claim.get("tipo", "fonte"), claim.get("doc_id"), claim.get("chunk_id"),
                     claim.get("page"), claim.get("section"), claim.get("source_name"), claim.get("score")),
                )
        conn.commit()
    finally:
        conn.close()


def get_provenance(lesson_id: str) -> list[dict]:
    conn = _connect()
    try:
        _ensure_schema(conn)
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as c:
            c.execute(
                "SELECT * FROM provenance_claims WHERE lesson_id = %s ORDER BY id",
                (lesson_id,),
            )
            rows = c.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ── Glossário (Fase 2) ───────────────────────────────────────────────────

def save_concept_definitions(course_id: str, definicoes: dict[str, str]) -> int:
    """definicoes: {nome_do_conceito: definição}. Casa por nome exato com
    o que já foi gravado em concepts (vem do manifest, ver _gravar_estrutura).
    Termos do dict que não batem com nenhum concept existente são
    ignorados (fail-open — não cria concept novo aqui)."""
    conn = _connect()
    try:
        _ensure_schema(conn)
        atualizados = 0
        with conn.cursor() as c:
            for nome, definicao in definicoes.items():
                c.execute(
                    "UPDATE concepts SET definicao = %s WHERE course_id = %s AND nome = %s",
                    (definicao, course_id, nome),
                )
                atualizados += c.rowcount
        conn.commit()
        return atualizados
    finally:
        conn.close()


def get_glossario(course_id: str) -> list[dict]:
    """Lista de conceitos do curso com definição (se já gerada) e as
    aulas onde cada um aparece (via lesson_concepts) — pra poder navegar
    do termo direto pra aula."""
    conn = _connect()
    try:
        _ensure_schema(conn)
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as c:
            c.execute(
                """SELECT co.id, co.nome, co.definicao,
                       COALESCE(json_agg(json_build_object('lesson_id', l.id, 'titulo', l.titulo))
                                FILTER (WHERE l.id IS NOT NULL), '[]') AS licoes
                   FROM concepts co
                   LEFT JOIN lesson_concepts lc ON lc.concept_id = co.id
                   LEFT JOIN lessons l ON l.id = lc.lesson_id
                   WHERE co.course_id = %s
                   GROUP BY co.id, co.nome, co.definicao
                   ORDER BY co.nome""",
                (course_id,),
            )
            rows = c.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ── Seleção editorial do curso final (V15) ─────────────────────────────
def get_lesson_inclusion(lesson_id: str) -> dict:
    """Retorna o que entra no curso final. Campos NULL herdam a intenção
    pedagógica original da aula; assim cursos já existentes ganham o novo
    recurso sem migração destrutiva."""
    conn = _connect()
    try:
        _ensure_schema(conn)
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as c:
            c.execute("SELECT * FROM lessons WHERE id = %s", (lesson_id,))
            lesson = c.fetchone()
            if not lesson:
                raise CursoStoreError("aula não encontrada")
            c.execute("SELECT * FROM lesson_inclusions WHERE lesson_id = %s", (lesson_id,))
            row = c.fetchone()
        row = dict(row) if row else {}
        def val(name, fallback):
            return fallback if row.get(name) is None else bool(row.get(name))
        return {
            "lesson_id": lesson_id,
            "include_text": val("include_text", True),
            "include_video": val("include_video", bool(lesson["video_required"])),
            "include_audio": val("include_audio", bool(lesson["audio_required"])),
            "include_podcast": val("include_podcast", False),
            "include_quiz": val("include_quiz", bool(lesson["quiz_required"])),
            "include_exercise": val("include_exercise", bool(lesson["exercise_required"])),
            "tutor_notes": row.get("tutor_notes_json") or [],
        }
    finally:
        conn.close()


def save_lesson_inclusion(lesson_id: str, patch: dict) -> dict:
    atual = get_lesson_inclusion(lesson_id)
    permitidos = {"include_text", "include_video", "include_audio", "include_podcast",
                  "include_quiz", "include_exercise"}
    for k in permitidos:
        if k in patch:
            atual[k] = bool(patch[k])
    notes = list(atual.get("tutor_notes") or [])
    nota = patch.get("add_tutor_note")
    if isinstance(nota, str) and nota.strip() and nota.strip() not in notes:
        notes.append(nota.strip())
    remover = patch.get("remove_tutor_note")
    if isinstance(remover, str) and remover in notes:
        notes.remove(remover)

    conn = _connect()
    try:
        _ensure_schema(conn)
        with conn.cursor() as c:
            c.execute(
                """INSERT INTO lesson_inclusions
                   (lesson_id, include_text, include_video, include_audio, include_podcast,
                    include_quiz, include_exercise, tutor_notes_json, atualizado_em)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,now())
                   ON CONFLICT (lesson_id) DO UPDATE SET
                     include_text=EXCLUDED.include_text, include_video=EXCLUDED.include_video,
                     include_audio=EXCLUDED.include_audio, include_podcast=EXCLUDED.include_podcast,
                     include_quiz=EXCLUDED.include_quiz, include_exercise=EXCLUDED.include_exercise,
                     tutor_notes_json=EXCLUDED.tutor_notes_json, atualizado_em=now()""",
                (lesson_id, atual["include_text"], atual["include_video"], atual["include_audio"],
                 atual["include_podcast"], atual["include_quiz"], atual["include_exercise"],
                 json.dumps(notes)),
            )
        conn.commit()
    finally:
        conn.close()
    atual["tutor_notes"] = notes
    return atual
