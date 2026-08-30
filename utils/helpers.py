"""
helpers.py
----------
Small reusable utility functions shared across the project.

Provides:
- Cross-platform file opening
- Human-readable size formatting
- Human-readable duration formatting
- Optional extra scan directories
- Logging setup

This module must NOT import controller.py.
"""

import json
import logging
import platform
import subprocess
from pathlib import Path
from typing import List, Optional

from utils.config import USER_CONFIG_PATH

logger = logging.getLogger("local_search_engine")


# ---------------------------------------------------------------------
# Cross-platform file opening
# ---------------------------------------------------------------------

def open_file(filepath: str) -> Optional[str]:
    """
    Open a file using the operating system's default application.

    Returns:
        None on success
        Error message on failure
    """

    path = Path(filepath)

    if not path.exists():
        return "That file no longer exists at its recorded location."

    try:
        system = platform.system()

        if system == "Windows":
            import os
            os.startfile(str(path))  # type: ignore[attr-defined]

        elif system == "Darwin":
            subprocess.run(
                ["open", str(path)],
                check=True
            )

        else:
            subprocess.run(
                ["xdg-open", str(path)],
                check=True
            )

        return None

    except FileNotFoundError:
        return "No default application handler was found for this file type."

    except (subprocess.CalledProcessError, OSError) as exc:
        logger.warning(
            "Failed to open file %s: %s",
            filepath,
            exc
        )

        return (
            "The file could not be opened automatically. "
            "Try opening it manually."
        )


# ---------------------------------------------------------------------
# Human-readable file size
# ---------------------------------------------------------------------

def format_size(num_bytes: float) -> str:
    """
    Convert bytes into a human-readable size.

    Example:
        1536 -> 1.5 KB
    """

    size = float(num_bytes)

    for unit in ("B", "KB", "MB", "GB", "TB"):

        if size < 1024 or unit == "TB":

            if unit == "B":
                return f"{int(size)} {unit}"

            return f"{size:.1f} {unit}"

        size /= 1024

    return f"{size:.1f} TB"


# ---------------------------------------------------------------------
# Human-readable duration
# ---------------------------------------------------------------------

def format_duration(seconds: float) -> str:
    """
    Convert seconds into a human-readable duration.

    Example:
        134.2 -> 2m 14s
    """

    seconds = int(round(seconds))

    minutes, secs = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)

    if hours:
        return f"{hours}h {minutes}m {secs}s"

    if minutes:
        return f"{minutes}m {secs}s"

    return f"{secs}s"


# ---------------------------------------------------------------------
# Optional extra scan directories
# ---------------------------------------------------------------------

def load_extra_directories() -> List[Path]:
    """
    Read optional extra directories from:

        ~/.local_search_engine/config.json

    Expected format:

        {
            "extra_directories": [
                "/some/path",
                "C:/some/other/path"
            ]
        }

    Invalid or missing configuration is treated as
    having no extra directories.
    """

    if not USER_CONFIG_PATH.exists():
        return []

    try:

        with open(
            USER_CONFIG_PATH,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        if not isinstance(data, dict):
            return []

        raw_dirs = data.get(
            "extra_directories",
            []
        )

        if not isinstance(raw_dirs, list):
            return []

        directories = []

        for directory in raw_dirs:

            if not isinstance(directory, str):
                continue

            path = Path(directory).expanduser()

            if path.exists() and path.is_dir():
                directories.append(path)

        return directories

    except (json.JSONDecodeError, OSError) as exc:

        logger.warning(
            "Could not read user config %s: %s",
            USER_CONFIG_PATH,
            exc
        )

        return []


# ---------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------

def setup_logging() -> None:
    """
    Configure application logging.
    """

    from utils.config import LOG_PATH

    logging.basicConfig(
        filename=str(LOG_PATH),
        level=logging.INFO,
        format=(
            "%(asctime)s "
            "[%(levelname)s] "
            "%(name)s: "
            "%(message)s"
        )
    )