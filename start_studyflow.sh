#!/usr/bin/env bash
# start_studyflow.sh — inicia o ambiente LOCAL do StudyFlow UX v2.
#
# Este launcher é resiliente: Fooocus e MoneyPrinterTurbo são opcionais.
# Se MoneyPrinterTurbo não existir, o StudyFlow ainda sobe para você testar
# UX, Georgina, Youtuber, Trends, Catálogo, etc. O módulo Marcos Cezar apenas
# ficará sem o motor de geração de vídeo até o MPT ser configurado.
#
# Uso:
#   ./start_studyflow.sh
#   ./start_studyflow.sh --no-build
#   ./start_studyflow.sh --no-fooocus
#   ./start_studyflow.sh --no-mpt
#   ./start_studyflow.sh --logs
#
# Caminhos opcionais:
#   MPT_DIR=/caminho/MoneyPrinterTurbo-main ./start_studyflow.sh
#   FOOOCUS_DIR=/caminho/Fooocus-API-main ./start_studyflow.sh
#
# Bitwarden é OPT-IN:
#   export BW_SESSION="$(bw unlock --raw)"
#   STUDYFLOW_SYNC_BITWARDEN=1 ./start_studyflow.sh

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

COMPOSE_FILE="docker-compose.full.yml"
FOOOCUS_DIR="${FOOOCUS_DIR:-$SCRIPT_DIR/../Fooocus-API-main}"
FOOOCUS_PORT="${FOOOCUS_PORT:-8888}"
FOOOCUS_LOG="${FOOOCUS_LOG:-/tmp/studyflow-fooocus-api.log}"
FOOOCUS_PID_FILE="${FOOOCUS_PID_FILE:-/tmp/studyflow-fooocus-api.pid}"
STUDYFLOW_URL="${STUDYFLOW_URL:-http://localhost:5001}"
MPT_URL="${MPT_URL:-http://localhost:8080}"
N8N_URL="${N8N_URL:-http://localhost:5678}"

USE_FOOOCUS=1
USE_MPT=1
DO_BUILD=1
OPEN_BROWSER=1
FOLLOW_LOGS=0

for arg in "$@"; do
  case "$arg" in
    --no-fooocus) USE_FOOOCUS=0 ;;
    --no-mpt)     USE_MPT=0 ;;
    --no-build)   DO_BUILD=0 ;;
    --no-open)    OPEN_BROWSER=0 ;;
    --logs)       FOLLOW_LOGS=1 ;;
    -h|--help)
      cat <<'HELP'
StudyFlow UX v2 — execução local

Uso:
  ./start_studyflow.sh [opções]

Opções:
  --no-fooocus  Sobe sem Fooocus-API
  --no-mpt      Sobe sem MoneyPrinterTurbo
  --no-build    Não força rebuild das imagens Docker
  --no-open     Não abre o navegador automaticamente
  --logs        Acompanha logs de web/worker/scheduler
  -h, --help    Mostra esta ajuda

Variáveis opcionais:
  FOOOCUS_DIR=/caminho/Fooocus-API-main
  MPT_DIR=/caminho/MoneyPrinterTurbo-main
  STUDYFLOW_SYNC_BITWARDEN=1
HELP
      exit 0
      ;;
    *)
      echo "❌ Opção desconhecida: $arg"
      echo "   Use: ./start_studyflow.sh --help"
      exit 2
      ;;
  esac
done

line() { printf '%s\n' "════════════════════════════════════════════════════════"; }
info() { printf '→ %s\n' "$*"; }
ok()   { printf '✓ %s\n' "$*"; }
warn() { printf '⚠ %s\n' "$*"; }
fail() { printf '❌ %s\n' "$*" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }

http_ok() {
  local url="$1" code
  code="$(curl -L -sS -o /dev/null -w '%{http_code}' --connect-timeout 2 --max-time 5 "$url" 2>/dev/null || true)"
  [[ "$code" =~ ^(200|204|301|302|303|307|308)$ ]]
}

wait_http() {
  local url="$1" seconds="$2" label="$3" elapsed=0
  while (( elapsed < seconds )); do
    if http_ok "$url"; then
      ok "$label respondeu em $url"
      return 0
    fi
    sleep 2
    elapsed=$((elapsed + 2))
  done
  return 1
}

resolve_dir() {
  local candidate="$1"
  [[ -d "$candidate" ]] || return 1
  (cd "$candidate" && pwd)
}

find_mpt_dir() {
  # 1) caminho explicitamente informado pelo usuário
  if [[ -n "${MPT_DIR:-}" ]]; then
    resolve_dir "$MPT_DIR" && return 0
    return 1
  fi

  # 2) locais comuns, sem depender do usuário do macOS
  local candidates=(
    "$SCRIPT_DIR/../MoneyPrinterTurbo-main"
    "$SCRIPT_DIR/../MoneyPrinterTurbo"
    "$HOME/Documents/GitHub/MoneyPrinterTurbo-main"
    "$HOME/Documents/GitHub/MoneyPrinterTurbo"
    "$HOME/GitHub/MoneyPrinterTurbo-main"
    "$HOME/GitHub/MoneyPrinterTurbo"
  )

  local c
  for c in "${candidates[@]}"; do
    if [[ -d "$c" ]]; then
      resolve_dir "$c"
      return 0
    fi
  done

  # 3) busca curta apenas nas pastas de desenvolvimento mais prováveis
  local base found
  for base in "$HOME/Documents/GitHub" "$HOME/GitHub" "$HOME/Documents"; do
    [[ -d "$base" ]] || continue
    found="$(find "$base" -maxdepth 3 -type d \( -name 'MoneyPrinterTurbo-main' -o -name 'MoneyPrinterTurbo' \) -print -quit 2>/dev/null || true)"
    if [[ -n "$found" ]]; then
      resolve_dir "$found"
      return 0
    fi
  done

  return 1
}

line
echo " StudyFlow UX v2 — ambiente local"
line
printf ' Projeto: %s\n\n' "$SCRIPT_DIR"

# ── Pré-flight ───────────────────────────────────────────────────────────────
[[ -f "$COMPOSE_FILE" ]] || fail "Não encontrei $COMPOSE_FILE em $SCRIPT_DIR"
[[ -f "Dockerfile" ]] || fail "Não encontrei Dockerfile em $SCRIPT_DIR"
have curl || fail "curl não encontrado."
have docker || fail "Docker não encontrado. Instale/abra o Docker Desktop."
docker info >/dev/null 2>&1 || fail "Docker Desktop não está pronto. Abra-o e tente novamente."
docker compose version >/dev/null 2>&1 || fail "O plugin 'docker compose' não está disponível."

if [[ ! -f ".env" ]]; then
  if [[ -f ".env.example" ]]; then
    cp .env.example .env
    warn ".env não existia; criei a partir de .env.example. Revise as chaves de IA."
  else
    fail "Arquivo .env não encontrado."
  fi
fi

[[ -e youtube_token.json ]] || : > youtube_token.json
[[ -e client_secret.json ]] || : > client_secret.json
if [[ ! -s client_secret.json ]]; then
  warn "client_secret.json vazio/ausente. Publicação no YouTube exigirá OAuth."
fi

# ── MoneyPrinterTurbo: auto-detect + profile opcional ────────────────────────
if (( USE_MPT == 1 )); then
  if DETECTED_MPT_DIR="$(find_mpt_dir)"; then
    export MPT_DIR="$DETECTED_MPT_DIR"
    ok "MoneyPrinterTurbo encontrado em: $MPT_DIR"
    if [[ ! -f "$MPT_DIR/config.toml" ]]; then
      if [[ -f "$MPT_DIR/config.example.toml" ]]; then
        warn "MoneyPrinterTurbo está sem config.toml. Marcos Cezar pode não gerar vídeos."
        echo "   Crie com: cp \"$MPT_DIR/config.example.toml\" \"$MPT_DIR/config.toml\""
      else
        warn "MoneyPrinterTurbo encontrado, mas config.toml/config.example.toml não existem."
      fi
    fi
  else
    USE_MPT=0
    warn "MoneyPrinterTurbo não foi encontrado."
    echo "   StudyFlow vai subir NORMALMENTE para testes de UX."
    echo "   Apenas o motor de vídeo do Marcos Cezar ficará indisponível."
    echo "   Se ele estiver em outro local, use:"
    echo "   MPT_DIR=/caminho/MoneyPrinterTurbo-main ./start_studyflow.sh"
  fi
else
  info "MoneyPrinterTurbo ignorado (--no-mpt)."
fi

# Bitwarden é opt-in. Nunca pede senha sem o usuário solicitar.
if [[ "${STUDYFLOW_SYNC_BITWARDEN:-0}" == "1" ]]; then
  info "Sincronizando .env com Bitwarden..."
  if ! have bw; then
    warn "Bitwarden CLI não instalado. Mantendo .env atual."
  elif [[ ! -f bitwarden_to_env.py ]]; then
    warn "bitwarden_to_env.py não encontrado. Mantendo .env atual."
  elif [[ -z "${BW_SESSION:-}" ]]; then
    warn "BW_SESSION não definido. Mantendo .env atual."
    echo '   Execute antes: export BW_SESSION="$(bw unlock --raw)"'
  elif python3 bitwarden_to_env.py --out .env.bw_sync >/tmp/studyflow-bw-sync.log 2>&1; then
    mv .env.bw_sync .env
    ok ".env sincronizado com Bitwarden"
  else
    warn "Sync do Bitwarden falhou. Mantendo .env atual. Veja /tmp/studyflow-bw-sync.log"
    rm -f .env.bw_sync
  fi
fi

COMPOSE_CMD=(docker compose -f "$COMPOSE_FILE")
if (( USE_MPT == 1 )); then
  COMPOSE_CMD+=(--profile mpt)
fi

info "Validando $COMPOSE_FILE..."
if ! "${COMPOSE_CMD[@]}" config --quiet 2>/tmp/studyflow-compose-validation.log; then
  cat /tmp/studyflow-compose-validation.log >&2
  fail "$COMPOSE_FILE tem erro de configuração."
fi
ok "Docker Compose válido"

# ── Fooocus nativo (opcional) ────────────────────────────────────────────────
if (( USE_FOOOCUS == 1 )); then
  echo ""
  if http_ok "http://localhost:${FOOOCUS_PORT}/ping"; then
    ok "Fooocus-API já está rodando em http://localhost:${FOOOCUS_PORT}"
  elif [[ ! -d "$FOOOCUS_DIR" ]]; then
    warn "Fooocus-API não encontrado em $FOOOCUS_DIR. Continuando sem ele."
  else
    FOOOCUS_DIR="$(cd "$FOOOCUS_DIR" && pwd)"
    PYTHON_BIN=""
    if [[ -x "$FOOOCUS_DIR/venv/bin/python3" ]]; then
      PYTHON_BIN="$FOOOCUS_DIR/venv/bin/python3"
    elif [[ -x "$FOOOCUS_DIR/.venv/bin/python3" ]]; then
      PYTHON_BIN="$FOOOCUS_DIR/.venv/bin/python3"
    elif have python3; then
      PYTHON_BIN="$(command -v python3)"
    fi

    if [[ -z "$PYTHON_BIN" || ! -f "$FOOOCUS_DIR/main.py" ]]; then
      warn "Fooocus encontrado, mas Python/main.py não está pronto. Continuando sem ele."
    else
      info "Iniciando Fooocus-API nativo em :${FOOOCUS_PORT}..."
      CAFFEINATE=()
      have caffeinate && CAFFEINATE=(caffeinate -i)
      (
        cd "$FOOOCUS_DIR"
        nohup "${CAFFEINATE[@]}" "$PYTHON_BIN" main.py \
          --host 0.0.0.0 --port "$FOOOCUS_PORT" --skip-pip \
          >"$FOOOCUS_LOG" 2>&1 &
        echo $! >"$FOOOCUS_PID_FILE"
      )
      ok "Fooocus iniciado em background (PID $(cat "$FOOOCUS_PID_FILE"))"
      if ! wait_http "http://localhost:${FOOOCUS_PORT}/ping" 300 "Fooocus-API"; then
        warn "Fooocus ainda não respondeu. StudyFlow continuará subindo."
        echo "   Log: tail -f \"$FOOOCUS_LOG\""
      fi
    fi
  fi
else
  info "Fooocus ignorado (--no-fooocus)."
fi

# ── Stack Docker ──────────────────────────────────────────────────────────────
echo ""
if (( DO_BUILD == 1 )); then
  info "Subindo StudyFlow + serviços locais (com build)..."
  "${COMPOSE_CMD[@]}" up --build -d
else
  info "Subindo StudyFlow + serviços locais (sem forçar build)..."
  "${COMPOSE_CMD[@]}" up -d
fi

echo ""
info "Aguardando serviços estabilizarem..."
sleep 5
"${COMPOSE_CMD[@]}" ps

echo ""
if ! wait_http "$STUDYFLOW_URL" 90 "StudyFlow"; then
  warn "StudyFlow ainda não respondeu em $STUDYFLOW_URL"
  echo "   Veja: ${COMPOSE_CMD[*]} logs --tail=120 web"
fi

if (( USE_MPT == 1 )); then
  if http_ok "$MPT_URL/openapi.json"; then
    ok "MoneyPrinterTurbo respondeu em $MPT_URL"
  else
    warn "MoneyPrinterTurbo ainda não respondeu em $MPT_URL"
  fi
fi

if http_ok "$N8N_URL/healthz"; then
  ok "n8n respondeu em $N8N_URL"
else
  warn "n8n ainda não respondeu em $N8N_URL"
fi

echo ""
line
echo " Ambiente local pronto"
echo ""
echo "   StudyFlow       → $STUDYFLOW_URL"
if (( USE_MPT == 1 )); then
  echo "   MoneyPrinter    → $MPT_URL"
else
  echo "   MoneyPrinter    → não iniciado (opcional)"
fi
echo "   n8n             → $N8N_URL"
echo "   PostgreSQL      → localhost:5432"
echo "   Fooocus-API     → http://localhost:${FOOOCUS_PORT}"
echo ""
echo "   Status          → ${COMPOSE_CMD[*]} ps"
echo "   Logs StudyFlow  → ${COMPOSE_CMD[*]} logs -f web worker"
echo "   Parar tudo      → ./stop_studyflow.sh"
line

if (( OPEN_BROWSER == 1 )); then
  if have open; then
    open "$STUDYFLOW_URL" >/dev/null 2>&1 || true
  elif have xdg-open; then
    xdg-open "$STUDYFLOW_URL" >/dev/null 2>&1 || true
  fi
fi

if (( FOLLOW_LOGS == 1 )); then
  echo ""
  info "Acompanhando logs (Ctrl+C sai sem derrubar containers)..."
  "${COMPOSE_CMD[@]}" logs -f web worker scheduler
fi
