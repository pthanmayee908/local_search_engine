"""
test_scanner.py
----------------
Tests for scanner.scanner: per-format text extraction, the extraction
dispatcher, directory-skip rules, and the full scan_and_extract()
walk. All tests operate on files under pytest's ``tmp_path``, never
on the real filesystem.
"""

import json
from pathlib import Path

from scanner import scanner


# ==============================================================
# TEXT FILE EXTRACTION
# ==============================================================

class TestExtractTextFromTextFile:

    def test_reads_utf8_content(self, tmp_path: Path):
        file_path = tmp_path / "note.txt"
        file_path.write_text("hello world", encoding="utf-8")
        assert scanner.extract_text_from_text_file(file_path) == "hello world"

    def test_falls_back_to_latin1_on_decode_error(self, tmp_path: Path):
        file_path = tmp_path / "note.txt"
        file_path.write_bytes("café".encode("latin-1"))
        text = scanner.extract_text_from_text_file(file_path)
        assert "caf" in text

    def test_missing_file_returns_empty_string(self, tmp_path: Path):
        assert scanner.extract_text_from_text_file(tmp_path / "missing.txt") == ""


# ==============================================================
# CSV EXTRACTION
# ==============================================================

class TestExtractTextFromCsv:

    def test_flattens_rows(self, tmp_path: Path):
        file_path = tmp_path / "data.csv"
        file_path.write_text("a,b,c\n1,2,3\n", encoding="utf-8")
        text = scanner.extract_text_from_csv(file_path)
        assert "a" in text and "1" in text and "3" in text

    def test_missing_file_returns_empty_string(self, tmp_path: Path):
        assert scanner.extract_text_from_csv(tmp_path / "missing.csv") == ""


# ==============================================================
# JSON EXTRACTION
# ==============================================================

class TestExtractTextFromJson:

    def test_valid_json_is_reserialized(self, tmp_path: Path):
        file_path = tmp_path / "data.json"
        file_path.write_text(json.dumps({"key": "value"}), encoding="utf-8")
        text = scanner.extract_text_from_json(file_path)
        assert "key" in text and "value" in text

    def test_invalid_json_falls_back_to_raw_text(self, tmp_path: Path):
        file_path = tmp_path / "broken.json"
        file_path.write_text("{not valid json", encoding="utf-8")
        text = scanner.extract_text_from_json(file_path)
        assert "not valid json" in text


# ==============================================================
# HTML EXTRACTION
# ==============================================================

class TestExtractTextFromHtml:

    def test_strips_tags(self, tmp_path: Path):
        file_path = tmp_path / "page.html"
        file_path.write_text(
            "<html><body><h1>Title</h1><p>Body text.</p></body></html>",
            encoding="utf-8",
        )
        text = scanner.extract_text_from_html(file_path)
        assert "<h1>" not in text
        assert "Title" in text
        assert "Body text." in text


# ==============================================================
# DOCX EXTRACTION
# ==============================================================

class TestExtractTextFromDocx:

    def test_extracts_paragraph_text(self, tmp_path: Path, make_docx):
        file_path = make_docx(tmp_path / "doc.docx", ["Hello there", "Second paragraph"])
        text = scanner.extract_text_from_docx(file_path)
        assert "Hello there" in text
        assert "Second paragraph" in text

    def test_invalid_docx_returns_empty_string(self, tmp_path: Path):
        file_path = tmp_path / "not_really.docx"
        file_path.write_text("this is not a zip file", encoding="utf-8")
        assert scanner.extract_text_from_docx(file_path) == ""


# ==============================================================
# DISPATCHER
# ==============================================================

class TestExtractTextDispatcher:

    def test_routes_txt_to_text_extractor(self, tmp_path: Path):
        file_path = tmp_path / "a.txt"
        file_path.write_text("plain text", encoding="utf-8")
        assert scanner.extract_text(file_path) == "plain text"

    def test_routes_csv(self, tmp_path: Path):
        file_path = tmp_path / "a.csv"
        file_path.write_text("x,y\n1,2\n", encoding="utf-8")
        assert "x" in scanner.extract_text(file_path)

    def test_unsupported_extension_returns_empty_string(self, tmp_path: Path):
        file_path = tmp_path / "a.exe"
        file_path.write_bytes(b"\x00\x01")
        assert scanner.extract_text(file_path) == ""


# ==============================================================
# DIRECTORY SKIP RULES
# ==============================================================

class TestShouldSkipDir:

    def test_skips_hidden_directories(self, tmp_path: Path):
        assert scanner.should_skip_dir(tmp_path / ".git") is True

    def test_skips_known_system_directories(self):
        assert scanner.should_skip_dir(Path("C:/Windows")) is True
        assert scanner.should_skip_dir(Path("/some/AppData")) is True

    def test_does_not_skip_ordinary_directories(self, tmp_path: Path):
        assert scanner.should_skip_dir(tmp_path / "Documents") is False


# ==============================================================
# FULL SCAN
# ==============================================================

class TestScanAndExtract:

    def _build_tree(self, tmp_path: Path):
        (tmp_path / "notes.txt").write_text("first file", encoding="utf-8")
        (tmp_path / "ignored.exe").write_bytes(b"\x00")

        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "more.md").write_text("nested markdown", encoding="utf-8")

        hidden = tmp_path / ".git"
        hidden.mkdir()
        (hidden / "secret.txt").write_text("should not be scanned", encoding="utf-8")

        return tmp_path

    def test_finds_supported_files_recursively(self, tmp_path: Path):
        root = self._build_tree(tmp_path)
        found = {p.name for p, _meta, _text in scanner.scan_and_extract([root])}
        assert found == {"notes.txt", "more.md"}

    def test_skips_unsupported_extensions(self, tmp_path: Path):
        root = self._build_tree(tmp_path)
        found = {p.name for p, _meta, _text in scanner.scan_and_extract([root])}
        assert "ignored.exe" not in found

    def test_skips_hidden_directories(self, tmp_path: Path):
        root = self._build_tree(tmp_path)
        found = {p.name for p, _meta, _text in scanner.scan_and_extract([root])}
        assert "secret.txt" not in found

    def test_metadata_contains_extension_and_size(self, tmp_path: Path):
        root = self._build_tree(tmp_path)
        results = list(scanner.scan_and_extract([root]))
        notes = next(r for r in results if r[0].name == "notes.txt")
        _path, metadata, text = notes
        assert metadata["extension"] == ".txt"
        assert metadata["size"] > 0
        assert text == "first file"

    def test_nonexistent_root_is_skipped_without_error(self, tmp_path: Path):
        fake_root = tmp_path / "does_not_exist"
        results = list(scanner.scan_and_extract([fake_root]))
        assert results == []

    def test_duplicate_roots_are_not_scanned_twice(self, tmp_path: Path):
        root = self._build_tree(tmp_path)
        results = list(scanner.scan_and_extract([root, root]))
        names = [p.name for p, _meta, _text in results]
        assert names.count("notes.txt") == 1

    def test_get_all_files_returns_a_list(self, tmp_path: Path):
        root = self._build_tree(tmp_path)
        results = scanner.get_all_files([root])
        assert isinstance(results, list)
        assert len(results) == 2
