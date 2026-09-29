from __future__ import annotations

import asyncio
import html
import logging
import random
import re
import time
from collections import deque
from dataclasses import dataclass

import aiohttp
import discord
import yt_dlp
from discord import app_commands
from discord.ext import commands

import config

log = logging.getLogger("mercia.music")

YDL_OPTS = {
    "format": "bestaudio/best",
    "quiet": True,
    "no_warnings": True,
    "noplaylist": True,
    "source_address": "0.0.0.0",
    "socket_timeout": 15,
}
FFMPEG_OPTS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}
MAX_QUEUE = 100
IDLE_TIMEOUT = 180
URL_RE = re.compile(r"^https?://", re.IGNORECASE)
SPOTIFY_RE = re.compile(r"open\.spotify\.com/(?:intl-[a-z]+/)?(track|album|playlist)/([A-Za-z0-9]+)")


def fmt_time(seconds) -> str:
    if not seconds:
        return "?"
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


async def respond(interaction: discord.Interaction, *args, **kwargs):
    if interaction.response.is_done():
        return await interaction.followup.send(*args, **kwargs)
    return await interaction.response.send_message(*args, **kwargs)


# ---------------- yt-dlp ----------------
def _extract(query: str, playlist: bool = False):
    opts = dict(YDL_OPTS)
    if playlist:
        opts.update(noplaylist=False, extract_flat="in_playlist", playlistend=50)
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(query, download=False)


async def extract(query: str, playlist: bool = False):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: _extract(query, playlist))


def first_entry(info):
    if info and "entries" in info:
        entries = [e for e in info["entries"] if e]
        if not entries:
            raise RuntimeError("Sonuç bulunamadı.")
        return entries[0]
    return info


@dataclass
class Track:
    title: str
    requester: discord.abc.User | None = None
    url: str | None = None
    search: str | None = None
    duration: int | None = None
    thumbnail: str | None = None
    stream_url: str | None = None
    resolved_at: float = 0.0

    def apply(self, info: dict):
        self.stream_url = info["url"]
        self.title = info.get("title") or self.title
        self.duration = info.get("duration") or self.duration
        self.thumbnail = info.get("thumbnail") or self.thumbnail
        self.url = info.get("webpage_url") or self.url
        self.resolved_at = time.monotonic()

    async def resolve(self):
        if self.stream_url and time.monotonic() - self.resolved_at < 1200:
            return
        info = first_entry(await extract(self.url or f"ytsearch1:{self.search}"))
        self.apply(info)


# ---------------- Spotify ----------------
class Spotify:
    def __init__(self):
        self.token: str | None = None
        self.expires = 0.0

    @property
    def enabled(self) -> bool:
        return bool(config.SPOTIFY_CLIENT_ID and config.SPOTIFY_CLIENT_SECRET)

    async def _auth(self, s: aiohttp.ClientSession):
        if self.token and time.time() < self.expires - 30:
            return
        async with s.post(
            "https://accounts.spotify.com/api/token",
            data={"grant_type": "client_credentials"},
            auth=aiohttp.BasicAuth(config.SPOTIFY_CLIENT_ID, config.SPOTIFY_CLIENT_SECRET),
        ) as r:
            data = await r.json()
        if "access_token" not in data:
            raise RuntimeError("Spotify anahtarları hatalı.")
        self.token = data["access_token"]
        self.expires = time.time() + data.get("expires_in", 3600)

    async def _get(self, s, url):
        async with s.get(url, headers={"Authorization": f"Bearer {self.token}"}) as r:
            if r.status != 200:
                raise RuntimeError(f"Spotify hatası ({r.status}). Playlist özel olabilir.")
            return await r.json()

    async def tracks(self, kind: str, sid: str) -> list[tuple[str, str]]:
        """[(şarkı adı, sanatçı)]"""
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as s:
            if self.enabled:
                await self._auth(s)
                api = "https://api.spotify.com/v1"
                if kind == "track":
                    d = await self._get(s, f"{api}/tracks/{sid}")
                    return [(d["name"], d["artists"][0]["name"])]
                if kind == "album":
                    d = await self._get(s, f"{api}/albums/{sid}")
                    return [(i["name"], i["artists"][0]["name"]) for i in d["tracks"]["items"][:50]]
                d = await self._get(s, f"{api}/playlists/{sid}/tracks?limit=50")
                return [(i["track"]["name"], i["track"]["artists"][0]["name"])
                        for i in d["items"] if i.get("track")]
            # anahtarsız yedek: sadece tek şarkı
            if kind != "track":
                raise RuntimeError("Spotify albüm/playlist için `.env` içine SPOTIFY_CLIENT_ID ve SPOTIFY_CLIENT_SECRET gerekli.")
            async with s.get(f"https://open.spotify.com/track/{sid}", headers={"User-Agent": "Mozilla/5.0"}) as r:
                page = await r.text()
            t = re.search(r'<meta property="og:title" content="([^"]+)"', page)
            d = re.search(r'<meta property="og:description" content="([^"]+)"', page)
            if not t or not d:
                raise RuntimeError("Spotify şarkısı okunamadı.")
            return [(html.unescape(t.group(1)), html.unescape(d.group(1)).split(" · ")[0])]


# ---------------- Oynatıcı ----------------
class MusicControls(discord.ui.View):
    def __init__(self, player: "Player"):
        super().__init__(timeout=None)
        self.player = player

    async def _ok(self, interaction: discord.Interaction) -> bool:
        vc = self.player.guild.voice_client
        if not vc or not interaction.user.voice or interaction.user.voice.channel != vc.channel:
            await interaction.response.send_message("❌ Önce botla aynı ses kanalına gir.", ephemeral=True)
            return False
        return True

    @discord.ui.button(emoji="⏯️", style=discord.ButtonStyle.secondary)
    async def toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._ok(interaction):
            return
        vc = self.player.guild.voice_client
        if vc.is_paused():
            vc.resume()
            await interaction.response.send_message("▶️ Devam ediyor.", ephemeral=True)
        else:
            vc.pause()
            await interaction.response.send_message("⏸️ Duraklatıldı.", ephemeral=True)

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.secondary)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._ok(interaction):
            return
        self.player.skip()
        await interaction.response.send_message("⏭️ Atlandı.", ephemeral=True)

    @discord.ui.button(emoji="⏹️", style=discord.ButtonStyle.danger)
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._ok(interaction):
            return
        await interaction.response.send_message("⏹️ Durduruldu, çıkıyorum.", ephemeral=True)
        self.player.task.cancel()


class Player:
    def __init__(self, cog: "Music", guild: discord.Guild, channel):
        self.cog = cog
        self.bot = cog.bot
        self.guild = guild
        self.text_channel = channel
        self.queue: deque[Track] = deque()
        self.current: Track | None = None
        self.loop = "off"  # off | track | queue
        self.volume = 0.5
        self.wakeup = asyncio.Event()
        self.next = asyncio.Event()
        self.skipping = False
        self.task = asyncio.create_task(self.run())

    def add(self, tracks: list[Track]):
        self.queue.extend(tracks)
        self.wakeup.set()

    def skip(self):
        vc = self.guild.voice_client
        if vc and (vc.is_playing() or vc.is_paused()):
            self.skipping = True
            vc.stop()

    def _after(self, error):
        if error:
            log.warning("Oynatma hatası: %s", error)
        self.bot.loop.call_soon_threadsafe(self.next.set)

    async def notify(self, text=None, **kwargs):
        try:
            await self.text_channel.send(text, **kwargs)
        except discord.HTTPException:
            pass

    async def run(self):
        try:
            while True:
                if not self.queue:
                    self.wakeup.clear()
                    try:
                        await asyncio.wait_for(self.wakeup.wait(), IDLE_TIMEOUT)
                    except asyncio.TimeoutError:
                        await self.notify("👋 Uzun süredir şarkı yok, kanaldan çıkıyorum.")
                        break
                    continue
                track = self.queue.popleft()
                self.current = track
                vc = self.guild.voice_client
                if not vc:
                    break
                try:
                    await track.resolve()
                    source = discord.PCMVolumeTransformer(
                        discord.FFmpegPCMAudio(track.stream_url, **FFMPEG_OPTS), volume=self.volume)
                except Exception as e:
                    log.warning("Şarkı hazırlanamadı: %s", e)
                    await self.notify(f"❌ **{track.title}** çalınamadı: `{str(e)[:150]}`")
                    self.current = None
                    continue
                self.next.clear()
                self.skipping = False
                vc.play(source, after=self._after)
                await self.announce(track)
                await self.next.wait()
                if not self.skipping:
                    if self.loop == "track":
                        self.queue.appendleft(track)
                    elif self.loop == "queue":
                        self.queue.append(track)
                self.current = None
        finally:
            self.current = None
            self.queue.clear()
            self.cog.players.pop(self.guild.id, None)
            vc = self.guild.voice_client
            if vc:
                try:
                    await vc.disconnect()
                except Exception:
                    pass

    async def announce(self, track: Track):
        e = discord.Embed(title="🎶 Şimdi çalıyor", color=config.COLOR_INFO,
                          description=f"[{track.title}]({track.url})" if track.url else track.title)
        e.add_field(name="Süre", value=fmt_time(track.duration))
        if track.requester:
            e.add_field(name="İsteyen", value=track.requester.mention)
        if track.thumbnail:
            e.set_thumbnail(url=track.thumbnail)
        await self.notify(embed=e, view=MusicControls(self))


# ---------------- Cog ----------------
class Music(commands.Cog):
    muzik = app_commands.Group(name="müzik", description="Müzik sistemi", guild_only=True)

    def __init__(self, bot):
        self.bot = bot
        self.players: dict[int, Player] = {}
        self.spotify = Spotify()

    async def cog_unload(self):
        for p in list(self.players.values()):
            p.task.cancel()

    # ---- yardımcılar ----
    async def build_tracks(self, query: str, requester) -> list[Track]:
        query = query.strip()
        m = SPOTIFY_RE.search(query)
        if m:
            pairs = await self.spotify.tracks(*m.groups())
            return [Track(title=f"{artist} - {name}", search=f"{artist} - {name}", requester=requester)
                    for name, artist in pairs]
        if URL_RE.match(query):
            is_playlist = ("list=" in query and "v=" not in query) or "/playlist" in query
            if is_playlist:
                info = await extract(query, playlist=True)
                out = []
                for e in info.get("entries", []):
                    if not e:
                        continue
                    url = e.get("url") or (f"https://www.youtube.com/watch?v={e['id']}" if e.get("id") else None)
                    if url:
                        out.append(Track(title=e.get("title") or "Bilinmeyen", url=url,
                                         duration=e.get("duration"), requester=requester))
                return out
            info = first_entry(await extract(query))
        else:
            info = first_entry(await extract(f"ytsearch1:{query}"))
        t = Track(title=info.get("title") or "Bilinmeyen", requester=requester)
        t.apply(info)
        return [t]

    async def join(self, interaction: discord.Interaction) -> Player | None:
        user, guild = interaction.user, interaction.guild
        if not user.voice or not user.voice.channel:
            await respond(interaction, "❌ Önce bir ses kanalına gir.", ephemeral=True)
            return None
        channel = user.voice.channel
        perms = channel.permissions_for(guild.me)
        if not (perms.connect and perms.speak):
            await respond(interaction, "❌ O kanalda bağlanma/konuşma iznim yok.", ephemeral=True)
            return None
        vc = guild.voice_client
        player = self.players.get(guild.id)
        if vc and vc.channel != channel:
            if vc.is_playing() or vc.is_paused():
                await respond(interaction, f"❌ Şu an {vc.channel.mention} kanalında çalıyorum.", ephemeral=True)
                return None
            await vc.move_to(channel)
        elif not vc:
            await channel.connect(self_deaf=True)
        if not player:
            player = Player(self, guild, interaction.channel)
            self.players[guild.id] = player
        return player

    async def get_player(self, interaction: discord.Interaction) -> Player | None:
        player = self.players.get(interaction.guild.id)
        vc = interaction.guild.voice_client
        if not player or not vc:
            await respond(interaction, "❌ Şu an bir şey çalmıyor.", ephemeral=True)
            return None
        if not interaction.user.voice or interaction.user.voice.channel != vc.channel:
            await respond(interaction, "❌ Botla aynı ses kanalında olmalısın.", ephemeral=True)
            return None
        return player

    # ---- komutlar ----
    @muzik.command(name="çal", description="YouTube/Spotify linki veya şarkı adıyla müzik çal")
    @app_commands.describe(sorgu="YouTube, Spotify, SoundCloud linki ya da şarkı adı")
    async def cal(self, interaction: discord.Interaction, sorgu: str):
        await interaction.response.defer()
        player = await self.join(interaction)
        if not player:
            return
        if len(player.queue) >= MAX_QUEUE:
            return await respond(interaction, f"❌ Kuyruk dolu (en fazla {MAX_QUEUE}).", ephemeral=True)
        try:
            tracks = await self.build_tracks(sorgu, interaction.user)
        except Exception as e:
            log.warning("Sorgu hatası: %s", e)
            return await respond(interaction, f"❌ Şarkı bulunamadı ya da okunamadı.\n`{str(e)[:200]}`", ephemeral=True)
        if not tracks:
            return await respond(interaction, "❌ Sonuç bulunamadı.", ephemeral=True)
        tracks = tracks[: MAX_QUEUE - len(player.queue)]
        player.text_channel = interaction.channel
        player.add(tracks)
        if len(tracks) == 1:
            t = tracks[0]
            e = discord.Embed(title="➕ Kuyruğa eklendi", color=config.COLOR_OK,
                              description=f"[{t.title}]({t.url})" if t.url else t.title)
            e.set_footer(text=f"Kuyrukta {len(player.queue)} şarkı")
        else:
            e = discord.Embed(title="➕ Çalma listesi eklendi", color=config.COLOR_OK,
                              description=f"**{len(tracks)}** şarkı kuyruğa eklendi.")
        await interaction.followup.send(embed=e)

    @muzik.command(name="duraklat", description="Müziği duraklat")
    async def duraklat(self, interaction: discord.Interaction):
        if player := await self.get_player(interaction):
            vc = interaction.guild.voice_client
            if vc.is_playing():
                vc.pause()
                return await interaction.response.send_message("⏸️ Duraklatıldı.")
            await interaction.response.send_message("❌ Çalan bir şey yok.", ephemeral=True)

    @muzik.command(name="devam", description="Duraklatılan müziği devam ettir")
    async def devam(self, interaction: discord.Interaction):
        if player := await self.get_player(interaction):
            vc = interaction.guild.voice_client
            if vc.is_paused():
                vc.resume()
                return await interaction.response.send_message("▶️ Devam ediyor.")
            await interaction.response.send_message("❌ Duraklatılmış bir şey yok.", ephemeral=True)

    @muzik.command(name="atla", description="Şarkıyı atla")
    async def atla(self, interaction: discord.Interaction):
        if player := await self.get_player(interaction):
            player.skip()
            await interaction.response.send_message("⏭️ Atlandı.")

    @muzik.command(name="dur", description="Müziği durdur, kuyruğu temizle ve kanaldan çık")
    async def dur(self, interaction: discord.Interaction):
        if player := await self.get_player(interaction):
            await interaction.response.send_message("⏹️ Durduruldu, çıkıyorum.")
            player.task.cancel()

    @muzik.command(name="kuyruk", description="Şarkı kuyruğunu göster")
    async def kuyruk(self, interaction: discord.Interaction):
        player = self.players.get(interaction.guild.id)
        if not player or (not player.current and not player.queue):
            return await interaction.response.send_message("📭 Kuyruk boş.", ephemeral=True)
        lines = []
        if player.current:
            lines.append(f"▶️ **{player.current.title}** `{fmt_time(player.current.duration)}`\n")
        for i, t in enumerate(list(player.queue)[:10], 1):
            lines.append(f"`{i}.` {t.title} `{fmt_time(t.duration)}`")
        if len(player.queue) > 10:
            lines.append(f"\n… ve **{len(player.queue) - 10}** şarkı daha")
        e = discord.Embed(title="📜 Kuyruk", description="\n".join(lines), color=config.COLOR_INFO)
        e.set_footer(text=f"Döngü: {player.loop} • Ses: %{int(player.volume * 100)}")
        await interaction.response.send_message(embed=e)

    @muzik.command(name="şimdi", description="Şu an çalan şarkıyı göster")
    async def simdi(self, interaction: discord.Interaction):
        player = self.players.get(interaction.guild.id)
        if not player or not player.current:
            return await interaction.response.send_message("❌ Şu an bir şey çalmıyor.", ephemeral=True)
        t = player.current
        e = discord.Embed(title="🎶 Şimdi çalıyor", color=config.COLOR_INFO,
                          description=f"[{t.title}]({t.url})" if t.url else t.title)
        e.add_field(name="Süre", value=fmt_time(t.duration))
        if t.requester:
            e.add_field(name="İsteyen", value=t.requester.mention)
        if t.thumbnail:
            e.set_thumbnail(url=t.thumbnail)
        await interaction.response.send_message(embed=e)

    @muzik.command(name="ses", description="Ses seviyesini ayarla (1-100)")
    async def ses(self, interaction: discord.Interaction, seviye: app_commands.Range[int, 1, 100]):
        if player := await self.get_player(interaction):
            player.volume = seviye / 100
            vc = interaction.guild.voice_client
            if isinstance(vc.source, discord.PCMVolumeTransformer):
                vc.source.volume = player.volume
            await interaction.response.send_message(f"🔊 Ses: **%{seviye}**")

    @muzik.command(name="döngü", description="Döngü modunu ayarla")
    @app_commands.choices(mod=[
        app_commands.Choice(name="Kapalı", value="off"),
        app_commands.Choice(name="Şarkı", value="track"),
        app_commands.Choice(name="Kuyruk", value="queue"),
    ])
    async def dongu(self, interaction: discord.Interaction, mod: app_commands.Choice[str]):
        if player := await self.get_player(interaction):
            player.loop = mod.value
            await interaction.response.send_message(f"🔁 Döngü: **{mod.name}**")

    @muzik.command(name="karıştır", description="Kuyruğu karıştır")
    async def karistir(self, interaction: discord.Interaction):
        if player := await self.get_player(interaction):
            items = list(player.queue)
            random.shuffle(items)
            player.queue = deque(items)
            await interaction.response.send_message("🔀 Kuyruk karıştırıldı.")

    @muzik.command(name="sil", description="Kuyruktan sıra numarasıyla şarkı sil")
    async def sil(self, interaction: discord.Interaction, sira: app_commands.Range[int, 1, 100]):
        if player := await self.get_player(interaction):
            if sira > len(player.queue):
                return await interaction.response.send_message("❌ Bu sırada şarkı yok.", ephemeral=True)
            items = list(player.queue)
            removed = items.pop(sira - 1)
            player.queue = deque(items)
            await interaction.response.send_message(f"🗑️ **{removed.title}** kuyruktan silindi.")

    @muzik.command(name="temizle", description="Kuyruğu temizle (çalan şarkı devam eder)")
    async def temizle(self, interaction: discord.Interaction):
        if player := await self.get_player(interaction):
            player.queue.clear()
            await interaction.response.send_message("🧹 Kuyruk temizlendi.")

    # ---- ses kanalı olayları ----
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        guild = member.guild
        player = self.players.get(guild.id)
        if not player:
            return
        if member.id == self.bot.user.id and after.channel is None:
            player.task.cancel()
            return
        vc = guild.voice_client
        if vc and vc.channel and before.channel == vc.channel and after.channel != vc.channel:
            if not any(not m.bot for m in vc.channel.members):
                await asyncio.sleep(60)
                vc = guild.voice_client
                p = self.players.get(guild.id)
                if p and vc and vc.channel and not any(not m.bot for m in vc.channel.members):
                    await p.notify("👋 Kanalda kimse kalmadı, çıkıyorum.")
                    p.task.cancel()


async def setup(bot):
    await bot.add_cog(Music(bot))
