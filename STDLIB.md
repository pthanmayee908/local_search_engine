# STDLIB.md

## Standard Library Usage

### About This Project

Our project, **Local Search Engine**, is built using Python and the Python Standard Library.

The main goal of this project is to help users find files when they remember some content from inside the file but do not remember the file name or location.

For this hackathon, we decided not to use third-party Python packages. Instead, we used modules already available in Python and implemented the main search functionality ourselves.

Our project has **zero third-party runtime dependencies**.

---

## Why We Used the Python Standard Library

Normally, a project like this could use different external libraries for:

* searching;
* database storage;
* file handling;
* command-line interfaces;
* testing;
* logging.

Instead of installing those packages, we explored what Python already provides.

This was one of the main challenges of the project. As a team of four second-year students, we wanted to build something useful while learning how core features such as file indexing and searching actually work.

---

## Standard Library Replacements

### 1. Search Engine

**Normally, we could use:**

* Whoosh
* Elasticsearch
* Apache Solr

**Instead, we implemented:**

A custom inverted index.

An inverted index stores a relationship between words and the documents that contain them.

For example:

```text
fourier → [document_1, document_5]
series  → [document_1, document_8]
sine    → [document_1, document_3]
```

This allows the program to search for documents without opening and reading every file every time a user searches.

---

### 2. Database Storage

**Normally, we could use:**

* SQLAlchemy
* An external database system

**Instead, we used:**

```python
sqlite3
```

SQLite is available through Python's standard library.

We use it to store information related to indexed files and search data so that the application can keep its data between program runs.

---

### 3. File and Folder Handling

**Normally, we could use an external file utility library.**

**Instead, we used:**

```python
os
pathlib
```

These modules help us:

* access files and folders;
* traverse directories;
* identify file paths;
* work with file extensions.

This is important because our project needs to discover files without requiring the user to remember where every file is located.

---

### 4. Text Processing

**Normally, we could use an NLP library.**

**Instead, we used:**

```python
re
```

along with Python's built-in string operations.

We use these to process text and search queries by performing operations such as:

* converting text to a common case;
* separating text into words;
* removing unnecessary characters;
* preparing words for indexing.

---

### 5. Relevance and Ranking

**Normally, we could use:**

* NumPy
* scikit-learn

**Instead, we used:**

```python
math
collections
```

along with our own Python logic.

Our search system calculates which documents are more relevant to a user's search query and displays better matches first.

---

### 6. Command-Line Interface

**Normally, we could use:**

* Click
* Typer

**Instead, we use:**

Python's built-in functionality such as:

```python
input()
print()
```

and standard command-line tools where required.

This keeps the application simple and avoids adding an external CLI dependency.

---

### 7. Data Storage and Serialization

**Normally, we could use an external JSON library.**

**Instead, we used:**

```python
json
```

The built-in `json` module can be used to store and read structured data when needed.

---

### 8. File Hashing

**Normally, an external utility could be used for hashing.**

**Instead, we use:**

```python
hashlib
```

This module can be used to create hashes for files or content when required by the indexing process.

---

### 9. Logging

**Normally, we could use:**

* Loguru

**Instead, we use:**

```python
logging
```

Python's built-in logging module can be used to record:

* errors;
* warnings;
* indexing information;
* debugging messages.

---

### 10. Automated Testing

**Normally, we could use:**

* pytest

**Instead, we use:**

```python
unittest
```

The Python Standard Library already includes a testing framework.

We use tests to check important parts of the project such as:

* file discovery;
* indexing;
* searching;
* ranking;
* error handling.

Tests can be run using:

```bash
python -m unittest discover
```

---

## Standard Library Modules Used

Depending on the final implementation, our project uses standard-library modules such as:

```text
os
pathlib
sqlite3
re
math
collections
json
hashlib
logging
unittest
argparse
```

These modules allow us to implement the main functionality of our application without installing third-party packages.

---

## What We Learned

This project helped us understand that many features usually provided by external packages can also be implemented using Python's Standard Library.

Instead of treating a search engine as a black box, we worked with the basic ideas behind it, including:

* file discovery;
* text processing;
* inverted indexes;
* storing indexed data;
* searching;
* ranking results.

The goal of our project was not to recreate a large commercial search engine. Our goal was to build a useful local application and understand how its core functionality works.

---

## Dependency Proof

The project is designed to have:

```text
Third-party runtime dependencies: 0
```

The application does not require external Python packages to run.

Our dependency manifest is intentionally empty as required by the hackathon.

The project can be run using Python and the code included in this repository.

---

## Summary

For this project, our four-member team chose to rely on the Python Standard Library instead of third-party packages wherever possible.

Some of our main replacements are:

| Normally Used           | Our Approach                      |
| ----------------------- | --------------------------------- |
| Whoosh / Elasticsearch  | Custom inverted index             |
| SQLAlchemy              | `sqlite3`                         |
| Click / Typer           | Built-in Python CLI functionality |
| NLP libraries           | `re` and string operations        |
| NumPy / scikit-learn    | `math` and custom ranking logic   |
| External file utilities | `os` and `pathlib`                |
| External JSON libraries | `json`                            |
| Loguru                  | `logging`                         |
| pytest                  | `unittest`                        |

This project demonstrates how a useful application can be built by combining Python's built-in modules with custom logic, while keeping the project free from third-party runtime dependencies.
