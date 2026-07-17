from __future__ import annotations

import html
import re
from dataclasses import dataclass
from urllib.parse import parse_qs, quote, unquote, urlparse

import httpx


@dataclass(slots=True)
class SearchResult:
    title: str
    url: str
    snippet: str


async def search_web(query: str, max_results: int = 5, timeout: float = 15.0) -> list[SearchResult]:
    url = f"https://duckduckgo.com/html/?q={quote(query)}"
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        response = await client.get(url, headers={"user-agent": "PaiCLI-Python/0.1.0"})
        response.raise_for_status()
    return _parse_duckduckgo(response.text)[:max_results]


def _parse_duckduckgo(raw_html: str) -> list[SearchResult]:
    results: list[SearchResult] = []
    pattern = re.compile(
        r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>([\s\S]*?)</a>'
        r"[\s\S]*?"
        r'<a[^>]+class="result__snippet"[^>]*>([\s\S]*?)</a>',
        re.I,
    )
    for match in pattern.finditer(raw_html):
        results.append(
            SearchResult(
                title=_clean(match.group(2)),
                url=_normalize_duckduckgo_url(html.unescape(match.group(1))),
                snippet=_clean(match.group(3)),
            )
        )
    return results


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value))).strip()


def _normalize_duckduckgo_url(url: str) -> str:
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    if "uddg" in params and params["uddg"]:
        return unquote(params["uddg"][0])
    return url


async def tavily_search_web(
    query: str, api_key: str, max_results: int = 5
) -> list[SearchResult]:
    try:
        from tavily import AsyncTavilyClient  # noqa: PLC0415
    except ImportError as exc:
        raise ImportError(
            "tavily-python is required for Tavily search. "
            "Install it with: pip install paicli-python[search]"
        ) from exc

    client = AsyncTavilyClient(api_key=api_key)
    response = await client.search(query=query, max_results=max_results)
    results: list[SearchResult] = []
    for item in response.get("results", []):
        results.append(
            SearchResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=item.get("content", ""),
            )
        )
    return results
