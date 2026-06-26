import discord
from discord import app_commands

from database import (
    register_player,
    get_ign,
    claim_flower,
    get_registry
)


class Flower(app_commands.Group):
    def __init__(self):
        super().__init__(name="flower", description="Flower commands")

    @app_commands.command(name="claim", description="Claim one or more flowers")
    @app_commands.describe(flowers="Example: Red Lily, White Rose, Pincushion")
    async def claim(self, interaction: discord.Interaction, flowers: str):

        ign = get_ign(interaction.user.id)

        if ign is None:
            await interaction.response.send_message(
                "❌ Please register first using /register",
                ephemeral=True
            )
            return

        added = []
        failed = []

        flower_list = [f.strip() for f in flowers.split(",")]

        for flower in flower_list:

            success, owner = claim_flower(
                flower,
                ign,
                interaction.user.id
            )

            if success:
                added.append(flower)
            else:
                failed.append(f"{flower} — owned by {owner}")

        message = ""

        if added:
            message += "## ✅ Added\n"
            for flower in added:
                message += f"• {flower}\n"

        if failed:
            message += "\n## ❌ Already Owned\n"
            for flower in failed:
                message += f"• {flower}\n"

        await interaction.response.send_message(message)


    @app_commands.command(name="whohas", description="Find who owns a flower")
    async def whohas(self, interaction: discord.Interaction, flower: str):

        registry = get_registry()

        if flower not in registry:
            await interaction.response.send_message(
                "❌ Nobody owns that flower yet."
            )
            return

        owner = registry[flower]["owner"]

        await interaction.response.send_message(
            f"🌸 **{flower}** → **{owner}**"
        )


def setup(bot):

    bot.tree.add_command(Flower())

    @bot.tree.command(name="register", description="Register your in-game name")
    async def register(interaction: discord.Interaction, ign: str):

        register_player(
            interaction.user.id,
            ign
        )

        await interaction.response.send_message(
            f"✅ Registered as **{ign}**",
            ephemeral=True
        )

    @bot.tree.command(name="ping", description="Ping")
    async def ping(interaction: discord.Interaction):

        await interaction.response.send_message(
            "🏓 Pong!",
            ephemeral=True
        )
