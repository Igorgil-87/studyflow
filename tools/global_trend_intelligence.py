"""
tools/global_trend_intelligence.py

Orquestrador multi-IA para análise de tendências globais por categoria.

Pipeline de 3 chains com modelos distintos:
  Chain 1 — GPT-4o-mini  (temp 0.1): Ranker      — classifica dados brutos das 4 fontes
  Chain 2 — Claude Haiku (temp 0.7): Insights     — análise criativa e nuançada por tema
  Chain 3 — Claude Sonnet(temp 0.4): Synthesizer  — padrões globais + resumo editorial

Fontes de dados (sem chave adicional):
  • Reddit   — JSON público por subreddit (hot posts)
  • HackerNews — Firebase REST API (top stories filtradas por keyword)
  • Wikipedia  — Wikimedia REST API (páginas mais visitadas)
  • YouTube   — yt_dlp search por categoria
"""

import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

import requests
import yt_dlp
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

try:
    from langchain_anthropic import ChatAnthropic
    _ANTHROPIC_OK = True
except ImportError:
    _ANTHROPIC_OK = False

# ── Category config ────────────────────────────────────────────────────────
CATEGORIES: dict[str, dict] = {
    "esportes": {
        "label": "Esportes",
        "icon": "⚽",
        "subreddits": ["soccer", "formula1", "nba", "mma", "sports"],
        "hn_keywords": ["sports", "football", "championship", "olympic", "league"],
        "yt_query": "esportes viral trending 2025",
    },
    "games": {
        "label": "Games",
        "icon": "🎮",
        "subreddits": ["gaming", "pcgaming", "PS5", "gamedev", "nintendo"],
        "hn_keywords": ["game", "gaming", "playstation", "xbox", "nintendo", "steam"],
        "yt_query": "games viral trending 2025",
    },
    "politica": {
        "label": "Política",
        "icon": "🏛",
        "subreddits": ["worldnews", "geopolitics", "europe", "brasil", "politics"],
        "hn_keywords": ["politics", "government", "election", "policy", "president"],
        "yt_query": "política mundial tendência 2025",
    },
    "ciencia": {
        "label": "Ciência",
        "icon": "🔬",
        "subreddits": ["science", "technology", "space", "MachineLearning", "futurology"],
        "hn_keywords": ["AI", "research", "science", "study", "discovery", "model"],
        "yt_query": "ciência tecnologia viral 2025",
    },
    "cultura": {
        "label": "Cultura",
        "icon": "🎭",
        "subreddits": ["movies", "Music", "television", "books", "Art"],
        "hn_keywords": ["music", "film", "art", "culture", "entertainment", "show"],
        "yt_query": "cultura entretenimento viral 2025",
    },
    "historia": {
        "label": "História",
        "icon": "📜",
        "subreddits": ["history", "AskHistorians", "todayilearned", "worldhistory"],
        "hn_keywords": ["history", "historical", "anniversary", "ancient", "discovery"],
        "yt_query": "história fatos virais curiosidades 2025",
    },
    "beleza": {
        "label": "Beleza",
        "icon": "💄",
        "subreddits": ["beauty", "SkincareAddiction", "MakeupAddiction", "Hair", "fragrance"],
        "hn_keywords": ["beauty", "skincare", "cosmetics", "makeup", "fragrance"],
        "yt_query": "beleza skincare maquiagem viral 2026",
    },
    "fitness": {
        "label": "Mundo Fitness",
        "icon": "💪",
        "subreddits": ["Fitness", "bodyweightfitness", "gym", "nutrition", "running"],
        "hn_keywords": ["fitness", "workout", "nutrition", "health", "exercise", "gym"],
        "yt_query": "fitness treino nutrição viral 2026",
    },
    "economia": {
        "label": "Economia",
        "icon": "📈",
        "subreddits": ["economics", "investing", "finance", "wallstreetbets", "CryptoCurrency"],
        "hn_keywords": ["economy", "market", "inflation", "stocks", "crypto", "interest"],
        "yt_query": "economia mercado bolsa dólar análise 2026",
    },
}


# ── Pydantic models ────────────────────────────────────────────────────────

class RankedTopics(BaseModel):
    topics: list[str] = Field(
        description=(
            "Top 10 tópicos mais relevantes e em alta para a categoria, "
            "ordenados do mais para o menos relevante. "
            "Use apenas o que está nos dados brutos fornecidos."
        )
    )


class TrendInsightItem(BaseModel):
    titulo: str = Field(description="Nome limpo e direto do tópico (máx 60 chars)")
    insight: str = Field(
        description=(
            "Análise em 2-3 frases: por que está em alta agora, "
            "o que isso revela sobre o momento cultural/social, "
            "e qual a tendência de curto prazo."
        )
    )
    angulo: str = Field(
        description=(
            "Ângulo único e específico para um criador de conteúdo explorar "
            "este tema de forma diferenciada (1-2 frases concretas)."
        )
    )
    viral_score: int = Field(description="Potencial viral 1-10")
    oportunidade_score: int = Field(description="Oportunidade para criadores 1-10")
    polemica_score: int = Field(description="Nível de controvérsia/polêmica 1-10")
    hashtags: list[str] = Field(description="5 hashtags sem # otimizadas para alcance")
    podcasts: list[str] = Field(
        description=(
            "2-3 nomes de podcasts reais e conhecidos (brasileiros ou internacionais) "
            "que provavelmente já discutiram ou discutiriam esse tema."
        )
    )


class CategoryInsightsOutput(BaseModel):
    items: list[TrendInsightItem]


class CrossTheme(BaseModel):
    tema: str = Field(description="Nome do padrão transversal detectado")
    categorias: list[str] = Field(
        description="Lista de categorias onde esse tema aparece (use os nomes em português)"
    )
    explicacao: str = Field(
        description="Por que esse tema está dominando múltiplas categorias (2 frases analíticas)"
    )


class SynthesisOutput(BaseModel):
    temas_cruzados: list[CrossTheme] = Field(
        description="3-5 padrões que transcendem categorias"
    )
    resumo_editorial: str = Field(
        description=(
            "Resumo editorial de 4-5 frases sobre o cenário global de tendências "
            "desta semana — com tom analítico e perspicaz, como um editor de mídia."
        )
    )


# ── Main class ─────────────────────────────────────────────────────────────

class GlobalTrendIntelligence:
    """
    Orquestrador multi-IA.

    Uso:
        intel = GlobalTrendIntelligence()
        raw   = intel.collect_all_data(["esportes", "games", "ciencia"])
        # Em paralelo, por categoria:
        result = intel.analyze_category("esportes", raw["esportes"])
        # Depois de todas as categorias:
        synthesis = intel.synthesize_global(all_results)
    """

    def __init__(
        self,
        openai_model: str = "gpt-4o-mini",
        claude_model: str = "claude-sonnet-4-6",
        claude_fast_model: str = "claude-haiku-4-5-20251001",
        cookies_browser: str = "",
    ):
        self.cookies_browser = cookies_browser

        from tools.llm_fallback import build_llm_with_fallback

        # Chain 1 — GPT-4o-mini principal (rápido, estruturado, barato),
        # cai pro Claude se o OpenAI falhar em tempo de execução.
        self.llm_ranker = build_llm_with_fallback(
            temperature=0.1, primary_provider="openai", primary_model=openai_model,
            fallback_provider="anthropic", fallback_model=claude_fast_model,
        )

        # Chain 2/3 — Claude principal (criativo/síntese), cai pro GPT se
        # a Anthropic falhar OU não estiver configurada. Antes disso era
        # uma checagem só na inicialização (se a chave não existisse,
        # usava GPT pra sessão INTEIRA) — agora reage a falha de verdade
        # em tempo de execução também, não só ausência de configuração.
        self.claude_available = _ANTHROPIC_OK and os.getenv("ANTHROPIC_API_KEY", "").startswith("sk-ant")
        if self.claude_available:
            self.llm_insights = build_llm_with_fallback(
                temperature=0.7, primary_provider="anthropic", primary_model=claude_fast_model,
                fallback_provider="openai", fallback_model=openai_model,
            )
            self.llm_synth = build_llm_with_fallback(
                temperature=0.4, primary_provider="anthropic", primary_model=claude_model,
                fallback_provider="openai", fallback_model=openai_model,
            )
        else:
            self.llm_insights = ChatOpenAI(model=openai_model, temperature=0.6)
            self.llm_synth = ChatOpenAI(model=openai_model, temperature=0.4)

        self._build_prompts()

    # ── Prompt builders ────────────────────────────────────────────────────

    def _build_prompts(self) -> None:
        # Chain 1 prompt (GPT-4o-mini)
        self.ranker_prompt = ChatPromptTemplate.from_messages([
            ("system", (
                "Você é um analista de tendências digitais com faro para o que VIRALIZA. "
                "Analise os dados brutos e extraia os 10 tópicos mais quentes e específicos "
                "para a categoria {category_label}. "
                "Priorize tópicos com alto engajamento ou que aparecem em múltiplas fontes — "
                "em especial os que vêm de notícias recentes e da Perplexity (mais atuais), "
                "e DÊ PESO EXTRA a POLÊMICAS, debates, opiniões divididas e fatos que "
                "contrariam o senso comum ('estouram bolha'). "
                "PREFIRA assuntos ESPECÍFICOS e concretos (nomes, eventos, fatos datados) "
                "em vez de temas genéricos ou perenes. Evite chavões. "
                "Use apenas o que está nos dados.\n\n"
                "{format_instructions}"
            )),
            ("human", (
                "Categoria: {category_label}\n\n"
                "Dados brutos de múltiplas fontes:\n{raw_text}\n\n"
                "Extraia os 10 tópicos mais quentes, específicos e polêmicos."
            )),
        ])

        # Chain 2 prompt (Claude Haiku)
        self.insights_prompt = ChatPromptTemplate.from_messages([
            ("system", (
                "Você é um estrategista de conteúdo sênior especializado em {category_label}, "
                "com profundo conhecimento de cultura digital, redes sociais e comportamento de audiência. "
                "Gere análises ricas, específicas e acionáveis para criadores de conteúdo. "
                "Seja perspicaz, criativo e concreto — evite generalidades. "
                "Responda sempre em português brasileiro.\n\n"
                "{format_instructions}"
            )),
            ("human", (
                "Categoria: {category_label}\n"
                "Tópicos em alta detectados:\n{topics_text}\n\n"
                "Contexto adicional das fontes:\n{context}\n\n"
                "Para cada tópico, gere um insight completo com análise, um ÂNGULO "
                "DE CONTEÚDO ousado (de preferência um lado polêmico ou contraintuitivo "
                "que gere debate), scores e recomendações reais. Mire o que faz a pessoa "
                "PARAR e comentar."
            )),
        ])

        # Chain 3 prompt (Claude Sonnet)
        self.synthesis_prompt = ChatPromptTemplate.from_messages([
            ("system", (
                "Você é o editor-chefe de uma publicação de inteligência cultural e tendências globais. "
                "Sua tarefa é identificar padrões que transcendem categorias temáticas e "
                "escrever um resumo editorial perspicaz do momento atual. "
                "Seja analítico, cultural e com voz editorial forte. "
                "Responda em português brasileiro.\n\n"
                "{format_instructions}"
            )),
            ("human", (
                "Tendências globais detectadas esta semana por categoria:\n\n"
                "{categories_summary}\n\n"
                "1. Identifique 3-5 temas transversais que aparecem em múltiplas categorias.\n"
                "2. Escreva um resumo editorial analítico do cenário de tendências desta semana."
            )),
        ])

    # ── Data collection ────────────────────────────────────────────────────

    def collect_all_data(self, categories: list[str]) -> dict:
        """Coleta dados de todas as categorias em paralelo."""
        results = {}
        # paralelismo moderado: 3 categorias por vez evita estourar o rate limit
        # do X e do GNews (que falhavam com 429 quando 6+ disparavam juntas)
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(self._collect_category, cat): cat
                for cat in categories
                if cat in CATEGORIES
            }
            for future in as_completed(futures):
                cat = futures[future]
                try:
                    results[cat] = future.result()
                except Exception as e:
                    print(f"[trends] collect_all {cat}: {e}")
                    results[cat] = {"topics": [], "context": "", "sources": []}
        return results

    def _collect_category(self, category: str) -> dict:
        """Coleta dados de várias fontes em paralelo para uma categoria."""
        cfg = CATEGORIES[category]
        label = cfg.get("label", category)
        with ThreadPoolExecutor(max_workers=7) as ex:
            f_reddit = ex.submit(self._fetch_reddit, cfg["subreddits"])
            f_hn     = ex.submit(self._fetch_hackernews, cfg["hn_keywords"])
            f_wiki   = ex.submit(self._fetch_wikipedia)
            f_yt     = ex.submit(self._fetch_youtube, cfg["yt_query"])
            f_px     = ex.submit(self._fetch_perplexity, label)
            f_news   = ex.submit(self._fetch_news, label)
            f_x      = ex.submit(self._fetch_x, label)

            reddit_data = f_reddit.result()
            hn_data     = f_hn.result()
            wiki_data   = f_wiki.result()
            yt_data     = f_yt.result()
            px_data     = f_px.result()
            news_data   = f_news.result()
            x_data      = f_x.result()

        topics: list[str] = []
        context_parts: list[str] = []
        sources: list[str] = []
        links: list[dict] = []

        if reddit_data:
            sources.append("reddit")
            topics += [p["title"] for p in reddit_data]
            context_parts.append(
                "Reddit (posts quentes):\n"
                + "\n".join(
                    f"  • {p['title']} [↑{p['score']} | r/{p['subreddit']}]"
                    for p in reddit_data[:6]
                )
            )
            links += [
                {"url": p["url"], "title": p["title"], "score": p["score"], "source": "reddit"}
                for p in reddit_data
                if p.get("url", "").startswith("http")
            ]

        if hn_data:
            sources.append("hackernews")
            topics += [s["title"] for s in hn_data]
            context_parts.append(
                "HackerNews (top stories):\n"
                + "\n".join(f"  • {s['title']} [{s.get('score', 0)} pts]" for s in hn_data[:5])
            )
            links += [
                {"url": s["url"], "title": s["title"], "score": s.get("score", 0), "source": "hackernews"}
                for s in hn_data
                if s.get("url", "").startswith("http")
            ]

        if wiki_data:
            sources.append("wikipedia")
            topics += wiki_data[:6]
            context_parts.append(
                "Wikipedia (mais acessadas):\n"
                + "\n".join(f"  • {t}" for t in wiki_data[:5])
            )

        if yt_data:
            sources.append("youtube")
            topics += [v["title"] for v in yt_data]
            context_parts.append(
                "YouTube (busca tendências):\n"
                + "\n".join(f"  • {v['title']}" for v in yt_data[:5])
            )

        if px_data and px_data.get("topics"):
            sources.append("perplexity")
            topics += px_data["topics"]
            if px_data.get("context"):
                context_parts.append(px_data["context"])
            links += px_data.get("links", [])

        if news_data and news_data.get("topics"):
            sources.append("news")
            topics += news_data["topics"]
            context_parts.append(
                "Notícias (manchetes recentes):\n"
                + "\n".join(f"  • {h['title']}" for h in news_data["headlines"][:6])
            )
            links += news_data.get("links", [])

        if x_data and x_data.get("topics"):
            sources.append("x")
            topics += x_data["topics"]
            if x_data.get("context"):
                context_parts.append(x_data["context"])
            links += x_data.get("links", [])

        links.sort(key=lambda l: l.get("score", 0), reverse=True)
        return {
            "topics":  topics,
            "context": "\n\n".join(context_parts),
            "sources": sources,
            "links":   links[:12],
        }

    def _fetch_x(self, category_label: str) -> dict:
        try:
            from tools.x_source import fetch_x_trends
            return fetch_x_trends(category_label)
        except Exception as e:
            print(f"[trends] x: {e}")
            return {}

    def _fetch_perplexity(self, category_label: str) -> dict:
        try:
            from tools.perplexity_source import fetch_trends, fetch_controversies
            base = fetch_trends(category_label)
            pol = fetch_controversies(category_label)
            # une tendências + polêmicas (polêmicas primeiro: viralizam mais)
            topics = (pol.get("topics", []) or []) + (base.get("topics", []) or [])
            links = (pol.get("links", []) or []) + (base.get("links", []) or [])
            ctx_parts = [c for c in (pol.get("context"), base.get("context")) if c]
            return {"topics": topics, "context": "\n\n".join(ctx_parts), "links": links}
        except Exception as e:
            print(f"[trends] perplexity: {e}")
            return {}

    def _fetch_news(self, category_label: str) -> dict:
        try:
            from tools.news_source import fetch_news
            return fetch_news(category_label)
        except Exception as e:
            print(f"[trends] news: {e}")
            return {}

    def _fetch_reddit(self, subreddits: list[str]) -> list[dict]:
        headers = {"User-Agent": "StudyFlow/1.0 (educational research)"}
        posts: list[dict] = []
        for sub in subreddits[:3]:
            try:
                resp = requests.get(
                    f"https://www.reddit.com/r/{sub}/hot.json?limit=6",
                    headers=headers, timeout=8,
                )
                if resp.status_code != 200:
                    continue
                for item in resp.json().get("data", {}).get("children", []):
                    p = item.get("data", {})
                    if p.get("stickied"):
                        continue
                    posts.append({
                        "title":     p.get("title", ""),
                        "score":     p.get("score", 0),
                        "subreddit": sub,
                        "comments":  p.get("num_comments", 0),
                        "url":       p.get("url", ""),
                    })
            except Exception as e:
                print(f"[trends] reddit r/{sub}: {e}")
        posts.sort(key=lambda x: x["score"], reverse=True)
        return posts[:10]

    def _fetch_hn_item(self, item_id: int) -> dict | None:
        try:
            resp = requests.get(
                f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json",
                timeout=5,
            )
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return None

    def _fetch_hackernews(self, keywords: list[str]) -> list[dict]:
        try:
            resp = requests.get(
                "https://hacker-news.firebaseio.com/v0/topstories.json",
                timeout=8,
            )
            if resp.status_code != 200:
                return []
            top_ids = resp.json()[:25]
            stories: list[dict] = []
            with ThreadPoolExecutor(max_workers=8) as ex:
                futures = {ex.submit(self._fetch_hn_item, sid): sid for sid in top_ids}
                for f in as_completed(futures):
                    s = f.result()
                    if not s or s.get("type") != "story":
                        continue
                    title = (s.get("title") or "").lower()
                    if any(kw.lower() in title for kw in keywords):
                        stories.append({
                            "title": s.get("title", ""),
                            "score": s.get("score", 0),
                            "url":   s.get("url", ""),
                        })
            stories.sort(key=lambda x: x["score"], reverse=True)
            return stories[:5]
        except Exception as e:
            print(f"[trends] hackernews: {e}")
        return []

    def _fetch_wikipedia(self) -> list[str]:
        _SKIP = {
            "Especial:", "Wikipédia:", "Wikipedia:", "Página_principal",
            "Main_Page", "Special:", "Portal:", "Ajuda:",
        }
        try:
            yesterday = datetime.now(tz=timezone.utc) - timedelta(days=1)
            url = (
                "https://wikimedia.org/api/rest_v1/metrics/pageviews/top/"
                f"pt.wikipedia.org/all-access/"
                f"{yesterday.year}/{yesterday.month:02d}/{yesterday.day:02d}"
            )
            resp = requests.get(url, timeout=10)
            if resp.status_code != 200:
                return []
            articles = resp.json()["items"][0]["articles"]
            result = []
            for a in articles[:40]:
                title = a["article"].replace("_", " ")
                if not any(sk in a["article"] for sk in _SKIP):
                    result.append(title)
                if len(result) >= 10:
                    break
            return result
        except Exception as e:
            print(f"[trends] wikipedia: {e}")
        return []

    def _fetch_youtube(self, query: str) -> list[dict]:
        opts: dict = {"quiet": True, "no_warnings": True, "extract_flat": True}
        if self.cookies_browser:
            opts["cookiesfrombrowser"] = (self.cookies_browser,)
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(f"ytsearch8:{query}", download=False)
                return [
                    {
                        "title": e.get("title", ""),
                        "views": e.get("view_count", 0),
                    }
                    for e in (info or {}).get("entries", [])
                    if e and e.get("title")
                ][:8]
        except Exception as e:
            print(f"[trends] youtube '{query}': {e}")
        return []

    # ── Per-category AI analysis (Chain 1 + Chain 2) ──────────────────────

    def analyze_category(self, category: str, raw: dict) -> list[dict]:
        """
        Executa Chain 1 (GPT-4o-mini Ranker) seguido de
        Chain 2 (Claude Haiku Insights) para uma categoria.
        """
        cfg   = CATEGORIES.get(category, {})
        label = cfg.get("label", category)
        icon  = cfg.get("icon", "")

        # Chain 1 — Ranker (GPT-4o-mini)
        ranked_topics = self._chain1_rank(raw, label)
        if not ranked_topics:
            return []

        # Chain 2 — Insights (Claude Haiku)
        insight_items = self._chain2_insights(ranked_topics, label, raw.get("context", ""))

        results = []
        for i, item in enumerate(insight_items[:4]):
            results.append({
                "posicao":            i + 1,
                "categoria":          category,
                "categoria_label":    label,
                "categoria_icon":     icon,
                "titulo":             item.titulo,
                "insight":            item.insight,
                "angulo":             item.angulo,
                "viral_score":        item.viral_score,
                "oportunidade_score": item.oportunidade_score,
                "polemica_score":     item.polemica_score,
                "hashtags":           item.hashtags,
                "podcasts":           item.podcasts,
                "fontes":             raw.get("sources", []),
                "links":              raw.get("links", []),
            })
        return results

    def _chain1_rank(self, raw: dict, label: str) -> list[str]:
        """Chain 1 — GPT-4o-mini: normaliza e ranqueia dados brutos."""
        topics = raw.get("topics", [])
        if not topics:
            return []

        parser = PydanticOutputParser(pydantic_object=RankedTopics)
        chain  = self.ranker_prompt | self.llm_ranker | parser

        raw_text = "\n".join(f"- {t}" for t in topics[:35] if t)

        try:
            result = chain.invoke({
                "category_label":    label,
                "raw_text":          raw_text[:3500],
                "format_instructions": parser.get_format_instructions(),
            })
            print(f"[trends:chain1] {label}: {len(result.topics)} tópicos ranqueados")
            return result.topics
        except Exception as e:
            # Recuperação: a IA às vezes gera aspas não-escapadas no meio do texto,
            # quebrando o JSON. Tenta extrair os tópicos manualmente.
            recovered = self._recover_topics(e)
            if recovered:
                print(f"[trends:chain1] {label}: {len(recovered)} tópicos recuperados "
                      "(JSON tolerante)")
                return recovered
            print(f"[trends:chain1] {label} erro: {e}")
            return topics[:5]

    @staticmethod
    def _recover_topics(err) -> list[str]:
        """Extrai a lista de tópicos de um JSON malformado (aspas não-escapadas)."""
        import re
        text = str(err)
        m = re.search(r'"topics"\s*:\s*\[(.*?)\]', text, re.DOTALL)
        if not m:
            return []
        # separa por '","' (fronteira entre itens), depois limpa aspas das pontas
        bruto = m.group(1)
        itens = re.split(r'"\s*,\s*"', bruto)
        out = []
        for it in itens:
            t = it.strip().strip('"').strip()
            # remove escapes e aspas internas soltas
            t = t.replace('\\"', '"').replace('\\n', ' ').strip()
            if len(t) >= 8:
                out.append(t)
        return out[:10]

    def _chain2_insights(
        self, topics: list[str], label: str, context: str
    ) -> list[TrendInsightItem]:
        """Chain 2 — Claude Haiku: gera insights ricos por tópico."""
        parser = PydanticOutputParser(pydantic_object=CategoryInsightsOutput)
        chain  = self.insights_prompt | self.llm_insights | parser

        topics_text = "\n".join(f"{i+1}. {t}" for i, t in enumerate(topics[:5]))
        model_name  = "Claude Haiku" if self.claude_available else "GPT-4o-mini"

        try:
            result = chain.invoke({
                "category_label":    label,
                "topics_text":       topics_text,
                "context":           context[:2500],
                "format_instructions": parser.get_format_instructions(),
            })
            print(
                f"[trends:chain2/{model_name}] {label}: "
                f"{len(result.items)} insights gerados"
            )
            return result.items
        except Exception as e:
            print(f"[trends:chain2] {label} erro: {e}")
            return [
                TrendInsightItem(
                    titulo=t, insight="", angulo="",
                    viral_score=5, oportunidade_score=5, polemica_score=3,
                    hashtags=[], podcasts=[],
                )
                for t in topics[:4]
            ]

    # ── Global synthesis (Chain 3) ─────────────────────────────────────────

    def synthesize_global(self, all_results: dict) -> dict:
        """
        Chain 3 — Claude Sonnet: detecta padrões cross-category
        e gera resumo editorial do cenário global.
        """
        summary_parts = []
        for cat, trends in all_results.items():
            if not trends:
                continue
            cfg   = CATEGORIES.get(cat, {})
            label = cfg.get("label", cat)
            icon  = cfg.get("icon", "")
            tops  = ", ".join(t["titulo"] for t in trends[:2])
            summary_parts.append(f"{icon} {label}: {tops}")

        if not summary_parts:
            return {"temas_cruzados": [], "resumo_editorial": ""}

        parser = PydanticOutputParser(pydantic_object=SynthesisOutput)
        chain  = self.synthesis_prompt | self.llm_synth | parser
        model_name = "Claude Sonnet" if self.claude_available else "GPT-4o-mini"

        try:
            result = chain.invoke({
                "categories_summary":  "\n".join(summary_parts),
                "format_instructions": parser.get_format_instructions(),
            })
            print(
                f"[trends:chain3/{model_name}] "
                f"{len(result.temas_cruzados)} temas cruzados detectados"
            )
            return result.model_dump()
        except Exception as e:
            print(f"[trends:chain3] erro: {e}")
            return {"temas_cruzados": [], "resumo_editorial": ""}
