#!/usr/bin/env python3
"""
dependency_proof.py
--------------------
Standalone, dependency-free verification tool for the Local Search
Engine ("BlossomSearch / FloraFind") project.

WHAT THIS SCRIPT DOES
======================
It walks every first-party ``.py`` source file in the project, parses
each one with the ``ast`` module (no execution, no imports of project
code required), collects every module named in an ``import`` or
``from ... import`` statement, and classifies each one as:

    LOCAL       - a module that is part of this project
    STDLIB      - a module that ships with the Python standard library
    THIRD_PARTY - anything else (would indicate an external dependency)

The classification does NOT rely on a hard-coded list of "known
stdlib module names" that could go stale. Instead it asks the
*running* Python interpreter to resolve each module (via
``importlib.util.find_spec``) and inspects where that module actually
lives on disk (or whether it is a compiled-in / frozen module),
comparing that location against ``sysconfig``'s reported standard
library directory. That is the same mechanism Python itself uses to
find modules, so the result is authoritative for whatever interpreter
you run this with.

The script exits with status code ``0`` and prints "PASS" when zero
third-party imports are found anywhere in the project, and exits with
status code ``1`` and prints "FAIL" (naming the offending imports)
otherwise.

USAGE
=====
    python dependency_proof.py
    python dependency_proof.py --verbose
    python dependency_proof.py --json report.json
    python dependency_proof.py --root /path/to/LSEngine

This script itself only imports the standard library, so running it
never requires ``pip install`` anything.
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import sys
import sysconfig
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set


# ==============================================================
# PROJECT-LOCAL PACKAGES / MODULES
# ==============================================================
# These names are part of THIS project, not third-party libraries.
# They are discovered dynamically below (any top-level directory
# containing an __init__.py, plus any top-level .py file), but the
# fallback set below documents them explicitly for readability.

KNOWN_LOCAL_MODULES = {
    "main",
    "controller",
    "web_app",
    "scanner",
    "indexer",
    "search",
    "storage",
    "cli",
    "utils",
    "tests",
    "dependency_proof",
}

# Directories that are never part of the shipped source tree.
EXCLUDED_DIR_NAMES = {
    "__pycache__",
    ".git",
    ".venv",
    "venv",
    "env",
    "build",
    "dist",
    ".pytest_cache",
    ".mypy_cache",
    "node_modules",
}


# ==============================================================
# DATA MODEL
# ==============================================================

@dataclass
class ImportSite:
    """One import statement found in the source tree."""

    module: str          # top-level module name, e.g. "os" from "os.path"
    full_name: str        # the exact dotted name as written, e.g. "os.path"
    file: str              # file it was found in (relative path)
    lineno: int


@dataclass
class ClassificationResult:
    module: str
    kind: str              # "LOCAL" | "STDLIB" | "THIRD_PARTY" | "UNRESOLVED"
    reason: str
    sites: List[ImportSite] = field(default_factory=list)


# ==============================================================
# SOURCE DISCOVERY
# ==============================================================

def discover_python_files(root: Path) -> List[Path]:
    """Return every first-party .py file under ``root``.

    ``tests/`` and this script itself are excluded from the audited
    set because the point of this tool is to prove the *shipped
    application* has zero third-party runtime dependencies; the test
    suite is a development-time concern and is audited separately by
    ``tests/test_dependency_proof.py``.
    """

    files: List[Path] = []

    for path in sorted(root.rglob("*.py")):

        if path.name == "dependency_proof.py":
            continue

        relative_parts = path.relative_to(root).parts

        if any(part in EXCLUDED_DIR_NAMES for part in relative_parts):
            continue

        if "tests" in relative_parts:
            continue

        files.append(path)

    return files


# ==============================================================
# IMPORT EXTRACTION (AST — no code execution)
# ==============================================================

def extract_imports(file_path: Path, root: Path) -> List[ImportSite]:
    """Parse a single file with ``ast`` and list its imports."""

    source = file_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(file_path))

    relative = str(file_path.relative_to(root))
    sites: List[ImportSite] = []

    for node in ast.walk(tree):

        if isinstance(node, ast.Import):
            for alias in node.names:
                top_level = alias.name.split(".")[0]
                sites.append(
                    ImportSite(
                        module=top_level,
                        full_name=alias.name,
                        file=relative,
                        lineno=node.lineno,
                    )
                )

        elif isinstance(node, ast.ImportFrom):

            # Relative imports (e.g. "from . import x") reference
            # local project code by definition.
            if node.level and node.level > 0:
                sites.append(
                    ImportSite(
                        module="." * node.level + (node.module or ""),
                        full_name="." * node.level + (node.module or ""),
                        file=relative,
                        lineno=node.lineno,
                    )
                )
                continue

            if node.module:
                top_level = node.module.split(".")[0]
                sites.append(
                    ImportSite(
                        module=top_level,
                        full_name=node.module,
                        file=relative,
                        lineno=node.lineno,
                    )
                )

    return sites


# ==============================================================
# CLASSIFICATION
# ==============================================================

def _stdlib_dirs() -> Set[str]:
    """Directories the running interpreter considers 'standard library'."""

    candidates = set()

    paths = sysconfig.get_paths()

    for key in ("stdlib", "platstdlib"):
        value = paths.get(key)
        if value:
            candidates.add(str(Path(value).resolve()))

    return candidates


def classify_module(name: str, local_names: Set[str]) -> ClassificationResult:
    """Decide whether ``name`` is LOCAL, STDLIB, THIRD_PARTY, or UNRESOLVED."""

    # ----------------------------------------------------------
    # Relative imports and known local packages/modules.
    # ----------------------------------------------------------
    if name.startswith("."):
        return ClassificationResult(name, "LOCAL", "relative import")

    if name in local_names:
        return ClassificationResult(name, "LOCAL", "matches a project module/package")

    # ----------------------------------------------------------
    # Built-in / frozen modules compiled directly into the
    # interpreter (e.g. "sys", "builtins", "_thread") are always
    # standard library, and have no importable file on disk.
    # ----------------------------------------------------------
    if name in sys.builtin_module_names:
        return ClassificationResult(name, "STDLIB", "compiled-in builtin module")

    # ----------------------------------------------------------
    # Ask the interpreter to resolve the module the same way an
    # `import` statement would, without actually importing it.
    # ----------------------------------------------------------
    try:
        spec = importlib.util.find_spec(name)
    except (ImportError, ValueError, ModuleNotFoundError):
        spec = None
    except Exception as exc:  # pragma: no cover - defensive
        return ClassificationResult(
            name, "UNRESOLVED", f"error while resolving module: {exc}"
        )

    if spec is None:
        return ClassificationResult(
            name, "UNRESOLVED", "module could not be found by the interpreter"
        )

    # A namespace/frozen/builtin module with no file origin but a
    # resolvable spec (e.g. some "_frozen_importlib" internals) is
    # standard library by construction.
    if spec.origin in (None, "built-in", "frozen"):
        return ClassificationResult(name, "STDLIB", f"builtin/frozen module (origin={spec.origin!r})")

    origin_path = str(Path(spec.origin).resolve())

    if "site-packages" in origin_path or "dist-packages" in origin_path:
        return ClassificationResult(
            name, "THIRD_PARTY", f"installed under a site-packages location: {origin_path}"
        )

    for stdlib_dir in _stdlib_dirs():
        if origin_path.startswith(stdlib_dir):
            return ClassificationResult(
                name, "STDLIB", f"resolved inside interpreter stdlib dir: {stdlib_dir}"
            )

    # Fall back to Python 3.10+'s explicit stdlib name list, if present.
    stdlib_names = getattr(sys, "stdlib_module_names", None)
    if stdlib_names and name in stdlib_names:
        return ClassificationResult(name, "STDLIB", "listed in sys.stdlib_module_names")

    return ClassificationResult(
        name, "THIRD_PARTY", f"origin outside known stdlib directories: {origin_path}"
    )


# ==============================================================
# MAIN AUDIT
# ==============================================================

def discover_local_module_names(root: Path) -> Set[str]:
    """Find top-level package/module names that belong to this project."""

    names = set(KNOWN_LOCAL_MODULES)

    for entry in root.iterdir():

        if entry.name in EXCLUDED_DIR_NAMES:
            continue

        if entry.is_dir() and (entry / "__init__.py").exists():
            names.add(entry.name)

        elif entry.is_file() and entry.suffix == ".py":
            names.add(entry.stem)

    return names


def run_audit(root: Path, verbose: bool = False) -> Dict[str, ClassificationResult]:
    """Run the full audit and return module_name -> ClassificationResult."""

    local_names = discover_local_module_names(root)
    files = discover_python_files(root)

    all_sites: List[ImportSite] = []
    for file_path in files:
        all_sites.extend(extract_imports(file_path, root))

    grouped: Dict[str, ClassificationResult] = {}

    for site in all_sites:
        if site.module not in grouped:
            grouped[site.module] = classify_module(site.module, local_names)
        grouped[site.module].sites.append(site)

    return grouped


def print_report(results: Dict[str, ClassificationResult], verbose: bool) -> bool:
    """Print a human-readable report. Returns True if the audit passed."""

    stdlib_mods = sorted(m for m, r in results.items() if r.kind == "STDLIB")
    local_mods = sorted(m for m, r in results.items() if r.kind == "LOCAL")
    third_party_mods = sorted(m for m, r in results.items() if r.kind == "THIRD_PARTY")
    unresolved_mods = sorted(m for m, r in results.items() if r.kind == "UNRESOLVED")

    print("=" * 72)
    print("LOCAL SEARCH ENGINE — DEPENDENCY PROOF")
    print("=" * 72)
    print(f"Python interpreter : {sys.executable}")
    print(f"Python version     : {sys.version.split()[0]}")
    print()

    print(f"Local project modules  ({len(local_mods)}): {', '.join(local_mods)}")
    print()
    print(f"Standard library modules used ({len(stdlib_mods)}):")
    for name in stdlib_mods:
        sites = results[name].sites
        locations = ", ".join(sorted({s.file for s in sites}))
        if verbose:
            print(f"  - {name:<20} used in: {locations}")
        else:
            print(f"  - {name}")

    print()

    if third_party_mods:
        print(f"THIRD-PARTY modules found ({len(third_party_mods)}):")
        for name in third_party_mods:
            result = results[name]
            print(f"  ! {name}: {result.reason}")
            for site in result.sites:
                print(f"      {site.file}:{site.lineno}  ({site.full_name})")
    else:
        print("Third-party modules found (0): none")

    if unresolved_mods:
        print()
        print(f"UNRESOLVED modules ({len(unresolved_mods)}) — could not classify:")
        for name in unresolved_mods:
            result = results[name]
            print(f"  ? {name}: {result.reason}")

    print()
    print("=" * 72)

    passed = not third_party_mods and not unresolved_mods

    if passed:
        print("RESULT: PASS — zero third-party runtime dependencies detected.")
    else:
        print("RESULT: FAIL — see THIRD_PARTY / UNRESOLVED modules above.")

    print("=" * 72)

    return passed


def results_to_json(results: Dict[str, ClassificationResult]) -> dict:
    return {
        "python_version": sys.version,
        "modules": {
            name: {
                "kind": result.kind,
                "reason": result.reason,
                "used_in": sorted(
                    {f"{s.file}:{s.lineno}" for s in result.sites}
                ),
            }
            for name, result in sorted(results.items())
        },
        "summary": {
            "local": sorted(m for m, r in results.items() if r.kind == "LOCAL"),
            "stdlib": sorted(m for m, r in results.items() if r.kind == "STDLIB"),
            "third_party": sorted(m for m, r in results.items() if r.kind == "THIRD_PARTY"),
            "unresolved": sorted(m for m, r in results.items() if r.kind == "UNRESOLVED"),
        },
    }


def main(argv: Optional[List[str]] = None) -> int:

    parser = argparse.ArgumentParser(
        description="Prove the Local Search Engine has zero third-party runtime dependencies."
    )

    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="Project root to audit (default: this script's directory).",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show which files each stdlib module is used in.",
    )

    parser.add_argument(
        "--json",
        type=Path,
        default=None,
        help="Also write a machine-readable JSON report to this path.",
    )

    args = parser.parse_args(argv)

    results = run_audit(args.root, verbose=args.verbose)
    passed = print_report(results, verbose=args.verbose)

    if args.json:
        args.json.write_text(
            json.dumps(results_to_json(results), indent=2),
            encoding="utf-8",
        )
        print(f"\nJSON report written to: {args.json}")

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
