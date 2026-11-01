"""Sunucu istatistik paneli: güncel üye/kanal/rol sayılarını gösteren embed."""

import discord
from discord import app_commands
from discord.ext import commands, tasks

import config
from utils import make_embed


def istatistik_embed(guild: discord.Guild) -> discord.Embed:
    bot_sayisi = sum(1 for m in guild.members if m.bot)
    insan = guild.member_count - bot_sayisi
    embed = make_embed(f"📊 {guild.name} — Canlı İstatistik", config.RENK_ANA)
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    embed.add_field(name="👥 Toplam Üye", value=str(guild.member_count), inline=True)
    embed.add_field(name="👤 Kullanıcı", value=str(insan), inline=True)
    embed.add_field(name="🤖 Bot", value=str(bot_sayisi), inline=True)
    embed.add_field(name="💬 Metin Kanalı", value=str(len(guild.text_channels)), inline=True)
    embed.add_field(name="🔊 Ses Kanalı", value=str(len(guild.voice_channels)), inline=True)
    embed.add_field(name="🛡️ Rol Sayısı", value=str(len(guild.roles)), inline=True)
    embed.add_field(name="✨ Boost Seviyesi", value=f"Seviye {guild.premium_tier}", inline=True)
    embed.add_field(name="🚀 Boost Sayısı", value=str(guild.premium_subscription_count), inline=True)
    embed.set_footer(text=f"Son güncelleme • {config.BOT_ADI}")
    embed.timestamp = discord.utils.utcnow()
    return embed


class Stats(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.guncelleme_dongusu.start()

    def cog_unload(self):
        self.guncelleme_dongusu.cancel()

    async def _guncelle(self, guild: discord.Guild, kanal_id: int, mesaj_id: int | None):
        kanal = guild.get_channel(kanal_id)
        if not kanal:
            return
        embed = istatistik_embed(guild)
        if mesaj_id:
            try:
                mesaj = await kanal.fetch_message(mesaj_id)
                await mesaj.edit(embed=embed)
                return
            except discord.HTTPException:
                pass
        try:
            mesaj = await kanal.send(embed=embed)
            await self.bot.db.set_setting(guild.id, "stats_message_id", mesaj.id)
        except discord.HTTPException:
            pass

    @tasks.loop(minutes=config.STATS_GUNCELLEME_DAKIKA)
    async def guncelleme_dongusu(self):
        for guild in list(self.bot.guilds):
            s = await self.bot.db.get_settings(guild.id)
            if s.get("stats_channel_id"):
                await self._guncelle(guild, s["stats_channel_id"], s.get("stats_message_id"))

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        s = await self.bot.db.get_settings(member.guild.id)
        if s.get("stats_channel_id"):
            await self._guncelle(member.guild, s["stats_channel_id"], s.get("stats_message_id"))

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        s = await self.bot.db.get_settings(member.guild.id)
        if s.get("stats_channel_id"):
            await self._guncelle(member.guild, s["stats_channel_id"], s.get("stats_message_id"))

    @app_commands.command(
        name="istatistik-panel",
        description="[Yönetici] Bu kanala kendiliğinden güncellenen istatistik panelini kurar.",
    )
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def istatistik_panel(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        embed = istatistik_embed(interaction.guild)
        mesaj = await interaction.channel.send(embed=embed)
        await self.bot.db.set_setting(interaction.guild.id, "stats_channel_id", interaction.channel.id)
        await self.bot.db.set_setting(interaction.guild.id, "stats_message_id", mesaj.id)
        await interaction.followup.send(
            f"✅ İstatistik paneli {interaction.channel.mention} kanalına kuruldu, "
            f"her {config.STATS_GUNCELLEME_DAKIKA} dakikada ve üye giriş/çıkışında güncellenir.",
            ephemeral=True,
        )

    @app_commands.command(name="istatistik-kapat", description="[Yönetici] İstatistik panelini kapatır.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def istatistik_kapat(self, interaction: discord.Interaction):
        await self.bot.db.set_setting(interaction.guild.id, "stats_channel_id", None)
        await self.bot.db.set_setting(interaction.guild.id, "stats_message_id", None)
        await interaction.response.send_message("✅ İstatistik paneli kapatıldı.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Stats(bot))
