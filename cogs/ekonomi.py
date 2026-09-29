from __future__ import annotations

import random
import time
from datetime import datetime, timezone

import discord
from discord.ext import commands

import config

ISLER = [
    "madende elmas kazdın", "çiftlikte buğday topladın", "köylülerle takas yaptın", "balık tutup sattın",
    "Nether'da altın topladın", "kale inşaatında usta olarak çalıştın", "pazarda demir sattın",
]


def fmt(n: int) -> str:
    return f"{n:,}".replace(",", ".") + f" 🪙 {config.CURRENCY}"


def when(ts: float) -> str:
    return discord.utils.format_dt(datetime.fromtimestamp(ts, tz=timezone.utc), "R")


class Ekonomi(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="bakiye", description="Bakiyeni göster", aliases=["para", "cuzdan"])
    @commands.guild_only()
    async def bakiye(self, ctx: commands.Context, uye: discord.Member = None):
        uye = uye or ctx.author
        bal, _, _ = await self.bot.db.get_eco(ctx.guild.id, uye.id)
        e = discord.Embed(title=f"💰 {uye.display_name} cüzdanı", description=f"**{fmt(bal)}**", color=config.COLOR_JOIN)
        e.set_thumbnail(url=uye.display_avatar.url)
        await ctx.send(embed=e)

    @commands.hybrid_command(name="gunluk", description="Günlük ödülünü al", aliases=["günlük", "daily"])
    @commands.guild_only()
    async def gunluk(self, ctx: commands.Context):
        bal, last, _ = await self.bot.db.get_eco(ctx.guild.id, ctx.author.id)
        now = time.time()
        if now - last < 86400:
            return await ctx.send(f"⏳ Günlük ödülünü zaten aldın. Tekrar: {when(last + 86400)}", ephemeral=True)
        amount = random.randint(200, 400)
        await self.bot.db.set_eco_time(ctx.guild.id, ctx.author.id, "last_daily", now)
        new = await self.bot.db.add_balance(ctx.guild.id, ctx.author.id, amount)
        await ctx.send(f"🎁 {ctx.author.mention} günlük ödülünü aldın: **+{fmt(amount)}**\nYeni bakiye: **{fmt(new)}**")

    @commands.hybrid_command(name="calis", description="Çalışıp para kazan (1 saatte bir)", aliases=["çalış", "work"])
    @commands.guild_only()
    async def calis(self, ctx: commands.Context):
        _, _, last = await self.bot.db.get_eco(ctx.guild.id, ctx.author.id)
        now = time.time()
        if now - last < 3600:
            return await ctx.send(f"⏳ Yorgunsun! Tekrar çalışabilirsin: {when(last + 3600)}", ephemeral=True)
        amount = random.randint(50, 150)
        await self.bot.db.set_eco_time(ctx.guild.id, ctx.author.id, "last_work", now)
        await self.bot.db.add_balance(ctx.guild.id, ctx.author.id, amount)
        await ctx.send(f"⛏️ {ctx.author.mention} {random.choice(ISLER)} ve **{fmt(amount)}** kazandın!")

    @commands.hybrid_command(name="gonder", description="Bir üyeye para gönder", aliases=["öde", "pay"])
    @commands.guild_only()
    async def gonder(self, ctx: commands.Context, uye: discord.Member, miktar: commands.Range[int, 1, 10_000_000]):
        if uye.bot or uye.id == ctx.author.id:
            return await ctx.send("❌ Kendine ya da bota para gönderemezsin.", ephemeral=True)
        bal, _, _ = await self.bot.db.get_eco(ctx.guild.id, ctx.author.id)
        if miktar > bal:
            return await ctx.send(f"❌ Yetersiz bakiye. Bakiyen: **{fmt(bal)}**", ephemeral=True)
        await self.bot.db.add_balance(ctx.guild.id, ctx.author.id, -miktar)
        await self.bot.db.add_balance(ctx.guild.id, uye.id, miktar)
        await ctx.send(f"💸 {ctx.author.mention} → {uye.mention}: **{fmt(miktar)}** gönderildi!")

    @commands.hybrid_command(name="kumar", description="Bahis oyna (%45 kazanma şansı, 2 katı)")
    @commands.guild_only()
    @commands.cooldown(1, 8, commands.BucketType.user)
    async def kumar(self, ctx: commands.Context, miktar: commands.Range[int, 10, 100_000]):
        bal, _, _ = await self.bot.db.get_eco(ctx.guild.id, ctx.author.id)
        if miktar > bal:
            return await ctx.send(f"❌ Yetersiz bakiye. Bakiyen: **{fmt(bal)}**", ephemeral=True)
        if random.random() < 0.45:
            new = await self.bot.db.add_balance(ctx.guild.id, ctx.author.id, miktar)
            await ctx.send(f"🎰 Kazandın! **+{fmt(miktar)}** • Bakiye: **{fmt(new)}**")
        else:
            new = await self.bot.db.add_balance(ctx.guild.id, ctx.author.id, -miktar)
            await ctx.send(f"💥 Kaybettin! **-{fmt(miktar)}** • Bakiye: **{fmt(new)}**")

    @commands.hybrid_command(name="zenginler", description="En zengin 10 üye", aliases=["zenginlik"])
    @commands.guild_only()
    async def zenginler(self, ctx: commands.Context):
        rows = await self.bot.db.top_balances(ctx.guild.id, 10)
        if not rows:
            return await ctx.send("Henüz kimsenin parası yok.", ephemeral=True)
        medals = ["🥇", "🥈", "🥉"]
        lines = [f"{medals[i] if i < 3 else f'`{i + 1}.`'} <@{uid}> • **{fmt(b)}**" for i, (uid, b) in enumerate(rows)]
        await ctx.send(embed=discord.Embed(title="💎 En Zenginler", description="\n".join(lines), color=config.COLOR_JOIN))


async def setup(bot):
    await bot.add_cog(Ekonomi(bot))
