# main.py  
import os  
import logging  
import asyncio  
  
import discord  
from discord.ext import commands  
from dotenv import load_dotenv  
  
from database import JSONStorage  
from command_file import FlowerCog  
  
# ---------------------------------------------------------------------------  
# Logging  
# ---------------------------------------------------------------------------  
logging.basicConfig(  
    level=logging.INFO,  
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",  
)  
logger = logging.getLogger(__name__)  
  
# ---------------------------------------------------------------------------  
# Async entry point  
# ---------------------------------------------------------------------------  
async def main() -> None:  
    """Start the Flower Registry Bot."""  
  
    # Load token from .env  
    load_dotenv()  
    token = os.getenv("DISCORD_TOKEN") or os.getenv("TOKEN")  
    if not token:  
        logger.critical("No token found. Set DISCORD_TOKEN or TOKEN in .env.")  
        return  
  
    # -------------------------------------------------------------------  
    # Storage (single instance)  
    # -------------------------------------------------------------------  
    storage = JSONStorage()  
    storage.initializefiles()  
    logger.info("JSONStorage initialised.")  
  
    # -------------------------------------------------------------------  
    # Bot setup  
    # -------------------------------------------------------------------  
    intents = discord.Intents.default()  # enough for slash commands  
    bot = commands.Bot(command_prefix=None, intents=intents)  # no prefix commands  
    bot.storage = storage  # attach for convenience  
  
    # Register the Flower cog  
    await bot.add_cog(FlowerCog(bot, storage))  
    logger.info("FlowerCog loaded.")  
  
    # -------------------------------------------------------------------  
    # Event: on_ready  
    # -------------------------------------------------------------------  
    @bot.event  
    async def on_ready() -> None:  
        """Sync slash commands once, then print startup info."""  
        if not hasattr(bot, "_has_synced"):  
            bot._has_synced = True  
            try:  
                synced = await bot.tree.sync()  
                logger.info(f"Synced {len(synced)} slash commands.")  
            except Exception as exc:  
                logger.error(f"Failed to sync commands: {exc}")  
  
        logger.info(f"Logged in as {bot.user.name} (ID: {bot.user.id})")  
        logger.info(f"Connected to {len(bot.guilds)} guilds.")  
  
    # -------------------------------------------------------------------  
    # Optional: log disconnects / resumes  
    # -------------------------------------------------------------------  
    @bot.event  
    async def on_disconnect() -> None:  
        logger.warning("Bot disconnected.")  
  
    @bot.event  
    async def on_resumed() -> None:  
        logger.info("Bot session resumed.")  
  
    # -------------------------------------------------------------------  
    # Run the bot  
    # -------------------------------------------------------------------  
    try:  
        await bot.start(token)  
    except KeyboardInterrupt:  
        logger.info("Shutdown requested (KeyboardInterrupt).")  
    except Exception as exc:  
        logger.critical(f"Fatal error: {exc}", exc_info=True)  
    finally:  
        if not bot.is_closed():  
            await bot.close()  
            logger.info("Bot connection closed.")  
  
  
# ---------------------------------------------------------------------------  
# Execute  
# ---------------------------------------------------------------------------  
if __name__ == "__main__":  
    asyncio.run(main())  
