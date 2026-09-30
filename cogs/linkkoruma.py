from __future__ import annotations

import json
import logging
import re
import time
from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands

import config
from utils import apply_warn_penalty, format_duration

log = logging.getLogger("mercia.linkkoruma")

DOT = r"\s*(?:\.|\(dot\)|\[dot\]|\bdot\b)\s*"
SLASH = r"\s*/\s*"
INVITE_RE = re.compile(
    rf"(?:discord(?:app)?{DOT}gg|discord(?:app)?{DOT}com{SLASH}invite|dsc{DOT}gg"
    rf"|discord{DOT}(?:me|li|io)|invite{DOT}gg){SLASH}([A-Za-z0-9-]{{2,32}})",
    re.IGNORECASE,
)
INVISIBLE_RE = re.compile(r"[\u200b-\u200f\u2060\ufeff\u00ad]")
NOT_FOUND, ERROR = 0, -1


def _ints(raw: str | None) -> list[int]:
    try:
        return [int(x) for x in json.loads(raw or "[]")]
    except (ValueError, TypeError):
        return []


class LinkKoruma(commands.Cog):
    linkkoruma = app_commands.Group(
        name="linkkoruma", description="Başka sunucuların davet linkini engelle", guild_only=True,
        default_permissions=discord.Permissions(manage_guild=True),
    )

    def __init__(self, bot):
        self.bot = bot
        self.cache: dict[str, tuple[int, float]] = {}

    # ---------- yardımcılar ----------
    async def resolve(self, code: str) -> int:
        """Davetin ait olduğu sunucu ID'si. 0 = geçersiz davet, -1 = Discord'a ulaşılamadı."""
        hit = self.cache.get(code)
        if hit and time.monotonic() - hit[1] < 600:
            return hit[0]
        try:
            inv = await self.bot.fetch_invite(code, with_counts=False, with_expiration=False)
            gid = inv.guild.id if inv.guild else NOT_FOUND
        except discord.NotFound:
            gid = NOT_FOUND
        except discord.HTTPException:
            return ERROR
        if len(self.cache) > 1000:
            self.cache.clear()
        self.cache[code] = (gid, time.monotonic())
        return gid

    async def cfg(self, guild: discord.Guild) -> dict:
        raw = await self.bot.db.get_prefix(guild.id, "lk_")
        return {
            "enabled": raw.get("lk_enabled", "1") == "1",
            "action": raw.get("lk_action", "uyar"),
            "channels": _ints(raw.get("lk_channels")),
            "roles": _ints(raw.get("lk_roles")),
            "guilds": _ints(raw.get("lk_guilds")),
        }

    async def toggle(self, guild_id: int, key: str, value: int) -> bool:
        items = _ints(await self.bot.db.get(guild_id, key, "[]"))
        if value in items:
            items.remove(value)
            added = False
        else:
            items.append(value)
            added = True
        await self.bot.db.set(guild_id, key, json.dumps(items) if items else None)
        return added

    # ---------- kontrol ----------
    async def check(self, message: discord.Message):
        if message.author.bot or not message.guild or not message.content:
            return
        member = message.author
        if not isinstance(member, discord.Member):
            return
        perms = member.guild_permissions
        if perms.administrator or perms.manage_guild or perms.manage_messages:
            return
        content = INVISIBLE_RE.sub("", message.content)
        codes = {m.group(1) for m in INVITE_RE.finditer(content)}
        if not codes:
            return
        cfg = await self.cfg(message.guild)
        if not cfg["enabled"]:
            return
        if {message.channel.id, getattr(message.channel, "parent_id", None)} & set(cfg["channels"]):
            return
        if any(r.id in cfg["roles"] for r in member.roles):
            return
        bad = []
        for code in codes:
            gid = await self.resolve(code)
            if gid == ERROR or gid == message.guild.id or gid in cfg["guilds"]:
                continue
            bad.append(code)
        if bad:
            await self.punish(message, cfg["action"], bad)

    async def punish(self, message: discord.Message, action: str, codes: list[str]):
        member = message.author
        try:
            await message.delete()
        except discord.HTTPException:
            pass
        extra = ""
        if action == "uyar":
            count = await self.bot.db.add_warn(message.guild.id, member.id, self.bot.user.id,
                                               "Başka sunucunun davet linkini paylaşmak")
            dur = await apply_warn_penalty(member, count)
            extra = f"\nToplam uyarı: **{count}**" + (f" • {format_duration(dur)} mute" if dur else "")
        elif action == "mute":
            try:
                await member.timeout(timedelta(minutes=10), reason="Başka sunucu daveti paylaştı")
                extra = "\n10 dakika susturuldu"
            except discord.HTTPException:
                pass
        try:
            await message.channel.send(
                f"🚫 {member.mention} başka sunucuların davet linkini paylaşmak yasak!", delete_after=8)
        except discord.HTTPException:
            pass
        e = discord.Embed(title="🔗 Davet Linki Engellendi", color=config.COLOR_WARN,
                          description=f"{member.mention} • {message.channel.mention}{extra}")
        e.add_field(name="Davet kodu", value=", ".join(f"`{c}`" for c in codes)[:1000], inline=False)
        await self.bot.send_log(message.guild, e)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        await self.check(message)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.content != after.content:
            await self.check(after)

    # ---------- komutlar ----------
    @linkkoruma.command(name="durum", description="Link korumasının durumunu göster")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def durum(self, interaction: discord.Interaction):
        cfg = await self.cfg(interaction.guild)
        actions = {"sil": "Sadece sil", "uyar": "Sil + uyarı", "mute": "Sil + 10 dk mute"}
        e = discord.Embed(title="🔗 Link Koruması", color=config.COLOR_INFO)
        e.add_field(name="Durum", value="✅ Açık" if cfg["enabled"] else "❌ Kapalı")
        e.add_field(name="Ceza", value=actions.get(cfg["action"], cfg["action"]))
        e.add_field(name="İzinli kanallar", value=" ".join(f"<#{i}>" for i in cfg["channels"]) or "Yok", inline=False)
        e.add_field(name="İzinli roller", value=" ".join(f"<@&{i}>" for i in cfg["roles"]) or "Yok", inline=False)
        e.add_field(name="İzinli sunucular", value=", ".join(f"`{i}`" for i in cfg["guilds"]) or "Yok (bu sunucu her zaman izinli)", inline=False)
        await interaction.response.send_message(embed=e, ephemeral=True)

    @linkkoruma.command(name="ayarla", description="Korumayı aç/kapat ve cezayı seç")
    @app_commands.describe(acik="Koruma açık olsun mu?", ceza="Davet atana ne yapılsın?")
    @app_commands.choices(ceza=[
        app_commands.Choice(name="Sadece mesajı sil", value="sil"),
        app_commands.Choice(name="Sil + uyarı ver (varsayılan)", value="uyar"),
        app_commands.Choice(name="Sil + 10 dakika sustur", value="mute"),
    ])
    @app_commands.checks.has_permissions(manage_guild=True)
    async def ayarla(self, interaction: discord.Interaction, acik: bool | None = None,
                     ceza: app_commands.Choice[str] | None = None):
        if acik is not None:
            await self.bot.db.set(interaction.guild.id, "lk_enabled", "1" if acik else "0")
        if ceza is not None:
            await self.bot.db.set(interaction.guild.id, "lk_action", ceza.value)
        await self.durum.callback(self, interaction)

    @linkkoruma.command(name="kanal", description="Kanalı izinli listesine ekle/çıkar (tekrar yazınca çıkarır)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def kanal(self, interaction: discord.Interaction, kanal: discord.TextChannel):
        added = await self.toggle(interaction.guild.id, "lk_channels", kanal.id)
        await interaction.response.send_message(
            f"✅ {kanal.mention} artık davet linkine **izinli**." if added else f"✅ {kanal.mention} izinli listesinden çıkarıldı.",
            ephemeral=True)

    @linkkoruma.command(name="rol", description="Rolü izinli listesine ekle/çıkar (tekrar yazınca çıkarır)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def rol(self, interaction: discord.Interaction, rol: discord.Role):
        added = await self.toggle(interaction.guild.id, "lk_roles", rol.id)
        await interaction.response.send_message(
            f"✅ {rol.mention} rolü artık davet linkine **izinli**." if added else f"✅ {rol.mention} izinli listesinden çıkarıldı.",
            ephemeral=True, allowed_mentions=discord.AllowedMentions.none())

    @linkkoruma.command(name="sunucu", description="Başka bir sunucunun davetini izinli yap (ortak/partner sunucu)")
    @app_commands.describe(davet="O sunucuya ait bir davet linki veya kodu")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def sunucu(self, interaction: discord.Interaction, davet: str):
        await interaction.response.defer(ephemeral=True)
        m = INVITE_RE.search(davet)
        code = m.group(1) if m else davet.strip().rstrip("/").split("/")[-1]
        gid = await self.resolve(code)
        if gid <= 0:
            return await interaction.followup.send("❌ Geçerli bir davet bulunamadı.", ephemeral=True)
        added = await self.toggle(interaction.guild.id, "lk_guilds", gid)
        await interaction.followup.send(
            f"✅ Sunucu `{gid}` artık **izinli** (partner)." if added else f"✅ Sunucu `{gid}` izinli listesinden çıkarıldı.",
            ephemeral=True)


async def setup(bot):
    await bot.add_cog(LinkKoruma(bot))
