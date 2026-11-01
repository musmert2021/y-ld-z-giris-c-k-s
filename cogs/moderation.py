"""Moderasyon komutları: ban, kick, timeout, unban, kilit, sil, rol, isim."""

import datetime

import discord
from discord import app_commands
from discord.ext import commands

import config
from utils import dm_gonder, hiyerarsi_hatasi, make_embed, send_log


class Moderation(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="ban", description="Belirttiğiniz üyeyi sunucudan kalıcı olarak yasaklar."
    )
    @app_commands.describe(uye="Yasaklanacak üye", sebep="Yasaklanma nedeni")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban(
        self, interaction: discord.Interaction, uye: discord.Member,
        sebep: str = "Belirtilmedi",
    ):
        hata = hiyerarsi_hatasi(interaction, uye)
        if hata:
            return await interaction.response.send_message(hata, ephemeral=True)

        await interaction.response.defer(thinking=True)
        dm = make_embed("🔨 Yasaklandınız", config.RENK_HATA)
        dm.add_field(name="Sunucu", value=interaction.guild.name, inline=False)
        dm.add_field(name="Sebep", value=sebep, inline=False)
        await dm_gonder(uye, dm)
        try:
            await uye.ban(reason=f"{interaction.user}: {sebep}")
        except discord.Forbidden:
            return await interaction.followup.send(
                "⚠️ Bu üyeyi yasaklamak için yetkim yetmiyor! Rolümü üste çekin."
            )
        await interaction.followup.send(
            f"🔨 {uye.name} sunucudan **yasaklandı!**\n📄 **Sebep:** {sebep}"
        )
        embed = make_embed("🔨 Üye Yasaklandı", discord.Color.dark_red())
        embed.add_field(name="Üye", value=f"{uye} ({uye.id})", inline=True)
        embed.add_field(name="Yetkili", value=interaction.user.mention, inline=True)
        embed.add_field(name="Sebep", value=sebep, inline=False)
        await send_log(self.bot, interaction.guild, embed)

    @app_commands.command(
        name="unban", description="Yasaklı bir üyenin banını ID numarası ile kaldırır."
    )
    @app_commands.describe(kullanici_id="Banı kaldırılacak kişinin sayısal ID adresi")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(ban_members=True)
    async def unban(self, interaction: discord.Interaction, kullanici_id: str):
        await interaction.response.defer(thinking=True)
        try:
            user = await self.bot.fetch_user(int(kullanici_id))
            await interaction.guild.unban(user)
        except (ValueError, discord.NotFound):
            return await interaction.followup.send(
                "❌ Bu ID numarasına ait banlı bir kullanıcı bulunamadı."
            )
        except discord.Forbidden:
            return await interaction.followup.send("⚠️ Ban kaldırmak için yetkim yok!")
        await interaction.followup.send(
            f"🔓 **{user.name}** isimli kullanıcının banı kaldırıldı!"
        )
        embed = make_embed("🔓 Ban Kaldırıldı", config.RENK_BASARI)
        embed.add_field(name="Kullanıcı", value=f"{user} ({user.id})", inline=True)
        embed.add_field(name="Yetkili", value=interaction.user.mention, inline=True)
        await send_log(self.bot, interaction.guild, embed)

    @app_commands.command(name="kick", description="Belirttiğiniz üyeyi sunucudan atar.")
    @app_commands.describe(uye="Sunucudan atılacak üye", sebep="Atılma nedeni")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick(
        self, interaction: discord.Interaction, uye: discord.Member,
        sebep: str = "Belirtilmedi",
    ):
        hata = hiyerarsi_hatasi(interaction, uye)
        if hata:
            return await interaction.response.send_message(hata, ephemeral=True)

        await interaction.response.defer(thinking=True)
        dm = make_embed("🚪 Sunucudan Atıldınız", config.RENK_UYARI)
        dm.add_field(name="Sunucu", value=interaction.guild.name, inline=False)
        dm.add_field(name="Sebep", value=sebep, inline=False)
        await dm_gonder(uye, dm)
        try:
            await uye.kick(reason=f"{interaction.user}: {sebep}")
        except discord.Forbidden:
            return await interaction.followup.send(
                "⚠️ Bu üyeyi sunucudan atmak için yetkim yetmiyor!"
            )
        await interaction.followup.send(
            f"🚪 {uye.name} sunucudan **atıldı!**\n📄 **Sebep:** {sebep}"
        )
        embed = make_embed("🚪 Üye Atıldı", config.RENK_UYARI)
        embed.add_field(name="Üye", value=f"{uye} ({uye.id})", inline=True)
        embed.add_field(name="Yetkili", value=interaction.user.mention, inline=True)
        embed.add_field(name="Sebep", value=sebep, inline=False)
        await send_log(self.bot, interaction.guild, embed)

    @app_commands.command(
        name="timeout", description="Kurallara uymayan bir üyeyi belirli süre susturur."
    )
    @app_commands.describe(
        uye="Susturulacak üye",
        dakika="Kaç dakika susturulsun? (1 - 40320)",
        sebep="Susturulma nedeni",
    )
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(moderate_members=True)
    async def timeout(
        self, interaction: discord.Interaction, uye: discord.Member,
        dakika: app_commands.Range[int, 1, 40320], sebep: str = "Belirtilmedi",
    ):
        hata = hiyerarsi_hatasi(interaction, uye)
        if hata:
            return await interaction.response.send_message(hata, ephemeral=True)

        await interaction.response.defer(thinking=True)
        try:
            await uye.timeout(datetime.timedelta(minutes=dakika), reason=sebep)
        except discord.Forbidden:
            return await interaction.followup.send(
                "⚠️ Yetki hatası! Bot rolünü en yukarı taşımalısınız."
            )
        await interaction.followup.send(
            f"🔇 {uye.mention} **{dakika} dakika** susturuldu.\n📄 **Sebep:** {sebep}"
        )
        embed = make_embed("🔇 Üye Susturuldu", discord.Color.dark_orange())
        embed.add_field(name="Üye", value=uye.mention, inline=True)
        embed.add_field(name="Yetkili", value=interaction.user.mention, inline=True)
        embed.add_field(name="Süre", value=f"{dakika} dk", inline=True)
        embed.add_field(name="Sebep", value=sebep, inline=False)
        await send_log(self.bot, interaction.guild, embed)

    @app_commands.command(
        name="timeout-kaldır", description="Bir üyenin susturmasını kaldırır."
    )
    @app_commands.describe(uye="Susturması kaldırılacak üye")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(moderate_members=True)
    async def timeout_kaldir(self, interaction: discord.Interaction, uye: discord.Member):
        if not uye.is_timed_out():
            return await interaction.response.send_message(
                "ℹ️ Bu üye zaten susturulmuş değil.", ephemeral=True
            )
        try:
            await uye.timeout(None, reason=f"{interaction.user} tarafından kaldırıldı")
        except discord.Forbidden:
            return await interaction.response.send_message(
                "⚠️ Yetkim yetersiz!", ephemeral=True
            )
        await interaction.response.send_message(
            f"🔊 {uye.mention} kullanıcısının susturması kaldırıldı."
        )

    @app_commands.command(
        name="lockdown", description="Mevcut kanalı sohbet için geçici olarak kilitler."
    )
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_channels=True)
    async def lockdown(self, interaction: discord.Interaction):
        kanal = interaction.channel
        izin = kanal.overwrites_for(interaction.guild.default_role)
        izin.send_messages = False
        await kanal.set_permissions(interaction.guild.default_role, overwrite=izin)
        await interaction.response.send_message(
            f"🔒 {kanal.mention} kanalı güvenlik nedeniyle kilitlendi!"
        )
        embed = make_embed("🔒 Kanal Kilitlendi", discord.Color.dark_red())
        embed.add_field(name="Kanal", value=kanal.mention, inline=True)
        embed.add_field(name="Yetkili", value=interaction.user.mention, inline=True)
        await send_log(self.bot, interaction.guild, embed)

    @app_commands.command(
        name="unlock", description="Kilitlenmiş kanalı tekrar konuşmaya açar."
    )
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_channels=True)
    async def unlock(self, interaction: discord.Interaction):
        kanal = interaction.channel
        izin = kanal.overwrites_for(interaction.guild.default_role)
        izin.send_messages = None
        await kanal.set_permissions(interaction.guild.default_role, overwrite=izin)
        await interaction.response.send_message(
            f"🔓 {kanal.mention} kanalının kilidi kaldırıldı, tekrar aktif!"
        )
        embed = make_embed("🔓 Kanal Kilidi Açıldı", config.RENK_BASARI)
        embed.add_field(name="Kanal", value=kanal.mention, inline=True)
        embed.add_field(name="Yetkili", value=interaction.user.mention, inline=True)
        await send_log(self.bot, interaction.guild, embed)

    @app_commands.command(
        name="yavaş-mod", description="Kanalın yavaş mod süresini ayarlar (0 = kapat)."
    )
    @app_commands.describe(saniye="Mesajlar arası bekleme süresi (0-21600 sn)")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_channels=True)
    async def yavas_mod(
        self, interaction: discord.Interaction,
        saniye: app_commands.Range[int, 0, 21600],
    ):
        await interaction.channel.edit(slowmode_delay=saniye)
        if saniye == 0:
            await interaction.response.send_message("🐇 Yavaş mod kapatıldı.")
        else:
            await interaction.response.send_message(
                f"🐢 Yavaş mod **{saniye} saniye** olarak ayarlandı."
            )

    @app_commands.command(name="sil", description="Girdiğiniz miktarda mesajı temizler.")
    @app_commands.describe(miktar="Silinecek mesaj sayısı (1-100)")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_messages=True)
    async def sil(
        self, interaction: discord.Interaction, miktar: app_commands.Range[int, 1, 100]
    ):
        await interaction.response.defer(ephemeral=True)
        silinen = await interaction.channel.purge(limit=miktar)
        await interaction.followup.send(
            f"🧹 Kanaldan **{len(silinen)}** adet mesaj temizlendi.", ephemeral=True
        )
        embed = make_embed("🧹 Mesajlar Temizlendi", discord.Color.light_grey())
        embed.add_field(name="Kanal", value=interaction.channel.mention, inline=True)
        embed.add_field(name="Yetkili", value=interaction.user.mention, inline=True)
        embed.add_field(name="Adet", value=str(len(silinen)), inline=True)
        await send_log(self.bot, interaction.guild, embed)

    @app_commands.command(
        name="isim-değiştir", description="Bir üyenin sunucudaki takma adını değiştirir."
    )
    @app_commands.describe(
        uye="İsmi değiştirilecek üye", yeni_isim="Verilecek yeni takma ad"
    )
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_nicknames=True)
    async def isimdegistir(
        self, interaction: discord.Interaction, uye: discord.Member,
        yeni_isim: app_commands.Range[str, 1, 32],
    ):
        hata = hiyerarsi_hatasi(interaction, uye)
        if hata and uye.id != interaction.user.id:
            return await interaction.response.send_message(hata, ephemeral=True)
        await interaction.response.defer(thinking=True)
        try:
            await uye.edit(nick=yeni_isim)
        except discord.Forbidden:
            return await interaction.followup.send(
                "⚠️ Yetkim yetersiz veya sunucu sahibinin ismini değiştirmeye çalışıyorsunuz!"
            )
        await interaction.followup.send(
            f"📝 {uye.mention} kullanıcısının ismi **{yeni_isim}** olarak değiştirildi!"
        )

    @app_commands.command(
        name="rol-düzenle",
        description="Kullanıcıya veya tüm botlara toplu/tekli rol ekler veya kaldırır.",
    )
    @app_commands.describe(
        islem="Yapılacak işlem türü",
        rol="İşlem yapılacak rol",
        uye="İşlem yapılacak üye (bot işlemlerinde gerekmez)",
    )
    @app_commands.choices(islem=[
        app_commands.Choice(name="Kullanıcıya Rol Ekle (+)", value="uye_ekle"),
        app_commands.Choice(name="Kullanıcıdan Rol Kaldır (-)", value="uye_kaldir"),
        app_commands.Choice(name="Tüm Botlara Toplu Rol Ekle (🤖+)", value="bot_ekle"),
        app_commands.Choice(name="Tüm Botlardan Toplu Rol Kaldır (🤖-)", value="bot_kaldir"),
    ])
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_roles=True)
    async def rolduzenle(
        self, interaction: discord.Interaction, islem: app_commands.Choice[str],
        rol: discord.Role, uye: discord.Member = None,
    ):
        guild = interaction.guild
        if rol.is_default() or rol.managed:
            return await interaction.response.send_message(
                "⛔ Bu rol verilemez/alınamaz (@everyone veya bot/entegrasyon rolü).",
                ephemeral=True,
            )
        if interaction.user.id != guild.owner_id and rol >= interaction.user.top_role:
            return await interaction.response.send_message(
                "⛔ Kendi rolünüzden yüksek veya eşit bir rolü yönetemezsiniz!",
                ephemeral=True,
            )
        if rol >= guild.me.top_role:
            return await interaction.response.send_message(
                "⚠️ Bu rol benim rolümden yüksek/eşit. Bot rolünü yukarı taşıyın.",
                ephemeral=True,
            )

        await interaction.response.defer(thinking=True)
        try:
            if islem.value in ("uye_ekle", "uye_kaldir"):
                if uye is None:
                    return await interaction.followup.send(
                        "⚠️ **Hata:** Lütfen bir `uye` seçin!"
                    )
                hata = hiyerarsi_hatasi(interaction, uye)
                if hata and uye.id != interaction.user.id:
                    return await interaction.followup.send(hata)
                if islem.value == "uye_ekle":
                    await uye.add_roles(rol)
                    await interaction.followup.send(
                        f"✅ {uye.mention} kullanıcısına **{rol.name}** rolü **eklendi**."
                    )
                else:
                    await uye.remove_roles(rol)
                    await interaction.followup.send(
                        f"❌ {uye.mention} kullanıcısından **{rol.name}** rolü **kaldırıldı**."
                    )
            else:
                sayac = 0
                for m in guild.members:
                    if not m.bot:
                        continue
                    try:
                        if islem.value == "bot_ekle" and rol not in m.roles:
                            await m.add_roles(rol)
                            sayac += 1
                        elif islem.value == "bot_kaldir" and rol in m.roles:
                            await m.remove_roles(rol)
                            sayac += 1
                    except discord.HTTPException:
                        pass
                await interaction.followup.send(
                    f"🤖 İşlem tamamlandı! **{sayac}** bot hesaba işlem uygulandı."
                )
        except discord.Forbidden:
            await interaction.followup.send(
                "⚠️ Yetki hatası! Lütfen bot rolünü en yukarıya taşıyın."
            )


async def setup(bot):
    await bot.add_cog(Moderation(bot))
