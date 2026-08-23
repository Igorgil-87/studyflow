# Coletar métrica real do Instagram via browser-harness (fallback do Growth)

Por quê: `analytics/instagram_fetcher.py` chama `/insights` na API oficial,
mas `tools/instagram_client.py` só tem as permissões
`instagram_business_basic` + `instagram_business_content_publish` — **não**
tem `instagram_business_manage_insights`. Sem essa permissão a chamada
falha e o Growth fica sem métrica real (fail-open silencioso). Este runbook
usa a skill browser-harness pra ler a métrica direto da tela de Insights,
com sua sessão logada no Instagram, sem depender dessa permissão.

Roda **local**, via Claude Code na sua máquina (não no servidor Hetzner —
precisa de um Chrome real com sua sessão logada). Ver
`browser-harness/install.md` se a conexão falhar.

## 1. Ver o que falta coletar

Com o StudyFlow rodando local ou apontando pro servidor:

```bash
curl -s -H "Cookie: <sua sessão de login do StudyFlow>" \
  https://studyflow.vip/api/growth/pendentes_metrica_browser | jq
```

Retorna `{"pendentes": [{"url": "...", "titulo": "...", "publicado_em": "..."}, ...]}`
— são os posts que já foram sincronizados (`Sincronizar perfil` no Growth)
mas ainda não têm métrica.

## 2. Coletar com browser-harness

No Claude Code, com o Chrome já autenticado no Instagram (Configurações →
`chrome://inspect/#remote-debugging` habilitado):

Peça ao agente, pra cada URL da lista do passo 1:

1. `new_tab(url)` na URL do post, `wait_for_load()`.
2. Clicar em "Ver insights" (só aparece pra posts da própria conta business).
3. Ler os números pela árvore de acessibilidade (não por posição de tela —
   o layout muda). Mapear pros nomes que o StudyFlow espera:
   - "Contas alcançadas" → `alcance`
   - "Visualizações" / "Reproduções" → `views`
   - "Curtidas" → `likes`
   - "Comentários" → `comentarios`
   - "Compartilhamentos" → `compartilhamentos`
4. Tirar um print do painel de Insights (screenshot) — guarda como prova
   pra relatório de marca/patrocinador depois, mesmo que o import de hoje
   não tenha campo pra anexar isso ainda.
5. Montar um item `{"url": <a mesma URL do passo 1>, "alcance": N, "views": N,
   "likes": N, "comentarios": N, "compartilhamentos": N}` — só incluir os
   campos que realmente apareceram na tela.

Repetir pra cada URL da lista, acumulando os itens num array.

## 3. Importar pro StudyFlow

Com o array de itens montado no passo 2:

```bash
curl -s -X POST https://studyflow.vip/api/growth/importar_metricas_browser \
  -H "Content-Type: application/json" \
  -H "Cookie: <sua sessão de login do StudyFlow>" \
  -d '{"dados": [ {"url": "...", "alcance": 1200, "views": 3400, "likes": 80, "comentarios": 5, "compartilhamentos": 2}, ... ]}'
```

Retorna `{"processados": N, "ok": N, "falhas": N, "detalhes": [...]}` — cada
item com `status: "ok"`, `"nao_encontrada"` (URL não bate com nenhum post
sincronizado — rodar "Sincronizar perfil" de novo) ou `"sem_metrica_valida"`.

## Segurança

Use uma conta/perfil do Chrome com a sessão do Instagram já logada, mas
evite deixar esse mesmo perfil aberto durante tarefas de agente não
relacionadas — o browser-harness usa a sessão real, com todos os
privilégios dela.
