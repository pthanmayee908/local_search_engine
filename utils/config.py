"""
config.py
---------
Centralized configuration for the Local Search Engine.

No personal or machine-specific paths are hard-coded here. Everything
is derived at runtime from the current user's home directory, so the
application works unmodified on any machine (Windows, macOS, Linux).
"""

from pathlib import Path

# ---------------------------------------------------------------------
# Application data directory (holds the SQLite index + logs).
# Lives under the current user's home folder, e.g.:
#   Linux/macOS: ~/.local_search_engine/
#   Windows:     C:\Users\<name>\.local_search_engine\
# ---------------------------------------------------------------------
APP_DIR: Path = Path.home() / ".local_search_engine"
APP_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH: Path = APP_DIR / "search_index.db"
LOG_PATH: Path = APP_DIR / "app.log"

# Optional user-editable config file (JSON) letting the user add extra
# directories to scan beyond the defaults Member 1's scanner picks up
# (Desktop/Documents/Downloads/Pictures/Music/Videos/OneDrive/home).
USER_CONFIG_PATH: Path = APP_DIR / "config.json"

# Default search result limit shown in the CLI.
DEFAULT_RESULT_LIMIT = 10

# How many files to scan before printing a progress update.
PROGRESS_INTERVAL = 25
