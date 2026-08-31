# BUILD.md

Build, run, and packaging instructions for the Local Search Engine
("FloraFind").

## Requirements

- **Python 3.8 or newer** (developed/tested against 3.12). No other
  runtime software is required — see [DEPENDENCY_PROOF.md](DEPENDENCY_PROOF.md).
- A desktop OS with a default web browser, if you plan to use the web
  UI (it auto-opens one, but works with any browser pointed at the
  right URL).
- No database server, no Node.js, no build toolchain, and no `pip
  install` step are needed to run the application.

## 1. Get the source

```bash
# however you obtained it — e.g.:
unzip LSEngine.zip
cd LSEngine
```

There is no compilation or build step — this is a pure-Python
application plus a static HTML/CSS/JS frontend served directly by the
Python standard library's `http.server`. "Building" it just means
having a Python interpreter available.

## 2. (Optional) Create a virtual environment

Not required for running the app (there's nothing to install into
it), but recommended if you also want to run the test suite, to keep
`pytest` out of your system Python:

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
```

## 3. Install dependencies

```bash
pip install -r requirements.txt
```

This installs nothing (see `requirements.txt`) but is included as a
standard, expected step. If you want to run the tests, also run:

```bash
pip install -r requirements-dev.txt
```

## 4. Run the application

### Web UI (default)

```bash
python main.py
```

This starts a local web server at `http://127.0.0.1:8765/` and opens
it in your default browser automatically. Stop it with `Ctrl+C`.

The first thing to do in the UI is click **Index / Scan Files** (or
call `POST /api/index`) — search returns nothing until an index
exists.

### Command-line interface

```bash
python main.py --cli
```

This launches an interactive terminal menu (index, search, view
statistics).

## 5. Where data is stored

On first run, the application creates:

```
~/.local_search_engine/
├── search_index.db   # SQLite database: the inverted index + document store
├── app.log            # application log
└── config.json         # optional: user-added extra scan directories (see below)
```

Nothing is written anywhere else on disk, and no data leaves your
machine — the web UI only binds to `127.0.0.1` (localhost), never a
public interface.

### Adding extra directories to scan

By default the scanner indexes your home directory. To add more
locations, create `~/.local_search_engine/config.json`:

```json
{
  "extra_directories": [
    "/path/to/another/folder"
  ]
}
```

Non-existent paths are silently ignored; invalid JSON falls back to
"no extra directories" rather than crashing.

## 6. Running the test suite

```bash
pip install -r requirements-dev.txt
pytest
```

For a coverage-style verbose run, or to run just one area:

```bash
pytest -v
pytest tests/test_search_engine.py -v
pytest tests/test_dependency_proof.py -v   # verifies zero third-party deps
```

The test suite never touches your real home directory's search index
— every test that needs a database or scanned files uses pytest's
`tmp_path` fixture.

## 7. Verifying the zero-dependency claim yourself

```bash
python dependency_proof.py --verbose
```

Exit code `0` means the audit passed. See
[DEPENDENCY_PROOF.md](DEPENDENCY_PROOF.md) for exactly how this
works and what it checks.

## 8. Packaging for distribution (optional)

Since there's nothing to compile, "packaging" is optional and only
useful if you want a single-file executable for users without Python
installed. Using [PyInstaller](https://pyinstaller.org/) (a
build-time tool only, not a runtime dependency of the app itself):

```bash
pip install pyinstaller
pyinstaller --onefile --add-data "web:web" main.py
```

This is entirely optional — the project runs directly with `python
main.py` on any machine with Python 3.8+, with no packaging step
required.

## Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| `Address already in use` on startup | Something else is using port 8765. Stop it, or edit `HOST`/`PORT` in `web_app.py`. |
| Search returns nothing | You haven't indexed yet — run **Index / Scan Files** first (CLI option 1, or the web UI's index button). |
| `.docx` files show no content | The file may not be a real OOXML `.docx` (e.g. a renamed `.doc`), or it has no readable `word/document.xml`; extraction fails safely and returns empty text rather than raising. |
| Nothing indexed at all | Check `~/.local_search_engine/app.log` — indexing swallows per-file errors so one bad file won't stop a whole run, but they're logged. |
