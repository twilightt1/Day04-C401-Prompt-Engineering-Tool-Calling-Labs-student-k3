"""Smoke-test the four team tools directly, without the model in the loop.

Run from starter_v0/:

    python scripts/smoke_new_tools.py           # offline checks + live hn_search
    python scripts/smoke_new_tools.py --offline # skip the live API check

Exits non-zero if any check fails, so it can gate a demo.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import TOOL_FUNCTIONS  # noqa: E402


PASSED: list[str] = []
FAILED: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    if condition:
        PASSED.append(label)
        print(f"[PASS] {label}")
    else:
        FAILED.append(label)
        print(f"[FAIL] {label} {detail}")


def check_now() -> None:
    now = TOOL_FUNCTIONS["now"]

    result = now()
    check("now: no error", "error" not in result, str(result))
    check("now: default zone is Asia/Ho_Chi_Minh", result.get("timezone") == "Asia/Ho_Chi_Minh")
    check("now: date matches YYYY-MM-DD", len(str(result.get("date", ""))) == 10)
    check("now: no spurious warning", "warning" not in result, str(result.get("warning")))

    ranged = now(timeframe="week")
    window = ranged.get("resolved_range", {})
    expected_start = (date.fromisoformat(ranged["date"]) - timedelta(days=7)).isoformat()
    check("now: week resolves a range", window.get("start") == expected_start, str(window))
    check("now: range ends today", window.get("end") == ranged["date"])

    bad_zone = now(timezone="Mars/Olympus_Mons")
    check("now: unknown zone falls back to UTC", bad_zone.get("timezone") == "UTC")
    check("now: unknown zone warns instead of failing", "warning" in bad_zone and "error" not in bad_zone)

    bad_frame = now(timeframe="fortnight")
    check("now: unknown timeframe warns", "warning" in bad_frame and "resolved_range" not in bad_frame)


def check_dedupe() -> None:
    dedupe = TOOL_FUNCTIONS["dedupe"]

    empty = dedupe()
    check("dedupe: None input is safe", empty.get("kept") == [] and empty.get("removed_count") == 0, str(empty))

    duplicated = dedupe(items=[
        {"title": "GPT-5 released", "url": "https://openai.com/blog/gpt-5", "source": "openai.com"},
        {"title": "GPT-5 released", "url": "https://www.openai.com/blog/gpt-5/", "source": "openai.com"},
        {"title": "Anthropic ships Claude", "url": "https://anthropic.com/news", "source": "anthropic.com"},
    ])
    check("dedupe: url variants collapse", duplicated.get("removed_count") == 1, str(duplicated.get("removed_count")))
    check("dedupe: keeps the survivors", duplicated.get("kept_count") == 2)
    check("dedupe: counts distinct sources", duplicated.get("unique_sources") == ["anthropic.com", "openai.com"])
    check("dedupe: diversity satisfied at 2", duplicated.get("source_diversity_ok") is True)

    single = dedupe(items=[{"title": "Only one", "url": "https://a.example/x", "source": "a.example"}])
    check("dedupe: single source fails diversity", single.get("source_diversity_ok") is False)

    by_title = dedupe(
        items=[
            {"title": "OpenAI launches GPT-5 today", "url": "https://a.example/1", "source": "a.example"},
            {"title": "OpenAI launches GPT-5 today", "url": "https://b.example/2", "source": "b.example"},
        ],
        match_by="title",
    )
    check("dedupe: title matching collapses reposts", by_title.get("removed_count") == 1, str(by_title))


def check_save_digest() -> None:
    save = TOOL_FUNCTIONS["save_digest"]
    outputs = ROOT / "outputs"

    unconfirmed = save(markdown="# Digest\n\n- item", filename="smoke-unconfirmed.md")
    check("save_digest: unconfirmed needs confirmation", unconfirmed.get("status") == "needs_confirmation")
    check("save_digest: unconfirmed writes nothing", not (outputs / "smoke-unconfirmed.md").exists())
    check("save_digest: unconfirmed shows a preview", "# Digest" in unconfirmed.get("preview", ""))

    target = outputs / "smoke-confirmed.md"
    target.unlink(missing_ok=True)
    confirmed = save(markdown="# Digest\n\n- item", filename="smoke-confirmed.md", confirmed=True)
    check("save_digest: confirmed saves", confirmed.get("status") == "saved", str(confirmed))
    check("save_digest: file is on disk", target.exists())
    if target.exists():
        check("save_digest: content round-trips", target.read_text(encoding="utf-8").startswith("# Digest"))

    traversal = save(markdown="x", filename="../../../etc/passwd", confirmed=True)
    written = Path(ROOT / traversal.get("path", "outputs/none.md")).resolve()
    check("save_digest: path traversal is contained", written.parent == outputs.resolve(), str(traversal.get("path")))
    check("save_digest: traversal flagged as sanitized", traversal.get("sanitized") is True)

    empty = save(markdown="   ", filename="smoke-empty.md", confirmed=True)
    check("save_digest: empty digest is an error", "error" in empty, str(empty))

    for leftover in ("smoke-confirmed.md", "passwd.md"):
        (outputs / leftover).unlink(missing_ok=True)


def check_hn_search() -> None:
    result = TOOL_FUNCTIONS["hn_search"](query="artificial intelligence", limit=3)
    if "error" in result:
        check("hn_search: live call", False, f"{result.get('error')}: {result.get('message')}")
        return
    items = result.get("items", [])
    check("hn_search: returns items", len(items) > 0, str(result.get("total_hits")))
    if items:
        first = items[0]
        check("hn_search: item has format-compatible keys", all(k in first for k in ("title", "url", "source", "summary")))
        check("hn_search: item carries a link", bool(first.get("url")))
    check("hn_search: respects limit", len(items) <= 3)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true", help="skip the live hn_search check")
    args = parser.parse_args()

    check_now()
    check_dedupe()
    check_save_digest()
    if args.offline:
        print("[SKIP] hn_search (--offline)")
    else:
        check_hn_search()

    print(f"\n{len(PASSED)} passed, {len(FAILED)} failed")
    for label in FAILED:
        print(f"  failed: {label}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
