#!/usr/bin/env bash
# start_studyflow.sh — sobe TUDO com um comando só:
#   1. Fooocus-API  (nativo no Mac, fora do Docker — precisa da GPU/MPS)
#   2. StudyFlow + MoneyPrinter (via docker-compose.full.yml)
#
# Por que o Fooocus-API não entra no Docker: o Docker Desktop no Mac não
# repassa acesso à GPU (nem Nvidia, nem Apple Silicon/MPS) pros containers.
# Rodando nativo, ele usa a GPU de verdade — dentro do Docker cairia pra
# CPU (minutos por imagem em vez de segundos). Esse script não muda essa
# regra; só evita você ter que abrir duas janelas de terminal na mão.
#
# Uso (de dentro da pasta youtube-study-agent):
#     bash start_studyflow.sh
#
# Pra parar tudo depois:
#     bash stop_studyflow.sh

set -e

# ── Ajuste aqui se sua pasta do Fooocus-API tiver outro nome/local ──────────
FOOOCUS_DIR="../Fooocus-API-main"
FOOOCUS_PORT=8888
FOOOCUS_LOG="/tmp/fooocus-api.log"
FOOOCUS_PID_FILE="/tmp/fooocus-api.pid"

echo "════════════════════════════════════════════════════════"
echo " StudyFlow — subindo tudo"
echo "════════════════════════════════════════════════════════"

# ── 1. Fooocus-API já está rodando? ─────────────────────────────────────────
if curl -s -o /dev/null -w "%{http_code}" "http://localhost:${FOOOCUS_PORT}/ping" 2>/dev/null | grep -q "200"; then
  echo "✓ Fooocus-API já está rodando em http://localhost:${FOOOCUS_PORT}"
else
  if [ ! -d "$FOOOCUS_DIR" ]; then
    echo "❌ Não encontrei a pasta do Fooocus-API em: $FOOOCUS_DIR"
    echo "   Ajuste a variável FOOOCUS_DIR no topo deste script."
    exit 1
  fi

  echo "→ Fooocus-API não está no ar. Iniciando..."

  # Detecta sozinho o Python certo: primeiro tenta um venv DENTRO da pasta
  # do Fooocus-API (venv/ ou .venv/); se não achar, usa o python3 do sistema
  # — o mesmo que você já usava quando rodava na mão.
  PYTHON_BIN="python3"
  if [ -x "$FOOOCUS_DIR/venv/bin/python3" ]; then
    PYTHON_BIN="$FOOOCUS_DIR/venv/bin/python3"
    echo "  (usando ambiente virtual encontrado em venv/)"
  elif [ -x "$FOOOCUS_DIR/.venv/bin/python3" ]; then
    PYTHON_BIN="$FOOOCUS_DIR/.venv/bin/python3"
    echo "  (usando ambiente virtual encontrado em .venv/)"
  else
    echo "  (usando python3 do sistema — nenhum venv/.venv encontrado na pasta)"
  fi

  # Sobe em background, log vai pro arquivo, sobrevive ao fechar o terminal
  # --skip-pip: o auto-instalador do Fooocus-API checa "torch.cuda.is_available()"
  # pra decidir se reinstala o torch — no Mac isso é SEMPRE falso (não tem CUDA),
  # então sem essa flag ele tentaria reinstalar a versão errada (CUDA) toda vez.
  # Pré-requisito (uma vez só, manual): pip3 install torch==2.1.0 torchvision==0.16.0
  # caffeinate -i: impede o Mac de suspender enquanto o Fooocus-API roda.
  # Sem isso, o macOS pode pausar o processo em segundo plano por vários
  # minutos (visto de verdade em teste: buracos de 10-15 min no log,
  # travando a geração no meio).
  (cd "$FOOOCUS_DIR" && nohup caffeinate -i "$PYTHON_BIN" main.py --host 0.0.0.0 --port "$FOOOCUS_PORT" --skip-pip \
      > "$FOOOCUS_LOG" 2>&1 &
   echo $! > "$FOOOCUS_PID_FILE")

  echo "→ Iniciado (PID $(cat "$FOOOCUS_PID_FILE")). Log em: $FOOOCUS_LOG"
  echo "→ Aguardando o serviço ficar pronto (pode levar um tempo na 1ª vez)..."

  # Espera até 5 minutos (modelos grandes podem demorar a carregar)
  READY=0
  for i in $(seq 1 150); do
    if curl -s -o /dev/null -w "%{http_code}" "http://localhost:${FOOOCUS_PORT}/ping" 2>/dev/null | grep -q "200"; then
      READY=1
      break
    fi
    sleep 2
  done

  if [ "$READY" -eq 1 ]; then
    echo "✓ Fooocus-API no ar em http://localhost:${FOOOCUS_PORT}"
  else
    echo "⚠ Fooocus-API ainda não respondeu após 5 minutos."
    echo "  Confira o log: tail -f $FOOOCUS_LOG"
    echo "  Vou continuar subindo o StudyFlow mesmo assim — a aba Imagens"
    echo "  vai avisar 'indisponível' até o Fooocus-API terminar de carregar."
  fi
fi

echo ""
echo "→ Sincronizando .env com o Bitwarden (opcional — se algo falhar, segue com o .env atual)..."
if command -v bw >/dev/null 2>&1; then
  BW_STATUS=$(bw status 2>/dev/null | grep -o '"status":"[a-z]*"' | cut -d'"' -f4)
  if [ "$BW_STATUS" = "unauthenticated" ]; then
    echo "  (Bitwarden CLI instalado mas não logado — pulando sync. 'bw login' pra ativar.)"
  else
    if [ "$BW_STATUS" != "unlocked" ] && [ -z "$BW_SESSION" ]; then
      echo "  Cofre bloqueado — digite sua senha mestra pra desbloquear"
      echo "  (ou Ctrl+C agora pra pular o sync e seguir com o .env atual):"
      export BW_SESSION="$(bw unlock --raw)" || true
    fi
    if [ -n "$BW_SESSION" ]; then
      if python3 bitwarden_to_env.py --out .env.bw_sync > /tmp/bw_sync.log 2>&1; then
        mv .env.bw_sync .env
        echo "  ✓ .env sincronizado com o Bitwarden"
      else
        echo "  ⚠ Sync falhou (detalhes em /tmp/bw_sync.log) — seguindo com o .env atual"
      fi
    else
      echo "  (Cofre não desbloqueado — seguindo com o .env atual)"
    fi
  fi
else
  echo "  (Bitwarden CLI não instalado — pulando, seguindo com o .env atual."
  echo "   'brew install bitwarden-cli' pra ativar essa sincronização.)"
fi

echo ""
echo "→ Subindo StudyFlow + MoneyPrinter via Docker..."
# Garante que os arquivos existem no host ANTES do Docker montar como
# volume — se não existir, o Docker cria uma PASTA vazia no lugar (em vez
# de erro claro), e o publish/auth.py quebra de um jeito confuso.
touch -a youtube_token.json client_secret.json 2>/dev/null

# Valida o docker-compose ANTES de gastar tempo com build — pega erro de
# sintaxe/config na hora, em vez de descobrir só depois de minutos de
# build (foi exatamente esse tipo de erro que travou o dia várias vezes).
if ! docker compose -f docker-compose.full.yml config --quiet 2>/tmp/compose_validation_error.log; then
    echo "🔴 docker-compose.full.yml tem um erro de configuração — build nem começou:"
    cat /tmp/compose_validation_error.log
    exit 1
fi

docker compose -f docker-compose.full.yml up --build -d

# Resumo de saúde: espera alguns segundos pros healthchecks rodarem e
# mostra o estado real de cada serviço — sem isso, "subiu" nem sempre
# quer dizer "está saudável" (containers podem subir e morrer em loop).
echo ""
echo "→ Conferindo saúde dos serviços (10s)..."
sleep 10
docker compose -f docker-compose.full.yml ps --format "table {{.Name}}\t{{.Status}}"

echo ""
echo "════════════════════════════════════════════════════════"
echo " Tudo no ar:"
echo "   StudyFlow      → http://localhost:5001"
echo "   Fooocus-API    → http://localhost:${FOOOCUS_PORT}"
echo "   MoneyPrinter   → http://localhost:8080"
echo "   n8n            → http://localhost:5678"
echo "════════════════════════════════════════════════════════"
echo " Pra parar tudo: bash stop_studyflow.sh"
