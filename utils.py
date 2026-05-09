"""
Geteilte Hilfsfunktionen: Berechtigungen, Hierarchie, Logging.
"""
import discord
from discord.ext import commands

import config


def rang_name(rang_nr: int) -> str:
    return config.RANGS.get(rang_nr, ("Unbekannt", 0))[0]


def get_user_rang(member: discord.Member) -> int:
    """Hoechster Rang den der Member ueber Discord-Rollen besitzt. 0 = kein Rang."""
    if not isinstance(member, discord.Member):
        return 0
    role_ids = {r.id for r in member.roles}
    hoechster = 0
    for rang_nr, (_, rolle_id) in config.RANGS.items():
        if rolle_id and rolle_id in role_ids and rang_nr > hoechster:
            hoechster = rang_nr
    return hoechster


def has_rang_in(member: discord.Member, rang_liste: list[int]) -> bool:
    """Prueft ob Member mindestens einen der Raenge in der Liste hat."""
    own = get_user_rang(member)
    return own in rang_liste


def can_manage(actor: discord.Member, target: discord.Member, allowed_ranks: list[int]) -> tuple[bool, str]:
    """
    Hierarchie-geschuetzter Check:
      1. actor muss einen der allowed_ranks haben
      2. actor's Rang muss STRIKT HOEHER sein als target's Rang
    Gibt (ok, fehlertext) zurueck.
    """
    actor_rang = get_user_rang(actor)
    target_rang = get_user_rang(target)

    if actor_rang not in allowed_ranks:
        erlaubte = ", ".join(rang_name(r) for r in allowed_ranks)
        return False, f"❌ Nur folgende Raenge duerfen diese Aktion: {erlaubte}"

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
