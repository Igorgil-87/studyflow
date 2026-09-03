# UX Sprint 15 — Analytics & Validação

## Objetivo
Fechar o redesign com telemetria mínima, agregada e orientada à jornada, sem capturar texto livre, URLs, títulos de tendências ou identidade bruta.

## Eventos
Home: `home_view`, `continue_learning_click`, `learn_click`, `create_click`, `trends_click`.
Tendências: `trends_view`, `trend_filter_used`, `trend_opened`, `trend_sources_opened`, `trend_create_content_clicked`, `trend_analysis_completed`, `trend_analysis_failed`.

## Métricas agregadas
`GET /api/ux/analytics?days=30` retorna contagens de eventos/usuários e funis simples Home e Tendências. O endpoint não retorna `user_key`, conteúdo do usuário ou payload de tendência.

## Interpretação
Os dados medem comportamento observado, não causalidade. Conversão baixa não prova problema de UX sem investigação qualitativa. Contagens históricas anteriores à Sprint 15 não possuem os novos eventos.

## Validação recomendada
Usar janela de 30 dias, comparar taxa de ação da Home, abertura de análise em Tendências, clique para criação e falhas de análise. Complementar com teste moderado em desktop/mobile antes de conclusões de produto.
