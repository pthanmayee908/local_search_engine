# local_search_engine
> **An offline, zero-dependency search engine that helps users find files by what they remember from inside them—not by their filename or location.**

## Overview

Local Search Engine is a Python application designed for users who remember part of a document's content but cannot remember its filename, folder, or exact location.

The application discovers supported local files, extracts searchable content, builds a persistent search index, and returns ranked results for user queries.

For example, a student may remember that a document discussed **Fourier series, periodic functions, sine coefficients, and cosine coefficients**, but may not remember what the file was named or where it was saved. Instead of manually searching through folders, the user can search using the content they remember.

### Why use it?

* Search files using remembered content.
* Find files even when their name and location are forgotten.
* Work locally without relying on cloud services.
* Use a persistent index instead of scanning every file for every query.
* Run without third-party Python runtime dependencies.

### Why might you not use it?

This project is not intended to replace enterprise-scale search platforms or provide AI-powered semantic search. Its purpose is to provide a lightweight and useful local search system built using Python's standard library.

---

## Example Usage

Suppose you remember that one of your documents contained notes about Fourier series.

Run the application:

```bash
python main.py
```

Enter a search query:

```text
fourier series sine cosine coefficients
```

The application may return ranked results similar to:

```text
================================================================
SEARCH RESULTS
================================================================

[1] Mathematics_Unit_4_Notes.txt

    Relevance : 94.2%
    Type      : .txt

    Location:
    /home/user/Documents/Mathematics/

    Match:
    "...a Fourier series represents a periodic function as a
    combination of sine and cosine terms. The Fourier
    coefficients determine the contribution of each component..."

----------------------------------------------------------------

[2] Signals_and_Systems_Revision.txt

    Relevance : 81.5%

    Location:
    /home/user/Desktop/Study_Material/

    Match:
    "...Fourier coefficients can be calculated to express a
    periodic signal using sine and cosine functions..."
```

The user can identify the required document even though they did not remember its filename or location.

---

## Getting Started

### Prerequisites

* Python 3.x
* No third-party Python runtime dependencies

### Installation

Clone the repository:

```bash
git clone <REPOSITORY-URL>
cd local-search-engine
```

No dependency installation is required for the application's runtime functionality.

### Run

From the project root:

```bash
python main.py
```

This is the project's one-command run method.

### Run Tests

The project uses Python's built-in `unittest` framework:

```bash
python -m unittest discover
```

### Project Resources

| Resource                        | Location            |
| ------------------------------- | ------------------- |
| Source Code                     | This repository     |
| Issue Tracker                   | GitHub Issues       |
| Documentation                   | `README.md`         |
| Standard Library Dependency Log | `STDLIB.md`         |
| Tests                           | `tests/`            |
| Demo Video                      | `<DEMO-VIDEO-LINK>` |

No server or daemon process is required because the application is designed as a local program.

---

## Design Goals

### Zero Dependencies

The application is built using Python's standard library and custom implementations rather than third-party runtime packages.

### Local-First

Files are processed locally. The core functionality does not require a cloud service, external search server, or external AI API.

### Useful and Lightweight

The project focuses on one practical problem:

> **Finding a file when the user remembers its contents but not its name or location.**

### Maintainable

The application separates major responsibilities such as file discovery, indexing, storage, search, and user interaction.

### Efficient Search

Files are indexed so that searches can use stored index information rather than opening and reading every file again for every query.

---

## Detailed Usage

### How It Works

The application follows the workflow below:

```text
Accessible Local Files
        │
        ▼
File Discovery
        │
        ▼
Text Extraction
        │
        ▼
Token Processing
        │
        ▼
Custom Inverted Index
        │
        ▼
Persistent Local Storage
        │
        ▼
User Search Query
        │
        ▼
Index Lookup
        │
        ▼
Relevance Ranking
        │
        ▼
Ranked Results
```

### File Discovery

The application traverses accessible directories and identifies supported files.

For each file, relevant information can be recorded, including:

* Filename
* File path
* File type
* Modification information

The user does not need to remember the location of every file. Files are discovered during the indexing process.

### Search Index

The search engine uses an inverted index.

Conceptually:

```text
fourier
    ├── document 12
    ├── document 31
    └── document 44

sine
    ├── document 12
    └── document 27

cosine
    ├── document 12
    └── document 27
```

This maps searchable terms to the documents containing those terms.

### Searching

When a user enters:

```text
fourier series sine cosine
```

the application:

1. Processes the query.
2. Looks up the query terms in the index.
3. Retrieves relevant documents.
4. Calculates relevance scores.
5. Ranks the results.
6. Displays matching documents with their location and relevant content.

### Persistent Storage

The project uses Python's built-in `sqlite3` module for persistent local storage.

The stored information can include:

* Document metadata
* File paths
* Indexed terms
* Term frequencies
* Document frequencies
* Indexing information

This allows the search index to persist between application runs.

### Configuration

The application is designed to access only files and directories available to the current user and does not bypass operating-system permissions.

Supported directories and file types depend on the final implementation.

---

## Zero-Dependency Design

A major objective of this project is to demonstrate how useful search functionality can be implemented without third-party Python runtime dependencies.

The project uses Python's standard library and custom implementations for functionality such as:

| Requirement              | Implementation                      |
| ------------------------ | ----------------------------------- |
| File system access       | `os`, `pathlib`                     |
| Persistent local storage | `sqlite3`                           |
| Text processing          | `re` and built-in string operations |
| Search index             | Custom inverted index               |
| Relevance calculations   | Custom logic using `math`           |
| Logging                  | `logging`                           |
| File hashing             | `hashlib`                           |
| Structured data          | `json`                              |
| XML processing           | `xml.etree.ElementTree`             |
| Archive processing       | `zipfile`                           |
| Testing                  | `unittest`                          |

The detailed dependency proof and standard-library substitutions are documented in `STDLIB.md`.

The application intentionally avoids third-party runtime dependencies.

---

## Comparable Tools

Local Search Engine shares concepts with several types of search systems:

| Category                 | Comparison                                                                                             |
| ------------------------ | ------------------------------------------------------------------------------------------------------ |
| Desktop search tools     | Both help users locate files using indexed information                                                 |
| Full-text search engines | Both use indexing and query processing                                                                 |
| Elasticsearch            | Designed for distributed and enterprise-scale search; this project focuses on lightweight local search |
| Apache Solr              | Provides large-scale search capabilities; this project implements a smaller local alternative          |
| Whoosh                   | Provides Python search functionality; this project implements its own core search logic                |

This project is not intended to reproduce every feature of these systems. Its purpose is to implement a useful subset of search-engine functionality using only the Python Standard Library.

---

## Developer Information

### Important Components

**File Scanner**
Discovers accessible files and collects relevant file information.

**Text Extraction**
Reads supported files and extracts searchable text.

**Indexer**
Processes text and builds the searchable inverted index.

**Storage Layer**
Persists document and index information locally.

**Search Engine**
Processes queries, retrieves matching documents, and ranks results.

**Command-Line Interface**
Provides the user interface for interacting with the application.

### Project Structure

```text
local-search-engine/
├── main.py
├── controller.py
├── cli/
├── scanner/
├── indexer/
├── search/
├── storage/
├── utils/
├── tests/
├── README.md
├── STDLIB.md
└── requirements.txt
```

### Limitations and Known Issues

The application's capabilities depend on the final implementation. General limitations may include:

* Only implemented file types can be indexed.
* Files must be indexed before their contents can be searched.
* Protected or inaccessible locations cannot be scanned.
* Search quality depends on text extraction and ranking logic.
* Image and video content is not searched unless explicitly implemented.
* Large file collections may require additional indexing time.

### Performance

The application uses an index-based search approach.

Without an index:

```text
Search Query
    ↓
Read File 1
Read File 2
Read File 3
    ↓
Continue through all files
```

With an inverted index:

```text
Search Query
    ↓
Look Up Query Terms
    ↓
Retrieve Relevant Documents
    ↓
Rank Results
```

This reduces the need to repeatedly read every indexed document during each search.

Performance depends on the number and size of files, storage hardware, file formats, and the final index implementation.

### Testing

The project uses Python's built-in `unittest` framework.

The test suite covers major functionality including:

* File discovery
* Text extraction
* Token processing
* Index construction
* Search queries
* Relevance ranking
* Empty results
* Error handling
* Component integration

Run all tests with:

```bash
python -m unittest discover
```

---

## Colophon

### Credits

Developed by a four-member team for the Zero-Dependency Hackathon.

The project uses Python's standard library and custom implementations for its core functionality.

### Contributing

Contributions should preserve the project's zero-dependency design principles.

Before submitting changes:

1. Do not introduce third-party runtime dependencies.
2. Follow the existing project structure and coding style.
3. Add or update tests when changing functionality.
4. Update `STDLIB.md` when adding a meaningful standard-library substitution.

### References

The project is based on established information-retrieval concepts, including:

* Inverted indexes
* Term frequency
* Document frequency
* Relevance ranking
* Persistent local storage

Standard-library implementation details and dependency substitutions are documented in `STDLIB.md`.

---

## Core Idea

Traditional file search often starts with:

> **Where did I save this file?**

Local Search Engine starts with:

> **What do I remember from inside the file?**

By indexing document contents and storing searchable information locally, the application helps users find files based on remembered content rather than remembered filenames or locations.
