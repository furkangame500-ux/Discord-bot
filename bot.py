import logging

import discord
from discord import app_commands
from discord.ext import commands
from google import genai

import config
from database import Database

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("mercia")

EXTENSIONS = [
    "cogs.welcome",
    "cogs.ticket",
    "cogs.moderation",
    "cogs.automod",
    "cogs.subscribe",
    "cogs.minecraft",
    "cogs.levels",
    "cogs.logs",
    "cogs.stats",
    "cogs.music",
    "cogs.eglence",
    "cogs.araclar",
    "cogs.ekonomi",
    "cogs.yonetim",
    "cogs.linkkoruma",
    "cogs.menu",
    "cogs.utility",
]


class BXProjectBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        super().__init__(
            command_prefix=commands.when_mentioned_or("B!", "b!"),
            case_insensitive=True,
            strip_after_prefix=True,
            intents=intents,
            help_command=None,
            activity=discord.Activity(
                type=discord.ActivityType.watching, name=f"{config.BRAND} | B!yardim"
            ),
        )
        self.started_at = discord.utils.utcnow()
        self.db = Database()
        
        # Gemini İstemcisi (Client) Tanımlaması
        self.ai = (
            genai.Client(api_key=config.GEMINI_API_KEY)
            if config.GEMINI_API_KEY
            else None
        )
        if not self.ai:
            log.warning("GEMINI_API_KEY yok: AI özellikleri (küfür filtresi, abone doğrulama, çeviri, yapay zeka) çalışmaz.")

    async def setup_hook(self):
        await self.db.connect()
        for ext in EXTENSIONS:
            await self.load_extension(ext)
            log.info("Yüklendi: %s", ext)
        if config.GUILD_ID:
            guild = discord.Object(id=config.GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()

    async def send_log(self, guild: discord.Guild, embed: discord.Embed):
        ch_id = await self.db.get_int(guild.id, "log_channel")
        channel = guild.get_channel(ch_id) if ch_id else None
        if channel:
            try:
                await channel.send(embed=embed)
            except discord.HTTPException:
                pass

    async def on_ready(self):
        log.info("Giriş yapıldı: %s (%s)", self.user, self.user.id)

    async def close(self):
        await self.db.close()
        await super().close()


bot = BXProjectBot()

_handled: set[int] = set()


def error_message(error: Exception) -> str | None:
    error = getattr(error, "original", error)
    if isinstance(error, (commands.MissingPermissions, app_commands.MissingPermissions)):
        return "❌ Bu komutu kullanmak için yetkin yok."
    if isinstance(error, (commands.BotMissingPermissions, app_commands.BotMissingPermissions)):
        return "❌ Botun bu işlem için yetkisi yok."
    if isinstance(error, (commands.NoPrivateMessage, app_commands.NoPrivateMessage)):
        return "❌ Bu komut sadece sunucuda kullanılabilir."
    if isinstance(error, commands.MissingRequiredArgument):
        return f"❌ Eksik bilgi girdin: `{error.param.name}`. Komutları görmek için `B!yardim`"
    if isinstance(error, commands.BadArgument):
        return "❌ Geçersiz bir değer girdin. Örnek kullanım için `B!yardim`"
    if isinstance(error, (commands.CommandOnCooldown, app_commands.CommandOnCooldown)):
        return f"⏳ Biraz yavaş! **{error.retry_after:.0f} saniye** sonra tekrar dene."
    if isinstance(error, (commands.CheckFailure, app_commands.CheckFailure)):
        return "❌ Bu komutu kullanamazsın."
    if isinstance(error, commands.CommandNotFound):
        return None
    log.exception("Komut hatası", exc_info=error)
    return "❌ Bir hata oluştu, biraz sonra tekrar dene."


def _first_time(key: int) -> bool:
    if key in _handled:
        return False
    if len(_handled) > 500:
        _handled.clear()
    _handled.add(key)
    return True


@bot.tree.error
async def on_tree_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    msg = error_message(error)
    if not msg or not _first_time(interaction.id):
        return
    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except discord.HTTPException:
        pass


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    msg = error_message(error)
    key = ctx.interaction.id if ctx.interaction else ctx.message.id
    if not msg or not _first_time(key):
        return
    try:
        await ctx.send(msg, ephemeral=True)
    except discord.HTTPException:
        pass


if __name__ == "__main__":
    if not config.TOKEN:
        raise SystemExit("DISCORD_TOKEN bulunamadı. .env dosyasını doldur.")
    bot.run(config.TOKEN, log_handler=None)