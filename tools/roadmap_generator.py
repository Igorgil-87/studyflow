"""
tools/roadmap_generator.py
Gera um roteiro de treinamento estruturado a partir de uma transcrição,
usando LLM via LangChain.
"""

import json
from datetime import datetime
from pathlib import Path
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field


# ── Schemas de saída ──────────────────────────────────────────────────────────

class Modulo(BaseModel):
    titulo: str = Field(description="Título do módulo")
    objetivo: str = Field(description="O que o aluno aprende neste módulo")
    topicos: list[str] = Field(description="Tópicos abordados no módulo")
    duracao_estimada: str = Field(description="Tempo estimado, ex: '30 min'")
    pratica: str = Field(description="Exercício ou atividade prática sugerida")

class RoadmapOutput(BaseModel):
    tema: str
    nivel: str = Field(description="iniciante, intermediário ou avançado")
    resumo: str = Field(description="Resumo do que o treinamento cobre")
    pre_requisitos: list[str] = Field(description="Conhecimentos prévios necessários")
    modulos: list[Modulo]
    proximos_passos: list[str] = Field(description="O que estudar depois")


# ── Tool ──────────────────────────────────────────────────────────────────────

class RoadmapGeneratorInput(BaseModel):
    transcript: str = Field(description="Transcrição completa do vídeo")
    topic: str = Field(description="Tema do treinamento")
    num_modules: int = Field(default=4, description="Quantidade de módulos do roteiro")


class RoadmapGeneratorTool(BaseTool):
    name: str = "roadmap_generator"
    description: str = (
        "Gera um roteiro de treinamento estruturado em módulos a partir da "
        "transcrição de um vídeo. Inclui objetivos, tópicos, práticas e próximos passos. "
        "Retorna o caminho do arquivo JSON gerado. Use após transcrever o áudio."
    )
    args_schema: type[BaseModel] = RoadmapGeneratorInput
    llm_model: str = "gpt-4o-mini"
    output_dir: str = "output/roadmaps"

    def _run(self, transcript: str, topic: str, num_modules: int = 4) -> str:
        from tools.llm_fallback import build_llm_with_fallback
        llm = build_llm_with_fallback(
            temperature=0.4, primary_provider="openai", primary_model=self.llm_model,
        )
        parser = PydanticOutputParser(pydantic_object=RoadmapOutput)

        prompt = ChatPromptTemplate.from_messages([
            ("system", (
                "Você é um designer instrucional especialista em criar trilhas de "
                "aprendizado. Com base APENAS no conteúdo fornecido, monte um roteiro "
                "de treinamento prático, progressivo e didático. "
                "Responda sempre em português brasileiro.\n\n{format_instructions}"
            )),
            ("human", (
                "Tema: {topic}\n\n"
                "Transcrição do vídeo:\n{transcript}\n\n"
                "Crie um roteiro de treinamento com {num_modules} módulos, organizados "
                "do básico ao avançado, cobrindo os conceitos do conteúdo acima. "
                "Cada módulo deve ter objetivo claro, tópicos e uma atividade prática."
            )),
        ])

        chain = prompt | llm | parser

        try:
            print("[roadmap_generator] Gerando roteiro de treinamento...")
            result: RoadmapOutput = chain.invoke({
                "topic": topic,
                "transcript": transcript[:6000],
                "num_modules": num_modules,
                "format_instructions": parser.get_format_instructions(),
            })
        except Exception as e:
            return f"ERRO ao gerar roteiro: {e}"

        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_topic = "".join(c if c.isalnum() else "_" for c in topic)[:30]
        filename = f"{self.output_dir}/roadmap_{safe_topic}_{timestamp}.json"

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(result.model_dump(), f, ensure_ascii=False, indent=2)

        print(f"[roadmap_generator] Roteiro salvo em {filename}")
        return filename

    async def _arun(self, **kwargs) -> str:
        return self._run(**kwargs)
