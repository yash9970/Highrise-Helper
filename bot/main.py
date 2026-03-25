import asyncio
import os
import sys
import traceback
sys.path.insert(0, os.path.dirname(__file__))

from highrise.__main__ import main, BotDefinition
from bot import HigrhiseBot
from keep_alive import run_keep_alive

RECONNECT_DELAY = 15  # seconds between reconnect attempts


async def run_bot(token: str, room_id: str):
    attempt = 0
    while True:
        attempt += 1
        print(f"[MAIN] Starting bot (attempt #{attempt})...")
        try:
            bot = HigrhiseBot()
            definitions = [
                BotDefinition(
                    bot=bot,
                    room_id=room_id,
                    api_token=token,
                )
            ]
            await main(definitions)
            print("[MAIN] Bot session ended cleanly.")
        except KeyboardInterrupt:
            print("[MAIN] Stopped by user.")
            break
        except Exception as e:
            print(f"[MAIN] Bot crashed: {e}")
            traceback.print_exc()
        print(f"[MAIN] Reconnecting in {RECONNECT_DELAY}s... (attempt #{attempt + 1} will follow)")
        await asyncio.sleep(RECONNECT_DELAY)


if __name__ == "__main__":
    token = os.environ.get("HIGHRISE_TOKEN")
    room_id = os.environ.get("HIGHRISE_ROOM_ID")

    if not token:
        raise RuntimeError("HIGHRISE_TOKEN is not set!")
    if not room_id:
        raise RuntimeError("HIGHRISE_ROOM_ID is not set!")

    run_keep_alive()
    print(f"[MAIN] ZenBot starting for room: {room_id}")
    asyncio.run(run_bot(token, room_id))
