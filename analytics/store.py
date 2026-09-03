"""
analytics/store.py — fecha o loop entre PREVISÃO da IA e RESULTADO real.

Toda vez que um clip é publicado (YouTube ou Instagram), guarda uma
"foto" do que a IA previu na hora (viral_score, hook, thumbnail) junto
com o ID real da publicação. Os campos de métrica real (views, retenção,
CTR...) ficam vazios até os fetchers do YouTube Analytics / Instagram
Insights (Sprint 2/3) preencherem depois.

Mesmo padrão de rag/store.py e planning/store.py — Postgres via
psycopg2, schema criado/migrado sozinho na primeira conexão.
"""

from __future__ import annotations

import json
import os
import uuid

import psycopg2
import psycopg2.extras


class AnalyticsError(RuntimeError):
    """Erro no módulo de analytics."""


PLATAFORMAS = ["youtube", "instagram"]
MODULOS = ["youtuber", "criador"]

_COLS = [
    "id", "plataforma", "external_id", "url", "modulo",
    "titulo", "hook", "viral_score", "tier", "thumb_texto", "thumb_emocao",
    "publicado_em",
    "views", "watch_time_min", "retencao_media_pct", "likes", "comentarios",
    "compartilhamentos", "ctr_pct", "alcance",
    "metricas_atualizadas_em",
    "origem", "caption", "analise_ia",
]


def _connect():
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        raise AnalyticsError("DATABASE_URL não configurada no .env")
    return psycopg2.connect(dsn)


def _ensure_table(conn) -> None:
    with conn.cursor() as c:
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS publicacoes (
                id            uuid PRIMARY KEY,
                plataforma    text NOT NULL,
                external_id   text NOT NULL,
                url           text,
                modulo        text NOT NULL DEFAULT 'youtuber',
                titulo        text DEFAULT '',
                hook          text DEFAULT '',
                viral_score   integer,
                tier          text,
                thumb_texto   text,
                thumb_emocao  text,
                publicado_em  timestamptz NOT NULL DEFAULT now(),
                views                    integer,
                watch_time_min           double precision,
                retencao_media_pct       double precision,
                likes                    integer,
                comentarios              integer,
                compartilhamentos        integer,
                ctr_pct                  double precision,
                alcance                  integer,
                metricas_atualizadas_em  timestamptz
            );
            """
        )
        # evita duplicar a mesma publicação (mesma plataforma+external_id)
        # se por acaso a rota de publish for chamada 2x pro mesmo clip
        c.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_publicacoes_plataforma_external "
            "ON publicacoes (plataforma, external_id);"
        )
        c.execute(
            "CREATE INDEX IF NOT EXISTS ix_publicacoes_modulo ON publicacoes (modulo);"
        )
        # 'sistema' = gerado pelo pipeline do StudyFlow (tem previsão da IA:
        # viral_score/tier/hook) · 'historico' = já existia na conta, puxado
        # do perfil real pro Growth (sem previsão, só métrica real)
        c.execute("ALTER TABLE publicacoes ADD COLUMN IF NOT EXISTS origem text NOT NULL DEFAULT 'sistema';")
        c.execute("ALTER TABLE publicacoes ADD COLUMN IF NOT EXISTS caption text DEFAULT '';")
        c.execute("ALTER TABLE publicacoes ADD COLUMN IF NOT EXISTS analise_ia jsonb;")
        c.execute("CREATE INDEX IF NOT EXISTS ix_publicacoes_origem ON publicacoes (origem);")
        # índice pro fetcher (Sprint 2/3) achar rápido o que ainda não
        # tem métrica atualizada recentemente
        c.execute(
            "CREATE INDEX IF NOT EXISTS ix_publicacoes_metricas_atualizadas "
            "ON publicacoes (metricas_atualizadas_em);"
        )
    conn.commit()


def _row_to_dict(row, cols) -> dict:
    d = dict(zip(cols, row))
    for campo in ("publicado_em", "metricas_atualizadas_em"):
        if d.get(campo) is not None:
            d[campo] = d[campo].isoformat()
    return d


def resumo_por_gancho(plataforma: str | None = None) -> list[dict]:
    """Agrupa pelo tipo_gancho que a IA identificou (analise_ia, Sprint B)
    e calcula a média de views/likes REAIS — é isso que responde 'qual
    tipo de gancho funciona MELHOR NO MEU perfil especificamente', não
    uma regra genérica de mercado."""
    conn = _connect()
    try:
        _ensure_table(conn)
        sql = (
            "SELECT analise_ia->>'tipo_gancho' as tipo_gancho, COUNT(*) as n, "
            "       AVG(views) as media_views, AVG(likes) as media_likes "
            "FROM publicacoes WHERE views IS NOT NULL AND analise_ia IS NOT NULL"
        )
        params: list = []
        if plataforma:
            sql += " AND plataforma = %s"
            params.append(plataforma)
        sql += " GROUP BY tipo_gancho ORDER BY media_views DESC NULLS LAST"
        with conn.cursor() as c:
            c.execute(sql, params)
            cols = ["tipo_gancho", "n", "media_views", "media_likes"]
            return [dict(zip(cols, row)) for row in c.fetchall()]
    finally:
        conn.close()


def resumo_por_tier(plataforma: str | None = None) -> list[dict]:
    """Agrupa por tier PREVISTO pela IA (S/A/B/C) e calcula a média de
    views/retenção REAIS de cada grupo — é isso que prova (ou desmente)
    se a previsão da IA bate com o resultado de verdade. Só considera
    publicações que já tiveram métrica buscada (views IS NOT NULL).

    Ordena por retenção média, não por views brutas — a partir de
    24/08/2026 o YouTube passou a contar "view" a partir do primeiro
    frame (sem tempo mínimo) em vídeos longos, igualando ao que já
    fazia com Shorts desde 2025. Isso infla view em conteúdo novo por
    causa da régua ter mudado, não porque o vídeo ficou melhor —
    retenção continua sendo a métrica que o próprio YouTube usa pra
    monetização/recomendação (chamada de "Engaged Views"/"Engaged
    Watch Hours" no Analytics deles), então é o sinal mais estável
    pra comparar tier entre si."""
    conn = _connect()
    try:
        _ensure_table(conn)
        sql = (
            "SELECT tier, COUNT(*) as n, AVG(views) as media_views, "
            "       AVG(retencao_media_pct) as media_retencao "
            "FROM publicacoes WHERE views IS NOT NULL AND tier IS NOT NULL"
        )
        params: list = []
        if plataforma:
            sql += " AND plataforma = %s"
            params.append(plataforma)
        sql += " GROUP BY tier ORDER BY media_retencao DESC NULLS LAST, media_views DESC NULLS LAST"
        with conn.cursor() as c:
            c.execute(sql, params)
            cols = ["tier", "n", "media_views", "media_retencao"]
            return [dict(zip(cols, row)) for row in c.fetchall()]
    finally:
        conn.close()


def top_publicacoes_reais(plataforma: str | None = None, limit: int = 10) -> list[dict]:
    """As publicações com mais views DE VERDADE, com a previsão da IA ao
    lado — pra achar padrão visual (ex: 'os 5 com mais view tinham
    thumb_emocao=choque em comum?')."""
    conn = _connect()
    try:
        _ensure_table(conn)
        sql = f"SELECT {', '.join(_COLS)} FROM publicacoes WHERE views IS NOT NULL"
        params: list = []
        if plataforma:
            sql += " AND plataforma = %s"
            params.append(plataforma)
        sql += " ORDER BY views DESC LIMIT %s"
        params.append(limit)
        with conn.cursor() as c:
            c.execute(sql, params)
            return [_row_to_dict(row, _COLS) for row in c.fetchall()]
    finally:
        conn.close()


def registrar_publicacao(
    plataforma: str, external_id: str, *, url: str = "", modulo: str = "youtuber",
    titulo: str = "", hook: str = "", viral_score: int | None = None,
    tier: str | None = None, thumb_texto: str = "", thumb_emocao: str = "",
    origem: str = "sistema", caption: str = "", publicado_em: str | None = None,
) -> dict:
    """Chamado logo após publicar com sucesso — guarda a 'foto' do que a
    IA previu, pra comparar com o resultado real depois. Fail-open por
    natureza: se der erro aqui, quem chama deve LOGAR mas nunca falhar a
    publicação em si por causa disso (a publicação já aconteceu de
    verdade, registrar a previsão é só telemetria).

    origem: 'sistema' (gerado pelo StudyFlow, tem previsão da IA) ou
    'historico' (post que já existia na conta, sincronizado pro Growth —
    sem previsão, só usado pra métrica real + análise de padrão depois).
    publicado_em: só usado com origem='historico', pra manter a DATA REAL
    de quando o post foi ao ar (senão usaria 'agora', o que distorceria
    qualquer análise por período)."""
    if plataforma not in PLATAFORMAS:
        raise AnalyticsError(f"Plataforma inválida: {plataforma}")
    if not external_id:
        raise AnalyticsError("external_id (video_id/media_id) é obrigatório")
    if origem not in ("sistema", "historico"):
        raise AnalyticsError(f"Origem inválida: {origem}")

    new_id = str(uuid.uuid4())
    conn = _connect()
    try:
        _ensure_table(conn)
        with conn.cursor() as c:
            if publicado_em:
                c.execute(
                    "INSERT INTO publicacoes "
                    "(id, plataforma, external_id, url, modulo, titulo, hook, "
                    " viral_score, tier, thumb_texto, thumb_emocao, origem, caption, publicado_em) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                    "ON CONFLICT (plataforma, external_id) DO UPDATE SET "
                    "  titulo = EXCLUDED.titulo, hook = EXCLUDED.hook, caption = EXCLUDED.caption, "
                    "  viral_score = EXCLUDED.viral_score, tier = EXCLUDED.tier, "
                    "  thumb_texto = EXCLUDED.thumb_texto, thumb_emocao = EXCLUDED.thumb_emocao "
                    "RETURNING id",
                    (new_id, plataforma, external_id, url, modulo, titulo, hook,
                     viral_score, tier, thumb_texto, thumb_emocao, origem, caption, publicado_em),
                )
            else:
                c.execute(
                    "INSERT INTO publicacoes "
                    "(id, plataforma, external_id, url, modulo, titulo, hook, "
                    " viral_score, tier, thumb_texto, thumb_emocao, origem, caption) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                    "ON CONFLICT (plataforma, external_id) DO UPDATE SET "
                    "  titulo = EXCLUDED.titulo, hook = EXCLUDED.hook, caption = EXCLUDED.caption, "
                    "  viral_score = EXCLUDED.viral_score, tier = EXCLUDED.tier, "
                    "  thumb_texto = EXCLUDED.thumb_texto, thumb_emocao = EXCLUDED.thumb_emocao "
                    "RETURNING id",
                    (new_id, plataforma, external_id, url, modulo, titulo, hook,
                     viral_score, tier, thumb_texto, thumb_emocao, origem, caption),
                )
            row_id = c.fetchone()[0]
        conn.commit()
        with conn.cursor() as c:
            c.execute(f"SELECT {', '.join(_COLS)} FROM publicacoes WHERE id = %s", (row_id,))
            return _row_to_dict(c.fetchone(), _COLS)
    finally:
        conn.close()


def list_publicacoes(*, modulo: str | None = None, plataforma: str | None = None,
                      limit: int = 100) -> list[dict]:
    conn = _connect()
    try:
        _ensure_table(conn)
        sql = f"SELECT {', '.join(_COLS)} FROM publicacoes WHERE 1=1"
        params: list = []
        if modulo:
            sql += " AND modulo = %s"
            params.append(modulo)
        if plataforma:
            sql += " AND plataforma = %s"
            params.append(plataforma)
        sql += " ORDER BY publicado_em DESC LIMIT %s"
        params.append(limit)
        with conn.cursor() as c:
            c.execute(sql, params)
            return [_row_to_dict(row, _COLS) for row in c.fetchall()]
    finally:
        conn.close()


def pendentes_de_metrica(horas_desde_publicacao: int = 24, limit: int = 50) -> list[dict]:
    """Lista publicações que já têm tempo suficiente no ar (padrão 24h,
    pra métrica de retenção/CTR fazer sentido) mas ainda não tiveram
    métrica buscada — é o que os fetchers do Sprint 2/3 vão consultar
    pra saber o que ir atualizar."""
    conn = _connect()
    try:
        _ensure_table(conn)
        with conn.cursor() as c:
            c.execute(
                f"SELECT {', '.join(_COLS)} FROM publicacoes "
                "WHERE publicado_em <= now() - (%s || ' hours')::interval "
                "  AND metricas_atualizadas_em IS NULL "
                "ORDER BY publicado_em ASC LIMIT %s",
                (horas_desde_publicacao, limit),
            )
            return [_row_to_dict(row, _COLS) for row in c.fetchall()]
    finally:
        conn.close()


def atualizar_metricas(publicacao_id: str, **metricas) -> dict:
    """Preenche as métricas reais (chamado pelos fetchers do Sprint 2/3).
    Aceita: views, watch_time_min, retencao_media_pct, likes, comentarios,
    compartilhamentos, ctr_pct, alcance."""
    allowed = {
        "views", "watch_time_min", "retencao_media_pct", "likes",
        "comentarios", "compartilhamentos", "ctr_pct", "alcance",
    }
    updates = {k: v for k, v in metricas.items() if k in allowed}
    if not updates:
        raise AnalyticsError("Nenhuma métrica válida pra atualizar")

    set_clause = ", ".join(f"{k} = %s" for k in updates)
    values = list(updates.values()) + [publicacao_id]

    conn = _connect()
    try:
        _ensure_table(conn)
        with conn.cursor() as c:
            c.execute(
                f"UPDATE publicacoes SET {set_clause}, metricas_atualizadas_em = now() "
                "WHERE id = %s RETURNING id",
                values,
            )
            row = c.fetchone()
            if row is None:
                raise AnalyticsError(f"Publicação {publicacao_id} não encontrada")
        conn.commit()
        with conn.cursor() as c:
            c.execute(f"SELECT {', '.join(_COLS)} FROM publicacoes WHERE id = %s", (publicacao_id,))
            return _row_to_dict(c.fetchone(), _COLS)
    finally:
        conn.close()


def salvar_analise_ia(publicacao_id: str, analise: dict) -> dict:
    """Salva a classificação da IA sobre esse post (tipo de gancho,
    presença de substância, payoff, etc — framework das skills de growth,
    ver analytics/growth_analyzer.py) na coluna analise_ia (jsonb)."""
    conn = _connect()
    try:
        _ensure_table(conn)
        with conn.cursor() as c:
            c.execute(
                "UPDATE publicacoes SET analise_ia = %s::jsonb WHERE id = %s RETURNING id",
                (json.dumps(analise), publicacao_id),
            )
            row = c.fetchone()
            if row is None:
                raise AnalyticsError(f"Publicação {publicacao_id} não encontrada")
        conn.commit()
        with conn.cursor() as c:
            c.execute(f"SELECT {', '.join(_COLS)} FROM publicacoes WHERE id = %s", (publicacao_id,))
            return _row_to_dict(c.fetchone(), _COLS)
    finally:
        conn.close()


def list_sem_analise(plataforma: str | None = None, limit: int = 50) -> list[dict]:
    """Publicações que já têm métrica real mas ainda não passaram pela
    análise de padrão da IA (Sprint B) — o que o analisador vai processar."""
    conn = _connect()
    try:
        _ensure_table(conn)
        sql = (f"SELECT {', '.join(_COLS)} FROM publicacoes "
               "WHERE views IS NOT NULL AND analise_ia IS NULL")
        params: list = []
        if plataforma:
            sql += " AND plataforma = %s"
            params.append(plataforma)
        sql += " ORDER BY views DESC LIMIT %s"
        params.append(limit)
        with conn.cursor() as c:
            c.execute(sql, params)
            return [_row_to_dict(row, _COLS) for row in c.fetchall()]
    finally:
        conn.close()
