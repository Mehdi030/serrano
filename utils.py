"""
Geteilte Hilfsfunktionen: Berechtigungen, Hierarchie, Logging, Formatierung.
"""
from datetime import datetime
import discord
from discord.ext import commands

import config


def format_relative_time(iso_ts: str) -> str:
    """'vor 2 Min', 'vor 3 Std', 'vor 5 Tagen'."""
    if not iso_ts:
        return "—"
    try:
        ts = datetime.fromisoformat(iso_ts)
        delta = datetime.utcnow() - ts
        secs = int(delta.total_seconds())
        if secs < 60:
            return f"vor {secs} Sek"
        if secs < 3600:
            return f"vor {secs // 60} Min"
        if secs < 86400:
            return f"vor {secs // 3600} Std"
        return f"vor {secs // 86400} Tagen"
    except Exception:
        return iso_ts[:16].replace("T", " ")


def rang_name(rang_nr: int) -> str:
    return config.RANGS.get(rang_nr, ("Unbekannt", 0))[0]


def get_user_rang(member: discord.Member) -> int:
    """Höchster Rang den der Member über Discord-Rollen besitzt. 0 = kein Rang."""
    if not isinstance(member, discord.Member):
        return 0
    role_ids = {r.id for r in member.roles}
    hoechster = 0
    for rang_nr, (_, rolle_id) in config.RANGS.items():
        if rolle_id and rolle_id in role_ids and rang_nr > hoechster:
            hoechster = rang_nr
    return hoechster


def has_rang_in(member: discord.Member, rang_liste: list[int]) -> bool:
    """Prüft ob Member mindestens einen der Ränge in der Liste hat."""
    own = get_user_rang(member)
    return own in rang_liste


def can_manage(actor: discord.Member, target: discord.Member, allowed_ranks: list[int]) -> tuple[bool, str]:
    """
    Hierarchie-geschützter Check:
      1. actor muss einen der allowed_ranks haben
      2. actor's Rang muss STRIKT HÖHER sein als target's Rang
    Gibt (ok, fehlertext) zurück.
    """
    actor_rang = get_user_rang(actor)
    target_rang = get_user_rang(target)

    if actor_rang not in allowed_ranks:
        erlaubte = ", ".join(rang_name(r) for r in allowed_ranks)
        return False, f"❌ Nur folgende Ränge dürfen diese Aktion: {erlaubte}"

    if target_rang >= actor_rang:
        return False, (
            f"❌ Du kannst nur Mitglieder mit niedrigerem Rang verwalten. "
            f"Dein Rang: **{rang_name(actor_rang)}** · Ziel-Rang: **{rang_name(target_rang)}**"
        )

    return True, ""


async def log_action(bot: commands.Bot, text: str):
    """Schreibt Aktion in den konfigurierten Logs-Channel."""
    if not config.CHANNEL_LOGS:
        return
    ch = bot.get_channel(config.CHANNEL_LOGS)
    if ch:
        try:
            await ch.send(text)
        except Exception:
            pass
