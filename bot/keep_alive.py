import threading
import os
from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return "ZenBot is alive and running! 🤖"

@app.route("/health")
def health():
    return {"status": "ok", "bot": "ZenBot", "version": "1.0"}

@app.route("/ping")
def ping():
    return "pong"

def run_keep_alive():
    port = int(os.environ.get("PORT", 8000))
    t = threading.Thread(target=lambda: app.run(host="0.0.0.0", port=port), daemon=True)
    t.start()
    print(f"[KEEP-ALIVE] Web server started on port {port}")
