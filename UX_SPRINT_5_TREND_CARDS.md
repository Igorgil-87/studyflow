# UX Sprint 5 — Sistema único de cards de tendência

## Auditoria
A camada de resultados misturava hero editorial, cards Trend Insights, badges, múltiplos scores, fontes e CTA, criando padrões concorrentes para a mesma entidade.

## Solução
Um único componente `ux-trend-card` passa a representar toda tendência. O primeiro item usa apenas uma variação `is-featured`, preservando o mesmo modelo mental e ações.

Cada card prioriza: categoria/contexto, o que aconteceu (título + insight), potencial já fornecido pelo backend (`oportunidade_score`), ação secundária `Ver análise` e ação primária `Criar conteúdo`.

Detalhes existentes (ângulo e fontes) ficam em progressive disclosure. Nenhum dado, score ou fonte é criado no frontend.

## Escopo
Frontend only. Nenhuma API/rota foi alterada. A Sprint 6 continua responsável por revisar metodologia, significado e apresentação definitiva do score/potencial.
