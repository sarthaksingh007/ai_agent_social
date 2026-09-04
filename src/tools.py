"""Agent tools. Currently: free web search via DuckDuckGo (no API key).

Used by the Strategist for competitor analysis and trend discovery. Returns
real result URLs so the agent can satisfy the evidence-citation guardrail.

DuckDuckGo rate-limits bursts of queries (HTTP 202 "Ratelimit"), so we retry
with backoff and fall back across its search backends.
"""
import time

from crewai.tools import BaseTool
from duckduckgo_search import DDGS
from pydantic import BaseModel, Field


class _SearchArgs(BaseModel):
    query: str = Field(description="The search query")


def _search(query: str, max_results: int = 4) -> list[dict]:
    """Fail-fast web search. Tries two backends with a single short retry so a
    rate-limited search never blocks the agent for long — returns [] instead."""
    for backend in ("lite", "html"):
        for attempt in range(2):
            try:
                with DDGS(timeout=8) as ddgs:
                    return list(
                        ddgs.text(query, max_results=max_results, backend=backend)
                    )
            except Exception as exc:  # noqa: BLE001
                if attempt == 0 and (
                    "ratelimit" in str(exc).lower() or "202" in str(exc)
                ):
                    time.sleep(1)
                    continue
                break  # give up on this backend quickly
    return []


class WebSearchTool(BaseTool):
    name: str = "web_search"
    description: str = (
        "Search the web for competitor activity, market trends, and evidence. "
        "Returns results with title, snippet, and URL. Cite the returned URLs "
        "as evidence. Use sparingly — 2-3 focused queries is enough."
    )
    args_schema: type[BaseModel] = _SearchArgs

    def _run(self, query: str) -> str:
        results = _search(query)
        if not results:
            return (
                "No results (search temporarily rate-limited). Proceed with "
                "what you already have; do not invent URLs."
            )
        lines = []
        for r in results:
            title = r.get("title", "")
            url = r.get("href", "")
            body = r.get("body", "")[:180]
            lines.append(f"- {title}\n  URL: {url}\n  {body}")
        return "\n".join(lines)
