from __future__ import annotations

import logging

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks

import config

log = logging.getLogger("mercia.minecraft")


async def fetch_status(ip: str) -> dict:
    timeout = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(timeout=timeout, headers={"User-Agent": "MerciaBot/1.0"}) as s:
        async with s.get(f"https://api.mcsrvstat.us/3/{ip}") as r:
            return await r.json(content_type=None)


class Minecraft(commands.Cog):
    mc = app_commands.Group(name="mc", description="Minecraft sunucu araçları", guild_only=True)

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        self.stat_loop.start()

    async def cog_unload(self):
        self.stat_loop.cancel()

    @tasks.loop(minutes=10)
    async def stat_loop(self):
        for guild in self.bot.guilds:
            ip = await self.bot.db.get(guild.id, "mc_ip")
            ch_id = await self.bot.db.get_int(guild.id, "mc_stat_channel")
            channel = guild.get_channel(ch_id) if ch_id else None
            if not ip or not channel:
                continue
            try:
                data = await fetch_status(ip)
                if data.get("online"):
                    p = data.get("players", {})
                    name = f"🟢 Oyuncu: {p.get('online', 0)}/{p.get('max', 0)}"
                else:
                    name = "🔴 Sunucu Kapalı"
                if channel.name != name:
                    await channel.edit(name=name, reason="Minecraft durum güncellemesi")
            except Exception:
                log.exception("Minecraft durum döngüsü hatası")

    @stat_loop.before_loop
    async def before_loop(self):
        await self.bot.wait_until_ready()

    @mc.command(name="ip-ayarla", description="Minecraft sunucu IP'sini kaydet")
    @app_commands.describe(ip="Örn: play.merciaproject.com")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def ip_ayarla(self, interaction: discord.Interaction, ip: str):
        await self.bot.db.set(interaction.guild.id, "mc_ip", ip.strip())
        await interaction.response.send_message(f"✅ Sunucu IP: `{ip.strip()}`", ephemeral=True)

    @mc.command(name="durum-kanali", description="Oyuncu sayısını gösterecek sesli/metin kanalını seç")
    @app_commands.describe(kanal="Adı otomatik güncellenecek kanal (10 dakikada bir)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def durum_kanali(self, interaction: discord.Interaction, kanal: discord.VoiceChannel | discord.TextChannel):
        await self.bot.db.set(interaction.guild.id, "mc_stat_channel", kanal.id)
        await interaction.response.send_message(f"✅ {kanal.mention} kanalının adı 10 dakikada bir güncellenecek.", ephemeral=True)

    @mc.command(name="ip", description="Sunucu IP'sini göster")
    async def ip(self, interaction: discord.Interaction):
        ip = await self.bot.db.get(interaction.guild.id, "mc_ip")
        if not ip:
            return await interaction.response.send_message("❌ IP ayarlanmamış (`/mc ip-ayarla`).", ephemeral=True)
        await interaction.response.send_message(f"🎮 Sunucu IP: `{ip}`")

    @mc.command(name="durum", description="Minecraft sunucusunun durumunu göster")
    @app_commands.describe(ip="Boş bırakırsan kayıtlı IP kullanılır")
    async def durum(self, interaction: discord.Interaction, ip: str | None = None):
        ip = ip or await self.bot.db.get(interaction.guild.id, "mc_ip")
        if not ip:
            return await interaction.response.send_message("❌ IP ayarlanmamış (`/mc ip-ayarla`).", ephemeral=True)
        await interaction.response.defer()
        try:
            data = await fetch_status(ip)
        except Exception:
            return await interaction.followup.send("❌ Sunucu durumu alınamadı.")
        if not data.get("online"):
            e = discord.Embed(title=f"🔴 {ip}", description="Sunucu şu an **kapalı**.", color=config.COLOR_LEAVE)
            return await interaction.followup.send(embed=e)
        players = data.get("players", {})
        motd = "\n".join(data.get("motd", {}).get("clean", [])) or "-"
        e = discord.Embed(title=f"🟢 {ip}", description=motd, color=config.COLOR_OK)
        e.add_field(name="Oyuncu", value=f"{players.get('online', 0)}/{players.get('max', 0)}")
        e.add_field(name="Sürüm", value=str(data.get("version", "?")))
        names = [p.get("name", "?") for p in players.get("list", [])[:15]]
        if names:
            e.add_field(name="Çevrimiçi", value=", ".join(names), inline=False)
        await interaction.followup.send(embed=e)


async def setup(bot):
    await bot.add_cog(Minecraft(bot))
