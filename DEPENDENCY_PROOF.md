# DEPENDENCY_PROOF.md

## Claim

**The Local Search Engine application has zero third-party runtime
dependencies.** Everything it does — file scanning, text extraction
(including `.docx`), tokenization, the inverted index, TF-IDF ranking,
the CLI, and the web UI backend and server — is implemented using only
the Python standard library and vanilla browser JavaScript/HTML/CSS.

This document explains *how that claim is verified*, not just asserted.

## Why "we didn't write a `requirements.txt` with anything in it" isn't proof enough

An empty `requirements.txt` only proves nobody declared a dependency —
it says nothing about whether the code actually imports one anyway
(e.g. a leftover `import requests` from a debugging session, or a
transitively-required package). A real proof has to look at what the
source code *actually imports* and check each one against what the
running interpreter considers "standard library."

## How the proof works

[`dependency_proof.py`](dependency_proof.py) is a small, **itself
dependency-free**, standalone script that:

1. **Walks the source tree** (every `.py` file in the project, except
   `tests/` — see "Why tests/ is excluded" below) without executing
   any of it.
2. **Parses each file with `ast`**, Python's built-in syntax-tree
   parser, and collects every `import x` / `from x import y`
   statement it finds. Nothing is imported or run — this is pure
   static analysis, so it can't miss a dependency because a code path
   wasn't exercised, and it can't be fooled by a conditionally-skipped
   test.
3. **Classifies every top-level module name** it found using the
   *running interpreter itself* — via `importlib.util.find_spec()` —
   rather than a hard-coded "list of known stdlib module names" that
   could go stale as Python versions change. Concretely, a module is
   classified as:
   - **LOCAL** — it's one of this project's own packages/modules
     (`scanner`, `indexer`, `search`, `storage`, `cli`, `utils`,
     `controller`, `web_app`, `main`), discovered dynamically by
     scanning the project's own top-level directories, or a relative
     import (`from . import x`).
   - **STDLIB** — it's a compiled-in builtin (`sys.builtin_module_names`),
     or `find_spec()` resolves it to a file that lives inside the
     interpreter's own standard-library directory
     (`sysconfig.get_paths()["stdlib"]` / `"platstdlib"`), confirmed
     against `sys.stdlib_module_names` on Python 3.10+ as a second
     check.
   - **THIRD_PARTY** — it resolves to anything under a
     `site-packages` / `dist-packages` directory (i.e. something
     installed with `pip`).
   - **UNRESOLVED** — the interpreter couldn't find the module at
     all. This is treated as a *failure*, the same as `THIRD_PARTY`,
     because an application that fails to import in a clean
     environment is exactly the kind of problem this proof exists to
     catch.
4. **Reports the result** and exits with status code `0` only if
   every single import resolved to `LOCAL` or `STDLIB`.

Because step 3 asks the interpreter itself, this proof is
**self-updating**: run it against Python 3.9, 3.11, or 3.13 and it
will correctly reclassify any module whose stdlib status changed
between versions (e.g. `distutils` was removed from the stdlib in
3.12) — no manual list to maintain.

### Why `tests/` is excluded from the main audit

`dependency_proof.py` audits the *shipped application* — the code a
user actually runs (`main.py`, `web_app.py`, everything under
`scanner/`, `indexer/`, `search/`, `storage/`, `cli/`, `utils/`, plus
`controller.py`). The test suite is a development-time tool, uses
`pytest` (a normal, declared dev dependency — see
`requirements-dev.txt`), and is never imported by or shipped with the
application. `tests/test_dependency_proof.py` separately verifies
this audit continues to pass as the codebase changes, so the guarantee
is enforced by CI, not just documented once.

## Run it yourself

```bash
python dependency_proof.py
```

Add `--verbose` to see exactly which files use each stdlib module, or
`--json report.json` to get a machine-readable report for CI:

```bash
python dependency_proof.py --verbose
python dependency_proof.py --json dependency_report.json
```

Exit code `0` = pass, `1` = fail (third-party or unresolved imports
found — details are printed).

## Sample output

The following is real, unedited output from running
`python dependency_proof.py --verbose` against this project:

```
========================================================================
LOCAL SEARCH ENGINE — DEPENDENCY PROOF
========================================================================
Python interpreter : /usr/bin/python3
Python version     : 3.12.3

Local project modules  (8): cli, controller, indexer, scanner, search, storage, utils, web_app

Standard library modules used (22):
  - csv                  used in: scanner/scanner.py
  - dataclasses          used in: controller.py, indexer/indexer.py, search/search_engine.py, web_app.py
  - datetime             used in: cli/interface.py, controller.py
  - html                 used in: scanner/scanner.py
  - http                 used in: web_app.py
  - json                 used in: scanner/scanner.py, utils/helpers.py, web_app.py
  - logging              used in: controller.py, utils/helpers.py, web_app.py
  - math                 used in: search/search_engine.py
  - os                   used in: indexer/indexer.py, scanner/scanner.py, utils/helpers.py
  - pathlib              used in: controller.py, scanner/scanner.py, storage/database.py, utils/config.py, utils/helpers.py, web_app.py
  - platform             used in: utils/helpers.py
  - re                   used in: indexer/indexer.py, scanner/scanner.py, search/search_engine.py
  - sqlite3              used in: indexer/indexer.py, storage/database.py
  - subprocess           used in: utils/helpers.py
  - sys                  used in: main.py
  - threading            used in: web_app.py
  - time                 used in: controller.py, storage/database.py, web_app.py
  - typing               used in: cli/interface.py, controller.py, indexer/indexer.py, scanner/scanner.py, search/search_engine.py, storage/database.py, utils/helpers.py
  - urllib               used in: web_app.py
  - webbrowser           used in: web_app.py
  - xml                  used in: scanner/scanner.py
  - zipfile              used in: scanner/scanner.py

Third-party modules found (0): none

========================================================================
RESULT: PASS — zero third-party runtime dependencies detected.
========================================================================
```

See [STDLIB.md](STDLIB.md) for a human-annotated version of this same
table explaining *why* each module is used.

## Enforcing this in CI

`tests/test_dependency_proof.py` runs this same audit as part of the
normal `pytest` test suite (both by calling `dependency_proof.py`'s
functions directly and by invoking the script as a subprocess), so any
pull request that introduces a third-party import will fail CI
automatically:

```bash
pytest tests/test_dependency_proof.py -v
```
