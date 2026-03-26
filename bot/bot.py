import asyncio
import random
import traceback
from highrise import BaseBot
from highrise.models import Position, SessionMetadata, User, CurrencyItem, Item

from store import (
    load_data, save_data, is_vip, add_vip, remove_vip,
    set_wrap, get_wrap, delete_wrap,
    current_song, next_song, add_song, remove_song,
    queue_song, dequeue_song, get_queue, search_soundcloud,
    now_str,
)

MASTER_USERNAME = "Zen1thos"
TIP_VIP_THRESHOLD = 500
SONG_ANNOUNCE_INTERVAL = 300   # 5 minutes between auto song announcements
KEEPALIVE_INTERVAL = 25        # seconds between Highrise pings

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

    async def safe_walk_to(self, pos: Position, retries: int = 15, delay: float = 8.0):
        for attempt in range(retries):
            try:
                await self.highrise.walk_to(pos)
                print(f"[BOT] Successfully walked to target position.")
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
        try:
            resp = await self.highrise.get_room_users()
            if hasattr(resp, "content"):
                for room_user, pos in resp.content:
                    if room_user.username.lower() == username.lower():
                        return pos
        except Exception as e:
            print(f"[BOT] get_user_pos error: {e}")
        return None

    async def _song_loop(self):
        """Announce songs every 5 minutes. Queued requests play first."""
        await asyncio.sleep(SONG_ANNOUNCE_INTERVAL)
        while True:
            try:
                # Drain the request queue first
                queued = dequeue_song(self.data)
                if queued:
                    msg = (f"🎵 Now Playing (requested by @{queued['requested_by']}): "
                           f"{queued['title']} by {queued['artist']}")
                    if queued.get("url"):
                        msg += f"\n🔗 {queued['url']}"
                    remaining = len(get_queue(self.data))
                    if remaining:
                        msg += f"\n📋 {remaining} more in queue"
                else:
                    # Fall back to auto-playlist
                    song = current_song(self.data)
                    msg = f"🎵 Now Playing: {song['title']} by {song['artist']}"
                    if song.get("url"):
                        msg += f"\n🔗 {song['url']}"
                    next_song(self.data)
                await self.safe_chat(msg)
                await asyncio.sleep(SONG_ANNOUNCE_INTERVAL)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[BOT] song loop error: {e}")
                await asyncio.sleep(30)

    # ─── Lifecycle ────────────────────────────────────────────────────────────

    async def on_start(self, session_metadata: SessionMetadata) -> None:
        print(f"[BOT] Connected! Session: {session_metadata.user_id}")
        # Launch song loop as a free task — NOT in the SDK's TaskGroup,
        # so a crash here cannot kill the bot connection.
        self._song_task = asyncio.create_task(self._song_loop())
        await asyncio.sleep(8)
        await self.safe_walk_to(DEFAULT_POS, retries=15, delay=8.0)
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
            amount = getattr(tip, "amount", 0)
            if not isinstance(amount, int):
                amount = 0
            print(f"[BOT] Tip: {sender.username} → {amount} gold")
            if amount >= TIP_VIP_THRESHOLD and not is_vip(sender.username, self.data) and not is_master(sender):
                add_vip(sender.username, f"AutoVIP (tipped {amount})", self.data)
                await save_data(self.data)
                await self.safe_chat(
                    f"💰 WOW! @{sender.username} tipped {amount} gold and earned VIP status! 👑✨"
                )
            elif amount > 0:
                await self.safe_chat(f"💖 Thank you for the {amount} gold tip, @{sender.username}!")
        except Exception as e:
            print(f"[BOT] on_tip error: {e}")
            traceback.print_exc()

    async def on_chat(self, user: User, message: str) -> None:
        try:
            await self._handle_command(user, message.strip())
        except Exception as e:
            print(f"[BOT] on_chat error '{message}': {e}")
            traceback.print_exc()

    # ─── Commands ────────────────────────────────────────────────────────────

    async def _handle_command(self, user: User, msg: str):
        ml = msg.lower()

        # ── Help ───────────────────────────────────────────────────────────

        if ml == "!help":
            await self.safe_chat(
                "📋 ZenBot Commands (1/2):\n"
                "!hi  !joke  !flip  !dance\n"
                "!hug  !slap  !kiss  !rizz\n"
                "!8ball <q>  !emote <name>\n"
                "!song  !playlist  !queue\n"
                "!play <q> — req song (VIP)\n"
                "@summon <name> — teleport\n"
                "!vip  !f0  !<wrap> (VIP)\n"
            )
            await asyncio.sleep(0.5)
            await self.safe_chat(
                "📋 Commands (2/2) [Master]:\n"
                "!setbot !tele !pos !home\n"
                "!setwrap !wraplist !deletewrap\n"
                "!addvip !removevip\n"
                "!viplist !viphistory !nextsong\n"
                "!addsong !removesong !clearqueue"
            )

        # ── Fun (everyone) ─────────────────────────────────────────────────

        elif ml == "!hi":
            await self.safe_chat(f"@{user.username} {random.choice(GREETINGS)}")

        elif ml == "!joke":
            jokes = [
                "Why don't scientists trust atoms? They make up everything! 😂",
                "I told my wife she was drawing her eyebrows too high. She looked surprised. 😂",
                "What do you call a fake noodle? An impasta! 😂",
                "Why did the scarecrow win an award? Outstanding in his field! 😂",
                "I'm reading a book about anti-gravity. Impossible to put down! 😂",
            ]
            await self.safe_chat(random.choice(jokes))

        elif ml.startswith("!8ball"):
            answers = ["Absolutely! 🎱", "No way! 🎱", "Most likely yes! 🎱", "I doubt it 🎱",
                       "The stars say YES! 🎱", "Ask again later 🎱", "Definitely! 🎱", "Signs point to no 🎱"]
            await self.safe_chat(random.choice(answers))

        elif ml == "!dance":
            # Only use free/universal emotes — no target_id to avoid ownership errors
            dances = ["emote-dance", "emote-wave", "emote-clap", "emote-shy", "emote-yes"]
            await self.safe_emote(random.choice(dances))

        elif ml == "!flip":
            res = random.choice(["Heads", "Tails"])
            await self.safe_chat(f"🪙 @{user.username} flipped a coin: {res}!")

        # ── Social interactions ─────────────────────────────────────────────
        elif ml.startswith("!hug "):
            target = msg[5:].strip()
            await self.safe_chat(f"@{user.username} sends a warm, cozy hug to {target}! 🤗💖")

        elif ml.startswith("!slap "):
            target = msg[6:].strip()
            await self.safe_chat(f"@{user.username} playfully slaps {target}! *Ouch!* 🖐️💥")

        elif ml.startswith("!kiss "):
            target = msg[6:].strip()
            await self.safe_chat(f"@{user.username} blows a sweet kiss to {target}! 💋✨")

        elif ml == "!rizz":
            rizz_lines = [
                "Are you a magician? Because whenever I look at you, everyone else disappears. ✨",
                "Do you have a map? I keep getting lost in your eyes. 🗺️",
                "Are you a campfire? Because you are hot and I want s'more. 🔥"
            ]
            await self.safe_chat(f"@{user.username}: {random.choice(rizz_lines)}")

        # ── !emote — anyone can use; master gets no target (bot emotes freely)


        elif ml.startswith("!emote "):
            emote_name = msg[7:].strip()
            if emote_name:
                if is_master(user):
                    # Bot performs emote freely (no target)
                    await self.safe_emote(f"emote-{emote_name}")
                    await self.safe_chat(f"✨ *does {emote_name}*")
                else:
                    # Bot emotes toward the requester
                    await self.safe_emote(f"emote-{emote_name}", user.id)

        # ── Music (everyone) ───────────────────────────────────────────────

        elif ml == "!song":
            song = current_song(self.data)
            reply = f"🎵 Now Playing: {song['title']} by {song['artist']}"
            if song.get("url"):
                reply += f"\n🔗 {song['url']}"
            await self.safe_chat(reply)

        elif ml == "!queue":
            queue = get_queue(self.data)
            if not queue:
                await self.safe_chat("📋 No songs in queue! Type !play <title> to request one.")
            else:
                lines = [f"📋 Song Queue ({len(queue)}):"]
                for i, s in enumerate(queue[:5], 1):
                    lines.append(f"  {i}. {s['title']} — {s['artist']} (by @{s['requested_by']})")
                if len(queue) > 5:
                    lines.append(f"  ... and {len(queue)-5} more")
                await self.safe_chat("\n".join(lines))

        elif ml.startswith("!play "):
            if not (is_vip(user.username, self.data) or is_master(user)):
                await self.safe_chat(f"@{user.username} 🎵 Song requests are VIP only! Ask Master {MASTER_USERNAME} for VIP 💎")
                return
            query_str = msg[6:].strip()
            query_lower = query_str.lower()
            songs = self.data["songs"]
            
            # 1. Find best match in local playlist
            match = next(
                (s for s in songs if query_lower in s["title"].lower() or query_lower in s["artist"].lower()),
                None
            )
            
            # 2. If found locally, queue it
            if match:
                queue_song(match, user.username, self.data)
                pos = len(get_queue(self.data))
                await self.safe_chat(
                    f"✅ @{user.username} queued: {match['title']} by {match['artist']} "
                    f"(#{pos} in queue) 🎵"
                )
            # 3. If not found locally, search SoundCloud via yt-dlp
            else:
                await self.safe_chat(f"🔍 Searching SoundCloud for '{query_str}'...")
                # Run the synchronous yt-dlp search in a thread to avoid blocking the bot loop
                sc_match = await asyncio.to_thread(search_soundcloud, query_str)
                if sc_match:
                    queue_song(sc_match, user.username, self.data)
                    pos = len(get_queue(self.data))
                    await self.safe_chat(
                        f"✅ @{user.username} queued (via SoundCloud): {sc_match['title']} by {sc_match['artist']} "
                        f"(#{pos} in queue) 🎵\n🔗 {sc_match['url']}"
                    )
                else:
                    await self.safe_chat(
                        f"@{user.username} ❌ Couldn't find '{query_str}' in playlist or SoundCloud."
                    )


        elif ml == "!nextsong":
            if is_master(user):
                # If there's a queue, pop from it; otherwise advance playlist
                queued = dequeue_song(self.data)
                if queued:
                    msg_text = (f"⏭️ Now Playing (requested by @{queued['requested_by']}): "
                                f"{queued['title']} by {queued['artist']}")
                    if queued.get("url"):
                        msg_text += f"\n🔗 {queued['url']}"
                    remaining = len(get_queue(self.data))
                    if remaining:
                        msg_text += f"\n📋 {remaining} more in queue"
                    await self.safe_chat(msg_text)
                else:
                    song = next_song(self.data)
                    await save_data(self.data)
                    reply = f"⏭️ Next: {song['title']} by {song['artist']}"
                    if song.get("url"):
                        reply += f"\n🔗 {song['url']}"
                    await self.safe_chat(reply)
            else:
                await self.safe_chat(f"@{user.username} Only Master can skip songs! 🚫")

        elif ml == "!playlist":
            songs = self.data["songs"]
            if not songs:
                await self.safe_chat("Playlist is empty! Master can add with !addsong")
                return
            idx = self.data["song_index"] % len(songs)
            lines = ["🎶 Playlist:"]
            for i, s in enumerate(songs[:10]):
                marker = "▶️" if i == idx else f"{i+1}."
                lines.append(f"{marker} {s['title']} — {s['artist']}")
            await self.safe_chat("\n".join(lines))

        # ── @summon (everyone) ─────────────────────────────────────────────

        elif ml.startswith("@summon "):
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

        # ── VIP teleport (VIP + master) ────────────────────────────────────

        elif ml == "!vip":
            if is_vip(user.username, self.data) or is_master(user):
                await self.safe_teleport(user.id, VIP_FLOOR)
                await self.safe_chat(f"✨ VIP floor, @{user.username}!")
            else:
                await self.safe_chat(f"@{user.username} VIPs only! Ask Master {MASTER_USERNAME} 💎")

        elif ml == "!f0":
            if is_vip(user.username, self.data) or is_master(user):
                await self.safe_teleport(user.id, GROUND_FLOOR)
                await self.safe_chat(f"🚀 Ground floor, @{user.username}!")
            else:
                await self.safe_chat(f"@{user.username} VIP only! 🚫")

        # ── Master: bot movement ───────────────────────────────────────────

        elif ml == "!setbot":
            if not is_master(user):
                await self.safe_chat(f"@{user.username} Master only! 🚫"); return
            pos = await self._get_user_pos(MASTER_USERNAME)
            if not pos:
                await self.safe_chat("Couldn't find your position!"); return
            if not isinstance(pos, Position):
                await self.safe_chat("Please stand up first!"); return
            await self.safe_walk_to(pos)
            await self.safe_chat("✅ Moved to your position, Master!")

        elif ml == "!home":
            if not is_master(user):
                await self.safe_chat(f"@{user.username} Master only! 🚫"); return
            await self.safe_walk_to(DEFAULT_POS)
            await self.safe_chat("Returning to my post! 🏠")

        elif ml == "!tele":
            if not is_master(user):
                await self.safe_chat(f"@{user.username} Master only! 🚫"); return
            pos = await self._get_user_pos(MASTER_USERNAME)
            if not pos:
                await self.safe_chat("Couldn't find your location!"); return
            if not isinstance(pos, Position):
                await self.safe_chat("Please stand up first!"); return
            await self.safe_walk_to(pos)
            await self.safe_chat("Coming to you, Master! 🚀")

        elif ml == "!pos":
            if not is_master(user):
                await self.safe_chat(f"@{user.username} Master only! 🚫"); return
            pos = await self._get_user_pos(MASTER_USERNAME)
            if not pos:
                await self.safe_chat("Couldn't find your location!"); return
            if not isinstance(pos, Position):
                await self.safe_chat("You are sitting on an anchor!"); return
            await self.safe_chat(f"📍 x={pos.x:.1f}, y={pos.y:.2f}, z={pos.z:.1f}")

        # ── Master: setwrap ────────────────────────────────────────────────

        elif ml.startswith("!setwrap ") or ml.startswith("/setwrap "):
            if not is_master(user):
                await self.safe_chat(f"@{user.username} Master only! 🚫"); return
            keyword = msg.split(None, 1)[1].strip().lower()
            if not keyword:
                await self.safe_chat("Usage: !setwrap <keyword>"); return
            pos = await self._get_user_pos(user.username)
            if not pos:
                await self.safe_chat("Couldn't find your position!"); return
            if not isinstance(pos, Position):
                await self.safe_chat("Please stand up first to set a wrap!"); return
            set_wrap(keyword, pos.x, pos.y, pos.z, pos.facing, user.username, self.data)
            await save_data(self.data)
            await self.safe_chat(f"✅ '!{keyword}' saved! VIPs can now type !{keyword} to teleport here.")

        elif ml in ("!wraplist", "/wraplist"):
            if not is_master(user):
                await self.safe_chat(f"@{user.username} Master only! 🚫"); return
            wraps = self.data["wraps"]
            if not wraps:
                await self.safe_chat("No wraps yet. Use !setwrap <keyword>")
            else:
                lines = [f"📍 Wraps ({len(wraps)}):"]
                for kw, w in wraps.items():
                    lines.append(f"  !{kw} — by {w['set_by']}")
                await self.safe_chat("\n".join(lines))

        elif ml.startswith("!deletewrap ") or ml.startswith("/deletewrap "):
            if not is_master(user):
                await self.safe_chat(f"@{user.username} Master only! 🚫"); return
            keyword = msg.split(None, 1)[1].strip().lower()
            if delete_wrap(keyword, self.data):
                await save_data(self.data)
                await self.safe_chat(f"✅ '!{keyword}' deleted.")
            else:
                await self.safe_chat(f"No wrap '!{keyword}' found.")

        # ── Master: VIP management ─────────────────────────────────────────

        elif ml.startswith("!addvip "):
            if not is_master(user):
                await self.safe_chat(f"@{user.username} Master only! 🚫"); return
            target = msg[8:].strip().lstrip("@")
            if target:
                already = add_vip(target, user.username, self.data)
                await save_data(self.data)
                if already:
                    await self.safe_chat(f"@{target} was already VIP — history updated.")
                else:
                    await self.safe_chat(f"✨ @{target} granted VIP by {user.username}! 👑")
            else:
                await self.safe_chat("Usage: !addvip <username>")

        elif ml.startswith("!removevip "):
            if not is_master(user):
                await self.safe_chat(f"@{user.username} Master only! 🚫"); return
            target = msg[11:].strip().lstrip("@")
            found = remove_vip(target, user.username, self.data)
            await save_data(self.data)
            await self.safe_chat(f"@{target} VIP removed." if found else f"@{target} is not a VIP.")

        elif ml == "!viplist":
            if not is_master(user):
                await self.safe_chat(f"@{user.username} Master only! 🚫"); return
            vips = self.data["vips"]
            if vips:
                await self.safe_chat(f"💎 VIPs ({len(vips)}): {', '.join(vips.keys())}")
            else:
                await self.safe_chat("No VIPs yet.")

        elif ml.startswith("!viphistory"):
            if not is_master(user):
                await self.safe_chat(f"@{user.username} Master only! 🚫"); return
            parts = msg.split(None, 1)
            if len(parts) == 2:
                target = parts[1].strip().lstrip("@")
                entry = next((v for k, v in self.data["vips"].items() if k.lower() == target.lower()), None)
                if entry:
                    lines = [f"📋 @{target} history:"]
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
                        lines.append(f"  {name} — added by {e.get('added_by','?')}")
                    await self.safe_chat("\n".join(lines))
                else:
                    await self.safe_chat("No VIP history yet.")

        # ── Master: song management ────────────────────────────────────────

        elif ml.startswith("!addsong "):
            if not is_master(user):
                await self.safe_chat(f"@{user.username} Master only! 🚫"); return
            raw = msg[9:].strip()
            parts = [p.strip() for p in raw.split("|")]
            if len(parts) < 2:
                await self.safe_chat("Usage: !addsong <title> | <artist> | <soundcloud_url>"); return
            title = parts[0]; artist = parts[1]; url = parts[2] if len(parts) > 2 else ""
            add_song(title, artist, url, self.data)
            await save_data(self.data)
            await self.safe_chat(f"✅ Added: {title} by {artist} (song #{len(self.data['songs'])})")

        elif ml.startswith("!removesong "):
            if not is_master(user):
                await self.safe_chat(f"@{user.username} Master only! 🚫"); return
            try:
                idx = int(msg[12:].strip()) - 1
                songs = self.data["songs"]
                if 0 <= idx < len(songs):
                    removed = songs[idx]
                    remove_song(idx, self.data)
                    await save_data(self.data)
                    await self.safe_chat(f"✅ Removed: {removed['title']} by {removed['artist']}")
                else:
                    await self.safe_chat(f"Invalid number. Playlist has {len(songs)} songs.")
            except ValueError:
                await self.safe_chat("Usage: !removesong <number>  (see !playlist for numbers)")

        elif ml == "!clearqueue":
            if not is_master(user):
                await self.safe_chat(f"@{user.username} Master only! 🚫"); return
            count = len(get_queue(self.data))
            self.data["song_queue"] = []
            await self.safe_chat(f"✅ Queue cleared! ({count} requests removed)" if count else "Queue was already empty.")

        # ── Dynamic wrap teleport (VIP + Master) ───────────────────────────
        # Must be LAST — catches any !keyword that matches a saved wrap

        elif ml.startswith("!") and " " not in ml:
            keyword = ml[1:]
            wrap = get_wrap(keyword, self.data)
            if wrap:
                if not (is_vip(user.username, self.data) or is_master(user)):
                    await self.safe_chat(f"@{user.username} Wrap teleports are VIP only! 🚫"); return
                pos = Position(x=wrap["x"], y=wrap["y"], z=wrap["z"], facing=wrap["facing"])
                await self.safe_teleport(user.id, pos)
                await self.safe_chat(f"🌀 Teleporting @{user.username} to '{keyword}'!")
