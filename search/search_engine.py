"""
search_engine.py
-----------------
Person 3: Search + Ranking

>>> MEMBER 3 MODULE — LOGIC UNCHANGED <<<
Only change made for integration: the import of Indexer now points at
its package location (`indexer.indexer`) instead of a bare top-level
`indexer` module, since this project is organised into packages.
No scoring, tokenization, or snippet logic was touched.

Responsibilities:
    1. Accept user's search query.
    2. Clean and tokenize the query.
    3. Find candidate documents using Person 2's index.
    4. Calculate TF-IDF.
    5. Rank matching documents.
    6. Generate useful snippets.
    7. Return structured search results.

Does NOT:
    - scan folders
    - extract documents
    - build the inverted index
    - create another database
    - use third-party packages
"""

import math
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Set

from indexer.indexer import Indexer


# ==============================================================
# SEARCH RESULT
# ==============================================================

@dataclass
class SearchResult:

    document_id: int

    filename: str

    filepath: str

    file_type: str

    raw_score: float

    relevance_pct: float = 0.0

    snippet: str = ""


# ==============================================================
# SEARCH ENGINE
# ==============================================================

class SearchEngine:

    def __init__(
        self,
        indexer: Indexer
    ):

        self.indexer = indexer

    # ==========================================================
    # QUERY TOKENIZATION
    # ==========================================================

    def tokenize_query(
        self,
        query: str
    ) -> List[str]:

        if not query:

            return []

        # Use same cleaning method as Person 2.
        cleaned = self.indexer.clean_text(
            query
        )

        tokens = cleaned.split()

        # Remove the same stopwords.
        tokens = [
            token
            for token in tokens
            if token not in self.indexer.stopwords
        ]

        return tokens

    # ==========================================================
    # FIND CANDIDATE DOCUMENTS
    # ==========================================================

    def find_candidate_documents(
        self,
        terms: List[str]
    ) -> Set[int]:

        candidates = set()

        for term in set(terms):

            document_ids = (
                self.indexer.get_documents_for_term(
                    term
                )
            )

            candidates.update(
                document_ids
            )

        return candidates

    # ==========================================================
    # TF-IDF
    # ==========================================================

    def calculate_tfidf(
        self,
        term: str,
        document_id: int,
        total_documents: int,
        df_cache: Dict[str, int]
    ) -> float:

        term_frequency = (
            self.indexer.get_term_frequency(
                term,
                document_id
            )
        )

        if term_frequency == 0:

            return 0.0

        # Document frequency caching.
        if term not in df_cache:

            df_cache[term] = (
                self.indexer.get_document_frequency(
                    term
                )
            )

        document_frequency = df_cache[term]

        if document_frequency == 0:

            return 0.0

        # Logarithmic TF.
        tf = 1 + math.log(
            term_frequency
        )

        # Smoothed IDF.
        idf = (
            math.log(
                (total_documents + 1)
                /
                (document_frequency + 1)
            )
            + 1
        )

        return tf * idf

    # ==========================================================
    # DOCUMENT SCORE
    # ==========================================================

    def calculate_document_score(
        self,
        terms: List[str],
        document_id: int,
        total_documents: int,
        df_cache: Dict[str, int]
    ) -> float:

        unique_terms = set(terms)

        score = 0.0

        matched_terms = 0

        for term in unique_terms:

            term_score = self.calculate_tfidf(
                term,
                document_id,
                total_documents,
                df_cache
            )

            if term_score > 0:

                score += term_score

                matched_terms += 1

        # ------------------------------------------------------
        # Multi-term bonus
        #
        # A document containing several different query words
        # should normally rank above a document containing
        # only one of them.
        # ------------------------------------------------------

        if matched_terms > 1:

            score *= (
                1
                +
                0.10 * (matched_terms - 1)
            )

        return score

    # ==========================================================
    # SNIPPET NORMALIZATION
    # ==========================================================

    @staticmethod
    def normalize_word(
        word: str
    ) -> str:

        word = word.lower()

        word = re.sub(
            r"[^\w\s]",
            "",
            word
        )

        return word

    # ==========================================================
    # MAKE SNIPPET
    # ==========================================================

    def make_snippet(
        self,
        content: Optional[str],
        terms: List[str],
        window: int = 18
    ) -> str:

        if not content:

            return ""

        if not terms:

            return ""

        words = content.split()

        normalized_words = [
            self.normalize_word(word)
            for word in words
        ]

        term_set = set(terms)

        # ------------------------------------------------------
        # Find the first query term in the document.
        # ------------------------------------------------------

        position = None

        for i, word in enumerate(
            normalized_words
        ):

            if word in term_set:

                position = i

                break

        # ------------------------------------------------------
        # No term found.
        # ------------------------------------------------------

        if position is None:

            snippet_words = words[:window]

            snippet = " ".join(
                snippet_words
            )

            if len(words) > window:

                snippet += "..."

            return snippet

        # ------------------------------------------------------
        # Calculate snippet boundaries.
        # ------------------------------------------------------

        start = max(
            0,
            position - window // 2
        )

        end = min(
            len(words),
            start + window
        )

        snippet_words = words[start:end]

        # ------------------------------------------------------
        # Add ellipsis if text continues.
        # ------------------------------------------------------

        prefix = "..." if start > 0 else ""

        suffix = "..." if end < len(words) else ""

        # ------------------------------------------------------
        # Highlight query terms.
        # ------------------------------------------------------

        highlighted_words = []

        for word in snippet_words:

            normalized = self.normalize_word(
                word
            )

            if normalized in term_set:

                highlighted_words.append(
                    f"**{word}**"
                )

            else:

                highlighted_words.append(
                    word
                )

        snippet = " ".join(
            highlighted_words
        )

        return prefix + snippet + suffix

    # ==========================================================
    # MAIN SEARCH FUNCTION
    # ==========================================================

    def search(
        self,
        query: str,
        limit: int = 10
    ) -> List[SearchResult]:

        # ------------------------------------------------------
        # Step 1: Tokenize query.
        # ------------------------------------------------------

        terms = self.tokenize_query(
            query
        )

        if not terms:

            return []

        # ------------------------------------------------------
        # Step 2: Find candidate documents.
        # ------------------------------------------------------

        candidates = (
            self.find_candidate_documents(
                terms
            )
        )

        if not candidates:

            return []

        # ------------------------------------------------------
        # Step 3: Total document count.
        # ------------------------------------------------------

        total_documents = (
            self.indexer.get_total_document_count()
        )

        if total_documents == 0:

            return []

        # ------------------------------------------------------
        # Step 4: Cache document frequencies.
        # ------------------------------------------------------

        df_cache: Dict[str, int] = {}

        results: List[SearchResult] = []

        # ------------------------------------------------------
        # Step 5: Score every candidate.
        # ------------------------------------------------------

        for document_id in candidates:

            score = (
                self.calculate_document_score(
                    terms,
                    document_id,
                    total_documents,
                    df_cache
                )
            )

            if score <= 0:

                continue

            # Get metadata.
            metadata = (
                self.indexer.get_document_metadata(
                    document_id
                )
            )

            if metadata is None:

                continue

            # Get original extracted content.
            content = (
                self.indexer.get_document_content(
                    document_id
                )
            )

            # Create snippet.
            snippet = self.make_snippet(
                content,
                terms
            )

            result = SearchResult(

                document_id=document_id,

                filename=metadata["filename"],

                filepath=metadata["filepath"],

                file_type=metadata["file_type"],

                raw_score=score,

                snippet=snippet
            )

            results.append(result)

        # ------------------------------------------------------
        # Step 6: Highest score first.
        # ------------------------------------------------------

        results.sort(
            key=lambda result: result.raw_score,
            reverse=True
        )

        # ------------------------------------------------------
        # Step 7: Limit results.
        # ------------------------------------------------------

        results = results[:limit]

        # ------------------------------------------------------
        # Step 8: Relative relevance percentage.
        # ------------------------------------------------------

        if results:

            highest_score = (
                results[0].raw_score
            )

            if highest_score > 0:

                for result in results:

                    result.relevance_pct = (
                        result.raw_score
                        /
                        highest_score
                    ) * 100

        return results


# ==============================================================
# DISPLAY RESULTS (kept for standalone/demo use of this module)
# ==============================================================

def print_results(
    results: List[SearchResult]
):

    if not results:

        print(
            "\nNo matching documents found."
        )

        return

    print(
        "\n" + "=" * 70
    )

    print(
        "SEARCH RESULTS"
    )

    print(
        "=" * 70
    )

    for position, result in enumerate(
        results,
        start=1
    ):

        print(
            f"\n{position}. {result.filename}"
        )

        print(
            f"   Relevance : "
            f"{result.relevance_pct:.0f}%"
        )

        print(
            f"   Type      : "
            f"{result.file_type}"
        )

        print(
            f"   Location  : "
            f"{result.filepath}"
        )

        if result.snippet:

            print(
                f"   Preview   : "
                f"{result.snippet}"
            )

        print(
            "-" * 70
        )


# ==============================================================
# DEMO
# ==============================================================

if __name__ == "__main__":

    # Connect to Person 2's database.
    indexer = Indexer(
        db_path="demo_index.db"
    )

    # Create search engine.
    search_engine = SearchEngine(
        indexer
    )

    print(
        "=" * 70
    )

    print(
        "LOCAL SEARCH ENGINE"
    )

    print(
        "=" * 70
    )

    print(
        "\nIndexed documents:",
        indexer.get_total_document_count()
    )

    query = "deadlock prevention"

    print(
        f'\nSearching for: "{query}"'
    )

    results = search_engine.search(
        query,
        limit=10
    )

    print_results(
        results
    )

    indexer.close()