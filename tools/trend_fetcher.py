"""
tools/trend_fetcher.py
Busca tendências para um nicho no YouTube, Google Trends, Reddit e X.
"""

import json
import os
import re
from collections import Counter

import requests
import yt_dlp
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

# URL do provedor de PO Token (bgutil-ytdlp-pot-provider), se configurado.
POT_PROVIDER_URL = os.getenv("POT_PROVIDER_URL", "").strip()

try:
    from pytrends.request import TrendReq
    _PYTRENDS = True
except ImportError:
    _PYTRENDS = False


class TrendFetcherInput(BaseModel):
    niche: str = Field(description="Nicho ou tema para buscar")
    country: str = Field(default="BR", description="Código do país")


class TrendFetcherTool(BaseTool):
    name: str = "trend_fetcher"
    description: str = (
        "Busca tendências no YouTube, Google Trends, Reddit e X "
        "para um nicho. Retorna JSON com trending topics e top vídeos."
    )
    args_schema: type[BaseModel] = TrendFetcherInput
    cookies_browser: str = ""
    cookies_file: str = ""

    # ── YouTube ───────────────────────────────────────────────
    def _fetch_youtube(self, niche: str) -> list[dict]:
        opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,
        }
        if self.cookies_browser:
            opts["cookiesfrombrowser"] = (self.cookies_browser,)
        elif self.cookies_file:
            opts["cookiefile"] = self.cookies_file
        if POT_PROVIDER_URL:
            opts.setdefault("extractor_args", {})["youtubepot-bgutilhttp"] = {"base_url": [POT_PROVIDER_URL]}

        queries = [f"{niche} trending 2025", f"{niche} viral"]
        videos, seen = [], set()

        for query in queries:
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(
                        f"ytsearch6:{query}", download=False
                    )
                    for e in (info or {}).get("entries", []):
                        if not e:
                            continue
                        url = e.get("url") or e.get("webpage_url", "")
                        if not url or url in seen:
                            continue
                        seen.add(url)
                        dur = e.get("duration") or 0
                        videos.append({
                            "titulo": e.get("title", "Sem título"),
                            "url": url,
                            "canal": e.get("uploader", ""),
                            "duracao_minutos": round(dur / 60, 1),
                            "visualizacoes": e.get("view_count") or 0,
                            "thumbnail": e.get("thumbnail", ""),
                        })
            except Exception as ex:
                print(f"[trend_fetcher] YouTube '{query}': {ex}")

        videos.sort(key=lambda v: v["visualizacoes"], reverse=True)
        return videos[:6]

    # ── Google Trends ─────────────────────────────────────────
    def _fetch_google_trends(
        self, niche: str, country: str
    ) -> list[str]:
        if not _PYTRENDS:
            return []
        geo = {"BR": "BR", "US": "US", "PT": "PT"}.get(
            country.upper(), "BR"
        )
        try:
            pt = TrendReq(hl="pt-BR", tz=180, timeout=(10, 25))
            pt.build_payload(
                [niche], cat=0, timeframe="now 7-d", geo=geo
            )
            related = pt.related_queries()
            top = (
                related.get(niche, {}).get("top")
                if isinstance(related.get(niche), dict)
                else None
            )
            if top is not None and not top.empty:
                return top["query"].tolist()[:8]
        except Exception as ex:
            print(f"[trend_fetcher] Google Trends: {ex}")
        return []

    # ── Reddit ────────────────────────────────────────────────
    def _fetch_reddit(self, niche: str) -> list[dict]:
        headers = {"User-Agent": "StudyFlow/1.0 (educational)"}
        try:
            url = (
                f"https://www.reddit.com/search.json"
                f"?q={requests.utils.quote(niche)}&sort=hot&limit=6"
            )
            resp = requests.get(url, headers=headers, timeout=8)
            if resp.status_code != 200:
                return []
            posts = []
            for item in resp.json().get("data", {}).get("children", []):
                p = item.get("data", {})
                posts.append({
                    "titulo": p.get("title", ""),
                    "url": f"https://reddit.com{p.get('permalink','')}",
                    "upvotes": p.get("ups", 0),
                    "subreddit": p.get("subreddit", ""),
                })
            return posts
        except Exception as ex:
            print(f"[trend_fetcher] Reddit: {ex}")
        return []

    # ── Twitter / X ───────────────────────────────────────────
    def _fetch_twitter(self, niche: str) -> list[dict]:
        token = os.getenv("TWITTER_BEARER_TOKEN", "").strip()
        if not token:
            return []
        try:
            resp = requests.get(
                "https://api.twitter.com/2/tweets/search/recent",
                headers={"Authorization": f"Bearer {token}"},
                params={
                    "query": f"{niche} lang:pt -is:retweet",
                    "max_results": 10,
                    "sort_order": "relevancy",
                    "tweet.fields": "public_metrics",
                },
                timeout=8,
            )
            if resp.status_code != 200:
                return []
            tweets = []
            for t in resp.json().get("data", []):
                m = t.get("public_metrics", {})
                tweets.append({
                    "texto": t.get("text", "")[:140],
                    "likes": m.get("like_count", 0),
                    "retweets": m.get("retweet_count", 0),
                })
            return tweets
        except Exception as ex:
            print(f"[trend_fetcher] Twitter: {ex}")
        return []

    # ── Main ──────────────────────────────────────────────────
    def _run(self, niche: str, country: str = "BR") -> str:
        print(f"[trend_fetcher] Buscando tendências: '{niche}'")

        videos = self._fetch_youtube(niche)
        topics = self._fetch_google_trends(niche, country)
        reddit = self._fetch_reddit(niche)
        twitter = self._fetch_twitter(niche)

        # Fallback: extrai palavras-chave dos títulos dos vídeos
        if not topics:
            words = []
            for v in videos[:4]:
                words += re.findall(r"\b\w{4,}\b", v["titulo"].lower())
            stopwords = {
                "como", "para", "que", "com", "uma", "mais",
                "esse", "esta", "esse", "isso", "este", "pelo",
                "pela", "todo", "toda", "você", "voce", niche.lower(),
            }
            topics = [
                w for w, _ in Counter(words).most_common(12)
                if w not in stopwords
            ][:8]

        result = {
            "niche": niche,
            "trending_topics": topics,
            "top_videos": videos,
            "reddit_posts": reddit[:5],
            "twitter_posts": twitter[:5],
            "sources": {
                "youtube": bool(videos),
                "google_trends": bool(topics),
                "reddit": bool(reddit),
                "twitter": bool(twitter),
            },
        }
        print(
            f"[trend_fetcher] {len(videos)} vídeos, "
            f"{len(topics)} topics, {len(reddit)} reddit"
        )
        return json.dumps(result, ensure_ascii=False)

    async def _arun(self, **kwargs) -> str:
        return self._run(**kwargs)
