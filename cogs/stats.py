from __future__ import annotations

import json
import logging

import discord
from discord import app_commands
from discord.ext import commands, tasks

import config

log = logging.getLogger("mercia.stats")

TYPES = {
    "uye": ("👥 Üye", lambda g: g.member_count),
    "insan": ("🙋 İnsan", lambda g: sum(1 for m in g.members if not m.bot)),
    "bot": ("🤖 Bot", lambda g: sum(1 for m in g.members if m.bot)),
    "boost": ("🚀 Boost", lambda g: g.premium_subscription_count),
    "rol": ("🎭 Rol", lambda g: len(g.roles)),
    "kanal": ("📁 Kanal", lambda g: len(g.channels)),
}
CHOICES = [
    app_commands.Choice(name="Üye sayısı (varsayılan)", value="uye"),
    app_commands.Choice(name="İnsan sayısı (bot hariç)", value="insan"),
    app_commands.Choice(name="Bot sayısı", value="bot"),
    app_commands.Choice(name="Boost sayısı", value="boost"),
    app_commands.Choice(name="Rol sayısı", value="rol"),
    app_commands.Choice(name="Kanal sayısı", value="kanal"),
    app_commands.Choice(name="Minecraft oyuncu sayısı", value="minecraft"),
]


class Stats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        self.loop.start()

    async def cog_unload(self):
        self.loop.cancel()

    async def _load(self, guild) -> dict:
        try:
            return json.loads(await self.bot.db.get(guild.id, "stat_channels", "{}"))
        except ValueError:
            return {}

    async def _save(self, guild, data: dict):
        await self.bot.db.set(guild.id, "stat_channels", json.dumps(data) if data else None)

    async def _name(self, guild, kind: str) -> str | None:
        if kind == "minecraft":
            from cogs.minecraft import fetch_status
            ip = await self.bot.db.get(guild.id, "mc_ip")
            if not ip:
                return None
            try:
                d = await fetch_status(ip)
            except Exception:
                return None
            if not d.get("online"):
                return "🔴 Sunucu Kapalı"
            p = d.get("players", {})
            return f"🎮 Oyuncu: {p.get('online', 0)}/{p.get('max', 0)}"
        label, fn = TYPES[kind]
        return f"{label}: {fn(guild)}"

    async def update_guild(self, guild: discord.Guild):
        data = await self._load(guild)
        changed = False
        for ch_id, kind in list(data.items()):
            channel = guild.get_channel(int(ch_id))
            if not channel:
                del data[ch_id]
                changed = True
                continue
            name = await self._name(guild, kind)
            if name and channel.name != name:
                try:
                    await channel.edit(name=name, reason="İstatistik güncellemesi")
                except discord.HTTPException:
                    log.warning("Kanal adı değiştirilemedi: %s", ch_id)
        if changed:
            await self._save(guild, data)

    @tasks.loop(minutes=10)
    async def loop(self):
        for guild in self.bot.guilds:
            try:
                await self.update_guild(guild)
            except Exception:
                log.exception("İstatistik güncelleme hatası")

    @loop.before_loop
    async def before_loop(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="istatistik", description="Seçtiğin ses kanalını istatistik kanalına çevirir")
    @app_commands.describe(kanal="İstatistik kanalı olacak SES kanalı", tur="Ne gösterilsin? (varsayılan: üye sayısı)")
    @app_commands.choices(tur=CHOICES)
    @app_commands.default_permissions(manage_channels=True)
    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.guild_only()
    async def istatistik(self, interaction: discord.Interaction, kanal: discord.VoiceChannel,
                         tur: app_commands.Choice[str] | None = None):
        kind = tur.value if tur else "uye"
        if kind == "minecraft" and not await self.bot.db.get(interaction.guild.id, "mc_ip"):
            return await interaction.response.send_message("❌ Önce `/mc ip-ayarla` ile sunucu IP'sini gir.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        data = await self._load(interaction.guild)
        data[str(kanal.id)] = kind
        await self._save(interaction.guild, data)
        try:  # kimse girip çıkmasın, sadece görünsün
            await kanal.set_permissions(interaction.guild.default_role, connect=False, reason="İstatistik kanalı")
        except discord.HTTPException:
            pass
        await self.update_guild(interaction.guild)
        await interaction.followup.send(
            f"✅ {kanal.mention} artık istatistik kanalı. Adı 10 dakikada bir güncellenir.", ephemeral=True)

    @app_commands.command(name="istatistik-kaldir", description="Bir kanalı istatistik kanalı olmaktan çıkar")
    @app_commands.default_permissions(manage_channels=True)
    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.guild_only()
    async def istatistik_kaldir(self, interaction: discord.Interaction, kanal: discord.VoiceChannel):
        data = await self._load(interaction.guild)
        if str(kanal.id) not in data:
            return await interaction.response.send_message("❌ Bu kanal istatistik kanalı değil.", ephemeral=True)
        del data[str(kanal.id)]
        await self._save(interaction.guild, data)
        await interaction.response.send_message(f"✅ {kanal.mention} artık güncellenmeyecek.", ephemeral=True)

    @app_commands.command(name="istatistik-liste", description="Aktif istatistik kanallarını göster")
    @app_commands.guild_only()
    async def istatistik_liste(self, interaction: discord.Interaction):
        data = await self._load(interaction.guild)
        if not data:
            return await interaction.response.send_message("Henüz istatistik kanalı yok.", ephemeral=True)
        names = {c.value: c.name for c in CHOICES}
        lines = [f"<#{cid}> → {names.get(k, k)}" for cid, k in data.items()]
        await interaction.response.send_message("\n".join(lines), ephemeral=True)


async def setup(bot):
    await bot.add_cog(Stats(bot))
