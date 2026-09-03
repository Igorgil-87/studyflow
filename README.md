# YouTube Study Agent 🎓

Digite um tema → o agente busca no YouTube → baixa o áudio → transcreve → cria quiz + roteiro de treinamento.

## Stack

| Camada | Lib |
|---|---|
| Orquestração | LangChain (ReAct agent) |
| Busca YouTube | yt-dlp (extração de metadados) |
| Download + corte | yt-dlp + moviepy |
| Transcrição | OpenAI Whisper (local) |
| Geração de quiz | LangChain + GPT-4o-mini (ou Claude) |
| Roteiro de treino | LangChain + LLM (módulos progressivos) |
| Interface web | Flask + SSE + HTML/CSS/JS (dark premium) |

## Estrutura

```
youtube-study-agent/
├── app.py              # backend Flask (API + SSE)
├── main.py             # CLI (modo terminal)
├── requirements.txt
├── .env.example
├── tools/
│   ├── youtube_search.py
│   ├── audio_extractor.py
│   ├── transcriber.py
│   ├── quiz_generator.py
│   └── roadmap_generator.py
├── templates/
│   └── index.html
└── static/
    ├── css/style.css
    └── js/app.js
```

## Pré-requisitos

- Python 3.10+
- `ffmpeg` instalado no sistema:
  - Mac: `brew install ffmpeg`
  - Ubuntu: `sudo apt install ffmpeg`
  - Windows: baixe em https://ffmpeg.org/download.html e adicione ao PATH

## Setup

```bash
# 1. Clone e entre na pasta
git clone <repo> && cd youtube-study-agent

# 2. Crie o ambiente virtual
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. Instale as dependências
pip install -r requirements.txt

# 4. Configure as variáveis de ambiente
cp .env.example .env
# Edite .env e adicione sua OPENAI_API_KEY
```

## Uso

### 🌐 Interface web (recomendado)

```bash
python app.py
# abre em http://localhost:5000
```

A interface mostra o agente trabalhando ao vivo (busca → download → transcrição → quiz)
via Server-Sent Events, e renderiza os flashcards e questões de forma interativa.

### 💻 Modo terminal (CLI)

```bash
# Modo interativo (pergunta o tema)
python main.py

# Passando o tema direto
python main.py --topic "redes neurais convolucionais"

# Customizando o quiz
python main.py --topic "Docker e containers" --flashcards 8 --questions 10
```

## Saída

O quiz é salvo em `output/quizzes/quiz_<tema>_<timestamp>.json`:

```json
{
  "tema": "Docker e containers",
  "flashcards": [
    { "frente": "O que é um container?", "verso": "..." }
  ],
  "questoes": [
    {
      "enunciado": "Qual comando lista containers em execução?",
      "alternativas": ["a) docker ps", "b) docker ls", "c) docker run", "d) docker list"],
      "resposta_correta": "a",
      "explicacao": "..."
    }
  ]
}
```

## Trocar OpenAI por Claude (Anthropic)

1. No `requirements.txt`, descomente `anthropic` e comente `openai`
2. Instale: `pip install langchain-anthropic`
3. Em `tools/quiz_generator.py` e `main.py`, troque:
   ```python
   from langchain_openai import ChatOpenAI
   # por:
   from langchain_anthropic import ChatAnthropic
   ```
4. No `.env`, defina `ANTHROPIC_API_KEY` e `LLM_MODEL=claude-3-5-sonnet-20241022`

---

## GenAI Case Cockpit

Para a apresentação técnica do case de IA generativa, acesse `/case`. O cockpit consolida problema de negócio, arquitetura, matriz requisito→implementação→evidência, Quality Gates, RAG, Responsible AI, AI Gateway e Production Health sem disparar chamadas pagas de LLM ao abrir a página.

Documentação dedicada: `docs/case/README_CASE.md`.

Pré-checks antes da apresentação:

```bash
python scripts/verify_reproducibility.py
python scripts/verify_case_coverage.py
```
