"""
Inventar-, Kasse- und Abgaben-Verwaltung des Serrano Kartells

Berechtigungen: INVENTORY_RANKS (Contabile, Maestro, Vice Don, Don)
Lesen (bestand, stand, historie): alle Mitglieder.

Live-Dashboard:
  Eine persistente Nachricht in #Bestand zeigt den kompletten Lagerbestand,
  Kassenstand, letzte Bewegung. Aktualisiert sich automatisch bei jeder
  Inventar-/Kasse-Aktion. Befehle in #Bestand werden abgelehnt.
"""
from datetime import datetime
import discord
from discord import app_commands
from discord.ext import commands

import config
import database
from utils import has_rang_in, rang_name, log_action


KATEGORIE_EMOJI = {
    "droge":      "🌿",
    "drogen":     "🌿",
    "waffe":      "🔫",
    "waffen":     "🔫",
    "munition":   "🎯",
    "fahrzeug":   "🚗",
    "fahrzeuge":  "🚗",
    "geld":       "💰",
    "sonstiges":  "📦",
}


def perm_check(interaction: discord.Interaction) -> tuple[bool, str]:
    if not has_rang_in(interaction.user, config.INVENTORY_RANKS):
        erlaubte = ", ".join(rang_name(r) for r in config.INVENTORY_RANKS)
        return False, f"❌ Nur folgende Ränge: {erlaubte}"
    return True, ""


def channel_check(interaction: discord.Interaction) -> tuple[bool, str]:
    """Lehnt Befehle in #Bestand ab — dort soll nur das Live-Dashboard sein."""
    if config.CHANNEL_BESTAND and interaction.channel and interaction.channel.id == config.CHANNEL_BESTAND:
        return False, (
            f"❌ Bitte nicht in <#{config.CHANNEL_BESTAND}> ausführen.\n"
            f"Dort ist nur das Live-Dashboard. Nutze einen anderen Channel für Befehle."
        )
    return True, ""


async def auto_post(bot: commands.Bot, channel_id: int, content: str = None, embed: discord.Embed = None):
    if not channel_id:
        return
    ch = bot.get_channel(channel_id)
    if ch:
        try:
            await ch.send(content=content, embed=embed)
        except Exception:
            pass


def fmt_money(betrag: int) -> str:
    return f"{betrag:,}".replace(",", ".") + " $"


def format_relative_time(iso_ts: str) -> str:
    """'vor 2 Min', 'vor 3 Std', 'vor 5 Tagen'."""
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


def build_inventar_dashboard_embed() -> discord.Embed:
    """Live-Dashboard für #Bestand. Wird bei jeder Aktion aktualisiert."""
    items = database.inv_item_list()
    kasse_stand = database.kasse_stand()
    last = database.inv_last_log()

    embed = discord.Embed(
        title=f"🌵 Lagerbestand · {config.KARTELL_NAME}",
        description="*Live-Übersicht — aktualisiert sich automatisch*",
        color=config.EMBED_COLOR,
    )

    if not items:
        embed.add_field(
            name="📦 Lager",
            value="*Noch keine Items registriert.*\nNutze `/inventar neu` zum Anlegen.",
            inline=False,
        )
    else:
        kategorien = {}
        for it in items:
            kat = (it["kategorie"] or "Sonstiges").strip()
            kategorien.setdefault(kat, []).append(it)

        for kat, lst in sorted(kategorien.items()):
            emoji = KATEGORIE_EMOJI.get(kat.lower(), "📦")
            text = "\n".join(
                f"`{i['bestand']:>6}` {i['einheit']}  ·  **{i['name']}**"
                for i in sorted(lst, key=lambda x: -x["bestand"])
            )
            embed.add_field(name=f"{emoji} {kat}", value=text, inline=False)

    # Kasse
    embed.add_field(name="💼 Kasse", value=f"**{fmt_money(kasse_stand)}**", inline=True)

    # Item-Anzahl
    embed.add_field(name="📊 Item-Arten", value=str(len(items)), inline=True)

    # Letzte Bewegung
    if last:
        zeichen = "📥 +" if last["aktion"] == "ein" else "📤 -"
        rel = format_relative_time(last["timestamp"])
        embed.add_field(
            name="🕒 Letzte Bewegung",
            value=f"{zeichen}{last['menge']} {last['einheit']} **{last['item_name']}**\n"
                  f"<@{last['member_id']}> · {rel}\n*Grund: {last['grund']}*",
            inline=False,
        )

    embed.set_footer(text=f"🔄 Live-Update aktiv  ·  Stand: {datetime.utcnow().strftime('%d.%m.%Y %H:%M')} UTC")
    return embed


async def update_inventar_dashboard(bot: commands.Bot):
    """Aktualisiert die persistente Dashboard-Message. Stillschweigend wenn nicht gesetzt."""
    msg_id = database.state_get("inv_dashboard_msg_id")
    ch_id = database.state_get("inv_dashboard_ch_id")
    if not msg_id or not ch_id:
        return False

    ch = bot.get_channel(int(ch_id))
    if not ch:
        return False

    try:
        msg = await ch.fetch_message(int(msg_id))
        await msg.edit(embed=build_inventar_dashboard_embed())
        return True
    except discord.NotFound:
        # Message wurde geloescht
        database.state_set("inv_dashboard_msg_id", None)
        database.state_set("inv_dashboard_ch_id", None)
        return False
    except Exception:
        return False


# ---------- Inventar Cog ----------
class Inventar(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    inv = app_commands.Group(name="inventar", description="Inventar-Verwaltung des Serrano Kartells")
    kasse = app_commands.Group(name="kasse", description="Kasse / Geldverlauf")
    abgabe = app_commands.Group(name="abgabe", description="Mitglieder-Abgaben (Tributi)")

    # ---------- /inventar dashboard ----------
    @inv.command(name="dashboard", description="Live-Dashboard in #Bestand aufstellen oder neu generieren")
    async def inv_dashboard(self, interaction: discord.Interaction):
        ok, err = perm_check(interaction)
        if not ok:
            await interaction.response.send_message(err, ephemeral=True)
            return

        if not config.CHANNEL_BESTAND:
            await interaction.response.send_message(
                "❌ `CHANNEL_BESTAND` ist in `config.py` nicht gesetzt. "
                "Trag die ID des Bestand-Channels ein, dann nochmal versuchen.",
                ephemeral=True,
            )
            return

        ch = self.bot.get_channel(config.CHANNEL_BESTAND)
        if not ch:
            await interaction.response.send_message(
                "❌ Bestand-Channel nicht gefunden. Prüf die ID in der Config.",
                ephemeral=True,
            )
            return

        # Alten Dashboard-Post (falls existiert) löschen
        old_msg_id = database.state_get("inv_dashboard_msg_id")
        old_ch_id = database.state_get("inv_dashboard_ch_id")
        if old_msg_id and old_ch_id:
            try:
                old_ch = self.bot.get_channel(int(old_ch_id))
                if old_ch:
                    old_msg = await old_ch.fetch_message(int(old_msg_id))
                    await old_msg.delete()
            except Exception:
                pass

        # Neuen Dashboard-Post anlegen
        embed = build_inventar_dashboard_embed()
        msg = await ch.send(embed=embed)
        database.state_set("inv_dashboard_msg_id", msg.id)
        database.state_set("inv_dashboard_ch_id", ch.id)

        await interaction.response.send_message(
            f"✅ Live-Dashboard in <#{ch.id}> aufgestellt.\n"
            f"Es aktualisiert sich automatisch bei jeder Inventar-/Kasse-Aktion.\n\n"
            f"**Tipp:** Setz die Channel-Berechtigung von <#{ch.id}> so dass nur der Bot dort schreiben darf.",
            ephemeral=True,
        )
        await log_action(self.bot, f"🆕 Inventar-Live-Dashboard aufgestellt in <#{ch.id}> von {interaction.user.mention}")

    # ---------- /inventar neu ----------
    @inv.command(name="neu", description="Neues Item zur Liste hinzufügen")
    @app_commands.describe(
        name="Item-Name (z.B. Weed, Koks, Pistole)",
        kategorie="Kategorie (Droge / Waffe / Sonstiges)",
        einheit="Einheit (z.B. g, kg, Stück)",
    )
    async def inv_neu(self, interaction: discord.Interaction, name: str, kategorie: str, einheit: str = "Stück"):
        ch_ok, ch_err = channel_check(interaction)
        if not ch_ok:
            await interaction.response.send_message(ch_err, ephemeral=True)
            return
        ok, err = perm_check(interaction)
        if not ok:
            await interaction.response.send_message(err, ephemeral=True)
            return

        if database.inv_item_get(name):
            await interaction.response.send_message(f"⚠️ Item **{name}** existiert bereits.", ephemeral=True)
            return

        item_id = database.inv_item_create(name, kategorie, einheit)
        await interaction.response.send_message(
            f"✅ Item **{name}** (#{item_id}, {kategorie}, in {einheit}) angelegt.",
        )
        await log_action(self.bot, f"📦 Inventar: Item '{name}' angelegt von {interaction.user.mention}")
        await update_inventar_dashboard(self.bot)

    # ---------- /inventar ein ----------
    @inv.command(name="ein", description="Bestand erhöhen (Wareneingang)")
    @app_commands.describe(item="Item-Name", menge="Menge", grund="Grund (z.B. Produktion, Kauf)")
    async def inv_ein(self, interaction: discord.Interaction, item: str, menge: int, grund: str):
        ch_ok, ch_err = channel_check(interaction)
        if not ch_ok:
            await interaction.response.send_message(ch_err, ephemeral=True)
            return
        ok, err = perm_check(interaction)
        if not ok:
            await interaction.response.send_message(err, ephemeral=True)
            return
        if menge <= 0:
            await interaction.response.send_message("❌ Menge muss positiv sein.", ephemeral=True)
            return

        row = database.inv_item_get(item)
        if not row:
            await interaction.response.send_message(
                f"❌ Item **{item}** nicht gefunden. Erst mit `/inventar neu` anlegen.",
                ephemeral=True,
            )
            return

        database.inv_buchen(row["id"], "ein", menge, grund, interaction.user.id)
        neuer_bestand = row["bestand"] + menge

        embed = discord.Embed(
            title=f"📥 Wareneingang: {row['name']}",
            description=f"**+{menge} {row['einheit']}** durch {interaction.user.mention}\n**Grund:** {grund}",
            color=0x2ECC71,
        )
        embed.add_field(name="Neuer Bestand", value=f"**{neuer_bestand} {row['einheit']}**")
        embed.set_footer(text=f"{config.KARTELL_NAME}")
        await interaction.response.send_message(embed=embed)
        await auto_post(self.bot, config.CHANNEL_LAGERVERLAUF, embed=embed)
        await log_action(self.bot, f"📥 +{menge} {row['einheit']} {row['name']} ({grund}) — {interaction.user.mention}")
        await update_inventar_dashboard(self.bot)

    # ---------- /inventar aus ----------
    @inv.command(name="aus", description="Bestand reduzieren (Warenausgang)")
    @app_commands.describe(item="Item-Name", menge="Menge", grund="Grund (z.B. Verkauf, Verbrauch)")
    async def inv_aus(self, interaction: discord.Interaction, item: str, menge: int, grund: str):
        ch_ok, ch_err = channel_check(interaction)
        if not ch_ok:
            await interaction.response.send_message(ch_err, ephemeral=True)
            return
        ok, err = perm_check(interaction)
        if not ok:
            await interaction.response.send_message(err, ephemeral=True)
            return
        if menge <= 0:
            await interaction.response.send_message("❌ Menge muss positiv sein.", ephemeral=True)
            return

        row = database.inv_item_get(item)
        if not row:
            await interaction.response.send_message(f"❌ Item **{item}** nicht gefunden.", ephemeral=True)
            return
        if row["bestand"] < menge:
            await interaction.response.send_message(
                f"❌ Nicht genug Bestand. Verfügbar: **{row['bestand']} {row['einheit']}**, "
                f"angefordert: **{menge}**.",
                ephemeral=True,
            )
            return

        database.inv_buchen(row["id"], "aus", menge, grund, interaction.user.id)
        neuer_bestand = row["bestand"] - menge

        embed = discord.Embed(
            title=f"📤 Warenausgang: {row['name']}",
            description=f"**-{menge} {row['einheit']}** durch {interaction.user.mention}\n**Grund:** {grund}",
            color=0xE74C3C,
        )
        embed.add_field(name="Neuer Bestand", value=f"**{neuer_bestand} {row['einheit']}**")
        embed.set_footer(text=f"{config.KARTELL_NAME}")
        await interaction.response.send_message(embed=embed)
        await auto_post(self.bot, config.CHANNEL_LAGERVERLAUF, embed=embed)
        await log_action(self.bot, f"📤 -{menge} {row['einheit']} {row['name']} ({grund}) — {interaction.user.mention}")
        await update_inventar_dashboard(self.bot)

    # ---------- /inventar bestand ----------
    @inv.command(name="bestand", description="Kompletter Lagerbestand")
    async def inv_bestand(self, interaction: discord.Interaction):
        items = database.inv_item_list()
        if not items:
            await interaction.response.send_message("Lager ist leer. Mit `/inventar neu` Items anlegen.", ephemeral=True)
            return

        kategorien = {}
        for item in items:
            kat = item["kategorie"] or "Sonstiges"
            kategorien.setdefault(kat, []).append(item)

        embed = discord.Embed(title="📦 Lagerbestand", color=config.EMBED_COLOR)
        for kat, lst in kategorien.items():
            text = "\n".join(f"• **{i['name']}**: {i['bestand']} {i['einheit']}" for i in lst)
            embed.add_field(name=f"━ {kat} ━", value=text, inline=False)
        embed.set_footer(text=f"{config.KARTELL_NAME} · {len(items)} Item(s)")
        await interaction.response.send_message(embed=embed)
        await auto_post(self.bot, config.CHANNEL_BESTAND, embed=embed)

    # ---------- /inventar historie ----------
    @inv.command(name="historie", description="Letzte Bewegungen anzeigen")
    @app_commands.describe(item="Optional: nur ein bestimmtes Item")
    async def inv_historie(self, interaction: discord.Interaction, item: str = None):
        item_id = None
        if item:
            row = database.inv_item_get(item)
            if not row:
                await interaction.response.send_message(f"❌ Item **{item}** nicht gefunden.", ephemeral=True)
                return
            item_id = row["id"]

        rows = database.inv_log(item_id, limit=15)
        if not rows:
            await interaction.response.send_message("Keine Bewegungen gefunden.", ephemeral=True)
            return

        lines = []
        for r in rows:
            zeichen = "📥 +" if r["aktion"] == "ein" else "📤 -"
            lines.append(
                f"{zeichen}{r['menge']} **{r['item_name']}** · {r['grund']} · "
                f"<@{r['member_id']}> · `{r['timestamp'][:16].replace('T', ' ')}`"
            )

        embed = discord.Embed(
            title=f"📋 Inventar-Historie{' · ' + item if item else ''}",
            description="\n".join(lines),
            color=config.EMBED_COLOR,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ---------- /inventar entfernen ----------
    @inv.command(name="entfernen", description="Item komplett aus dem System löschen")
    @app_commands.describe(item="Item-Name")
    async def inv_entfernen(self, interaction: discord.Interaction, item: str):
        ch_ok, ch_err = channel_check(interaction)
        if not ch_ok:
            await interaction.response.send_message(ch_err, ephemeral=True)
            return
        ok, err = perm_check(interaction)
        if not ok:
            await interaction.response.send_message(err, ephemeral=True)
            return
        row = database.inv_item_get(item)
        if not row:
            await interaction.response.send_message(f"❌ Item **{item}** nicht gefunden.", ephemeral=True)
            return
        database.inv_item_delete(row["id"])
        await interaction.response.send_message(f"🗑️ Item **{item}** komplett gelöscht.")
        await log_action(self.bot, f"🗑️ Inventar: Item '{item}' gelöscht von {interaction.user.mention}")
        await update_inventar_dashboard(self.bot)

    # ========================================
    # ============ /kasse ====================
    # ========================================

    @kasse.command(name="ein", description="Geld in die Kasse einzahlen")
    @app_commands.describe(betrag="Betrag in $", grund="Grund (z.B. Verkauf, Tribut)")
    async def kasse_ein(self, interaction: discord.Interaction, betrag: int, grund: str):
        ch_ok, ch_err = channel_check(interaction)
        if not ch_ok:
            await interaction.response.send_message(ch_err, ephemeral=True)
            return
        ok, err = perm_check(interaction)
        if not ok:
            await interaction.response.send_message(err, ephemeral=True)
            return
        if betrag <= 0:
            await interaction.response.send_message("❌ Betrag muss positiv sein.", ephemeral=True)
            return

        database.kasse_buchen("ein", betrag, grund, interaction.user.id)
        stand = database.kasse_stand()

        embed = discord.Embed(
            title="💰 Kasseneingang",
            description=f"**+{fmt_money(betrag)}** durch {interaction.user.mention}\n**Grund:** {grund}",
            color=0x2ECC71,
        )
        embed.add_field(name="Neuer Kassenstand", value=f"**{fmt_money(stand)}**")
        await interaction.response.send_message(embed=embed)
        await auto_post(self.bot, config.CHANNEL_GELDVERLAUF, embed=embed)
        await log_action(self.bot, f"💰 Kasse +{fmt_money(betrag)} ({grund}) — {interaction.user.mention}")
        await update_inventar_dashboard(self.bot)

    @kasse.command(name="aus", description="Geld aus der Kasse auszahlen")
    @app_commands.describe(betrag="Betrag in $", grund="Grund")
    async def kasse_aus(self, interaction: discord.Interaction, betrag: int, grund: str):
        ch_ok, ch_err = channel_check(interaction)
        if not ch_ok:
            await interaction.response.send_message(ch_err, ephemeral=True)
            return
        ok, err = perm_check(interaction)
        if not ok:
            await interaction.response.send_message(err, ephemeral=True)
            return
        if betrag <= 0:
            await interaction.response.send_message("❌ Betrag muss positiv sein.", ephemeral=True)
            return

        stand = database.kasse_stand()
        if betrag > stand:
            await interaction.response.send_message(
                f"❌ Nicht genug in der Kasse. Aktuell: **{fmt_money(stand)}**.",
                ephemeral=True,
            )
            return

        database.kasse_buchen("aus", betrag, grund, interaction.user.id)
        neuer_stand = stand - betrag

        embed = discord.Embed(
            title="💸 Kassenausgang",
            description=f"**-{fmt_money(betrag)}** durch {interaction.user.mention}\n**Grund:** {grund}",
            color=0xE74C3C,
        )
        embed.add_field(name="Neuer Kassenstand", value=f"**{fmt_money(neuer_stand)}**")
        await interaction.response.send_message(embed=embed)
        await auto_post(self.bot, config.CHANNEL_GELDVERLAUF, embed=embed)
        await log_action(self.bot, f"💸 Kasse -{fmt_money(betrag)} ({grund}) — {interaction.user.mention}")
        await update_inventar_dashboard(self.bot)

    @kasse.command(name="stand", description="Aktueller Kassenstand")
    async def kasse_stand_cmd(self, interaction: discord.Interaction):
        stand = database.kasse_stand()
        embed = discord.Embed(
            title="💼 Kassenstand",
            description=f"**{fmt_money(stand)}**",
            color=config.EMBED_COLOR,
        )
        await interaction.response.send_message(embed=embed)

    @kasse.command(name="historie", description="Letzte Kassen-Bewegungen")
    async def kasse_historie(self, interaction: discord.Interaction):
        rows = database.kasse_log(limit=15)
        if not rows:
            await interaction.response.send_message("Keine Bewegungen.", ephemeral=True)
            return
        lines = []
        for r in rows:
            zeichen = "💰 +" if r["aktion"] == "ein" else "💸 -"
            lines.append(
                f"{zeichen}{fmt_money(r['betrag'])} · {r['grund']} · "
                f"<@{r['member_id']}> · `{r['timestamp'][:16].replace('T', ' ')}`"
            )
        embed = discord.Embed(title="📋 Kasse-Historie", description="\n".join(lines), color=config.EMBED_COLOR)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ========================================
    # ============ /abgabe ===================
    # ========================================

    @abgabe.command(name="verbuchen", description="Abgabe (Tribut) eines Mitglieds verbuchen")
    @app_commands.describe(user="Mitglied", betrag="Betrag in $", notiz="Notiz (z.B. Wochen-Tribut)")
    async def abgabe_verbuchen(self, interaction: discord.Interaction, user: discord.Member, betrag: int, notiz: str = "—"):
        ch_ok, ch_err = channel_check(interaction)
        if not ch_ok:
            await interaction.response.send_message(ch_err, ephemeral=True)
            return
        ok, err = perm_check(interaction)
        if not ok:
            await interaction.response.send_message(err, ephemeral=True)
            return
        if betrag <= 0:
            await interaction.response.send_message("❌ Betrag muss positiv sein.", ephemeral=True)
            return

        database.abgabe_add(user.id, betrag, notiz, interaction.user.id)
        # Geld geht automatisch in Kasse
        database.kasse_buchen("ein", betrag, f"Abgabe von {user.display_name}: {notiz}", interaction.user.id)
        total = database.abgabe_total(user.id)

        embed = discord.Embed(
            title="📝 Abgabe verbucht",
            description=f"{user.mention} hat **{fmt_money(betrag)}** abgegeben.\n**Notiz:** {notiz}",
            color=config.EMBED_COLOR,
        )
        embed.add_field(name="Gesamt-Abgaben dieses Mitglieds", value=f"**{fmt_money(total)}**")
        embed.set_footer(text=f"Erfasst von {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed)
        await auto_post(self.bot, config.CHANNEL_ABGABEN, embed=embed)
        await log_action(self.bot, f"📝 Abgabe: {user.mention} {fmt_money(betrag)} ({notiz}) — erfasst von {interaction.user.mention}")
        await update_inventar_dashboard(self.bot)

    @abgabe.command(name="historie", description="Abgaben eines Mitglieds")
    @app_commands.describe(user="Mitglied")
    async def abgabe_historie(self, interaction: discord.Interaction, user: discord.Member):
        rows = database.abgabe_list(user.id)
        if not rows:
            await interaction.response.send_message(f"Keine Abgaben für {user.mention}.", ephemeral=True)
            return
        total = database.abgabe_total(user.id)
        lines = [
            f"• `{r['timestamp'][:10]}` **{fmt_money(r['betrag'])}** — {r['notiz']}"
            for r in rows[:15]
        ]
        embed = discord.Embed(
            title=f"📊 Abgaben-Historie — {user.display_name}",
            description="\n".join(lines),
            color=config.EMBED_COLOR,
        )
        embed.add_field(name="Gesamt", value=f"**{fmt_money(total)}** in {len(rows)} Zahlung(en)")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @abgabe.command(name="top", description="Top-Zahler des Kartells")
    async def abgabe_top_cmd(self, interaction: discord.Interaction):
        rows = database.abgabe_top(limit=10)
        if not rows:
            await interaction.response.send_message("Noch keine Abgaben verbucht.", ephemeral=True)
            return
        lines = []
        for i, r in enumerate(rows, 1):
            medal = ["🥇", "🥈", "🥉"][i-1] if i <= 3 else f"`#{i}`"
            lines.append(f"{medal} <@{r['user_id']}> — **{fmt_money(r['total'])}** ({r['anzahl']} Zahlungen)")
        embed = discord.Embed(
            title="🏆 Top-Zahler",
            description="\n".join(lines),
            color=config.EMBED_COLOR,
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Inventar(bot))
