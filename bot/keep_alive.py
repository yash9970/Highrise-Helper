import threading
import os
import time
from flask import Flask, jsonify

app = Flask(__name__)

# Shared state — bot.py writes to this so we can expose it via /status
bot_status = {
    "connected": False,
    "session_id": None,
    "reconnect_attempts": 0,
    "last_connected_at": None,
}


@app.route("/")
def home():
    return "ZenBot is alive and running! 🤖"


@app.route("/ping")
def ping():
    return "pong"


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "bot_connected": bot_status["connected"],
        "reconnect_attempts": bot_status["reconnect_attempts"],
        "last_connected_at": bot_status["last_connected_at"],
    })


@app.route("/status")
def status():
    return jsonify(bot_status)


def run_keep_alive():
    port = int(os.environ.get("PORT", 8000))
    t = threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=port, use_reloader=False),
        daemon=True,
    )
    t.start()
    print(f"[KEEP-ALIVE] Web server started on port {port}")
