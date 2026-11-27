import json
from pathlib import Path

from Logic.GameState import GameState

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config.json"

# Values that belong to a player row, not to the operator's config file.
# Account ids are deliberately excluded: changing them would move the player
# to a different row (and lose their farm).
MUTABLE_FIELDS = [
    "PassToken", "Name", "Diamonds", "Cash", "ExpLevel", "ExpPoints",
    "TutorialCompleted",
]

_FIELD_MAP = {
    "PassToken": "pass_token",
    "Name": "name",
    "Diamonds": "diamonds",
    "Cash": "cash",
    "ExpLevel": "exp_level",
    "ExpPoints": "exp_points",
    "TutorialCompleted": "tutorial_completed",
}


def load_config(account=None):
    """config.json with the player's account values layered on top.

    Passing an ``account`` makes the returned dict describe *that* player
    (used for per-player messages); without one the configured account is
    used for operator-facing endpoints.  The mutable player fields always
    come from SQLite, never from the file on disk.
    """
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            conf = json.load(f)
    except (OSError, ValueError):
        conf = {}
    if not isinstance(conf, dict):
        conf = {}
    try:
        acct = account or GameState.instance().account
        conf.update(acct.to_config())
    except Exception:
        pass
    return conf


def save_config(conf):
    """Apply player fields from ``conf`` to the live account.

    Kept for tools/admin scripts that used to write ``config.json`` to change
    a player's resources.  The values now land in the account row through
    :meth:`GameState.account_set`, so the next ``flush()`` persists them and
    the file on disk is no longer silently out of date.
    """
    changes = {}
    for key in MUTABLE_FIELDS:
        if key in conf:
            changes[_FIELD_MAP[key]] = conf[key]
    if changes:
        try:
            GameState.instance().account_set(**changes)
        except (ValueError, TypeError):
            return False
    return True
