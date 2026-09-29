from __future__ import annotations

from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands

import config
from utils import apply_warn_penalty, format_duration, parse_duration


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _check(self, interaction: discord.Interaction, target: discord.Member) -> str | None:
        guild = interaction.guild
        if target.id == interaction.user.id:
            return "Kendine bu işlemi yapamazsın."
        if target.id == guild.owner_id:
            return "Sunucu sahibine işlem yapılamaz."
        if target.id == self.bot.user.id:
            return "Bana işlem yapamazsın 😅"
        if interaction.user.id != guild.owner_id and target.top_role >= interaction.user.top_role:
            return "Bu kişinin rolü seninkinden yüksek veya eşit."
        if target.top_role >= guild.me.top_role:
            return "Bu kişinin rolü benim rolümden yüksek veya eşit."
        return None

    def _embed(self, title, color, target, mod, reason, extra=None) -> discord.Embed:
        e = discord.Embed(title=title, color=color)
        e.add_field(name="Kullanıcı", value=f"{target} ({target.id})", inline=False)
        e.add_field(name="Yetkili", value=mod.mention)
        if extra:
            e.add_field(name=extra[0], value=extra[1])
        e.add_field(name="Sebep", value=reason, inline=False)
        e.timestamp = discord.utils.utcnow()
        return e

    async def _dm(self, user, guild, text):
        try:
            await user.send(f"**{guild.name}** sunucusunda {text}")
        except discord.HTTPException:
            pass

    # ---------- ban / unban / kick ----------
    @app_commands.command(name="ban", description="Bir üyeyi banla")
    @app_commands.describe(uye="Banlanacak üye", sebep="Sebep", mesaj_sil_gun="Kaç günlük mesajı silinsin (0-7)")
    @app_commands.default_permissions(ban_members=True)
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.guild_only()
    async def ban(self, interaction: discord.Interaction, uye: discord.Member, sebep: str = "Belirtilmedi",
                  mesaj_sil_gun: app_commands.Range[int, 0, 7] = 0):
        if err := self._check(interaction, uye):
            return await interaction.response.send_message(f"❌ {err}", ephemeral=True)
        await self._dm(uye, interaction.guild, f"banlandın. Sebep: {sebep}")
        await uye.ban(reason=f"{interaction.user}: {sebep}", delete_message_days=mesaj_sil_gun)
        e = self._embed("🔨 Üye Banlandı", config.COLOR_LEAVE, uye, interaction.user, sebep)
        await interaction.response.send_message(embed=e)
        await self.bot.send_log(interaction.guild, e)

    @app_commands.command(name="unban", description="Bir kullanıcının banını kaldır")
    @app_commands.describe(kullanici_id="Kullanıcı ID'si", sebep="Sebep")
    @app_commands.default_permissions(ban_members=True)
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.guild_only()
    async def unban(self, interaction: discord.Interaction, kullanici_id: str, sebep: str = "Belirtilmedi"):
        try:
            uid = int(kullanici_id)
        except ValueError:
            return await interaction.response.send_message("❌ Geçerli bir kullanıcı ID'si gir.", ephemeral=True)
        try:
            await interaction.guild.unban(discord.Object(id=uid), reason=f"{interaction.user}: {sebep}")
        except discord.NotFound:
            return await interaction.response.send_message("❌ Bu kullanıcı banlı değil.", ephemeral=True)
        await interaction.response.send_message(f"✅ `{uid}` kullanıcısının banı kaldırıldı.")

    @app_commands.command(name="kick", description="Bir üyeyi sunucudan at")
    @app_commands.describe(uye="Atılacak üye", sebep="Sebep")
    @app_commands.default_permissions(kick_members=True)
    @app_commands.checks.has_permissions(kick_members=True)
    @app_commands.guild_only()
    async def kick(self, interaction: discord.Interaction, uye: discord.Member, sebep: str = "Belirtilmedi"):
        if err := self._check(interaction, uye):
            return await interaction.response.send_message(f"❌ {err}", ephemeral=True)
        await self._dm(uye, interaction.guild, f"atıldın. Sebep: {sebep}")
        await uye.kick(reason=f"{interaction.user}: {sebep}")
        e = self._embed("👢 Üye Atıldı", config.COLOR_WARN, uye, interaction.user, sebep)
        await interaction.response.send_message(embed=e)
        await self.bot.send_log(interaction.guild, e)

    # ---------- mute / unmute ----------
    @app_commands.command(name="mute", description="Bir üyeyi sustur (timeout)")
    @app_commands.describe(uye="Susturulacak üye", sure="Süre: 30sn, 10dk, 2sa, 1g (en fazla 28g)", sebep="Sebep")
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.guild_only()
    async def mute(self, interaction: discord.Interaction, uye: discord.Member, sure: str, sebep: str = "Belirtilmedi"):
        if err := self._check(interaction, uye):
            return await interaction.response.send_message(f"❌ {err}", ephemeral=True)
        dur = parse_duration(sure)
        if not dur or dur > timedelta(days=28):
            return await interaction.response.send_message(
                "❌ Geçersiz süre. Örnek: `30sn`, `10dk`, `2sa`, `1g` (en fazla 28 gün)", ephemeral=True)
        await uye.timeout(dur, reason=f"{interaction.user}: {sebep}")
        await self._dm(uye, interaction.guild, f"{format_duration(dur)} susturuldun. Sebep: {sebep}")
        e = self._embed("🔇 Üye Susturuldu", config.COLOR_WARN, uye, interaction.user, sebep, ("Süre", format_duration(dur)))
        await interaction.response.send_message(embed=e)
        await self.bot.send_log(interaction.guild, e)

    @app_commands.command(name="unmute", description="Susturmayı kaldır")
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.guild_only()
    async def unmute(self, interaction: discord.Interaction, uye: discord.Member):
        await uye.timeout(None, reason=f"{interaction.user} kaldırdı")
        await interaction.response.send_message(f"✅ {uye.mention} kullanıcısının susturması kaldırıldı.")

    # ---------- uyarı sistemi ----------
    @app_commands.command(name="uyar", description="Bir üyeyi uyar")
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.guild_only()
    async def uyar(self, interaction: discord.Interaction, uye: discord.Member, sebep: str = "Belirtilmedi"):
        if err := self._check(interaction, uye):
            return await interaction.response.send_message(f"❌ {err}", ephemeral=True)
        count = await self.bot.db.add_warn(interaction.guild.id, uye.id, interaction.user.id, sebep)
        dur = await apply_warn_penalty(uye, count)
        await self._dm(uye, interaction.guild, f"uyarıldın ({count}. uyarı). Sebep: {sebep}")
        e = self._embed("⚠️ Üye Uyarıldı", config.COLOR_WARN, uye, interaction.user, sebep, ("Toplam uyarı", str(count)))
        if dur:
            e.add_field(name="Otomatik ceza", value=f"{format_duration(dur)} mute", inline=False)
        await interaction.response.send_message(embed=e)
        await self.bot.send_log(interaction.guild, e)

    @app_commands.command(name="uyarilar", description="Bir üyenin uyarılarını göster")
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.guild_only()
    async def uyarilar(self, interaction: discord.Interaction, uye: discord.Member):
        rows = await self.bot.db.get_warns(interaction.guild.id, uye.id)
        if not rows:
            return await interaction.response.send_message(f"✅ {uye.mention} kullanıcısının uyarısı yok.", ephemeral=True)
        desc = "\n".join(f"**#{wid}** • <@{mid}> • {when[:10]}\n└ {reason}" for wid, mid, reason, when in rows)
        e = discord.Embed(title=f"⚠️ {uye.display_name} uyarıları", description=desc, color=config.COLOR_WARN)
        await interaction.response.send_message(embed=e, ephemeral=True)

    @app_commands.command(name="uyari-sil", description="Uyarıyı ID ile sil")
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.guild_only()
    async def uyari_sil(self, interaction: discord.Interaction, uyari_id: int):
        n = await self.bot.db.delete_warn(interaction.guild.id, uyari_id)
        await interaction.response.send_message("✅ Uyarı silindi." if n else "❌ Bu ID'de uyarı yok.", ephemeral=True)

    @app_commands.command(name="uyari-temizle", description="Bir üyenin tüm uyarılarını sil")
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.guild_only()
    async def uyari_temizle(self, interaction: discord.Interaction, uye: discord.Member):
        n = await self.bot.db.clear_warns(interaction.guild.id, uye.id)
        await interaction.response.send_message(f"✅ {n} uyarı silindi.", ephemeral=True)

    # ---------- kanal araçları ----------
    @app_commands.command(name="temizle", description="Mesajları toplu sil")
    @app_commands.describe(miktar="Silinecek mesaj sayısı (1-100)", uye="Sadece bu üyenin mesajları")
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.guild_only()
    async def temizle(self, interaction: discord.Interaction, miktar: app_commands.Range[int, 1, 100],
                      uye: discord.Member | None = None):
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=miktar, check=lambda m: uye is None or m.author.id == uye.id)
        await interaction.followup.send(f"🧹 {len(deleted)} mesaj silindi.", ephemeral=True)

    @app_commands.command(name="kilitle", description="Kanalı kilitle")
    @app_commands.default_permissions(manage_channels=True)
    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.guild_only()
    async def kilitle(self, interaction: discord.Interaction, kanal: discord.TextChannel | None = None):
        kanal = kanal or interaction.channel
        ow = kanal.overwrites_for(interaction.guild.default_role)
        ow.send_messages = False
        await kanal.set_permissions(interaction.guild.default_role, overwrite=ow)
        await interaction.response.send_message(f"🔒 {kanal.mention} kilitlendi.")

    @app_commands.command(name="kilit-ac", description="Kanal kilidini aç")
    @app_commands.default_permissions(manage_channels=True)
    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.guild_only()
    async def kilit_ac(self, interaction: discord.Interaction, kanal: discord.TextChannel | None = None):
        kanal = kanal or interaction.channel
        ow = kanal.overwrites_for(interaction.guild.default_role)
        ow.send_messages = None
        await kanal.set_permissions(interaction.guild.default_role, overwrite=ow)
        await interaction.response.send_message(f"🔓 {kanal.mention} kilidi açıldı.")

    @app_commands.command(name="yavasmod", description="Kanala yavaş mod koy (0 = kapat)")
    @app_commands.default_permissions(manage_channels=True)
    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.guild_only()
    async def yavasmod(self, interaction: discord.Interaction, saniye: app_commands.Range[int, 0, 21600],
                       kanal: discord.TextChannel | None = None):
        kanal = kanal or interaction.channel
        await kanal.edit(slowmode_delay=saniye)
        await interaction.response.send_message(
            f"🐌 {kanal.mention} yavaş modu: **{saniye}sn**" if saniye else f"✅ {kanal.mention} yavaş modu kapatıldı.")


async def setup(bot):
    await bot.add_cog(Moderation(bot))
