"""
test_database.py
-----------------
Tests for storage.database: the small SQLite helper layer that tracks
indexing-run history and exposes read-only statistics, kept separate
from indexer.indexer.Indexer by design (see storage/database.py's
module docstring).
"""

from pathlib import Path

from indexer.indexer import DocumentInput, Indexer
from storage import database


class TestDatabaseExists:

    def test_false_for_missing_file(self, tmp_path: Path):
        assert database.database_exists(str(tmp_path / "nope.db")) is False

    def test_true_once_created(self, db_path, indexer):
        # `indexer` fixture opening a connection creates the file on disk.
        assert database.database_exists(db_path) is True


class TestRunHistory:

    def test_get_last_run_is_none_before_any_run(self, db_path, indexer):
        assert database.get_last_run(db_path) is None

    def test_record_and_retrieve_a_run(self, db_path, indexer):
        database.record_index_run(
            db_path,
            started_at=1000.0,
            duration_seconds=12.5,
            files_discovered=10,
            files_indexed=8,
            files_skipped=2,
            errors=0,
        )
        last_run = database.get_last_run(db_path)
        assert last_run is not None
        assert last_run["files_discovered"] == 10
        assert last_run["files_indexed"] == 8
        assert last_run["files_skipped"] == 2
        assert last_run["errors"] == 0

    def test_get_last_run_returns_the_most_recent(self, db_path, indexer):
        database.record_index_run(
            db_path, started_at=1000.0, duration_seconds=1.0,
            files_discovered=1, files_indexed=1, files_skipped=0, errors=0,
        )
        database.record_index_run(
            db_path, started_at=2000.0, duration_seconds=2.0,
            files_discovered=2, files_indexed=2, files_skipped=0, errors=0,
        )
        last_run = database.get_last_run(db_path)
        assert last_run["started_at"] == 2000.0


class TestUniqueTermCount:

    def test_zero_when_database_does_not_exist(self, tmp_path: Path):
        assert database.get_unique_term_count(str(tmp_path / "nope.db")) == 0

    def test_zero_when_terms_table_does_not_exist(self, db_path):
        # Create the file but never build the `terms` table.
        Path(db_path).touch()
        assert database.get_unique_term_count(db_path) == 0

    def test_counts_distinct_terms(self, db_path):
        idx = Indexer(db_path=db_path)
        try:
            idx.index_document(DocumentInput(
                filename="a.txt", filepath="/a.txt", content="apple banana",
                file_type=".txt", modified_time="2026-01-01T00:00:00",
            ))
            idx.index_document(DocumentInput(
                filename="b.txt", filepath="/b.txt", content="banana cherry",
                file_type=".txt", modified_time="2026-01-01T00:00:00",
            ))
        finally:
            idx.close()

        # apple, banana, cherry -> 3 distinct terms.
        assert database.get_unique_term_count(db_path) == 3


class TestDatabaseSize:

    def test_zero_for_missing_file(self, tmp_path: Path):
        assert database.get_database_size_bytes(str(tmp_path / "nope.db")) == 0

    def test_positive_for_existing_file(self, db_path, indexer):
        assert database.get_database_size_bytes(db_path) > 0
