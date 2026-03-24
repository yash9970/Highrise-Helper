import asyncio
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from highrise.__main__ import main, BotDefinition
from bot import HigrhiseBot
from keep_alive import run_keep_alive

RECONNECT_DELAY = 10  # seconds to wait before reconnecting after a crash


async def run_bot(token: str, room_id: str):
    """Run the bot and auto-reconnect on any crash, forever."""
    attempt = 0
    while True:
        attempt += 1
        print(f"[MAIN] Starting bot (attempt #{attempt})...")
        try:
            definitions = [
                BotDefinition(
                    bot=HigrhiseBot(),
                    room_id=room_id,
                    api_token=token,
                )
            ]
            await main(definitions)
        except KeyboardInterrupt:
            print("[MAIN] Stopped by user.")
            break
        except Exception as e:
            print(f"[MAIN] Bot crashed with error: {e}")
            print(f"[MAIN] Reconnecting in {RECONNECT_DELAY} seconds...")
            await asyncio.sleep(RECONNECT_DELAY)


if __name__ == "__main__":
    token = os.environ.get("HIGHRISE_TOKEN")
    room_id = os.environ.get("HIGHRISE_ROOM_ID")

    if not token:
        raise RuntimeError("HIGHRISE_TOKEN environment variable is not set!")
    if not room_id:
        raise RuntimeError("HIGHRISE_ROOM_ID environment variable is not set!")

    # Start the keep-alive web server (for UptimeRobot pings)
    run_keep_alive()

    print(f"[MAIN] ZenBot starting for room: {room_id}")
    asyncio.run(run_bot(token, room_id))
