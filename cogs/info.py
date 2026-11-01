"""Bilgi komutları."""

import discord
from discord import app_commands
from discord.ext import commands

import config
from utils import make_embed


class Info(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="yapımcı", description="Bot yapımcısı hakkında bilgi verir."
    )
    async def yapimci(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="👑 Bot Yapımcısı",
            description="🚀 Bu bot musmert2021 tarafından geliştirildi!",
            color=discord.Color.gold(),
        )
        embed.set_footer(text=f"{config.BOT_ADI} Sistemleri")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="ping", description="Botun gecikme süresini gösterir.")
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            f"🏓 Pong! **{round(self.bot.latency * 1000)} ms**"
        )

    @app_commands.command(name="yardım", description="Tüm komutların listesini gösterir.")
    async def yardim(self, interaction: discord.Interaction):
        satirlar = [
            f"`/{c.name}` — {c.description}"
            for c in sorted(self.bot.tree.get_commands(), key=lambda c: c.name)
        ]
        embed = make_embed("📖 Komut Listesi", description="\n".join(satirlar)[:4000])
        embed.set_footer(text=f"Toplam {len(satirlar)} komut")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="kullanıcı-bilgi", description="Bir üyenin hesap ve sunucu bilgilerini gösterir."
    )
    @app_commands.describe(uye="Bilgisi görüntülenecek üye (boşsa kendiniz)")
    @app_commands.guild_only()
    async def kullanici_bilgi(self, interaction: discord.Interaction, uye: discord.Member = None):
        uye = uye or interaction.user
        roller = [r.mention for r in reversed(uye.roles) if not r.is_default()]
        embed = make_embed(f"👤 {uye}", config.RENK_ANA)
        embed.set_thumbnail(url=uye.display_avatar.url)
        embed.add_field(name="ID", value=f"`{uye.id}`", inline=True)
        embed.add_field(
            name="Hesap Oluşturma",
            value=discord.utils.format_dt(uye.created_at, "D"), inline=True,
        )
        embed.add_field(
            name="Sunucuya Katılma",
            value=discord.utils.format_dt(uye.joined_at, "D") if uye.joined_at else "?",
            inline=True,
        )
        embed.add_field(
            name=f"Roller ({len(roller)})",
            value=" ".join(roller)[:1000] or "Rol yok", inline=False,
        )
        s = await self.bot.db.count_warnings(interaction.guild.id, uye.id)
        embed.add_field(name="Uyarı Sayısı", value=str(s), inline=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="sunucu-hakkında-herşey",
        description="Sunucunun detaylı istatistiklerini, kurucusunu, kanallarını ve kurallarını gösterir.",
    )
    @app_commands.guild_only()
    async def sunucu_hersey(self, interaction: discord.Interaction):
        guild = interaction.guild
        bot_sayisi = sum(1 for m in guild.members if m.bot)
        insan = guild.member_count - bot_sayisi
        kurucu = guild.owner.mention if guild.owner else "Bulunamadı"

        embed = discord.Embed(
            title=f"👑 {guild.name} — Sunucu Hakkında Her Şey",
            description=(
                f"🚀 **{guild.name}** sunucusuna ait istatistikler, kurucu bilgileri"
                " ve resmî kurallar aşağıdadır!"
            ),
            color=discord.Color.gold(),
        )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.add_field(
            name="📌 Genel Bilgiler",
            value=(
                f"👑 **Kurucu:** {kurucu}\n"
                f"🆔 **Sunucu ID:** `{guild.id}`\n"
                f"📅 **Oluşturulma:** {discord.utils.format_dt(guild.created_at, 'D')}\n"
                f"✨ **Boost:** Seviye {guild.premium_tier} "
                f"({guild.premium_subscription_count} Takviye)"
            ),
            inline=False,
        )
        embed.add_field(
            name="👥 Üye İstatistikleri",
            value=(
                f"👥 **Toplam:** {guild.member_count}\n👤 **Kullanıcı:** {insan}\n"
                f"🤖 **Bot:** {bot_sayisi}\n🛡️ **Rol:** {len(guild.roles)}"
            ),
            inline=True,
        )
        embed.add_field(
            name="📝 Kanal Yapısı",
            value=(
                f"📂 **Kategori:** {len(guild.categories)}\n"
                f"💬 **Metin:** {len(guild.text_channels)}\n"
                f"🔊 **Ses:** {len(guild.voice_channels)}\n"
                f"📊 **Toplam:** {len(guild.channels)}"
            ),
            inline=True,
        )
        embed.add_field(name="📜 SUNUCU KURALLARI", value=config.KURALLAR_METNI, inline=False)
        embed.set_footer(
            text=f"{config.BOT_ADI} Moderasyon & Analiz Sistemi • {self.bot.user.name}",
            icon_url=self.bot.user.display_avatar.url,
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="sunucubilgi", description="Sunucunun detaylı istatistiklerini getirir."
    )
    @app_commands.guild_only()
    async def sunucubilgi(self, interaction: discord.Interaction):
        guild = interaction.guild
        embed = discord.Embed(
            title=f"📊 {guild.name} Sunucu İstatistikleri",
            color=discord.Color.dark_magenta(),
        )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.add_field(
            name="Sunucu Sahibi",
            value=guild.owner.mention if guild.owner else "Bulunamadı", inline=True,
        )
        embed.add_field(name="Sunucu ID", value=str(guild.id), inline=True)
        embed.add_field(name="Toplam Üye", value=f"👥 {guild.member_count}", inline=False)
        embed.add_field(name="Kanal", value=f"📝 {len(guild.channels)}", inline=True)
        embed.add_field(name="Rol", value=f"🛡️ {len(guild.roles)}", inline=True)
        embed.set_footer(text=f"{config.BOT_ADI} Analiz Modülü")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="kurallar", description="Sunucu kurallarını bulunduğunuz kanala gönderir."
    )
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def kurallar(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title=f"📜 {config.BOT_ADI} SUNUCU KURALLARI",
            description="Sunucumuzun samimi bir yer olmasını istiyoruz! Lütfen kurallara uyunuz.",
            color=discord.Color.red(),
        )
        embed.add_field(name="Kurallar", value=config.KURALLAR_METNI, inline=False)
        embed.set_footer(text=f"{config.BOT_ADI} Koruma Sistemleri")
        await interaction.response.send_message("✅ Kurallar gönderildi!", ephemeral=True)
        await interaction.channel.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Info(bot))
