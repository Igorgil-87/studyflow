#!/usr/bin/env bash
# scripts/doctor.sh — diagnóstico rápido ANTES de rodar start_studyflow.sh.
# Checa exatamente as coisas que já deram problema nesse projeto: Docker
# fora do ar, porta ocupada, arquivo de credencial faltando.
#
# Uso: bash scripts/doctor.sh

cd "$(dirname "$0")/.."
PROBLEMS=0

ok()   { echo "✅ $1"; }
warn() { echo "⚠️  $1"; PROBLEMS=$((PROBLEMS+1)); }
fail() { echo "❌ $1"; PROBLEMS=$((PROBLEMS+1)); }

echo "── Diagnóstico do StudyFlow ──────────────────────────"

# 1. Docker rodando?
if docker info >/dev/null 2>&1; then
  ok "Docker Desktop está rodando"
else
  fail "Docker Desktop NÃO está rodando (abre o app antes de continuar)"
fi

# 2. Portas que o compose vai usar — livres ou já sendo usadas por NÓS?
check_port() {
  local port="$1"
  local service="$2"
  local user
  user=$(lsof -nP -iTCP:"$port" -sTCP:LISTEN 2>/dev/null | tail -n +2 | awk '{print $1}' | head -1)
  if [ -z "$user" ]; then
    ok "Porta $port ($service) livre"
  elif [ "$user" = "com.docke" ] || [ "$user" = "docker" ] || [[ "$user" == *"docker"* ]]; then
    ok "Porta $port ($service) já em uso pelo próprio Docker (normal se já estava rodando)"
  else
    warn "Porta $port ($service) ocupada por outro processo: $user — pode dar conflito ao subir"
  fi
}
check_port 5001 "StudyFlow web"
check_port 5432 "Postgres"
check_port 8080 "MoneyPrinter"
check_port 5678 "n8n"
check_port 8888 "Fooocus-API (nativo)"

# 3. Arquivos de credencial esperados (mesmo vazios, precisam EXISTIR —
#    senão o Docker bind mount cria uma PASTA no lugar, e td quebra)
for f in .env youtube_token.json client_secret.json; do
  if [ -f "$f" ]; then
    ok "$f existe"
  else
    warn "$f não existe — cria com 'touch $f' antes de subir (senão o Docker" \
         " cria uma PASTA vazia no lugar, e o mount quebra)"
  fi
done

# 4. .env tem as variáveis mínimas pra subir?
if [ -f .env ]; then
  for var in ANTHROPIC_API_KEY OPENAI_API_KEY DATABASE_URL; do
    if grep -q "^${var}=" .env && ! grep -q "^${var}=$" .env; then
      ok ".env tem $var preenchida"
    else
      warn ".env não tem $var preenchida (ou está vazia) — alguns módulos podem falhar"
    fi
  done
fi

# 5. Espaço em disco (Whisper + vídeos ocupam bastante)
avail_gb=$(df -g . 2>/dev/null | tail -1 | awk '{print $4}')
if [ -n "$avail_gb" ]; then
  if [ "$avail_gb" -lt 5 ]; then
    warn "Só ${avail_gb}GB livres em disco — pode faltar espaço pra vídeo/modelo Whisper"
  else
    ok "${avail_gb}GB livres em disco"
  fi
fi

echo "────────────────────────────────────────────────────"
if [ "$PROBLEMS" -eq 0 ]; then
  echo "✅ Tudo certo — pode rodar: bash start_studyflow.sh"
else
  echo "⚠️  $PROBLEMS ponto(s) de atenção acima — resolve antes de subir,"
  echo "   ou pode dar o mesmo tipo de erro que já apareceu nesse projeto."
fi
