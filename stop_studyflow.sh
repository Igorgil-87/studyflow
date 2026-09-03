#!/usr/bin/env bash
# stop_studyflow.sh — para o ambiente LOCAL iniciado por start_studyflow.sh.
#
# Uso:
#   ./stop_studyflow.sh
#
# Opções:
#   ./stop_studyflow.sh --volumes   # TAMBÉM apaga volumes locais (dados!)
#   ./stop_studyflow.sh --keep-fooocus

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

COMPOSE_FILE="docker-compose.full.yml"
FOOOCUS_PID_FILE="${FOOOCUS_PID_FILE:-/tmp/studyflow-fooocus-api.pid}"

REMOVE_VOLUMES=0
STOP_FOOOCUS=1

for arg in "$@"; do
  case "$arg" in
    --volumes) REMOVE_VOLUMES=1 ;;
    --keep-fooocus) STOP_FOOOCUS=0 ;;
    -h|--help)
      cat <<'HELP'
StudyFlow UX v2 — parar ambiente local

Uso:
  ./stop_studyflow.sh [opções]

Opções:
  --volumes       Remove também volumes/dados locais (destrutivo)
  --keep-fooocus  Mantém o Fooocus-API em execução
  -h, --help      Mostra esta ajuda
HELP
      exit 0
      ;;
    *)
      echo "❌ Opção desconhecida: $arg"
      exit 2
      ;;
  esac
done

line() { printf '%s\n' "════════════════════════════════════════════════════════"; }
info() { printf '→ %s\n' "$*"; }
ok()   { printf '✓ %s\n' "$*"; }
warn() { printf '⚠ %s\n' "$*"; }

line
echo " StudyFlow UX v2 — parando ambiente local"
line

if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1 && [[ -f "$COMPOSE_FILE" ]]; then
  if (( REMOVE_VOLUMES == 1 )); then
    echo ""
    warn "--volumes foi informado: PostgreSQL, n8n e mídias persistidas serão removidos."
    info "Derrubando containers e volumes..."
    docker compose -f "$COMPOSE_FILE" down --remove-orphans --volumes
  else
    info "Derrubando containers (mantendo volumes/dados)..."
    docker compose -f "$COMPOSE_FILE" down --remove-orphans
  fi
  ok "Stack Docker parada"
else
  warn "Docker indisponível ou compose não encontrado; pulando containers."
fi

if (( STOP_FOOOCUS == 1 )); then
  echo ""
  if [[ -f "$FOOOCUS_PID_FILE" ]]; then
    PID="$(cat "$FOOOCUS_PID_FILE" 2>/dev/null || true)"
    if [[ "$PID" =~ ^[0-9]+$ ]] && kill -0 "$PID" 2>/dev/null; then
      info "Parando Fooocus-API iniciado pelo StudyFlow (PID $PID)..."
      # Encerra filhos diretos (ex.: python sob caffeinate) e depois o wrapper.
      pkill -TERM -P "$PID" 2>/dev/null || true
      kill -TERM "$PID" 2>/dev/null || true
      sleep 1
      if kill -0 "$PID" 2>/dev/null; then
        kill -KILL "$PID" 2>/dev/null || true
      fi
      ok "Fooocus-API parado"
    else
      warn "PID salvo do Fooocus não está mais ativo."
    fi
    rm -f "$FOOOCUS_PID_FILE"
  else
    echo "  (Nenhum Fooocus iniciado por este script.)"
  fi
else
  info "Fooocus mantido em execução (--keep-fooocus)."
fi

echo ""
if (( REMOVE_VOLUMES == 1 )); then
  ok "Ambiente local parado e volumes locais removidos."
else
  ok "Ambiente local parado. Dados persistentes foram mantidos."
fi
