import os
import threading
from flask import Flask

import discord
from discord.ext import commands

app = Flask(__name__)

@app.route("/")
def home():
    return "Flower Registry Bot is online!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_web).start()

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash commands.")
    except Exception as e:
        print(e)

    print(f"Logged in as {bot.user}")


import commands_file

commands_file.setup(bot)

TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(TOKEN)
