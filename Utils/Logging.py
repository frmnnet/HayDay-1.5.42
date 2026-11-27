"""Central colored logging configuration for the Hay Day server.

Usage::

    from Utils.Logging import logger, setup_logging
    setup_logging()           # once, at startup (Main.py)
    logger.info("...")

Levels/colors can be configured in config.json:

    "LogLevel": "INFO",      # DEBUG/INFO/WARNING/ERROR/CRITICAL
    "LogColor": true,
    "LogDir": "logs",        # file log directory
    "LogMaxBytes": 5242880,  # rotate at 5 MB
    "LogBackups": 3

On Windows, VT100/ANSI processing is enabled on the console so colors work.
File logs: logs/hayday.log (all) and logs/errors.log (warnings + errors).
"""
import json
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config.json"


class ColoredFormatter(logging.Formatter):
    """Formatter that colors the level name and message by severity."""

    COLORS = {
        logging.DEBUG: "\x1b[36m",     # cyan
        logging.INFO: "\x1b[32m",      # green
        logging.WARNING: "\x1b[33m",   # yellow
        logging.ERROR: "\x1b[31m",     # red
        logging.CRITICAL: "\x1b[1;31m",  # bold red
    }
    RESET = "\x1b[0m"
    DIM = "\x1b[2m"

    def __init__(self, fmt=None, datefmt=None, color=True):
        super().__init__(fmt or "%(asctime)s %(levelname)-8s %(name)-12s %(message)s",
                         datefmt or "%H:%M:%S")
        self.color = color

    def format(self, record):
        if self.color:
            color = self.COLORS.get(record.levelno, "")
            orig_levelname = record.levelname
            record.levelname = "%s%s%s" % (color, orig_levelname, self.RESET)
            try:
                return super().format(record)
            finally:
                record.levelname = orig_levelname
        return super().format(record)


def _enable_windows_ansi():
    """Enable ANSI escape processing on Windows consoles."""
    if os.name != "nt":
        return
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        STD_OUTPUT_HANDLE = -11
        ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
        handle = kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING)
    except Exception:
        pass


def _read_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def setup_logging(level=None, color=None, log_dir=None):
    """Configure the root logger once. Safe to call multiple times.

    Adds a colored console handler plus two rotating file handlers:
      - ``logs/hayday.log``  : everything at the configured level
      - ``logs/errors.log``  : WARNING and above (issues only)
    """
    conf = _read_config()
    if level is None:
        level = conf.get("LogLevel", "INFO")
    if color is None:
        color = conf.get("LogColor", True)
    if isinstance(color, str):
        color = color.lower() not in ("false", "0", "no", "off")

    log_dir = Path(log_dir or conf.get("LogDir", BASE_DIR / "logs"))
    max_bytes = int(conf.get("LogMaxBytes", 5 * 1024 * 1024))
    backups = int(conf.get("LogBackups", 3))

    _enable_windows_ansi()
    numeric = getattr(logging, str(level).upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(numeric)
    for h in list(root.handlers):
        root.removeHandler(h)

    # Console: colored, compact
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(numeric)
    handler.setFormatter(ColoredFormatter(color=bool(color)))
    root.addHandler(handler)

    # Files: plain text, full timestamps. Wrapped in try/except so a
    # read-only filesystem never prevents the server from starting.
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        file_fmt = logging.Formatter(
            "%(asctime)s %(levelname)-8s %(name)-12s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S")

        all_log = RotatingFileHandler(
            str(log_dir / "hayday.log"), maxBytes=max_bytes,
            backupCount=backups, encoding="utf-8")
        all_log.setLevel(numeric)
        all_log.setFormatter(file_fmt)
        root.addHandler(all_log)

        issues_log = RotatingFileHandler(
            str(log_dir / "errors.log"), maxBytes=max_bytes,
            backupCount=backups, encoding="utf-8")
        issues_log.setLevel(logging.WARNING)
        issues_log.setFormatter(file_fmt)
        root.addHandler(issues_log)
    except Exception as e:
        root.warning("File logging disabled: %s" % e)

    return logging.getLogger("hayday")


# Default logger for modules that import it before setup_logging() is called.
logger = logging.getLogger("hayday")
