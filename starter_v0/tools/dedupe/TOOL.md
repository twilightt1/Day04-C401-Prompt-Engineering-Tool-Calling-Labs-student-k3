---
name: dedupe
track: bonus
kind: local_formatter
provider: none
requires_env: []
inputs: [items, match_by, min_sources]
outputs: [kept, removed_count, unique_sources, source_diversity_ok]
side_effect: false
---
# dedupe

Merges result lists that came from different tools and drops repeats. Pure
function, no network.

`match_by="url"` compares domain plus path, so the same article found twice with
different query strings collapses into one. `match_by="title"` compares the word
sets from `_shared.terms()` and treats a Jaccard overlap of 0.8 or higher as the
same story, which catches the same headline republished on two sites.

`source_diversity_ok` reports whether the kept items span at least
`min_sources` distinct sources. That connects to the source-citation rules in
`company_policy/`: a digest built from a single source should not be presented
as if it were corroborated.

Takes items already in hand. It fetches nothing, so calling it on a single item
is always wasted work.
