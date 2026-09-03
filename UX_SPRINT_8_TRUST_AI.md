# UX Sprint 8 — Confiança, IA e conteúdos sensíveis

## Auditoria
O detalhe já separava síntese da IA, interpretação, fontes e sugestão criativa, mas essa distinção dependia de badges locais e não havia orientação adicional para temas com maior custo de erro. As fontes existentes trazem URL/título/origem de forma irregular; não há classificação confiável entre fonte primária/secundária nem trechos de evidência consistentes.

## Implementação
- Adicionada legenda de proveniência no topo do detalhe: evidência verificável, síntese/interpretação da IA e sugestão criativa.
- Temas de política, economia/finanças, ciência, saúde/bem-estar e segurança recebem aviso contextual de verificação, sem bloquear a tarefa.
- O aviso informa apenas a quantidade real de links verificáveis presentes no objeto da tendência; não inventa fontes primárias/secundárias.
- Quando existem fontes, o aviso oferece `Revisar evidências`, levando à seção correspondente.
- A classificação sensível é uma regra UX conservadora por categoria/palavras-chave, não um classificador de verdade, risco ou conteúdo.

## Backend requirement
Para proveniência mais forte, cada evidência deveria expor de forma estruturada: `source`, `title`, `url`, `published_at`, `collected_at`, `source_type`, `evidence_excerpt` e, somente se houver metodologia, `primary/secondary`.

## Riscos / limites
O aviso contextual pode produzir falsos positivos/negativos porque não é um classificador semântico. Ele existe para aumentar cautela e transparência, não para certificar segurança ou factualidade.
