from __future__ import annotations

import random
import time

import discord
from discord import app_commands
from discord.ext import commands

import config


def xp_needed(level: int) -> int:
    return 5 * level**2 + 50 * level + 100


class Levels(commands.Cog):
    seviye = app_commands.Group(name="seviye", description="Seviye sistemi", guild_only=True)

    def __init__(self, bot):
        self.bot = bot
        self.cooldown: dict[tuple[int, int], float] = {}

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild or len(message.content) < 3:
            return
        key = (message.guild.id, message.author.id)
        now = time.monotonic()
        if now - self.cooldown.get(key, 0) < 60:
            return
        self.cooldown[key] = now
        xp, level = await self.bot.db.get_level(*key)
        xp += random.randint(15, 25)
        leveled = False
        while xp >= xp_needed(level):
            xp -= xp_needed(level)
            level += 1
            leveled = True
        await self.bot.db.set_level(key[0], key[1], xp, level)
        if not leveled:
            return
        try:
            await message.channel.send(f"🎉 {message.author.mention} seviye atladı! Yeni seviye: **{level}**")
        except discord.HTTPException:
            pass
        role_id = await self.bot.db.get_int(message.guild.id, f"levelrole_{level}")
        role = message.guild.get_role(role_id) if role_id else None
        if role and isinstance(message.author, discord.Member):
            try:
                await message.author.add_roles(role, reason=f"Seviye {level} ödülü")
            except discord.HTTPException:
                pass

    @seviye.command(name="bak", description="Seviyeni göster")
    async def bak(self, interaction: discord.Interaction, uye: discord.Member | None = None):
        uye = uye or interaction.user
        xp, level = await self.bot.db.get_level(interaction.guild.id, uye.id)
        need = xp_needed(level)
        rank = await self.bot.db.get_rank(interaction.guild.id, uye.id)
        filled = int(10 * xp / need)
        bar = "🟩" * filled + "⬛" * (10 - filled)
        e = discord.Embed(title=f"⭐ {uye.display_name}", color=config.COLOR_INFO)
        e.set_thumbnail(url=uye.display_avatar.url)
        e.add_field(name="Seviye", value=str(level))
        e.add_field(name="Sıra", value=f"#{rank}")
        e.add_field(name="XP", value=f"{xp}/{need}")
        e.add_field(name="İlerleme", value=bar, inline=False)
        await interaction.response.send_message(embed=e)

    @seviye.command(name="liderlik", description="En yüksek seviyeli 10 üye")
    async def liderlik(self, interaction: discord.Interaction):
        rows = await self.bot.db.top_levels(interaction.guild.id, 10)
        if not rows:
            return await interaction.response.send_message("Henüz kimse XP kazanmadı.", ephemeral=True)
        medals = ["🥇", "🥈", "🥉"]
        lines = [f"{medals[i] if i < 3 else f'`{i + 1}.`'} <@{uid}> • Seviye **{lvl}** ({xp} XP)"
                 for i, (uid, xp, lvl) in enumerate(rows)]
        e = discord.Embed(title="🏆 Liderlik Tablosu", description="\n".join(lines), color=config.COLOR_JOIN)
        await interaction.response.send_message(embed=e)

    @seviye.command(name="rol", description="Belirli seviyeye ulaşınca verilecek rolü ayarla")
    @app_commands.describe(seviye="Seviye", rol="Verilecek rol (boş = kaldır)")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def rol(self, interaction: discord.Interaction, seviye: app_commands.Range[int, 1, 500],
                  rol: discord.Role | None = None):
        if rol and (rol.managed or rol >= interaction.guild.me.top_role):
            return await interaction.response.send_message("❌ Bu rolü veremem (bot rolü daha altta).", ephemeral=True)
        await self.bot.db.set(interaction.guild.id, f"levelrole_{seviye}", rol.id if rol else None)
        await interaction.response.send_message(
            f"✅ Seviye {seviye} → {rol.mention}" if rol else f"✅ Seviye {seviye} ödülü kaldırıldı.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Levels(bot))
