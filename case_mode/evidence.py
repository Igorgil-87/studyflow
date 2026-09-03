"""Evidence matrix for the StudyFlow Generative AI case.

The matrix intentionally distinguishes implemented evidence from presentation
claims.  A requirement only counts as covered when there is a concrete route,
component, document or reproducibility artifact that can be shown to an
evaluator.
"""
from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _exists(path: str) -> bool:
    return (PROJECT_ROOT / path).exists()


def requirement_matrix() -> list[dict]:
    rows = [
        {
            "id": "business_case", "requirement": "Caso real de negócio",
            "implementation": "Knowledge-to-Learning multimodal para transformar conhecimento não estruturado em aprendizagem mensurável.",
            "evidence": ["/curso", "/rag", "docs/case/README_CASE.md"],
            "checks": [_exists("templates/curso.html"), _exists("templates/rag.html"), _exists("docs/case/README_CASE.md")],
        },
        {
            "id": "genai_models", "requirement": "Um ou mais modelos de IA generativa",
            "implementation": "AI Gateway com Gemini, OpenAI e Anthropic, roteamento e fallback.",
            "evidence": ["/models", "ai_gateway/gateway.py", "SPRINT_4_AI_GATEWAY.md"],
            "checks": [_exists("ai_gateway/gateway.py"), _exists("templates/models.html")],
        },
        {
            "id": "prompting", "requirement": "Prompts e controle de respostas",
            "implementation": "Prompts estruturados por fluxo, versionamento do prompt de avaliação e guardrails de entrada/saída.",
            "evidence": ["obs/judge.py", "security/guards.py", "/security"],
            "checks": [_exists("obs/judge.py"), _exists("security/guards.py")],
        },
        {
            "id": "company_data", "requirement": "Uso e preparação de dados da empresa",
            "implementation": "Upload/extração de documentos, vídeos e materiais; chunking, metadados e armazenamento vetorial.",
            "evidence": ["rag/document_extractor.py", "rag/index.py", "rag/store.py", "/rag"],
            "checks": [_exists("rag/document_extractor.py"), _exists("rag/index.py"), _exists("rag/store.py")],
        },
        {
            "id": "rag", "requirement": "Estratégia de ajuste/uso do LLM",
            "implementation": "RAG com pgvector, Top-K, metadados de origem, citações e Retrieval Debug.",
            "evidence": ["/rag", "/api/rag/retrieve", "SPRINT_2_RAG_CITATIONS.md"],
            "checks": [_exists("rag/query.py"), _exists("db/init_pgvector.sql"), _exists("SPRINT_2_RAG_CITATIONS.md")],
        },
        {
            "id": "orchestration", "requirement": "Arquitetura de modelos/agentes e orquestração",
            "implementation": "Pipelines de curso, tutor, RAG, filas/workers e AI Gateway com responsabilidades separadas.",
            "evidence": ["pipelines.py", "curso/tutor_agent.py", "infra/dispatch.py", "docs/case/ARCHITECTURE.md"],
            "checks": [_exists("pipelines.py"), _exists("curso/tutor_agent.py"), _exists("infra/dispatch.py")],
        },
        {
            "id": "evaluation", "requirement": "Avaliação de performance da solução",
            "implementation": "LLM-as-Judge, groundedness, relevância, fidelidade, completude, hallucination rate e Quality Gates.",
            "evidence": ["/obs", "/api/observability/quality-gate", "SPRINT_1_AI_EVALUATION.md", "SPRINT_1B_QUALITY_GATES.md"],
            "checks": [_exists("obs/judge.py"), _exists("obs/quality.py"), _exists("SPRINT_1B_QUALITY_GATES.md")],
        },
        {
            "id": "responsible_ai", "requirement": "Ética, privacidade e IA responsável",
            "implementation": "Prompt-injection guard, output redaction, audit trail, ownership, sessão segura e evidências de gaps de secrets.",
            "evidence": ["/security", "security/guards.py", "security/audit.py", "SPRINT_3_RESPONSIBLE_AI_SECURITY.md"],
            "checks": [_exists("security/guards.py"), _exists("security/audit.py"), _exists("templates/security.html")],
        },
        {
            "id": "architecture_tradeoffs", "requirement": "Arquitetura, decisões e trade-offs",
            "implementation": "Arquitetura documentada e ADR narrativo para RAG vs fine-tuning, multi-provider, filas e controles.",
            "evidence": ["docs/case/ARCHITECTURE.md", "docs/case/TRADEOFFS.md", "/case"],
            "checks": [_exists("docs/case/ARCHITECTURE.md"), _exists("docs/case/TRADEOFFS.md")],
        },
        {
            "id": "reproducibility", "requirement": "Projeto empacotado e reproduzível",
            "implementation": "Docker Compose, .env.example, scripts de verificação e instruções de execução em outra máquina.",
            "evidence": ["docker-compose.full.yml", ".env.example", "scripts/verify_reproducibility.py", "docs/case/REPRODUCIBILITY.md"],
            "checks": [_exists("Dockerfile"), _exists("docker-compose.full.yml"), _exists(".env.example"), _exists("scripts/verify_reproducibility.py")],
        },
        {
            "id": "production", "requirement": "Escalabilidade, segurança e eficiência",
            "implementation": "Workers/fila, readiness/liveness, observabilidade, cache, FinOps, health de dependências e providers.",
            "evidence": ["/system", "/healthz", "/readyz", "production/health.py"],
            "checks": [_exists("production/health.py"), _exists("worker.py"), _exists("cache/llm_cache.py")],
        },
        {
            "id": "documentation", "requirement": "Documentação detalhada e próximos passos",
            "implementation": "Pacote de case com problema, arquitetura, matriz de evidências, execução, trade-offs, demo e roadmap.",
            "evidence": ["docs/case/README_CASE.md", "docs/case/REQUIREMENTS_MATRIX.md", "docs/case/DEMO_SCRIPT.md", "docs/case/NEXT_STEPS.md"],
            "checks": [_exists("docs/case/README_CASE.md"), _exists("docs/case/REQUIREMENTS_MATRIX.md"), _exists("docs/case/DEMO_SCRIPT.md"), _exists("docs/case/NEXT_STEPS.md")],
        },
    ]
    for row in rows:
        row["covered"] = all(row.pop("checks"))
    return rows


def coverage_summary() -> dict:
    rows = requirement_matrix()
    covered = sum(1 for row in rows if row["covered"])
    total = len(rows)
    return {
        "covered": covered,
        "total": total,
        "coverage_pct": round((covered / total) * 100, 1) if total else 0.0,
        "all_covered": covered == total,
    }


def architecture_layers() -> list[dict]:
    return [
        {"name": "Experience", "items": ["Georgina · Study", "Marcos Cezar · Creator", "Youtuber", "Case Cockpit"]},
        {"name": "AI Orchestration", "items": ["Course Pipeline", "Tutor Agent", "AI Gateway", "Quality Gates"]},
        {"name": "Knowledge", "items": ["Document Extraction", "Chunking", "Embeddings", "pgvector", "Citations"]},
        {"name": "Responsible AI", "items": ["Input Guard", "Output Guard", "Ownership", "Audit Trail"]},
        {"name": "Platform", "items": ["Flask", "Redis/RQ", "PostgreSQL", "Docker", "Observability"]},
        {"name": "Models", "items": ["Gemini", "OpenAI", "Anthropic"]},
    ]
