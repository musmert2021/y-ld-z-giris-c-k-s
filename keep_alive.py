"""7/24 aktif tutmak için Flask sunucusu."""

import os
from threading import Thread

from flask import Flask

app = Flask("")


@app.route("/")
def home():
    return "ŞİMŞEK 7/24 Aktif ve Koruma Modunda!"


def _run():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))


def keep_alive():
    Thread(target=_run, daemon=True).start()
