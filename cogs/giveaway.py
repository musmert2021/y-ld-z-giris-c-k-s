"""Çekiliş (giveaway) sistemi: buton ile katılım, otomatik kazanan seçimi."""

import datetime
import random
import re

import discord
from discord import app_commands
from discord.ext import commands, tasks

import config
from utils import make_embed, send_log

SURE_REGEX = re.compile(r"^(\d+)\s*(s|sn|dk|dakika|sa|saat|g|gun|gün)$", re.I)
CATIL_EMOJI = "🎉"


def sureyi_coz(metin: str) -> datetime.timedelta | None:
    m = SURE_REGEX.match(metin.strip())
    if not m:
        return None
    sayi, birim = int(m.group(1)), m.group(2).lower()
    if birim in ("s", "sn"):
        return datetime.timedelta(seconds=sayi)
    if birim in ("dk", "dakika"):
        return datetime.timedelta(minutes=sayi)
    if birim in ("sa", "saat"):
        return datetime.timedelta(hours=sayi)
    if birim in ("g", "gun", "gün"):
        return datetime.timedelta(days=sayi)
    return None


class CekilisView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Çekilişe Katıl", emoji=CATIL_EMOJI,
                       style=discord.ButtonStyle.success, custom_id="yildiz:giveaway_join")
    async def katil(self, interaction: discord.Interaction, button: discord.ui.Button):
        db = interaction.client.db
        row = await db.get_giveaway_by_message(interaction.message.id)
        if not row or row["ended"]:
            return await interaction.response.send_message("⚠️ Bu çekiliş artık aktif değil.", ephemeral=True)

        eklendi = await db.add_giveaway_entry(row["id"], interaction.user.id)
        if eklendi:
            sayi = await db.giveaway_entry_count(row["id"])
            await interaction.response.send_message(
                f"🎉 Çekilişe katıldın! Şu an **{sayi}** katılımcı var.", ephemeral=True
            )
        else:
            await db.remove_giveaway_entry(row["id"], interaction.user.id)
            sayi = await db.giveaway_entry_count(row["id"])
            await interaction.response.send_message(
                f"❌ Katılımın geri çekildi. Şu an **{sayi}** katılımcı var.", ephemeral=True
            )


def cekilis_embed(prize: str, winners: int, bitis: datetime.datetime, host_id: int, katilimci=0) -> discord.Embed:
    embed = discord.Embed(
        title=f"🎉 ÇEKİLİŞ: {prize}",
        description=(
            f"Katılmak için **{CATIL_EMOJI} Çekilişe Katıl** butonuna bas!\n\n"
            f"🏆 **Kazanan Sayısı:** {winners}\n"
            f"⏰ **Bitiş:** {discord.utils.format_dt(bitis, 'R')} ({discord.utils.format_dt(bitis, 'f')})\n"
            f"👤 **Düzenleyen:** <@{host_id}>\n"
            f"👥 **Katılımcı:** {katilimci}"
        ),
        color=config.RENK_ANA,
    )
    embed.set_footer(text=f"{config.BOT_ADI} Çekiliş Sistemi")
    return embed


class Giveaway(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.kontrol_dongusu.start()

    def cog_unload(self):
        self.kontrol_dongusu.cancel()

    async def cog_load(self):
        self.bot.add_view(CekilisView())

    @tasks.loop(seconds=config.CEKILIS_KONTROL_SANIYE)
    async def kontrol_dongusu(self):
        try:
            aktifler = await self.bot.db.active_giveaways()
        except Exception:
            return
        simdi = datetime.datetime.now(datetime.timezone.utc)
        for g in aktifler:
            bitis = datetime.datetime.fromisoformat(g["end_time"])
            if bitis <= simdi:
                await self._cekilisi_bitir(g)

    async def _cekilisi_bitir(self, g):
        await self.bot.db.end_giveaway(g["id"])
        guild = self.bot.get_guild(g["guild_id"])
        if not guild:
            return
        kanal = guild.get_channel(g["channel_id"])
        if not kanal:
            return
        try:
            mesaj = await kanal.fetch_message(g["message_id"])
        except discord.HTTPException:
            mesaj = None

        katilimcilar = await self.bot.db.giveaway_entrants(g["id"])
        kazananlar = random.sample(katilimcilar, min(g["winners_count"], len(katilimcilar))) if katilimcilar else []

        if kazananlar:
            mention_listesi = ", ".join(f"<@{k}>" for k in kazananlar)
            sonuc = f"🎉 Tebrikler {mention_listesi}! **{g['prize']}** kazandınız!"
        else:
            sonuc = "😢 Kimse katılmadığı için kazanan seçilemedi."

        if mesaj:
            try:
                bitmis_embed = cekilis_embed(
                    g["prize"], g["winners_count"],
                    datetime.datetime.fromisoformat(g["end_time"]),
                    g["host_id"], len(katilimcilar),
                )
                bitmis_embed.title = f"🎉 ÇEKİLİŞ BİTTİ: {g['prize']}"
                bitmis_embed.color = config.RENK_HATA
                await mesaj.edit(embed=bitmis_embed, view=None)
                await mesaj.reply(sonuc)
            except discord.HTTPException:
                pass

    @app_commands.command(name="çekiliş-başlat", description="[Yönetici] Yeni bir çekiliş başlatır.")
    @app_commands.describe(
        odul="Çekilişte verilecek ödül",
        sure="Örnek: 10dk, 2sa, 1g",
        kazanan_sayisi="Kaç kişi kazansın (varsayılan 1)",
    )
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    async def cekilis_baslat(
        self, interaction: discord.Interaction, odul: str, sure: str,
        kazanan_sayisi: app_commands.Range[int, 1, 20] = 1,
    ):
        delta = sureyi_coz(sure)
        if not delta:
            return await interaction.response.send_message(
                "❌ Geçersiz süre. Örnek: `10dk`, `2sa`, `1g`", ephemeral=True
            )
        bitis = datetime.datetime.now(datetime.timezone.utc) + delta
        embed = cekilis_embed(odul, kazanan_sayisi, bitis, interaction.user.id, 0)
        await interaction.response.send_message("✅ Çekiliş başlatıldı!", ephemeral=True)
        mesaj = await interaction.channel.send(embed=embed, view=CekilisView())
        await self.bot.db.create_giveaway(
            interaction.guild.id, interaction.channel.id, mesaj.id,
            odul, kazanan_sayisi, bitis.isoformat(), interaction.user.id,
        )

    @app_commands.command(name="çekiliş-bitir", description="[Yönetici] Bir çekilişi hemen sonlandırır.")
    @app_commands.describe(mesaj_id="Çekiliş mesajının ID'si")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    async def cekilis_bitir(self, interaction: discord.Interaction, mesaj_id: str):
        try:
            g = await self.bot.db.get_giveaway_by_message(int(mesaj_id))
        except ValueError:
            g = None
        if not g or g["ended"]:
            return await interaction.response.send_message("❌ Aktif bir çekiliş bulunamadı.", ephemeral=True)
        await interaction.response.send_message("✅ Çekiliş sonlandırılıyor...", ephemeral=True)
        await self._cekilisi_bitir(g)

    @app_commands.command(name="çekiliş-yeniden-çek", description="[Yönetici] Biten bir çekiliş için yeni kazanan seçer.")
    @app_commands.describe(mesaj_id="Çekiliş mesajının ID'si")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    async def cekilis_yeniden(self, interaction: discord.Interaction, mesaj_id: str):
        try:
            g = await self.bot.db.get_giveaway_by_message(int(mesaj_id))
        except ValueError:
            g = None
        if not g:
            return await interaction.response.send_message("❌ Çekiliş bulunamadı.", ephemeral=True)
        katilimcilar = await self.bot.db.giveaway_entrants(g["id"])
        if not katilimcilar:
            return await interaction.response.send_message("😢 Katılımcı yok.", ephemeral=True)
        kazanan = random.choice(katilimcilar)
        await interaction.response.send_message(f"🎉 Yeni kazanan: <@{kazanan}> — **{g['prize']}**")


async def setup(bot):
    await bot.add_cog(Giveaway(bot))
