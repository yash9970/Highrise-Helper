"""
Unified persistent storage for ZenBot.
Saves all data to a single Render environment variable (BOT_DATA) via the Render API.
Falls back gracefully to a local JSON file if Render credentials are not available.

Data shape:
{
  "vips":  { username: { added_by, added_at, history: [{action, by, at}] } },
  "wraps": { keyword:  { x, y, z, facing, set_by, set_at } },
  "mods":  { username: { added_by, added_at } },
}
"""

import json
import os
import aiohttp
from datetime import datetime
from pathlib import Path

LOCAL_FILE = Path("bot/bot_data.json")
RENDER_VAR_KEY = "BOT_DATA"


def now_str() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")


def _empty_data() -> dict:
    return {
        "vips": {},
        "wraps": {},
        "mods": {},
    }


_RUNTIME_DATA = None


def load_data() -> dict:
    global _RUNTIME_DATA
    if _RUNTIME_DATA is not None:
        return _RUNTIME_DATA

    # 1. Try Render env var
    raw = os.environ.get(RENDER_VAR_KEY, "").strip()
    if raw:
        try:
            data = json.loads(raw)
            data = _ensure_keys(data)
            print(f"[STORE] Loaded from Render env var — "
                  f"{len(data['vips'])} VIPs, {len(data['wraps'])} wraps, {len(data['mods'])} mods.")
            _RUNTIME_DATA = data
            return data
        except Exception as e:
            print(f"[STORE] Could not parse BOT_DATA env var: {e}")

    # 2. Try local file
    if LOCAL_FILE.exists():
        try:
            with open(LOCAL_FILE, "r") as f:
                data = json.load(f)
            data = _ensure_keys(data)
            print(f"[STORE] Loaded from local file — "
                  f"{len(data['vips'])} VIPs, {len(data['wraps'])} wraps, {len(data['mods'])} mods.")
            _RUNTIME_DATA = data
            return data
        except Exception as e:
            print(f"[STORE] Could not load local file: {e}")

    print("[STORE] No existing data found — starting fresh.")
    data = _empty_data()
    _RUNTIME_DATA = data
    return data


def _ensure_keys(data: dict) -> dict:
    base = _empty_data()
    for key in base:
        if key not in data:
            data[key] = base[key]
    # Remove legacy song keys if present
    for legacy in ("songs", "song_index", "song_queue"):
        data.pop(legacy, None)
    # Migrate old flat VIP format
    for username, v in list(data["vips"].items()):
        if not isinstance(v, dict):
            data["vips"][username] = {
                "added_by": "Unknown",
                "added_at": "Unknown",
                "history": [{"action": "added", "by": "Unknown", "at": "Unknown"}],
            }
    return data


# ── Save ──────────────────────────────────────────────────────────────────────

def _save_local(data: dict):
    try:
        LOCAL_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOCAL_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[STORE] Local save failed: {e}")


async def _save_to_render(data: dict):
    api_key = os.environ.get("RENDER_API_KEY", "").strip()
    service_id = os.environ.get("RENDER_SERVICE_ID", "").strip()
    if not api_key or not service_id:
        return
    url = f"https://api.render.com/v1/services/{service_id}/env-vars"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = [{"key": RENDER_VAR_KEY, "value": json.dumps(data)}]
    try:
        async with aiohttp.ClientSession() as session:
            async with session.put(url, headers=headers, json=payload,
                                   timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status in (200, 201):
                    print(f"[STORE] Saved to Render env var ✅  "
                          f"({len(data['vips'])} VIPs, {len(data['wraps'])} wraps, {len(data['mods'])} mods)")
                else:
                    body = await resp.text()
                    print(f"[STORE] Render API error {resp.status}: {body}")
    except Exception as e:
        print(f"[STORE] Render API request failed: {e}")


async def save_data(data: dict):
    _save_local(data)
    await _save_to_render(data)


# ── VIP helpers ───────────────────────────────────────────────────────────────

def is_vip(username: str, data: dict) -> bool:
    return username.lower() in [u.lower() for u in data["vips"]]


def add_vip(username: str, added_by: str, data: dict) -> bool:
    """Returns True if user was already a VIP."""
    already = is_vip(username, data)
    entry = data["vips"].get(username, {"added_by": added_by, "added_at": now_str(), "history": []})
    entry["history"].append({"action": "added", "by": added_by, "at": now_str()})
    entry["added_by"] = added_by
    entry["added_at"] = now_str()
    data["vips"][username] = entry
    return already


def remove_vip(username: str, removed_by: str, data: dict) -> bool:
    """Returns True if user was found and removed."""
    key = next((k for k in data["vips"] if k.lower() == username.lower()), None)
    if not key:
        return False
    data["vips"][key]["history"].append({"action": "removed", "by": removed_by, "at": now_str()})
    del data["vips"][key]
    return True


# ── Mod helpers ───────────────────────────────────────────────────────────────

def is_mod(username: str, data: dict) -> bool:
    return username.lower() in [u.lower() for u in data.get("mods", {})]


def add_mod(username: str, added_by: str, data: dict) -> bool:
    """Returns True if user was already a mod."""
    already = is_mod(username, data)
    data.setdefault("mods", {})[username] = {"added_by": added_by, "added_at": now_str()}
    return already


def remove_mod(username: str, data: dict) -> bool:
    """Returns True if user was found and removed."""
    mods = data.setdefault("mods", {})
    key = next((k for k in mods if k.lower() == username.lower()), None)
    if not key:
        return False
    del mods[key]
    return True


# ── Wrap helpers ──────────────────────────────────────────────────────────────

def set_wrap(keyword: str, x: float, y: float, z: float, facing: str, set_by: str, data: dict):
    data["wraps"][keyword.lower()] = {
        "x": x, "y": y, "z": z, "facing": facing,
        "set_by": set_by, "set_at": now_str()
    }


def get_wrap(keyword: str, data: dict) -> dict | None:
    return data["wraps"].get(keyword.lower())


def delete_wrap(keyword: str, data: dict) -> bool:
    if keyword.lower() in data["wraps"]:
        del data["wraps"][keyword.lower()]
        return True
    return False
