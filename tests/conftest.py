"""
conftest.py
-----------
Shared pytest fixtures.

All fixtures that touch the filesystem use pytest's built-in
``tmp_path`` fixture so tests never read or write real files on the
developer's machine (with the sole harmless exception of
``utils.config`` creating ``~/.local_search_engine/`` the first time
it is imported anywhere in the process — that directory is part of
the application's normal, documented behaviour, and every test below
passes an explicit ``db_path`` so no test data is ever written there).
"""

import sys
import zipfile
from pathlib import Path

import pytest

# Make the project root importable regardless of where pytest is
# invoked from (e.g. `pytest`, `pytest tests/`, `python -m pytest`).
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from indexer.indexer import DocumentInput, Indexer  # noqa: E402
from search.search_engine import SearchEngine  # noqa: E402


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    """A fresh, unique SQLite database path for one test."""
    return str(tmp_path / "test_index.db")


@pytest.fixture
def indexer(db_path: str):
    """A fresh Indexer bound to an isolated, temporary database."""
    idx = Indexer(db_path=db_path)
    yield idx
    idx.close()


@pytest.fixture
def search_engine(indexer):
    """A SearchEngine wired to the ``indexer`` fixture."""
    return SearchEngine(indexer)


@pytest.fixture
def sample_documents():
    """A small, deterministic corpus used across several test modules."""
    return [
        DocumentInput(
            filename="deadlock.md",
            filepath="/docs/deadlock.md",
            content=(
                "Deadlock prevention and resource allocation. "
                "A process waits for a resource held by another process."
            ),
            file_type=".md",
            modified_time="2026-01-01T10:00:00",
        ),
        DocumentInput(
            filename="python_notes.txt",
            filepath="/docs/python_notes.txt",
            content=(
                "Python resource management and deadlock avoidance "
                "in concurrent python programs."
            ),
            file_type=".txt",
            modified_time="2026-01-02T09:30:00",
        ),
        DocumentInput(
            filename="recipe.txt",
            filepath="/docs/recipe.txt",
            content="Bake the cake for forty minutes at high temperature.",
            file_type=".txt",
            modified_time="2026-01-03T08:00:00",
        ),
    ]


@pytest.fixture
def populated_indexer(indexer, sample_documents):
    """An Indexer that already has ``sample_documents`` indexed."""
    for doc in sample_documents:
        indexer.index_document(doc)
    return indexer


@pytest.fixture
def make_docx():
    """Factory fixture: build a minimal, valid .docx file at a given path."""

    def _make_docx(path: Path, paragraphs):
        document_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w='
            '"http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            "<w:body>"
        )
        for paragraph in paragraphs:
            document_xml += f"<w:p><w:r><w:t>{paragraph}</w:t></w:r></w:p>"
        document_xml += "</w:body></w:document>"

        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("word/document.xml", document_xml)

        return path

    return _make_docx
