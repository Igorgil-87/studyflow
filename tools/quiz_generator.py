"""
tools/quiz_generator.py
Gera flashcards e quiz a partir de uma transcrição usando LLM via LangChain.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field


# ── Schemas de saída ──────────────────────────────────────────────────────────

class Flashcard(BaseModel):
    frente: str = Field(description="Pergunta ou conceito")
    verso: str = Field(description="Resposta ou explicação")

class AlternativaQuestao(BaseModel):
    enunciado: str
    alternativas: list[str] = Field(description="4 alternativas (a, b, c, d)")
    resposta_correta: str = Field(description="Letra da resposta correta: a, b, c ou d")
    explicacao: str

class QuizOutput(BaseModel):
    tema: str
    flashcards: list[Flashcard]
    questoes: list[AlternativaQuestao]


# ── Tool ──────────────────────────────────────────────────────────────────────

class QuizGeneratorInput(BaseModel):
    transcript: str = Field(description="Transcrição completa do vídeo")
    topic: str = Field(description="Tema do vídeo para contextualizar o quiz")
    num_flashcards: int = Field(default=5, description="Quantidade de flashcards")
    num_questions: int = Field(default=5, description="Quantidade de questões de múltipla escolha")


class QuizGeneratorTool(BaseTool):
    name: str = "quiz_generator"
    description: str = (
        "Gera flashcards e questões de múltipla escolha a partir da transcrição de um vídeo. "
        "Retorna o caminho do arquivo JSON com o quiz gerado. "
        "Use após transcrever o áudio."
    )
    args_schema: type[BaseModel] = QuizGeneratorInput
    llm_model: str = "gpt-4o-mini"
    output_dir: str = "output/quizzes"
    # "openai" é o default de SEMPRE (preserva 100% o comportamento atual
    # de run_curso_pipeline/Opção 1). curso/lesson_agent.py (Fase 1 do
    # AI Course Generation Engine) instancia com provider="anthropic" pra
    # usar o tier de qualidade pedido, sem tocar em quem já usa esta tool.
    provider: str = "openai"

    def _run(
        self,
        transcript: str,
        topic: str,
        num_flashcards: int = 5,
        num_questions: int = 5,
    ) -> str:
        from tools.llm_fallback import build_llm_with_fallback
        # fallback precisa ser o provedor COMPLEMENTAR — se self.provider
        # já for "anthropic", o default de build_llm_with_fallback
        # (fallback_provider="anthropic") cairia no MESMO provedor, o que
        # anula a resiliência real (nenhum ganho se a Anthropic cair).
        fallback_provider = "openai" if self.provider == "anthropic" else "anthropic"
        llm = build_llm_with_fallback(
            temperature=0.3, primary_provider=self.provider, primary_model=self.llm_model,
            fallback_provider=fallback_provider,
        )
        parser = PydanticOutputParser(pydantic_object=QuizOutput)

        prompt = ChatPromptTemplate.from_messages([
            ("system", (
                "Você é um especialista em pedagogia e criação de material de estudo. "
                "Gere flashcards e questões de múltipla escolha APENAS com base no conteúdo fornecido. "
                "Seja preciso, claro e didático. Responda sempre em português brasileiro.\n\n"
                "{format_instructions}"
            )),
            ("human", (
                "Tema: {topic}\n\n"
                "Transcrição do vídeo:\n{transcript}\n\n"
                "Gere {num_flashcards} flashcards e {num_questions} questões de múltipla escolha "
                "cobrindo os conceitos mais importantes do conteúdo acima."
            )),
        ])

        chain = prompt | llm | parser

        try:
            print("[quiz_generator] Gerando quiz com LLM...")
            result: QuizOutput = chain.invoke({
                "topic": topic,
                "transcript": transcript[:6000],   # limita tokens
                "num_flashcards": num_flashcards,
                "num_questions": num_questions,
                "format_instructions": parser.get_format_instructions(),
            })
        except Exception as e:
            return f"ERRO ao gerar quiz: {e}"

        # ── Salva JSON ────────────────────────────────────────────────
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_topic = "".join(c if c.isalnum() else "_" for c in topic)[:30]
        filename = f"{self.output_dir}/quiz_{safe_topic}_{timestamp}.json"

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(result.model_dump(), f, ensure_ascii=False, indent=2)

        print(f"[quiz_generator] Quiz salvo em {filename}")
        return filename

    async def _arun(self, **kwargs) -> str:
        return self._run(**kwargs)
