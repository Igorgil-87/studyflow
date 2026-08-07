"""
main.py
Ponto de entrada do YouTube Study Agent.

Uso:
    python main.py
    python main.py --topic "LangChain agents" --flashcards 5 --questions 5
"""
import argparse
import json
import os
import sys
from pathlib import Path

from colorama import Fore, Style, init as colorama_init
from dotenv import load_dotenv
from langchain.agents import AgentExecutor, create_react_agent
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

from tools import (
    AudioExtractorTool,
    QuizGeneratorTool,
    TranscriberTool,
    YouTubeSearchTool,
)

# ── Setup ─────────────────────────────────────────────────────────────────────
load_dotenv()
colorama_init(autoreset=True)

LLM_MODEL     = os.getenv("LLM_MODEL", "gpt-4o-mini")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
OUTPUT_DIR    = os.getenv("OUTPUT_DIR", "output/quizzes")


# ── Helpers de print ──────────────────────────────────────────────────────────
def banner():
    print(Fore.CYAN + """
╔══════════════════════════════════════════╗
║        YouTube Study Agent 🎓            ║
║  LangChain + Whisper + LLM + Quiz        ║
╚══════════════════════════════════════════╝
""" + Style.RESET_ALL)

def step(msg: str):
    print(Fore.YELLOW + f"\n▶ {msg}" + Style.RESET_ALL)

def success(msg: str):
    print(Fore.GREEN + f"✔ {msg}" + Style.RESET_ALL)

def error(msg: str):
    print(Fore.RED + f"✘ {msg}" + Style.RESET_ALL)


# ── Prompt do agente ReAct ────────────────────────────────────────────────────
REACT_PROMPT = PromptTemplate.from_template("""
Você é um agente de estudo que ajuda usuários a aprender qualquer tema através de vídeos do YouTube.

Você tem acesso às seguintes ferramentas:
{tools}

Nomes das ferramentas disponíveis: {tool_names}

Siga EXATAMENTE esta ordem:
1. Use youtube_search para encontrar os melhores vídeos sobre o tema.
2. Escolha o vídeo mais relevante e educacional (prefira vídeos de 5 a 20 minutos).
3. Use audio_extractor com a URL do vídeo escolhido.
4. Use transcriber com o caminho do áudio gerado.
5. Use quiz_generator com a transcrição e o tema original.
6. Retorne o caminho do arquivo JSON do quiz gerado.

Tema para estudar: {input}
Número de flashcards: {num_flashcards}
Número de questões: {num_questions}

{agent_scratchpad}

Use o formato:
Thought: [raciocínio]
Action: [nome da ferramenta]
Action Input: [input em JSON]
Observation: [resultado]
... (repita até concluir)
Thought: Concluí todas as etapas.
Final Answer: [caminho do arquivo JSON gerado]
""")


# ── Montagem do agente ────────────────────────────────────────────────────────
def build_agent(num_flashcards: int, num_questions: int) -> AgentExecutor:
    llm = ChatOpenAI(model=LLM_MODEL, temperature=0)

    tools = [
        YouTubeSearchTool(),
        AudioExtractorTool(output_dir="output"),
        TranscriberTool(whisper_model=WHISPER_MODEL),
        QuizGeneratorTool(
            llm_model=LLM_MODEL,
            output_dir=OUTPUT_DIR,
        ),
    ]

    agent = create_react_agent(llm=llm, tools=tools, prompt=REACT_PROMPT)

    return AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        max_iterations=10,
        handle_parsing_errors=True,
    )


# ── Exibe o quiz no terminal ──────────────────────────────────────────────────
def display_quiz(json_path: str):
    if not Path(json_path).exists():
        error(f"Arquivo não encontrado: {json_path}")
        return

    with open(json_path, encoding="utf-8") as f:
        quiz = json.load(f)

    print(Fore.CYAN + f"\n{'═'*50}")
    print(f"  QUIZ: {quiz.get('tema', 'Sem tema')}")
    print(f"{'═'*50}" + Style.RESET_ALL)

    # Flashcards
    print(Fore.YELLOW + "\n📌 FLASHCARDS\n" + Style.RESET_ALL)
    for i, card in enumerate(quiz.get("flashcards", []), 1):
        print(f"  {i}. {Fore.WHITE}{card['frente']}{Style.RESET_ALL}")
        print(f"     → {card['verso']}\n")

    # Questões
    print(Fore.YELLOW + "\n❓ QUESTÕES DE MÚLTIPLA ESCOLHA\n" + Style.RESET_ALL)
    for i, q in enumerate(quiz.get("questoes", []), 1):
        print(f"  {i}. {q['enunciado']}")
        for alt in q.get("alternativas", []):
            print(f"     {alt}")
        print(Fore.GREEN + f"     ✔ Resposta: {q['resposta_correta']}" + Style.RESET_ALL)
        print(f"     💡 {q['explicacao']}\n")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    banner()

    parser = argparse.ArgumentParser(description="YouTube Study Agent")
    parser.add_argument("--topic",      type=str, default=None, help="Tema para estudar")
    parser.add_argument("--flashcards", type=int, default=5,    help="Nº de flashcards")
    parser.add_argument("--questions",  type=int, default=5,    help="Nº de questões")
    args = parser.parse_args()

    # Permite rodar sem argumento (modo interativo)
    topic = args.topic
    if not topic:
        topic = input(Fore.CYAN + "📚 O que você quer estudar hoje? " + Style.RESET_ALL).strip()
        if not topic:
            error("Nenhum tema informado. Encerrando.")
            sys.exit(1)

    step(f"Iniciando agente para o tema: '{topic}'")
    step(f"Modelo LLM: {LLM_MODEL} | Whisper: {WHISPER_MODEL}")

    agent_executor = build_agent(
        num_flashcards=args.flashcards,
        num_questions=args.questions,
    )

    try:
        result = agent_executor.invoke({
            "input": topic,
            "num_flashcards": args.flashcards,
            "num_questions": args.questions,
        })
        quiz_path = result.get("output", "").strip()
        success(f"Quiz gerado em: {quiz_path}")
        display_quiz(quiz_path)

    except KeyboardInterrupt:
        print("\n\nInterrompido pelo usuário.")
        sys.exit(0)
    except Exception as e:
        error(f"Erro inesperado: {e}")
        raise


if __name__ == "__main__":
    main()