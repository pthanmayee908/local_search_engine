"""
scanner.py – Zero‑dependency file scanner and text extractor.
Searches user directories, identifies supported file types,
and extracts plain text content using only the standard library.

>>> MEMBER 1 MODULE — UNCHANGED <<<
"""

import os
import re
import csv
import json
import zipfile
import html.parser
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Generator, Set

# -------------------------------------------------------------------
# 1. Supported file extensions
# -------------------------------------------------------------------
SUPPORTED_EXTENSIONS: Set[str] = {
    '.txt', '.py', '.md', '.csv', '.json',
    '.html', '.htm', '.xml', '.log', '.docx'
}

# System directories to skip (Windows examples)
SKIP_DIRS = {
    'Windows', 'Program Files', 'Program Files (x86)',
    'AppData', 'System32', 'System Volume Information',
    '$Recycle.Bin', 'msocache', 'PerfLogs'
}

# -------------------------------------------------------------------
# 2. Text extraction helpers
# -------------------------------------------------------------------

class HTMLTextExtractor(html.parser.HTMLParser):
    """Extract plain text from HTML/XML by removing tags."""
    def __init__(self):
        super().__init__()
        self.text = []

    def handle_data(self, data):
        self.text.append(data)

    def get_text(self):
        return ' '.join(self.text).strip()


def extract_text_from_docx(file_path: Path) -> str:
    """
    Extract text from a .docx file using zipfile and XML parsing.
    """
    try:
        with zipfile.ZipFile(file_path, 'r') as zf:
            # The main document is inside word/document.xml
            with zf.open('word/document.xml') as xml_file:
                tree = ET.parse(xml_file)
                root = tree.getroot()
                # Namespace: typically 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
                namespace = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
                # Find all text nodes (w:t)
                text_nodes = root.findall('.//w:t', namespace)
                text = ' '.join(node.text for node in text_nodes if node.text)
                return text.strip()
    except Exception as e:
        # If anything fails, we return empty string and let the caller handle.
        return ''


def extract_text_from_html(file_path: Path) -> str:
    """Strip HTML tags and return plain text."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        parser = HTMLTextExtractor()
        parser.feed(content)
        return parser.get_text()
    except UnicodeDecodeError:
        # fallback to latin-1
        with open(file_path, 'r', encoding='latin-1') as f:
            content = f.read()
        parser = HTMLTextExtractor()
        parser.feed(content)
        return parser.get_text()


def extract_text_from_csv(file_path: Path) -> str:
    """Read CSV and return all cell values as a space-separated string."""
    rows = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                rows.extend(row)   # flat list of strings
        return ' '.join(rows)
    except UnicodeDecodeError:
        # fallback to latin-1
        with open(file_path, 'r', encoding='latin-1') as f:
            reader = csv.reader(f)
            for row in reader:
                rows.extend(row)
        return ' '.join(rows)


def extract_text_from_json(file_path: Path) -> str:
    """Read JSON and return it as a compact string (for search purposes)."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        # Convert to string representation (keys and values)
        return json.dumps(data, ensure_ascii=False)
    except (UnicodeDecodeError, json.JSONDecodeError):
        # If not valid JSON, fallback to reading as text
        with open(file_path, 'r', encoding='latin-1') as f:
            return f.read()


def extract_text_from_text_file(file_path: Path) -> str:
    """Read as plain text (UTF-8 fallback to latin-1)."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except UnicodeDecodeError:
        with open(file_path, 'r', encoding='latin-1') as f:
            return f.read()


# -------------------------------------------------------------------
# 3. Main extraction dispatcher
# -------------------------------------------------------------------

def extract_text(file_path: Path) -> str:
    """
    Route file to the appropriate extractor based on extension.
    Returns an empty string if unsupported or error.
    """
    ext = file_path.suffix.lower()
    if ext == '.docx':
        return extract_text_from_docx(file_path)
    elif ext in ('.html', '.htm'):
        return extract_text_from_html(file_path)
    elif ext == '.csv':
        return extract_text_from_csv(file_path)
    elif ext == '.json':
        return extract_text_from_json(file_path)
    elif ext in ('.txt', '.py', '.md', '.xml', '.log'):
        return extract_text_from_text_file(file_path)
    else:
        return ''   # should never happen because we filter by extensions


# -------------------------------------------------------------------
# 4. Directory discovery & scanning
# -------------------------------------------------------------------

def get_user_directories() -> List[Path]:
    """
    Return a list of typical user personal folders.
    On Windows: Desktop, Documents, Downloads, and the home folder itself.
    On Linux/macOS: home folder + common subdirectories.
    """
    home = Path.home()
    dirs = [home]   # always include home

    # Common subdirectories
    common = ['Desktop', 'Documents', 'Downloads', 'Pictures', 'Music', 'Videos']
    for sub in common:
        p = home / sub
        if p.exists() and p.is_dir():
            dirs.append(p)

    # On Windows, also add OneDrive if present
    one_drive = home / 'OneDrive'
    if one_drive.exists() and one_drive.is_dir():
        dirs.append(one_drive)

    # Remove duplicates (if any)
    unique = []
    for d in dirs:
        if d not in unique:
            unique.append(d)
    return unique


def should_skip_dir(dir_path: Path) -> bool:
    """Check if a directory should be skipped (system, hidden, or protected)."""
    name = dir_path.name
    # Skip hidden directories (starting with '.')
    if name.startswith('.'):
        return True
    # Skip system directories
    if name in SKIP_DIRS:
        return True
    # Skip if no read access (will be caught later)
    return False


def scan_and_extract(
    root_dirs: Optional[List[Path]] = None
) -> Generator[Tuple[Path, Dict[str, object], str], None, None]:
    """
    Scan all directories in root_dirs (or use get_user_directories() if None).
    For each supported file, extract metadata and text, and yield
    (file_path, metadata_dict, text).

    Metadata dict contains: 'size', 'modified' (timestamp), 'extension'.
    """
    if root_dirs is None:
        root_dirs = get_user_directories()

    for root_dir in root_dirs:
        if not root_dir.exists() or not root_dir.is_dir():
            continue

        for dirpath, dirnames, filenames in os.walk(root_dir):
            # Filter out directories we want to skip (in-place modification)
            dirnames[:] = [d for d in dirnames if not should_skip_dir(Path(dirpath) / d)]

            for filename in filenames:
                file_path = Path(dirpath) / filename
                ext = file_path.suffix.lower()
                if ext not in SUPPORTED_EXTENSIONS:
                    continue

                # Get metadata
                try:
                    stat = file_path.stat()
                    metadata = {
                        'size': stat.st_size,
                        'modified': stat.st_mtime,   # timestamp
                        'extension': ext,
                    }
                except (OSError, PermissionError):
                    continue   # skip if we can't stat

                # Extract text
                try:
                    text = extract_text(file_path)
                except Exception as e:
                    # If extraction fails, we still yield empty text? Better to skip?
                    # We'll yield empty text and let the indexer decide.
                    text = ''

                # Yield even if text is empty (so the file gets indexed with no terms)
                yield file_path, metadata, text


# -------------------------------------------------------------------
# 5. Utility for the main program: get all files in one list (optional)
# -------------------------------------------------------------------

def get_all_files(root_dirs=None) -> List[Tuple[Path, Dict, str]]:
    """Convenience: collect all results into a list (use with caution for huge datasets)."""
    return list(scan_and_extract(root_dirs))


# -------------------------------------------------------------------
# 6. Demo / quick test
# -------------------------------------------------------------------
if __name__ == '__main__':
    # Demo mode - scans user's Desktop/Documents/Downloads
    print("Scanning user directories (Desktop, Documents, Downloads, OneDrive)...")
    for i, (path, meta, text) in enumerate(scan_and_extract()):
        if i >= 10:  # Show first 10 files
            break
        print(f"{path.name} | size={meta['size']} bytes | preview: {text[:80]}...")
        print("-" * 50)
    print("✅ Scanner ready for integration!")
