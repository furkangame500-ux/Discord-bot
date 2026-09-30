# BXProject-bot

Türkçe Discord botu: moderasyon, ticket, müzik, AI küfür filtresi, abone doğrulama, ekonomi, eğlence ve daha fazlası.
Önek: **B!** (büyük/küçük harf fark etmez) veya `/` ile kullanılır. Tüm komutlar: `B!yardim`

## 1) Discord'da bot oluştur
1. https://discord.com/developers/applications → **New Application** → adı `BXProject-bot` yap → **Bot** sekmesi → **Reset Token** (tokeni kopyala).
2. Aynı sayfada **Privileged Gateway Intents** altında şunları AÇ:
   - **Server Members Intent**
   - **Message Content Intent**
3. **OAuth2 → URL Generator**: scope `bot` + `applications.commands`, izin olarak **Administrator** seç, çıkan linkle botu sunucuya ekle.
4. Sunucuda **bot rolünü** verilecek rollerin (abone rolü, otorol, rol paneli) **üstüne** sürükle.

## 2) Bilgisayara kurulacaklar
- **Python 3.10+**
- **FFmpeg** (müzik için): Windows `winget install ffmpeg` • Ubuntu/Debian `sudo apt install ffmpeg libopus0`
- **Deno** (YouTube için, yt-dlp artık bunu istiyor): Windows `winget install DenoLand.Deno` • Linux/Mac `curl -fsSL https://deno.land/install.sh | sh`

## 3) Kur ve çalıştır
```bash
pip install -r requirements.txt
cp .env.example .env     # Windows: copy .env.example .env
# .env dosyasını aç: DISCORD_TOKEN, ANTHROPIC_API_KEY, GUILD_ID doldur
python bot.py
```
AI anahtarı: https://console.anthropic.com (küfür filtresi, abone doğrulama, `B!cevir`, `B!yapayzeka` için)

> **Müzik notu:** Discord, Mart 2026'dan beri ses kanallarında DAVE şifrelemesini zorunlu tutuyor.
> Bunun için `discord.py 2.7.1+` ve `davey` paketi gerekir (requirements.txt'de var).
> Ses kanalına bağlanamazsa: `pip install -U "discord.py[voice]" davey`
> YouTube bir şeyi bozarsa: `pip install -U "yt-dlp[default]"`

## 4) Sunucuda ayarla (yönetici olarak)
| Komut | Ne yapar |
|---|---|
| `/gelengiden kur kanal` | Gelen-giden embed kanalı (hedef adımı 100) |
| `/ticket kur kanal kategori yetkili_rol [log_kanal]` | Destek paneli |
| `/abone kur kanal rol` | YouTube abone doğrulama |
| `/log kur kanal` | Mod log kanalı |
| `/automod ayarla` | Küfür/AI/spam/etiket aç-kapat |
| `/linkkoruma durum/ayarla/kanal/rol/sunucu` | Başka sunucu daveti engeli + izinli kanal/rol/partner sunucu |
| `/menu oluştur kanal aciklama link` | Açıklamalı, link butonlu menü mesajı |
| `/istatistik kanal [tur]` | Seçtiğin SES kanalını istatistik kanalı yapar |
| `/mc ip-ayarla`, `/mc durum-kanali` | Minecraft sunucu IP'si + canlı oyuncu sayısı kanalı |
| `/seviye rol seviye rol` | Seviye ödül rolü |
| `/rolpanel`, `/otocevap`, `B!onerikanal` | Rol paneli, otomatik cevap, öneri kanalı |

## Komutlar
| Kategori | Komutlar |
|---|---|
| Moderasyon | `/ban` `/unban` `/kick` `/mute` `/unmute` `/uyar` `/uyarilar` `/uyari-sil` `/uyari-temizle` `/temizle` `/kilitle` `/kilit-ac` `/yavasmod` `rolver` `rolal` `nick` `banliste` |
| Müzik | `/müzik çal` (YouTube/Spotify/SoundCloud link veya şarkı adı) `duraklat` `devam` `atla` `dur` `kuyruk` `şimdi` `ses` `döngü` `karıştır` `sil` `temizle` |
| Eğlence | `zar` `yazitura` `kure` `sec` `tkm` `tahmin` `ask` `iq` `sans` `espri` `soz` `tokat` `sarilma` `tersle` |
| Ekonomi | `bakiye` `gunluk` `calis` `gonder` `kumar` `zenginler` |
| Minecraft | `mcskin` `mckafa` `mcoyuncu` `mcipucu` `/mc durum` `/mc ip` |
| Araçlar | `avatar` `banner` `ping` `botbilgi` `davet` `kullanici` `sunucu` `rolbilgi` `kanalbilgi` `afk` `hatirlat` `hesapla` `qr` `hava` |
| AI | `cevir` `yapayzeka` |
| Diğer | `/anket` `/cekilis` `/duyuru` `/seviye bak` `/seviye liderlik` |

## Notlar
- Discord bir bot için en fazla 100 slash komut izin verir; şu an 79 tane kullanılıyor.
- Bot 7/24 açık bir bilgisayar/VPS'te çalışmalı (`python bot.py` kapanınca bot kapanır).
- Veriler `data.db` (SQLite) dosyasında tutulur.
- Çekilişler bot yeniden başlarsa iptal olur (en fazla 7 gün).
- AI küfür filtresi her mesaj için küçük bir API çağrısı yapar (Haiku, çok ucuz). Kapatmak için `/automod ayarla ai:False`; yerel filtre çalışmaya devam eder.
- Abone doğrulaması AI ile yapılır, %100 kesin değildir; aynı görselin ikinci kez kullanılması engellenir. Şüpheli durumda `/abone onayla` ile elle verebilirsin.
- Spotify'dan ses çalınmaz; bot Spotify linkinden şarkı adını alıp YouTube'da arar. Tek şarkı linki anahtarsız çalışır; albüm/playlist için `.env`'ye Spotify Client ID/Secret ekle.
- Bazı VPS/hosting IP'lerini YouTube engelleyebilir; ev bilgisayarında genelde sorun olmaz.
- `.env` dosyasını ve tokeni kimseyle paylaşma.
