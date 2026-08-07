#!/usr/bin/env python3
"""
bitwarden_to_env.py — gera/atualiza o .env do projeto a partir da pasta
"StudyFlow" no seu cofre do Bitwarden. É o caminho inverso do
env_to_bitwarden.py (aquele importou o .env PRA DENTRO do Bitwarden;
este aqui lê o Bitwarden e regenera o .env).

Fluxo pretendido: o Bitwarden vira a fonte de verdade. Quando você mudar
uma chave lá (regenerar uma API key, por exemplo), roda este script de
novo pra atualizar o .env local — sem editar o .env na mão.

PRÉ-REQUISITOS (uma vez só):
    brew install bitwarden-cli
    bw login                       # login interativo, uma vez
    export BW_SESSION="$(bw unlock --raw)"   # desbloqueia o cofre nesta
                                    # sessão do terminal (expira depois
                                    # de um tempo — repete quando precisar)

USO:
    python3 bitwarden_to_env.py                  # gera ./.env
    python3 bitwarden_to_env.py --out .env.novo   # gera em outro arquivo
                                                   # (mais seguro pra
                                                   # conferir antes de
                                                   # substituir o real)
    python3 bitwarden_to_env.py --folder StudyFlow  # nome da pasta (padrão: StudyFlow)

Nada é hardcoded aqui — o script só lê o que já está no seu cofre.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys


class BitwardenError(RuntimeError):
    pass


def _run_bw(args: list[str]) -> str:
    try:
        result = subprocess.run(
            ["bw", *args], capture_output=True, text=True, check=True
        )
    except FileNotFoundError as exc:
        raise BitwardenError(
            "Bitwarden CLI (bw) não encontrado. Instala com: brew install bitwarden-cli"
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise BitwardenError(f"Comando 'bw {' '.join(args)}' falhou: {exc.stderr.strip()}") from exc
    return result.stdout


def get_folder_id(folder_name: str) -> str:
    folders = json.loads(_run_bw(["list", "folders"]))
    # match exato primeiro; senão aceita pasta aninhada tipo "algo/StudyFlow"
    # (o Bitwarden usa "/" no próprio nome pra simular subpastas)
    for f in folders:
        if f.get("name") == folder_name:
            return f["id"]
    for f in folders:
        name = f.get("name") or ""
        if name == folder_name or name.endswith(f"/{folder_name}"):
            return f["id"]
    raise BitwardenError(
        f"Pasta '{folder_name}' não encontrada no cofre. "
        f"Pastas disponíveis: {[f.get('name') for f in folders]}"
    )


def get_items_in_folder(folder_id: str) -> list[dict]:
    items = json.loads(_run_bw(["list", "items", "--folderid", folder_id]))
    # cada item de "Nota segura" (type 2) guarda o valor no campo "notes"
    return [i for i in items if i.get("type") == 2 and i.get("notes")]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=".env", help="Arquivo de saída (padrão: .env)")
    parser.add_argument("--folder", default="StudyFlow", help="Nome da pasta no Bitwarden (padrão: StudyFlow)")
    args = parser.parse_args()

    if not _run_bw(["status"]).strip():
        raise BitwardenError("Não deu pra checar o status do Bitwarden CLI.")
    status = json.loads(_run_bw(["status"]))
    if status.get("status") != "unlocked":
        print(
            "Cofre bloqueado ou deslogado. Roda antes:\n"
            "  export BW_SESSION=\"$(bw unlock --raw)\"\n"
            "(ou 'bw login' primeiro, se ainda não tiver logado nesta máquina)"
        )
        sys.exit(1)

    folder_id = get_folder_id(args.folder)
    items = get_items_in_folder(folder_id)
    if not items:
        print(f"Nenhuma nota segura encontrada na pasta '{args.folder}'.")
        sys.exit(1)

    lines = [f"{item['name']}={item['notes']}" for item in sorted(items, key=lambda i: i["name"])]
    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"OK — {len(items)} chave(s) escrita(s) em {args.out}:")
    for item in items:
        print(f"  - {item['name']}")


if __name__ == "__main__":
    try:
        main()
    except BitwardenError as e:
        print(f"Erro: {e}")
        sys.exit(1)
