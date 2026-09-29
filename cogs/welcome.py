from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

import config


class Welcome(commands.Cog):
    gelengiden = app_commands.Group(
        name="gelengiden",
        description="Gelen-giden mesaj ayarları",
        guild_only=True,
        default_permissions=discord.Permissions(manage_guild=True),
    )

    def __init__(self, bot):
        self.bot = bot

    async def _embed(self, guild: discord.Guild, member: discord.abc.User, joined: bool):
        step = await self.bot.db.get_int(guild.id, "goal_step", 100)
        count = guild.member_count or 0
        goal = (count // step + 1) * step
        remaining = goal - count
        if joined:
            title = "Bir Üye Aramıza Katıldı"
            verb = "katıldı"
            color = config.COLOR_JOIN
        else:
            title = "Bir Üye Aramızdan Ayrıldı"
            verb = "ayrıldı"
            color = config.COLOR_LEAVE
        desc = (
            f"**{member.name}** {config.BRAND} topluluğuna {verb}. "
            if joined
            else f"**{member.name}** {config.BRAND} topluluğundan {verb}. "
        )
        desc += (
            f"Şu an **{count}** kişiyiz.\n\n"
            f"**{goal}** kişiye ulaşmamıza sadece **{remaining}** kişi kaldı."
        )
        embed = discord.Embed(title=title, description=desc, color=color)
        embed.set_author(name=config.BRAND)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=config.WEBSITE_URL)
        return embed

    async def _view(self, guild: discord.Guild):
        view = discord.ui.View(timeout=None)
        panel_ch = await self.bot.db.get_int(guild.id, "ticket_panel_channel")
        if panel_ch:
            view.add_item(
                discord.ui.Button(
                    label="Destek Talebi",
                    url=f"https://discord.com/channels/{guild.id}/{panel_ch}",
                )
            )
        view.add_item(discord.ui.Button(label="Web Sitesi", url=config.WEBSITE_URL))
        return view

    async def _send(self, guild: discord.Guild, member, joined: bool):
        ch_id = await self.bot.db.get_int(guild.id, "welcome_channel")
        channel = guild.get_channel(ch_id) if ch_id else None
        if not channel:
            return
        try:
            await channel.send(
                embed=await self._embed(guild, member, joined), view=await self._view(guild)
            )
        except discord.HTTPException:
            pass

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        role_id = await self.bot.db.get_int(member.guild.id, "autorole")
        role = member.guild.get_role(role_id) if role_id else None
        if role and not member.bot:
            try:
                await member.add_roles(role, reason="Otorol")
            except discord.HTTPException:
                pass
        await self._send(member.guild, member, True)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        await self._send(member.guild, member, False)

    @gelengiden.command(name="kur", description="Gelen-giden mesajlarının atılacağı kanalı ayarla")
    @app_commands.describe(kanal="Mesajların atılacağı kanal", hedef_adim="Hedef adımı (varsayılan 100)")
    async def kur(
        self,
        interaction: discord.Interaction,
        kanal: discord.TextChannel,
        hedef_adim: app_commands.Range[int, 10, 100000] = 100,
    ):
        await self.bot.db.set(interaction.guild.id, "welcome_channel", kanal.id)
        await self.bot.db.set(interaction.guild.id, "goal_step", hedef_adim)
        await interaction.response.send_message(
            f"✅ Gelen-giden kanalı {kanal.mention} olarak ayarlandı. Hedef adımı: **{hedef_adim}**",
            ephemeral=True,
        )

    @gelengiden.command(name="kapat", description="Gelen-giden mesajlarını kapat")
    async def kapat(self, interaction: discord.Interaction):
        await self.bot.db.set(interaction.guild.id, "welcome_channel", None)
        await interaction.response.send_message("✅ Gelen-giden mesajları kapatıldı.", ephemeral=True)

    @gelengiden.command(name="test", description="Test mesajı gönder")
    async def test(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await self._send(interaction.guild, interaction.user, True)
        await self._send(interaction.guild, interaction.user, False)
        await interaction.followup.send("✅ Test mesajları gönderildi.", ephemeral=True)

    @gelengiden.command(name="otorol", description="Yeni gelenlere otomatik verilecek rol (boş = kapat)")
    async def otorol(self, interaction: discord.Interaction, rol: discord.Role | None = None):
        if rol and (rol.managed or rol >= interaction.guild.me.top_role):
            return await interaction.response.send_message(
                "❌ Bu rolü veremem (rolüm bu rolden düşük olabilir).", ephemeral=True
            )
        await self.bot.db.set(interaction.guild.id, "autorole", rol.id if rol else None)
        await interaction.response.send_message(
            f"✅ Otorol: {rol.mention}" if rol else "✅ Otorol kapatıldı.", ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(Welcome(bot))
