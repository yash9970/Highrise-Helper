import threading
import os
import time
from flask import Flask, jsonify, request

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


@app.route("/vips")
def get_vips():
    from store import load_data
    data = load_data()
    return jsonify(list(data.get("vips", {}).keys()))


@app.route("/mods")
def get_mods():
    from store import load_data
    data = load_data()
    return jsonify(list(data.get("mods", {}).keys()))


@app.route("/djpos", methods=["GET"])
def get_dj_position():
    from store import load_data, get_dj_pos
    data = load_data()
    pos = get_dj_pos(data)
    if pos:
        return jsonify(pos)
    return jsonify({"error": "No position saved"}), 404


@app.route("/djpos", methods=["POST"])
def set_dj_position():
    from store import load_data, save_data, set_dj_pos
    import asyncio
    
    req = request.get_json()
    if not req or "x" not in req or "y" not in req or "z" not in req:
        return jsonify({"error": "Missing coordinates"}), 400
        
    data = load_data()
    set_dj_pos(req["x"], req["y"], req["z"], req.get("facing", "FrontLeft"), data)
    
    # save_data is async, so we need to run it in the event loop if one exists,
    # or create a new loop just to save it (since Flask runs in a separate thread)
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError
        loop.create_task(save_data(data))
    except (RuntimeError, ValueError):
        asyncio.run(save_data(data))
        
    return jsonify({"success": True, "pos": get_dj_pos(data)})


def run_keep_alive():
    port = int(os.environ.get("PORT", 8000))
    t = threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=port, use_reloader=False),
        daemon=True,
    )
    t.start()
    print(f"[KEEP-ALIVE] Web server started on port {port}")
