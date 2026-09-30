from __future__ import annotations

from urllib.parse import urlparse

import discord
from discord import app_commands
from discord.ext import commands

import config


def clean_url(text: str) -> str | None:
    text = text.strip()
    if "://" not in text:
        text = "https://" + text
    u = urlparse(text)
    return text if u.scheme in ("http", "https") and "." in u.netloc else None


class Menu(commands.Cog):
    menu = app_commands.Group(
        name="menu", description="Menü paneli", guild_only=True,
        default_permissions=discord.Permissions(manage_guild=True),
    )

    def __init__(self, bot):
        self.bot = bot

    @menu.command(name="oluştur", description="Bir kanala açıklamalı ve link butonlu menü gönder")
    @app_commands.describe(
        kanal="Menünün gönderileceği kanal",
        aciklama="Menü açıklaması (satır atlamak için \\n yaz)",
        link="Butonun gideceği link (örn: bxproject.com)",
        baslik="Menü başlığı (isteğe bağlı)",
        buton="Buton yazısı (isteğe bağlı)",
        gorsel="Menüde görünecek resim linki (isteğe bağlı)",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def olustur(self, interaction: discord.Interaction, kanal: discord.TextChannel, aciklama: str, link: str,
                      baslik: str | None = None, buton: str | None = None, gorsel: str | None = None):
        url = clean_url(link)
        if not url:
            return await interaction.response.send_message("❌ Geçerli bir link gir. Örnek: `https://bxproject.com`", ephemeral=True)
        image = None
        if gorsel:
            image = clean_url(gorsel)
            if not image:
                return await interaction.response.send_message("❌ Görsel linki geçersiz.", ephemeral=True)
        perms = kanal.permissions_for(interaction.guild.me)
        if not (perms.view_channel and perms.send_messages and perms.embed_links):
            return await interaction.response.send_message(f"❌ {kanal.mention} kanalına mesaj/embed gönderme iznim yok.", ephemeral=True)

        e = discord.Embed(title=(baslik or f"📋 {config.BRAND} Menü")[:250],
                          description=aciklama.replace("\\n", "\n")[:4000], color=config.COLOR_INFO)
        if image:
            e.set_image(url=image)
        e.set_footer(text=config.BRAND)
        view = discord.ui.View(timeout=None)
        view.add_item(discord.ui.Button(label=(buton or "Bağlantıya Git")[:80], url=url))
        try:
            msg = await kanal.send(embed=e, view=view)
        except discord.HTTPException:
            return await interaction.response.send_message("❌ Menü gönderilemedi.", ephemeral=True)
        await interaction.response.send_message(f"✅ Menü oluşturuldu: {msg.jump_url}", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Menu(bot))
