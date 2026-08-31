"""
test_indexer.py
----------------
Tests for indexer.indexer.Indexer: tokenization, stopword removal,
term-frequency computation, the SQLite-backed inverted index
(insert / update / delete), and the read APIs the search engine
depends on.
"""

from indexer.indexer import DocumentInput, Indexer


# ==============================================================
# TEXT PROCESSING
# ==============================================================

class TestCleanText:

    def test_lowercases(self, indexer):
        assert indexer.clean_text("HELLO World") == "hello world"

    def test_strips_punctuation(self, indexer):
        assert indexer.clean_text("Hello, World!!") == "hello world"

    def test_collapses_whitespace(self, indexer):
        assert indexer.clean_text("a   b\t\tc\n\nd") == "a b c d"

    def test_empty_string(self, indexer):
        assert indexer.clean_text("") == ""


class TestTokenize:

    def test_basic(self, indexer):
        assert indexer.tokenize("Hello World") == ["hello", "world"]

    def test_empty_content_returns_empty_list(self, indexer):
        assert indexer.tokenize("") == []

    def test_only_punctuation_returns_empty_list(self, indexer):
        assert indexer.tokenize("!!! ... ,,,") == []


class TestRemoveStopwords:

    def test_filters_default_stopwords(self, indexer):
        tokens = ["the", "quick", "fox", "is", "fast"]
        assert indexer.remove_stopwords(tokens) == ["quick", "fox", "fast"]

    def test_custom_stopwords(self, db_path):
        idx = Indexer(db_path=db_path, stopwords={"quick", "fox"})
        try:
            assert idx.remove_stopwords(["the", "quick", "fox"]) == ["the"]
        finally:
            idx.close()


class TestComputeTermFrequencies:

    def test_counts_occurrences(self, indexer):
        freqs = indexer.compute_term_frequencies(["a", "b", "a", "c", "a"])
        assert freqs == {"a": 3, "b": 1, "c": 1}

    def test_empty_tokens(self, indexer):
        assert indexer.compute_term_frequencies([]) == {}


# ==============================================================
# INDEXING A SINGLE DOCUMENT
# ==============================================================

class TestIndexDocument:

    def test_new_document_gets_an_id(self, indexer):
        doc = DocumentInput(
            filename="a.txt",
            filepath="/a.txt",
            content="hello world",
            file_type=".txt",
            modified_time="2026-01-01T00:00:00",
        )
        document_id = indexer.index_document(doc)
        assert isinstance(document_id, int)
        assert document_id > 0

    def test_metadata_is_stored(self, indexer):
        doc = DocumentInput(
            filename="a.txt",
            filepath="/a.txt",
            content="hello world",
            file_type=".txt",
            modified_time="2026-01-01T00:00:00",
        )
        document_id = indexer.index_document(doc)
        metadata = indexer.get_document_metadata(document_id)
        assert metadata["filename"] == "a.txt"
        assert metadata["filepath"] == "/a.txt"
        assert metadata["file_type"] == ".txt"

    def test_content_is_retrievable(self, indexer):
        doc = DocumentInput(
            filename="a.txt",
            filepath="/a.txt",
            content="hello world",
            file_type=".txt",
            modified_time="2026-01-01T00:00:00",
        )
        document_id = indexer.index_document(doc)
        assert indexer.get_document_content(document_id) == "hello world"

    def test_stopwords_are_not_indexed(self, indexer):
        doc = DocumentInput(
            filename="a.txt",
            filepath="/a.txt",
            content="the cat and the hat",
            file_type=".txt",
            modified_time="2026-01-01T00:00:00",
        )
        document_id = indexer.index_document(doc)
        assert indexer.get_term_frequency("the", document_id) == 0
        assert indexer.get_term_frequency("cat", document_id) == 1

    def test_reindexing_same_filepath_reuses_document_id(self, indexer):
        doc_v1 = DocumentInput(
            filename="a.txt", filepath="/a.txt", content="version one",
            file_type=".txt", modified_time="2026-01-01T00:00:00",
        )
        doc_v2 = DocumentInput(
            filename="a.txt", filepath="/a.txt", content="version two revised",
            file_type=".txt", modified_time="2026-01-02T00:00:00",
        )
        id1 = indexer.index_document(doc_v1)
        id2 = indexer.index_document(doc_v2)
        assert id1 == id2

    def test_reindexing_replaces_old_terms(self, indexer):
        doc_v1 = DocumentInput(
            filename="a.txt", filepath="/a.txt", content="apple banana",
            file_type=".txt", modified_time="2026-01-01T00:00:00",
        )
        doc_v2 = DocumentInput(
            filename="a.txt", filepath="/a.txt", content="cherry date",
            file_type=".txt", modified_time="2026-01-02T00:00:00",
        )
        document_id = indexer.index_document(doc_v1)
        indexer.index_document(doc_v2)

        assert indexer.get_term_frequency("apple", document_id) == 0
        assert indexer.get_term_frequency("cherry", document_id) == 1

    def test_total_document_count(self, populated_indexer):
        assert populated_indexer.get_total_document_count() == 3


# ==============================================================
# NEEDS_REINDEX
# ==============================================================

class TestNeedsReindex:

    def test_new_file_needs_indexing(self, indexer):
        assert indexer.needs_reindex("/new.txt", "2026-01-01T00:00:00") is True

    def test_unchanged_file_does_not_need_reindexing(self, indexer):
        doc = DocumentInput(
            filename="a.txt", filepath="/a.txt", content="hello",
            file_type=".txt", modified_time="2026-01-01T00:00:00",
        )
        indexer.index_document(doc)
        assert indexer.needs_reindex("/a.txt", "2026-01-01T00:00:00") is False

    def test_changed_mtime_needs_reindexing(self, indexer):
        doc = DocumentInput(
            filename="a.txt", filepath="/a.txt", content="hello",
            file_type=".txt", modified_time="2026-01-01T00:00:00",
        )
        indexer.index_document(doc)
        assert indexer.needs_reindex("/a.txt", "2026-02-02T00:00:00") is True


# ==============================================================
# REMOVAL
# ==============================================================

class TestRemoveDocument:

    def test_remove_by_id_deletes_document_and_terms(self, indexer):
        doc = DocumentInput(
            filename="a.txt", filepath="/a.txt", content="hello world",
            file_type=".txt", modified_time="2026-01-01T00:00:00",
        )
        document_id = indexer.index_document(doc)
        indexer.remove_document_index(document_id)

        assert indexer.get_document_metadata(document_id) is None
        assert indexer.get_term_frequency("hello", document_id) == 0
        assert indexer.get_total_document_count() == 0

    def test_remove_by_filepath(self, indexer):
        doc = DocumentInput(
            filename="a.txt", filepath="/a.txt", content="hello world",
            file_type=".txt", modified_time="2026-01-01T00:00:00",
        )
        indexer.index_document(doc)
        indexer.remove_document_by_filepath("/a.txt")
        assert indexer.get_total_document_count() == 0

    def test_remove_by_filepath_missing_file_is_a_no_op(self, indexer):
        # Should not raise even though nothing was ever indexed.
        indexer.remove_document_by_filepath("/does/not/exist.txt")
        assert indexer.get_total_document_count() == 0


# ==============================================================
# SYNC (full-scan reconciliation)
# ==============================================================

class TestSync:

    def test_sync_indexes_all_new_documents(self, indexer, sample_documents):
        indexer.sync(sample_documents)
        assert indexer.get_total_document_count() == len(sample_documents)

    def test_sync_removes_deleted_files(self, indexer, sample_documents):
        indexer.sync(sample_documents)
        # Second sync only reports two of the three files (one "deleted").
        remaining = [d for d in sample_documents if d.filepath != "/docs/recipe.txt"]
        indexer.sync(remaining)
        assert indexer.get_total_document_count() == 2

    def test_sync_skips_unchanged_files(self, indexer, sample_documents):
        indexer.sync(sample_documents)
        first_id = indexer.get_existing_document("/docs/deadlock.md")["document_id"]
        indexer.sync(sample_documents)
        second_id = indexer.get_existing_document("/docs/deadlock.md")["document_id"]
        assert first_id == second_id

    def test_sync_reindexes_modified_files(self, indexer, sample_documents):
        indexer.sync(sample_documents)

        modified = list(sample_documents)
        modified[0] = DocumentInput(
            filename=modified[0].filename,
            filepath=modified[0].filepath,
            content="completely different words now",
            file_type=modified[0].file_type,
            modified_time="2027-01-01T00:00:00",
        )
        indexer.sync(modified)

        doc_id = indexer.get_existing_document("/docs/deadlock.md")["document_id"]
        assert indexer.get_term_frequency("deadlock", doc_id) == 0
        assert indexer.get_term_frequency("completely", doc_id) == 1

    def test_sync_with_empty_list_clears_index(self, indexer, sample_documents):
        indexer.sync(sample_documents)
        indexer.sync([])
        assert indexer.get_total_document_count() == 0


# ==============================================================
# DOCUMENT / TERM FREQUENCY QUERIES
# ==============================================================

class TestQueries:

    def test_get_document_frequency_counts_distinct_docs(self, populated_indexer):
        # "deadlock" appears in 2 of the 3 sample documents.
        assert populated_indexer.get_document_frequency("deadlock") == 2

    def test_get_document_frequency_zero_for_unknown_term(self, populated_indexer):
        assert populated_indexer.get_document_frequency("nonexistentword") == 0

    def test_get_documents_for_term(self, populated_indexer):
        doc_ids = populated_indexer.get_documents_for_term("deadlock")
        assert len(doc_ids) == 2

    def test_get_document_content_missing_id_returns_none(self, populated_indexer):
        assert populated_indexer.get_document_content(999999) is None

    def test_get_document_metadata_missing_id_returns_none(self, populated_indexer):
        assert populated_indexer.get_document_metadata(999999) is None
