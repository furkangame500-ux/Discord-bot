from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

import config


class Logs(commands.Cog):
    log = app_commands.Group(
        name="log", description="Log sistemi", guild_only=True,
        default_permissions=discord.Permissions(manage_guild=True),
    )

    def __init__(self, bot):
        self.bot = bot

    @log.command(name="kur", description="Log kanalını ayarla")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def kur(self, interaction: discord.Interaction, kanal: discord.TextChannel):
        await self.bot.db.set(interaction.guild.id, "log_channel", kanal.id)
        await interaction.response.send_message(f"✅ Log kanalı: {kanal.mention}", ephemeral=True)

    @log.command(name="kapat", description="Log sistemini kapat")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def kapat(self, interaction: discord.Interaction):
        await self.bot.db.set(interaction.guild.id, "log_channel", None)
        await interaction.response.send_message("✅ Log kapatıldı.", ephemeral=True)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if not message.guild or message.author.bot or not message.content:
            return
        e = discord.Embed(title="🗑️ Mesaj Silindi", color=config.COLOR_LEAVE,
                          description=f"{message.author.mention} • {message.channel.mention}")
        e.add_field(name="Mesaj", value=message.content[:1000], inline=False)
        await self.bot.send_log(message.guild, e)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if not before.guild or before.author.bot or before.content == after.content:
            return
        e = discord.Embed(title="✏️ Mesaj Düzenlendi", color=config.COLOR_WARN,
                          description=f"{before.author.mention} • [Mesaja git]({after.jump_url})")
        e.add_field(name="Önce", value=(before.content or "-")[:1000], inline=False)
        e.add_field(name="Sonra", value=(after.content or "-")[:1000], inline=False)
        await self.bot.send_log(before.guild, e)

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        e = discord.Embed(title="🔨 Ban", color=config.COLOR_LEAVE, description=f"{user} ({user.id})")
        await self.bot.send_log(guild, e)

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User):
        e = discord.Embed(title="♻️ Ban Kaldırıldı", color=config.COLOR_OK, description=f"{user} ({user.id})")
        await self.bot.send_log(guild, e)


async def setup(bot):
    await bot.add_cog(Logs(bot))
