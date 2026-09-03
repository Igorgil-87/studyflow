# UX Sprint 4 — Simplificação estrutural de Tendências

## Objetivo
Fazer a primeira camada responder “que assunto vale acompanhar para virar conteúdo agora?”, escondendo complexidade técnica sem remover capacidades.

## Frontend only
A rota `/trends`, `/api/trends/analyze`, SSE, filtros, Crawl4AI opcional e pipeline existente foram preservados. A mudança é de hierarquia e progressive disclosure.

## Mudanças
- Remove da primeira camada o banner TRENDLIVE, ticker, mercado e Mission Control.
- Cabeçalho orientado à tarefa, filtros e uma única ação principal.
- URLs adicionais movidas para disclosure opcional.
- Pipeline renomeado para etapas compreensíveis: Coletando fontes → Analisando sinais → Organizando oportunidades.
- Resultados organizados em contexto, oportunidades, destaque/tendências e detalhes da análise.
- Modelos/fontes ficam em `Ver detalhes da análise`.
- Empty state explica o objetivo e oferece ação.

## Deliberadamente fora desta sprint
Cards, metodologia/score, detalhe individual, separação fato/síntese/interpretação e proveniência profunda pertencem às Sprints 5–8.

## Backend requirements
Nenhum para esta sprint. O backend não expõe uma contagem confiável de “fontes analisadas”, portanto a UI não inventa esse número.
