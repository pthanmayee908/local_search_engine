"""
test_search_engine.py
----------------------
Tests for search.search_engine.SearchEngine: query tokenization,
candidate retrieval, TF-IDF scoring, snippet generation, and the
end-to-end ranked ``search()`` pipeline.
"""

from indexer.indexer import DocumentInput


# ==============================================================
# QUERY TOKENIZATION
# ==============================================================

class TestTokenizeQuery:

    def test_basic_tokenization(self, search_engine):
        assert search_engine.tokenize_query("Deadlock Prevention") == [
            "deadlock",
            "prevention",
        ]

    def test_empty_query(self, search_engine):
        assert search_engine.tokenize_query("") == []

    def test_stopwords_removed(self, search_engine):
        assert search_engine.tokenize_query("the deadlock and the resource") == [
            "deadlock",
            "resource",
        ]


# ==============================================================
# CANDIDATE DOCUMENTS
# ==============================================================

class TestFindCandidateDocuments:

    def test_finds_docs_containing_any_term(self, search_engine, populated_indexer):
        candidates = search_engine.find_candidate_documents(["deadlock", "cake"])
        assert len(candidates) == 3  # deadlock.md, python_notes.txt, recipe.txt

    def test_no_match_returns_empty_set(self, search_engine, populated_indexer):
        assert search_engine.find_candidate_documents(["zzznomatch"]) == set()

    def test_empty_terms_returns_empty_set(self, search_engine, populated_indexer):
        assert search_engine.find_candidate_documents([]) == set()


# ==============================================================
# TF-IDF SCORING
# ==============================================================

class TestCalculateTfidf:

    def test_zero_for_term_not_in_document(self, search_engine, populated_indexer):
        doc_id = populated_indexer.get_existing_document("/docs/recipe.txt")["document_id"]
        score = search_engine.calculate_tfidf("deadlock", doc_id, 3, {})
        assert score == 0.0

    def test_positive_for_term_in_document(self, search_engine, populated_indexer):
        doc_id = populated_indexer.get_existing_document("/docs/deadlock.md")["document_id"]
        score = search_engine.calculate_tfidf("deadlock", doc_id, 3, {})
        assert score > 0.0

    def test_rarer_terms_score_higher(self, search_engine, populated_indexer):
        # "deadlock" appears in 2/3 docs, "cake" in 1/3 -> cake has
        # higher IDF, so should score higher for equal term frequency.
        deadlock_doc = populated_indexer.get_existing_document("/docs/deadlock.md")["document_id"]
        cake_doc = populated_indexer.get_existing_document("/docs/recipe.txt")["document_id"]

        deadlock_score = search_engine.calculate_tfidf("deadlock", deadlock_doc, 3, {})
        cake_score = search_engine.calculate_tfidf("cake", cake_doc, 3, {})

        assert cake_score > deadlock_score

    def test_df_cache_is_populated(self, search_engine, populated_indexer):
        cache = {}
        doc_id = populated_indexer.get_existing_document("/docs/deadlock.md")["document_id"]
        search_engine.calculate_tfidf("deadlock", doc_id, 3, cache)
        assert cache["deadlock"] == 2


# ==============================================================
# DOCUMENT SCORING (multi-term bonus)
# ==============================================================

class TestCalculateDocumentScore:

    def test_multi_term_match_beats_single_term_match(self, search_engine, populated_indexer):
        doc_id = populated_indexer.get_existing_document("/docs/deadlock.md")["document_id"]

        single_term_score = search_engine.calculate_document_score(
            ["deadlock"], doc_id, 3, {}
        )
        multi_term_score = search_engine.calculate_document_score(
            ["deadlock", "resource"], doc_id, 3, {}
        )

        assert multi_term_score > single_term_score

    def test_no_matching_terms_scores_zero(self, search_engine, populated_indexer):
        doc_id = populated_indexer.get_existing_document("/docs/recipe.txt")["document_id"]
        score = search_engine.calculate_document_score(["deadlock"], doc_id, 3, {})
        assert score == 0.0


# ==============================================================
# SNIPPETS
# ==============================================================

class TestMakeSnippet:

    def test_empty_content_returns_empty_string(self, search_engine):
        assert search_engine.make_snippet("", ["hello"]) == ""

    def test_empty_terms_returns_empty_string(self, search_engine):
        assert search_engine.make_snippet("some content here", []) == ""

    def test_highlights_matching_term(self, search_engine):
        snippet = search_engine.make_snippet("the quick brown fox jumps", ["fox"])
        assert "**fox**" in snippet

    def test_no_term_found_returns_leading_window(self, search_engine):
        snippet = search_engine.make_snippet("alpha beta gamma delta", ["zulu"])
        assert snippet.startswith("alpha beta gamma delta")

    def test_adds_ellipsis_when_truncated(self, search_engine):
        long_content = " ".join(f"word{i}" for i in range(100))
        snippet = search_engine.make_snippet(long_content, ["word50"])
        assert snippet.startswith("...")
        assert snippet.endswith("...")
        assert "**word50**" in snippet


# ==============================================================
# END-TO-END SEARCH
# ==============================================================

class TestSearch:

    def test_returns_results_for_matching_query(self, search_engine, populated_indexer):
        results = search_engine.search("deadlock")
        assert len(results) == 2
        filenames = {r.filename for r in results}
        assert filenames == {"deadlock.md", "python_notes.txt"}

    def test_empty_query_returns_no_results(self, search_engine, populated_indexer):
        assert search_engine.search("") == []

    def test_only_stopwords_returns_no_results(self, search_engine, populated_indexer):
        assert search_engine.search("the and of") == []

    def test_no_matching_documents(self, search_engine, populated_indexer):
        assert search_engine.search("nonexistentxyz") == []

    def test_results_are_sorted_descending_by_score(self, search_engine, populated_indexer):
        results = search_engine.search("deadlock resource python")
        scores = [r.raw_score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_top_result_has_100_percent_relevance(self, search_engine, populated_indexer):
        results = search_engine.search("deadlock")
        assert results[0].relevance_pct == 100.0

    def test_limit_is_respected(self, search_engine, populated_indexer):
        results = search_engine.search("deadlock resource python cake", limit=1)
        assert len(results) == 1

    def test_search_on_empty_index_returns_no_results(self, search_engine, indexer):
        # `indexer` here has nothing indexed (populated_indexer not used).
        assert search_engine.search("anything") == []

    def test_snippets_are_populated(self, search_engine, populated_indexer):
        results = search_engine.search("deadlock")
        assert all(r.snippet for r in results)
