"""
planning/store.py — Módulo Planejamento: atividades de produção de conteúdo
(vídeos, carrosséis, posts) com status, data de publicação e checklist.

Arquitetura: "1 dado, N visualizações" — mesmo princípio de bancos de dados
tipo Notion/AppFlowy. Uma atividade é UM registro só; Board (kanban) e
Calendário são só jeitos diferentes de consultar/exibir a mesma tabela.
Não precisa manter dado duplicado por view.

Reaproveita a MESMA infra que já existe (DATABASE_URL do Postgres do
docker-compose, psycopg2 sem ORM) — nenhum serviço novo pra manter.
"""

from __future__ import annotations

import json
import os
import uuid

STATUSES = ["ideia", "roteiro", "gravacao", "edicao", "publicado"]
STATUS_LABELS = {
    "ideia": "Ideia",
    "roteiro": "Roteiro",
    "gravacao": "Gravação",
    "edicao": "Edição",
    "publicado": "Publicado",
}
TIPOS = ["video", "carrossel", "post", "outro"]

# ── Módulo (Sprint 1) ──────────────────────────────────────────────────
# Cada card pertence a UM módulo — isso decide qual botão de ação aparece
# e quais campos extras fazem sentido pra ele. "geral" é o card genérico
# de antes (continua funcionando, sem quebrar nada que já existia).
MODULOS = ["estudo", "criador", "youtuber", "geral"]
MODULO_LABELS = {
    "estudo": "Estudo",
    "criador": "Criador",
    "youtuber": "Youtuber",
    "geral": "Geral",
}
# Campos esperados dentro de campos_extra (jsonb), por módulo — documentação,
# não é validado rigidamente (fica flexível de propósito, filosofia
# Notion/AppFlowy já mencionada no docstring do arquivo):
#   estudo:   {"materia": str, "tecnica": str, "duracao_estimada_min": int}
#   criador:  {"tipo_conteudo": "reels"|"carrossel"|"post", "pilar_conteudo": str}
#   youtuber: {"url_video": str, "plataforma": "youtube"|"instagram", "thumbnail_path": str}


class PlanningError(RuntimeError):
    """Erro no módulo de planejamento."""


def _dsn() -> str:
    return os.getenv(
        "DATABASE_URL", "postgresql://studyflow:studyflow@localhost:5432/studyflow"
    )


def _connect():
    import psycopg2  # import tardio — igual ao padrão do rag/store.py

    conn = psycopg2.connect(_dsn())
    conn.autocommit = True
    return conn


def _ensure_table(conn) -> None:
    with conn.cursor() as c:
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS atividades (
                id            uuid PRIMARY KEY,
                titulo        text NOT NULL,
                descricao     text DEFAULT '',
                status        text NOT NULL DEFAULT 'ideia',
                tipo          text NOT NULL DEFAULT 'video',
                pilar         text DEFAULT '',
                data_pub      date,
                posicao       integer NOT NULL DEFAULT 0,
                checklist     jsonb NOT NULL DEFAULT '[]',
                video_id      text,
                carrossel_job_id text,
                criado_em     timestamptz NOT NULL DEFAULT now(),
                atualizado_em timestamptz NOT NULL DEFAULT now()
            );
            """
        )
        c.execute(
            "CREATE INDEX IF NOT EXISTS ix_atividades_status ON atividades (status);"
        )
        c.execute(
            "CREATE INDEX IF NOT EXISTS ix_atividades_data_pub ON atividades (data_pub);"
        )
        # Migração (Sprint 1) — ADD COLUMN IF NOT EXISTS funciona tanto em
        # banco novo (cria já com tudo) quanto em banco que já existia
        # antes dessa mudança (adiciona sem apagar nenhum dado existente).
        c.execute("ALTER TABLE atividades ADD COLUMN IF NOT EXISTS modulo text NOT NULL DEFAULT 'geral';")
        c.execute("ALTER TABLE atividades ADD COLUMN IF NOT EXISTS hora_inicio time;")
        c.execute("ALTER TABLE atividades ADD COLUMN IF NOT EXISTS duracao_min integer;")
        c.execute("ALTER TABLE atividades ADD COLUMN IF NOT EXISTS campos_extra jsonb NOT NULL DEFAULT '{}';")
        c.execute(
            "CREATE INDEX IF NOT EXISTS ix_atividades_modulo ON atividades (modulo);"
        )
        # Índice composto pra consulta de agenda do dia (data_pub + ordena
        # por hora_inicio) — a query da Sprint 3 vai filtrar por
        # data_pub e ordenar por hora_inicio, então o índice já entra
        # pronto pra isso.
        c.execute(
            "CREATE INDEX IF NOT EXISTS ix_atividades_agenda ON atividades (data_pub, hora_inicio);"
        )


def _row_to_dict(row, cols) -> dict:
    d = dict(zip(cols, row))
    if d.get("data_pub") is not None:
        d["data_pub"] = d["data_pub"].isoformat()
    if d.get("hora_inicio") is not None:
        d["hora_inicio"] = d["hora_inicio"].isoformat(timespec="minutes")
    if d.get("criado_em") is not None:
        d["criado_em"] = d["criado_em"].isoformat()
    if d.get("atualizado_em") is not None:
        d["atualizado_em"] = d["atualizado_em"].isoformat()
    return d


_COLS = [
    "id", "titulo", "descricao", "status", "tipo", "pilar", "data_pub",
    "posicao", "checklist", "video_id", "carrossel_job_id",
    "modulo", "hora_inicio", "duracao_min", "campos_extra",
    "criado_em", "atualizado_em",
]


def list_atividades() -> list[dict]:
    """Retorna todas as atividades — front-end decide como agrupar
    (por status pro board, por data_pub pro calendário)."""
    conn = _connect()
    try:
        _ensure_table(conn)
        with conn.cursor() as c:
            c.execute(
                f"SELECT {', '.join(_COLS)} FROM atividades "
                "ORDER BY status, posicao, criado_em"
            )
            return [_row_to_dict(r, _COLS) for r in c.fetchall()]
    finally:
        conn.close()


def create_atividade(
    titulo: str, *, descricao: str = "", status: str = "ideia",
    tipo: str = "video", pilar: str = "", data_pub: str | None = None,
    video_id: str | None = None, carrossel_job_id: str | None = None,
    modulo: str = "geral", hora_inicio: str | None = None,
    duracao_min: int | None = None, campos_extra: dict | None = None,
) -> dict:
    if not titulo or not titulo.strip():
        raise PlanningError("Título é obrigatório")
    if status not in STATUSES:
        raise PlanningError(f"Status inválido: {status}")
    if tipo not in TIPOS:
        raise PlanningError(f"Tipo inválido: {tipo}")
    if modulo not in MODULOS:
        raise PlanningError(f"Módulo inválido: {modulo}")

    new_id = str(uuid.uuid4())
    conn = _connect()
    try:
        _ensure_table(conn)
        with conn.cursor() as c:
            # posiciona no fim da coluna de status (maior posicao + 1)
            c.execute("SELECT COALESCE(MAX(posicao), -1) + 1 FROM atividades WHERE status = %s", (status,))
            posicao = c.fetchone()[0]
            c.execute(
                "INSERT INTO atividades "
                "(id, titulo, descricao, status, tipo, pilar, data_pub, posicao, "
                " checklist, video_id, carrossel_job_id, modulo, hora_inicio, "
                " duracao_min, campos_extra) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'[]'::jsonb,%s,%s,%s,%s,%s,%s::jsonb)",
                (new_id, titulo.strip(), descricao, status, tipo, pilar,
                 data_pub, posicao, video_id, carrossel_job_id, modulo,
                 hora_inicio, duracao_min, json.dumps(campos_extra or {})),
            )
            c.execute(f"SELECT {', '.join(_COLS)} FROM atividades WHERE id = %s", (new_id,))
            return _row_to_dict(c.fetchone(), _COLS)
    finally:
        conn.close()


def update_atividade(atividade_id: str, **fields) -> dict:
    """Atualiza campos parciais. Aceita: titulo, descricao, status, tipo,
    pilar, data_pub, posicao, checklist (lista de {texto, feito}),
    video_id, carrossel_job_id, modulo, hora_inicio, duracao_min,
    campos_extra (dict — específico por módulo)."""
    allowed = {
        "titulo", "descricao", "status", "tipo", "pilar", "data_pub",
        "posicao", "checklist", "video_id", "carrossel_job_id",
        "modulo", "hora_inicio", "duracao_min", "campos_extra",
    }
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        raise PlanningError("Nada pra atualizar")
    if "status" in updates and updates["status"] not in STATUSES:
        raise PlanningError(f"Status inválido: {updates['status']}")
    if "tipo" in updates and updates["tipo"] not in TIPOS:
        raise PlanningError(f"Tipo inválido: {updates['tipo']}")
    if "modulo" in updates and updates["modulo"] not in MODULOS:
        raise PlanningError(f"Módulo inválido: {updates['modulo']}")

    set_clause = ", ".join(
        f"{k} = %s::jsonb" if k == "campos_extra" else f"{k} = %s"
        for k in updates
    )
    values = list(updates.values())
    if "checklist" in updates:
        idx = list(updates.keys()).index("checklist")
        values[idx] = json.dumps(updates["checklist"])
    if "campos_extra" in updates:
        idx = list(updates.keys()).index("campos_extra")
        values[idx] = json.dumps(updates["campos_extra"])

    conn = _connect()
    try:
        _ensure_table(conn)
        with conn.cursor() as c:
            c.execute(
                f"UPDATE atividades SET {set_clause}, atualizado_em = now() "
                f"WHERE id = %s",
                values + [atividade_id],
            )
            if c.rowcount == 0:
                raise PlanningError("Atividade não encontrada")
            c.execute(f"SELECT {', '.join(_COLS)} FROM atividades WHERE id = %s", (atividade_id,))
            return _row_to_dict(c.fetchone(), _COLS)
    finally:
        conn.close()


def delete_atividade(atividade_id: str) -> None:
    conn = _connect()
    try:
        _ensure_table(conn)
        with conn.cursor() as c:
            c.execute("DELETE FROM atividades WHERE id = %s", (atividade_id,))
            if c.rowcount == 0:
                raise PlanningError("Atividade não encontrada")
    finally:
        conn.close()
