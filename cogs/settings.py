"""Sunucu ayarları: log kanalı, karşılama mesajı, otomatik rol."""

import discord
from discord import app_commands
from discord.ext import commands

import config
from utils import make_embed


class Settings(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="log-kanal-ayarla",
        description="Moderasyon log kayıtlarının gönderileceği kanalı belirler.",
    )
    @app_commands.describe(kanal="Logların gönderileceği metin kanalı")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def logkanalayarla(
        self, interaction: discord.Interaction, kanal: discord.TextChannel
    ):
        await self.bot.db.set_setting(interaction.guild.id, "log_channel_id", kanal.id)
        await interaction.response.send_message(
            f"✅ Log kanalı {kanal.mention} olarak ayarlandı!", ephemeral=True
        )

    @app_commands.command(
        name="hoşgeldin-kanal-ayarla",
        description="Yeni üyeler için karşılama mesajının gönderileceği kanalı belirler.",
    )
    @app_commands.describe(kanal="Karşılama kanalı (kapatmak için boş bırakın)")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def hosgeldin_ayarla(
        self, interaction: discord.Interaction, kanal: discord.TextChannel = None
    ):
        await self.bot.db.set_setting(
            interaction.guild.id, "welcome_channel_id", kanal.id if kanal else None
        )
        msg = (
            f"✅ Karşılama kanalı {kanal.mention} olarak ayarlandı!"
            if kanal else "✅ Karşılama mesajı kapatıldı."
        )
        await interaction.response.send_message(msg, ephemeral=True)

    @app_commands.command(
        name="otorol-ayarla",
        description="Sunucuya katılan herkese otomatik verilecek rolü belirler.",
    )
    @app_commands.describe(rol="Otomatik rol (kapatmak için boş bırakın)")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def otorol_ayarla(self, interaction: discord.Interaction, rol: discord.Role = None):
        if rol and (rol.is_default() or rol.managed or rol >= interaction.guild.me.top_role):
            return await interaction.response.send_message(
                "⚠️ Bu rolü veremem. Rol, botun rolünün altında ve normal bir rol olmalı.",
                ephemeral=True,
            )
        await self.bot.db.set_setting(
            interaction.guild.id, "autorole_id", rol.id if rol else None
        )
        msg = (
            f"✅ Otomatik rol {rol.mention} olarak ayarlandı!"
            if rol else "✅ Otomatik rol kapatıldı."
        )
        await interaction.response.send_message(msg, ephemeral=True)

    @app_commands.command(name="ayarlar", description="Sunucunun mevcut bot ayarlarını gösterir.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def ayarlar(self, interaction: discord.Interaction):
        s = await self.bot.db.get_settings(interaction.guild.id)

        def kanal(k):
            return f"<#{s[k]}>" if s.get(k) else "❌ Ayarlanmamış"

        def rol(k):
            return f"<@&{s[k]}>" if s.get(k) else "❌ Ayarlanmamış"

        embed = make_embed("⚙️ Sunucu Ayarları")
        embed.add_field(name="Log Kanalı", value=kanal("log_channel_id"), inline=False)
        embed.add_field(name="Karşılama Kanalı", value=kanal("welcome_channel_id"), inline=False)
        embed.add_field(name="Otomatik Rol", value=rol("autorole_id"), inline=False)
        embed.add_field(name="Ticket Yetkili Rolü", value=rol("ticket_staff_role_id"), inline=False)
        kat = s.get("ticket_category_id")
        embed.add_field(
            name="Ticket Kategorisi",
            value=f"<#{kat}>" if kat else "❌ Ayarlanmamış",
            inline=False,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        # Karşılama mesajı/kartı cogs/welcome.py tarafından gönderilir.
        s = await self.bot.db.get_settings(member.guild.id)

        if s.get("autorole_id") and not member.bot:
            rol = member.guild.get_role(s["autorole_id"])
            if rol and rol < member.guild.me.top_role:
                try:
                    await member.add_roles(rol, reason="Otomatik rol")
                except discord.HTTPException:
                    pass


async def setup(bot):
    await bot.add_cog(Settings(bot))
