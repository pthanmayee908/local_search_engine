"""
indexer.py
----------
Person 2's module: Indexing.

>>> MEMBER 2 MODULE — UNCHANGED <<<

Responsibility:
    Take an extracted document (from Person 1's File Discovery + Text
    Extraction module) and build/maintain a persistent SQLite inverted
    index: term -> {document_id: frequency}.

    This module also stores each document's full extracted content
    (needed later for snippet generation) and exposes it through
    get_document_content(). It does NOT generate snippets itself —
    that's Person 3's job, once they know which document matched and
    where the query terms sit in the text.

    This module does NOT compute TF-IDF scores. It only stores the raw
    ingredients (term frequency, document frequency, total document
    count, document content) that Person 3's Search & Ranking module
    needs.

Expected input per document (e.g. as a dict or dataclass from Person 1):
    document_id    : int   (can be None for a brand-new file; DB assigns one)
    filename        : str
    filepath        : str   (unique key used to detect new/modified/deleted)
    content         : str   (raw extracted text)
    file_type       : str   (".txt", ".py", ".md", ".csv", ".json",
                              ".html", ".htm", ".xml", ".log", ".docx")
    modified_time   : str   (ISO string or timestamp, from os.path.getmtime)
"""

import os
import re
import sqlite3
from dataclasses import dataclass
from typing import Iterable, List, Dict, Optional


# ----------------------------------------------------------------------
# Configurable stop word list (Step 3)
# ----------------------------------------------------------------------
DEFAULT_STOPWORDS = {
    "the", "is", "a", "an", "and", "of", "to", "in", "for", "on", "at",
    "by", "with", "as", "it", "this", "that", "be", "are", "was", "were",
    "or", "from", "but", "not", "have", "has", "had", "will", "would",
    "can", "could", "should", "we", "you", "your", "i", "he", "she",
    "they", "them", "his", "her", "their", "if", "then", "so", "into",
}


@dataclass
class DocumentInput:
    filename: str
    filepath: str
    content: str
    file_type: str
    modified_time: str
    document_id: Optional[int] = None  # None => new file, DB assigns id


class Indexer:
    """Builds and maintains a persistent SQLite inverted index."""

    def __init__(self, db_path: str = "search_index.db", stopwords: Iterable[str] = None):
        self.db_path = db_path
        self.stopwords = set(stopwords) if stopwords is not None else set(DEFAULT_STOPWORDS)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._create_tables()

    # ------------------------------------------------------------------
    # Schema (Step 8 / Step 9)
    # ------------------------------------------------------------------
    def _create_tables(self):
        cur = self.conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                document_id   INTEGER PRIMARY KEY AUTOINCREMENT,
                filename      TEXT NOT NULL,
                filepath      TEXT NOT NULL UNIQUE,
                file_type     TEXT NOT NULL,
                modified_time TEXT NOT NULL,
                content       TEXT NOT NULL DEFAULT ''
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS terms (
                term          TEXT NOT NULL,
                document_id   INTEGER NOT NULL,
                frequency     INTEGER NOT NULL,
                PRIMARY KEY (term, document_id),
                FOREIGN KEY (document_id) REFERENCES documents(document_id)
                    ON DELETE CASCADE
            )
        """)
        # Speeds up "find all docs containing term X" (search) and
        # "delete/re-index everything for document Y" (updates).
        cur.execute("CREATE INDEX IF NOT EXISTS idx_terms_term ON terms(term)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_terms_doc ON terms(document_id)")
        self.conn.commit()

    # ------------------------------------------------------------------
    # Step 2 + Step 4: clean + tokenize
    # ------------------------------------------------------------------
    @staticmethod
    def clean_text(text: str) -> str:
        text = text.lower()
        text = re.sub(r"[^\w\s]", " ", text)   # strip punctuation
        text = re.sub(r"\s+", " ", text).strip()  # collapse whitespace
        return text

    def tokenize(self, text: str) -> List[str]:
        cleaned = self.clean_text(text)
        return cleaned.split() if cleaned else []

    # ------------------------------------------------------------------
    # Step 3: remove stop words
    # ------------------------------------------------------------------
    def remove_stopwords(self, tokens: List[str]) -> List[str]:
        return [t for t in tokens if t not in self.stopwords]

    # ------------------------------------------------------------------
    # Step 5: word frequency per document
    # ------------------------------------------------------------------
    @staticmethod
    def compute_term_frequencies(tokens: List[str]) -> Dict[str, int]:
        freqs: Dict[str, int] = {}
        for tok in tokens:
            freqs[tok] = freqs.get(tok, 0) + 1
        return freqs

    # ------------------------------------------------------------------
    # Step 10 helpers: new vs modified vs unchanged
    # ------------------------------------------------------------------
    def get_existing_document(self, filepath: str) -> Optional[sqlite3.Row]:
        self.conn.row_factory = sqlite3.Row
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM documents WHERE filepath = ?", (filepath,))
        return cur.fetchone()

    def needs_reindex(self, filepath: str, modified_time: str) -> bool:
        """True if file is new OR its modified_time changed since last index."""
        row = self.get_existing_document(filepath)
        if row is None:
            return True  # new file
        return row["modified_time"] != modified_time

    # ------------------------------------------------------------------
    # Remove a document's old index entries (used on modify/delete)
    # ------------------------------------------------------------------
    def remove_document_index(self, document_id: int):
        cur = self.conn.cursor()
        cur.execute("DELETE FROM terms WHERE document_id = ?", (document_id,))
        cur.execute("DELETE FROM documents WHERE document_id = ?", (document_id,))
        self.conn.commit()

    def remove_document_by_filepath(self, filepath: str):
        row = self.get_existing_document(filepath)
        if row is not None:
            self.remove_document_index(row["document_id"])

    # ------------------------------------------------------------------
    # MAIN PIPELINE: Step 1 -> Step 9 for one document
    # ------------------------------------------------------------------
    def index_document(self, doc: DocumentInput) -> int:
        """
        Runs the full pipeline for a single document and returns its
        document_id. Handles new files and re-indexing of modified files
        (old entries are wiped first so counts never double up).
        """
        existing = self.get_existing_document(doc.filepath)

        if existing is not None:
            # Modified file: wipe old term entries, but reuse the same
            # document_id and update its metadata row afterward.
            document_id = existing["document_id"]
            cur = self.conn.cursor()
            cur.execute("DELETE FROM terms WHERE document_id = ?", (document_id,))
            cur.execute(
                """UPDATE documents
                   SET filename = ?, file_type = ?, modified_time = ?, content = ?
                   WHERE document_id = ?""",
                (doc.filename, doc.file_type, doc.modified_time, doc.content, document_id),
            )
        else:
            # New file: insert metadata row (incl. content), get the assigned id.
            cur = self.conn.cursor()
            cur.execute(
                """INSERT INTO documents (filename, filepath, file_type, modified_time, content)
                   VALUES (?, ?, ?, ?, ?)""",
                (doc.filename, doc.filepath, doc.file_type, doc.modified_time, doc.content),
            )
            document_id = cur.lastrowid

        # Steps 2-5: clean -> tokenize -> remove stopwords -> count
        tokens = self.tokenize(doc.content)
        tokens = self.remove_stopwords(tokens)
        term_freqs = self.compute_term_frequencies(tokens)

        # Steps 6-7: build inverted index rows (doc frequency is derived
        # later via COUNT(DISTINCT document_id), not stored redundantly)
        cur.executemany(
            "INSERT INTO terms (term, document_id, frequency) VALUES (?, ?, ?)",
            [(term, document_id, freq) for term, freq in term_freqs.items()],
        )

        self.conn.commit()
        return document_id

    # ------------------------------------------------------------------
    # Step 10: reconcile against a fresh scan (handles deletions)
    # ------------------------------------------------------------------
    def sync(self, scanned_documents: List[DocumentInput]):
        """
        Call this once per full scan cycle. `scanned_documents` is the
        complete list of files Person 1's scanner currently finds.
        - New / modified files are (re)indexed.
        - Files no longer present on disk are removed from the index.
        """
        scanned_filepaths = {d.filepath for d in scanned_documents}

        # Remove documents that no longer exist on disk.
        cur = self.conn.cursor()
        cur.execute("SELECT document_id, filepath FROM documents")
        for document_id, filepath in cur.fetchall():
            if filepath not in scanned_filepaths:
                self.remove_document_index(document_id)

        # Index new/changed files only.
        for doc in scanned_documents:
            if self.needs_reindex(doc.filepath, doc.modified_time):
                self.index_document(doc)

    # ------------------------------------------------------------------
    # Data Person 3 (Search + TF-IDF) will query — indexer just exposes it
    # ------------------------------------------------------------------
    def get_term_frequency(self, term: str, document_id: int) -> int:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT frequency FROM terms WHERE term = ? AND document_id = ?",
            (term, document_id),
        )
        row = cur.fetchone()
        return row[0] if row else 0

    def get_document_frequency(self, term: str) -> int:
        """Number of documents containing `term`."""
        cur = self.conn.cursor()
        cur.execute(
            "SELECT COUNT(DISTINCT document_id) FROM terms WHERE term = ?", (term,)
        )
        return cur.fetchone()[0]

    def get_documents_for_term(self, term: str) -> List[int]:
        cur = self.conn.cursor()
        cur.execute("SELECT document_id FROM terms WHERE term = ?", (term,))
        return [row[0] for row in cur.fetchall()]

    def get_total_document_count(self) -> int:
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM documents")
        return cur.fetchone()[0]

    def get_document_metadata(self, document_id: int) -> Optional[sqlite3.Row]:
        self.conn.row_factory = sqlite3.Row
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM documents WHERE document_id = ?", (document_id,))
        return cur.fetchone()

    def get_document_content(self, document_id: int) -> Optional[str]:
        """
        Returns the full extracted text for a document, so Person 3 can
        locate a matching query term and slice out a snippet around it.
        This module does not build the snippet itself.
        """
        cur = self.conn.cursor()
        cur.execute("SELECT content FROM documents WHERE document_id = ?", (document_id,))
        row = cur.fetchone()
        return row[0] if row else None

    def close(self):
        self.conn.close()


# ----------------------------------------------------------------------
# Demo / smoke test
# ----------------------------------------------------------------------
if __name__ == "__main__":
    indexer = Indexer(db_path="demo_index.db")

    docs = [
        DocumentInput(
            filename="OS_Unit3.md",
            filepath=r"C:\Users\Student\Documents\OS\OS_Unit3.md",
            content="Deadlock, Prevention & Resource Allocation! The process waits for a resource.",
            file_type=".md",
            modified_time="2026-08-20T10:00:00",
        ),
        DocumentInput(
            filename="notes.txt",
            filepath=r"C:\Users\Student\Documents\notes.txt",
            content="Python resource management and deadlock avoidance in python programs.",
            file_type=".txt",
            modified_time="2026-08-21T09:30:00",
        ),
    ]

    for d in docs:
        doc_id = indexer.index_document(d)
        print(f"Indexed '{d.filename}' as document_id={doc_id}")

    print("\n--- Stats Person 3 will use ---")
    for term in ["deadlock", "resource", "python"]:
        df = indexer.get_document_frequency(term)
        print(f"'{term}': document_frequency={df}, "
              f"in docs={indexer.get_documents_for_term(term)}")

    print(f"\nTotal documents indexed: {indexer.get_total_document_count()}")

    print("\n--- Content retrieval (for Person 3's snippet generation) ---")
    content = indexer.get_document_content(1)
    print(f"document_id=1 content: {content!r}")

    indexer.close()
