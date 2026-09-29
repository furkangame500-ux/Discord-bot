from __future__ import annotations

import asyncio
import random
import re
from datetime import date

import aiohttp
import discord
from discord.ext import commands

import config

ESPRILER = [
    "Creeper'a neden arkadaşın yok demişler. 'Herkes yaklaşınca kaçıyor, ben de üzülüp patlıyorum' demiş.",
    "Kitap okumayı seven zombi ne demiş? 'Beyin fırtınası yapalım!'",
    "Hangi blok her zaman iyimserdir? Elmas blok, çünkü hep parlıyor!",
    "Enderman neden selfie çekmiyor? Çünkü kameraya bakınca sinirleniyor!",
    "Balık neden internete giremiyor? Çünkü hep ağa takılıyor!",
    "Bilgisayar doktora gitmiş: 'Doktor bey, bende virüs var!' Doktor: 'Geçmiş olsun, önce bir yeniden başlatalım.'",
    "Baba: 'Oğlum notların neden düşük?' Oğul: 'Baba, sınav zor değil, sadece cevaplar hep yanlış çıkıyor.'",
    "Pilot: 'Sayın yolcular, sağımızda bulut, solumuzda bulut, altımızda da bulut.' Yolcu: 'Peki yeryüzü nerede?'",
    "İskelet neden hiç yalnız kalmaz? Çünkü kemiklerinden bile arkadaşı var!",
    "Madenci neden hep iyi uyur? Çünkü gün boyu yatak (kat) kat kazıyor!",
]
SOZLER = [
    "Düşmeden yürümeyi öğrenen yoktur.",
    "Küçük adımlar, büyük yolların başlangıcıdır.",
    "Zor olan başlamaktır, gerisi gelir.",
    "Her usta bir zamanlar acemiydi.",
    "Hata yapmak, denemeye cesaret ettiğinin kanıtıdır.",
    "Sabır, en sağlam kazmadır.",
    "İlk blok konmadan hiçbir kale yükselmez.",
    "Bugün attığın küçük adım, yarınki büyük farkın ta kendisi.",
]
MC_IPUCLARI = [
    "Uyuduğun yatak, yeniden doğma noktanı (spawn) belirler.",
    "Nether ve End'de yatağa tıklarsan patlar, dikkat!",
    "Düşerken su kovasını yere doğru kullanırsan düşme hasarı almazsın.",
    "İpek Dokunuşu (Silk Touch) ile cam ve cevher bloklarını olduğu gibi alabilirsin.",
    "Servet (Fortune) büyüsü elmas ve lapis gibi cevherlerden daha fazla eşya düşürür.",
    "Enderman'a bakmadan önce kafana oyulmuş kabak takarsan sana saldırmaz.",
    "Kaybolursan F3 ile koordinatlarını görebilir, eve dönüş yolunu bulabilirsin.",
    "Evinin çevresini meşale ile aydınlatırsan canavarlar oluşamaz (spawn olmaz).",
    "Creeper yaklaşırken vur ve hemen geri çekil; patlamadan önce mesafeyi aç.",
    "Sandıkları çift yaparsan depolama alanın iki katına çıkar.",
]
KURE = [
    "🎱 Kesinlikle evet!", "🎱 Bence evet.", "🎱 Büyük ihtimalle.", "🎱 Görünüşe göre evet.",
    "🎱 Şimdilik belirsiz, tekrar sor.", "🎱 Şimdi söylemesem daha iyi.", "🎱 Konsantre ol ve tekrar sor.",
    "🎱 Buna güvenme.", "🎱 Cevabım hayır.", "🎱 Pek sanmıyorum.", "🎱 Kesinlikle hayır!",
]
TOKAT = ["{a} → {b} kişisine müthiş bir tokat attı! 👋💥", "{a}, {b} kişisine tokadı bastı, ses odada yankılandı! 😵",
         "{b}, {a} tarafından tokatlandı! Yüzü kıpkırmızı 🍅"]
SARIL = ["{a}, {b} kişisine sımsıkı sarıldı! 🤗", "{a} → {b}: sıcacık bir sarılma! 💞", "{b}, {a} tarafından ayı gibi sarıldı! 🐻"]
NAME_RE = re.compile(r"^[A-Za-z0-9_]{3,16}$")


def bar(pct: int, size: int = 10) -> str:
    filled = round(pct / 100 * size)
    return "🟥" * filled + "⬛" * (size - filled)


class TkmView(discord.ui.View):
    def __init__(self, author: discord.abc.User):
        super().__init__(timeout=30)
        self.author = author

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("❌ Bu oyun sana ait değil.", ephemeral=True)
            return False
        return True

    async def _play(self, interaction: discord.Interaction, choice: str):
        opts = {"tas": "🪨 Taş", "kagit": "📄 Kağıt", "makas": "✂️ Makas"}
        bot_choice = random.choice(list(opts))
        wins = {("tas", "makas"), ("kagit", "tas"), ("makas", "kagit")}
        if choice == bot_choice:
            result, color = "🤝 Berabere!", config.COLOR_WARN
        elif (choice, bot_choice) in wins:
            result, color = "🎉 Kazandın!", config.COLOR_OK
        else:
            result, color = "😈 Kaybettin!", config.COLOR_LEAVE
        e = discord.Embed(title="Taş • Kağıt • Makas", color=color,
                          description=f"Sen: {opts[choice]}\nBot: {opts[bot_choice]}\n\n**{result}**")
        for item in self.children:
            item.disabled = True
        self.stop()
        await interaction.response.edit_message(embed=e, view=self)

    @discord.ui.button(label="Taş", emoji="🪨", style=discord.ButtonStyle.secondary)
    async def tas(self, interaction, button):
        await self._play(interaction, "tas")

    @discord.ui.button(label="Kağıt", emoji="📄", style=discord.ButtonStyle.secondary)
    async def kagit(self, interaction, button):
        await self._play(interaction, "kagit")

    @discord.ui.button(label="Makas", emoji="✂️", style=discord.ButtonStyle.secondary)
    async def makas(self, interaction, button):
        await self._play(interaction, "makas")


class Eglence(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.playing: set[tuple[int, int]] = set()

    # ---------- profil ----------
    @commands.hybrid_command(name="avatar", description="Bir üyenin avatarını büyük göster", aliases=["av", "pp"])
    async def avatar(self, ctx: commands.Context, uye: discord.User = None):
        uye = uye or ctx.author
        e = discord.Embed(title=f"🖼️ {uye.display_name} avatarı", color=config.COLOR_INFO)
        e.set_image(url=uye.display_avatar.with_size(1024).url)
        e.description = f"[PNG]({uye.display_avatar.with_format('png').url}) • [WEBP]({uye.display_avatar.with_format('webp').url})"
        await ctx.send(embed=e)

    @commands.hybrid_command(name="banner", description="Bir üyenin profil bannerını göster")
    async def banner(self, ctx: commands.Context, uye: discord.User = None):
        uye = uye or ctx.author
        user = await self.bot.fetch_user(uye.id)
        if not user.banner:
            return await ctx.send("❌ Bu kullanıcının bannerı yok.", ephemeral=True)
        e = discord.Embed(title=f"🎨 {user.display_name} bannerı", color=config.COLOR_INFO)
        e.set_image(url=user.banner.with_size(1024).url)
        await ctx.send(embed=e)

    # ---------- şans oyunları ----------
    @commands.hybrid_command(name="zar", description="Zar at (varsayılan 6 yüzlü)")
    async def zar(self, ctx: commands.Context, yuz: commands.Range[int, 2, 1000] = 6):
        await ctx.send(f"🎲 {ctx.author.mention} **{yuz}** yüzlü zar attı: **{random.randint(1, yuz)}**")

    @commands.hybrid_command(name="yazitura", description="Yazı tura at", aliases=["yt"])
    async def yazitura(self, ctx: commands.Context):
        await ctx.send(f"🪙 {random.choice(['**Yazı**', '**Tura**'])} geldi!")

    @commands.hybrid_command(name="kure", description="Sihirli küreye evet/hayır sorusu sor", aliases=["8ball", "sihirlikure"])
    async def kure(self, ctx: commands.Context, *, soru: str):
        e = discord.Embed(color=config.COLOR_INFO)
        e.add_field(name="❓ Soru", value=soru[:500], inline=False)
        e.add_field(name="Cevap", value=random.choice(KURE), inline=False)
        await ctx.send(embed=e)

    @commands.hybrid_command(name="sec", description="Seçenekler arasından biri seçsin (| ile ayır)")
    async def sec(self, ctx: commands.Context, *, secenekler: str):
        opts = [o.strip() for o in re.split(r"[|,]", secenekler) if o.strip()]
        if len(opts) < 2:
            return await ctx.send("❌ En az 2 seçenek yaz. Örnek: `B!sec elma | armut | muz`", ephemeral=True)
        await ctx.send(f"🤔 Benim seçimim: **{random.choice(opts)}**")

    @commands.hybrid_command(name="tkm", description="Bota karşı taş kağıt makas oyna")
    async def tkm(self, ctx: commands.Context):
        e = discord.Embed(title="Taş • Kağıt • Makas", description="Seçimini yap!", color=config.COLOR_INFO)
        await ctx.send(embed=e, view=TkmView(ctx.author))

    @commands.hybrid_command(name="tahmin", description="1-100 arası sayıyı 7 hakta bulmaya çalış")
    @commands.guild_only()
    async def tahmin(self, ctx: commands.Context):
        key = (ctx.channel.id, ctx.author.id)
        if key in self.playing:
            return await ctx.send("❌ Zaten bu kanalda bir oyunun var.", ephemeral=True)
        self.playing.add(key)
        try:
            sayi, hak = random.randint(1, 100), 7
            await ctx.send(f"🔢 {ctx.author.mention} 1-100 arası bir sayı tuttum! **{hak}** hakkın var. Tahminlerini kanala yaz (60 sn).")

            def check(m: discord.Message):
                return m.author == ctx.author and m.channel == ctx.channel and m.content.isdigit()

            while hak > 0:
                try:
                    m = await self.bot.wait_for("message", check=check, timeout=60)
                except asyncio.TimeoutError:
                    return await ctx.send(f"⏰ Süre doldu! Sayı **{sayi}** idi.")
                n, hak = int(m.content), hak - 1
                if n == sayi:
                    return await ctx.send(f"🎉 Tebrikler {ctx.author.mention}, **{sayi}** sayısını buldun!")
                if hak:
                    await ctx.send(f"{'⬆️ Daha büyük' if n < sayi else '⬇️ Daha küçük'} • Kalan hak: **{hak}**")
            await ctx.send(f"😢 Bilemedin, sayı **{sayi}** idi.")
        finally:
            self.playing.discard(key)

    # ---------- eğlence ----------
    @commands.hybrid_command(name="ask", description="İki kişi arasındaki aşk uyumunu ölç", aliases=["ship", "aşk"])
    @commands.guild_only()
    async def ask(self, ctx: commands.Context, uye1: discord.Member, uye2: discord.Member = None):
        uye2 = uye2 or ctx.author
        pct = (uye1.id ^ uye2.id) % 101
        if pct >= 80:
            yorum = "Ruh eşi olabilirsiniz! 💍"
        elif pct >= 50:
            yorum = "Fena değil, umut var! 💕"
        elif pct >= 25:
            yorum = "Biraz çaba gerek. 🙂"
        else:
            yorum = "Şimdilik sadece arkadaş kalın. 😅"
        e = discord.Embed(title="💘 Aşk Ölçer", color=0xFF69B4,
                          description=f"{uye1.mention} ❤️ {uye2.mention}\n\n{bar(pct)} **%{pct}**\n{yorum}")
        await ctx.send(embed=e)

    @commands.hybrid_command(name="iq", description="Bugünkü IQ seviyeni öğren (eğlence)")
    async def iq(self, ctx: commands.Context, uye: discord.Member = None):
        uye = uye or ctx.author
        val = random.Random(f"iq{uye.id}{date.today()}").randint(60, 160)
        await ctx.send(f"🧠 {uye.mention} kişisinin bugünkü IQ'su: **{val}**")

    @commands.hybrid_command(name="sans", description="Bugünkü şans yüzdeni öğren (eğlence)")
    async def sans(self, ctx: commands.Context, uye: discord.Member = None):
        uye = uye or ctx.author
        pct = random.Random(f"sans{uye.id}{date.today()}").randint(0, 100)
        await ctx.send(f"🍀 {uye.mention} bugünkü şansın: {bar(pct)} **%{pct}**")

    @commands.hybrid_command(name="espri", description="Rastgele espri yap", aliases=["fıkra", "fikra"])
    async def espri(self, ctx: commands.Context):
        await ctx.send(f"😄 {random.choice(ESPRILER)}")

    @commands.hybrid_command(name="soz", description="Rastgele motivasyon sözü", aliases=["söz"])
    async def soz(self, ctx: commands.Context):
        await ctx.send(f"💬 *{random.choice(SOZLER)}*")

    @commands.hybrid_command(name="tokat", description="Birine tokat at")
    @commands.guild_only()
    async def tokat(self, ctx: commands.Context, uye: discord.Member):
        await ctx.send(random.choice(TOKAT).format(a=ctx.author.mention, b=uye.mention),
                       allowed_mentions=discord.AllowedMentions.none())

    @commands.hybrid_command(name="sarilma", description="Birine sarıl", aliases=["sarıl"])
    @commands.guild_only()
    async def sarilma(self, ctx: commands.Context, uye: discord.Member):
        await ctx.send(random.choice(SARIL).format(a=ctx.author.mention, b=uye.mention),
                       allowed_mentions=discord.AllowedMentions.none())

    @commands.hybrid_command(name="tersle", description="Yazıyı tersten yaz")
    async def tersle(self, ctx: commands.Context, *, metin: str):
        await ctx.send(discord.utils.escape_mentions(metin[::-1])[:1900])

    # ---------- Minecraft ----------
    @commands.hybrid_command(name="mcskin", description="Bir Minecraft oyuncusunun skinini göster")
    async def mcskin(self, ctx: commands.Context, isim: str):
        if not NAME_RE.match(isim):
            return await ctx.send("❌ Geçersiz Minecraft kullanıcı adı.", ephemeral=True)
        e = discord.Embed(title=f"🧍 {isim} skini", color=config.COLOR_OK,
                          description=f"[Skini indir](https://mc-heads.net/download/{isim}) • [NameMC](https://namemc.com/profile/{isim})")
        e.set_image(url=f"https://mc-heads.net/body/{isim}/right")
        e.set_thumbnail(url=f"https://mc-heads.net/avatar/{isim}/128")
        await ctx.send(embed=e)

    @commands.hybrid_command(name="mckafa", description="Bir Minecraft oyuncusunun kafasını göster")
    async def mckafa(self, ctx: commands.Context, isim: str):
        if not NAME_RE.match(isim):
            return await ctx.send("❌ Geçersiz Minecraft kullanıcı adı.", ephemeral=True)
        e = discord.Embed(title=f"🗿 {isim} kafası", color=config.COLOR_OK)
        e.set_image(url=f"https://mc-heads.net/avatar/{isim}/256")
        await ctx.send(embed=e)

    @commands.hybrid_command(name="mcoyuncu", description="Bir Minecraft oyuncusunun UUID'sini bul")
    async def mcoyuncu(self, ctx: commands.Context, isim: str):
        if not NAME_RE.match(isim):
            return await ctx.send("❌ Geçersiz Minecraft kullanıcı adı.", ephemeral=True)
        await ctx.defer()
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as s:
                async with s.get(f"https://api.mojang.com/users/profiles/minecraft/{isim}") as r:
                    if r.status != 200:
                        return await ctx.send("❌ Böyle bir Minecraft oyuncusu bulunamadı.")
                    data = await r.json(content_type=None)
        except Exception:
            return await ctx.send("❌ Mojang'a şu an ulaşılamıyor.")
        raw = data["id"]
        uuid = f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"
        e = discord.Embed(title=f"🎮 {data['name']}", color=config.COLOR_OK)
        e.add_field(name="UUID", value=f"`{uuid}`", inline=False)
        e.add_field(name="Bağlantılar", value=f"[NameMC](https://namemc.com/profile/{data['name']})")
        e.set_thumbnail(url=f"https://mc-heads.net/avatar/{data['name']}/128")
        await ctx.send(embed=e)

    @commands.hybrid_command(name="mcipucu", description="Rastgele Minecraft ipucu", aliases=["ipucu"])
    async def mcipucu(self, ctx: commands.Context):
        await ctx.send(f"⛏️ **Minecraft İpucu:** {random.choice(MC_IPUCLARI)}")


async def setup(bot):
    await bot.add_cog(Eglence(bot))
