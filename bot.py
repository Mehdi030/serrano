"""
Serrano-Bot — Main Entry
Startet den Bot, lädt Cogs, syncht Slash-Commands.
"""
import os
import asyncio
import logging
import discord
from discord.ext import commands
from dotenv import load_dotenv

import database

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", "0"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("serrano")

intents = discord.Intents.default()
intents.members = True
intents.message_content = False

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    log.info(f"Eingeloggt als {bot.user} (ID {bot.user.id})")
    if GUILD_ID:
        guild = discord.Object(id=GUILD_ID)
        bot.tree.copy_global_to(guild=guild)
        synced = await bot.tree.sync(guild=guild)
        log.info(f"{len(synced)} Slash-Commands für Guild {GUILD_ID} gesynced")
    else:
        synced = await bot.tree.sync()
        log.info(f"{len(synced)} Slash-Commands global gesynced")


@bot.event
async def on_member_update(before, after):
    if before.roles != after.roles and database.member_exists(after.id):
        database.member_update_active(after.id)


@bot.event
async def on_message(message):
    if message.author.bot:
        return
    if database.member_exists(message.author.id):
        database.member_update_active(message.author.id)
    await bot.process_commands(message)


async def main():
    if not TOKEN:
        raise SystemExit("DISCORD_TOKEN fehlt in der .env Datei!")
    database.init_db()
    log.info("Datenbank initialisiert")

    async with bot:
        await bot.load_extension("cogs.bewerbung")
        await bot.load_extension("cogs.personal")
        await bot.load_extension("cogs.route")
        log.info("Cogs geladen")
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
