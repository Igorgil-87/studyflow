#!/usr/bin/env python3
"""
scan_secrets.py — varre o código-fonte procurando chaves de API/tokens
que tenham ficado hardcoded por engano (não no .env, que é seguro/
gitignored, mas dentro de arquivos .py/.js/.html/.yml que PODEM acabar
indo pro Git/GitHub um dia).

Rode isso:
  - de vez em quando, por precaução
  - SEMPRE antes de rodar "git add ." pela primeira vez, se um dia
    decidir versionar este projeto (hoje ainda não é um repo Git)
  - depois de qualquer sessão em que você colou uma chave em algum
    lugar "pra testar rápido" e pode ter esquecido de tirar

Uso:
    python3 scan_secrets.py
    python3 scan_secrets.py --path /caminho/do/projeto
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

# padrões de chave/token conhecidos — cada um: (nome, regex)
PATTERNS = [
    ("OpenAI API key", r"sk-[a-zA-Z0-9]{20,}"),
    ("OpenAI project key", r"sk-proj-[a-zA-Z0-9_-]{20,}"),
    ("Anthropic API key", r"sk-ant-[a-zA-Z0-9_-]{20,}"),
    ("Instagram/Meta access token", r"IGAA[A-Za-z0-9]{20,}"),
    ("Meta/Facebook access token", r"EAA[A-Za-z0-9]{30,}"),
    ("Google API key", r"AIza[A-Za-z0-9_-]{20,}"),
    ("Perplexity API key", r"pplx-[a-zA-Z0-9]{20,}"),
    ("AWS access key ID", r"AKIA[0-9A-Z]{16}"),
    ("Chave privada PEM", r"-----BEGIN (RSA |EC )?PRIVATE KEY-----"),
    ("Bitwarden session key (padrão base64 longo)", r"BW_SESSION=[\"']?[A-Za-z0-9+/=]{40,}"),
]

# pastas/arquivos que nunca precisam ser varridos (binário, dependência, etc)
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", "static/videos", "static/images"}
SKIP_EXTENSIONS = {".pyc", ".mp4", ".png", ".jpg", ".jpeg", ".gif", ".mp3", ".wav", ".zip", ".db"}
# .env é INTENCIONALMENTE ignorado aqui — ele É pra ter as chaves, e já
# está no .gitignore. O objetivo deste script é achar chave em lugar
# ERRADO (código), não o .env em si.
SKIP_FILES = {".env"}


def scan_file(path: Path) -> list[tuple[str, int, str]]:
    """Retorna [(nome_do_padrão, linha, trecho), ...] encontrados no arquivo."""
    findings = []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return findings

    for line_num, line in enumerate(text.splitlines(), start=1):
        for name, pattern in PATTERNS:
            match = re.search(pattern, line)
            if match:
                snippet = match.group(0)
                masked = snippet[:10] + "..." + snippet[-4:] if len(snippet) > 18 else snippet
                findings.append((name, line_num, masked))
    return findings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", default=".", help="Pasta raiz a varrer (padrão: pasta atual)")
    args = parser.parse_args()

    root = Path(args.path).resolve()
    total_findings = 0

    for file_path in root.rglob("*"):
        if not file_path.is_file():
            continue
        if file_path.name in SKIP_FILES:
            continue
        if file_path.suffix in SKIP_EXTENSIONS:
            continue
        if any(skip in file_path.parts for skip in SKIP_DIRS):
            continue

        findings = scan_file(file_path)
        for name, line_num, masked in findings:
            total_findings += 1
            rel = file_path.relative_to(root)
            print(f"⚠️  {rel}:{line_num} — possível {name}: {masked}")

    print()
    if total_findings == 0:
        print("✅ Nenhuma chave/token hardcoded encontrado no código.")
    else:
        print(f"🔴 {total_findings} possível(is) segredo(s) exposto(s) no código — "
              f"confere cada linha acima e move pra .env se for chave de verdade.")


if __name__ == "__main__":
    main()
