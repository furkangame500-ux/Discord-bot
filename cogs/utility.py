from __future__ import annotations

import asyncio
import random

import discord
from discord import app_commands
from discord.ext import commands

import config
from utils import format_duration, parse_duration

NUM_EMOJIS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]


class GiveawayView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.entries: set[int] = set()

    @discord.ui.button(label="Katıl", emoji="🎉", style=discord.ButtonStyle.success)
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id in self.entries:
            self.entries.discard(interaction.user.id)
            msg = "❌ Çekilişten ayrıldın."
        else:
            self.entries.add(interaction.user.id)
            msg = "✅ Çekilişe katıldın!"
        button.label = f"Katıl ({len(self.entries)})"
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(msg, ephemeral=True)


class Utility(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="anket", description="Anket oluştur")
    @app_commands.describe(soru="Anket sorusu", secenekler="Seçenekleri | ile ayır (en fazla 10). Boşsa Evet/Hayır")
    @app_commands.guild_only()
    async def anket(self, interaction: discord.Interaction, soru: str, secenekler: str | None = None):
        if secenekler:
            opts = [o.strip() for o in secenekler.split("|") if o.strip()][:10]
            if len(opts) < 2:
                return await interaction.response.send_message("❌ En az 2 seçenek gerekli.", ephemeral=True)
            desc = "\n".join(f"{NUM_EMOJIS[i]} {o}" for i, o in enumerate(opts))
            emojis = NUM_EMOJIS[: len(opts)]
        else:
            desc, emojis = "✅ Evet\n❌ Hayır", ["✅", "❌"]
        e = discord.Embed(title=f"📊 {soru}", description=desc, color=config.COLOR_INFO)
        e.set_footer(text=f"Anketi açan: {interaction.user.display_name}")
        await interaction.response.send_message(embed=e)
        msg = await interaction.original_response()
        for em in emojis:
            await msg.add_reaction(em)

    @app_commands.command(name="duyuru", description="Embed duyuru gönder")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def duyuru(self, interaction: discord.Interaction, kanal: discord.TextChannel, baslik: str, mesaj: str,
                     etiket: discord.Role | None = None):
        e = discord.Embed(title=baslik, description=mesaj.replace("\\n", "\n"), color=config.COLOR_JOIN)
        e.set_footer(text=config.BRAND)
        await kanal.send(content=etiket.mention if etiket else None, embed=e,
                         allowed_mentions=discord.AllowedMentions(roles=True))
        await interaction.response.send_message("✅ Duyuru gönderildi.", ephemeral=True)

    @app_commands.command(name="cekilis", description="Çekiliş başlat")
    @app_commands.describe(odul="Ödül", sure="Süre: 10dk, 2sa, 1g", kazanan="Kazanan sayısı")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def cekilis(self, interaction: discord.Interaction, odul: str, sure: str,
                      kazanan: app_commands.Range[int, 1, 20] = 1):
        dur = parse_duration(sure)
        if not dur:
            return await interaction.response.send_message("❌ Geçersiz süre. Örnek: `10dk`, `2sa`, `1g`", ephemeral=True)
        end = discord.utils.utcnow() + dur
        view = GiveawayView()
        e = discord.Embed(title=f"🎁 {odul}", color=config.COLOR_JOIN,
                          description=f"Katılmak için butona bas!\nBitiş: {discord.utils.format_dt(end, 'R')}\nKazanan: **{kazanan}**")
        await interaction.response.send_message(embed=e, view=view)
        msg = await interaction.original_response()
        await asyncio.sleep(dur.total_seconds())
        entries = list(view.entries)
        winners = random.sample(entries, min(kazanan, len(entries))) if entries else []
        view.stop()
        for item in view.children:
            item.disabled = True
        result = " ".join(f"<@{w}>" for w in winners) if winners else "Katılan olmadı 😢"
        e.description = f"Çekiliş bitti!\n**Kazanan:** {result}"
        e.color = config.COLOR_OK
        try:
            await msg.edit(embed=e, view=view)
            if winners:
                await msg.reply(f"🎉 Tebrikler {result}! **{odul}** kazandınız!")
        except discord.HTTPException:
            pass


async def setup(bot):
    await bot.add_cog(Utility(bot))
