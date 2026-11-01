# 🌟 YILDIZ Bot

Çok amaçlı, herkese açık (public) Discord sunucu botu. Moderasyon, seviye/XP,
müzik, çekiliş, anti-raid, resimli karşılama kartı, reaction-role ve canlı
istatistik panelini bir arada sunar.

## Kurulum
1. `pip install -r requirements.txt`
2. `DISCORD_TOKEN` ortam değişkenini ayarlayın.
3. Developer Portal'da **Message Content**, **Server Members** intent'lerini açın.
4. Müzik komutları için sunucuda **ffmpeg** kurulu olmalı:
   - Render'da: bu depodaki `Dockerfile`'ı kullanarak "Docker" ortamıyla deploy edin.
   - Native Python ortamında ffmpeg yoksa diğer her şey çalışır, sadece `/çal` hata verir.
5. `python main.py`

## Bot adını değiştirme
`config.py` dosyasındaki `BOT_ADI` ve `BOT_EMOJI` değişkenlerini değiştirin.

## Yapı
- `main.py`, `config.py`, `database.py`, `utils.py`, `keep_alive.py`
- `cogs/`: automod, moderation, warnings, logs, settings, tickets, info, forum,
  leveling, music, giveaway, antiraid, welcome, reactionroles, stats
