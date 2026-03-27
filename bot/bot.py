import asyncio
import random
import traceback
from highrise import BaseBot
from highrise.models import Position, SessionMetadata, User, CurrencyItem, Item

from store import (
    load_data, save_data,
    is_vip, add_vip, remove_vip,
    is_mod, add_mod, remove_mod,
    set_wrap, get_wrap, delete_wrap,
    now_str,
)

MASTER_USERNAME = "Zen1thos"
TIP_VIP_THRESHOLD = 500
KEEPALIVE_INTERVAL = 25        # seconds between Highrise pings

DEFAULT_POS  = Position(x=13.0, y=0.10,  z=5.0,  facing="FrontRight")
VIP_FLOOR    = Position(x=4.0,  y=12.25, z=4.5,  facing="FrontRight")
GROUND_FLOOR = Position(x=13.0, y=0.10,  z=5.0,  facing="FrontRight")
FREEZE_POS   = Position(x=0.5,  y=0.0,   z=0.5,  facing="FrontRight")

# Known free emotes (bot can perform these without owning them)
FREE_EMOTES = [
    "wave", "clap", "shy", "yes", "no", "bow", "sit", "sleep",
    "flex", "laugh", "cry", "angry", "shrug", "think", "point",
    "thumbsup", "heart", "dance",
]

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
        super().__init__()
        self.data = load_data()
        print(f"[BOT] Loaded: {len(self.data['vips'])} VIPs, "
              f"{len(self.data['wraps'])} wraps, {len(self.data['mods'])} mods.")

    # ─── Safe helpers ─────────────────────────────────────────────────────────

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
                err = str(e).lower()
                print(f"[BOT] walk_to attempt {attempt+1}/{retries}: {e}")
                # Transport is permanently closed — no point retrying
                if "closing transport" in err or "closed" in err:
                    print("[BOT] walk_to aborted: transport is gone (session replaced).")
                    return
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

    async def _get_outfit(self) -> list:
        """Return the bot's current outfit as a list of Items."""
        try:
            resp = await self.highrise.get_my_outfit()
            # SDK returns GetMyOutfitResponse; outfit is resp.outfit
            if hasattr(resp, "outfit"):
                return list(resp.outfit)
        except Exception as e:
            print(f"[BOT] get_outfit error: {e}")
        return []

    async def _keepalive_loop(self):
        """Ping Highrise every 5 min to keep the WebSocket alive."""
        await asyncio.sleep(60)  # Let startup settle first
        while True:
            try:
                await asyncio.sleep(5 * 60)  # 5 minutes
                await self.highrise.get_room_users()
                print("[BOT] Keepalive ping ✓")
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[BOT] keepalive error: {e}")

    # ─── Lifecycle ────────────────────────────────────────────────────────────

    async def on_start(self, session_metadata: SessionMetadata) -> None:
        print(f"[BOT] Connected! Session: {session_metadata.user_id}")
        # Keepalive loop — runs as a free task so a crash can't kill the connection
        asyncio.create_task(self._keepalive_loop())
        await asyncio.sleep(8)
        await self.safe_walk_to(DEFAULT_POS, retries=15, delay=8.0)
        await self.safe_chat("🤖 ZenBot is online! Type !help for commands.")

    async def on_user_join(self, user: User, position: Position) -> None:
        try:
            await asyncio.sleep(0.5)
            if is_master(user):
                await self.safe_emote("emote-bow")  # bot bows — no target = bot performs
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

    # ─── Commands ─────────────────────────────────────────────────────────────

    async def _handle_command(self, user: User, msg: str):
        ml = msg.lower()

        # ── Help ──────────────────────────────────────────────────────────────

        if ml == "!help":
            await self.safe_chat(
                "📋 ZenBot Commands (1/2):\n"
                "!hi  !joke  !flip  !dance\n"
                "!hug  !slap  !kiss  !rizz\n"
                "!8ball <q>  !emote <name>\n"
                "!vip  !f0  !<wrap> (VIP)\n"
                "@summon <name> — teleport\n"
                "!roomusers  !find <name> (Mod)\n"
                "!kick <name>  !freeze <name> (Mod)"
            )
            await asyncio.sleep(0.5)
            await self.safe_chat(
                "📋 Commands (2/2) [Master]:\n"
                "!setbot  !tele  !pos  !home\n"
                "!setwrap  !wraplist  !deletewrap\n"
                "!addvip  !removevip  !viplist  !viphistory\n"
                "!addmod  !removemod  !modlist\n"
                "!inventory  !emotes\n"
                "!wear <id>  !unwear <id>  !botinfo"
            )

        # ── Fun (everyone) ────────────────────────────────────────────────────

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

        # ── Social interactions ───────────────────────────────────────────────

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
                    await self.safe_emote(f"emote-{emote_name}")
                    await self.safe_chat(f"✨ *does {emote_name}*")
                else:
                    await self.safe_emote(f"emote-{emote_name}", user.id)

        # ── @summon (everyone) ────────────────────────────────────────────────

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

        # ── VIP teleport (VIP + master) ───────────────────────────────────────

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

        # ── Mod commands (Mod + Master) ───────────────────────────────────────

        elif ml == "!roomusers":
            if not (is_mod(user.username, self.data) or is_master(user)):
                await self.safe_chat(f"@{user.username} Mod only! 🚫"); return
            try:
                resp = await self.highrise.get_room_users()
                if hasattr(resp, "content"):
                    lines = [f"👥 Room ({len(resp.content)} users):"]
                    for ru, pos in resp.content[:15]:
                        if isinstance(pos, Position):
                            lines.append(f"  @{ru.username} — ({pos.x:.0f},{pos.y:.1f},{pos.z:.0f})")
                        else:
                            lines.append(f"  @{ru.username} — (sitting)")
                    if len(resp.content) > 15:
                        lines.append(f"  ... and {len(resp.content)-15} more")
                    await self.safe_chat("\n".join(lines))
            except Exception as e:
                print(f"[BOT] !roomusers error: {e}")

        elif ml.startswith("!find "):
            if not (is_mod(user.username, self.data) or is_master(user)):
                await self.safe_chat(f"@{user.username} Mod only! 🚫"); return
            target_name = msg[6:].strip().lstrip("@")
            pos = await self._get_user_pos(target_name)
            if pos is None:
                await self.safe_chat(f"@{target_name} is not in the room.")
            elif isinstance(pos, Position):
                await self.safe_chat(f"📍 @{target_name} → x={pos.x:.1f}, y={pos.y:.2f}, z={pos.z:.1f}")
            else:
                await self.safe_chat(f"📍 @{target_name} is sitting on an anchor.")

        elif ml.startswith("!kick "):
            if not (is_mod(user.username, self.data) or is_master(user)):
                await self.safe_chat(f"@{user.username} Mod only! 🚫"); return
            target_name = msg[6:].strip().lstrip("@")
            try:
                resp = await self.highrise.get_room_users()
                if hasattr(resp, "content"):
                    target_user = next((ru for ru, _ in resp.content
                                        if ru.username.lower() == target_name.lower()), None)
                    if not target_user:
                        await self.safe_chat(f"'{target_name}' is not in the room.")
                    else:
                        await self.safe_teleport(target_user.id, GROUND_FLOOR)
                        await self.safe_chat(f"🚪 @{target_user.username} has been moved to the entrance.")
            except Exception as e:
                print(f"[BOT] !kick error: {e}")

        elif ml.startswith("!freeze "):
            if not (is_mod(user.username, self.data) or is_master(user)):
                await self.safe_chat(f"@{user.username} Mod only! 🚫"); return
            target_name = msg[8:].strip().lstrip("@")
            try:
                resp = await self.highrise.get_room_users()
                if hasattr(resp, "content"):
                    target_user = next((ru for ru, _ in resp.content
                                        if ru.username.lower() == target_name.lower()), None)
                    if not target_user:
                        await self.safe_chat(f"'{target_name}' is not in the room.")
                    else:
                        # Teleport to freeze corner 3 times in quick succession
                        for _ in range(3):
                            await self.safe_teleport(target_user.id, FREEZE_POS)
                            await asyncio.sleep(0.5)
                        await self.safe_chat(f"🧊 @{target_user.username} has been frozen!")
            except Exception as e:
                print(f"[BOT] !freeze error: {e}")

        # ── Master: bot movement ──────────────────────────────────────────────

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

        # ── Master: bot inventory & outfit ────────────────────────────────────

        elif ml == "!inventory":
            if not is_master(user):
                await self.safe_chat(f"@{user.username} Master only! 🚫"); return
            outfit = await self._get_outfit()
            if not outfit:
                await self.safe_chat("👗 Bot outfit is empty or couldn't be fetched.")
            else:
                await self.safe_chat(f"👗 Bot Outfit ({len(outfit)} items):")
                # Send in batches of 5 to stay under Highrise's message length limit
                batch = []
                for i, item in enumerate(outfit):
                    batch.append(f"{i+1}. {item.id}")
                    if len(batch) == 5:
                        await self.safe_chat("\n".join(batch))
                        batch = []
                        await asyncio.sleep(0.4)
                if batch:
                    await self.safe_chat("\n".join(batch))

        elif ml == "!emotes":
            if not is_master(user):
                await self.safe_chat(f"@{user.username} Master only! 🚫"); return
            await self.safe_chat(
                f"🎭 Free emotes ({len(FREE_EMOTES)}):\n"
                f"{', '.join(FREE_EMOTES)}\n"
                f"Usage: !emote <name>"
            )

        elif ml.startswith("!wear "):
            if not is_master(user):
                await self.safe_chat(f"@{user.username} Master only! 🚫"); return
            item_id = msg[6:].strip()
            if not item_id:
                await self.safe_chat("Usage: !wear <item_id>"); return
            try:
                outfit = await self._get_outfit()
                # Avoid duplicates
                if any(i.id == item_id for i in outfit):
                    await self.safe_chat(f"Already wearing '{item_id}'.")
                    return
                new_item = Item(type="clothing", amount=1, id=item_id)
                new_outfit = outfit + [new_item]
                await self.highrise.set_outfit(new_outfit)
                await self.safe_chat(f"✅ Equipped: {item_id}")
            except Exception as e:
                await self.safe_chat(f"❌ Couldn't equip '{item_id}': {e}")

        elif ml.startswith("!unwear "):
            if not is_master(user):
                await self.safe_chat(f"@{user.username} Master only! 🚫"); return
            item_id = msg[8:].strip()
            if not item_id:
                await self.safe_chat("Usage: !unwear <item_id>"); return
            try:
                outfit = await self._get_outfit()
                new_outfit = [i for i in outfit if i.id != item_id]
                if len(new_outfit) == len(outfit):
                    await self.safe_chat(f"'{item_id}' is not in the current outfit.")
                    return
                await self.highrise.set_outfit(new_outfit)
                await self.safe_chat(f"✅ Removed: {item_id}")
            except Exception as e:
                await self.safe_chat(f"❌ Couldn't remove '{item_id}': {e}")

        elif ml == "!botinfo":
            if not is_master(user):
                await self.safe_chat(f"@{user.username} Master only! 🚫"); return
            try:
                resp = await self.highrise.get_room_users()
                count = len(resp.content) if hasattr(resp, "content") else "?"
                vip_count = len(self.data["vips"])
                mod_count = len(self.data.get("mods", {}))
                wrap_count = len(self.data["wraps"])
                await self.safe_chat(
                    f"🤖 ZenBot Status:\n"
                    f"  👥 Room: {count} users\n"
                    f"  💎 VIPs: {vip_count}  🛡️ Mods: {mod_count}\n"
                    f"  📍 Wraps: {wrap_count}"
                )
            except Exception as e:
                await self.safe_chat(f"❌ botinfo error: {e}")

        # ── Master: setwrap ───────────────────────────────────────────────────

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

        # ── Master: VIP management ────────────────────────────────────────────

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

        # ── Master: Mod management ────────────────────────────────────────────

        elif ml.startswith("!addmod "):
            if not is_master(user):
                await self.safe_chat(f"@{user.username} Master only! 🚫"); return
            target = msg[8:].strip().lstrip("@")
            if not target:
                await self.safe_chat("Usage: !addmod <username>"); return
            already = add_mod(target, user.username, self.data)
            await save_data(self.data)
            if already:
                await self.safe_chat(f"@{target} is already a Mod.")
            else:
                await self.safe_chat(f"🛡️ @{target} is now a Mod!")

        elif ml.startswith("!removemod "):
            if not is_master(user):
                await self.safe_chat(f"@{user.username} Master only! 🚫"); return
            target = msg[11:].strip().lstrip("@")
            found = remove_mod(target, self.data)
            await save_data(self.data)
            await self.safe_chat(f"@{target} Mod removed." if found else f"@{target} is not a Mod.")

        elif ml == "!modlist":
            if not is_master(user):
                await self.safe_chat(f"@{user.username} Master only! 🚫"); return
            mods = self.data.get("mods", {})
            if mods:
                await self.safe_chat(f"🛡️ Mods ({len(mods)}): {', '.join(mods.keys())}")
            else:
                await self.safe_chat("No mods yet. Use !addmod <username>")

        # ── Dynamic wrap teleport (VIP + Master) ──────────────────────────────
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
