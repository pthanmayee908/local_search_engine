from pathlib import Path

APP_DIR = Path.home() / ".local_search_engine"
APP_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = APP_DIR / "search_index.db"
LOG_PATH = APP_DIR / "app.log"

USER_CONFIG_PATH = APP_DIR / "config.json"

DEFAULT_RESULT_LIMIT = 10
PROGRESS_INTERVAL = 25