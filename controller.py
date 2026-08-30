"""
controller.py
--------------
Member 4's integration layer.

Wires together, unchanged:
    scanner.scanner          (Member 1: discovery + text extraction)
    indexer.indexer.Indexer  (Member 2: inverted index + storage)
    search.search_engine     (Member 3: TF-IDF ranking + snippets)

This module contains the ONLY adapter code needed to make Member 1's
output shape match Member 2's expected input shape (a small dataclass
conversion — no algorithm from any member is reimplemented here).
"""

import logging
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional

from scanner import scanner
from indexer.indexer import Indexer, DocumentInput
from search.search_engine import SearchEngine, SearchResult
from storage import database
from utils.config import DB_PATH, DEFAULT_RESULT_LIMIT
from utils.helpers import load_extra_directories

logger = logging.getLogger("local_search_engine")


@dataclass
class IndexRunSummary:
    """Result of one Index/Update run, for the CLI to display."""
    files_discovered: int
    files_indexed: int
    files_skipped: int
    errors: int
    duration_seconds: float


class IntegrationError(Exception):
    """Raised for integration-layer problems the CLI should show nicely."""


class SearchEngineController:
    """
    Single entry point the CLI talks to. Owns the Indexer connection and
    the SearchEngine instance, and knows how to adapt Member 1's scan
    results into Member 2's DocumentInput objects.
    """

    def __init__(self, db_path: str = str(DB_PATH)):
        self.db_path = db_path
        self._indexer: Optional[Indexer] = None
        self._search_engine: Optional[SearchEngine] = None

    # ------------------------------------------------------------------
    # Lazy connection so a missing/empty DB never crashes startup.
    # ------------------------------------------------------------------
    @property
    def indexer(self) -> Indexer:
        if self._indexer is None:
            try:
                self._indexer = Indexer(db_path=self.db_path)
            except Exception as exc:  # sqlite3.Error and friends
                logger.exception("Failed to open index database")
                raise IntegrationError(
                    "Could not open the local search index database. "
                    "Check that the application folder is writable."
                ) from exc
        return self._indexer

    @property
    def search_engine(self) -> SearchEngine:
        if self._search_engine is None:
            self._search_engine = SearchEngine(self.indexer)
        return self._search_engine

    def index_exists(self) -> bool:
        return database.database_exists(self.db_path)

    def document_count(self) -> int:
        try:
            return self.indexer.get_total_document_count()
        except Exception:
            logger.exception("Failed to read document count")
            return 0

    # ------------------------------------------------------------------
    # ADAPTER: Member 1's (Path, metadata dict, text) -> Member 2's DocumentInput
    # ------------------------------------------------------------------
    @staticmethod
    def _to_document_input(file_path: Path, metadata: dict, text: str) -> DocumentInput:
        modified_iso = datetime.fromtimestamp(metadata["modified"]).isoformat()
        return DocumentInput(
            filename=file_path.name,
            filepath=str(file_path),
            content=text,
            file_type=metadata["extension"],
            modified_time=modified_iso,
        )

    def _scan_root_directories(self) -> List[Path]:
        """Member 1's default user directories plus any user-configured extras."""
        roots = scanner.get_user_directories()
        roots.extend(load_extra_directories())
        return roots

    # ------------------------------------------------------------------
    # INDEXING / UPDATING
    # ------------------------------------------------------------------
    def run_index(
        self,
        progress_callback: Optional[Callable[[int, int, int], None]] = None,
    ) -> IndexRunSummary:
        """
        Scan the configured directories (Member 1), convert results
        (adapter), and sync them into the index (Member 2).

        Works for both the initial scan and "Update Index": Member 2's
        `sync()` already only re-tokenizes new/modified files and drops
        deleted ones, so this single method safely serves both menu
        options without ever rebuilding the whole index from scratch.

        progress_callback(discovered, indexed_so_far, errors) is called
        periodically so the CLI can show liveliness on large scans.
        """
        started_at = time.time()
        discovered = 0
        errors = 0
        documents: List[DocumentInput] = []

        try:
            for file_path, metadata, text in scanner.scan_and_extract(
                self._scan_root_directories()
            ):
                discovered += 1
                try:
                    documents.append(self._to_document_input(file_path, metadata, text))
                except Exception:
                    # A single malformed record should never abort the scan.
                    errors += 1
                    logger.exception("Failed to adapt scanned file: %s", file_path)

                if progress_callback and discovered % 25 == 0:
                    progress_callback(discovered, len(documents), errors)
        except Exception as exc:
            logger.exception("Scanning failed")
            raise IntegrationError(
                "Something went wrong while scanning your files. "
                "See the log for details; no changes were saved."
            ) from exc

        # Figure out how many are genuinely new/changed vs. already up to date,
        # purely for the summary the user sees (sync() recomputes this itself).
        already_indexed_unchanged = 0
        to_index = 0
        for doc in documents:
            try:
                if self.indexer.needs_reindex(doc.filepath, doc.modified_time):
                    to_index += 1
                else:
                    already_indexed_unchanged += 1
            except Exception:
                errors += 1
                logger.exception("Failed to check reindex status for %s", doc.filepath)

        try:
            self.indexer.sync(documents)
        except Exception as exc:
            logger.exception("Failed to write to the index")
            raise IntegrationError(
                "Could not save the index to disk. "
                "Check available disk space and folder permissions."
            ) from exc

        duration = time.time() - started_at

        try:
            database.record_index_run(
                self.db_path,
                started_at=started_at,
                duration_seconds=duration,
                files_discovered=discovered,
                files_indexed=to_index,
                files_skipped=already_indexed_unchanged,
                errors=errors,
            )
        except Exception:
            # Stats history is best-effort; never fail the indexing run over it.
            logger.exception("Failed to record index run history")

        return IndexRunSummary(
            files_discovered=discovered,
            files_indexed=to_index,
            files_skipped=already_indexed_unchanged,
            errors=errors,
            duration_seconds=duration,
        )

    # ------------------------------------------------------------------
    # SEARCH
    # ------------------------------------------------------------------
    def search(self, query: str, limit: int = DEFAULT_RESULT_LIMIT) -> List[SearchResult]:
        if not query or not query.strip():
            return []
        try:
            return self.search_engine.search(query.strip(), limit=limit)
        except Exception as exc:
            logger.exception("Search failed for query: %s", query)
            raise IntegrationError(
                "Something went wrong while searching. Please try again."
            ) from exc

    # ------------------------------------------------------------------
    # STATISTICS
    # ------------------------------------------------------------------
    def get_statistics(self) -> dict:
        stats = {
            "documents_indexed": 0,
            "unique_terms": 0,
            "database_size_bytes": 0,
            "last_run": None,
        }
        if not self.index_exists():
            return stats

        stats["documents_indexed"] = self.document_count()
        stats["unique_terms"] = database.get_unique_term_count(self.db_path)
        stats["database_size_bytes"] = database.get_database_size_bytes(self.db_path)
        stats["last_run"] = database.get_last_run(self.db_path)
        return stats

    def close(self) -> None:
        if self._indexer is not None:
            try:
                self._indexer.close()
            except Exception:
                logger.exception("Error while closing the index database")
