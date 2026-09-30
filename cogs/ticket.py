from __future__ import annotations

import asyncio
import io
import re

import discord
from discord import app_commands
from discord.ext import commands

import config

OWNER_RE = re.compile(r"ticket_owner:(\d+)")


def ticket_owner_id(channel) -> int | None:
    m = OWNER_RE.search(getattr(channel, "topic", None) or "")
    return int(m.group(1)) if m else None


async def is_staff(bot, member: discord.Member) -> bool:
    if member.guild_permissions.manage_channels:
        return True
    role_id = await bot.db.get_int(member.guild.id, "ticket_role")
    return bool(role_id and any(r.id == role_id for r in member.roles))


async def close_ticket(bot, channel: discord.TextChannel, closer: discord.abc.User):
    guild = channel.guild
    owner_id = ticket_owner_id(channel)
    lines = []
    async for m in channel.history(limit=None, oldest_first=True):
        text = m.content or ("[embed]" if m.embeds else "")
        if m.attachments:
            text += " " + " ".join(a.url for a in m.attachments)
        lines.append(f"[{m.created_at:%Y-%m-%d %H:%M}] {m.author} ({m.author.id}): {text}")
    log_id = await bot.db.get_int(guild.id, "ticket_log")
    log_ch = guild.get_channel(log_id) if log_id else None
    if log_ch:
        embed = discord.Embed(title="🔒 Ticket Kapatıldı", color=config.COLOR_LEAVE)
        embed.add_field(name="Kanal", value=channel.name)
        embed.add_field(name="Açan", value=f"<@{owner_id}>" if owner_id else "?")
        embed.add_field(name="Kapatan", value=closer.mention)
        file = discord.File(io.BytesIO("\n".join(lines).encode("utf-8")), filename=f"{channel.name}.txt")
        try:
            await log_ch.send(embed=embed, file=file)
        except discord.HTTPException:
            pass
    await channel.delete(reason=f"Ticket kapatıldı: {closer}")


class TicketControlView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="Talebi Kapat", emoji="🔒", style=discord.ButtonStyle.danger, custom_id="mercia:ticket:close")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        owner = ticket_owner_id(interaction.channel)
        if interaction.user.id != owner and not await is_staff(self.bot, interaction.user):
            return await interaction.response.send_message("❌ Bu talebi kapatamazsın.", ephemeral=True)
        await interaction.response.send_message("🔒 Talep 5 saniye içinde kapatılıyor...")
        await asyncio.sleep(5)
        await close_ticket(self.bot, interaction.channel, interaction.user)

    @discord.ui.button(label="Üstlen", emoji="🙋", style=discord.ButtonStyle.success, custom_id="mercia:ticket:claim")
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await is_staff(self.bot, interaction.user):
            return await interaction.response.send_message("❌ Sadece yetkililer üstlenebilir.", ephemeral=True)
        await interaction.response.send_message(f"🙋 Bu talebi {interaction.user.mention} üstlendi.")


class TicketPanelView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="Destek Talebi Aç", emoji="🎫", style=discord.ButtonStyle.primary, custom_id="mercia:ticket:open")
    async def open(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        guild, user = interaction.guild, interaction.user
        db = self.bot.db
        cat_id = await db.get_int(guild.id, "ticket_category")
        role_id = await db.get_int(guild.id, "ticket_role")
        category = guild.get_channel(cat_id) if cat_id else None
        role = guild.get_role(role_id) if role_id else None

        pool = category.text_channels if category else guild.text_channels
        for ch in pool:
            if ticket_owner_id(ch) == user.id:
                return await interaction.followup.send(f"❌ Zaten açık bir talebin var: {ch.mention}", ephemeral=True)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, attach_files=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True, read_message_history=True),
        }
        if role:
            overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, manage_messages=True)
        try:
            channel = await guild.create_text_channel(
                name=f"destek-{user.name}"[:90],
                category=category,
                overwrites=overwrites,
                topic=f"ticket_owner:{user.id}",
                reason=f"Ticket: {user}",
            )
        except discord.HTTPException:
            return await interaction.followup.send("❌ Kanal oluşturamadım. Yetkilerimi kontrol et.", ephemeral=True)

        embed = discord.Embed(
            title="🎫 Destek Talebi",
            description=f"Merhaba {user.mention}! Sorununu detaylı yaz, yetkililer en kısa sürede ilgilenecek.",
            color=config.COLOR_INFO,
        )
        embed.set_footer(text=config.BRAND)
        await channel.send(
            content=f"{user.mention} {role.mention if role else ''}",
            embed=embed,
            view=TicketControlView(self.bot),
        )
        await interaction.followup.send(f"✅ Talebin açıldı: {channel.mention}", ephemeral=True)


class Ticket(commands.Cog):
    ticket = app_commands.Group(name="ticket", description="Destek talebi sistemi", guild_only=True)

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(TicketPanelView(self.bot))
        self.bot.add_view(TicketControlView(self.bot))

    @ticket.command(name="kur", description="Ticket panelini kur")
    @app_commands.describe(
        kanal="Panelin gönderileceği kanal",
        kategori="Ticket kanallarının açılacağı kategori",
        yetkili_rol="Ticketları görecek yetkili rol",
        log_kanal="Kapanan ticketların kaydı (isteğe bağlı)",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def kur(
        self,
        interaction: discord.Interaction,
        kanal: discord.TextChannel,
        kategori: discord.CategoryChannel,
        yetkili_rol: discord.Role,
        log_kanal: discord.TextChannel | None = None,
    ):
        db, gid = self.bot.db, interaction.guild.id
        await db.set(gid, "ticket_category", kategori.id)
        await db.set(gid, "ticket_role", yetkili_rol.id)
        await db.set(gid, "ticket_panel_channel", kanal.id)
        await db.set(gid, "ticket_log", log_kanal.id if log_kanal else None)
        embed = discord.Embed(
            title="🎫 Destek Talebi",
            description="Yardıma mı ihtiyacın var? Aşağıdaki butona basarak yetkililerle özel bir kanal aç.",
            color=config.COLOR_INFO,
        )
        embed.set_footer(text=config.BRAND)
        try:
            await kanal.send(embed=embed, view=TicketPanelView(self.bot))
        except discord.HTTPException:
            return await interaction.response.send_message("❌ O kanala yazamıyorum.", ephemeral=True)
        await interaction.response.send_message(f"✅ Ticket paneli {kanal.mention} kanalına kuruldu.", ephemeral=True)

    async def _staff_in_ticket(self, interaction) -> bool:
        if ticket_owner_id(interaction.channel) is None:
            await interaction.response.send_message("❌ Bu bir ticket kanalı değil.", ephemeral=True)
            return False
        if not await is_staff(self.bot, interaction.user):
            await interaction.response.send_message("❌ Yetkin yok.", ephemeral=True)
            return False
        return True

    @ticket.command(name="ekle", description="Ticket'a kullanıcı ekle")
    async def ekle(self, interaction: discord.Interaction, uye: discord.Member):
        if not await self._staff_in_ticket(interaction):
            return
        await interaction.channel.set_permissions(uye, view_channel=True, send_messages=True, read_message_history=True)
        await interaction.response.send_message(f"✅ {uye.mention} talebe eklendi.")

    @ticket.command(name="cikar", description="Ticket'tan kullanıcı çıkar")
    async def cikar(self, interaction: discord.Interaction, uye: discord.Member):
        if not await self._staff_in_ticket(interaction):
            return
        await interaction.channel.set_permissions(uye, overwrite=None)
        await interaction.response.send_message(f"✅ {uye.mention} talepten çıkarıldı.")

    @ticket.command(name="kapat", description="Bu ticket'ı kapat")
    async def kapat(self, interaction: discord.Interaction):
        if not await self._staff_in_ticket(interaction):
            return
        await interaction.response.send_message("🔒 Talep 5 saniye içinde kapatılıyor...")
        await asyncio.sleep(5)
        await close_ticket(self.bot, interaction.channel, interaction.user)


async def setup(bot):
    await bot.add_cog(Ticket(bot))
