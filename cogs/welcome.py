"""Resimli karşılama kartı (Pillow ile üretilir) ve karşılama mesajı."""

import io

import discord
from discord import app_commands
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont, ImageOps

import config
from utils import make_embed

KART_GENISLIK = 900
KART_YUKSEKLIK = 300
AVATAR_BOYUT = 180
VARSAYILAN_ARKA_PLAN = (47, 49, 54)


def _font(boyut: int):
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf", boyut)
    except Exception:
        return ImageFont.load_default()


def _hex_to_rgb(hex_str: str):
    hex_str = hex_str.lstrip("#")
    if len(hex_str) != 6:
        return VARSAYILAN_ARKA_PLAN
    try:
        return tuple(int(hex_str[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return VARSAYILAN_ARKA_PLAN


async def karsilama_karti_olustur(member: discord.Member, arka_plan_hex: str | None) -> io.BytesIO:
    renk_ust = _hex_to_rgb(arka_plan_hex) if arka_plan_hex else VARSAYILAN_ARKA_PLAN
    renk_alt = tuple(max(0, c - 25) for c in renk_ust)

    kart = Image.new("RGB", (KART_GENISLIK, KART_YUKSEKLIK), renk_ust)
    cizici = ImageDraw.Draw(kart)
    for y in range(KART_YUKSEKLIK):
        oran = y / KART_YUKSEKLIK
        renk = tuple(int(renk_ust[i] + (renk_alt[i] - renk_ust[i]) * oran) for i in range(3))
        cizici.line([(0, y), (KART_GENISLIK, y)], fill=renk)

    avatar_bytes = await member.display_avatar.replace(size=256).read()
    avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA").resize((AVATAR_BOYUT, AVATAR_BOYUT))
    maske = Image.new("L", (AVATAR_BOYUT, AVATAR_BOYUT), 0)
    ImageDraw.Draw(maske).ellipse((0, 0, AVATAR_BOYUT, AVATAR_BOYUT), fill=255)
    avatar_yuvarlak = ImageOps.fit(avatar, (AVATAR_BOYUT, AVATAR_BOYUT))
    kart.paste(avatar_yuvarlak, (60, (KART_YUKSEKLIK - AVATAR_BOYUT) // 2), maske)

    cizici.ellipse((56, (KART_YUKSEKLIK - AVATAR_BOYUT) // 2 - 4,
                    56 + AVATAR_BOYUT + 8, (KART_YUKSEKLIK - AVATAR_BOYUT) // 2 + AVATAR_BOYUT + 4),
                   outline=(255, 255, 255), width=4)

    metin_x = 280
    cizici.text((metin_x, 95), "HOŞ GELDİN", font=_font(28), fill=(200, 200, 200))
    isim = member.display_name
    if len(isim) > 20:
        isim = isim[:19] + "…"
    cizici.text((metin_x, 130), isim, font=_font(44), fill=(255, 255, 255))
    cizici.text(
        (metin_x, 190),
        f"Sen {member.guild.member_count}. üyemizsin!",
        font=_font(22), fill=(190, 190, 190),
    )

    arabellek = io.BytesIO()
    kart.save(arabellek, format="PNG")
    arabellek.seek(0)
    return arabellek


class Welcome(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot:
            return
        s = await self.bot.db.get_settings(member.guild.id)
        if not s.get("welcome_channel_id"):
            return
        kanal = member.guild.get_channel(s["welcome_channel_id"])
        if not kanal:
            return

        if s.get("welcome_card_enabled", 1) == 0:
            embed = discord.Embed(
                title="👋 Hoş Geldin!",
                description=f"{member.mention}, **{member.guild.name}** sunucusuna hoş geldin!",
                color=config.RENK_ANA,
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            try:
                await kanal.send(embed=embed)
            except discord.HTTPException:
                pass
            return

        try:
            arabellek = await karsilama_karti_olustur(member, s.get("welcome_background_hex"))
            dosya = discord.File(arabellek, filename="hosgeldin.png")
            await kanal.send(content=member.mention, file=dosya)
        except Exception:
            embed = discord.Embed(
                title="👋 Hoş Geldin!",
                description=f"{member.mention}, **{member.guild.name}** sunucusuna hoş geldin!",
                color=config.RENK_ANA,
            )
            await kanal.send(embed=embed)

    @app_commands.command(name="karşılama-önizle", description="Karşılama kartının nasıl göründüğünü gösterir.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def onizle(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        s = await self.bot.db.get_settings(interaction.guild.id)
        arabellek = await karsilama_karti_olustur(interaction.user, s.get("welcome_background_hex"))
        dosya = discord.File(arabellek, filename="onizleme.png")
        await interaction.followup.send(file=dosya, ephemeral=True)

    @app_commands.command(name="karşılama-renk-ayarla", description="[Yönetici] Karşılama kartının arka plan rengini ayarlar.")
    @app_commands.describe(hex_renk="Örnek: 2F3136 (# işareti olmadan)")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def renk_ayarla(self, interaction: discord.Interaction, hex_renk: str):
        hex_renk = hex_renk.lstrip("#")
        if len(hex_renk) != 6:
            return await interaction.response.send_message(
                "❌ Geçersiz renk kodu. Örnek: `2F3136`", ephemeral=True
            )
        await self.bot.db.set_setting(interaction.guild.id, "welcome_background_hex", hex_renk)
        await interaction.response.send_message(f"✅ Karşılama kartı rengi **#{hex_renk}** olarak ayarlandı.", ephemeral=True)

    @app_commands.command(name="karşılama-kart", description="[Yönetici] Resimli karşılama kartını açar/kapatır.")
    @app_commands.describe(durum="Açık mı kapalı mı olsun")
    @app_commands.choices(durum=[
        app_commands.Choice(name="Açık (resimli kart)", value="acik"),
        app_commands.Choice(name="Kapalı (sade embed)", value="kapali"),
    ])
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def kart_durumu(self, interaction: discord.Interaction, durum: app_commands.Choice[str]):
        await self.bot.db.set_setting(
            interaction.guild.id, "welcome_card_enabled", 1 if durum.value == "acik" else 0
        )
        await interaction.response.send_message(f"✅ Karşılama kartı **{durum.name}**.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Welcome(bot))
