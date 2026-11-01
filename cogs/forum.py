"""Otomatik sunucu rehberi (forum).

Bot bir sunucuya eklenince kurucunun forum kanalında o sunucunun adıyla bir
başlık açılır (davet linki + bilgiler). O sunucuda kullanılan komutlar da
aynı başlığa yazılır. Yönetim komutları sadece bot kurucusuna aittir.
"""

import asyncio
import logging

import discord
from discord import app_commands
from discord.ext import commands

import config
from utils import sadece_kurucu

log = logging.getLogger("simsek.forum")
YOK = discord.AllowedMentions.none()


def bilgi_embed(guild: discord.Guild, davet: str | None, aktif: bool = True) -> discord.Embed:
    embed = discord.Embed(
        title=f"🖥️ {guild.name}",
        color=config.RENK_ANA if aktif else config.RENK_HATA,
        timestamp=discord.utils.utcnow(),
    )
    embed.add_field(
        name="🔗 Davet Linki",
        value=davet or "❌ Oluşturulamadı (botun davet oluşturma yetkisi yok)",
        inline=False,
    )
    embed.add_field(name="🆔 Sunucu ID", value=f"`{guild.id}`", inline=True)
    embed.add_field(name="👥 Üye", value=str(guild.member_count), inline=True)
    sahip = str(guild.owner) if guild.owner else "Bilinmiyor"
    embed.add_field(name="👑 Sunucu Sahibi", value=f"{sahip} (`{guild.owner_id}`)", inline=False)
    embed.add_field(
        name="📅 Sunucu Oluşturulma", value=discord.utils.format_dt(guild.created_at, "D"), inline=True
    )
    if guild.me and guild.me.joined_at:
        embed.add_field(
            name="📥 Bota Eklenme", value=discord.utils.format_dt(guild.me.joined_at, "f"), inline=True
        )
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    embed.set_footer(text="Bu sunucuda kullanılan komutlar aşağıda listelenir")
    return embed


def davet_view(davet: str | None):
    if not davet:
        return None
    view = discord.ui.View()
    view.add_item(
        discord.ui.Button(label="Sunucuya Katıl", emoji="🚀",
                          style=discord.ButtonStyle.link, url=davet)
    )
    return view


class Forum(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    async def _forum(self):
        cid = await self.bot.db.get_global("forum_channel_id")
        if not cid:
            return None
        kanal = self.bot.get_channel(cid)
        return kanal if isinstance(kanal, discord.ForumChannel) else None

    async def _thread_al(self, thread_id: int):
        t = self.bot.get_channel(thread_id)
        if t:
            return t
        try:
            return await self.bot.fetch_channel(thread_id)
        except (discord.NotFound, discord.Forbidden):
            return None

    async def _davet_olustur(self, guild: discord.Guild):
        adaylar = []
        if guild.system_channel:
            adaylar.append(guild.system_channel)
        adaylar += [c for c in guild.text_channels if c != guild.system_channel]
        for kanal in adaylar[:15]:
            if kanal.permissions_for(guild.me).create_instant_invite:
                try:
                    inv = await kanal.create_invite(
                        max_age=0, max_uses=0, reason="YILDIZ sunucu rehberi"
                    )
                    return inv.url
                except discord.HTTPException:
                    continue
        return None

    async def kayit_olustur(self, guild: discord.Guild) -> str:
        db = self.bot.db
        davet = await self._davet_olustur(guild)
        embed = bilgi_embed(guild, davet)
        view = davet_view(davet)

        row = await db.get_guild_thread(guild.id)
        if row:
            thread = await self._thread_al(row["thread_id"])
            if thread:
                try:
                    mesaj = await thread.fetch_message(thread.id)
                    await mesaj.edit(embed=embed, view=view)
                    await thread.edit(name=guild.name[:100], archived=False)
                    await db.set_guild_thread(guild.id, thread.id, guild.name, davet)
                    return "guncellendi"
                except discord.HTTPException:
                    log.exception("Başlık güncellenemedi: %s", guild.name)
                    return "hata"

        forum = await self._forum()
        if not forum:
            log.warning("Forum kanalı ayarlanmamış; %s için başlık açılmadı.", guild.name)
            return "hata"
        kwargs = dict(name=guild.name[:100], embed=embed, auto_archive_duration=10080)
        if view:
            kwargs["view"] = view
        try:
            sonuc = await forum.create_thread(**kwargs)
        except discord.HTTPException:
            log.exception("Başlık oluşturulamadı: %s", guild.name)
            return "hata"
        await db.set_guild_thread(guild.id, sonuc.thread.id, guild.name, davet)
        return "yeni"

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        sonuc = await self.kayit_olustur(guild)
        if sonuc != "hata":
            row = await self.bot.db.get_guild_thread(guild.id)
            thread = await self._thread_al(row["thread_id"]) if row else None
            if thread:
                await thread.send("📥 **Bot sunucuya eklendi.**", allowed_mentions=YOK)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        row = await self.bot.db.get_guild_thread(guild.id)
        if not row:
            return
        thread = await self._thread_al(row["thread_id"])
        if not thread:
            return
        try:
            await thread.send("🚪 **Bot bu sunucudan ayrıldı / çıkarıldı.**", allowed_mentions=YOK)
            await thread.edit(name=f"[AYRILDI] {row['name']}"[:100])
        except discord.HTTPException:
            pass

    @commands.Cog.listener()
    async def on_app_command_completion(self, interaction: discord.Interaction, command):
        if not interaction.guild:
            return
        row = await self.bot.db.get_guild_thread(interaction.guild.id)
        if not row:
            return
        thread = await self._thread_al(row["thread_id"])
        if not thread:
            return
        kanal = getattr(interaction.channel, "name", "?")
        try:
            await thread.send(
                f"{discord.utils.format_dt(discord.utils.utcnow(), 'T')} • "
                f"👤 **{interaction.user}** → `/{command.qualified_name}` • #{kanal}",
                allowed_mentions=YOK,
            )
        except discord.HTTPException:
            pass

    @commands.Cog.listener()
    async def on_thread_delete(self, thread: discord.Thread):
        await self.bot.db.delete_guild_thread_by_thread(thread.id)

    @app_commands.command(
        name="forum-ayarla", description="[Kurucu] Sunucuların listeleneceği forum kanalını seçer."
    )
    @app_commands.describe(kanal="Forum kanalı")
    @app_commands.guild_only()
    @sadece_kurucu()
    async def forum_ayarla(self, interaction: discord.Interaction, kanal: discord.ForumChannel):
        await self.bot.db.set_global("forum_channel_id", kanal.id)
        await interaction.response.send_message(
            f"✅ Forum kanalı {kanal.mention} olarak ayarlandı!\n"
            "Bot şu an bulunduğu sunucuları da forumda görmek için "
            "`/sunucuları-senkronla` komutunu çalıştırın.",
            ephemeral=True,
        )

    @app_commands.command(
        name="sunucuları-senkronla",
        description="[Kurucu] Botun bulunduğu tüm sunucuları forumda oluşturur/günceller.",
    )
    @sadece_kurucu()
    async def senkronla(self, interaction: discord.Interaction):
        if not await self._forum():
            return await interaction.response.send_message(
                "⚠️ Önce `/forum-ayarla` ile forum kanalını seçin.", ephemeral=True
            )
        await interaction.response.defer(ephemeral=True)
        sayac = {"yeni": 0, "guncellendi": 0, "hata": 0}
        for guild in list(self.bot.guilds):
            sayac[await self.kayit_olustur(guild)] += 1
            await asyncio.sleep(1.5)
        await interaction.followup.send(
            f"✅ Senkronizasyon bitti.\n🆕 Yeni başlık: **{sayac['yeni']}**\n"
            f"🔄 Güncellenen: **{sayac['guncellendi']}**\n⚠️ Hatalı: **{sayac['hata']}**",
            ephemeral=True,
        )

    @app_commands.command(
        name="sunucu-liste", description="[Kurucu] Botun bulunduğu sunucuları davet linkleriyle listeler."
    )
    @sadece_kurucu()
    async def sunucu_liste(self, interaction: discord.Interaction):
        rows = await self.bot.db.list_guild_threads()
        if not rows:
            return await interaction.response.send_message(
                "📭 Henüz kayıtlı sunucu yok.", ephemeral=True
            )
        satirlar = []
        for r in rows:
            davet = f" • [Davet]({r['invite']})" if r["invite"] else ""
            satirlar.append(f"• **{r['name']}** → <#{r['thread_id']}>{davet}")
        embed = discord.Embed(
            title=f"🗂️ Kayıtlı Sunucular ({len(rows)})",
            description="\n".join(satirlar)[:4000],
            color=config.RENK_ANA,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Forum(bot))
