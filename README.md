# BXProject-Bot

## 1) Bot oluştur
1. https://discord.com/developers/applications → **New Application** → **Bot** sekmesi → **Reset Token** (tokeni kopyala).
2. Aynı sayfada **Privileged Gateway Intents** altında şunları AÇ:
   - **Server Members Intent**
   - **Message Content Intent**
3. **OAuth2 → URL Generator**: scope `bot` + `applications.commands`, izin olarak **Administrator** (en kolayı) seç, çıkan linkle botu sunucuya ekle.
4. Sunucuda **bot rolünü** verilecek rollerin (abone rolü, otorol vs.) **üstüne** sürükle.

## 2) Müzik için FFmpeg kur
Müzik sistemi FFmpeg ister (bilgisayarda/VPS'te bir kez kurulur):
- Windows: `winget install ffmpeg` (ya da ffmpeg.org'dan indirip PATH'e ekle)
- Ubuntu/Debian: `sudo apt install ffmpeg libopus0`
- YouTube bir şeyi bozarsa: `pip install -U yt-dlp`

## 3) Kur ve çalıştır
```bash
pip install -r requirements.txt
cp .env.example .env     # Windows: copy .env.example .env
# .env dosyasını aç: DISCORD_TOKEN, ANTHROPIC_API_KEY, GUILD_ID doldur
python bot.py
```
Python 3.10+ gerekir. AI anahtarı: https://console.anthropic.com

## 4) Sunucuda ayarla (yönetici olarak)
| Komut | Ne yapar |
|---|---|
| `/gelengiden kur kanal` | Gelen-giden embed kanalı (hedef adımı 100) |
| `/ticket kur kanal kategori yetkili_rol [log_kanal]` | Destek paneli |
| `/abone kur kanal rol` | YouTube abone doğrulama |
| `/log kur kanal` | Mod log kanalı |
| `/automod ayarla` | Küfür/AI/davet/spam/etiket aç-kapat |
| `/mc ip-ayarla` , `/mc durum-kanali` | Minecraft IP + canlı oyuncu sayısı kanalı |
| `/seviye rol seviye rol` | Seviye ödül rolü |
| `/istatistik kanal [tur]` | Seçtiğin SES kanalını istatistik kanalı yapar (üye/insan/bot/boost/rol/kanal/minecraft) |
| `/müzik çal link-veya-isim` | YouTube, Spotify, SoundCloud linki ya da şarkı adı |
| `/yardim` | Tüm komutlar |

## Ön ek: B!
Yeni komutların çoğu hem `/komut` hem `B!komut` olarak çalışır (büyük/küçük harf fark etmez: `B!Avatar`, `b!avatar`).
Tüm komutları görmek için: `B!yardim`

| Kategori | Komutlar |
|---|---|
| Eğlence | `zar` `yazitura` `kure` `sec` `tkm` `tahmin` `ask` `iq` `sans` `espri` `soz` `tokat` `sarilma` `tersle` |
| Ekonomi | `bakiye` `gunluk` `calis` `gonder` `kumar` `zenginler` |
| Minecraft | `mcskin` `mckafa` `mcoyuncu` `mcipucu` `/mc durum` `/istatistik` |
| Araçlar | `avatar` `banner` `ping` `botbilgi` `davet` `kullanici` `sunucu` `rolbilgi` `kanalbilgi` `afk` `hatirlat` `hesapla` `qr` `hava` |
| AI | `cevir` `yapayzeka` (Anthropic API anahtarı gerekir) |
| Yönetim | `rolver` `rolal` `nick` `banliste` `oneri` `onerikanal` `/otocevap` `/rolpanel` |

## Notlar
- Discord bir bot için en fazla 100 slash komut izin verir; şu an 77 tane kullanılıyor.
- Bot 7/24 açık bir bilgisayar/VPS'te çalışmalı (`python bot.py` kapanınca bot kapanır).
- Veriler `data.db` (SQLite) dosyasında tutulur.
- Çekilişler bot yeniden başlarsa iptal olur.
- AI küfür filtresi her mesaj için küçük bir API çağrısı yapar (Haiku, çok ucuz). Maliyeti düşürmek için `/automod ayarla ai:False` yap; yerel filtre çalışmaya devam eder.
- Abone doğrulaması AI ile yapılır, %100 kesin değildir; ayrıca aynı görselin ikinci kez kullanılması engellenir. Şüpheli durumda `/abone onayla` ile elle verebilirsin.
- Spotify'dan ses çalınmaz; bot Spotify linkinden şarkı adını alıp YouTube'da arar. Tek şarkı linki anahtarsız da çalışır; albüm/playlist için `.env`'ye Spotify Client ID/Secret ekle.
- Bazı VPS/hosting IP'lerini YouTube engelleyebilir; ev bilgisayarında genelde sorun olmaz.
- `.env` dosyasını ve tokeni kimseyle paylaşma.
