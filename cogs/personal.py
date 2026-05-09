"""
Personal — Verwaltung der bestehenden Mitglieder

Berechtigungen (siehe config.py):
  /akte, /mitglieder, /inaktiv      -> jeder darf einsehen
  /abmelden                          -> alle Kartell-Mitglieder
  /befoerdern, /degradieren,
  /verwarnen, /notiz                 -> PERSONAL_AKTION_RANKS, mit Hierarchie-Schutz
                                        (man kann nur Raenge UNTER sich anfassen)
  /rauswurf                          -> RAUSWURF_RANKS, mit Hierarchie-Schutz

Befoerdern-Logik: Der NEUE Rang muss noch unter dem eigenen Rang liegen.
                  Reclutatore (5) kann also max. auf Rang 4 befoerdern.
"""
import discord
from discord import app_commands
from discord.ext import commands

import config
import database
from utils import has_rang_in, can_manage, get_user_rang, rang_name, log_action


class Personal(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ---------- /akte ----------
    @app_commands.command(name="akte", description="Personal-Akte eines Mitglieds anzeigen")
    @app_commands.describe(user="Mitglied")
    async def akte(self, interaction: discord.Interaction, user: discord.Member):
        m = database.member_get(user.id)
        if not m:
            await interaction.response.send_message(
                f"❌ Keine Personal-Akte fuer {user.mention} vorhanden.", ephemeral=True,
            )
            return

        warns = database.warn_list(user.id)
        notes = database.note_list(user.id)
        history = database.rang_history(user.id)
        abmeldung = database.abmeldung_active(user.id)

        embed = discord.Embed(
            title=f"📁 Personal-Akte — {m['charakter_name']}",
            description=f"{user.mention} · `{user.id}`",
            color=config.EMBED_COLOR,
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.add_field(name="🎖️ Rang",            value=f"**{rang_name(m['rang'])}** (Rang {m['rang']})", inline=True)
        embed.add_field(name="📅 Eintritt",         value=m["eintritt"][:10] if m["eintritt"] else "—", inline=True)
        embed.add_field(name="📊 Status",           value=m["status"], inline=True)
        embed.add_field(name="👤 Rekrutiert von",   value=f"<@{m['recruiter_id']}>" if m["recruiter_id"] else "—", inline=True)
        embed.add_field(name="🕒 Zuletzt aktiv",    value=m["last_active"][:16].replace("T", " ") if m["last_active"] else "—", inline=True)
        embed.add_field(name="⚠️ Verwarnungen",     value=str(len(warns)), inline=True)

        if abmeldung:
            embed.add_field(
                name="🌴 Abmeldung aktiv",
                value=f"bis **{abmeldung['bis']}** — {abmeldung['grund']}",
                inline=False,
            )

        if warns:
            warn_text = "\n".join(f"• `{w['timestamp'][:10]}` — {w['grund']}" for w in warns[:5])
            embed.add_field(name=f"⚠️ Letzte Verwarnungen ({len(warns)})", value=warn_text, inline=False)

        if notes:
            note_text = "\n".join(f"• `{n['timestamp'][:10]}` — {n['text']}" for n in notes[:5])
            embed.add_field(name=f"📝 Notizen ({len(notes)})", value=note_text, inline=False)

        if history:
            hist_text = "\n".join(
                f"• `{h['timestamp'][:10]}` {rang_name(h['alter_rang'])} → **{rang_name(h['neuer_rang'])}** ({h['grund'] or '—'})"
                for h in history[:5]
            )
            embed.add_field(name="📈 Rang-Historie", value=hist_text, inline=False)

        embed.set_footer(text=f"{config.KARTELL_NAME} · {config.SERVER_NAME}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ---------- /befoerdern ----------
    @app_commands.command(name="befoerdern", description="Mitglied befoerdern (Rang +1, mit Hierarchie-Schutz)")
    @app_commands.describe(user="Mitglied", grund="Grund der Befoerderung")
    async def befoerdern(self, interaction: discord.Interaction, user: discord.Member, grund: str = "—"):
        ok, err = can_manage(interaction.user, user, config.PERSONAL_AKTION_RANKS)
        if not ok:
            await interaction.response.send_message(err, ephemeral=True)
            return

        m = database.member_get(user.id)
        if not m:
            await interaction.response.send_message("❌ Keine Personal-Akte vorhanden.", ephemeral=True)
            return

        alt = m["rang"]
        neu = alt + 1
        if neu not in config.RANGS:
            await interaction.response.send_message("❌ Hoechster Rang erreicht.", ephemeral=True)
            return

        # Hierarchie: Neuer Rang muss STRIKT UNTER eigenem Rang bleiben
        own_rang = get_user_rang(interaction.user)
        if neu >= own_rang:
            await interaction.response.send_message(
                f"❌ Du kannst nicht auf Rang **{rang_name(neu)}** befoerdern (>= dein eigener Rang **{rang_name(own_rang)}**).",
                ephemeral=True,
            )
            return

        alte_rolle_id = config.RANGS[alt][1]
        neue_rolle_id = config.RANGS[neu][1]
        if alte_rolle_id:
            r = interaction.guild.get_role(alte_rolle_id)
            if r and r in user.roles:
                await user.remove_roles(r, reason=f"Befoerderung: {grund}")
        if neue_rolle_id:
            r = interaction.guild.get_role(neue_rolle_id)
            if r:
                await user.add_roles(r, reason=f"Befoerderung: {grund}")

        database.member_update_rang(user.id, neu)
        database.rang_log(user.id, alt, neu, grund, interaction.user.id)

        try:
            await user.send(
                f"📈 Du wurdest im **{config.KARTELL_NAME}** befoerdert!\n"
                f"**{rang_name(alt)}** → **{rang_name(neu)}**\nGrund: {grund}"
            )
        except discord.Forbidden:
            pass

        await interaction.response.send_message(
            f"✅ {user.mention}: **{rang_name(alt)}** → **{rang_name(neu)}**",
        )
        await log_action(self.bot, f"📈 Befoerderung: {user.mention} {rang_name(alt)} → {rang_name(neu)} (von {interaction.user.mention}, Grund: {grund})")

    # ---------- /degradieren ----------
    @app_commands.command(name="degradieren", description="Mitglied degradieren (Rang -1)")
    @app_commands.describe(user="Mitglied", grund="Grund der Degradierung")
    async def degradieren(self, interaction: discord.Interaction, user: discord.Member, grund: str):
        ok, err = can_manage(interaction.user, user, config.PERSONAL_AKTION_RANKS)
        if not ok:
            await interaction.response.send_message(err, ephemeral=True)
            return

        m = database.member_get(user.id)
        if not m:
            await interaction.response.send_message("❌ Keine Personal-Akte vorhanden.", ephemeral=True)
            return

        alt = m["rang"]
        neu = alt - 1
        if neu < 1:
            await interaction.response.send_message("❌ Niedrigster Rang erreicht. Nutze /rauswurf falls noetig.", ephemeral=True)
            return

        alte_rolle_id = config.RANGS[alt][1]
        neue_rolle_id = config.RANGS[neu][1]
        if alte_rolle_id:
            r = interaction.guild.get_role(alte_rolle_id)
            if r and r in user.roles:
                await user.remove_roles(r, reason=f"Degradierung: {grund}")
        if neue_rolle_id:
            r = interaction.guild.get_role(neue_rolle_id)
            if r:
                await user.add_roles(r, reason=f"Degradierung: {grund}")

        database.member_update_rang(user.id, neu)
        database.rang_log(user.id, alt, neu, grund, interaction.user.id)

        try:
            await user.send(
                f"📉 Du wurdest im **{config.KARTELL_NAME}** degradiert.\n"
                f"**{rang_name(alt)}** → **{rang_name(neu)}**\nGrund: {grund}"
            )
        except discord.Forbidden:
            pass

        await interaction.response.send_message(
            f"📉 {user.mention}: **{rang_name(alt)}** → **{rang_name(neu)}**",
        )
        await log_action(self.bot, f"📉 Degradierung: {user.mention} {rang_name(alt)} → {rang_name(neu)} (von {interaction.user.mention}, Grund: {grund})")

    # ---------- /verwarnen ----------
    @app_commands.command(name="verwarnen", description="Mitglied verwarnen")
    @app_commands.describe(user="Mitglied", grund="Grund der Verwarnung")
    async def verwarnen(self, interaction: discord.Interaction, user: discord.Member, grund: str):
        ok, err = can_manage(interaction.user, user, config.PERSONAL_AKTION_RANKS)
        if not ok:
            await interaction.response.send_message(err, ephemeral=True)
            return

        database.warn_add(user.id, grund, interaction.user.id)
        count = database.warn_count(user.id)

        try:
            await user.send(
                f"⚠️ Du hast eine Verwarnung im **{config.KARTELL_NAME}** erhalten.\n"
                f"**Verwarnung Nr. {count}**\nGrund: {grund}"
            )
        except discord.Forbidden:
            pass

        msg = f"⚠️ {user.mention} verwarnt ({count}). Grund: {grund}"

        if count >= config.WARN_LIMIT_BIS_SANKTION and config.CHANNEL_SANKTIONEN:
            ch = self.bot.get_channel(config.CHANNEL_SANKTIONEN)
            if ch:
                eskal_embed = discord.Embed(
                    title="🚨 Sanktions-Eskalation",
                    description=f"{user.mention} hat **{count} Verwarnungen** erreicht.\n"
                                f"Letzter Grund: {grund}\n\n"
                                f"Capo+ entscheiden ueber weitere Sanktion.",
                    color=0xFF0000,
                )
                await ch.send(embed=eskal_embed)
            msg += f"\n🚨 Auto-Eskalation in <#{config.CHANNEL_SANKTIONEN}>"

        await interaction.response.send_message(msg)
        await log_action(self.bot, f"⚠️ Verwarnung: {user.mention} ({count}) von {interaction.user.mention} — {grund}")

    # ---------- /notiz ----------
    @app_commands.command(name="notiz", description="Interne Notiz zu einem Mitglied hinzufuegen")
    @app_commands.describe(user="Mitglied", text="Notiz")
    async def notiz(self, interaction: discord.Interaction, user: discord.Member, text: str):
        ok, err = can_manage(interaction.user, user, config.PERSONAL_AKTION_RANKS)
        if not ok:
            await interaction.response.send_message(err, ephemeral=True)
            return
        database.note_add(user.id, text, interaction.user.id)
        await interaction.response.send_message(f"📝 Notiz fuer {user.mention} gespeichert.", ephemeral=True)
        await log_action(self.bot, f"📝 Notiz fuer {user.mention} von {interaction.user.mention}: {text}")

    # ---------- /mitglieder ----------
    @app_commands.command(name="mitglieder", description="Mitglieder eines bestimmten Rangs auflisten")
    @app_commands.describe(rang="Welcher Rang? (1-12)")
    async def mitglieder(self, interaction: discord.Interaction, rang: int):
        if rang not in config.RANGS:
            await interaction.response.send_message("❌ Rang ungueltig (1-12).", ephemeral=True)
            return
        rows = database.member_list_by_rang(rang)
        if not rows:
            await interaction.response.send_message(f"Keine Mitglieder im Rang **{rang_name(rang)}**.", ephemeral=True)
            return

        lines = [f"• <@{r['user_id']}> — **{r['charakter_name']}** (seit {r['eintritt'][:10]})" for r in rows]
        embed = discord.Embed(
            title=f"🎖️ {rang_name(rang)} (Rang {rang})",
            description="\n".join(lines),
            color=config.EMBED_COLOR,
        )
        embed.set_footer(text=f"{len(rows)} Mitglied(er)")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ---------- /inaktiv ----------
    @app_commands.command(name="inaktiv", description="Inaktive Mitglieder anzeigen")
    @app_commands.describe(tage="Wie viele Tage Inaktivitaet?")
    async def inaktiv(self, interaction: discord.Interaction, tage: int = 7):
        rows = database.member_list_inactive(tage)
        if not rows:
            await interaction.response.send_message(f"✅ Keine Inaktivitaet > {tage} Tage.", ephemeral=True)
            return
        lines = [
            f"• <@{r['user_id']}> · **{r['charakter_name']}** · {rang_name(r['rang'])} · zuletzt {r['last_active'][:10] if r['last_active'] else '—'}"
            for r in rows[:25]
        ]
        embed = discord.Embed(
            title=f"😴 Inaktiv > {tage} Tage",
            description="\n".join(lines),
            color=0xFFA500,
        )
        embed.set_footer(text=f"{len(rows)} Mitglied(er)")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ---------- /abmelden ----------
    @app_commands.command(name="abmelden", description="Selbst abmelden (Urlaub etc.)")
    @app_commands.describe(bis="Bis wann (z.B. 15.05.2026)", grund="Grund")
    async def abmelden(self, interaction: discord.Interaction, bis: str, grund: str):
        if not database.member_exists(interaction.user.id):
            await interaction.response.send_message("Du bist kein registriertes Kartell-Mitglied.", ephemeral=True)
            return
        database.abmeldung_add(interaction.user.id, bis, grund)
        embed = discord.Embed(
            title="🌴 Abmeldung registriert",
            description=f"{interaction.user.mention} ist bis **{bis}** abgemeldet.\n**Grund:** {grund}",
            color=config.EMBED_COLOR,
        )
        await interaction.response.send_message(embed=embed)
        await log_action(self.bot, f"🌴 Abmeldung: {interaction.user.mention} bis {bis} — {grund}")

    # ---------- /rauswurf ----------
    @app_commands.command(name="rauswurf", description="Mitglied aus dem Kartell werfen")
    @app_commands.describe(user="Mitglied", grund="Grund")
    async def rauswurf(self, interaction: discord.Interaction, user: discord.Member, grund: str):
        ok, err = can_manage(interaction.user, user, config.RAUSWURF_RANKS)
        if not ok:
            await interaction.response.send_message(err, ephemeral=True)
            return

        m = database.member_get(user.id)
        if not m:
            await interaction.response.send_message("❌ Keine Personal-Akte vorhanden.", ephemeral=True)
            return

        for _rang_nr, (_, rolle_id) in config.RANGS.items():
            if rolle_id:
                r = interaction.guild.get_role(rolle_id)
                if r and r in user.roles:
                    try:
                        await user.remove_roles(r, reason=f"Rauswurf: {grund}")
                    except Exception:
                        pass

        database.member_set_status(user.id, "rausgeworfen")
        database.rang_log(user.id, m["rang"], 0, f"Rauswurf: {grund}", interaction.user.id)

        try:
            await user.send(
                f"🚫 Du wurdest aus dem **{config.KARTELL_NAME}** ausgeschlossen.\n**Grund:** {grund}"
            )
        except discord.Forbidden:
            pass

        await interaction.response.send_message(f"🚫 {user.mention} wurde rausgeworfen. Grund: {grund}")
        await log_action(self.bot, f"🚫 Rauswurf: {user.mention} von {interaction.user.mention} — {grund}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Personal(bot))
