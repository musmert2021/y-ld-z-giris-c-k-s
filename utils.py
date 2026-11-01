"""Ortak yardımcı fonksiyonlar."""

import re

import discord
from discord import app_commands

import config


def tr_lower(text: str) -> str:
    return text.replace("I", "ı").replace("İ", "i").lower()


def make_embed(title: str, color=config.RENK_ANA, description: str = None):
    return discord.Embed(
        title=title, description=description, color=color,
        timestamp=discord.utils.utcnow(),
    )


async def send_log(bot, guild: discord.Guild, embed: discord.Embed):
    settings = await bot.db.get_settings(guild.id)
    channel_id = settings.get("log_channel_id")
    if not channel_id:
        return
    channel = guild.get_channel(channel_id)
    if channel:
        try:
            await channel.send(embed=embed)
        except discord.HTTPException:
            pass


async def dm_gonder(user: discord.abc.User, embed: discord.Embed):
    try:
        await user.send(embed=embed)
    except (discord.Forbidden, discord.HTTPException):
        pass


def hiyerarsi_hatasi(interaction: discord.Interaction, hedef: discord.Member):
    guild = interaction.guild
    if hedef.id == guild.owner_id:
        return "⛔ Sunucu sahibine işlem yapılamaz!"
    if hedef.id == interaction.user.id:
        return "⛔ Kendinize işlem uygulayamazsınız!"
    if hedef.id == interaction.client.user.id:
        return "⛔ Bana işlem uygulayamazsınız!"
    if (interaction.user.id != guild.owner_id
            and hedef.top_role >= interaction.user.top_role):
        return "⛔ Sizinle aynı veya daha üst roldeki birine işlem yapamazsınız!"
    if hedef.top_role >= guild.me.top_role:
        return "⚠️ Bu üyenin rolü benim rolümden yüksek/eşit. Rolümü yukarı taşıyın."
    return None


def guvenli_kanal_adi(ad: str, yedek: str) -> str:
    temiz = re.sub(r"[^a-z0-9_-]", "", ad.lower())
    return temiz or yedek


class SadeceKurucu(app_commands.CheckFailure):
    """Komutu bot kurucusu dışında biri kullanmaya çalıştı."""


def sadece_kurucu():
    async def predicate(interaction: discord.Interaction) -> bool:
        if (await interaction.client.is_owner(interaction.user)
                or interaction.user.id in config.OWNER_IDS):
            return True
        raise SadeceKurucu()

    return app_commands.check(predicate)
