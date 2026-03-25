import asyncio
import random
import traceback
from highrise import BaseBot
from highrise.models import Position, SessionMetadata, User, CurrencyItem, Item

from store import (
    load_data, save_data, is_vip, add_vip, remove_vip,
    set_wrap, get_wrap, delete_wrap,
    current_song, next_song, add_song, remove_song,
    now_str,
)

MASTER_USERNAME = "Zen1thos"
TIP_VIP_THRESHOLD = 500       # gold bars needed for auto-VIP
SONG_ANNOUNCE_INTERVAL = 300  # seconds between auto song announcements (5 min)

DEFAULT_POS  = Position(x=18.0, y=0.0,  z=13.5, facing="FrontRight")
VIP_FLOOR    = Position(x=4.0,  y=12.25, z=4.5,  facing="FrontRight")
GROUND_FLOOR = Position(x=13.0, y=0.10,  z=5.0,  facing="FrontRight")

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
    "HI HI HI! 🎊",
    "Salutations! *does a little spin* 🌀",
    "Oh hey there gorgeous! 💖",
    "Wazzuuup! 😎",
    "HELLO HELLO! *waves frantically* 👋👋",
]


def is_master(user: User) -> bool:
    return user.username.lower() == MASTER_USERNAME.lower()


class HigrhiseBot(BaseBot):
    def __init__(self):
        self.data = load_data()
        self._song_task: asyncio.Task | None = None
        print(f"[BOT] Loaded: {len(self.data['vips'])} VIPs, "
              f"{len(self.data['wraps'])} wraps, {len(self.data['songs'])} songs.")

    # ─── Safe helpers ────────────────────────────────────────────────────────

    async def safe_chat(self, msg: str):
        try:
            await self.highrise.chat(msg)
        except Exception as e:
            print(f"[BOT] chat error: {e}")

    async def safe_emote(self, emote_id: str, target_id: str | None = None):
        try:
            await self.highrise.send_emote(emote_id, target_id)
        except Exception as e:
            print(f"[BOT] emote error: {e}")

    async def safe_walk_to(self, pos: Position, retries: int = 5, delay: float = 5.0):
        for attempt in range(retries):
            try:
                await self.highrise.walk_to(pos)
                return
            except Exception as e:
                print(f"[BOT] walk_to attempt {attempt+1}/{retries}: {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(delay)

    async def safe_teleport(self, user_id: str, pos: Position):
        try:
            await self.highrise.teleport(user_id, pos)
        except Exception as e:
            print(f"[BOT] teleport error: {e}")

    async def _get_user_pos(self, username: str) -> Position | None:
        """Return the current Position of a user in the room, or None."""
        try:
            resp = await self.highrise.get_room_users()
            if hasattr(resp, "content"):
                for room_user, pos in resp.content:
                    if room_user.username.lower() == username.lower():
                        return pos
        except Exception as e:
            print(f"[BOT] get_user_pos error: {e}")
        return None

    # ─── Song announcement loop ───────────────────────────────────────────────

    async def _song_loop(self):
        await asyncio.sleep(SONG_ANNOUNCE_INTERVAL)
        while True:
            try:
                song = current_song(self.data)
                msg = f"🎵 Now Playing: {song['title']} by {song['artist']}"
                if song.get("url"):
                    msg += f"\n🔗 {song['url']}"
                await self.safe_chat(msg)
                next_song(self.data)
                await asyncio.sleep(SONG_ANNOUNCE_INTERVAL)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[BOT] song loop error: {e}")
                await asyncio.sleep(30)

    # ─── Lifecycle ────────────────────────────────────────────────────────────

    async def on_start(self, session_metadata: SessionMetadata) -> None:
        print(f"[BOT] Connected! Session: {session_metadata.user_id}")
        if self._song_task and not self._song_task.done():
            self._song_task.cancel()
        self._song_task = asyncio.create_task(self._song_loop())
        await asyncio.sleep(8)
        await self.safe_walk_to(DEFAULT_POS, retries=5, delay=5.0)
        await self.safe_chat("🤖 ZenBot is online! Type !help for commands.")

    async def on_user_join(self, user: User, position: Position) -> None:
        try:
            await asyncio.sleep(0.5)
            if is_master(user):
                await self.safe_emote("emote-bow", user.id)
                await asyncio.sleep(0.5)
                await self.safe_chat(f"Welcome back, Master {user.username}! 🫡 Your humble servant awaits!")
            else:
                await self.safe_chat(f"@{user.username} {random.choice(GREETINGS)}")
                if is_vip(user.username, self.data):
                    await asyncio.sleep(0.5)
                    await self.safe_chat(f"✨ Welcome back, VIP @{user.username}! The VIP lounge is yours!")
        except Exception as e:
            print(f"[BOT] on_user_join error: {e}")

    async def on_user_leave(self, user: User) -> None:
        try:
            if is_master(user):
                await self.safe_chat(f"Master {user.username} has left. I'll guard the room! 🫡")
            else:
                await self.safe_chat(f"Bye bye @{user.username}! Come back soon! 👋")
        except Exception as e:
            print(f"[BOT] on_user_leave error: {e}")

    async def on_tip(self, sender: User, receiver: User, tip: CurrencyItem | Item) -> None:
        try:
            amount = 0
            if isinstance(tip, CurrencyItem):
                amount = tip.amount
            elif hasattr(tip, "amount"):
                amount = tip.amount

            print(f"[BOT] Tip: {sender.username} tipped {amount} gold.")

            if amount >= TIP_VIP_THRESHOLD and not is_vip(sender.username, self.data) and not is_master(sender):
                already = add_vip(sender.username, "AutoVIP (tip)", self.data)
                await save_data(self.data)
                if not already:
                    await self.safe_chat(
                        f"💰 WOW! @{sender.username} tipped {amount} gold and earned VIP status! "
                        f"Welcome to the VIP club! 👑✨"
                    )
            elif amount > 0:
                await self.safe_chat(f"💖 Thank you for the {amount} gold, @{sender.username}! You're amazing!")
        except Exception as e:
            print(f"[BOT] on_tip error: {e}")
            traceback.print_exc()

    async def on_chat(self, user: User, message: str) -> None:
        try:
            await self._handle_command(user, message.strip())
        except Exception as e:
            print(f"[BOT] on_chat error for '{message}': {e}")
            traceback.print_exc()

    # ─── Command dispatcher ───────────────────────────────────────────────────

    async def _handle_command(self, user: User, msg: str):
        ml = msg.lower().lstrip("/")  # accept both ! and / prefix

        # ── !help ──────────────────────────────────────────────────────────

        if ml in ("!help", "help"):
            await self.safe_chat(
                "📋 ZenBot Commands:\n"
                "!hi  !joke  !flip  !dance\n"
                "!8ball <q>  !emote <name>\n"
                "!song  !nextsong  !playlist\n"
                "@summon <name> — teleport to you\n"
                "!vip — VIP floor  |  !f0 — ground\n"
                "!<wrap> — any saved teleport spot\n"
                "[Master]: !setbot !setwrap !deletewrap\n"
                "!wraplist !addvip !removevip !viplist\n"
                "!addsong !removesong !viphistory"
            )

        # ── !hi ────────────────────────────────────────────────────────────

        elif msg.lower() == "!hi":
            await self.safe_chat(random.choice(RANDOM_HI))

        # ── Fun commands ───────────────────────────────────────────────────

        elif msg.lower() == "!dance":
            await self.safe_emote(random.choice(["emote-dance", "emote-dab", "emote-breakdance", "emote-curtsy"]))
            await self.safe_chat("🕺 Let's go!")

        elif msg.lower() == "!flip":
            await self.safe_chat(f"@{user.username} flipped: {random.choice(['Heads! 🪙', 'Tails! 🪙'])}")

        elif msg.lower() == "!joke":
            jokes = [
                "Why don't scientists trust atoms? They make up everything! 😂",
                "I told my wife she was drawing her eyebrows too high. She looked surprised. 😂",
                "What do you call a fake noodle? An impasta! 😂",
                "Why did the scarecrow win an award? Outstanding in his field! 😂",
                "I'm reading a book about anti-gravity. Impossible to put down! 😂",
            ]
            await self.safe_chat(random.choice(jokes))

        elif msg.lower().startswith("!8ball"):
            answers = ["Absolutely! 🎱","No way! 🎱","Most likely yes! 🎱","I doubt it 🎱",
                       "The stars say YES! 🎱","Ask again later 🎱","Definitely! 🎱","Signs point to no 🎱"]
            await self.safe_chat(random.choice(answers))

        elif msg.lower().startswith("!emote "):
            emote_name = msg[7:].strip()
            if emote_name:
                await self.safe_emote(f"emote-{emote_name}", user.id)

        # ── Music commands ─────────────────────────────────────────────────

        elif msg.lower() == "!song":
            song = current_song(self.data)
            reply = f"🎵 Now Playing: {song['title']} by {song['artist']}"
            if song.get("url"):
                reply += f"\n🔗 {song['url']}"
            await self.safe_chat(reply)

        elif msg.lower() == "!nextsong":
            song = next_song(self.data)
            await save_data(self.data)
            reply = f"⏭️ Next: {song['title']} by {song['artist']}"
            if song.get("url"):
                reply += f"\n🔗 {song['url']}"
            await self.safe_chat(reply)

        elif msg.lower() == "!playlist":
            songs = self.data["songs"]
            if not songs:
                await self.safe_chat("Playlist is empty! Master can add songs with !addsong")
                return
            idx = self.data["song_index"] % len(songs)
            lines = ["🎶 Playlist:"]
            for i, s in enumerate(songs[:10]):
                marker = "▶️" if i == idx else f"{i+1}."
                lines.append(f"{marker} {s['title']} — {s['artist']}")
            await self.safe_chat("\n".join(lines))

        # ── @summon (everyone) ─────────────────────────────────────────────

        elif msg.lower().startswith("@summon "):
            target_name = msg[8:].strip().lstrip("@")
            if not target_name:
                await self.safe_chat(f"@{user.username} Usage: @summon <playerName>")
                return
            try:
                resp = await self.highrise.get_room_users()
                if hasattr(resp, "content"):
                    sender_pos = target_user = None
                    for ru, pos in resp.content:
                        if ru.username.lower() == user.username.lower():
                            sender_pos = pos
                        if ru.username.lower() == target_name.lower():
                            target_user = ru
                    if not target_user:
                        await self.safe_chat(f"@{user.username} '{target_name}' is not in the room!")
                    elif not sender_pos:
                        await self.safe_chat(f"@{user.username} Could not find your location!")
                    else:
                        await self.safe_teleport(target_user.id, sender_pos)
                        await self.safe_chat(f"🌀 @{target_user.username} summoned to @{user.username}!")
            except Exception as e:
                print(f"[BOT] @summon error: {e}")

        # ── VIP teleport commands (VIP + master) ───────────────────────────

        elif msg.lower() == "!vip":
            if is_vip(user.username, self.data) or is_master(user):
                await self.safe_teleport(user.id, VIP_FLOOR)
                await self.safe_chat(f"✨ Welcome to the VIP floor, @{user.username}!")
            else:
                await self.safe_chat(f"@{user.username} VIPs only! Ask Master {MASTER_USERNAME} for access 💎")

        elif msg.lower() == "!f0":
            if is_vip(user.username, self.data) or is_master(user):
                await self.safe_teleport(user.id, GROUND_FLOOR)
                await self.safe_chat(f"🚀 Ground floor, @{user.username}!")
            else:
                await self.safe_chat(f"@{user.username} VIP only! 🚫")

        # ── Master-only: bot movement ──────────────────────────────────────

        elif msg.lower() == "!setbot":
            if not is_master(user):
                await self.safe_chat(f"@{user.username} Master only! 🚫")
                return
            pos = await self._get_user_pos(MASTER_USERNAME)
            if pos:
                await self.safe_walk_to(pos)
                await self.safe_chat(f"✅ Moved to your position, Master!")
            else:
                await self.safe_chat("Couldn't find your position right now!")

        elif msg.lower() == "!home":
            if not is_master(user):
                await self.safe_chat(f"@{user.username} Master only! 🚫")
                return
            await self.safe_walk_to(DEFAULT_POS)
            await self.safe_chat("Returning to my post! 🏠")

        elif msg.lower() == "!tele":
            if not is_master(user):
                await self.safe_chat(f"@{user.username} Master only! 🚫")
                return
            pos = await self._get_user_pos(MASTER_USERNAME)
            if pos:
                await self.safe_walk_to(pos)
                await self.safe_chat("Coming to you, Master! 🚀")
            else:
                await self.safe_chat("Couldn't find your location!")

        elif msg.lower() == "!pos":
            if not is_master(user):
                await self.safe_chat(f"@{user.username} Master only! 🚫")
                return
            pos = await self._get_user_pos(MASTER_USERNAME)
            if pos:
                await self.safe_chat(f"📍 Your position: x={pos.x:.1f}, y={pos.y:.2f}, z={pos.z:.1f}")
            else:
                await self.safe_chat("Couldn't find your location!")

        # ── Master-only: setwrap ───────────────────────────────────────────

        elif msg.lower().startswith("!setwrap ") or msg.lower().startswith("/setwrap "):
            if not is_master(user):
                await self.safe_chat(f"@{user.username} Master only! 🚫")
                return
            keyword = msg.split(None, 1)[1].strip().lower()
            if not keyword:
                await self.safe_chat("Usage: !setwrap <keyword>  (stand where you want users to teleport)")
                return
            pos = await self._get_user_pos(MASTER_USERNAME)
            if not pos:
                await self.safe_chat("Couldn't find your position! Are you in the room?")
                return
            set_wrap(keyword, pos.x, pos.y, pos.z, pos.facing, user.username, self.data)
            await save_data(self.data)
            await self.safe_chat(f"✅ Wrap '!{keyword}' saved! Users can now type !{keyword} to teleport here.")

        elif msg.lower() in ("!wraplist", "/wraplist"):
            if not is_master(user):
                await self.safe_chat(f"@{user.username} Master only! 🚫")
                return
            wraps = self.data["wraps"]
            if not wraps:
                await self.safe_chat("No wraps set yet. Use !setwrap <keyword>")
            else:
                lines = [f"📍 Saved wraps ({len(wraps)}):"]
                for kw, w in wraps.items():
                    lines.append(f"  !{kw} — set by {w['set_by']}")
                await self.safe_chat("\n".join(lines))

        elif msg.lower().startswith("!deletewrap ") or msg.lower().startswith("/deletewrap "):
            if not is_master(user):
                await self.safe_chat(f"@{user.username} Master only! 🚫")
                return
            keyword = msg.split(None, 1)[1].strip().lower()
            if delete_wrap(keyword, self.data):
                await save_data(self.data)
                await self.safe_chat(f"✅ Wrap '!{keyword}' deleted.")
            else:
                await self.safe_chat(f"No wrap named '!{keyword}' found.")

        # ── Master-only: VIP management ────────────────────────────────────

        elif msg.lower().startswith("!addvip "):
            if not is_master(user):
                await self.safe_chat(f"@{user.username} Master only! 🚫")
                return
            target = msg[8:].strip().lstrip("@")
            if target:
                already = add_vip(target, user.username, self.data)
                await save_data(self.data)
                if already:
                    await self.safe_chat(f"@{target} was already VIP — history updated.")
                else:
                    await self.safe_chat(f"✨ @{target} granted VIP status by {user.username}! 👑")
            else:
                await self.safe_chat("Usage: !addvip <username>")

        elif msg.lower().startswith("!removevip "):
            if not is_master(user):
                await self.safe_chat(f"@{user.username} Master only! 🚫")
                return
            target = msg[11:].strip().lstrip("@")
            found = remove_vip(target, user.username, self.data)
            await save_data(self.data)
            await self.safe_chat(f"@{target} VIP removed." if found else f"@{target} is not a VIP.")

        elif msg.lower() == "!viplist":
            if not is_master(user):
                await self.safe_chat(f"@{user.username} Master only! 🚫")
                return
            vips = self.data["vips"]
            if vips:
                await self.safe_chat(f"💎 VIPs ({len(vips)}): {', '.join(vips.keys())}")
            else:
                await self.safe_chat("No VIP members yet.")

        elif msg.lower().startswith("!viphistory"):
            if not is_master(user):
                await self.safe_chat(f"@{user.username} Master only! 🚫")
                return
            parts = msg.split(None, 1)
            if len(parts) == 2:
                target = parts[1].strip().lstrip("@")
                entry = next((v for k, v in self.data["vips"].items() if k.lower() == target.lower()), None)
                if entry:
                    lines = [f"📋 History for @{target}:"]
                    for h in entry.get("history", [])[-5:]:
                        lines.append(f"  {h['action'].upper()} by {h['by']} at {h['at']}")
                    await self.safe_chat("\n".join(lines))
                else:
                    await self.safe_chat(f"@{target} has no VIP history.")
            else:
                vips = self.data["vips"]
                if vips:
                    lines = [f"📋 All VIPs ({len(vips)}):"]
                    for name, e in list(vips.items())[:8]:
                        lines.append(f"  {name} — added by {e.get('added_by','?')} on {e.get('added_at','?')}")
                    await self.safe_chat("\n".join(lines))
                else:
                    await self.safe_chat("No VIP history yet.")

        # ── Master-only: song management ───────────────────────────────────

        elif msg.lower().startswith("!addsong "):
            if not is_master(user):
                await self.safe_chat(f"@{user.username} Master only! 🚫")
                return
            raw = msg[9:].strip()
            parts = [p.strip() for p in raw.split("|")]
            if len(parts) < 2:
                await self.safe_chat("Usage: !addsong <title> | <artist> | <soundcloud_url>")
                return
            title  = parts[0]
            artist = parts[1]
            url    = parts[2] if len(parts) > 2 else ""
            add_song(title, artist, url, self.data)
            await save_data(self.data)
            await self.safe_chat(f"✅ Added: {title} by {artist} (#{len(self.data['songs'])})")

        elif msg.lower().startswith("!removesong "):
            if not is_master(user):
                await self.safe_chat(f"@{user.username} Master only! 🚫")
                return
            raw = msg[12:].strip()
            try:
                idx = int(raw) - 1
                songs = self.data["songs"]
                if 0 <= idx < len(songs):
                    removed = songs[idx]
                    remove_song(idx, self.data)
                    await save_data(self.data)
                    await self.safe_chat(f"✅ Removed: {removed['title']} by {removed['artist']}")
                else:
                    await self.safe_chat(f"Invalid number. Playlist has {len(songs)} songs.")
            except ValueError:
                await self.safe_chat("Usage: !removesong <number>  (use !playlist to see numbers)")

        # ── Dynamic wrap teleport (anyone) ─────────────────────────────────
        # If the message is exactly !<keyword> and a wrap exists, teleport.

        elif msg.startswith("!") and not msg.startswith("! "):
            keyword = msg[1:].strip().lower()
            wrap = get_wrap(keyword, self.data)
            if wrap:
                pos = Position(x=wrap["x"], y=wrap["y"], z=wrap["z"], facing=wrap["facing"])
                await self.safe_teleport(user.id, pos)
                await self.safe_chat(f"🌀 Teleporting @{user.username} to '{keyword}'!")
