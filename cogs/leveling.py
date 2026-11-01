"""Seviye / XP sistemi: mesaj yazanlara puan, seviye atlama, liderlik tablosu, seviye rolleri."""

import random
import time

import discord
from discord import app_commands
from discord.ext import commands

import config
from utils import make_embed


def gereken_xp(seviye: int) -> int:
    return config.XP_SEVIYE_FORMULU(seviye)


class Leveling(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        simdi = time.time()
        db = self.bot.db
        mevcut = await db.get_level(message.guild.id, message.author.id)
        if mevcut and simdi - mevcut["son_mesaj_ts"] < config.XP_BEKLEME_SANIYE:
            return

        kazanilan = random.randint(config.XP_MIN, config.XP_MAX)
        yeni_xp, eski_seviye = await db.add_xp(
            message.guild.id, message.author.id, kazanilan, simdi
        )

        yeni_seviye = eski_seviye
        while yeni_xp >= gereken_xp(yeni_seviye):
            yeni_seviye += 1
        if yeni_seviye != eski_seviye:
            await db.set_level(message.guild.id, message.author.id, yeni_seviye)
            await self._seviye_atladi(message, yeni_seviye)

    async def _seviye_atladi(self, message: discord.Message, yeni_seviye: int):
        s = await self.bot.db.get_settings(message.guild.id)
        if s.get("levelup_enabled") == 0:
            return

        kanal_id = s.get("levelup_channel_id")
        kanal = message.guild.get_channel(kanal_id) if kanal_id else message.channel

        embed = make_embed(
            f"{config.BOT_EMOJI} Seviye Atlandı!",
            config.RENK_BASARI,
            f"{message.author.mention} artık **Seviye {yeni_seviye}**!",
        )
        if kanal:
            try:
                await kanal.send(embed=embed)
            except discord.HTTPException:
                pass

        roller = await self.bot.db.list_level_roles(message.guild.id)
        uygun = [r for r in roller if r["seviye"] <= yeni_seviye]
        if not uygun:
            return
        for r in uygun:
            rol = message.guild.get_role(r["role_id"])
            if rol and rol not in message.author.roles and rol < message.guild.me.top_role:
                try:
                    await message.author.add_roles(rol, reason="Seviye rolü")
                except discord.HTTPException:
                    pass

    @app_commands.command(name="seviye", description="Kendinizin veya bir üyenin seviyesini gösterir.")
    @app_commands.describe(uye="Seviyesi gösterilecek üye (boşsa kendiniz)")
    @app_commands.guild_only()
    async def seviye(self, interaction: discord.Interaction, uye: discord.Member = None):
        uye = uye or interaction.user
        row = await self.bot.db.get_level(interaction.guild.id, uye.id)
        if not row:
            return await interaction.response.send_message(
                f"📭 {uye.mention} henüz XP kazanmamış.", ephemeral=True
            )
        sira = await self.bot.db.rank(interaction.guild.id, uye.id)
        gereken = gereken_xp(row["seviye"])
        embed = make_embed(f"📊 {uye.display_name} — Seviye Kartı", config.RENK_ANA)
        embed.set_thumbnail(url=uye.display_avatar.url)
        embed.add_field(name="Seviye", value=str(row["seviye"]), inline=True)
        embed.add_field(name="Sıra", value=f"#{sira}", inline=True)
        embed.add_field(name="XP", value=f"{row['xp']} / {gereken}", inline=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="liderlik-tablosu", description="Sunucunun en çok XP'ye sahip üyelerini listeler.")
    @app_commands.guild_only()
    async def liderlik(self, interaction: discord.Interaction):
        rows = await self.bot.db.leaderboard(interaction.guild.id, 10)
        if not rows:
            return await interaction.response.send_message("📭 Henüz kimse XP kazanmadı.", ephemeral=True)
        madalya = ["🥇", "🥈", "🥉"]
        satirlar = []
        for i, r in enumerate(rows):
            on = madalya[i] if i < 3 else f"**{i + 1}.**"
            satirlar.append(f"{on} <@{r['user_id']}> — Seviye {r['seviye']} ({r['xp']} XP)")
        embed = make_embed(f"🏆 {interaction.guild.name} Liderlik Tablosu", config.RENK_ANA,
                           "\n".join(satirlar))
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="seviye-rolü-ekle", description="[Yönetici] Belirli bir seviyeye ulaşınca verilecek rolü ayarlar.")
    @app_commands.describe(seviye="Bu seviyeye ulaşınca rol verilir", rol="Verilecek rol")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def seviye_rolu_ekle(self, interaction: discord.Interaction, seviye: app_commands.Range[int, 1, 1000], rol: discord.Role):
        if rol >= interaction.guild.me.top_role:
            return await interaction.response.send_message(
                "⚠️ Bu rol benim rolümden yüksek/eşit, verilemez.", ephemeral=True
            )
        await self.bot.db.add_level_role(interaction.guild.id, seviye, rol.id)
        await interaction.response.send_message(
            f"✅ Seviye **{seviye}**'e ulaşan üyelere {rol.mention} rolü verilecek.", ephemeral=True
        )

    @app_commands.command(name="seviye-rolü-sil", description="[Yönetici] Bir seviye rolü kaydını kaldırır.")
    @app_commands.describe(seviye="Kaldırılacak seviye eşiği")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def seviye_rolu_sil(self, interaction: discord.Interaction, seviye: int):
        if await self.bot.db.remove_level_role(interaction.guild.id, seviye):
            await interaction.response.send_message(f"🗑️ Seviye **{seviye}** rol kaydı silindi.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Bu seviyede bir kayıt bulunamadı.", ephemeral=True)

    @app_commands.command(name="seviye-kanal-ayarla", description="[Yönetici] Seviye atlama mesajlarının gönderileceği kanalı belirler.")
    @app_commands.describe(kanal="Kanal (boş bırakılırsa mesajın yazıldığı kanala gider)")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def seviye_kanal_ayarla(self, interaction: discord.Interaction, kanal: discord.TextChannel = None):
        await self.bot.db.set_setting(
            interaction.guild.id, "levelup_channel_id", kanal.id if kanal else None
        )
        msg = f"✅ Seviye mesajları {kanal.mention} kanalına gönderilecek." if kanal else \
              "✅ Seviye mesajları artık yazıldığı kanala gönderilecek."
        await interaction.response.send_message(msg, ephemeral=True)

    @app_commands.command(name="seviye-sistemi", description="[Yönetici] Seviye sistemini açar/kapatır.")
    @app_commands.describe(durum="Açık mı kapalı mı olsun")
    @app_commands.choices(durum=[
        app_commands.Choice(name="Açık", value="acik"),
        app_commands.Choice(name="Kapalı", value="kapali"),
    ])
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def seviye_sistemi(self, interaction: discord.Interaction, durum: app_commands.Choice[str]):
        await self.bot.db.set_setting(
            interaction.guild.id, "levelup_enabled", 1 if durum.value == "acik" else 0
        )
        await interaction.response.send_message(
            f"✅ Seviye atlama bildirimleri **{durum.name}**.", ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(Leveling(bot))
