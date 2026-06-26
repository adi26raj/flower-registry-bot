import discord
from discord import app_commands

from database import (
    get_players,
    save_players,
    get_registry,
    save_registry,
    player_ign
)

def setup(bot):

    @bot.tree.command(name="register", description="Register your in-game name")
    @app_commands.describe(ign="Your in-game name")
    async def register(interaction: discord.Interaction, ign: str):

        players = get_players()

        players[str(interaction.user.id)] = {
            "ign": ign
        }

        save_players(players)

        await interaction.response.send_message(
            f"✅ Your IGN has been registered as **{ign}**.",
            ephemeral=True
        )

    @bot.tree.command(name="ping", description="Check if the bot is online")
    async def ping(interaction: discord.Interaction):

        await interaction.response.send_message(
            "🏓 Pong!",
            ephemeral=True
        )
