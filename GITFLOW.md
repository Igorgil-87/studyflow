# GitFlow — como trabalhar nesse repositório

Duas branches permanentes:

- **`main`** — só código **pronto pra produção**. Todo commit aqui é
  "deployável". É a branch que os workflows `Deploy Hetzner`/`Deploy
  Oracle` usam.
- **`develop`** — onde o trabalho do dia a dia acontece. Pode ter coisa
  incompleta, em teste. Nunca faz deploy direto daqui.

Branches temporárias (você cria e apaga):

- **`feature/nome-da-coisa`** — uma funcionalidade nova. Sai de `develop`,
  volta pra `develop`.
- **`hotfix/nome-do-bug`** — correção urgente que não pode esperar o
  próximo ciclo. Sai de `main`, volta pra **`main` E `develop`** (as duas,
  senão o bug volta na próxima release).
- **`release/x.y.z`** (opcional — só quando fizer sentido "fechar uma
  versão") — última reta antes de mandar pra produção. Sai de `develop`,
  volta pra `main` e `develop`.

## Fluxo do dia a dia (a maior parte do tempo)

```bash
# 1. Sempre parte da develop atualizada
git checkout develop
git pull origin develop

# 2. Cria a branch da funcionalidade
git checkout -b feature/legenda-multilingue

# 3. Trabalha, commita normal
git add .
git commit -m "Adiciona tradução de legenda pt/en/es"

# 4. Quando terminar, sobe e abre PR pra develop (não pra main)
git push -u origin feature/legenda-multilingue
# no GitHub: abre Pull Request feature/legenda-multilingue -> develop
# o CI roda sozinho no PR — só dá pra mergear se passar

# 5. Depois do merge, apaga a branch (local e remota)
git checkout develop
git pull origin develop
git branch -d feature/legenda-multilingue
git push origin --delete feature/legenda-multilingue
```

## Mandando pra produção (`develop` → `main`)

Quando `develop` estiver num ponto bom pra ir ao ar:

```bash
git checkout main
git pull origin main
git merge --no-ff develop -m "Release: legenda multilíngue + fallback de IA"
git push origin main

# marca a versão (opcional, mas ajuda a rastrear o que foi pra produção)
git tag -a v1.1.0 -m "Legenda multilíngue + fallback de IA"
git push origin v1.1.0
```

Depois disso, vai na aba **Actions** do GitHub → `Deploy Hetzner` (ou
`Deploy Oracle`) → **Run workflow**, escolhendo a branch `main`.

## Bug urgente em produção (hotfix)

Quando algo quebrou em produção e não pode esperar terminar o que está
em andamento na `develop`:

```bash
git checkout main
git pull origin main
git checkout -b hotfix/download-travando

# corrige, testa, commita
git add .
git commit -m "Corrige timeout de rede no download"

# volta pras DUAS branches — main (produção) e develop (senão o bug
# volta na próxima vez que develop for pra main)
git checkout main
git merge --no-ff hotfix/download-travando -m "Hotfix: timeout de rede"
git push origin main

git checkout develop
git merge --no-ff hotfix/download-travando -m "Hotfix: timeout de rede"
git push origin develop

git branch -d hotfix/download-travando
```

## Regra de ouro

**Nunca commita direto na `main`.** Toda mudança passa por uma branch
temporária + PR (mesmo sendo você sozinho revisando) — é o que garante
que o CI rodou e passou antes de qualquer coisa chegar em produção.
