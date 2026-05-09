"""
Bewerbung — Recruiting-System fuer Serrano

Workflow:
  Bewerber spricht Serrano IN-GAME an -> wird in Discord eingeladen
  Maestro tippt:  /bewerbung start @bewerber
    -> Modal Welle 1 oeffnet sich beim Maestro
    -> Maestro fragt muendlich, tippt Antworten ein
    -> Bot postet Dokument in Vorstellungsgespraech-Channel
  Maestro tippt:  /bewerbung welle2 <bewerbungs-id>
    -> Modal Welle 2 (Charakter-Tiefe, 2 Teile)
    -> Bot updated Dokument
  Klick [Annehmen] / [Ablehnen]
    -> Bei Annahme: Candidato-Rolle, Personal-Akte, Welcome-DM
"""
import json
import discord
from discord import app_commands
from discord.ext import commands

import config
import database
from utils import has_rang_in, rang_name, log_action


def build_dokument_embed(bewerbung_row, bewerber: discord.User, maestro: discord.User) -> discord.Embed:
    welle1 = json.loads(bewerbung_row["welle1_data"]) if bewerbung_row["welle1_data"] else {}
    welle2 = json.loads(bewerbung_row["welle2_data"]) if bewerbung_row["welle2_data"] else None

    status_emoji = {
        "welle1_offen":  "📝",
        "welle2_offen":  "🔍",
        "angenommen":    "✅",
        "abgelehnt":     "❌",
    }.get(bewerbung_row["status"], "📄")

    embed = discord.Embed(
        title=f"{status_emoji} Bewerbung #{bewerbung_row['id']} — {bewerber.display_name}",
        description=f"**Bewerber:** {bewerber.mention}\n**Maestro:** {maestro.mention}\n**Status:** `{bewerbung_row['status']}`",
        color=config.EMBED_COLOR,
    )
    embed.set_thumbnail(url=bewerber.display_avatar.url)

    embed.add_field(name="━━━━━━━━━━ WELLE 1 — Erstkontakt (IC) ━━━━━━━━━━", value="​", inline=False)
    embed.add_field(name="🎭 Charakter-Name",      value=welle1.get("name", "—"), inline=False)
    embed.add_field(name="🎂 Alter & Herkunft",    value=welle1.get("alter_herkunft", "—"), inline=False)
    embed.add_field(name="⚔️ Erfahrungsstand",     value=welle1.get("erfahrung", "—"), inline=False)
    embed.add_field(name="🏴 Vorherige Crews",     value=welle1.get("crews", "—"), inline=False)
    embed.add_field(name="🌵 Warum Serrano?",      value=welle1.get("warum", "—"), inline=False)

    if welle2:
        embed.add_field(name="━━━━━━━━━━ WELLE 2 — Charakter-Tiefe (IC) ━━━━━━━━━━", value="​", inline=False)
        embed.add_field(name="📖 Backstory",            value=welle2.get("backstory", "—"), inline=False)
        embed.add_field(name="🛣️ Weg zu Serrano",        value=welle2.get("weg", "—"), inline=False)
        embed.add_field(name="🎯 Spezialisierung",       value=welle2.get("spezi", "—"), inline=False)
        embed.add_field(name="🤝 Verbindungen",          value=welle2.get("verbindungen", "—"), inline=False)
        embed.add_field(name="⛓️ Vorstrafen IC",         value=welle2.get("vorstrafen", "—"), inline=False)
        embed.add_field(name="👮 Verhalten gg. Polizei", value=welle2.get("polizei", "—"), inline=False)
        embed.add_field(name="🏆 Ziele im Kartell",      value=welle2.get("ziele", "—"), inline=False)
        embed.add_field(name="🎬 RP-Beispiel-Szene",     value=welle2.get("szene", "—"), inline=False)

    embed.set_footer(text=f"{config.KARTELL_NAME} · {config.SERVER_NAME} · Bewerbungs-ID {bewerbung_row['id']}")
    return embed


# ---------- Welle 1 Modal ----------
class Welle1Modal(discord.ui.Modal, title="Bewerbung · Welle 1 (IC-Erstkontakt)"):
    def __init__(self, bot: commands.Bot, bewerber: discord.Member, maestro: discord.Member):
        super().__init__()
        self.bot = bot
        self.bewerber = bewerber
        self.maestro = maestro

        self.name = discord.ui.TextInput(
            label="Charakter-Name (Vor- + Nachname)",
            placeholder="z.B. Diego Hernandez",
            max_length=100, required=True,
        )
        self.alter_herkunft = discord.ui.TextInput(
            label="Alter & Herkunft",
            placeholder="z.B. 32, geboren in Tijuana, in Azzlack seit 4 Jahren",
            style=discord.TextStyle.paragraph, max_length=300, required=True,
        )
        self.erfahrung = discord.ui.TextInput(
            label="Erfahrungsstand des Charakters",
            placeholder="Anfaenger / Erfahren / Veteran — kurz erlaeutern",
            style=discord.TextStyle.paragraph, max_length=500, required=True,
        )
        self.crews = discord.ui.TextInput(
            label="Vorherige Crews / Fraktionen (IC)",
            placeholder="welche Gangs hat dein Char gesehen?",
            style=discord.TextStyle.paragraph, max_length=500, required=True,
        )
        self.warum = discord.ui.TextInput(
            label="Warum Serrano? (IC-Motivation)",
            placeholder="was zieht deinen Char zum Kartell?",
            style=discord.TextStyle.paragraph, max_length=700, required=True,
        )
        for item in (self.name, self.alter_herkunft, self.erfahrung, self.crews, self.warum):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction):
        data = {
            "name":           self.name.value,
            "alter_herkunft": self.alter_herkunft.value,
            "erfahrung":      self.erfahrung.value,
            "crews":          self.crews.value,
            "warum":          self.warum.value,
        }
        bewerbung_id = database.bewerbung_create(
            user_id=self.bewerber.id,
            maestro_id=self.maestro.id,
            welle1_json=json.dumps(data, ensure_ascii=False),
        )
        row = database.bewerbung_get(bewerbung_id)
        embed = build_dokument_embed(row, self.bewerber, self.maestro)

        target_ch = interaction.client.get_channel(config.CHANNEL_VORSTELLUNGSGESPRAECH) or interaction.channel
        view = AnnahmeView(bewerbung_id)
        msg = await target_ch.send(
            content=f"📝 Neue Bewerbung: {self.bewerber.mention} — Welle 1 abgeschlossen",
            embed=embed,
            view=view,
        )
        database.bewerbung_set_message(bewerbung_id, msg.id, target_ch.id)

        await interaction.response.send_message(
            f"✅ Welle 1 fuer {self.bewerber.mention} gespeichert (Bewerbungs-ID **#{bewerbung_id}**).\n"
            f"Dokument: {msg.jump_url}",
            ephemeral=True,
        )
        await log_action(self.bot, f"📝 Bewerbung #{bewerbung_id} gestartet von {self.maestro.mention} fuer {self.bewerber.mention}")


# ---------- Welle 2 Modale (2 Teile, Discord-Limit: 5 Felder pro Modal) ----------
class Welle2ModalA(discord.ui.Modal, title="Bewerbung · Welle 2A (Charakter-Tiefe)"):
    def __init__(self, bot: commands.Bot, bewerbung_id: int):
        super().__init__()
        self.bot = bot
        self.bewerbung_id = bewerbung_id

        self.backstory = discord.ui.TextInput(
            label="Backstory (3-5 Saetze)",
            style=discord.TextStyle.paragraph, max_length=1000, required=True,
        )
        self.weg = discord.ui.TextInput(
            label="Wie kam Char auf Serrano?",
            style=discord.TextStyle.paragraph, max_length=600, required=True,
        )
        self.spezi = discord.ui.TextInput(
            label="Spezialisierung",
            placeholder="Sicario / Lavador / Fahrer / Verhandler / Schmuggler / Tech",
            max_length=200, required=True,
        )
        self.verbindungen = discord.ui.TextInput(
            label="Verbindungen (Familie / Freunde / Feinde)",
            style=discord.TextStyle.paragraph, max_length=600, required=True,
        )
        self.vorstrafen = discord.ui.TextInput(
            label="Vorstrafen IC",
            style=discord.TextStyle.paragraph, max_length=400, required=True,
        )
        for item in (self.backstory, self.weg, self.spezi, self.verbindungen, self.vorstrafen):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction):
        partial = {
            "backstory":    self.backstory.value,
            "weg":          self.weg.value,
            "spezi":        self.spezi.value,
            "verbindungen": self.verbindungen.value,
            "vorstrafen":   self.vorstrafen.value,
        }
        await interaction.response.send_message(
            "Teil 1 von 2 erfasst. Klick auf **Weiter zu Teil 2**.",
            view=Welle2ContinueView(self.bot, self.bewerbung_id, partial),
            ephemeral=True,
        )


class Welle2ContinueView(discord.ui.View):
    def __init__(self, bot, bewerbung_id, partial):
        super().__init__(timeout=600)
        self.bot = bot
        self.bewerbung_id = bewerbung_id
        self.partial = partial

    @discord.ui.button(label="Weiter zu Teil 2", style=discord.ButtonStyle.primary, emoji="➡️")
    async def cont(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(Welle2ModalB(self.bot, self.bewerbung_id, self.partial))


class Welle2ModalB(discord.ui.Modal, title="Bewerbung · Welle 2B (Charakter-Tiefe)"):
    def __init__(self, bot: commands.Bot, bewerbung_id: int, partial: dict):
        super().__init__()
        self.bot = bot
        self.bewerbung_id = bewerbung_id
        self.partial = partial

        self.polizei = discord.ui.TextInput(
            label="Verhalten gegenueber Polizei",
            style=discord.TextStyle.paragraph, max_length=400, required=True,
        )
        self.ziele = discord.ui.TextInput(
            label="Ziele im Kartell",
            style=discord.TextStyle.paragraph, max_length=500, required=True,
        )
        self.szene = discord.ui.TextInput(
            label="RP-Beispiel-Szene (Rivale spricht Char an)",
            style=discord.TextStyle.paragraph, max_length=1000, required=True,
        )
        for item in (self.polizei, self.ziele, self.szene):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction):
        full = dict(self.partial)
        full["polizei"] = self.polizei.value
        full["ziele"] = self.ziele.value
        full["szene"] = self.szene.value

        database.bewerbung_set_welle2(self.bewerbung_id, json.dumps(full, ensure_ascii=False))
        row = database.bewerbung_get(self.bewerbung_id)

        bewerber = await interaction.client.fetch_user(int(row["user_id"]))
        maestro = await interaction.client.fetch_user(int(row["maestro_id"]))
        embed = build_dokument_embed(row, bewerber, maestro)

        if row["message_id"] and row["channel_id"]:
            try:
                ch = interaction.client.get_channel(int(row["channel_id"]))
                msg = await ch.fetch_message(int(row["message_id"]))
                await msg.edit(
                    content=f"🔍 Bewerbung: {bewerber.mention} — Welle 2 abgeschlossen, bereit zur Annahme",
                    embed=embed,
                    view=AnnahmeView(self.bewerbung_id),
                )
            except Exception:
                pass

        await interaction.response.send_message(
            f"✅ Welle 2 fuer Bewerbung **#{self.bewerbung_id}** gespeichert.",
            ephemeral=True,
        )
        await log_action(self.bot, f"🔍 Bewerbung #{self.bewerbung_id} Welle 2 abgeschlossen")


# ---------- Annahme/Ablehnung Buttons ----------
class AnnahmeView(discord.ui.View):
    def __init__(self, bewerbung_id: int):
        super().__init__(timeout=None)
        self.bewerbung_id = bewerbung_id

    @discord.ui.button(label="Annehmen", style=discord.ButtonStyle.success, emoji="✅", custom_id="bewerbung_accept")
    async def annehmen(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not has_rang_in(interaction.user, config.RECRUITING_RANKS):
            erlaubte = ", ".join(rang_name(r) for r in config.RECRUITING_RANKS)
            await interaction.response.send_message(
                f"❌ Nur folgende Raenge: {erlaubte}", ephemeral=True,
            )
            return

        row = database.bewerbung_get(self.bewerbung_id)
        if not row:
            await interaction.response.send_message("Bewerbung nicht gefunden.", ephemeral=True)
            return
        if row["status"] in ("angenommen", "abgelehnt"):
            await interaction.response.send_message(f"Bereits abgeschlossen: {row['status']}.", ephemeral=True)
            return

        bewerber = interaction.guild.get_member(int(row["user_id"]))
        if not bewerber:
            await interaction.response.send_message("Bewerber nicht mehr im Server.", ephemeral=True)
            return

        w1 = json.loads(row["welle1_data"]) if row["welle1_data"] else {}
        charakter_name = w1.get("name", bewerber.display_name)

        rang_nr = config.RANG_NACH_ANNAHME
        rolle_id = config.RANGS.get(rang_nr, (None, 0))[1]
        if rolle_id:
            rolle = interaction.guild.get_role(rolle_id)
            if rolle:
                try:
                    await bewerber.add_roles(rolle, reason="Bewerbung angenommen")
                except discord.Forbidden:
                    await interaction.response.send_message(
                        "⚠️ Bot fehlt Berechtigung zum Rollen-Vergeben. Manuell zuweisen.",
                        ephemeral=True,
                    )
                    return

        database.member_create(
            user_id=bewerber.id,
            charakter_name=charakter_name,
            rang=rang_nr,
            recruiter_id=int(row["maestro_id"]),
        )
        database.rang_log(bewerber.id, 0, rang_nr, "Annahme nach Bewerbung", interaction.user.id)
        database.bewerbung_set_status(self.bewerbung_id, "angenommen")

        try:
            new_row = database.bewerbung_get(self.bewerbung_id)
            maestro = await interaction.client.fetch_user(int(new_row["maestro_id"]))
            embed = build_dokument_embed(new_row, bewerber, maestro)
            for child in self.children:
                child.disabled = True
            await interaction.message.edit(
                content=f"✅ **ANGENOMMEN** — {bewerber.mention} ist nun **{rang_name(rang_nr)}**",
                embed=embed,
                view=self,
            )
        except Exception:
            pass

        try:
            await bewerber.send(
                f"🌵 **Willkommen im {config.KARTELL_NAME}**\n\n"
                f"Du wurdest als **{rang_name(rang_nr)}** aufgenommen.\n"
                f"Charakter: **{charakter_name}**\n"
                f"Server: **{config.SERVER_NAME}**\n\n"
                f"Probezeit: {config.PROBEZEIT_TAGE} Tage."
            )
        except discord.Forbidden:
            pass

        if config.CHANNEL_BENVENUTO:
            ch = interaction.client.get_channel(config.CHANNEL_BENVENUTO)
            if ch:
                welcome_embed = discord.Embed(
                    title=f"🎉 Benvenuto, {charakter_name}!",
                    description=f"{bewerber.mention} wurde als **{rang_name(rang_nr)}** ins {config.KARTELL_NAME} aufgenommen.\n\n*Que la familia te proteja.*",
                    color=config.EMBED_COLOR,
                )
                welcome_embed.set_thumbnail(url=bewerber.display_avatar.url)
                await ch.send(embed=welcome_embed)

        await interaction.response.send_message(
            f"✅ {bewerber.mention} angenommen als **{rang_name(rang_nr)}**.",
            ephemeral=True,
        )
        await log_action(interaction.client, f"✅ Bewerbung #{self.bewerbung_id} angenommen von {interaction.user.mention} — {bewerber.mention} ist {rang_name(rang_nr)}")

    @discord.ui.button(label="Ablehnen", style=discord.ButtonStyle.danger, emoji="❌", custom_id="bewerbung_reject")
    async def ablehnen(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not has_rang_in(interaction.user, config.RECRUITING_RANKS):
            erlaubte = ", ".join(rang_name(r) for r in config.RECRUITING_RANKS)
            await interaction.response.send_message(
                f"❌ Nur folgende Raenge: {erlaubte}", ephemeral=True,
            )
            return
        await interaction.response.send_modal(AblehnenModal(self.bewerbung_id))


class AblehnenModal(discord.ui.Modal, title="Bewerbung ablehnen"):
    grund = discord.ui.TextInput(
        label="Grund der Ablehnung",
        style=discord.TextStyle.paragraph, max_length=500, required=True,
    )

    def __init__(self, bewerbung_id: int):
        super().__init__()
        self.bewerbung_id = bewerbung_id

    async def on_submit(self, interaction: discord.Interaction):
        database.bewerbung_set_status(self.bewerbung_id, "abgelehnt")
        row = database.bewerbung_get(self.bewerbung_id)
        bewerber = interaction.guild.get_member(int(row["user_id"]))
        if bewerber:
            try:
                await bewerber.send(
                    f"❌ Deine Bewerbung beim **{config.KARTELL_NAME}** wurde abgelehnt.\n\n"
                    f"**Grund:** {self.grund.value}"
                )
            except discord.Forbidden:
                pass

        try:
            maestro = await interaction.client.fetch_user(int(row["maestro_id"]))
            user_obj = await interaction.client.fetch_user(int(row["user_id"]))
            embed = build_dokument_embed(database.bewerbung_get(self.bewerbung_id), user_obj, maestro)
            await interaction.message.edit(
                content=f"❌ **ABGELEHNT** — {user_obj.mention}\n**Grund:** {self.grund.value}",
                embed=embed,
                view=None,
            )
        except Exception:
            pass

        await interaction.response.send_message("❌ Bewerbung abgelehnt.", ephemeral=True)
        await log_action(interaction.client, f"❌ Bewerbung #{self.bewerbung_id} abgelehnt von {interaction.user.mention}")


# ---------- Cog ----------
class Bewerbung(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.add_view(AnnahmeView(0))  # persistent view

    group = app_commands.Group(name="bewerbung", description="Bewerbungs-System des Serrano Kartells")

    @group.command(name="start", description="Welle 1 starten — Maestro fuellt das Dokument aus")
    @app_commands.describe(bewerber="Der Bewerber im Discord")
    async def start(self, interaction: discord.Interaction, bewerber: discord.Member):
        if not has_rang_in(interaction.user, config.RECRUITING_RANKS):
            erlaubte = ", ".join(rang_name(r) for r in config.RECRUITING_RANKS)
            await interaction.response.send_message(
                f"❌ Nur folgende Raenge duerfen Bewerbungen starten: {erlaubte}",
                ephemeral=True,
            )
            return

        existing = database.bewerbung_get_active_by_user(bewerber.id)
        if existing:
            await interaction.response.send_message(
                f"⚠️ {bewerber.mention} hat bereits eine offene Bewerbung **#{existing['id']}** (Status: {existing['status']}).",
                ephemeral=True,
            )
            return

        await interaction.response.send_modal(Welle1Modal(self.bot, bewerber, interaction.user))

    @group.command(name="welle2", description="Welle 2 starten — Charakter-Tiefenpruefung")
    @app_commands.describe(bewerbung_id="Die ID der bestehenden Bewerbung")
    async def welle2(self, interaction: discord.Interaction, bewerbung_id: int):
        if not has_rang_in(interaction.user, config.RECRUITING_RANKS):
            await interaction.response.send_message("❌ Keine Berechtigung.", ephemeral=True)
            return

        row = database.bewerbung_get(bewerbung_id)
        if not row:
            await interaction.response.send_message(f"Bewerbung #{bewerbung_id} nicht gefunden.", ephemeral=True)
            return
        if row["status"] in ("angenommen", "abgelehnt"):
            await interaction.response.send_message(f"Bewerbung bereits {row['status']}.", ephemeral=True)
            return

        await interaction.response.send_modal(Welle2ModalA(self.bot, bewerbung_id))

    @group.command(name="liste", description="Alle Bewerbungen auflisten")
    @app_commands.describe(status="Filtern nach Status (optional)")
    @app_commands.choices(status=[
        app_commands.Choice(name="Welle 1 offen",  value="welle1_offen"),
        app_commands.Choice(name="Welle 2 offen",  value="welle2_offen"),
        app_commands.Choice(name="Angenommen",     value="angenommen"),
        app_commands.Choice(name="Abgelehnt",      value="abgelehnt"),
    ])
    async def liste(self, interaction: discord.Interaction, status: app_commands.Choice[str] = None):
        rows = database.bewerbung_list(status.value if status else None)
        if not rows:
            await interaction.response.send_message("Keine Bewerbungen gefunden.", ephemeral=True)
            return

        lines = []
        for r in rows[:25]:
            try:
                user = await interaction.client.fetch_user(int(r["user_id"]))
                user_str = user.display_name
            except Exception:
                user_str = r["user_id"]
            lines.append(f"`#{r['id']:>3}` · **{user_str}** · `{r['status']}` · {r['erstellt'][:10]}")

        embed = discord.Embed(
            title=f"📋 Bewerbungs-Uebersicht{' · ' + status.name if status else ''}",
            description="\n".join(lines),
            color=config.EMBED_COLOR,
        )
        embed.set_footer(text=f"{len(rows)} Bewerbung(en) gesamt")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @group.command(name="zeigen", description="Eine bestimmte Bewerbung anzeigen")
    @app_commands.describe(bewerbung_id="Die ID der Bewerbung")
    async def zeigen(self, interaction: discord.Interaction, bewerbung_id: int):
        row = database.bewerbung_get(bewerbung_id)
        if not row:
            await interaction.response.send_message("Nicht gefunden.", ephemeral=True)
            return
        bewerber = await interaction.client.fetch_user(int(row["user_id"]))
        maestro = await interaction.client.fetch_user(int(row["maestro_id"]))
        embed = build_dokument_embed(row, bewerber, maestro)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Bewerbung(bot))
