"""
Routenverwaltung — Schmuggel-/Drogen-/Geschäfts-Routen des Kartells

Berechtigungen: ROUTE_RANKS (Supervisore, Capo, Vice Don, Don)

Commands:
  /route anlegen      Neue Route erstellen
  /route liste        Alle Routen (optional gefiltert)
  /route info         Details einer Route
  /route status       Status setzen (aktiv/pausiert/verbrannt)
  /route notiz        Notiz zur Route hinzufügen
  /route entfernen    Route komplett löschen
"""
import discord
from discord import app_commands
from discord.ext import commands

import config
import database
from utils import has_rang_in, rang_name, log_action


STATUS_EMOJI = {
    "aktiv":     "🟢",
    "pausiert":  "🟡",
    "verbrannt": "🔴",
}


def perm_check(interaction: discord.Interaction) -> tuple[bool, str]:
    if not has_rang_in(interaction.user, config.ROUTE_RANKS):
        erlaubte = ", ".join(rang_name(r) for r in config.ROUTE_RANKS)
        return False, f"❌ Routenverwaltung nur für: {erlaubte}"
    return True, ""


def route_embed(row) -> discord.Embed:
    emoji = STATUS_EMOJI.get(row["status"], "⚪")
    embed = discord.Embed(
        title=f"{emoji} Route #{row['id']} — {row['name']}",
        color=config.EMBED_COLOR,
    )
    embed.add_field(name="📍 Start",  value=row["start_ort"] or "—", inline=True)
    embed.add_field(name="🎯 Ziel",   value=row["ziel"] or "—", inline=True)
    embed.add_field(name="📦 Ware",   value=row["ware"] or "—", inline=True)
    embed.add_field(name="⚙️ Status", value=f"{emoji} `{row['status']}`", inline=True)
    embed.add_field(name="👤 Erstellt von", value=f"<@{row['erstellt_von']}>" if row["erstellt_von"] else "—", inline=True)
    embed.add_field(name="📅 Erstellt", value=row["erstellt"][:10] if row["erstellt"] else "—", inline=True)
    if row["notizen"]:
        notizen = row["notizen"][-1000:]
        embed.add_field(name="📝 Notizen", value=notizen, inline=False)
    embed.set_footer(text=f"{config.KARTELL_NAME}")
    return embed


class Route(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    group = app_commands.Group(name="route", description="Routenverwaltung des Serrano Kartells")

    # ---------- /route anlegen ----------
    @group.command(name="anlegen", description="Neue Route erstellen")
    @app_commands.describe(
        name="Name der Route (z.B. 'Tijuana-Express')",
        start="Start-Ort",
        ziel="Ziel-Ort",
        ware="Was wird transportiert?",
    )
    async def anlegen(self, interaction: discord.Interaction, name: str, start: str, ziel: str, ware: str):
        ok, err = perm_check(interaction)
        if not ok:
            await interaction.response.send_message(err, ephemeral=True)
            return

        route_id = database.route_create(name, start, ziel, ware, interaction.user.id)
        row = database.route_get(route_id)
        embed = route_embed(row)
        await interaction.response.send_message(
            content=f"✅ Route **#{route_id}** angelegt.",
            embed=embed,
        )
        await log_action(self.bot, f"🗺️ Route #{route_id} '{name}' angelegt von {interaction.user.mention}")

    # ---------- /route liste ----------
    @group.command(name="liste", description="Alle Routen auflisten")
    @app_commands.describe(status="Filtern nach Status (optional)")
    @app_commands.choices(status=[
        app_commands.Choice(name="Aktiv",     value="aktiv"),
        app_commands.Choice(name="Pausiert",  value="pausiert"),
        app_commands.Choice(name="Verbrannt", value="verbrannt"),
    ])
    async def liste(self, interaction: discord.Interaction, status: app_commands.Choice[str] = None):
        rows = database.route_list(status.value if status else None)
        if not rows:
            await interaction.response.send_message("Keine Routen gefunden.", ephemeral=True)
            return

        lines = []
        for r in rows[:25]:
            emoji = STATUS_EMOJI.get(r["status"], "⚪")
            lines.append(f"{emoji} `#{r['id']:>3}` · **{r['name']}** · {r['start_ort']} → {r['ziel']} · {r['ware']}")

        embed = discord.Embed(
            title=f"🗺️ Routen-Übersicht{' · ' + status.name if status else ''}",
            description="\n".join(lines),
            color=config.EMBED_COLOR,
        )
        embed.set_footer(text=f"{len(rows)} Route(n) gesamt")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ---------- /route info ----------
    @group.command(name="info", description="Details einer Route anzeigen")
    @app_commands.describe(route_id="Die ID der Route")
    async def info(self, interaction: discord.Interaction, route_id: int):
        row = database.route_get(route_id)
        if not row:
            await interaction.response.send_message(f"Route #{route_id} nicht gefunden.", ephemeral=True)
            return
        await interaction.response.send_message(embed=route_embed(row), ephemeral=True)

    # ---------- /route status ----------
    @group.command(name="status", description="Status einer Route ändern")
    @app_commands.describe(route_id="Die ID der Route", neuer_status="Neuer Status")
    @app_commands.choices(neuer_status=[
        app_commands.Choice(name="Aktiv",     value="aktiv"),
        app_commands.Choice(name="Pausiert",  value="pausiert"),
        app_commands.Choice(name="Verbrannt", value="verbrannt"),
    ])
    async def status(self, interaction: discord.Interaction, route_id: int, neuer_status: app_commands.Choice[str]):
        ok, err = perm_check(interaction)
        if not ok:
            await interaction.response.send_message(err, ephemeral=True)
            return

        row = database.route_get(route_id)
        if not row:
            await interaction.response.send_message(f"Route #{route_id} nicht gefunden.", ephemeral=True)
            return

        database.route_set_status(route_id, neuer_status.value)
        await interaction.response.send_message(
            f"⚙️ Route **#{route_id}**: `{row['status']}` → `{neuer_status.value}`",
        )
        await log_action(self.bot, f"⚙️ Route #{route_id} Status: {row['status']} → {neuer_status.value} (von {interaction.user.mention})")

    # ---------- /route notiz ----------
    @group.command(name="notiz", description="Notiz zur Route hinzufügen")
    @app_commands.describe(route_id="Die ID der Route", text="Notiz")
    async def notiz(self, interaction: discord.Interaction, route_id: int, text: str):
        ok, err = perm_check(interaction)
        if not ok:
            await interaction.response.send_message(err, ephemeral=True)
            return

        row = database.route_get(route_id)
        if not row:
            await interaction.response.send_message(f"Route #{route_id} nicht gefunden.", ephemeral=True)
            return

        database.route_add_notiz(route_id, f"{interaction.user.display_name}: {text}")
        await interaction.response.send_message(f"📝 Notiz zu Route **#{route_id}** hinzugefügt.", ephemeral=True)
        await log_action(self.bot, f"📝 Route #{route_id} Notiz von {interaction.user.mention}: {text}")

    # ---------- /route entfernen ----------
    @group.command(name="entfernen", description="Route komplett löschen")
    @app_commands.describe(route_id="Die ID der Route")
    async def entfernen(self, interaction: discord.Interaction, route_id: int):
        ok, err = perm_check(interaction)
        if not ok:
            await interaction.response.send_message(err, ephemeral=True)
            return

        row = database.route_get(route_id)
        if not row:
            await interaction.response.send_message(f"Route #{route_id} nicht gefunden.", ephemeral=True)
            return

        database.route_delete(route_id)
        await interaction.response.send_message(f"🗑️ Route **#{route_id}** ({row['name']}) wurde gelöscht.")
        await log_action(self.bot, f"🗑️ Route #{route_id} '{row['name']}' gelöscht von {interaction.user.mention}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Route(bot))
