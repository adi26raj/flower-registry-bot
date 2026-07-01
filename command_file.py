```python
from __future__ import annotations

import asyncio
import traceback
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

from database import JSONStorage, ValidationError, DatabaseError

# ---------------------------------------------------------------------------
# Helper to delete messages after a delay
# ---------------------------------------------------------------------------
async def _delete_after(delay: float, message: discord.Message) -> None:
    """Delete `message` after `delay` seconds, ignoring errors."""
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
        pass


# ---------------------------------------------------------------------------
# Cog
# ---------------------------------------------------------------------------
class FlowerCog(commands.Cog):
    """Flower Registry bot – slash command implementation."""

    def __init__(self, bot: commands.Bot, storage: JSONStorage) -> None:
        self.bot = bot
        self.storage = storage

    # -----------------------------------------------------------------------
    # Autocomplete callbacks (static – accessible by all commands)
    # -----------------------------------------------------------------------
    @staticmethod
    async def flower_autocomplete(
        interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        """Provide case‑insensitive, sorted flower name suggestions (max 25)."""
        cog = interaction.client.get_cog("FlowerCog")
        if cog is None:
            return []
        flower_names = cog.storage.loadflowers().keys()
        if current:
            matches = [n for n in flower_names if n.lower().startswith(current.lower())]
        else:
            matches = list(flower_names)
        sorted_matches = sorted(matches, key=str.casefold)[:25]
        return [app_commands.Choice(name=name, value=name) for name in sorted_matches]

    @staticmethod
    async def ign_autocomplete(
        interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        """Provide case‑insensitive, sorted IGN suggestions (max 25)."""
        cog = interaction.client.get_cog("FlowerCog")
        if cog is None:
            return []
        igns = cog.storage.getallregisteredigns()  # already sorted case‑fold
        if current:
            matches = [i for i in igns if i.lower().startswith(current.lower())]
        else:
            matches = list(igns)
        sorted_matches = sorted(matches, key=str.casefold)[:25]
        return [app_commands.Choice(name=ign, value=ign) for ign in sorted_matches]

    # -----------------------------------------------------------------------
    # Utilities
    # -----------------------------------------------------------------------
    async def _is_manager(self, interaction: discord.Interaction) -> bool:
        """Return True if the user has the configured manager role."""
        config = self.storage.loadconfig()
        role_id = config.get("managerroleid")
        if role_id is None:
            await interaction.response.send_message(
                "Manager role is not configured. Ask an admin to use `/setup manager_role`.",
                ephemeral=True,
            )
            return False
        role = interaction.guild.get_role(role_id)  # type: ignore[union-attr]
        if role is None or role not in interaction.user.roles:  # type: ignore[union-attr]
            await interaction.response.send_message(
                "You do not have permission to use manager commands.", ephemeral=True
            )
            return False
        return True

    async def _send_response(
        self,
        interaction: discord.Interaction,
        content: str | None = None,
        embed: discord.Embed | None = None,
        *,
        ephemeral: bool = False,
        delete_after: int = 600,
    ) -> None:
        """
        Send a response that may auto‑delete.
        Handles both initial responses and follow‑ups correctly.
        """
        if ephemeral:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    content=content, embed=embed, ephemeral=True
                )
            else:
                await interaction.followup.send(content=content, embed=embed, ephemeral=True)
            return

        # Non‑ephemeral
        if not interaction.response.is_done():
            await interaction.response.send_message(content=content, embed=embed)
            msg = await interaction.original_response()
            self.bot.loop.create_task(_delete_after(delete_after, msg))
        else:
            msg = await interaction.followup.send(content=content, embed=embed)
            self.bot.loop.create_task(_delete_after(delete_after, msg))

    @staticmethod
    def _flower_range_index(flower_name: str) -> int:
        """Map a flower name to one of the four registry message slots (0‑3)."""
        first = flower_name[0].lower() if flower_name else "a"
        if "a" <= first <= "f":
            return 0
        if "g" <= first <= "m":
            return 1
        if "n" <= first <= "s":
            return 2
        return 3  # t‑z and everything else

    def _build_range_content(self, index: int, registry: dict[str, dict[str, Any]]) -> str:
        """Format one of the four registry messages."""
        ranges = [("a", "f"), ("g", "m"), ("n", "s"), ("t", "z")]
        start, end = ranges[index]

        lines: list[str] = []
        # Collect flowers that belong in this alphabetical range.
        for flower_name, data in registry.items():
            first = flower_name[0].lower() if flower_name else "a"
            if start <= first <= end:
                rarity_emoji = data["rarity"].split()[0]  # e.g. "🔴"
                owners_str = ", ".join(data["owners"]) if data["owners"] else "Nobody"
                lines.append(f"{rarity_emoji} {flower_name} — {owners_str}")

        if not lines:
            return "No flowers in this range."
        # Already sorted because registry is built from a sorted dict.
        return "\n".join(lines)

    async def _init_registry_messages(self, channel: discord.TextChannel) -> None:
        """Create the four registry messages and save their IDs."""
        config = self.storage.loadconfig()
        # Delete previous registry messages if any.
        old_ids = config.get("registrymessageids", [])
        for mid in old_ids:
            try:
                msg = await channel.fetch_message(mid)
                await msg.delete()
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass

        registry = self.storage.getfullregistry()
        new_ids = []
        for i in range(4):
            content = self._build_range_content(i, registry)
            msg = await channel.send(content)
            new_ids.append(msg.id)

        self.storage.setregistrymessageids(new_ids)

    async def _update_registry_message(self, index: int) -> None:
        """Edit the registry message at `index` to reflect current data."""
        config = self.storage.loadconfig()
        msg_ids = config.get("registrymessageids", [])
        if len(msg_ids) != 4:
            return  # Registry messages not yet initialized

        channel_id = config.get("registrychannelid")
        if channel_id is None:
            return
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            return

        try:
            message = await channel.fetch_message(msg_ids[index])  # type: ignore[union-attr]
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return

        registry = self.storage.getfullregistry()
        new_content = self._build_range_content(index, registry)
        await message.edit(content=new_content)

    async def _update_all_registry_messages(self) -> None:
        """Refresh all four registry messages (e.g. after an IGN change)."""
        for idx in range(4):
            await self._update_registry_message(idx)

    # -----------------------------------------------------------------------
    # Global checks & error handling
    # -----------------------------------------------------------------------
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Enforce command channel (except for `/setup` commands)."""
        if not interaction.guild:
            await interaction.response.send_message("Commands only work in servers.", ephemeral=True)
            return False

        # Setup commands are special – do not require command channel,
        # and bootstrap by allowing ANY user if no manager role is configured.
        if interaction.command and interaction.command.name.startswith("setup"):
            config = self.storage.loadconfig()
            if config.get("managerroleid") is None:
                return True  # bootstrap – anyone can run setup until a manager role exists
            return await self._is_manager(interaction)

        config = self.storage.loadconfig()
        cmd_channel_id = config.get("commandschannelid")
        if cmd_channel_id is not None and interaction.channel_id != cmd_channel_id:
            channel = interaction.guild.get_channel(cmd_channel_id)
            mention = channel.mention if channel else f"<#{cmd_channel_id}>"
            await interaction.response.send_message(
                f"Please use commands in {mention}.", ephemeral=True
            )
            return False
        return True

    @commands.Cog.listener()
    async def on_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        """Catch known errors and respond gracefully."""
        if isinstance(error, app_commands.CheckFailure):
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    str(error) or "You cannot use this command here.", ephemeral=True
                )
            # else: response already sent by the check, do nothing
            return

        if isinstance(error, (ValidationError, DatabaseError)):
            msg = str(error)
        else:
            # Log unexpected errors; show a generic message.
            traceback.print_exception(type(error), error, error.__traceback__)
            msg = "An unexpected error occurred. Please try again later."

        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)

    # -----------------------------------------------------------------------
    # /register
    # -----------------------------------------------------------------------
    @app_commands.command(name="register", description="Register your in‑game name (IGN)")
    @app_commands.describe(ign="Your IGN")
    async def register(self, interaction: discord.Interaction, ign: str) -> None:
        """Register a player."""
        self.storage.registerplayer(interaction.user.id, ign)  # raises ValidationError if IGN empty
        await interaction.response.send_message(f"Registered as **{ign}**.", ephemeral=True)

    # -----------------------------------------------------------------------
    # /flower claim
    # -----------------------------------------------------------------------
    flower_group = app_commands.Group(name="flower", description="Flower commands")

    @flower_group.command(name="claim", description="Claim 1–5 flowers")
    @app_commands.describe(
        flower1="Flower name (required)",
        flower2="Optional second flower",
        flower3="Optional third flower",
        flower4="Optional fourth flower",
        flower5="Optional fifth flower",
    )
    @app_commands.autocomplete(
        flower1=flower_autocomplete,
        flower2=flower_autocomplete,
        flower3=flower_autocomplete,
        flower4=flower_autocomplete,
        flower5=flower_autocomplete,
    )
    async def flower_claim(
        self,
        interaction: discord.Interaction,
        flower1: str,
        flower2: str | None = None,
        flower3: str | None = None,
        flower4: str | None = None,
        flower5: str | None = None,
    ) -> None:
        """Claim 1–5 flowers (duplicates ignored)."""
        ign = self.storage.getplayerign(interaction.user.id)
        if ign is None:
            await interaction.response.send_message(
                "You are not registered. Use `/register` first.", ephemeral=True
            )
            return

        # Collect non‑empty, deduplicated flower names in the order provided
        raw_flowers = [flower1, flower2, flower3, flower4, flower5]
        seen = set()
        flower_names = []
        for f in raw_flowers:
            if f and f.strip():
                name = f.strip()
                if name not in seen:
                    seen.add(name)
                    flower_names.append(name)

        if not flower_names:
            await interaction.response.send_message(
                "Provide at least one flower name.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=False)

        try:
            result = self.storage.claimflowers(ign, flower_names)
        except ValidationError as e:
            await self._send_response(interaction, content=str(e))
            return

        parts = []
        if result["added"]:
            parts.append(f"✅ Claimed: {', '.join(result['added'])}")
        if result["alreadyowned"]:
            parts.append(f"⚠️ Already owned: {', '.join(result['alreadyowned'])}")
        if result["missing"]:
            parts.append(f"❌ Not found: {', '.join(result['missing'])}")
        content = "\n".join(parts) if parts else "No flowers to claim."

        await self._send_response(interaction, content=content)

        # Update only the registry messages that changed
        affected = {self._flower_range_index(f) for f in result["added"]}
        for idx in affected:
            await self._update_registry_message(idx)

    # -----------------------------------------------------------------------
    # /flower whohas
    # -----------------------------------------------------------------------
    @flower_group.command(name="whohas", description="Find out who owns a flower")
    @app_commands.describe(flower="Flower name")
    @app_commands.autocomplete(flower=flower_autocomplete)
    async def flower_whohas(self, interaction: discord.Interaction, flower: str) -> None:
        """Look up a flower's owners and post the result in the lookup channel."""
        config = self.storage.loadconfig()
        lookup_channel_id = config.get("lookupchannelid")
        if lookup_channel_id is None:
            await interaction.response.send_message(
                "The lookup channel is not set. Use `/setup lookup_channel`.", ephemeral=True
            )
            return

        lookup_channel = self.bot.get_channel(lookup_channel_id)
        if lookup_channel is None:
            await interaction.response.send_message("Lookup channel not found.", ephemeral=True)
            return

        owners = self.storage.getflowerowners(flower)
        if owners is None:
            await interaction.response.send_message(
                f"Flower **{flower}** does not exist.", ephemeral=True
            )
            return

        owners_str = ", ".join(owners) if owners else "Nobody"
        msg = await lookup_channel.send(f"{flower} — {owners_str}")  # type: ignore[union-attr]
        self.bot.loop.create_task(_delete_after(600, msg))
        await interaction.response.send_message(
            f"Lookup result posted in {lookup_channel.mention}.", ephemeral=True
        )

    # -----------------------------------------------------------------------
    # Manager: /flower add
    # -----------------------------------------------------------------------
    @flower_group.command(name="add", description="[Manager] Add a new flower")
    @app_commands.describe(name="Flower name", rarity="Uncommon / Rare / Epic / Legendary")
    async def flower_add(self, interaction: discord.Interaction, name: str, rarity: str) -> None:
        """Add a flower."""
        if not await self._is_manager(interaction):
            return
        try:
            self.storage.addflower(name, rarity)
            await interaction.response.send_message(f"Added flower **{name}**.", ephemeral=True)
            await self._update_registry_message(self._flower_range_index(name))
        except ValidationError as e:
            await interaction.response.send_message(str(e), ephemeral=True)

    # -----------------------------------------------------------------------
    # Manager: /flower rename
    # -----------------------------------------------------------------------
    @flower_group.command(name="rename", description="[Manager] Rename a flower")
    @app_commands.describe(old_name="Current name", new_name="New name")
    @app_commands.autocomplete(old_name=flower_autocomplete)
    async def flower_rename(self, interaction: discord.Interaction, old_name: str, new_name: str) -> None:
        """Rename a flower."""
        if not await self._is_manager(interaction):
            return
        try:
            self.storage.renameflower(old_name, new_name)
            await interaction.response.send_message(
                f"Renamed **{old_name}** → **{new_name}**.", ephemeral=True
            )
            old_idx = self._flower_range_index(old_name)
            new_idx = self._flower_range_index(new_name)
            await self._update_registry_message(old_idx)
            if old_idx != new_idx:
                await self._update_registry_message(new_idx)
        except ValidationError as e:
            await interaction.response.send_message(str(e), ephemeral=True)

    # -----------------------------------------------------------------------
    # /ign change
    # -----------------------------------------------------------------------
    ign_group = app_commands.Group(name="ign", description="Manage your IGN")

    @ign_group.command(name="change", description="Change your IGN")
    @app_commands.describe(new_ign="Your new IGN")
    async def ign_change(self, interaction: discord.Interaction, new_ign: str) -> None:
        """Change your IGN."""
        try:
            old, new = self.storage.updateplayerign(interaction.user.id, new_ign)
            await interaction.response.send_message(
                f"IGN updated from **{old}** to **{new}**.", ephemeral=True
            )
            await self._update_all_registry_messages()
        except ValidationError as e:
            await interaction.response.send_message(str(e), ephemeral=True)

    # -----------------------------------------------------------------------
    # Manager: /player remove
    # -----------------------------------------------------------------------
    player_group = app_commands.Group(name="player", description="Player management")

    @player_group.command(name="remove", description="[Manager] Remove a player by IGN")
    @app_commands.describe(ign="Player IGN to remove")
    @app_commands.autocomplete(ign=ign_autocomplete)
    async def player_remove(self, interaction: discord.Interaction, ign: str) -> None:
        """Remove a player and all their flower claims."""
        if not await self._is_manager(interaction):
            return

        # Find which flowers are affected for updating messages later.
        full = self.storage.getfullregistry()
        affected_flowers = [name for name, data in full.items() if ign in data["owners"]]

        try:
            removed = self.storage.removeplayerbyign(ign)
        except ValidationError as e:
            await interaction.response.send_message(str(e), ephemeral=True)
            return

        if not removed:
            await interaction.response.send_message(
                f"No player found with IGN **{ign}**.", ephemeral=True
            )
            return

        await interaction.response.send_message(f"Player **{ign}** removed.", ephemeral=True)

        indices = {self._flower_range_index(f) for f in affected_flowers}
        for idx in indices:
            await self._update_registry_message(idx)

    # -----------------------------------------------------------------------
    # Setup commands
    # -----------------------------------------------------------------------
    setup_group = app_commands.Group(name="setup", description="Manager configuration")

    @setup_group.command(name="registry_channel", description="Set the registry channel")
    @app_commands.describe(channel="Channel where the registry will be displayed")
    async def setup_registry_channel(self, interaction: discord.Interaction, channel: discord.TextChannel) -> None:
        """Define the registry channel and create the four registry messages."""
        config = self.storage.loadconfig()
        config["registrychannelid"] = channel.id
        self.storage.saveconfig(config)
        await interaction.response.send_message(
            f"Registry channel set to {channel.mention}.", ephemeral=True
        )
        await self._init_registry_messages(channel)

    @setup_group.command(name="lookup_channel", description="Set the channel for /whohas results")
    @app_commands.describe(channel="Lookup results channel")
    async def setup_lookup_channel(self, interaction: discord.Interaction, channel: discord.TextChannel) -> None:
        """Set the lookup channel."""
        config = self.storage.loadconfig()
        config["lookupchannelid"] = channel.id
        self.storage.saveconfig(config)
        await interaction.response.send_message(
            f"Lookup channel set to {channel.mention}.", ephemeral=True
        )

    @setup_group.command(name="commands_channel", description="Restrict normal commands to this channel")
    @app_commands.describe(channel="Commands channel")
    async def setup_commands_channel(self, interaction: discord.Interaction, channel: discord.TextChannel) -> None:
        """Set the channel where all non‑setup commands must be used."""
        config = self.storage.loadconfig()
        config["commandschannelid"] = channel.id
        self.storage.saveconfig(config)
        await interaction.response.send_message(
            f"Commands channel set to {channel.mention}.", ephemeral=True
        )

    @setup_group.command(name="manager_role", description="Set the role allowed to use manager commands")
    @app_commands.describe(role="Manager role")
    async def setup_manager_role(self, interaction: discord.Interaction, role: discord.Role) -> None:
        """Set the manager role."""
        config = self.storage.loadconfig()
        config["managerroleid"] = role.id
        self.storage.saveconfig(config)
        await interaction.response.send_message(
            f"Manager role set to {role.mention}.", ephemeral=True
        )


# ---------------------------------------------------------------------------
# Standard setup entry point
# ---------------------------------------------------------------------------
async def setup(bot: commands.Bot) -> None:
    """Load the FlowerCog."""
    storage = JSONStorage()  # uses the directory of database.py by default
    storage.initializefiles()
    await bot.add_cog(FlowerCog(bot, storage))
```
