"""
Dashboard — Übersichten für Member und Server

  /dashboard ich      Eigenes persönliches Dashboard
  /dashboard server   Komplette Server-Statistik
  /dashboard top      Top-Listen (Recruiter, Zahler, etc.)
"""
import discord
from discord import app_commands
from discord.ext import commands

import config
import database
from utils import rang_name


def fmt_money(betrag: int) -> str:
    return f"{betrag:,}".replace(",", ".") + " $"


class Dashboard(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    group = app_commands.Group(name="dashboard", description="Übersichten und Statistiken")

    # ---------- /dashboard ich ----------
    @group.command(name="ich", description="Dein persönliches Mitglieder-Dashboard")
    async def ich(self, interaction: discord.Interaction):
        m = database.member_get(interaction.user.id)
        if not m:
            await interaction.response.send_message(
                "❌ Du bist nicht registriert. Frag einen Maestro nach einem Colloquio.",
                ephemeral=True,
            )
            return

        warns = database.warn_list(interaction.user.id)
        notes = database.note_list(interaction.user.id)
        history = database.rang_history(interaction.user.id)
        abm = database.abmeldung_active(interaction.user.id)
        abgaben_total = database.abgabe_total(interaction.user.id)
        abgaben_list = database.abgabe_list(interaction.user.id)

        embed = discord.Embed(
            title=f"🎴 Mein Dashboard — {m['charakter_name']}",
            description=f"{interaction.user.mention} · *{config.KARTELL_NAME}*",
            color=config.EMBED_COLOR,
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)

        embed.add_field(name="🎖️ Rang",         value=f"**{rang_name(m['rang'])}** (#{m['rang']})", inline=True)
        embed.add_field(name="📅 Eintritt",      value=m["eintritt"][:10] if m["eintritt"] else "—", inline=True)
        embed.add_field(name="📊 Status",        value=m["status"], inline=True)

        embed.add_field(name="⚠️ Verwarnungen",  value=str(len(warns)), inline=True)
        embed.add_field(name="📝 Notizen",       value=str(len(notes)), inline=True)
        embed.add_field(name="📈 Beförderungen", value=str(len([h for h in history if h['neuer_rang'] > h['alter_rang']])), inline=True)

        embed.add_field(name="💰 Abgaben gesamt", value=f"**{fmt_money(abgaben_total)}**", inline=True)
        embed.add_field(name="🧾 Anzahl Zahlungen", value=str(len(abgaben_list)), inline=True)
        embed.add_field(name="🕒 Zuletzt aktiv", value=m["last_active"][:10] if m["last_active"] else "—", inline=True)

        if abm:
            embed.add_field(
                name="🌴 Aktive Abmeldung",
                value=f"bis **{abm['bis']}** · {abm['grund']}",
                inline=False,
            )

        if history:
            last = history[0]
            embed.add_field(
                name="📈 Letzte Rang-Änderung",
                value=f"`{last['timestamp'][:10]}` {rang_name(last['alter_rang'])} → **{rang_name(last['neuer_rang'])}**",
                inline=False,
            )

        embed.set_footer(text=f"{config.SERVER_NAME}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ---------- /dashboard server ----------
    @group.command(name="server", description="Komplette Server-Statistik")
    async def server(self, interaction: discord.Interaction):
        anzahl_mitglieder = database.member_count_all()
        rang_counts = database.member_count_per_rang()
        warns_total = database.total_warns()
        bewerbungen_offen = database.total_bewerbungen_open()
        routen_aktiv = database.total_routen_aktiv()
        kasse_stand = database.kasse_stand()

        embed = discord.Embed(
            title=f"🌵 {config.KARTELL_NAME} — Server-Dashboard",
            description=f"*{config.SERVER_NAME}*",
            color=config.EMBED_COLOR,
        )

        # Rang-Verteilung als Hierarchie-Liste
        hierarchie_lines = []
        for rang_nr in sorted(config.RANGS.keys(), reverse=True):
            count = rang_counts.get(rang_nr, 0)
            indicator = "■" * min(count, 10) if count else "·"
            hierarchie_lines.append(f"`{rang_nr:>2}` **{rang_name(rang_nr):<12}** {indicator} {count}")

        embed.add_field(
            name=f"👥 Mitglieder gesamt: {anzahl_mitglieder}",
            value="\n".join(hierarchie_lines),
            inline=False,
        )

        embed.add_field(name="💼 Kasse",            value=f"**{fmt_money(kasse_stand)}**", inline=True)
        embed.add_field(name="📋 Offene Bewerbungen", value=str(bewerbungen_offen), inline=True)
        embed.add_field(name="🗺️ Aktive Routen",     value=str(routen_aktiv), inline=True)
        embed.add_field(name="⚠️ Verwarnungen total", value=str(warns_total), inline=True)

        # Inventar Top-3
        items = database.inv_item_list()
        if items:
            sorted_items = sorted(items, key=lambda x: x["bestand"], reverse=True)[:5]
            inv_text = "\n".join(f"• **{i['name']}**: {i['bestand']} {i['einheit']}" for i in sorted_items)
            embed.add_field(name="📦 Top-Bestände", value=inv_text, inline=False)

        embed.set_footer(text=f"Stand: {database.now()[:16].replace('T', ' ')} UTC")
        await interaction.response.send_message(embed=embed)

    # ---------- /dashboard top ----------
    @group.command(name="top", description="Top-Listen (Recruiter, Zahler, etc.)")
    async def top(self, interaction: discord.Interaction):
        recruiter = database.top_recruiter(limit=5)
        zahler = database.abgabe_top(limit=5)

        embed = discord.Embed(title="🏆 Top-Listen", color=config.EMBED_COLOR)

        # Top Recruiter
        if recruiter:
            lines = []
            for i, r in enumerate(recruiter, 1):
                medal = ["🥇", "🥈", "🥉"][i-1] if i <= 3 else f"`#{i}`"
                lines.append(f"{medal} <@{r['recruiter_id']}> — {r['n']} Rekrutierungen")
            embed.add_field(name="👤 Top-Rekrutierer", value="\n".join(lines), inline=False)
        else:
            embed.add_field(name="👤 Top-Rekrutierer", value="Noch keine Daten.", inline=False)

        # Top Zahler
        if zahler:
            lines = []
            for i, r in enumerate(zahler, 1):
                medal = ["🥇", "🥈", "🥉"][i-1] if i <= 3 else f"`#{i}`"
                lines.append(f"{medal} <@{r['user_id']}> — **{fmt_money(r['total'])}** ({r['anzahl']}x)")
            embed.add_field(name="💰 Top-Zahler", value="\n".join(lines), inline=False)
        else:
            embed.add_field(name="💰 Top-Zahler", value="Noch keine Abgaben verbucht.", inline=False)

        embed.set_footer(text=f"{config.KARTELL_NAME}")
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Dashboard(bot))
