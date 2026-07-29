from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from tools._shared import ROOT, err


OUTPUT_DIR = ROOT / "outputs"
PREVIEW_CHARS = 280
UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]")


def _safe_filename(raw: str) -> tuple[str, bool]:
    original = str(raw or "").strip()
    if not original:
        return f"digest-{datetime.now().strftime('%Y%m%d-%H%M%S')}.md", False
    # Split on both separators explicitly: Path().name only strips the separator
    # of the host OS, and this filename arrives from the model.
    basename = re.split(r"[\\/]", original)[-1]
    cleaned = UNSAFE_CHARS.sub("-", basename).strip("-.") or "digest"
    if not cleaned.lower().endswith(".md"):
        cleaned += ".md"
    return cleaned, cleaned != original


def save_digest(markdown: str = "", filename: str = "", confirmed: bool = False) -> dict[str, Any]:
    try:
        text = str(markdown or "")
        name, sanitized = _safe_filename(filename)

        if not confirmed:
            return {
                "tool": "save_digest",
                "status": "needs_confirmation",
                "message": "Only write the file after the user explicitly confirms.",
                "would_write": f"outputs/{name}",
                "preview": text[:PREVIEW_CHARS],
                "sanitized": sanitized,
            }

        if not text.strip():
            raise ValueError("Nothing to save: markdown is empty.")

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        target = (OUTPUT_DIR / name).resolve()
        if target.parent != OUTPUT_DIR.resolve():
            raise ValueError("Refusing to write outside outputs/.")

        target.write_text(text, encoding="utf-8")
        return {
            "tool": "save_digest",
            "status": "saved",
            "path": f"outputs/{name}",
            "bytes": len(text.encode("utf-8")),
            "sanitized": sanitized,
        }
    except Exception as exc:
        return err("save_digest", exc)
