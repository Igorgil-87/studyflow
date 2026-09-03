# UX Sprint 6 — Score / Potencial

## Auditoria
`oportunidade_score`, `viral_score` e `polemica_score` de Tendências são definidos no schema como notas 1–10 e preenchidos pelo LLM da Chain 2. O prompt atual pede “scores”, mas não implementa fórmula calibrada, pesos observáveis, validação histórica ou intervalo de confiança. Portanto, exibir `8/10` como medida objetiva cria falsa precisão.

## Decisão UX
Na camada principal, `oportunidade_score` passa a ser apresentado qualitativamente: **Alto**, **Médio** ou **Baixo**, sempre identificado como **Estimativa da IA**. O valor numérico bruto continua no payload/backend para compatibilidade, mas não é exibido como ciência na descoberta.

Faixas de apresentação: 8–10 Alto; 5–7 Médio; 1–4 Baixo. Elas são apenas uma tradução visual da escala legada, não uma nova metodologia preditiva.

A ajuda informa: “Estimativa qualitativa da IA a partir dos sinais disponíveis. Não é previsão de desempenho.” Não listamos crescimento, concorrência, recência ou outros fatores porque o backend não calcula esses componentes de forma explícita.

## Backend requirement
Para voltar a mostrar um score numérico defensável (por exemplo 82/100), criar metodologia versionada com sinais observáveis, pesos documentados, normalização, provenance dos inputs e validação retrospectiva contra desempenho real. Até isso existir, manter classificação qualitativa.
