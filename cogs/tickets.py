"""Buton tabanlı destek (ticket) sistemi."""

import asyncio

import discord
from discord import app_commands
from discord.ext import commands

import config
from utils import guvenli_kanal_adi, make_embed, send_log


def ticket_sahibi(channel: discord.abc.GuildChannel):
    topic = getattr(channel, "topic", None) or ""
    if topic.startswith("ticket:"):
        try:
            return int(topic.split(":", 1)[1])
        except ValueError:
            return None
    return None


class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Destek Talebi Aç", emoji="🎫",
        style=discord.ButtonStyle.primary, custom_id="simsek:ticket_open",
    )
    async def ac(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        user = interaction.user

        for ch in guild.text_channels:
            if ticket_sahibi(ch) == user.id:
                return await interaction.response.send_message(
                    f"⚠️ Zaten açık bir talebiniz var: {ch.mention}", ephemeral=True
                )

        await interaction.response.defer(ephemeral=True)
        s = await interaction.client.db.get_settings(guild.id)
        kategori = guild.get_channel(s.get("ticket_category_id") or 0)
        staff = guild.get_role(s.get("ticket_staff_role_id") or 0)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(
                view_channel=True, send_messages=True,
                attach_files=True, read_message_history=True,
            ),
            guild.me: discord.PermissionOverwrite(
                view_channel=True, send_messages=True,
                manage_channels=True, read_message_history=True,
            ),
        }
        if staff:
            overwrites[staff] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True,
                attach_files=True, read_message_history=True,
            )

        try:
            kanal = await guild.create_text_channel(
                name="ticket-" + guvenli_kanal_adi(user.name, str(user.id)),
                category=kategori if isinstance(kategori, discord.CategoryChannel) else None,
                topic=f"ticket:{user.id}",
                overwrites=overwrites,
                reason=f"{user} destek talebi açtı",
            )
        except discord.Forbidden:
            return await interaction.followup.send(
                "⚠️ Kanal oluşturma yetkim yok. Yöneticiye bildirin.", ephemeral=True
            )

        embed = make_embed(
            "🎫 Destek Talebi",
            config.RENK_ANA,
            f"Merhaba {user.mention}! Sorununuzu detaylıca yazın, "
            "yetkililer en kısa sürede ilgilenecek.\n\n"
            "Talebi kapatmak için aşağıdaki butonu kullanın.",
        )
        mention = staff.mention if staff else ""
        await kanal.send(content=f"{user.mention} {mention}".strip(),
                         embed=embed, view=TicketKapatView())
        await interaction.followup.send(f"✅ Talebiniz oluşturuldu: {kanal.mention}", ephemeral=True)

        log = make_embed("🎫 Ticket Açıldı", config.RENK_BASARI)
        log.add_field(name="Kullanıcı", value=user.mention, inline=True)
        log.add_field(name="Kanal", value=kanal.mention, inline=True)
        await send_log(interaction.client, guild, log)


class TicketKapatView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Talebi Kapat", emoji="🔒",
        style=discord.ButtonStyle.danger, custom_id="simsek:ticket_close",
    )
    async def kapat(self, interaction: discord.Interaction, button: discord.ui.Button):
        kanal = interaction.channel
        s = await interaction.client.db.get_settings(interaction.guild.id)
        yetkili_rol = s.get("ticket_staff_role_id")
        izinli = (
            ticket_sahibi(kanal) == interaction.user.id
            or interaction.user.guild_permissions.manage_channels
            or (yetkili_rol and any(r.id == yetkili_rol for r in interaction.user.roles))
        )
        if not izinli:
            return await interaction.response.send_message(
                "⛔ Bu talebi kapatma yetkiniz yok.", ephemeral=True
            )

        await interaction.response.send_message("🔒 Talep **5 saniye** içinde kapatılıyor...")
        log = make_embed("🔒 Ticket Kapatıldı", config.RENK_HATA)
        log.add_field(name="Kanal", value=f"#{kanal.name}", inline=True)
        log.add_field(name="Kapatan", value=interaction.user.mention, inline=True)
        await send_log(interaction.client, interaction.guild, log)
        await asyncio.sleep(5)
        try:
            await kanal.delete(reason=f"Ticket {interaction.user} tarafından kapatıldı")
        except discord.HTTPException:
            pass


class Tickets(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(TicketPanelView())
        self.bot.add_view(TicketKapatView())

    @app_commands.command(
        name="ticket-ayarla",
        description="Ticket kategorisini ve yetkili rolünü belirler.",
    )
    @app_commands.describe(
        kategori="Ticket kanallarının açılacağı kategori",
        yetkili_rol="Ticketları görebilecek yetkili rolü",
    )
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def ticket_ayarla(
        self, interaction: discord.Interaction,
        kategori: discord.CategoryChannel = None, yetkili_rol: discord.Role = None,
    ):
        db = self.bot.db
        if kategori:
            await db.set_setting(interaction.guild.id, "ticket_category_id", kategori.id)
        if yetkili_rol:
            await db.set_setting(interaction.guild.id, "ticket_staff_role_id", yetkili_rol.id)
        if not kategori and not yetkili_rol:
            return await interaction.response.send_message(
                "ℹ️ En az bir seçenek belirtin.", ephemeral=True
            )
        await interaction.response.send_message("✅ Ticket ayarları güncellendi.", ephemeral=True)

    @app_commands.command(
        name="ticket-panel", description="Bu kanala destek talebi paneli gönderir."
    )
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def ticket_panel(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🎫 Destek Merkezi",
            description=(
                "Bir sorunun veya şikayetin mi var?\n"
                "Aşağıdaki butona tıklayarak yetkililerle özel bir kanalda görüşebilirsin."
            ),
            color=config.RENK_ANA,
        )
        embed.set_footer(text=f"{config.BOT_ADI} Destek Sistemi")
        await interaction.response.send_message("✅ Panel gönderildi.", ephemeral=True)
        await interaction.channel.send(embed=embed, view=TicketPanelView())


async def setup(bot):
    await bot.add_cog(Tickets(bot))
