#!/usr/bin/env bash
# backup_postgres.sh — backup (e restore) do Postgres do StudyFlow.
#
# Por que isso importa: hoje os dados do RAG (embeddings indexados de
# vídeo/documento/URL) e do Planejamento (atividades, checklist) vivem
# só no volume Docker "pgdata". Se esse volume for apagado sem querer
# (ex: "docker compose down -v", ou limpeza de disco), TUDO some — sem
# aviso, sem como recuperar.
#
# Uso:
#   bash backup_postgres.sh                    # faz backup agora
#   bash backup_postgres.sh --restore ARQUIVO   # restaura de um backup
#   bash backup_postgres.sh --list              # lista backups existentes
#
# Backups ficam em ./backups/postgres/, formato:
#   studyflow_2026-07-31_143022.sql.gz

set -e

BACKUP_DIR="./backups/postgres"
CONTAINER="youtube-study-agent-postgres-1"
DB_USER="studyflow"
DB_NAME="studyflow"

mkdir -p "$BACKUP_DIR"

do_backup() {
    if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
        echo "🔴 Container '$CONTAINER' não está rodando. Sobe o StudyFlow primeiro (bash start_studyflow.sh)."
        exit 1
    fi

    local timestamp
    timestamp=$(date +%Y-%m-%d_%H%M%S)
    local outfile="${BACKUP_DIR}/studyflow_${timestamp}.sql.gz"

    echo "→ Fazendo backup do banco '$DB_NAME'..."
    docker exec "$CONTAINER" pg_dump -U "$DB_USER" "$DB_NAME" | gzip > "$outfile"

    local size
    size=$(du -h "$outfile" | cut -f1)
    echo "✅ Backup salvo: $outfile ($size)"

    # mantém só os 10 backups mais recentes, pra não acumular disco
    # infinitamente — ajusta esse número se quiser guardar mais histórico
    local count
    count=$(ls -1 "$BACKUP_DIR"/studyflow_*.sql.gz 2>/dev/null | wc -l | tr -d ' ')
    if [ "$count" -gt 10 ]; then
        echo "→ Limpando backups antigos (mantendo os 10 mais recentes)..."
        ls -1t "$BACKUP_DIR"/studyflow_*.sql.gz | tail -n +11 | xargs rm -f
    fi
}

do_restore() {
    local infile="$1"
    if [ -z "$infile" ] || [ ! -f "$infile" ]; then
        echo "🔴 Arquivo de backup não encontrado: $infile"
        echo "   Use --list pra ver os backups disponíveis."
        exit 1
    fi

    echo "⚠️  Isso vai APAGAR os dados atuais do banco '$DB_NAME' e substituir"
    echo "   pelo conteúdo de: $infile"
    read -p "   Confirma? Digite 'sim' pra continuar: " confirm
    if [ "$confirm" != "sim" ]; then
        echo "Cancelado."
        exit 0
    fi

    echo "→ Restaurando..."
    gunzip -c "$infile" | docker exec -i "$CONTAINER" psql -U "$DB_USER" "$DB_NAME"
    echo "✅ Restauração concluída."
}

do_list() {
    echo "Backups disponíveis em $BACKUP_DIR:"
    ls -lht "$BACKUP_DIR"/studyflow_*.sql.gz 2>/dev/null || echo "  (nenhum backup ainda — roda 'bash backup_postgres.sh' pra criar o primeiro)"
}

case "${1:-}" in
    --restore)
        do_restore "$2"
        ;;
    --list)
        do_list
        ;;
    "")
        do_backup
        ;;
    *)
        echo "Uso: bash backup_postgres.sh [--restore ARQUIVO | --list]"
        exit 1
        ;;
esac
