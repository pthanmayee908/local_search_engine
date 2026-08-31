"""
test_dependency_proof.py
-------------------------
Exercises dependency_proof.py's own logic, and asserts that the
application source tree (everything dependency_proof.py audits,
i.e. excluding tests/) is, in fact, free of third-party runtime
dependencies. This is what CI should run to keep that guarantee
enforced automatically rather than just documented.
"""

import subprocess
import sys
from pathlib import Path

import dependency_proof as dp

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_project_audit_has_no_third_party_modules():
    results = dp.run_audit(PROJECT_ROOT)
    third_party = {name: r for name, r in results.items() if r.kind == "THIRD_PARTY"}
    assert third_party == {}, f"Unexpected third-party imports: {third_party}"


def test_project_audit_has_no_unresolved_modules():
    results = dp.run_audit(PROJECT_ROOT)
    unresolved = {name: r for name, r in results.items() if r.kind == "UNRESOLVED"}
    assert unresolved == {}, f"Unresolved imports: {unresolved}"


def test_project_audit_finds_the_expected_local_packages():
    results = dp.run_audit(PROJECT_ROOT)
    local = {name for name, r in results.items() if r.kind == "LOCAL"}
    assert {"scanner", "indexer", "search", "storage", "utils"}.issubset(local)


def test_project_audit_finds_stdlib_modules_actually_used():
    results = dp.run_audit(PROJECT_ROOT)
    stdlib = {name for name, r in results.items() if r.kind == "STDLIB"}
    # A representative sample of modules the project is known to use.
    for expected in {"sqlite3", "json", "pathlib", "re", "zipfile"}:
        assert expected in stdlib


def test_classify_module_flags_a_real_third_party_package():
    # `pytest` is installed as a dev dependency in this environment,
    # so it is a genuine, verifiable example of a THIRD_PARTY module
    # (assuming it's importable — skip gracefully if not).
    try:
        import pytest  # noqa: F401
    except ImportError:
        return
    result = dp.classify_module("pytest", local_names=set())
    assert result.kind == "THIRD_PARTY"


def test_classify_module_flags_stdlib_module():
    result = dp.classify_module("json", local_names=set())
    assert result.kind == "STDLIB"


def test_classify_module_flags_builtin_module():
    result = dp.classify_module("sys", local_names=set())
    assert result.kind == "STDLIB"


def test_classify_module_flags_unknown_module_as_unresolved():
    result = dp.classify_module("this_module_does_not_exist_xyz", local_names=set())
    assert result.kind == "UNRESOLVED"


def test_cli_exits_zero_on_the_real_project():
    completed = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "dependency_proof.py")],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "RESULT: PASS" in completed.stdout


def test_cli_json_report_is_written(tmp_path):
    report_path = tmp_path / "report.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "dependency_proof.py"),
            "--json",
            str(report_path),
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0
    assert report_path.exists()

    import json

    data = json.loads(report_path.read_text(encoding="utf-8"))
    assert data["summary"]["third_party"] == []
    assert data["summary"]["unresolved"] == []
    assert len(data["summary"]["stdlib"]) > 0
