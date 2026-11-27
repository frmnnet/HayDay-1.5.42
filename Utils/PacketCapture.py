"""Plaintext packet capture for debugging the 1.5.42 client protocol.

The server sits at the end of the encrypted RC4 connection, so every packet
that matters can be recorded *after* decryption (client -> server) and before
encryption (server -> client).  Captures are JSONL files in ``captures/``:

    {"ts": "...", "dir": "C2S", "id": 14102, "len": 41,
     "version": 0, "hex": "000004d2..."}

Use ``tools/analyze_packets.py`` to decode them offline with the same message
and command classes the server uses.

Enable/disable with ``CapturePackets`` in config.json (default: true).
"""
import json
import threading
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config.json"

_lock = threading.Lock()
_enabled = None
_dir = None


def _settings():
    global _enabled, _dir
    if _enabled is None:
        try:
            conf = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            conf = {}
        _enabled = bool(conf.get("CapturePackets", True))
        name = conf.get("CaptureDir", "captures")
        path = Path(name)
        _dir = path if path.is_absolute() else BASE_DIR / path
    return _enabled, _dir


def record(direction, packet_id, payload, version=0):
    """Append one packet to the current day's capture file."""
    enabled, folder = _settings()
    if not enabled or payload is None:
        return
    try:
        body = bytes(payload).hex()
        entry = {
            "ts": datetime.now().isoformat(timespec="milliseconds"),
            "dir": direction,
            "id": int(packet_id),
            "len": len(payload),
            "version": int(version or 0),
            "hex": body,
        }
        with _lock:
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / ("packets_%s.jsonl" % datetime.now().strftime("%Y%m%d"))
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry) + "\n")
    except Exception:
        # Capturing must never break the game server.
        pass
