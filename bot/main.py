import os
import sys
import time
import subprocess
import threading

sys.path.insert(0, os.path.dirname(__file__))
from keep_alive import run_keep_alive

RECONNECT_DELAY = 15


def run_bot_loop(token: str, room_id: str):
    attempt = 0
    while True:
        attempt += 1
        print(f"[MAIN] Starting bot (attempt #{attempt}) for room: {room_id}")
        try:
            result = subprocess.run(
                [sys.executable, "-m", "highrise", "bot:HigrhiseBot", room_id, token],
                cwd=os.path.dirname(__file__),
                env={"PYTHONUNBUFFERED": "1", **os.environ},
            )
            print(f"[MAIN] Bot exited with code {result.returncode}.")
        except Exception as e:
            print(f"[MAIN] Failed to start bot process: {e}")
        print(f"[MAIN] Reconnecting in {RECONNECT_DELAY}s...")
        time.sleep(RECONNECT_DELAY)


if __name__ == "__main__":
    token = os.environ.get("HIGHRISE_TOKEN")
    room_id = os.environ.get("HIGHRISE_ROOM_ID")

    if not token:
        raise RuntimeError("HIGHRISE_TOKEN is not set!")
    if not room_id:
        raise RuntimeError("HIGHRISE_ROOM_ID is not set!")

    # Start the keep-alive web server in a daemon thread
    run_keep_alive()

    # Run the bot loop in the main thread (blocks forever, reconnects on crash)
    run_bot_loop(token, room_id)
