# StudyFlow — Generative AI Engineering Case

## Problema de negócio
Empresas acumulam conhecimento em PDFs, apresentações, vídeos, políticas e materiais técnicos, mas transformar esse conteúdo em aprendizagem estruturada, personalizada e mensurável exige esforço manual especializado.

## Solução
O StudyFlow é uma plataforma **Knowledge-to-Learning multimodal**. O usuário fornece uma fonte de conhecimento; a plataforma extrai e estrutura o conteúdo, indexa evidências em RAG, gera uma jornada de aprendizagem com aulas, mídia, flashcards, quiz e exercícios, e oferece uma tutora (Georgina) capaz de responder ancorada nas fontes.

## Diferenciais de engenharia
A solução separa experiência, orquestração, conhecimento, modelos e controles operacionais. O AI Gateway permite Gemini/OpenAI/Anthropic; o RAG usa pgvector e citações; respostas podem ser avaliadas por LLM-as-Judge com Quality Gates; Responsible AI inclui prompt-injection guard, redaction e audit trail; e Production Health expõe liveness/readiness, fila e dependências.

## Evidência para avaliação
A rota `/case` é o cockpit da apresentação. Ela consolida cobertura dos requisitos, arquitetura, qualidade observada, RAG, segurança, providers e readiness, sem inventar métricas ausentes: estados sem amostra aparecem como dados insuficientes.

## Execução rápida
1. Copie `.env.example` para `.env` e configure somente os providers necessários.
2. Execute `docker compose -f docker-compose.full.yml up -d --build`.
3. Abra a porta definida por `APP_PORT` (padrão local: 5001).
4. Valide `/healthz`, `/readyz`, `/case`, `/rag`, `/obs`, `/security`, `/models` e `/system`.
5. Rode `python scripts/verify_reproducibility.py` e `python scripts/verify_case_coverage.py`.

Veja também `ARCHITECTURE.md`, `TRADEOFFS.md`, `REQUIREMENTS_MATRIX.md`, `REPRODUCIBILITY.md`, `DEMO_SCRIPT.md` e `NEXT_STEPS.md` nesta pasta.
