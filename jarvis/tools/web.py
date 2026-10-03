"""Web search tool (DuckDuckGo via `ddgs`, no API key)."""

from ddgs import DDGS

from jarvis.tools.registry import tool

MAX_RESULTS = 5


@tool()
def web_search(query: str) -> str:
    """Search the web for current or factual information you do not know. Answer from the results in one or two short sentences and mention the source site names.

    Args:
        query: What to search for.
    """
    try:
        results = DDGS().text(query, max_results=MAX_RESULTS)
    except Exception as exc:  # noqa: BLE001  (network and rate-limit errors vary)
        return f"Error: web search failed ({exc})."
    if not results:
        return "No results found."
    return "\n\n".join(
        f"[{i}] {r.get('title', '')}\n{r.get('href', '')}\n{r.get('body', '')[:300]}"
        for i, r in enumerate(results, 1)
    )
