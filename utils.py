from __future__ import annotations

import re
from datetime import timedelta

import discord

_DUR_RE = re.compile(r"^(\d+)\s*(sn|s|dk|m|sa|h|g|d)$", re.IGNORECASE)
_UNITS = {"s": 1, "sn": 1, "m": 60, "dk": 60, "h": 3600, "sa": 3600, "d": 86400, "g": 86400}


def parse_duration(text: str) -> timedelta | None:
    """'30sn', '10dk', '2sa', '1g' (ya da s/m/h/d) -> timedelta"""
    m = _DUR_RE.match(text.strip())
    if not m:
        return None
    seconds = int(m.group(1)) * _UNITS[m.group(2).lower()]
    return timedelta(seconds=seconds) if seconds > 0 else None


def format_duration(td: timedelta) -> str:
    s = int(td.total_seconds())
    parts = []
    for name, size in (("gün", 86400), ("saat", 3600), ("dakika", 60), ("saniye", 1)):
        if s >= size:
            parts.append(f"{s // size} {name}")
            s %= size
    return " ".join(parts) or "0 saniye"


async def apply_warn_penalty(member: discord.Member, count: int) -> timedelta | None:
    """3-4. uyarıda 1 saat, 5+ uyarıda 1 gün mute."""
    if count >= 5:
        dur = timedelta(days=1)
    elif count >= 3:
        dur = timedelta(hours=1)
    else:
        return None
    try:
        await member.timeout(dur, reason=f"Otomatik ceza: {count}. uyarı")
        return dur
    except discord.HTTPException:
        return None
