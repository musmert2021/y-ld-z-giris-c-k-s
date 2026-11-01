"""Log olayları."""

import discord
from discord.ext import commands

import config
from utils import make_embed, send_log


class Logs(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        embed = make_embed("🗑️ Mesaj Silindi", config.RENK_UYARI)
        embed.add_field(name="Kullanıcı", value=message.author.mention, inline=True)
        embed.add_field(name="Kanal", value=message.channel.mention, inline=True)
        embed.add_field(
            name="Mesaj İçeriği",
            value=message.content[:1000] if message.content else "İçerik yok/Medya",
            inline=False,
        )
        embed.set_footer(text=f"ID: {message.author.id}")
        await send_log(self.bot, message.guild, embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.author.bot or not before.guild or before.content == after.content:
            return
        embed = make_embed("✏️ Mesaj Düzenlendi", discord.Color.blue())
        embed.add_field(name="Kullanıcı", value=before.author.mention, inline=True)
        embed.add_field(name="Kanal", value=before.channel.mention, inline=True)
        embed.add_field(name="Önce", value=before.content[:1000] or "-", inline=False)
        embed.add_field(name="Sonra", value=after.content[:1000] or "-", inline=False)
        embed.add_field(name="Git", value=f"[Mesaja git]({after.jump_url})", inline=False)
        await send_log(self.bot, before.guild, embed)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        embed = make_embed("📥 Yeni Üye Katıldı", config.RENK_BASARI)
        embed.add_field(name="Kullanıcı", value=member.mention, inline=False)
        embed.add_field(
            name="Hesap Oluşturulma",
            value=discord.utils.format_dt(member.created_at, "R"),
            inline=False,
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        await send_log(self.bot, member.guild, embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        embed = make_embed("📤 Üye Ayrıldı", config.RENK_HATA)
        embed.add_field(name="Kullanıcı", value=f"{member} ({member.mention})", inline=False)
        await send_log(self.bot, member.guild, embed)


async def setup(bot):
    await bot.add_cog(Logs(bot))
