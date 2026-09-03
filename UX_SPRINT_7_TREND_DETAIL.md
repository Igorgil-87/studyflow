# UX Sprint 7 — Detalhe da Tendência

## Auditoria
A Sprint 6 ainda abria `Ver análise` dentro do próprio card. Isso misturava descoberta rápida e investigação, e não distinguia visualmente conteúdo de fonte, síntese da IA e sugestão criativa.

## Implementação
- `Ver análise` abre drawer/modal dedicado, sem criar rota ou API nova.
- Hierarquia: Resumo → Por que merece atenção → Evidências e fontes → Ângulo possível → Criar conteúdo.
- `insight` é explicitamente rotulado como síntese/interpretação da IA.
- Links existentes são apresentados como evidências verificáveis com tipo de fonte/título/domínio quando disponíveis.
- `angulo` é rotulado como sugestão criativa da IA.
- Não inventamos datas, recência, trechos de evidência, número de fontes primárias/secundárias ou múltiplos ângulos.
- Modal tem Escape, focus trap básico, retorno de foco, clique no backdrop e layout mobile bottom-sheet.
- Analytics: `trend_opened`, `trend_sources_opened`, `trend_create_content_clicked`.

## Backend requirement
Para exibir data/recência confiável por evidência, classificação primária/secundária e fatos/trechos extraídos, o backend precisa persistir esses metadados por fonte. Hoje `links` fornece principalmente URL, título, source e eventualmente score.
