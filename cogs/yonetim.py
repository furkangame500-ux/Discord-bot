from __future__ import annotations

import json
import re
import time

import discord
from discord import app_commands
from discord.ext import commands

import config

DANGEROUS = ("administrator", "manage_guild", "manage_roles", "manage_channels", "manage_messages",
             "ban_members", "kick_members", "moderate_members", "mention_everyone", "manage_webhooks")


class RoleButton(discord.ui.DynamicItem[discord.ui.Button], template=r"mercia:rr:(?P<id>[0-9]+)"):
    def __init__(self, role_id: int, label: str = "Rol"):
        super().__init__(discord.ui.Button(label=label[:80], style=discord.ButtonStyle.primary,
                                           custom_id=f"mercia:rr:{role_id}"))
        self.role_id = role_id

    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Button, match: re.Match[str], /):
        return cls(int(match["id"]), item.label or "Rol")

    async def callback(self, interaction: discord.Interaction):
        role = interaction.guild.get_role(self.role_id)
        if not role:
            return await interaction.response.send_message("❌ Bu rol artık yok.", ephemeral=True)
        member = interaction.user
        try:
            if role in member.roles:
                await member.remove_roles(role, reason="Rol paneli")
                msg = f"➖ {role.mention} rolü alındı."
            else:
                await member.add_roles(role, reason="Rol paneli")
                msg = f"➕ {role.mention} rolü verildi."
        except discord.HTTPException:
            msg = "❌ Rolü ayarlayamadım (yetkim yetersiz)."
        await interaction.response.send_message(msg, ephemeral=True)


class Yonetim(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.resp_cd: dict[int, float] = {}

    async def cog_load(self):
        self.bot.add_dynamic_items(RoleButton)

    def _role_error(self, ctx: commands.Context, rol: discord.Role) -> str | None:
        if rol.managed or rol.is_default():
            return "Bu rol elle verilemez."
        if ctx.author.id != ctx.guild.owner_id and rol >= ctx.author.top_role:
            return "Bu rol senin rolünden yüksek veya eşit."
        if rol >= ctx.guild.me.top_role:
            return "Bu rol benim rolümden yüksek veya eşit."
        return None

    # ---------- rol / takma ad ----------
    @commands.hybrid_command(name="rolver", description="Bir üyeye rol ver")
    @commands.has_permissions(manage_roles=True)
    @commands.guild_only()
    async def rolver(self, ctx: commands.Context, uye: discord.Member, rol: discord.Role):
        if err := self._role_error(ctx, rol):
            return await ctx.send(f"❌ {err}", ephemeral=True)
        await uye.add_roles(rol, reason=f"{ctx.author} verdi")
        await ctx.send(f"✅ {uye.mention} kişisine {rol.mention} rolü verildi.", allowed_mentions=discord.AllowedMentions.none())

    @commands.hybrid_command(name="rolal", description="Bir üyeden rol al")
    @commands.has_permissions(manage_roles=True)
    @commands.guild_only()
    async def rolal(self, ctx: commands.Context, uye: discord.Member, rol: discord.Role):
        if err := self._role_error(ctx, rol):
            return await ctx.send(f"❌ {err}", ephemeral=True)
        await uye.remove_roles(rol, reason=f"{ctx.author} aldı")
        await ctx.send(f"✅ {uye.mention} kişisinden {rol.mention} rolü alındı.", allowed_mentions=discord.AllowedMentions.none())

    @commands.hybrid_command(name="nick", description="Bir üyenin takma adını değiştir (boş = sıfırla)")
    @commands.has_permissions(manage_nicknames=True)
    @commands.guild_only()
    async def nick(self, ctx: commands.Context, uye: discord.Member, *, isim: str = None):
        if uye.id == ctx.guild.owner_id or (ctx.author.id != ctx.guild.owner_id and uye.top_role >= ctx.author.top_role) \
                or uye.top_role >= ctx.guild.me.top_role:
            return await ctx.send("❌ Bu kişinin takma adını değiştiremem.", ephemeral=True)
        await uye.edit(nick=isim[:32] if isim else None, reason=f"{ctx.author}")
        await ctx.send(f"✅ {uye.mention} takma adı: **{isim[:32] if isim else 'sıfırlandı'}**",
                       allowed_mentions=discord.AllowedMentions.none())

    @commands.hybrid_command(name="banliste", description="Banlı kullanıcıları göster")
    @commands.has_permissions(ban_members=True)
    @commands.guild_only()
    async def banliste(self, ctx: commands.Context):
        await ctx.defer(ephemeral=True)
        lines = []
        async for entry in ctx.guild.bans(limit=25):
            lines.append(f"`{entry.user.id}` **{entry.user}** — {(entry.reason or 'Sebep yok')[:60]}")
        await ctx.send("\n".join(lines) or "✅ Banlı kimse yok.", ephemeral=True)

    # ---------- öneri ----------
    @commands.hybrid_command(name="onerikanal", description="Önerilerin gönderileceği kanalı ayarla")
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def onerikanal(self, ctx: commands.Context, kanal: discord.TextChannel):
        await self.bot.db.set(ctx.guild.id, "suggest_channel", kanal.id)
        await ctx.send(f"✅ Öneri kanalı: {kanal.mention}", ephemeral=True)

    @commands.hybrid_command(name="oneri", description="Sunucuya bir öneride bulun", aliases=["öneri"])
    @commands.guild_only()
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def oneri(self, ctx: commands.Context, *, metin: str):
        ch_id = await self.bot.db.get_int(ctx.guild.id, "suggest_channel")
        ch = ctx.guild.get_channel(ch_id) if ch_id else None
        if not ch:
            return await ctx.send("❌ Öneri kanalı ayarlanmamış (`/onerikanal`).", ephemeral=True)
        e = discord.Embed(title="💡 Yeni Öneri", description=metin[:1800], color=config.COLOR_JOIN)
        e.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
        e.timestamp = discord.utils.utcnow()
        msg = await ch.send(embed=e)
        for em in ("👍", "👎"):
            await msg.add_reaction(em)
        await ctx.send("✅ Önerin gönderildi, teşekkürler!", ephemeral=True)

    # ---------- otomatik cevap ----------
    async def _resp(self, guild) -> dict:
        try:
            return json.loads(await self.bot.db.get(guild.id, "autoresp", "{}"))
        except ValueError:
            return {}

    @commands.hybrid_group(name="otocevap", fallback="liste", description="Otomatik cevapları listele")
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def otocevap(self, ctx: commands.Context):
        data = await self._resp(ctx.guild)
        if not data:
            return await ctx.send("Henüz otomatik cevap yok. Eklemek için `/otocevap ekle`", ephemeral=True)
        lines = [f"`{k}` → {v[:80]}" for k, v in data.items()]
        await ctx.send("\n".join(lines)[:1900], ephemeral=True)

    @otocevap.command(name="ekle", description="Bir kelimeye otomatik cevap ekle")
    @app_commands.describe(tetik="Yazılınca cevap verilecek mesaj (örn: ip)", cevap="Botun vereceği cevap")
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def otocevap_ekle(self, ctx: commands.Context, tetik: str, *, cevap: str):
        data = await self._resp(ctx.guild)
        if len(data) >= 50 and tetik.lower() not in data:
            return await ctx.send("❌ En fazla 50 otomatik cevap eklenebilir.", ephemeral=True)
        data[tetik.lower().strip()] = cevap[:1500]
        await self.bot.db.set(ctx.guild.id, "autoresp", json.dumps(data))
        await ctx.send(f"✅ `{tetik}` yazılınca artık cevap vereceğim.", ephemeral=True)

    @otocevap.command(name="sil", description="Otomatik cevabı sil")
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def otocevap_sil(self, ctx: commands.Context, tetik: str):
        data = await self._resp(ctx.guild)
        if data.pop(tetik.lower().strip(), None) is None:
            return await ctx.send("❌ Böyle bir otomatik cevap yok.", ephemeral=True)
        await self.bot.db.set(ctx.guild.id, "autoresp", json.dumps(data) if data else None)
        await ctx.send("✅ Silindi.", ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild or not message.content:
            return
        data = await self._resp(message.guild)
        reply = data.get(message.content.lower().strip())
        if not reply:
            return
        now = time.monotonic()
        if now - self.resp_cd.get(message.channel.id, 0) < 5:
            return
        self.resp_cd[message.channel.id] = now
        try:
            await message.reply(reply, mention_author=False, allowed_mentions=discord.AllowedMentions.none())
        except discord.HTTPException:
            pass

    # ---------- rol paneli ----------
    @app_commands.command(name="rolpanel", description="Butonla rol alınan bir panel oluştur")
    @app_commands.describe(baslik="Panel başlığı", rol1="1. rol", rol2="2. rol", rol3="3. rol", rol4="4. rol", rol5="5. rol")
    @app_commands.default_permissions(manage_roles=True)
    @app_commands.checks.has_permissions(manage_roles=True)
    @app_commands.guild_only()
    async def rolpanel(self, interaction: discord.Interaction, baslik: str, rol1: discord.Role,
                       rol2: discord.Role | None = None, rol3: discord.Role | None = None,
                       rol4: discord.Role | None = None, rol5: discord.Role | None = None):
        roles = [r for r in (rol1, rol2, rol3, rol4, rol5) if r]
        for r in roles:
            if r.managed or r >= interaction.guild.me.top_role:
                return await interaction.response.send_message(
                    f"❌ {r.mention} rolünü veremem (botun rolü daha altta).", ephemeral=True)
            perms = r.permissions
            if any(getattr(perms, p) for p in DANGEROUS):
                return await interaction.response.send_message(
                    f"❌ {r.mention} yetkili bir rol, herkese açık panele konamaz.", ephemeral=True)
        view = discord.ui.View(timeout=None)
        for r in roles:
            view.add_item(RoleButton(r.id, r.name))
        e = discord.Embed(title=f"🎭 {baslik}", description="İstediğin role tıkla, tekrar tıklarsan geri alınır.",
                          color=config.COLOR_INFO)
        e.set_footer(text=config.BRAND)
        await interaction.channel.send(embed=e, view=view)
        await interaction.response.send_message("✅ Rol paneli oluşturuldu.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Yonetim(bot))
