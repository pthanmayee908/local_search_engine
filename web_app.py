"""
web_app.py
----------
Lightweight, zero-dependency HTTP server that connects the existing
Local Search Engine backend (controller.SearchEngineController) to a
static frontend (frontend/index.html, frontend/style.css,
frontend/script.js).

Standard library only: http.server, urllib.parse, json, webbrowser,
logging, threading, dataclasses, pathlib.

This file does NOT reimplement scanning, indexing, or search/ranking.
It only routes HTTP requests to SearchEngineController and serializes
its return values (dataclasses / SearchResult objects / dicts) to JSON.

--------------------------------------------------------------------
CONFIRMED BACKEND INTERFACE (from controller.py):

    from controller import SearchEngineController
    app_controller = SearchEngineController()   # uses DB_PATH by default

    app_controller.search(query: str, limit: int) -> List[SearchResult]
        SearchResult objects come from search.search_engine — exact
        attribute names aren't visible here, so results are read
        defensively (see _serialize_search_result below). If your
        SearchResult uses different field names than tried here,
        adjust only that one function.

    app_controller.get_statistics() -> dict
        {documents_indexed, unique_terms, database_size_bytes, last_run}

    app_controller.run_index() -> IndexRunSummary (dataclass)
        files_discovered, files_indexed, files_skipped, errors,
        duration_seconds

    app_controller.close()

Errors raised by the backend as IntegrationError are caught and turned
into {"success": false, "error": "..."} JSON, same as any other
unexpected exception.

The open_file(filepath) helper's location wasn't in the file you
shared — only the single import line marked below needs fixing if it
lives somewhere other than utils.file_opener / utils.
--------------------------------------------------------------------
"""

import json
import logging
import threading
import webbrowser
from dataclasses import asdict, is_dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

# --------------------------------------------------------------------
# Existing backend — DO NOT reimplement any of this logic here.
# --------------------------------------------------------------------
from controller import SearchEngineController, IntegrationError
from utils.config import DEFAULT_RESULT_LIMIT

try:
    from utils.file_opener import open_file
except ImportError:
    # Fallback if the helper actually lives directly under utils/.
    from utils import open_file  # noqa: F401


# --------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------
HOST = "127.0.0.1"
PORT = 8000
FRONTEND_DIR = Path(__file__).resolve().parent / "frontend"

STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
    "/script.js": ("script.js", "application/javascript; charset=utf-8"),
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("web_app")

# Single shared controller instance for the life of the server.
app_controller = SearchEngineController()


# --------------------------------------------------------------------
# Helpers to serialize backend objects to plain JSON-safe dicts
# --------------------------------------------------------------------
def _serialize_search_result(result) -> dict:
    """
    Convert one search.search_engine.SearchResult into the plain dict
    the frontend expects.

    Confirmed fields on SearchResult: document_id, filename, filepath,
    file_type, raw_score, relevance_pct, snippet. "score" sent to the
    frontend is relevance_pct (0-100, already normalized against the
    top result) since that's what the UI displays as e.g. "94.0%".
    raw_score is included too in case it's useful for debugging/judges.

    Note: snippet contains **term** markdown-style markers around
    matched words (added by SearchEngine.make_snippet) — script.js is
    responsible for turning those into <mark> highlighting, not this file.
    """
    return {
        "filename": result.filename,
        "filepath": result.filepath,
        "file_type": result.file_type,
        "score": round(result.relevance_pct, 1),
        "raw_score": round(result.raw_score, 4),
        "snippet": result.snippet,
    }


def _to_plain_dict(obj) -> dict:
    """Convert a dataclass (e.g. IndexRunSummary) or dict to a plain dict."""
    if is_dataclass(obj):
        return asdict(obj)
    if isinstance(obj, dict):
        return obj
    raise TypeError(f"Cannot serialize object of type {type(obj)!r}")


# --------------------------------------------------------------------
# Request handler
# --------------------------------------------------------------------
class SearchEngineRequestHandler(BaseHTTPRequestHandler):
    server_version = "LocalSearchEngine/1.0"

    def log_message(self, format, *args):
        logger.info("%s - %s", self.address_string(), format % args)

    # ------------------------------------------------------------------
    # Response helpers
    # ------------------------------------------------------------------
    def _send_json(self, status: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error_json(self, status: int, message: str):
        self._send_json(status, {"success": False, "error": message})

    def _send_static_file(self, filename: str, content_type: str):
        try:
            file_path = (FRONTEND_DIR / filename).resolve()
            frontend_root = FRONTEND_DIR.resolve()
            if frontend_root not in file_path.parents and file_path != frontend_root:
                raise FileNotFoundError
            data = file_path.read_bytes()
        except FileNotFoundError:
            self._send_error_json(404, f"Frontend file not found: {filename}")
            return
        except OSError as exc:
            self._send_error_json(500, f"Could not read frontend file: {exc}")
            return

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    # ------------------------------------------------------------------
    # GET routing
    # ------------------------------------------------------------------
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        try:
            if path in STATIC_FILES:
                filename, content_type = STATIC_FILES[path]
                self._send_static_file(filename, content_type)
                return

            if path == "/api/search":
                self._handle_search(query)
                return

            if path == "/api/statistics":
                self._handle_statistics()
                return

            if path == "/api/open":
                self._handle_open(query)
                return

            self._send_error_json(404, "Not found")

        except Exception as exc:  # noqa: BLE001 - never let a bad request kill the server
            logger.exception("Unhandled error while handling GET %s", path)
            self._send_error_json(500, f"Internal server error: {exc}")

    # ------------------------------------------------------------------
    # POST routing
    # ------------------------------------------------------------------
    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        try:
            if path == "/api/index":
                self._handle_run_index()
                return

            self._send_error_json(404, "Not found")

        except Exception as exc:  # noqa: BLE001
            logger.exception("Unhandled error while handling POST %s", path)
            self._send_error_json(500, f"Internal server error: {exc}")

    # ------------------------------------------------------------------
    # Endpoint implementations — thin wrappers around SearchEngineController
    # ------------------------------------------------------------------
    def _handle_search(self, query: dict):
        q_values = query.get("q", [])
        q = q_values[0].strip() if q_values else ""

        if not q:
            self._send_json(200, {"success": True, "results": []})
            return

        try:
            raw_results = app_controller.search(q, limit=DEFAULT_RESULT_LIMIT)
        except IntegrationError as exc:
            self._send_error_json(500, str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            logger.exception("Search failed for query=%r", q)
            self._send_error_json(500, f"Search failed: {exc}")
            return

        results = [_serialize_search_result(r) for r in raw_results]
        self._send_json(200, {"success": True, "results": results})

    def _handle_statistics(self):
        try:
            stats = app_controller.get_statistics()
        except Exception as exc:  # noqa: BLE001
            logger.exception("get_statistics failed")
            self._send_error_json(500, f"Could not load statistics: {exc}")
            return

        # stats is already the exact dict the backend returns —
        # nested under "statistics", matching the frontend's expected
        # response shape: {"success": true, "statistics": {...}}.
        self._send_json(200, {"success": True, "statistics": stats})

    def _handle_run_index(self):
        try:
            summary = app_controller.run_index()
        except IntegrationError as exc:
            self._send_error_json(500, str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            logger.exception("run_index failed")
            self._send_error_json(500, f"Indexing failed: {exc}")
            return

        payload = {"success": True, **_to_plain_dict(summary)}
        self._send_json(200, payload)

    def _handle_open(self, query: dict):
        path_values = query.get("path", [])
        filepath = path_values[0] if path_values else ""

        if not filepath:
            self._send_error_json(400, "Missing 'path' query parameter")
            return

        try:
            open_file(filepath)
        except Exception as exc:  # noqa: BLE001
            logger.exception("open_file failed for path=%r", filepath)
            self._send_error_json(500, f"Could not open file: {exc}")
            return

        self._send_json(200, {"success": True})


# --------------------------------------------------------------------
# Server bootstrap
# --------------------------------------------------------------------
def _open_browser_when_ready(url: str, delay_seconds: float = 0.75):
    threading.Timer(delay_seconds, webbrowser.open, args=(url,)).start()


def main():
    if not FRONTEND_DIR.exists():
        logger.warning(
            "Frontend directory not found at %s — static routes will 404 until it exists.",
            FRONTEND_DIR,
        )

    server = ThreadingHTTPServer((HOST, PORT), SearchEngineRequestHandler)
    url = f"http://{HOST}:{PORT}"

    logger.info("Local Search Engine running at %s", url)
    logger.info("Press Ctrl+C to stop.")

    _open_browser_when_ready(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        server.shutdown()
        server.server_close()
        app_controller.close()
        logger.info("Server stopped cleanly.")


if __name__ == "__main__":
    main()
