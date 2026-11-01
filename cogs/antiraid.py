"""Anti-raid koruması: kısa sürede çok üye katılırsa otomatik önlem alır."""

import collections
import datetime
import time

import discord
from discord import app_commands
from discord.ext import commands

import config
from utils import make_embed, send_log


class AntiRaid(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.katilimlar = collections.defaultdict(list)
        self.tetiklenen = set()

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild
        s = await self.bot.db.get_settings(guild.id)
        if not s.get("antiraid_enabled"):
            return

        esik = s.get("antiraid_esik") or config.ANTIRAID_VARSAYILAN_ESIK
        pencere = s.get("antiraid_pencere") or config.ANTIRAID_VARSAYILAN_PENCERE

        simdi = time.time()
        self.katilimlar[guild.id] = [t for t in self.katilimlar[guild.id] if simdi - t < pencere]
        self.katilimlar[guild.id].append(simdi)

        if len(self.katilimlar[guild.id]) < esik:
            return
        if guild.id in self.tetiklenen:
            return

        self.tetiklenen.add(guild.id)
        await self._raid_onlemi_al(guild, len(self.katilimlar[guild.id]), pencere)

    async def _raid_onlemi_al(self, guild: discord.Guild, kac_katilim: int, pencere: int):
        try:
            await guild.edit(verification_level=discord.VerificationLevel.high)
        except discord.HTTPException:
            pass

        embed = make_embed(
            "🚨 RAID TESPİT EDİLDİ", config.RENK_HATA,
            f"**{kac_katilim}** üye son **{pencere} saniyede** katıldı!\n"
            "Doğrulama seviyesi geçici olarak **Yüksek** yapıldı.\n"
            "`/antiraid-sıfırla` ile normale döndürebilirsiniz.",
        )
        await send_log(self.bot, guild, embed)

        for member in guild.members:
            if member.guild_permissions.administrator and not member.bot:
                try:
                    await member.send(embed=embed)
                except discord.HTTPException:
                    pass
                break

    @app_commands.command(name="antiraid-ayarla", description="[Yönetici] Anti-raid korumasını açar/kapatır ve eşik değerlerini ayarlar.")
    @app_commands.describe(
        durum="Açık mı kapalı mı olsun",
        esik="Bu kadar katılım olursa tetiklenir (varsayılan 6)",
        pencere_saniye="Kaç saniyelik pencerede sayılsın (varsayılan 10)",
    )
    @app_commands.choices(durum=[
        app_commands.Choice(name="Açık", value="acik"),
        app_commands.Choice(name="Kapalı", value="kapali"),
    ])
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def antiraid_ayarla(
        self, interaction: discord.Interaction, durum: app_commands.Choice[str],
        esik: app_commands.Range[int, 2, 100] = None,
        pencere_saniye: app_commands.Range[int, 3, 300] = None,
    ):
        db = self.bot.db
        await db.set_setting(interaction.guild.id, "antiraid_enabled", 1 if durum.value == "acik" else 0)
        if esik:
            await db.set_setting(interaction.guild.id, "antiraid_esik", esik)
        if pencere_saniye:
            await db.set_setting(interaction.guild.id, "antiraid_pencere", pencere_saniye)
        await interaction.response.send_message(
            f"✅ Anti-raid koruması **{durum.name}**."
            + (f" Eşik: **{esik}** katılım" if esik else "")
            + (f" / **{pencere_saniye}** sn" if pencere_saniye else ""),
            ephemeral=True,
        )

    @app_commands.command(name="antiraid-sıfırla", description="[Yönetici] Raid modunu kapatır, doğrulama seviyesini normale döndürür.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def antiraid_sifirla(self, interaction: discord.Interaction):
        self.tetiklenen.discard(interaction.guild.id)
        self.katilimlar[interaction.guild.id].clear()
        try:
            await interaction.guild.edit(verification_level=discord.VerificationLevel.medium)
        except discord.HTTPException:
            pass
        await interaction.response.send_message("✅ Raid modu kapatıldı, doğrulama seviyesi normale döndürüldü.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(AntiRaid(bot))
