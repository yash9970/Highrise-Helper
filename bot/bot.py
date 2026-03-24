import asyncio
import random
import json
import os
from datetime import datetime
from pathlib import Path
from highrise import BaseBot, Highrise
from highrise.models import Position, SessionMetadata, User

MASTER_USERNAME = "Zen1thos"

DEFAULT_POS = Position(x=18.0, y=0.0, z=13.5, facing="FrontRight")
VIP_FLOOR_POS = Position(x=4.0, y=12.25, z=4.5, facing="FrontRight")
GROUND_FLOOR_POS = Position(x=13.0, y=0.10000000149011612, z=5.0, facing="FrontRight")

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
    {"title": "Dynamite", "artist": "BTS"},
    {"title": "Butter", "artist": "BTS"},
    {"title": "Permission to Dance", "artist": "BTS"},
    {"title": "Heat Waves", "artist": "Glass Animals"},
]

VIP_FILE = Path("bot/vip_users.json")


def load_vip_data() -> dict:
    """Load full VIP data: {username: {added_by, added_at, history: [...]}}"""
    if VIP_FILE.exists():
        try:
            with open(VIP_FILE, "r") as f:
                data = json.load(f)
            # Migrate old flat format {username: True} to new format
            migrated = {}
            for k, v in data.items():
                if isinstance(v, dict):
                    migrated[k] = v
                else:
                    migrated[k] = {
                        "added_by": "Unknown",
                        "added_at": "Unknown",
                        "history": [{"action": "added", "by": "Unknown", "at": "Unknown"}],
                    }
            return migrated
        except Exception:
            pass
    return {}


def save_vip_data(vip_data: dict):
    try:
        with open(VIP_FILE, "w") as f:
            json.dump(vip_data, f, indent=2)
    except Exception as e:
        print(f"[BOT] Warning: could not save VIP list: {e}")


def now_str() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")


def is_master(user: User) -> bool:
    return user.username.lower() == MASTER_USERNAME.lower()


def is_vip(username: str, vip_data: dict) -> bool:
    return username.lower() in [u.lower() for u in vip_data.keys()]


class HigrhiseBot(BaseBot):
    def __init__(self):
        self.current_song_index = 0
        self.vip_data: dict = load_vip_data()
        self.my_position = DEFAULT_POS

    # ─── Safe helpers ───────────────────────────────────────────────────────────

    async def safe_chat(self, message: str):
        """Send a chat message, silently ignore failures."""
        try:
            await self.highrise.chat(message)
        except Exception as e:
            print(f"[BOT] chat error: {e}")

    async def safe_emote(self, emote_id: str, target_id: str | None = None):
        """Send an emote, silently ignore failures."""
        try:
            await self.highrise.send_emote(emote_id, target_id)
        except Exception as e:
            print(f"[BOT] emote error: {e}")

    async def safe_walk_to(self, pos: Position, retries: int = 5, delay: float = 3.0):
        """Walk to a position with retries. Never crashes the bot."""
        for attempt in range(retries):
            try:
                await self.highrise.walk_to(pos)
                self.my_position = pos
                return
            except Exception as e:
                print(f"[BOT] walk_to attempt {attempt + 1}/{retries} failed: {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(delay)
        print("[BOT] walk_to gave up after all retries.")

    async def safe_teleport(self, user_id: str, pos: Position):
        """Teleport a user, silently ignore failures."""
        try:
            await self.highrise.teleport(user_id, pos)
        except Exception as e:
            print(f"[BOT] teleport error: {e}")

    # ─── Lifecycle events ────────────────────────────────────────────────────────

    async def on_start(self, session_metadata: SessionMetadata) -> None:
        print(f"[BOT] Connected! Bot ID: {session_metadata.user_id}")
        # Wait 8 seconds — Highrise needs time to fully load the bot into the room
        # before any position or chat commands will work. Do NOT reduce this.
        await asyncio.sleep(8)
        await self.safe_walk_to(DEFAULT_POS, retries=5, delay=5.0)
        await self.safe_chat("🤖 ZenBot is online! Type !help for commands.")

    async def on_user_join(self, user: User, position: Position) -> None:
        try:
            await asyncio.sleep(0.5)
            if is_master(user):
                await self.safe_emote("emote-bow", user.id)
                await asyncio.sleep(0.5)
                await self.safe_chat(
                    f"Welcome back, Master {user.username}! 🫡 Your humble servant is at your service!"
                )
            else:
                greeting = random.choice(GREETINGS)
                await self.safe_chat(f"@{user.username} {greeting}")

            if is_vip(user.username, self.vip_data) and not is_master(user):
                await asyncio.sleep(0.5)
                await self.safe_chat(
                    f"✨ Welcome back, VIP @{user.username}! The VIP lounge is ready for you!"
                )
        except Exception as e:
            print(f"[BOT] on_user_join error: {e}")

    async def on_user_leave(self, user: User) -> None:
        try:
            if is_master(user):
                await self.safe_chat(
                    f"Master {user.username} has left. I'll guard the room until you return! 🫡"
                )
            else:
                await self.safe_chat(f"Bye bye @{user.username}! Come back soon! 👋")
        except Exception as e:
            print(f"[BOT] on_user_leave error: {e}")

    async def on_chat(self, user: User, message: str) -> None:
        try:
            await self._handle_command(user, message.strip())
        except Exception as e:
            print(f"[BOT] on_chat error for '{message}': {e}")

    # ─── Command handler ─────────────────────────────────────────────────────────

    async def _handle_command(self, user: User, msg: str):
        msg_lower = msg.lower()

        if msg_lower == "!hi":
            await self.safe_chat(random.choice(RANDOM_HI))

        elif msg_lower == "!pos":
            if is_master(user):
                try:
                    resp = await self.highrise.get_room_users()
                    if hasattr(resp, "content"):
                        for room_user, pos in resp.content:
                            if room_user.username.lower() == MASTER_USERNAME.lower():
                                await self.safe_chat(
                                    f"Master, you are at: x={pos.x:.1f}, y={pos.y:.2f}, z={pos.z:.1f} 📍"
                                )
                                return
                    await self.safe_chat("Master, I couldn't pinpoint your location right now!")
                except Exception as e:
                    print(f"[BOT] !pos error: {e}")
                    await self.safe_chat("Master, something went wrong fetching your position!")
            else:
                await self.safe_chat(f"@{user.username} That command is reserved for Master only! 🚫")

        elif msg_lower.startswith("!emote "):
            emote_name = msg[7:].strip()
            if emote_name:
                await self.safe_emote(f"emote-{emote_name}", user.id)
            else:
                await self.safe_chat(f"@{user.username} Usage: !emote wave")

        elif msg_lower == "!tele":
            if is_master(user):
                try:
                    resp = await self.highrise.get_room_users()
                    if hasattr(resp, "content"):
                        for room_user, pos in resp.content:
                            if room_user.username.lower() == MASTER_USERNAME.lower():
                                await self.safe_walk_to(pos)
                                await self.safe_chat("Teleporting to your side, Master! 🚀")
                                return
                    await self.safe_chat("Master, I couldn't find your location!")
                except Exception as e:
                    print(f"[BOT] !tele error: {e}")
                    await self.safe_chat("Master, something went wrong!")
            else:
                await self.safe_chat(f"@{user.username} That command is reserved for Master only! 🚫")

        elif msg_lower == "!home":
            if is_master(user):
                await self.safe_walk_to(DEFAULT_POS)
                await self.safe_chat("Returning to my post! 🏠")
            else:
                await self.safe_chat(f"@{user.username} Only Master can move me! 🚫")

        elif msg_lower == "!help":
            help_text = (
                "📋 ZenBot Commands:\n"
                "!hi — Random greeting\n"
                "!emote <name> — Bot does an emote\n"
                "!song / !nextsong / !playlist — Music\n"
                "!dance / !flip / !joke / !8ball — Fun\n"
                "@summon <name> — Teleport player to you\n"
                "!vip — VIP: go to VIP floor\n"
                "!f0 — VIP: go to ground floor\n"
                "[Master only]:\n"
                "!pos !tele !home\n"
                "!addvip !removevip !viplist\n"
                "!viphistory / !viphistory <name>"
            )
            await self.safe_chat(help_text)

        elif msg_lower == "!song":
            song = SONGS[self.current_song_index % len(SONGS)]
            await self.safe_chat(f"🎵 Now Playing: {song['title']} by {song['artist']}")

        elif msg_lower == "!nextsong":
            self.current_song_index = (self.current_song_index + 1) % len(SONGS)
            song = SONGS[self.current_song_index]
            await self.safe_chat(f"⏭️ Next up: {song['title']} by {song['artist']}")

        elif msg_lower == "!playlist":
            lines = ["🎶 Playlist:"]
            for i, s in enumerate(SONGS[:10]):
                marker = "▶️" if i == self.current_song_index % len(SONGS) else f"{i+1}."
                lines.append(f"{marker} {s['title']} - {s['artist']}")
            await self.safe_chat("\n".join(lines))

        elif msg_lower == "!vip":
            if is_vip(user.username, self.vip_data) or is_master(user):
                await self.safe_teleport(user.id, VIP_FLOOR_POS)
                await self.safe_chat(f"✨ Welcome to the VIP floor, @{user.username}!")
            else:
                await self.safe_chat(
                    f"@{user.username} You're not a VIP! Ask Master {MASTER_USERNAME} to grant VIP access! 💎"
                )

        elif msg_lower == "!f0":
            if is_vip(user.username, self.vip_data) or is_master(user):
                await self.safe_teleport(user.id, GROUND_FLOOR_POS)
                await self.safe_chat(f"🚀 Teleporting @{user.username} to the ground floor!")
            else:
                await self.safe_chat(f"@{user.username} VIP only command! 🚫")

        elif msg_lower.startswith("!addvip "):
            if is_master(user):
                target = msg[8:].strip().lstrip("@")
                if target:
                    already = is_vip(target, self.vip_data)
                    entry = self.vip_data.get(target, {
                        "added_by": user.username,
                        "added_at": now_str(),
                        "history": [],
                    })
                    entry["history"].append({
                        "action": "added",
                        "by": user.username,
                        "at": now_str(),
                    })
                    entry["added_by"] = user.username
                    entry["added_at"] = now_str()
                    self.vip_data[target] = entry
                    save_vip_data(self.vip_data)
                    if already:
                        await self.safe_chat(f"@{target} is already a VIP — history updated!")
                    else:
                        await self.safe_chat(f"✨ @{target} has been granted VIP status by {user.username}!")
                else:
                    await self.safe_chat("Usage: !addvip <username>")
            else:
                await self.safe_chat(f"@{user.username} Only Master can manage VIPs! 🚫")

        elif msg_lower.startswith("!removevip "):
            if is_master(user):
                target = msg[11:].strip().lstrip("@")
                removed_key = None
                for key in list(self.vip_data.keys()):
                    if key.lower() == target.lower():
                        removed_key = key
                        break
                if removed_key:
                    self.vip_data[removed_key]["history"].append({
                        "action": "removed",
                        "by": user.username,
                        "at": now_str(),
                    })
                    save_vip_data(self.vip_data)
                    del self.vip_data[removed_key]
                    save_vip_data(self.vip_data)
                    await self.safe_chat(f"@{target} VIP status removed by {user.username}.")
                else:
                    await self.safe_chat(f"@{target} was not in the VIP list.")
            else:
                await self.safe_chat(f"@{user.username} Only Master can manage VIPs! 🚫")

        elif msg_lower == "!viplist":
            if is_master(user):
                if self.vip_data:
                    names = ", ".join(self.vip_data.keys())
                    await self.safe_chat(f"💎 VIPs ({len(self.vip_data)}): {names}")
                else:
                    await self.safe_chat("No VIP members yet! Use !addvip <username>")
            else:
                await self.safe_chat(f"@{user.username} Only Master can view VIP list! 🚫")

        elif msg_lower.startswith("!viphistory"):
            if is_master(user):
                parts = msg.split(None, 1)
                if len(parts) == 2:
                    target = parts[1].strip().lstrip("@")
                    entry = next(
                        (v for k, v in self.vip_data.items() if k.lower() == target.lower()),
                        None,
                    )
                    if entry:
                        lines = [f"📋 VIP history for @{target}:"]
                        for h in entry.get("history", [])[-5:]:
                            lines.append(f"  {h['action'].upper()} by {h['by']} at {h['at']}")
                        await self.safe_chat("\n".join(lines))
                    else:
                        await self.safe_chat(f"@{target} has no VIP history.")
                else:
                    if self.vip_data:
                        lines = [f"📋 All VIPs ({len(self.vip_data)}):"]
                        for name, entry in list(self.vip_data.items())[:8]:
                            lines.append(f"  {name} — added by {entry.get('added_by','?')} on {entry.get('added_at','?')}")
                        await self.safe_chat("\n".join(lines))
                    else:
                        await self.safe_chat("No VIP history yet.")
            else:
                await self.safe_chat(f"@{user.username} Only Master can view VIP history! 🚫")

        elif msg_lower.startswith("@summon "):
            target_name = msg[8:].strip().lstrip("@")
            if not target_name:
                await self.safe_chat(f"@{user.username} Usage: @summon <playerName>")
            else:
                try:
                    resp = await self.highrise.get_room_users()
                    if hasattr(resp, "content"):
                        sender_pos = None
                        target_user = None

                        for room_user, pos in resp.content:
                            if room_user.username.lower() == user.username.lower():
                                sender_pos = pos
                            if room_user.username.lower() == target_name.lower():
                                target_user = room_user

                        if not target_user:
                            await self.safe_chat(
                                f"@{user.username} Could not find '{target_name}' in the room!"
                            )
                        elif not sender_pos:
                            await self.safe_chat(
                                f"@{user.username} Could not find your location!"
                            )
                        else:
                            await self.safe_teleport(target_user.id, sender_pos)
                            await self.safe_chat(
                                f"🌀 @{target_user.username} has been summoned to @{user.username}!"
                            )
                    else:
                        await self.safe_chat(f"@{user.username} Could not fetch room users right now.")
                except Exception as e:
                    print(f"[BOT] @summon error: {e}")
                    await self.safe_chat(f"@{user.username} Something went wrong with the summon!")

        elif msg_lower == "!dance":
            dance_emotes = ["emote-dance", "emote-dab", "emote-tpose", "emote-curtsy", "emote-breakdance"]
            await self.safe_emote(random.choice(dance_emotes))
            await self.safe_chat("🕺 Let's dance!")

        elif msg_lower.startswith("!8ball"):
            answers = [
                "Absolutely! 🎱", "No way! 🎱", "Most likely yes! 🎱",
                "I doubt it... 🎱", "The stars say YES! 🎱", "Hmm, ask again later 🎱",
                "Definitely! 🎱", "Signs point to no 🎱", "Without a doubt! 🎱",
                "Very doubtful... 🎱",
            ]
            await self.safe_chat(random.choice(answers))

        elif msg_lower == "!flip":
            result = random.choice(["Heads! 🪙", "Tails! 🪙"])
            await self.safe_chat(f"@{user.username} flipped a coin: {result}")

        elif msg_lower == "!joke":
            jokes = [
                "Why don't scientists trust atoms? Because they make up everything! 😂",
                "I told my wife she was drawing her eyebrows too high. She looked surprised. 😂",
                "What do you call a fake noodle? An impasta! 😂",
                "Why did the scarecrow win an award? He was outstanding in his field! 😂",
                "I'm reading a book about anti-gravity. It's impossible to put down! 😂",
            ]
            await self.safe_chat(random.choice(jokes))
