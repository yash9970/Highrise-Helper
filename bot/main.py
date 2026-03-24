import asyncio
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from highrise.__main__ import main, BotDefinition
from bot import HigrhiseBot
from keep_alive import run_keep_alive

if __name__ == "__main__":
    token = os.environ.get("HIGHRISE_TOKEN")
    room_id = os.environ.get("HIGHRISE_ROOM_ID")

    if not token:
        raise RuntimeError("HIGHRISE_TOKEN environment variable is not set!")
    if not room_id:
        raise RuntimeError("HIGHRISE_ROOM_ID environment variable is not set!")

    run_keep_alive()

    definitions = [
        BotDefinition(
            bot=HigrhiseBot(),
            room_id=room_id,
            api_token=token,
        )
    ]

    asyncio.run(main(definitions))
