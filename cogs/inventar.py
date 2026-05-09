"""
Inventar-, Kasse- und Abgaben-Verwaltung des Serrano Kartells

Berechtigungen: INVENTORY_RANKS (Contabile, Maestro, Vice Don, Don)
Lesen (bestand, stand, historie): alle Mitglieder.
"""
import discord
from discord import app_commands
from discord.ext import commands

import config
import database
from utils import has_rang_in, rang_name, log_action


def perm_check(interaction: discord.Interaction) -> tuple[bool, str]:
    if not has_rang_in(interaction.user, config.INVENTORY_RANKS):
        erlaubte = ", ".join(rang_name(r) for r in config.INVENTORY_RANKS)
        return False, f"❌ Nur folgende Ränge: {erlaubte}"
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


# ---------- Inventar Cog ----------
class Inventar(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    inv = app_commands.Group(name="inventar", description="Inventar-Verwaltung des Serrano Kartells")
    kasse = app_commands.Group(name="kasse", description="Kasse / Geldverlauf")
    abgabe = app_commands.Group(name="abgabe", description="Mitglieder-Abgaben (Tributi)")

    # ---------- /inventar neu ----------
    @inv.command(name="neu", description="Neues Item zur Liste hinzufügen")
    @app_commands.describe(
        name="Item-Name (z.B. Weed, Koks, Pistole)",
        kategorie="Kategorie (Droge / Waffe / Sonstiges)",
        einheit="Einheit (z.B. g, kg, Stück)",
    )
    async def inv_neu(self, interaction: discord.Interaction, name: str, kategorie: str, einheit: str = "Stück"):
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

    # ---------- /inventar ein ----------
    @inv.command(name="ein", description="Bestand erhöhen (Wareneingang)")
    @app_commands.describe(item="Item-Name", menge="Menge", grund="Grund (z.B. Produktion, Kauf)")
    async def inv_ein(self, interaction: discord.Interaction, item: str, menge: int, grund: str):
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

    # ---------- /inventar aus ----------
    @inv.command(name="aus", description="Bestand reduzieren (Warenausgang)")
    @app_commands.describe(item="Item-Name", menge="Menge", grund="Grund (z.B. Verkauf, Verbrauch)")
    async def inv_aus(self, interaction: discord.Interaction, item: str, menge: int, grund: str):
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

    # ========================================
    # ============ /kasse ====================
    # ========================================

    @kasse.command(name="ein", description="Geld in die Kasse einzahlen")
    @app_commands.describe(betrag="Betrag in $", grund="Grund (z.B. Verkauf, Tribut)")
    async def kasse_ein(self, interaction: discord.Interaction, betrag: int, grund: str):
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

    @kasse.command(name="aus", description="Geld aus der Kasse auszahlen")
    @app_commands.describe(betrag="Betrag in $", grund="Grund")
    async def kasse_aus(self, interaction: discord.Interaction, betrag: int, grund: str):
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
