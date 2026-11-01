"""
YILDIZ Bot — Çok Amaçlı Sunucu Botu
"""

import logging
import os

import discord
from discord import app_commands
from discord.ext import commands

import config
from database import Database
from keep_alive import keep_alive
from utils import SadeceKurucu

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("simsek")


class SimsekBot(commands.Bot):

    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents, help_command=None)
        self.db = Database(config.DB_PATH)
        self._temizlendi = False

    async def setup_hook(self):
        await self.db.connect()
        for ext in config.EXTENSIONS:
            try:
                await self.load_extension(ext)
                log.info("Modül yüklendi: %s", ext)
            except Exception:
                log.exception("Modül yüklenemedi: %s", ext)

        self.tree.on_error = self.on_tree_error
        await self.tree.sync()
        log.info("Komutlar küresel olarak senkronize edildi.")

    async def close(self):
        await self.db.close()
        await super().close()

    async def on_ready(self):
        if not self._temizlendi:
            self._temizlendi = True
            for guild in self.guilds:
                try:
                    self.tree.clear_commands(guild=guild)
                    await self.tree.sync(guild=guild)
                except Exception:
                    log.exception("%s temizleme hatası", guild.name)

        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching, name=f"{config.BOT_ADI} Sunucusunu 🛡️"
            )
        )
        log.info("%s aktif! %d sunucuda çalışıyor.", self.user, len(self.guilds))

    async def on_tree_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        if isinstance(error, SadeceKurucu):
            msg = "⛔ Bu komutu sadece **bot kurucusu** kullanabilir!"
        elif isinstance(error, app_commands.MissingPermissions):
            msg = "⛔ Bu komutu kullanmak için yetkiniz yok!"
        elif isinstance(error, app_commands.BotMissingPermissions):
            msg = "⚠️ Bu işlem için botun gerekli yetkisi yok!"
        elif isinstance(error, app_commands.NoPrivateMessage):
            msg = "⛔ Bu komut sadece sunucularda kullanılabilir."
        elif isinstance(error, app_commands.CommandOnCooldown):
            msg = f"⏳ Lütfen {error.retry_after:.0f} saniye sonra tekrar deneyin."
        else:
            msg = "⚠️ Beklenmeyen bir hata oluştu."
            log.error("Komut hatası", exc_info=error)

        try:
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except discord.HTTPException:
            pass


def main():
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise SystemExit("❌ DISCORD_TOKEN ortam değişkeni bulunamadı!")
    keep_alive()
    SimsekBot().run(token, log_handler=None)


if __name__ == "__main__":
    main()
