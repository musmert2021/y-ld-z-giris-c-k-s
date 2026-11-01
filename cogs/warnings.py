"""Uyarı sistemi."""

import datetime

import discord
from discord import app_commands
from discord.ext import commands

import config
from utils import dm_gonder, hiyerarsi_hatasi, make_embed, send_log


class Warnings(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="warn", description="Bir kullanıcıya kural ihlali nedeniyle uyarı verir."
    )
    @app_commands.describe(uye="Uyarılacak üye", sebep="Uyarı nedeni")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warn(
        self, interaction: discord.Interaction, uye: discord.Member,
        sebep: str = "Belirtilmedi",
    ):
        hata = hiyerarsi_hatasi(interaction, uye)
        if hata:
            return await interaction.response.send_message(hata, ephemeral=True)

        toplam = await self.bot.db.add_warning(
            interaction.guild.id, uye.id, sebep, interaction.user.id
        )
        mesaj = (
            f"⚠️ {uye.mention} kullanıcısı uyarıldı.\n"
            f"📄 **Sebep:** {sebep}\n📌 Toplam Uyarı: **{toplam}**"
        )
        if toplam % config.OTOMATIK_TIMEOUT_UYARI == 0:
            try:
                await uye.timeout(
                    datetime.timedelta(minutes=config.OTOMATIK_TIMEOUT_DAKIKA),
                    reason=f"{toplam} uyarıya ulaştı (otomatik)",
                )
                mesaj += (
                    f"\n🔇 {toplam} uyarıya ulaştığı için "
                    f"**{config.OTOMATIK_TIMEOUT_DAKIKA} dakika** otomatik susturuldu."
                )
            except discord.HTTPException:
                pass
        await interaction.response.send_message(mesaj)

        dm = make_embed("⚠️ Uyarı Aldınız", config.RENK_UYARI)
        dm.add_field(name="Sunucu", value=interaction.guild.name, inline=False)
        dm.add_field(name="Sebep", value=sebep, inline=False)
        dm.add_field(name="Toplam Uyarı", value=str(toplam), inline=False)
        await dm_gonder(uye, dm)

        embed = make_embed("⚠️ Kullanıcı Uyarıldı", discord.Color.yellow())
        embed.add_field(name="Üye", value=uye.mention, inline=True)
        embed.add_field(name="Yetkili", value=interaction.user.mention, inline=True)
        embed.add_field(name="Sebep", value=sebep, inline=False)
        embed.add_field(name="Toplam Uyarı", value=str(toplam), inline=True)
        await send_log(self.bot, interaction.guild, embed)

    @app_commands.command(
        name="uyarılar", description="Bir kullanıcının toplam uyarılarını listeler."
    )
    @app_commands.describe(uye="Uyarıları kontrol edilecek üye")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(moderate_members=True)
    async def uyarilar(self, interaction: discord.Interaction, uye: discord.Member):
        sonuclar = await self.bot.db.get_warnings(interaction.guild.id, uye.id)
        if not sonuclar:
            return await interaction.response.send_message(
                f"🎉 {uye.mention} kullanıcısının hiç uyarısı yok!", ephemeral=True
            )
        embed = discord.Embed(
            title=f"📋 {uye.name} Kullanıcısının Uyarıları (son 20)",
            color=config.RENK_UYARI,
        )
        for row in sonuclar:
            embed.add_field(
                name=f"Uyarı ID: {row['id']}",
                value=(
                    f"**Sebep:** {row['reason']}\n"
                    f"**Yetkili:** <@{row['moderator_id']}>\n"
                    f"*Tarih: {row['timestamp'][:19]}*"
                ),
                inline=False,
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="uyarı-sil", description="ID numarasına göre bir uyarıyı siler."
    )
    @app_commands.describe(uyari_id="Silinecek uyarının ID'si (/uyarılar ile görebilirsiniz)")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(moderate_members=True)
    async def uyari_sil(self, interaction: discord.Interaction, uyari_id: int):
        if await self.bot.db.delete_warning(interaction.guild.id, uyari_id):
            await interaction.response.send_message(
                f"🗑️ **#{uyari_id}** numaralı uyarı silindi.", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "❌ Bu ID'ye ait bir uyarı bulunamadı.", ephemeral=True
            )

    @app_commands.command(
        name="uyarı-temizle", description="Bir üyenin tüm uyarılarını siler."
    )
    @app_commands.describe(uye="Uyarıları temizlenecek üye")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def uyari_temizle(self, interaction: discord.Interaction, uye: discord.Member):
        adet = await self.bot.db.clear_warnings(interaction.guild.id, uye.id)
        await interaction.response.send_message(
            f"🧹 {uye.mention} kullanıcısının **{adet}** uyarısı temizlendi.",
            ephemeral=True,
        )


async def setup(bot):
    await bot.add_cog(Warnings(bot))
