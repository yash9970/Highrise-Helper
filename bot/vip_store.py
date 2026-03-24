"""
VIP persistence via Render Environment Variables.

The VIP list is stored as a JSON string in the RENDER env var VIP_DATA.
On every bot start it reads from that env var. On every VIP change it
writes back to Render via the API — so restarts never lose anything.

Falls back to a local file if Render API credentials are not set
(useful for local development / Replit).
"""

import json
import os
import asyncio
import aiohttp
from datetime import datetime
from pathlib import Path

LOCAL_VIP_FILE = Path("bot/vip_users.json")
RENDER_VAR_KEY = "VIP_DATA"


def now_str() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")


# ── Local fallback ────────────────────────────────────────────────────────────

def _load_local() -> dict:
    # 1. Check env var first (set by Render)
    raw = os.environ.get(RENDER_VAR_KEY, "")
    if raw:
        try:
            data = json.loads(raw)
            print(f"[VIP] Loaded {len(data)} VIPs from environment variable.")
            return _migrate(data)
        except Exception as e:
            print(f"[VIP] Could not parse VIP_DATA env var: {e}")

    # 2. Fallback: local file
    if LOCAL_VIP_FILE.exists():
        try:
            with open(LOCAL_VIP_FILE, "r") as f:
                data = json.load(f)
            print(f"[VIP] Loaded {len(data)} VIPs from local file.")
            return _migrate(data)
        except Exception as e:
            print(f"[VIP] Could not load local VIP file: {e}")

    return {}


def _migrate(data: dict) -> dict:
    """Upgrade old flat {username: True} format to rich format."""
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


def _save_local(data: dict):
    try:
        LOCAL_VIP_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOCAL_VIP_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[VIP] Could not write local VIP file: {e}")


# ── Render API persistence ────────────────────────────────────────────────────

async def _save_to_render(data: dict) -> bool:
    """Push VIP_DATA env var to Render. Returns True on success."""
    api_key = os.environ.get("RENDER_API_KEY", "")
    service_id = os.environ.get("RENDER_SERVICE_ID", "")

    if not api_key or not service_id:
        print("[VIP] No Render credentials — using local file only.")
        return False

    url = f"https://api.render.com/v1/services/{service_id}/env-vars"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = [{"key": RENDER_VAR_KEY, "value": json.dumps(data)}]

    try:
        async with aiohttp.ClientSession() as session:
            async with session.put(url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status in (200, 201):
                    print(f"[VIP] Saved {len(data)} VIPs to Render env vars ✅")
                    return True
                else:
                    body = await resp.text()
                    print(f"[VIP] Render API error {resp.status}: {body}")
                    return False
    except Exception as e:
        print(f"[VIP] Render API request failed: {e}")
        return False


# ── Public interface ──────────────────────────────────────────────────────────

def load_vips() -> dict:
    """Load VIPs. Call this at startup (sync)."""
    return _load_local()


async def save_vips(data: dict):
    """Save VIPs. Always writes locally, and also tries Render API."""
    _save_local(data)
    await _save_to_render(data)


def is_vip(username: str, vip_data: dict) -> bool:
    return username.lower() in [u.lower() for u in vip_data.keys()]


def add_vip(username: str, added_by: str, vip_data: dict) -> tuple[dict, bool]:
    """Add a VIP. Returns (updated_data, was_already_vip)."""
    already = is_vip(username, vip_data)
    entry = vip_data.get(username, {
        "added_by": added_by,
        "added_at": now_str(),
        "history": [],
    })
    entry["history"].append({"action": "added", "by": added_by, "at": now_str()})
    entry["added_by"] = added_by
    entry["added_at"] = now_str()
    vip_data[username] = entry
    return vip_data, already


def remove_vip(username: str, removed_by: str, vip_data: dict) -> tuple[dict, bool]:
    """Remove a VIP. Returns (updated_data, was_found)."""
    found_key = next((k for k in vip_data if k.lower() == username.lower()), None)
    if not found_key:
        return vip_data, False
    vip_data[found_key]["history"].append({"action": "removed", "by": removed_by, "at": now_str()})
    del vip_data[found_key]
    return vip_data, True
