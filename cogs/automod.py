"""Otomatik moderasyon: spam, küfür, phishing, reklam, caps, etiket spamı."""

import collections
import datetime
import re
import time

import discord
from discord.ext import commands

import config
from utils import make_embed, send_log, tr_lower

DAVET_REGEX = re.compile(r"(discord\.gg|discord(app)?\.com/invite)/\S+", re.I)
LINK_REGEX = re.compile(r"(https?://|www\.)(\S+)", re.I)


def kufur_var_mi(text: str) -> bool:
    for kelime in re.findall(r"\w+", tr_lower(text)):
        if kelime in config.YASAKLI_TAM or kelime.startswith(config.YASAKLI_ONEK):
            return True
    return False


def harici_link_var_mi(text: str) -> bool:
    if DAVET_REGEX.search(text):
        return True
    for m in LINK_REGEX.finditer(text):
        adres = tr_lower(m.group(2))
        izinli = any(
            adres.startswith(d) or adres.startswith("www." + d)
            for d in config.IZINLI_ALAN_ADLARI
        )
        if not izinli:
            return True
    return False


class AutoMod(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.mesajlar = collections.defaultdict(list)
        self.ihlaller = collections.defaultdict(list)

    def _kontrol(self, message: discord.Message, yetkili: bool):
        anahtar = (message.guild.id, message.author.id)
        simdi = time.time()
        self.mesajlar[anahtar] = [
            t for t in self.mesajlar[anahtar] if simdi - t < config.SPAM_SURE
        ]
        self.mesajlar[anahtar].append(simdi)
        if not yetkili and len(self.mesajlar[anahtar]) >= config.SPAM_MESAJ_LIMITI:
            return "Spam", "lütfen bu kadar hızlı mesaj atma! (Spam Koruması)", 3

        if kufur_var_mi(message.content):
            return "Küfür", f"{config.BOT_ADI} sunucusunda küfür etmek yasaktır! 🤬", 5

        if yetkili:
            return None

        icerik = tr_lower(message.content)
        if any(p in icerik for p in config.PHISHING):
            return (
                "Phishing / Dolandırıcılık",
                "zararlı bağlantı tespit edildi, mesajın engellendi! 🚨",
                5,
            )
        if harici_link_var_mi(message.content):
            return (
                "Reklam / Link",
                "sunucumuzda reklam veya dış bağlantı paylaşımı yasaktır! 🚫",
                5,
            )
        if len(message.mentions) + len(message.role_mentions) >= config.MAX_ETIKET:
            return "Etiket Spamı", "lütfen bu kadar çok kişiyi etiketleme! ⚠️", 4

        if len(message.content) > 10:
            harfler = [c for c in message.content if c.isalpha()]
            if len(harfler) > 5:
                oran = sum(1 for c in harfler if c.isupper()) / len(harfler)
                if oran > config.CAPS_ORANI:
                    return "Caps Lock", "lütfen büyük harfle (Caps Lock) yazma! ⚠️", 4
        return None

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        if not isinstance(message.author, discord.Member):
            return

        yetkili = message.author.guild_permissions.manage_messages
        sonuc = self._kontrol(message, yetkili)
        if not sonuc:
            return
        tur, uyari, sure = sonuc

        try:
            await message.delete()
        except discord.HTTPException:
            pass
        try:
            await message.channel.send(
                f"{message.author.mention}, {uyari}", delete_after=sure
            )
        except discord.HTTPException:
            pass

        embed = make_embed("🛡️ Otomatik Moderasyon", config.RENK_HATA)
        embed.add_field(name="Tür", value=tur, inline=True)
        embed.add_field(name="Kullanıcı", value=message.author.mention, inline=True)
        embed.add_field(name="Kanal", value=message.channel.mention, inline=True)
        embed.add_field(
            name="Mesaj", value=message.content[:1000] or "İçerik yok", inline=False
        )
        await send_log(self.bot, message.guild, embed)

        await self._tekrar_kontrol(message.author, message.guild)

    async def _tekrar_kontrol(self, uye: discord.Member, guild: discord.Guild):
        anahtar = (guild.id, uye.id)
        simdi = time.time()
        self.ihlaller[anahtar] = [
            t for t in self.ihlaller[anahtar] if simdi - t < config.IHLAL_PENCERE
        ]
        self.ihlaller[anahtar].append(simdi)
        if len(self.ihlaller[anahtar]) < config.IHLAL_LIMITI:
            return
        self.ihlaller[anahtar].clear()
        if uye.guild_permissions.manage_messages or uye.top_role >= guild.me.top_role:
            return
        try:
            await uye.timeout(
                datetime.timedelta(minutes=config.IHLAL_TIMEOUT_DAKIKA),
                reason="Tekrarlayan otomatik moderasyon ihlalleri",
            )
        except discord.HTTPException:
            return
        embed = make_embed("🔇 Otomatik Susturma", config.RENK_UYARI)
        embed.add_field(name="Üye", value=uye.mention, inline=True)
        embed.add_field(
            name="Süre", value=f"{config.IHLAL_TIMEOUT_DAKIKA} dk", inline=True
        )
        embed.add_field(name="Sebep", value="Tekrarlayan filtre ihlalleri", inline=False)
        await send_log(self.bot, guild, embed)


async def setup(bot):
    await bot.add_cog(AutoMod(bot))
