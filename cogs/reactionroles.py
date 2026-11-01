"""Reaction-role: emoji/butona basarak rol alma paneli."""

import discord
from discord import app_commands
from discord.ext import commands

import config
from utils import make_embed


def panel_view(satirlar) -> discord.ui.View:
    view = discord.ui.View(timeout=None)
    for emoji, role_id, label in satirlar[:25]:
        view.add_item(RolButonu(emoji, role_id, label))
    return view


class RolButonu(discord.ui.Button):
    def __init__(self, emoji: str, role_id: int, label: str):
        super().__init__(
            label=label[:80], emoji=emoji or None,
            style=discord.ButtonStyle.secondary,
            custom_id=f"yildiz:rr:{role_id}",
        )
        self.role_id = role_id

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        rol = guild.get_role(self.role_id)
        if not rol:
            return await interaction.response.send_message("⚠️ Rol artık mevcut değil.", ephemeral=True)
        if rol >= guild.me.top_role:
            return await interaction.response.send_message(
                "⚠️ Bu rolü veremem, rolüm yeterince yüksek değil.", ephemeral=True
            )
        uye = interaction.user
        if rol in uye.roles:
            await uye.remove_roles(rol, reason="Reaction role")
            await interaction.response.send_message(f"❌ {rol.mention} rolü kaldırıldı.", ephemeral=True)
        else:
            await uye.add_roles(rol, reason="Reaction role")
            await interaction.response.send_message(f"✅ {rol.mention} rolü verildi.", ephemeral=True)


class ReactionRoles(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        panelller = await self.bot.db.all_reaction_role_panels()
        for p in panelller:
            satirlar_raw = await self.bot.db.get_reaction_roles(p["message_id"])
            satirlar = [(r["emoji"], r["role_id"], r["label"]) for r in satirlar_raw]
            if satirlar:
                self.bot.add_view(panel_view(satirlar), message_id=p["message_id"])

    @app_commands.command(
        name="rol-panel-oluştur",
        description="[Yönetici] Emoji+rol+etiket listesiyle buton paneli oluşturur.",
    )
    @app_commands.describe(
        baslik="Panelin başlığı",
        satirlar=(
            "Her satıra bir tane: emoji | @rol | etiket. "
            "Örnek: 🎮 | @Oyuncu | Oyuncu Rolü"
        ),
    )
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def panel_olustur(self, interaction: discord.Interaction, baslik: str, satirlar: str):
        guild = interaction.guild
        hazirlanan = []
        hatalar = []
        for satir in satirlar.splitlines():
            satir = satir.strip()
            if not satir:
                continue
            parcalar = [p.strip() for p in satir.split("|")]
            if len(parcalar) < 2:
                hatalar.append(satir)
                continue
            emoji = parcalar[0]
            rol = discord.utils.find(
                lambda r, p=parcalar[1]: p.strip("<@&>") == str(r.id) or p.lstrip("@") == r.name,
                guild.roles,
            )
            if not rol:
                hatalar.append(satir)
                continue
            etiket = parcalar[2] if len(parcalar) > 2 else rol.name
            hazirlanan.append((emoji, rol.id, etiket))

        if not hazirlanan:
            return await interaction.response.send_message(
                "❌ Geçerli bir satır bulunamadı. Format: `emoji | @rol | etiket`", ephemeral=True
            )

        embed = make_embed(f"🎭 {baslik}", config.RENK_ANA,
                           "Rol almak/kaldırmak için ilgili butona tıkla.")
        await interaction.response.send_message("✅ Panel oluşturuluyor...", ephemeral=True)
        mesaj = await interaction.channel.send(embed=embed, view=panel_view(hazirlanan))

        for emoji, role_id, etiket in hazirlanan:
            await self.bot.db.add_reaction_role(guild.id, mesaj.id, emoji, role_id, etiket)

        if hatalar:
            await interaction.followup.send(
                "⚠️ Şu satırlar tanınamadı (rol bulunamadı): \n" + "\n".join(hatalar), ephemeral=True
            )

    @app_commands.command(name="rol-panel-sil", description="[Yönetici] Bir rol panelini siler.")
    @app_commands.describe(mesaj_id="Panel mesajının ID'si")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def panel_sil(self, interaction: discord.Interaction, mesaj_id: str):
        try:
            mid = int(mesaj_id)
        except ValueError:
            return await interaction.response.send_message("❌ Geçersiz mesaj ID'si.", ephemeral=True)
        await self.bot.db.delete_reaction_panel(mid)
        try:
            mesaj = await interaction.channel.fetch_message(mid)
            await mesaj.delete()
        except discord.HTTPException:
            pass
        await interaction.response.send_message("🗑️ Panel silindi.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(ReactionRoles(bot))
