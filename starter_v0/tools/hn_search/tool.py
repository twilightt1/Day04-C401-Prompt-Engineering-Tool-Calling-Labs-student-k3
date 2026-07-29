from __future__ import annotations

import time
from typing import Any

import requests

from tools._shared import TIMEOUT, domain, err


SEARCH_URL = "https://hn.algolia.com/api/v1/search"
SEARCH_BY_DATE_URL = "https://hn.algolia.com/api/v1/search_by_date"
HN_ITEM_URL = "https://news.ycombinator.com/item?id="
TIMEFRAME_SECONDS = {"day": 86_400, "week": 604_800, "month": 2_592_000, "year": 31_536_000}


def _summary(hit: dict[str, Any]) -> str:
    points = hit.get("points") or 0
    comments = hit.get("num_comments") or 0
    author = hit.get("author") or "unknown"
    return f"{points} points, {comments} comments on Hacker News; submitted by {author}."


def search_hackernews(
    query: str = "",
    sort_by: str = "relevance",
    limit: int = 5,
    timeframe: str = "all",
) -> dict[str, Any]:
    try:
        limit = max(1, min(int(limit or 5), 10))
        sort_by = sort_by if sort_by in {"relevance", "recent"} else "relevance"
        wanted_frame = (timeframe or "all").strip().lower()

        params: dict[str, Any] = {
            "query": str(query or ""),
            "tags": "story",
            "hitsPerPage": limit,
        }
        window = TIMEFRAME_SECONDS.get(wanted_frame)
        if window:
            params["numericFilters"] = f"created_at_i>{int(time.time()) - window}"

        url = SEARCH_BY_DATE_URL if sort_by == "recent" else SEARCH_URL
        response = requests.get(url, params=params, timeout=TIMEOUT)
        response.raise_for_status()
        payload = response.json()

        items: list[dict[str, Any]] = []
        for hit in payload.get("hits", [])[:limit]:
            object_id = str(hit.get("objectID") or "")
            hn_url = f"{HN_ITEM_URL}{object_id}" if object_id else ""
            story_url = str(hit.get("url") or "") or hn_url
            items.append({
                "title": hit.get("title") or hit.get("story_title") or "",
                "url": story_url,
                "source": domain(story_url) or "news.ycombinator.com",
                "summary": _summary(hit),
                "points": hit.get("points"),
                "num_comments": hit.get("num_comments"),
                "author": hit.get("author"),
                "created_at": hit.get("created_at"),
                "hn_url": hn_url,
            })

        return {
            "tool": "search_hackernews",
            "query": params["query"],
            "sort_by": sort_by,
            "timeframe": wanted_frame,
            "total_hits": payload.get("nbHits"),
            "items": items,
        }
    except Exception as exc:
        return err("search_hackernews", exc)
