"""
helpers.py
----------
Small, reusable utility functions shared across the CLI and
integration layer: cross-platform file opening, human-readable
formatting, and optional user-defined scan directories.

None of these touch Member 1/2/3's algorithms; they are pure
integration/UX glue.
"""

import json
import platform
import subprocess
import logging
from pathlib import Path
from typing import List, Optional

from utils.config import USER_CONFIG_PATH

logger = logging.getLogger("local_search_engine")


# ---------------------------------------------------------------------
# Cross-platform "open with default application"
# ---------------------------------------------------------------------
def open_file(filepath: str) -> Optional[str]:
    """
    Open `filepath` with the operating system's default application.

    Returns None on success, or a short human-readable error message
    on failure (never raises).
    """
    path = Path(filepath)
    if not path.exists():
        return "That file no longer exists at its recorded location."

    system = platform.system()
    try:
        if system == "Windows":
            # os.startfile is Windows-only; ignore attr-defined on other OSes.
            import os
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif system == "Darwin":
            subprocess.run(["open", str(path)], check=True)
        else:
            # Linux and other Unix-likes.
            subprocess.run(["xdg-open", str(path)], check=True)
        return None
    except FileNotFoundError:
        return "No default application handler was found for this file type."
    except (subprocess.CalledProcessError, OSError) as exc:
        logger.warning("Failed to open file %s: %s", filepath, exc)
        return "The file could not be opened automatically. Try opening it manually."


# ---------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------
def format_size(num_bytes: float) -> str:
    """Human-readable byte size, e.g. 1536 -> '1.5 KB'."""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def format_duration(seconds: float) -> str:
    """Human-readable duration, e.g. 134.2 -> '2m 14s'."""
    seconds = int(round(seconds))
    minutes, secs = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m {secs}s"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


# ---------------------------------------------------------------------
# Optional user-defined extra scan directories
# ---------------------------------------------------------------------
def load_extra_directories() -> List[Path]:
    """
    Read optional extra directories from the user config file
    (~/.local_search_engine/config.json), if it exists.

    Expected format: {"extra_directories": ["/some/path", "..."]}
    Missing/invalid config is treated as "no extra directories" and
    never raises.
    """
    if not USER_CONFIG_PATH.exists():
        return []

    try:
        with open(USER_CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        raw_dirs = data.get("extra_directories", [])
        dirs = [Path(d).expanduser() for d in raw_dirs if isinstance(d, str)]
        return [d for d in dirs if d.exists() and d.is_dir()]
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Could not read user config %s: %s", USER_CONFIG_PATH, exc)
        return []


def setup_logging() -> None:
    """Configure file-based logging; the CLI never shows raw tracebacks."""
    from utils.config import LOG_PATH

    logging.basicConfig(
        filename=str(LOG_PATH),
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
