import asyncio
import random
import json
import os
from pathlib import Path
from highrise import BaseBot, Highrise
from highrise.models import Position, SessionMetadata, User

MASTER_USERNAME = "Zen1thos"

DEFAULT_POS = Position(x=18.0, y=0.0, z=13.5, facing="FrontRight")

VIP_FLOOR_POS = Position(x=13.0, y=0.10000000149011612, z=5.0, facing="FrontRight")

GREETINGS = [
    "Hey there! Welcome! 👋",
    "Hello! Great to see you! 🌟",
    "Sup! Glad you're here! 😄",
    "Heyyy! Welcome to the room! 🎉",
    "Hi hi hi! Welcome in! ✨",
    "Yooo! What's up! 🙌",
    "Welcome welcome welcome! So happy you're here! 💫",
    "Ahh a new face! Hi there! 🤗",
]

RANDOM_HI = [
    "Heyyy! How's everyone doing?! 🌟",
    "Wassup people! The party is HERE! 🎉",
    "HEYYYY! I see you! 👀✨",
    "Hola amigos! 💃",
    "Oi oi oi! Glad to see ya! 🙌",
    "HI HI HI! 🎊 You rang?",
    "Salutations! *does a little spin* 🌀",
    "Oh hey there gorgeous! 💖",
    "Wazzuuup! 😎",
    "HELLO HELLO! *waves frantically* 👋👋",
]

SONGS = [
    {"title": "Blinding Lights", "artist": "The Weeknd"},
    {"title": "Shape of You", "artist": "Ed Sheeran"},
    {"title": "Stay", "artist": "The Kid LAROI & Justin Bieber"},
    {"title": "Levitating", "artist": "Dua Lipa"},
    {"title": "Peaches", "artist": "Justin Bieber"},
    {"title": "Good 4 U", "artist": "Olivia Rodrigo"},
    {"title": "Montero", "artist": "Lil Nas X"},
    {"title": "Save Your Tears", "artist": "The Weeknd"},
    {"title": "Watermelon Sugar", "artist": "Harry Styles"},
    {"title": "drivers license", "artist": "Olivia Rodrigo"},
    {"title": "MONTERO (Call Me By Your Name)", "artist": "Lil Nas X"},
    {"title": "Dynamite", "artist": "BTS"},
    {"title": "Butter", "artist": "BTS"},
    {"title": "Permission to Dance", "artist": "BTS"},
    {"title": "Heat Waves", "artist": "Glass Animals"},
]

VIP_FILE = Path("bot/vip_users.json")


def load_vip_users() -> dict:
    if VIP_FILE.exists():
        try:
            with open(VIP_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_vip_users(vip_data: dict):
    with open(VIP_FILE, "w") as f:
        json.dump(vip_data, f, indent=2)


class HigrhiseBot(BaseBot):
    def __init__(self):
        self.current_song_index = 0
        self.vip_users: dict = load_vip_users()
        self.user_positions: dict = {}
        self.my_position = DEFAULT_POS

    async def on_start(self, session_metadata: SessionMetadata) -> None:
        print(f"[BOT] Started! Bot ID: {session_metadata.user_id}")
        await asyncio.sleep(1)
        await self.highrise.walk_to(DEFAULT_POS)
        await self.highrise.chat("🤖 ZenBot is online and ready! Type !help for commands.")

    async def on_user_join(self, user: User, position: Position) -> None:
        await asyncio.sleep(0.5)

        if user.username.lower() == MASTER_USERNAME.lower():
            await self.highrise.send_emote("emote-bow", user.id)
            await asyncio.sleep(0.5)
            await self.highrise.chat(f"Welcome back, Master {user.username}! 🫡 Your humble servant is at your service!")
        else:
            greeting = random.choice(GREETINGS)
            await self.highrise.chat(f"@{user.username} {greeting}")

        if user.username.lower() in [u.lower() for u in self.vip_users.keys()]:
            await asyncio.sleep(0.5)
            await self.highrise.chat(f"✨ Welcome back, VIP {user.username}! The VIP lounge is ready for you!")

    async def on_user_leave(self, user: User) -> None:
        if user.username.lower() == MASTER_USERNAME.lower():
            await self.highrise.chat(f"Master {user.username} has left. I'll guard the room until you return! 🫡")
        else:
            await self.highrise.chat(f"Bye bye @{user.username}! Come back soon! 👋")

    async def on_chat(self, user: User, message: str) -> None:
        msg = message.strip()
        msg_lower = msg.lower()

        if msg_lower == "!hi":
            greeting = random.choice(RANDOM_HI)
            await self.highrise.chat(greeting)

        elif msg_lower == "!pos":
            if user.username.lower() == MASTER_USERNAME.lower():
                resp = await self.highrise.get_room_users()
                if hasattr(resp, 'content'):
                    for room_user, pos in resp.content:
                        if room_user.username.lower() == MASTER_USERNAME.lower():
                            await self.highrise.chat(
                                f"Master, you are at: x={pos.x:.1f}, y={pos.y:.2f}, z={pos.z:.1f} 📍"
                            )
                            return
                await self.highrise.chat(f"Master, I couldn't pinpoint your location right now!")
            else:
                await self.highrise.chat(f"@{user.username} That command is reserved for Master only! 🚫")

        elif msg_lower.startswith("!emote "):
            emote_name = msg[7:].strip()
            emote_id = f"emote-{emote_name}"
            try:
                await self.highrise.send_emote(emote_id, user.id)
            except Exception:
                await self.highrise.chat(f"@{user.username} Hmm, I don't know that emote! Try something like: !emote wave")

        elif msg_lower == "!tele":
            if user.username.lower() == MASTER_USERNAME.lower():
                resp = await self.highrise.get_room_users()
                if hasattr(resp, 'content'):
                    for room_user, pos in resp.content:
                        if room_user.username.lower() == MASTER_USERNAME.lower():
                            await self.highrise.walk_to(pos)
                            self.my_position = pos
                            await self.highrise.chat(f"Teleporting to your side, Master! 🚀")
                            return
                await self.highrise.chat(f"Master, I couldn't find your location!")
            else:
                await self.highrise.chat(f"@{user.username} That command is reserved for Master only! 🚫")

        elif msg_lower == "!help":
            help_text = (
                "📋 ZenBot Commands:\n"
                "!hi — Random greeting from me!\n"
                "!emote <name> — I'll do an emote (e.g. !emote wave)\n"
                "!help — Shows this list\n"
                "!song — Current song playing\n"
                "!nextsong — Skip to next song\n"
                "!vip — VIP teleport to main floor\n"
                "!f0 — VIP: Teleport to ground floor\n"
                "[Master only]: !pos, !tele, !addvip, !removevip"
            )
            await self.highrise.chat(help_text)

        elif msg_lower == "!song":
            song = SONGS[self.current_song_index % len(SONGS)]
            await self.highrise.chat(f"🎵 Now Playing: {song['title']} by {song['artist']}")

        elif msg_lower == "!nextsong":
            self.current_song_index = (self.current_song_index + 1) % len(SONGS)
            song = SONGS[self.current_song_index]
            await self.highrise.chat(f"⏭️ Next up: {song['title']} by {song['artist']}")

        elif msg_lower == "!playlist":
            lines = ["🎶 Song Playlist:"]
            for i, s in enumerate(SONGS[:10]):
                marker = "▶️" if i == self.current_song_index % len(SONGS) else f"{i+1}."
                lines.append(f"{marker} {s['title']} - {s['artist']}")
            await self.highrise.chat("\n".join(lines))

        elif msg_lower == "!vip":
            is_vip = user.username.lower() in [u.lower() for u in self.vip_users.keys()]
            if is_vip:
                await self.highrise.teleport(user.id, VIP_FLOOR_POS)
                await self.highrise.chat(f"✨ VIP Access granted, @{user.username}! Welcome to the VIP floor!")
            else:
                await self.highrise.chat(f"@{user.username} You are not a VIP! Ask Master Zen1thos to grant you VIP access! 💎")

        elif msg_lower == "!f0":
            is_vip = user.username.lower() in [u.lower() for u in self.vip_users.keys()]
            is_master = user.username.lower() == MASTER_USERNAME.lower()
            if is_vip or is_master:
                await self.highrise.teleport(user.id, VIP_FLOOR_POS)
                await self.highrise.chat(f"🚀 Teleporting @{user.username} to the ground floor!")
            else:
                await self.highrise.chat(f"@{user.username} VIP only command! 🚫")

        elif msg_lower.startswith("!addvip "):
            if user.username.lower() == MASTER_USERNAME.lower():
                target = msg[8:].strip().lstrip("@")
                self.vip_users[target] = True
                save_vip_users(self.vip_users)
                await self.highrise.chat(f"✨ @{target} has been granted VIP status! Welcome to the club!")
            else:
                await self.highrise.chat(f"@{user.username} Only Master can manage VIPs! 🚫")

        elif msg_lower.startswith("!removevip "):
            if user.username.lower() == MASTER_USERNAME.lower():
                target = msg[11:].strip().lstrip("@")
                removed = False
                for key in list(self.vip_users.keys()):
                    if key.lower() == target.lower():
                        del self.vip_users[key]
                        removed = True
                        break
                save_vip_users(self.vip_users)
                if removed:
                    await self.highrise.chat(f"@{target} VIP status has been removed.")
                else:
                    await self.highrise.chat(f"@{target} was not in the VIP list.")
            else:
                await self.highrise.chat(f"@{user.username} Only Master can manage VIPs! 🚫")

        elif msg_lower == "!viplist":
            if user.username.lower() == MASTER_USERNAME.lower():
                if self.vip_users:
                    vip_names = ", ".join(self.vip_users.keys())
                    await self.highrise.chat(f"💎 VIP Members: {vip_names}")
                else:
                    await self.highrise.chat("No VIP members yet! Use !addvip <username> to add one.")
            else:
                await self.highrise.chat(f"@{user.username} Only Master can view VIP list! 🚫")

        elif msg_lower == "!home":
            if user.username.lower() == MASTER_USERNAME.lower():
                await self.highrise.walk_to(DEFAULT_POS)
                self.my_position = DEFAULT_POS
                await self.highrise.chat("Returning to my post! 🏠")
            else:
                await self.highrise.chat(f"@{user.username} Only Master can move me! 🚫")

        elif msg_lower == "!dance":
            dance_emotes = ["emote-dance", "emote-dab", "emote-tpose", "emote-curtsy", "emote-breakdance"]
            emote = random.choice(dance_emotes)
            await self.highrise.send_emote(emote)
            await self.highrise.chat("🕺 Let's dance!")

        elif msg_lower == "!8ball " or msg_lower.startswith("!8ball "):
            answers = [
                "Absolutely! 🎱", "No way! 🎱", "Most likely yes! 🎱",
                "I doubt it... 🎱", "The stars say YES! 🎱", "Hmm, ask again later 🎱",
                "Definitely! 🎱", "Signs point to no 🎱", "Without a doubt! 🎱",
                "Very doubtful... 🎱"
            ]
            await self.highrise.chat(random.choice(answers))

        elif msg_lower == "!flip":
            result = random.choice(["Heads! 🪙", "Tails! 🪙"])
            await self.highrise.chat(f"@{user.username} flipped a coin: {result}")

        elif msg_lower == "!joke":
            jokes = [
                "Why don't scientists trust atoms? Because they make up everything! 😂",
                "I told my wife she was drawing her eyebrows too high. She looked surprised. 😂",
                "What do you call a fake noodle? An impasta! 😂",
                "Why did the scarecrow win an award? He was outstanding in his field! 😂",
                "I'm reading a book about anti-gravity. It's impossible to put down! 😂",
            ]
            await self.highrise.chat(random.choice(jokes))
