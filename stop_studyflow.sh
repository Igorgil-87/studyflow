#!/usr/bin/env bash
# stop_studyflow.sh — derruba tudo que o start_studyflow.sh subiu:
#   1. Docker (StudyFlow + MoneyPrinter)
#   2. Fooocus-API (processo nativo no Mac)
#
# Uso (de dentro da pasta youtube-study-agent):
#     bash stop_studyflow.sh

FOOOCUS_PID_FILE="/tmp/fooocus-api.pid"

echo "════════════════════════════════════════════════════════"
echo " StudyFlow — parando tudo"
echo "════════════════════════════════════════════════════════"

echo "→ Derrubando containers Docker..."
docker compose -f docker-compose.full.yml down

if [ -f "$FOOOCUS_PID_FILE" ]; then
  PID=$(cat "$FOOOCUS_PID_FILE")
  if kill -0 "$PID" 2>/dev/null; then
    echo "→ Parando Fooocus-API (PID $PID)..."
    kill "$PID"
    rm -f "$FOOOCUS_PID_FILE"
    echo "✓ Fooocus-API parado."
  else
    echo "  (Fooocus-API já não estava rodando com esse PID — talvez você"
    echo "   tenha iniciado ele manualmente. Nada a fazer aqui.)"
    rm -f "$FOOOCUS_PID_FILE"
  fi
else
  echo "  (Nenhum PID salvo do Fooocus-API — se ele estiver rodando, foi"
  echo "   iniciado manualmente; feche a janela de terminal dele.)"
fi

echo ""
echo "✓ Tudo parado."
