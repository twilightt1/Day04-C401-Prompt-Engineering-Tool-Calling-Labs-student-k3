---
name: hn_search
track: bonus
kind: live_api
provider: Hacker News (Algolia API)
requires_env: []
inputs: [query, sort_by, limit, timeframe]
outputs: [items, total_hits]
side_effect: false
---
# hn_search

Searches Hacker News stories through the public Algolia endpoint. No API key and
no account - this is why the tool exists. The team has no RapidAPI credentials,
so `timeline` and `social_search` cannot run, and this restores the "what is the
developer community saying about X" capability without paid access.

`sort_by="relevance"` hits `/api/v1/search`; `sort_by="recent"` hits
`/api/v1/search_by_date`. `timeframe` (`day`/`week`/`month`/`year`) becomes an
Algolia `numericFilters` window; the default `all` sends no filter at all.
`limit` is clamped to 1-10.

Each item carries `title`, `url`, `source` and `summary` in the exact shape
`format` consumes, so the two tools chain without the model reshaping anything
in between. `points`, `num_comments` and `hn_url` ride along for citation.

This is a live API, so it can fail on network trouble or rate limiting. Errors
come back as `{tool, error, message}` rather than raising.
