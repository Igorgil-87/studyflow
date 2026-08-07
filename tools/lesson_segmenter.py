"""
tools/lesson_segmenter.py
Analisa a transcrição com timestamps e identifica blocos temáticos (aulas)
usando LLM via LangChain.
"""

import json
from pathlib import Path
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field


class Aula(BaseModel):
    titulo: str = Field(
        description="Título curto da aula (máx 50 caracteres)"
    )
    inicio: float = Field(description="Tempo de início em segundos")
    fim: float = Field(description="Tempo de fim em segundos")
    resumo: str = Field(
        description="Resumo de 1-2 frases do conteúdo da aula"
    )


class AulasOutput(BaseModel):
    aulas: list[Aula]


class LessonSegmenterInput(BaseModel):
    segments_path: str = Field(
        description="Caminho para o JSON de segmentos com timestamps"
    )
    topic: str = Field(description="Tema do vídeo")


class LessonSegmenterTool(BaseTool):
    name: str = "lesson_segmenter"
    description: str = (
        "Analisa a transcrição com timestamps e identifica blocos "
        "temáticos (aulas). Retorna JSON com titulo, inicio, fim e "
        "resumo de cada aula. Use após a transcrição."
    )
    args_schema: type[BaseModel] = LessonSegmenterInput
    llm_model: str = "gpt-4o-mini"

    def _run(self, segments_path: str, topic: str) -> str:
        if not Path(segments_path).exists():
            return (
                f"ERRO: arquivo de segmentos não encontrado: "
                f"{segments_path}"
            )

        with open(segments_path, encoding="utf-8") as f:
            segments = json.load(f)

        if not segments:
            return "ERRO: arquivo de segmentos vazio."

        total_duration = segments[-1]["end"]

        # Formata transcrição compacta com timestamps para o LLM
        transcript_with_times = "\n".join(
            f"[{s['start']:.0f}s] {s['text']}"
            for s in segments
        )

        from tools.llm_fallback import build_llm_with_fallback
        llm = build_llm_with_fallback(
            temperature=0, primary_provider="openai", primary_model=self.llm_model,
        )
        parser = PydanticOutputParser(pydantic_object=AulasOutput)

        prompt = ChatPromptTemplate.from_messages([
            ("system", (
                "Você é um especialista em pedagogia e design "
                "instrucional. Analise a transcrição abaixo e "
                "identifique entre 3 e 6 blocos temáticos distintos "
                "(aulas). Cada bloco deve ter início e fim baseados "
                "nos timestamps. O primeiro bloco começa em 0. O "
                "último bloco termina em {total_duration:.0f}s. Os "
                "blocos devem cobrir toda a duração sem gaps. "
                "Responda em português brasileiro.\n\n"
                "{format_instructions}"
            )),
            ("human", (
                "Tema geral: {topic}\n\n"
                "Transcrição com timestamps ([segundos] texto):\n"
                "{transcript}\n\n"
                "Identifique os blocos temáticos naturais do conteúdo."
            )),
        ])

        chain = prompt | llm | parser

        try:
            print("[lesson_segmenter] Identificando blocos de aulas...")
            result: AulasOutput = chain.invoke({
                "topic": topic,
                "transcript": transcript_with_times[:8000],
                "total_duration": total_duration,
                "format_instructions": parser.get_format_instructions(),
            })
            n = len(result.aulas)
            print(f"[lesson_segmenter] {n} aulas identificadas.")
        except Exception as e:
            return f"ERRO ao segmentar aulas: {e}"

        return json.dumps(result.model_dump(), ensure_ascii=False)

    async def _arun(self, **kwargs) -> str:
        return self._run(**kwargs)
