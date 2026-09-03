# UX Sprint 14 — Responsividade

Escopo: refinamento transversal de Home, Georgina e Tendências sobre a V38, preservando identidade, APIs e regras de negócio.

## Auditoria
- Breakpoints já existiam em 1023/900/700/639/600/380px, mas alguns componentes apenas comprimiam.
- Riscos encontrados: overflow horizontal, topbar da Home apertada, controles Georgina em duas colunas estreitas, cards/drawer de Tendências em telas pequenas, safe areas e palavras longas.

## Implementação
- Contenção global de overflow e mídia fluida.
- Tablet: padding consistente, grids e controles com min-width seguro.
- Mobile: safe-area, topbar compacta, cards Home preservando leitura, filtros horizontais, cards Tendências flexíveis, drawer com `dvh`, ações acima da safe-area, controles Georgina em coluna única.
- 380px: tratamento específico para potencial, arte e cards.

## Classificação
Frontend-only. Nenhum BACKEND REQUIREMENT novo.

## Limite da validação
Os testes automatizados validam estrutura, CSS e regressões. Validação visual pixel-a-pixel em navegadores/dispositivos reais continua recomendada antes do release final.
