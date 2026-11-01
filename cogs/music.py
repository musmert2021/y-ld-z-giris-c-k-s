"""Basit müzik botu: YouTube üzerinden arama/çalma, kuyruk, atlama.

KURULUM NOTU: yt-dlp, PyNaCl ve sunucuda ffmpeg gerekir (bkz. Dockerfile).
"""

import asyncio
import collections

import discord
from discord import app_commands
from discord.ext import commands

import config
from utils import make_embed

FFMPEG_SECENEKLERI = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}
YTDLP_SECENEKLERI = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
}


class Parca:
    def __init__(self, baslik, url, stream_url, sure, istenen: discord.Member):
        self.baslik = baslik
        self.url = url
        self.stream_url = stream_url
        self.sure = sure
        self.istenen = istenen


class SunucuMuzikDurumu:
    def __init__(self, guild_id):
        self.guild_id = guild_id
        self.kuyruk: collections.deque[Parca] = collections.deque()
        self.simdi_calan: Parca | None = None
        self.ses_istemci: discord.VoiceClient | None = None


class Music(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.durumlar: dict[int, SunucuMuzikDurumu] = {}

    def _durum(self, guild_id) -> SunucuMuzikDurumu:
        if guild_id not in self.durumlar:
            self.durumlar[guild_id] = SunucuMuzikDurumu(guild_id)
        return self.durumlar[guild_id]

    async def _ara(self, sorgu: str) -> dict | None:
        try:
            import yt_dlp
        except ImportError:
            return None
        loop = asyncio.get_event_loop()

        def _cikar():
            with yt_dlp.YoutubeDL(YTDLP_SECENEKLERI) as ydl:
                bilgi = ydl.extract_info(sorgu, download=False)
                if "entries" in bilgi:
                    bilgi = bilgi["entries"][0]
                return bilgi

        return await loop.run_in_executor(None, _cikar)

    async def _sirada_sonraki(self, guild: discord.Guild):
        durum = self._durum(guild.id)
        if not durum.kuyruk:
            durum.simdi_calan = None
            return
        parca = durum.kuyruk.popleft()
        durum.simdi_calan = parca
        kaynak = discord.FFmpegPCMAudio(parca.stream_url, **FFMPEG_SECENEKLERI)

        def _sonraki(hata):
            fut = asyncio.run_coroutine_threadsafe(self._sirada_sonraki(guild), self.bot.loop)
            try:
                fut.result()
            except Exception:
                pass

        if durum.ses_istemci and durum.ses_istemci.is_connected():
            durum.ses_istemci.play(discord.PCMVolumeTransformer(kaynak, volume=0.5), after=_sonraki)

    async def _baglan(self, interaction: discord.Interaction) -> SunucuMuzikDurumu | None:
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.followup.send("⚠️ Önce bir ses kanalına katılmalısınız.", ephemeral=True)
            return None
        durum = self._durum(interaction.guild.id)
        kanal = interaction.user.voice.channel
        if durum.ses_istemci and durum.ses_istemci.is_connected():
            if durum.ses_istemci.channel != kanal:
                await durum.ses_istemci.move_to(kanal)
        else:
            try:
                durum.ses_istemci = await kanal.connect()
            except discord.ClientException:
                durum.ses_istemci = interaction.guild.voice_client
        return durum

    @app_commands.command(name="çal", description="YouTube'dan şarkı arar ve çalar/kuyruğa ekler.")
    @app_commands.describe(sorgu="Şarkı adı veya YouTube linki")
    @app_commands.guild_only()
    async def cal(self, interaction: discord.Interaction, sorgu: str):
        await interaction.response.defer()
        durum = await self._baglan(interaction)
        if not durum:
            return

        bilgi = await self._ara(sorgu)
        if not bilgi:
            return await interaction.followup.send(
                "❌ Bulunamadı veya müzik modülü kurulu değil (`yt-dlp` eksik olabilir)."
            )

        parca = Parca(
            baslik=bilgi.get("title", "Bilinmiyor"),
            url=bilgi.get("webpage_url", sorgu),
            stream_url=bilgi["url"],
            sure=bilgi.get("duration", 0),
            istenen=interaction.user,
        )
        durum.kuyruk.append(parca)

        if not (durum.ses_istemci and durum.ses_istemci.is_playing()):
            await self._sirada_sonraki(interaction.guild)
            await interaction.followup.send(embed=self._simdi_calan_embed(parca, yeni_kuyruk=False))
        else:
            await interaction.followup.send(embed=self._simdi_calan_embed(parca, yeni_kuyruk=True))

    def _simdi_calan_embed(self, parca: Parca, yeni_kuyruk: bool) -> discord.Embed:
        baslik = "➕ Kuyruğa Eklendi" if yeni_kuyruk else "🎵 Şimdi Çalıyor"
        dakika, saniye = divmod(parca.sure or 0, 60)
        embed = make_embed(baslik, config.RENK_ANA,
                           f"[{parca.baslik}]({parca.url})\n⏱️ {dakika}:{saniye:02d}")
        embed.set_footer(text=f"İsteyen: {parca.istenen.display_name}")
        return embed

    @app_commands.command(name="duraklat", description="Çalan şarkıyı duraklatır.")
    @app_commands.guild_only()
    async def duraklat(self, interaction: discord.Interaction):
        durum = self._durum(interaction.guild.id)
        if durum.ses_istemci and durum.ses_istemci.is_playing():
            durum.ses_istemci.pause()
            await interaction.response.send_message("⏸️ Duraklatıldı.")
        else:
            await interaction.response.send_message("⚠️ Çalan bir şey yok.", ephemeral=True)

    @app_commands.command(name="devam-ettir", description="Duraklatılmış şarkıyı devam ettirir.")
    @app_commands.guild_only()
    async def devam_ettir(self, interaction: discord.Interaction):
        durum = self._durum(interaction.guild.id)
        if durum.ses_istemci and durum.ses_istemci.is_paused():
            durum.ses_istemci.resume()
            await interaction.response.send_message("▶️ Devam ediyor.")
        else:
            await interaction.response.send_message("⚠️ Duraklatılmış bir şey yok.", ephemeral=True)

    @app_commands.command(name="geç", description="Çalan şarkıyı atlar.")
    @app_commands.guild_only()
    async def gec(self, interaction: discord.Interaction):
        durum = self._durum(interaction.guild.id)
        if durum.ses_istemci and (durum.ses_istemci.is_playing() or durum.ses_istemci.is_paused()):
            durum.ses_istemci.stop()
            await interaction.response.send_message("⏭️ Şarkı atlandı.")
        else:
            await interaction.response.send_message("⚠️ Çalan bir şey yok.", ephemeral=True)

    @app_commands.command(name="kuyruk", description="Sıradaki şarkıları listeler.")
    @app_commands.guild_only()
    async def kuyruk(self, interaction: discord.Interaction):
        durum = self._durum(interaction.guild.id)
        satirlar = []
        if durum.simdi_calan:
            satirlar.append(f"🎵 **Şimdi:** {durum.simdi_calan.baslik}")
        for i, p in enumerate(durum.kuyruk, 1):
            satirlar.append(f"{i}. {p.baslik} — *{p.istenen.display_name}*")
        if not satirlar:
            return await interaction.response.send_message("📭 Kuyruk boş.", ephemeral=True)
        embed = make_embed("🎶 Müzik Kuyruğu", config.RENK_ANA, "\n".join(satirlar)[:4000])
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="ayrıl", description="Bot ses kanalından ayrılır, kuyruğu temizler.")
    @app_commands.guild_only()
    async def ayril(self, interaction: discord.Interaction):
        durum = self._durum(interaction.guild.id)
        if durum.ses_istemci:
            await durum.ses_istemci.disconnect(force=True)
        durum.kuyruk.clear()
        durum.simdi_calan = None
        durum.ses_istemci = None
        await interaction.response.send_message("👋 Ses kanalından ayrıldım.")


async def setup(bot):
    await bot.add_cog(Music(bot))
