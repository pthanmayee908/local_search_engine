"""
web_app.py
----------
Web interface for the Local Search Engine.

Architecture:

    Browser
       |
       v
    web_app.py
       |
       v
    SearchEngineController
       |
       +--> Scanner
       +--> Indexer
       +--> SearchEngine
       +--> Storage

The web layer does NOT implement searching, indexing,
TF-IDF, tokenization, or scanning itself.

Standard library only.
"""

import json
import logging
import threading
import time
import webbrowser

from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from controller import SearchEngineController, IntegrationError
from utils.config import DEFAULT_RESULT_LIMIT
from utils.helpers import open_file, setup_logging


# ==============================================================
# CONFIGURATION
# ==============================================================

HOST = "127.0.0.1"
PORT = 8765

BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"

logger = logging.getLogger("local_search_engine.web")


# ==============================================================
# SHARED STATE
# ==============================================================

state_lock = threading.RLock()

indexing_state = {
    "is_indexing": False,
    "index_message": "Ready",
    "started_at": None,
    "last_summary": None,
    "error": None,
}


# Only one indexing operation may run at a time.
index_lock = threading.Lock()

# Controller operations are coordinated so search/statistics
# don't collide with the background indexing operation.
controller_lock = threading.RLock()


# ==============================================================
# HELPERS
# ==============================================================

def get_state():
    """Return a safe copy of the current indexing state."""

    with state_lock:
        return {
            "is_indexing": indexing_state["is_indexing"],
            "index_message": indexing_state["index_message"],
            "started_at": indexing_state["started_at"],
            "last_summary": indexing_state["last_summary"],
            "error": indexing_state["error"],
        }


def set_index_state(**updates):
    """Update shared indexing state safely."""

    with state_lock:
        indexing_state.update(updates)


def json_response(handler, data, status=200):
    """Send a JSON response."""

    payload = json.dumps(
        data,
        ensure_ascii=False
    ).encode("utf-8")

    handler.send_response(status)
    handler.send_header(
        "Content-Type",
        "application/json; charset=utf-8"
    )
    handler.send_header(
        "Content-Length",
        str(len(payload))
    )
    handler.send_header(
        "Cache-Control",
        "no-store"
    )
    handler.end_headers()

    handler.wfile.write(payload)


def text_response(
    handler,
    content,
    content_type="text/plain; charset=utf-8",
    status=200
):
    """Send a text/static response."""

    payload = content.encode("utf-8")

    handler.send_response(status)
    handler.send_header(
        "Content-Type",
        content_type
    )
    handler.send_header(
        "Content-Length",
        str(len(payload))
    )
    handler.send_header(
        "Cache-Control",
        "no-cache"
    )
    handler.end_headers()

    handler.wfile.write(payload)


def read_json_body(handler):
    """Read and decode a JSON request body."""

    try:
        length = int(
            handler.headers.get(
                "Content-Length",
                "0"
            )
        )
    except ValueError:
        return None

    if length <= 0:
        return None

    try:
        raw = handler.rfile.read(length)
        return json.loads(
            raw.decode("utf-8")
        )
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


# ==============================================================
# INDEXING
# ==============================================================

def run_background_index():
    """
    Perform indexing in a dedicated controller/thread.

    IMPORTANT:
    Indexer uses SQLite connections. The controller is therefore
    created inside this worker thread instead of sharing the
    request thread's SQLite connection.
    """

    if not index_lock.acquire(blocking=False):
        return

    controller = None

    try:
        set_index_state(
            is_indexing=True,
            index_message="Preparing file scan...",
            started_at=time.time(),
            error=None,
            last_summary=None,
        )

        controller = SearchEngineController()

        def progress(discovered, indexed, errors):
            set_index_state(
                is_indexing=True,
                index_message=(
                    f"Scanning files... "
                    f"{discovered:,} discovered • "
                    f"{indexed:,} ready • "
                    f"{errors:,} errors"
                ),
            )

        set_index_state(
            index_message="Scanning your accessible files..."
        )

        with controller_lock:
            summary = controller.run_index(
                progress_callback=progress
            )

        set_index_state(
            is_indexing=False,
            index_message=(
                f"Index updated — "
                f"{summary.files_indexed:,} files indexed"
            ),
            last_summary=asdict(summary),
            error=None,
        )

        logger.info(
            "Web indexing completed: %s",
            summary
        )

    except IntegrationError as exc:

        logger.exception(
            "Web indexing integration error"
        )

        set_index_state(
            is_indexing=False,
            index_message="Indexing failed",
            error=str(exc),
        )

    except Exception as exc:

        logger.exception(
            "Unexpected web indexing error"
        )

        set_index_state(
            is_indexing=False,
            index_message="Indexing failed",
            error="The indexing operation could not be completed.",
        )

    finally:

        if controller is not None:
            try:
                controller.close()
            except Exception:
                logger.exception(
                    "Error closing indexing controller"
                )

        set_index_state(
            is_indexing=False
        )

        index_lock.release()


def start_indexing():
    """Start indexing if it is not already running."""

    with state_lock:
        if indexing_state["is_indexing"]:
            return False

        indexing_state["is_indexing"] = True
        indexing_state["index_message"] = (
            "Starting file scan..."
        )
        indexing_state["started_at"] = time.time()
        indexing_state["error"] = None

    thread = threading.Thread(
        target=run_background_index,
        name="LocalSearchIndexer",
        daemon=True,
    )

    thread.start()

    return True


# ==============================================================
# HTTP HANDLER
# ==============================================================

class SearchRequestHandler(BaseHTTPRequestHandler):
    """HTTP handler for the Local Search Engine web UI."""

    server_version = "LocalSearchEngine/1.0"

    # ----------------------------------------------------------
    # Logging
    # ----------------------------------------------------------

    def log_message(self, format_string, *args):
        logger.info(
            "%s - %s",
            self.address_string(),
            format_string % args
        )

    # ----------------------------------------------------------
    # GET
    # ----------------------------------------------------------

    def do_GET(self):

        parsed = urlparse(self.path)

        path = parsed.path

        try:

            if path == "/":
                return self.serve_file(
                    WEB_DIR / "index.html",
                    "text/html; charset=utf-8"
                )

            if path == "/style.css":
                return self.serve_file(
                    WEB_DIR / "style.css",
                    "text/css; charset=utf-8"
                )

            if path == "/app.js":
                return self.serve_file(
                    WEB_DIR / "app.js",
                    "application/javascript; charset=utf-8"
                )

            if path == "/api/search":
                return self.handle_search(
                    parse_qs(parsed.query)
                )

            if path == "/api/stats":
                return self.handle_stats()

            if path == "/favicon.ico":
                self.send_response(204)
                self.end_headers()
                return

            json_response(
                self,
                {
                    "error": "Page not found."
                },
                status=404
            )

        except Exception:

            logger.exception(
                "GET request failed: %s",
                self.path
            )

            json_response(
                self,
                {
                    "error": "An unexpected server error occurred."
                },
                status=500
            )

    # ----------------------------------------------------------
    # POST
    # ----------------------------------------------------------

    def do_POST(self):

        parsed = urlparse(self.path)

        try:

            if parsed.path == "/api/index":
                return self.handle_index()

            if parsed.path == "/api/open":
                return self.handle_open()

            json_response(
                self,
                {
                    "error": "Endpoint not found."
                },
                status=404
            )

        except Exception:

            logger.exception(
                "POST request failed: %s",
                self.path
            )

            json_response(
                self,
                {
                    "error": "An unexpected server error occurred."
                },
                status=500
            )

    # ==========================================================
    # STATIC FILES
    # ==========================================================

    def serve_file(
        self,
        filepath,
        content_type
    ):

        filepath = Path(filepath)

        if not filepath.exists():
            return text_response(
                self,
                "File not found.",
                status=404
            )

        try:
            content = filepath.read_text(
                encoding="utf-8"
            )

        except OSError:

            return text_response(
                self,
                "Could not read requested file.",
                status=500
            )

        text_response(
            self,
            content,
            content_type=content_type
        )

    # ==========================================================
    # SEARCH
    # ==========================================================

    def handle_search(self, params):

        query_values = params.get("q", [""])
        filter_values = params.get("type", ["all"])

        query = query_values[0].strip()
        file_filter = filter_values[0].lower().strip()

        if not query:
            return json_response(
                self,
                {
                    "results": [],
                    "query": "",
                }
            )

        valid_filters = {
            "all",
            ".txt",
            ".py",
            ".md",
            ".csv",
            ".json",
            ".html",
            ".htm",
            ".xml",
            ".log",
            ".docx",
        }

        if file_filter not in valid_filters:
            file_filter = "all"

        # Ask backend for enough results so a file-type filter
        # does not accidentally hide valid matches.
        backend_limit = max(
            DEFAULT_RESULT_LIMIT,
            50
        )

        with controller_lock:

            controller = SearchEngineController()

            try:

                if controller.document_count() == 0:
                    return json_response(
                        self,
                        {
                            "results": [],
                            "query": query,
                            "index_empty": True,
                            "indexing": get_state()["is_indexing"],
                        }
                    )

                results = controller.search(
                    query,
                    limit=backend_limit
                )

                output = []

                for result in results:

                    if (
                        file_filter != "all"
                        and result.file_type.lower()
                        != file_filter
                    ):
                        continue

                    item = {
                        "document_id": result.document_id,
                        "filename": result.filename,
                        "filepath": result.filepath,
                        "file_type": result.file_type,
                        "raw_score": result.raw_score,
                        "relevance": round(
                            result.relevance_pct,
                            1
                        ),
                        "snippet": result.snippet or "",
                    }

                    # File size is obtained safely from the
                    # actual file. If it disappeared, show 0 B.
                    try:
                        item["size_bytes"] = Path(
                            result.filepath
                        ).stat().st_size
                    except OSError:
                        item["size_bytes"] = 0

                    output.append(item)

                # Limit AFTER filtering.
                output = output[:DEFAULT_RESULT_LIMIT]

                return json_response(
                    self,
                    {
                        "results": output,
                        "query": query,
                        "index_empty": False,
                        "indexing": get_state()["is_indexing"],
                    }
                )

            finally:

                controller.close()

    # ==========================================================
    # STATISTICS
    # ==========================================================

    def handle_stats(self):

        current_state = get_state()

        with controller_lock:

            controller = SearchEngineController()

            try:

                stats = controller.get_statistics()

            finally:

                controller.close()

        last_run = stats.get("last_run")

        database_size = stats.get(
            "database_size_bytes",
            0
        )

        # Human-readable database size.
        if database_size < 1024:
            readable_size = f"{database_size} B"

        elif database_size < 1024 * 1024:
            readable_size = (
                f"{database_size / 1024:.1f} KB"
            )

        elif database_size < 1024 * 1024 * 1024:
            readable_size = (
                f"{database_size / (1024 * 1024):.1f} MB"
            )

        else:
            readable_size = (
                f"{database_size / (1024 * 1024 * 1024):.1f} GB"
            )

        response = {
            "documents_indexed": int(
                stats.get(
                    "documents_indexed",
                    0
                )
            ),
            "unique_terms": int(
                stats.get(
                    "unique_terms",
                    0
                )
            ),
            "database_size": readable_size,
            "database_size_bytes": database_size,
            "is_indexing": current_state[
                "is_indexing"
            ],
            "index_message": current_state[
                "index_message"
            ],
            "index_error": current_state[
                "error"
            ],
            "last_run": last_run,
        }

        return json_response(
            self,
            response
        )

    # ==========================================================
    # START INDEXING
    # ==========================================================

    def handle_index(self):

        if get_state()["is_indexing"]:

            return json_response(
                self,
                {
                    "status": "already_running",
                    "message": (
                        "Indexing is already running."
                    )
                }
            )

        started = start_indexing()

        if not started:

            return json_response(
                self,
                {
                    "status": "already_running",
                    "message": (
                        "Indexing is already running."
                    )
                }
            )

        return json_response(
            self,
            {
                "status": "started",
                "message": (
                    "Indexing started in background."
                )
            }
        )

    # ==========================================================
    # OPEN FILE
    # ==========================================================

    def handle_open(self):

        body = read_json_body(self)

        if not isinstance(body, dict):

            return json_response(
                self,
                {
                    "error": "Invalid request."
                },
                status=400
            )

        filepath = body.get("filepath")

        if not isinstance(filepath, str):
            return json_response(
                self,
                {
                    "error": "No valid file path was supplied."
                },
                status=400
            )

        filepath = filepath.strip()

        if not filepath:
            return json_response(
                self,
                {
                    "error": "No file path was supplied."
                },
                status=400
            )

        path = Path(filepath)

        if not path.exists():

            return json_response(
                self,
                {
                    "error": (
                        "That file no longer exists."
                    )
                },
                status=404
            )

        if not path.is_file():

            return json_response(
                self,
                {
                    "error": (
                        "The selected path is not a file."
                    )
                },
                status=400
            )

        error = open_file(
            str(path)
        )

        if error:

            return json_response(
                self,
                {
                    "error": error
                },
                status=500
            )

        return json_response(
            self,
            {
                "status": "opened"
            }
        )


# ==============================================================
# SERVER
# ==============================================================

def create_server():
    """Create the HTTP server."""

    WEB_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    server = ThreadingHTTPServer(
        (HOST, PORT),
        SearchRequestHandler
    )

    return server


def start_web_app(open_browser=True):
    """Start the Local Search Engine web interface."""

    setup_logging()

    server = create_server()

    url = f"http://{HOST}:{PORT}/"

    print()
    print("=" * 72)
    print("LOCAL SEARCH ENGINE — WEB INTERFACE")
    print("=" * 72)
    print()
    print(f"Open: {url}")
    print()
    print("Press Ctrl+C to stop the server.")
    print()

    logger.info(
        "Web interface started at %s",
        url
    )

    if open_browser:

        threading.Timer(
            0.8,
            lambda: webbrowser.open(url)
        ).start()

    try:
        server.serve_forever()

    except KeyboardInterrupt:

        print("\nStopping web server...")

    finally:

        server.server_close()

        logger.info(
            "Web interface stopped"
        )


if __name__ == "__main__":
    start_web_app()