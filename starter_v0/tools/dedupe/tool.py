from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from tools._shared import domain, err, terms


TITLE_SIMILARITY_THRESHOLD = 0.8


def _url_key(item: dict[str, Any]) -> str:
    url = str(item.get("url") or "").strip()
    if not url:
        return ""
    path = urlparse(url).path.rstrip("/").lower()
    return f"{domain(url)}{path}"


def _is_similar(left: set[str], right: set[str]) -> bool:
    if not left or not right:
        return False
    return len(left & right) / len(left | right) >= TITLE_SIMILARITY_THRESHOLD


def dedupe_items(
    items: list[dict[str, Any]] | None = None,
    match_by: str = "url",
    min_sources: int = 2,
) -> dict[str, Any]:
    try:
        candidates = [item for item in (items or []) if isinstance(item, dict)]
        mode = (match_by or "url").strip().lower()
        if mode not in {"url", "title"}:
            mode = "url"

        kept: list[dict[str, Any]] = []
        removed_count = 0
        seen_urls: set[str] = set()
        seen_titles: list[set[str]] = []

        for item in candidates:
            if mode == "url":
                key = _url_key(item)
                duplicate = bool(key) and key in seen_urls
                if key and not duplicate:
                    seen_urls.add(key)
            else:
                title_terms = terms(str(item.get("title") or ""))
                duplicate = any(_is_similar(title_terms, seen) for seen in seen_titles)
                if title_terms and not duplicate:
                    seen_titles.append(title_terms)
            if duplicate:
                removed_count += 1
            else:
                kept.append(item)

        sources = sorted({
            str(item.get("source") or domain(str(item.get("url") or "")) or "unknown")
            for item in kept
        })
        required_sources = max(1, int(min_sources or 1))
        return {
            "tool": "dedupe_items",
            "match_by": mode,
            "kept": kept,
            "kept_count": len(kept),
            "removed_count": removed_count,
            "unique_sources": sources,
            "source_diversity_ok": len(sources) >= required_sources,
            "min_sources": required_sources,
        }
    except Exception as exc:
        return err("dedupe_items", exc)
