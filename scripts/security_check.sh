#!/usr/bin/env bash
# scripts/security_check.sh — auditoria rápida de segredos expostos, sem
# precisar instalar gitleaks/trufflehog. Baseado nos padrões da skill
# "Security Reviewer" (Jeffallan/claude-skills).
#
# Uso: bash scripts/security_check.sh
# Roda ANTES de qualquer commit/push, ou sempre que desconfiar que colou
# uma chave em algum lugar que não devia.

set -uo pipefail
cd "$(dirname "$0")/.."

FOUND=0

check() {
  local label="$1"
  local pattern="$2"
  local hits
  hits=$(grep -rnE "$pattern" \
    --include="*.py" --include="*.js" --include="*.html" \
    --include="*.json" --include="*.yml" --include="*.yaml" \
    --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=__pycache__ \
    . 2>/dev/null | grep -v "\.env\.example" | grep -v "security_check.sh")
  if [ -n "$hits" ]; then
    echo "⚠️  $label:"
    echo "$hits" | sed 's/^/    /'
    echo ""
    FOUND=1
  fi
}

echo "Auditando segredos expostos em $(pwd)..."
echo ""

check "Chave da OpenAI"          "sk-[a-zA-Z0-9]{20,}"
check "Chave da Anthropic"       "sk-ant-[a-zA-Z0-9_-]{20,}"
check "Chave da AWS"             "AKIA[0-9A-Z]{16}"
check "Token do GitHub"          "ghp_[A-Za-z0-9]{30,}"
check "Token do Slack"           "xox[baprs]-[A-Za-z0-9-]{10,}"
check "Chave do Stripe"          "sk_live_[A-Za-z0-9]{20,}"
check "Chave privada (RSA/EC)"   "-----BEGIN[A-Z ]*PRIVATE KEY-----"
check "JWT (token codificado)"   "eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}"

if [ "$FOUND" -eq 0 ]; then
  echo "✅ Nenhum segredo hardcoded encontrado nos arquivos do projeto."
else
  echo "❌ Achou pelo menos um segredo em texto puro no código — não" \
       "comita antes de resolver. Move pro .env e usa os.getenv() no lugar."
  exit 1
fi
