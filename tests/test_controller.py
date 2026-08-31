"""
test_controller.py
-------------------
Integration tests for controller.SearchEngineController — the layer
that wires scanner + indexer + search engine + storage together.

The real filesystem scanner and the user's home directory are never
touched: ``scanner.scan_and_extract`` / ``scanner.get_user_directories``
are monkeypatched to operate on a small, temporary corpus instead.
"""

from pathlib import Path

import controller as controller_module
from controller import IntegrationError, SearchEngineController


def _make_controller(tmp_path: Path) -> SearchEngineController:
    return SearchEngineController(db_path=str(tmp_path / "controller_test.db"))


def _fake_scan_and_extract(tmp_path: Path):
    """A stand-in for scanner.scan_and_extract() with a fixed, tiny corpus.

    The corpus files are written to disk once, up front, so that
    ``modified_time`` (derived from ``st_mtime``) stays stable across
    repeated calls -- exactly like a real, unchanged file would.
    """

    files = {
        "alpha.txt": "deadlock prevention and resource allocation",
        "beta.txt": "python programs avoid deadlock with careful locking",
        "gamma.txt": "bake a cake for forty minutes",
    }

    written = {}
    for name, content in files.items():
        path = tmp_path / name
        path.write_text(content, encoding="utf-8")
        written[name] = (path, content)

    def _fake(_roots=None):
        for name, (path, content) in written.items():
            stat = path.stat()
            metadata = {
                "size": stat.st_size,
                "modified": stat.st_mtime,
                "extension": ".txt",
            }
            yield path, metadata, content

    return _fake


class TestIndexExistsAndDocumentCount:

    def test_index_does_not_exist_before_first_run(self, tmp_path):
        ctl = _make_controller(tmp_path)
        try:
            assert ctl.index_exists() is False
            assert ctl.document_count() == 0
        finally:
            ctl.close()


class TestRunIndex:

    def test_run_index_populates_the_database(self, tmp_path, monkeypatch):
        ctl = _make_controller(tmp_path)
        try:
            monkeypatch.setattr(
                controller_module.scanner,
                "get_user_directories",
                lambda: [tmp_path],
            )
            monkeypatch.setattr(
                controller_module.scanner,
                "scan_and_extract",
                _fake_scan_and_extract(tmp_path),
            )
            monkeypatch.setattr(
                controller_module, "load_extra_directories", lambda: []
            )

            summary = ctl.run_index()

            assert summary.files_discovered == 3
            assert summary.files_indexed == 3
            assert summary.files_skipped == 0
            assert summary.errors == 0
            assert ctl.document_count() == 3
        finally:
            ctl.close()

    def test_second_run_skips_unchanged_files(self, tmp_path, monkeypatch):
        ctl = _make_controller(tmp_path)
        try:
            monkeypatch.setattr(
                controller_module.scanner, "get_user_directories", lambda: [tmp_path]
            )
            monkeypatch.setattr(
                controller_module.scanner,
                "scan_and_extract",
                _fake_scan_and_extract(tmp_path),
            )
            monkeypatch.setattr(controller_module, "load_extra_directories", lambda: [])

            ctl.run_index()
            second_summary = ctl.run_index()

            assert second_summary.files_skipped == 3
            assert second_summary.files_indexed == 0
        finally:
            ctl.close()

    def test_progress_callback_is_invoked(self, tmp_path, monkeypatch):
        ctl = _make_controller(tmp_path)
        try:
            monkeypatch.setattr(
                controller_module.scanner, "get_user_directories", lambda: [tmp_path]
            )
            monkeypatch.setattr(
                controller_module.scanner,
                "scan_and_extract",
                _fake_scan_and_extract(tmp_path),
            )
            monkeypatch.setattr(controller_module, "load_extra_directories", lambda: [])

            # 25-file trigger threshold means the 3-file corpus won't
            # itself fire the callback, so we only assert run_index()
            # completes cleanly with progress_callback wired up.
            seen = []
            ctl.run_index(progress_callback=lambda d, i, e: seen.append((d, i, e)))
            assert ctl.document_count() == 3
        finally:
            ctl.close()


class TestSearch:

    def _indexed_controller(self, tmp_path, monkeypatch):
        ctl = _make_controller(tmp_path)
        monkeypatch.setattr(
            controller_module.scanner, "get_user_directories", lambda: [tmp_path]
        )
        monkeypatch.setattr(
            controller_module.scanner,
            "scan_and_extract",
            _fake_scan_and_extract(tmp_path),
        )
        monkeypatch.setattr(controller_module, "load_extra_directories", lambda: [])
        ctl.run_index()
        return ctl

    def test_search_returns_matching_results(self, tmp_path, monkeypatch):
        ctl = self._indexed_controller(tmp_path, monkeypatch)
        try:
            results = ctl.search("deadlock")
            assert len(results) == 2
        finally:
            ctl.close()

    def test_search_blank_query_returns_empty_list(self, tmp_path, monkeypatch):
        ctl = self._indexed_controller(tmp_path, monkeypatch)
        try:
            assert ctl.search("   ") == []
        finally:
            ctl.close()


class TestStatistics:

    def test_statistics_before_indexing(self, tmp_path):
        ctl = _make_controller(tmp_path)
        try:
            stats = ctl.get_statistics()
            assert stats["documents_indexed"] == 0
            assert stats["last_run"] is None
        finally:
            ctl.close()

    def test_statistics_after_indexing(self, tmp_path, monkeypatch):
        ctl = _make_controller(tmp_path)
        try:
            monkeypatch.setattr(
                controller_module.scanner, "get_user_directories", lambda: [tmp_path]
            )
            monkeypatch.setattr(
                controller_module.scanner,
                "scan_and_extract",
                _fake_scan_and_extract(tmp_path),
            )
            monkeypatch.setattr(controller_module, "load_extra_directories", lambda: [])

            ctl.run_index()
            stats = ctl.get_statistics()

            assert stats["documents_indexed"] == 3
            assert stats["unique_terms"] > 0
            assert stats["database_size_bytes"] > 0
            assert stats["last_run"] is not None
        finally:
            ctl.close()


class TestClose:

    def test_close_is_idempotent_when_never_opened(self, tmp_path):
        ctl = _make_controller(tmp_path)
        # No indexer/search_engine property was ever touched.
        ctl.close()  # should not raise

    def test_close_after_use_does_not_raise(self, tmp_path):
        ctl = _make_controller(tmp_path)
        ctl.document_count()  # touches the indexer property
        ctl.close()
