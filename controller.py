"""
controller.py
--------------
Member 4: Integration Layer

Connects:
    scanner.scanner
    indexer.indexer
    search.search_engine
    storage.database
    utils

The controller is the bridge between all modules.
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


# ==============================================================
# INDEX RUN SUMMARY
# ==============================================================

@dataclass
class IndexRunSummary:
    """Information about one indexing run."""

    files_discovered: int
    files_indexed: int
    files_skipped: int
    errors: int
    duration_seconds: float


# ==============================================================
# INTEGRATION ERROR
# ==============================================================

class IntegrationError(Exception):
    """Error raised when modules cannot be connected properly."""
    pass


# ==============================================================
# SEARCH ENGINE CONTROLLER
# ==============================================================

class SearchEngineController:
    """
    Main integration layer.

    CLI talks to this class instead of directly talking
    to scanner, indexer, search engine or database.
    """

    def __init__(self, db_path: str = str(DB_PATH)):

        self.db_path = db_path

        self._indexer: Optional[Indexer] = None

        self._search_engine: Optional[SearchEngine] = None

    # ==========================================================
    # INDEXER
    # ==========================================================

    @property
    def indexer(self) -> Indexer:

        if self._indexer is None:

            try:
                self._indexer = Indexer(
                    db_path=self.db_path
                )

            except Exception as exc:

                logger.exception(
                    "Failed to open index database"
                )

                raise IntegrationError(
                    "Could not open the local search database."
                ) from exc

        return self._indexer

    # ==========================================================
    # SEARCH ENGINE
    # ==========================================================

    @property
    def search_engine(self) -> SearchEngine:

        if self._search_engine is None:

            self._search_engine = SearchEngine(
                self.indexer
            )

        return self._search_engine

    # ==========================================================
    # DATABASE STATUS
    # ==========================================================

    def index_exists(self) -> bool:

        try:
            return database.database_exists(
                self.db_path
            )

        except Exception:

            return False

    # ==========================================================
    # DOCUMENT COUNT
    # ==========================================================

    def document_count(self) -> int:

        try:

            return self.indexer.get_total_document_count()

        except Exception:

            logger.exception(
                "Failed to read document count"
            )

            return 0

    # ==========================================================
    # SCANNER -> INDEXER ADAPTER
    # ==========================================================

    @staticmethod
    def _to_document_input(
        file_path: Path,
        metadata: dict,
        text: str,
    ) -> DocumentInput:

        modified_iso = datetime.fromtimestamp(
            float(metadata["modified"])
        ).isoformat()

        return DocumentInput(

            filename=file_path.name,

            filepath=str(file_path),

            content=text,

            file_type=str(
                metadata["extension"]
            ),

            modified_time=modified_iso,
        )

    # ==========================================================
    # ROOT DIRECTORIES
    # ==========================================================

    def _scan_root_directories(self) -> List[Path]:

        roots = scanner.get_user_directories()

        extra_directories = load_extra_directories()

        for directory in extra_directories:

            if directory not in roots:

                roots.append(directory)

        return roots

    # ==========================================================
    # INDEX / UPDATE
    # ==========================================================

    def run_index(
        self,
        progress_callback: Optional[
            Callable[[int, int, int], None]
        ] = None,
    ) -> IndexRunSummary:

        started_at = time.time()

        discovered = 0
        errors = 0

        documents: List[DocumentInput] = []

        # ------------------------------------------------------
        # STEP 1: SCAN FILES
        # ------------------------------------------------------

        try:

            roots = self._scan_root_directories()

            logger.info(
                "Scanning directories: %s",
                roots
            )

            for file_path, metadata, text in scanner.scan_and_extract(
                roots
            ):

                discovered += 1

                try:

                    document = self._to_document_input(
                        file_path,
                        metadata,
                        text
                    )

                    documents.append(document)

                except Exception:

                    errors += 1

                    logger.exception(
                        "Could not convert file: %s",
                        file_path
                    )

                if (
                    progress_callback
                    and discovered % 25 == 0
                ):

                    progress_callback(
                        discovered,
                        len(documents),
                        errors
                    )

        except Exception as exc:

            logger.exception(
                "Scanning failed"
            )

            raise IntegrationError(
                "Something went wrong while scanning your files."
            ) from exc

        # ------------------------------------------------------
        # STEP 2: DETERMINE WHICH FILES NEED INDEXING
        # ------------------------------------------------------

        files_to_index = 0
        files_skipped = 0

        for document in documents:

            try:

                if self.indexer.needs_reindex(
                    document.filepath,
                    document.modified_time
                ):

                    files_to_index += 1

                else:

                    files_skipped += 1

            except Exception:

                errors += 1

                logger.exception(
                    "Could not check file: %s",
                    document.filepath
                )

        # ------------------------------------------------------
        # STEP 3: SYNCHRONIZE INDEX
        # ------------------------------------------------------

        try:

            self.indexer.sync(
                documents
            )

        except Exception as exc:

            logger.exception(
                "Index synchronization failed"
            )

            raise IntegrationError(
                "Could not save the search index."
            ) from exc

        # ------------------------------------------------------
        # STEP 4: CALCULATE DURATION
        # ------------------------------------------------------

        duration = time.time() - started_at

        # ------------------------------------------------------
        # STEP 5: SAVE HISTORY
        # ------------------------------------------------------

        try:

            database.record_index_run(

                self.db_path,

                started_at=started_at,

                duration_seconds=duration,

                files_discovered=discovered,

                files_indexed=files_to_index,

                files_skipped=files_skipped,

                errors=errors,
            )

        except Exception:

            logger.exception(
                "Could not save index history"
            )

        # ------------------------------------------------------
        # STEP 6: RETURN SUMMARY
        # ------------------------------------------------------

        return IndexRunSummary(

            files_discovered=discovered,

            files_indexed=files_to_index,

            files_skipped=files_skipped,

            errors=errors,

            duration_seconds=duration,
        )

    # ==========================================================
    # SEARCH
    # ==========================================================

    def search(
        self,
        query: str,
        limit: int = DEFAULT_RESULT_LIMIT,
    ) -> List[SearchResult]:

        if not query or not query.strip():

            return []

        try:

            return self.search_engine.search(

                query.strip(),

                limit=limit
            )

        except Exception as exc:

            logger.exception(
                "Search failed: %s",
                query
            )

            raise IntegrationError(
                "Something went wrong while searching."
            ) from exc

    # ==========================================================
    # STATISTICS
    # ==========================================================

    def get_statistics(self) -> dict:

        stats = {

            "documents_indexed": 0,

            "unique_terms": 0,

            "database_size_bytes": 0,

            "last_run": None,
        }

        try:

            if not self.index_exists():

                return stats

            stats["documents_indexed"] = (
                self.document_count()
            )

            stats["unique_terms"] = (
                database.get_unique_term_count(
                    self.db_path
                )
            )

            stats["database_size_bytes"] = (
                database.get_database_size_bytes(
                    self.db_path
                )
            )

            stats["last_run"] = (
                database.get_last_run(
                    self.db_path
                )
            )

        except Exception:

            logger.exception(
                "Failed to get statistics"
            )

        return stats

    # ==========================================================
    # CLOSE
    # ==========================================================

    def close(self) -> None:

        if self._indexer is not None:

            try:

                self._indexer.close()

            except Exception:

                logger.exception(
                    "Error closing index database"
                )