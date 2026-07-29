from __future__ import annotations

from datetime import datetime, timedelta, timezone as dt_timezone, tzinfo
from typing import Any

from tools._shared import err


# Windows ships no IANA tz database and `tzdata` is not in requirements.txt, so
# zoneinfo is tried first and this table is the fallback. Only zones that never
# observe DST are listed - a fixed offset would be wrong for anything else.
FIXED_OFFSET_HOURS = {
    "utc": 0.0,
    "asia/ho_chi_minh": 7.0,
    "asia/bangkok": 7.0,
    "asia/jakarta": 7.0,
    "asia/singapore": 8.0,
    "asia/shanghai": 8.0,
    "asia/tokyo": 9.0,
    "asia/seoul": 9.0,
    "asia/kolkata": 5.5,
    "asia/dubai": 4.0,
}

TIMEFRAME_DAYS = {"day": 1, "week": 7, "month": 30, "year": 365}


def _resolve_zone(name: str) -> tuple[tzinfo, str, str]:
    wanted = (name or "").strip() or "UTC"
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo(wanted), wanted, ""
    except Exception:
        pass
    offset = FIXED_OFFSET_HOURS.get(wanted.lower())
    if offset is None:
        return dt_timezone.utc, "UTC", f"Unknown timezone {wanted!r}; fell back to UTC."
    return dt_timezone(timedelta(hours=offset)), wanted, ""


def get_current_time(timezone: str = "Asia/Ho_Chi_Minh", timeframe: str = "") -> dict[str, Any]:
    try:
        zone, zone_label, zone_warning = _resolve_zone(timezone)
        now = datetime.now(zone)
        warnings = [zone_warning] if zone_warning else []

        result: dict[str, Any] = {
            "tool": "get_current_time",
            "now_iso": now.isoformat(timespec="seconds"),
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M"),
            "weekday": now.strftime("%A"),
            "timezone": zone_label,
        }

        wanted_frame = (timeframe or "").strip().lower()
        if wanted_frame in TIMEFRAME_DAYS:
            start = now - timedelta(days=TIMEFRAME_DAYS[wanted_frame])
            result["resolved_range"] = {
                "timeframe": wanted_frame,
                "start": start.strftime("%Y-%m-%d"),
                "end": now.strftime("%Y-%m-%d"),
            }
        elif wanted_frame:
            warnings.append(f"Unknown timeframe {wanted_frame!r}; expected one of {sorted(TIMEFRAME_DAYS)}.")

        if warnings:
            result["warning"] = " ".join(warnings)
        return result
    except Exception as exc:
        return err("get_current_time", exc)
