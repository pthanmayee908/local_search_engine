"""
test_helpers.py
----------------
Tests for utils.helpers: size/duration formatting, the optional
user-config loader, and the cross-platform "open file" helper.
"""

import json
import subprocess
from pathlib import Path

import pytest

from utils import helpers


# ==============================================================
# FORMAT SIZE
# ==============================================================

class TestFormatSize:

    @pytest.mark.parametrize(
        "num_bytes,expected",
        [
            (0, "0 B"),
            (512, "512 B"),
            (1536, "1.5 KB"),
            (1024 * 1024, "1.0 MB"),
            (1024 * 1024 * 1024, "1.0 GB"),
        ],
    )
    def test_formats_expected_units(self, num_bytes, expected):
        assert helpers.format_size(num_bytes) == expected


# ==============================================================
# FORMAT DURATION
# ==============================================================

class TestFormatDuration:

    def test_seconds_only(self):
        assert helpers.format_duration(45) == "45s"

    def test_minutes_and_seconds(self):
        assert helpers.format_duration(134) == "2m 14s"

    def test_hours_minutes_seconds(self):
        assert helpers.format_duration(3661) == "1h 1m 1s"

    def test_rounds_fractional_seconds(self):
        assert helpers.format_duration(1.6) == "2s"


# ==============================================================
# LOAD EXTRA DIRECTORIES
# ==============================================================

class TestLoadExtraDirectories:

    def test_missing_config_returns_empty_list(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(helpers, "USER_CONFIG_PATH", tmp_path / "config.json")
        assert helpers.load_extra_directories() == []

    def test_valid_config_returns_existing_directories(self, tmp_path: Path, monkeypatch):
        extra_dir = tmp_path / "extra"
        extra_dir.mkdir()

        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps({"extra_directories": [str(extra_dir)]}),
            encoding="utf-8",
        )
        monkeypatch.setattr(helpers, "USER_CONFIG_PATH", config_path)

        directories = helpers.load_extra_directories()
        assert directories == [extra_dir]

    def test_nonexistent_directory_in_config_is_skipped(self, tmp_path: Path, monkeypatch):
        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps({"extra_directories": [str(tmp_path / "ghost")]}),
            encoding="utf-8",
        )
        monkeypatch.setattr(helpers, "USER_CONFIG_PATH", config_path)
        assert helpers.load_extra_directories() == []

    def test_invalid_json_returns_empty_list(self, tmp_path: Path, monkeypatch):
        config_path = tmp_path / "config.json"
        config_path.write_text("{not valid json", encoding="utf-8")
        monkeypatch.setattr(helpers, "USER_CONFIG_PATH", config_path)
        assert helpers.load_extra_directories() == []

    def test_non_dict_json_returns_empty_list(self, tmp_path: Path, monkeypatch):
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
        monkeypatch.setattr(helpers, "USER_CONFIG_PATH", config_path)
        assert helpers.load_extra_directories() == []

    def test_non_list_extra_directories_returns_empty_list(self, tmp_path: Path, monkeypatch):
        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps({"extra_directories": "not a list"}), encoding="utf-8"
        )
        monkeypatch.setattr(helpers, "USER_CONFIG_PATH", config_path)
        assert helpers.load_extra_directories() == []


# ==============================================================
# OPEN FILE
# ==============================================================

class TestOpenFile:

    def test_missing_file_returns_error_message(self, tmp_path: Path):
        error = helpers.open_file(str(tmp_path / "missing.txt"))
        assert error is not None
        assert "no longer exists" in error

    def test_success_on_linux_returns_none(self, tmp_path: Path, monkeypatch):
        target = tmp_path / "file.txt"
        target.write_text("data", encoding="utf-8")

        monkeypatch.setattr(helpers.platform, "system", lambda: "Linux")
        monkeypatch.setattr(
            helpers.subprocess, "run", lambda *a, **k: None
        )

        assert helpers.open_file(str(target)) is None

    def test_missing_handler_returns_message(self, tmp_path: Path, monkeypatch):
        target = tmp_path / "file.txt"
        target.write_text("data", encoding="utf-8")

        monkeypatch.setattr(helpers.platform, "system", lambda: "Linux")

        def _raise(*_a, **_k):
            raise FileNotFoundError()

        monkeypatch.setattr(helpers.subprocess, "run", _raise)

        error = helpers.open_file(str(target))
        assert "No default application handler" in error

    def test_subprocess_failure_returns_friendly_message(self, tmp_path: Path, monkeypatch):
        target = tmp_path / "file.txt"
        target.write_text("data", encoding="utf-8")

        monkeypatch.setattr(helpers.platform, "system", lambda: "Darwin")

        def _raise(*_a, **_k):
            raise subprocess.CalledProcessError(1, "open")

        monkeypatch.setattr(helpers.subprocess, "run", _raise)

        error = helpers.open_file(str(target))
        assert "could not be opened automatically" in error
