"""
scanner.py
----------
Member 1: File Discovery + Text Extraction

Zero third-party packages.
Uses Python standard library only.
"""

import os
import re
import csv
import json
import zipfile
import html.parser
import xml.etree.ElementTree as ET

from pathlib import Path
from typing import Dict, List, Optional, Tuple, Generator, Set


# ==============================================================
# SUPPORTED FILE TYPES
# ==============================================================

SUPPORTED_EXTENSIONS: Set[str] = {

    ".txt",
    ".py",
    ".md",
    ".csv",
    ".json",
    ".html",
    ".htm",
    ".xml",
    ".log",
    ".docx",
}


# ==============================================================
# DIRECTORIES TO SKIP
# ==============================================================

SKIP_DIRS = {

    "Windows",
    "Program Files",
    "Program Files (x86)",
    "AppData",
    "System32",
    "System Volume Information",
    "$Recycle.Bin",
    "msocache",
    "PerfLogs",
}


# ==============================================================
# HTML TEXT EXTRACTOR
# ==============================================================

class HTMLTextExtractor(html.parser.HTMLParser):

    def __init__(self):

        super().__init__()

        self.text = []

    def handle_data(self, data):

        self.text.append(data)

    def get_text(self):

        return " ".join(
            self.text
        ).strip()


# ==============================================================
# DOCX EXTRACTION
# ==============================================================

def extract_text_from_docx(
    file_path: Path
) -> str:

    try:

        with zipfile.ZipFile(
            file_path,
            "r"
        ) as zf:

            with zf.open(
                "word/document.xml"
            ) as xml_file:

                tree = ET.parse(
                    xml_file
                )

                root = tree.getroot()

                namespace = {

                    "w":
                    "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
                }

                text_nodes = root.findall(
                    ".//w:t",
                    namespace
                )

                text = " ".join(

                    node.text
                    for node in text_nodes
                    if node.text
                )

                return text.strip()

    except Exception:

        return ""


# ==============================================================
# HTML EXTRACTION
# ==============================================================

def extract_text_from_html(
    file_path: Path
) -> str:

    try:

        try:

            with open(
                file_path,
                "r",
                encoding="utf-8"
            ) as file:

                content = file.read()

        except UnicodeDecodeError:

            with open(
                file_path,
                "r",
                encoding="latin-1"
            ) as file:

                content = file.read()

        parser = HTMLTextExtractor()

        parser.feed(content)

        return parser.get_text()

    except Exception:

        return ""


# ==============================================================
# CSV EXTRACTION
# ==============================================================

def extract_text_from_csv(
    file_path: Path
) -> str:

    rows = []

    try:

        try:

            encoding = "utf-8"

            with open(
                file_path,
                "r",
                encoding=encoding
            ) as file:

                reader = csv.reader(file)

                for row in reader:

                    rows.extend(row)

        except UnicodeDecodeError:

            with open(
                file_path,
                "r",
                encoding="latin-1"
            ) as file:

                reader = csv.reader(file)

                for row in reader:

                    rows.extend(row)

        return " ".join(rows)

    except Exception:

        return ""


# ==============================================================
# JSON EXTRACTION
# ==============================================================

def extract_text_from_json(
    file_path: Path
) -> str:

    try:

        try:

            with open(
                file_path,
                "r",
                encoding="utf-8"
            ) as file:

                data = json.load(file)

        except UnicodeDecodeError:

            with open(
                file_path,
                "r",
                encoding="latin-1"
            ) as file:

                data = json.load(file)

        return json.dumps(
            data,
            ensure_ascii=False
        )

    except Exception:

        try:

            with open(
                file_path,
                "r",
                encoding="latin-1"
            ) as file:

                return file.read()

        except Exception:

            return ""


# ==============================================================
# NORMAL TEXT EXTRACTION
# ==============================================================

def extract_text_from_text_file(
    file_path: Path
) -> str:

    try:

        with open(
            file_path,
            "r",
            encoding="utf-8"
        ) as file:

            return file.read()

    except UnicodeDecodeError:

        try:

            with open(
                file_path,
                "r",
                encoding="latin-1"
            ) as file:

                return file.read()

        except Exception:

            return ""

    except Exception:

        return ""


# ==============================================================
# EXTRACTION DISPATCHER
# ==============================================================

def extract_text(
    file_path: Path
) -> str:

    extension = file_path.suffix.lower()

    if extension == ".docx":

        return extract_text_from_docx(
            file_path
        )

    if extension in {".html", ".htm"}:

        return extract_text_from_html(
            file_path
        )

    if extension == ".csv":

        return extract_text_from_csv(
            file_path
        )

    if extension == ".json":

        return extract_text_from_json(
            file_path
        )

    if extension in {
        ".txt",
        ".py",
        ".md",
        ".xml",
        ".log",
    }:

        return extract_text_from_text_file(
            file_path
        )

    return ""


# ==============================================================
# USER DIRECTORIES
# ==============================================================

def get_user_directories() -> List[Path]:

    home = Path.home()

    directories = [home]

    # Extra location such as OneDrive.
    # Only add it if it is not already inside
    # a directory that we are scanning separately.

    one_drive = home / "OneDrive"

    if (
        one_drive.exists()
        and one_drive.is_dir()
        and one_drive not in directories
    ):

        # Home is already being scanned,
        # so OneDrive does not need to be added again.

        pass

    return directories


# ==============================================================
# DIRECTORY FILTER
# ==============================================================

def should_skip_dir(
    dir_path: Path
) -> bool:

    name = dir_path.name

    if name.startswith("."):

        return True

    if name in SKIP_DIRS:

        return True

    return False


# ==============================================================
# MAIN SCANNER
# ==============================================================

def scan_and_extract(
    root_dirs: Optional[List[Path]] = None
) -> Generator[
    Tuple[Path, Dict[str, object], str],
    None,
    None
]:

    if root_dirs is None:

        root_dirs = get_user_directories()

    # Remove duplicate roots.
    unique_roots = []

    for root in root_dirs:

        root = Path(root)

        if root not in unique_roots:

            unique_roots.append(root)

    for root_dir in unique_roots:

        if (
            not root_dir.exists()
            or not root_dir.is_dir()
        ):

            continue

        for dirpath, dirnames, filenames in os.walk(
            root_dir
        ):

            current_dir = Path(dirpath)

            # Remove unwanted directories.
            dirnames[:] = [

                directory
                for directory in dirnames

                if not should_skip_dir(
                    current_dir / directory
                )
            ]

            for filename in filenames:

                file_path = (
                    current_dir / filename
                )

                extension = (
                    file_path.suffix.lower()
                )

                if extension not in SUPPORTED_EXTENSIONS:

                    continue

                # --------------------------------------------------
                # FILE METADATA
                # --------------------------------------------------

                try:

                    stat = file_path.stat()

                    metadata = {

                        "size":
                        stat.st_size,

                        "modified":
                        stat.st_mtime,

                        "extension":
                        extension,
                    }

                except (
                    OSError,
                    PermissionError,
                ):

                    continue

                # --------------------------------------------------
                # EXTRACT TEXT
                # --------------------------------------------------

                try:

                    text = extract_text(
                        file_path
                    )

                except Exception:

                    text = ""

                # --------------------------------------------------
                # RETURN FILE
                # --------------------------------------------------

                yield (
                    file_path,
                    metadata,
                    text
                )


# ==============================================================
# OPTIONAL HELPER
# ==============================================================

def get_all_files(
    root_dirs=None
) -> List[Tuple[Path, Dict, str]]:

    return list(
        scan_and_extract(
            root_dirs
        )
    )


# ==============================================================
# TEST
# ==============================================================

if __name__ == "__main__":

    print(
        "LOCAL SEARCH ENGINE - SCANNER TEST"
    )

    print("=" * 60)

    count = 0

    for path, metadata, text in scan_and_extract():

        count += 1

        print(
            f"{count}. {path.name}"
        )

        print(
            f"   Type: {metadata['extension']}"
        )

        print(
            f"   Size: {metadata['size']} bytes"
        )

        print(
            f"   Preview: {text[:80]}"
        )

        print("-" * 60)

        if count >= 10:

            break

    print(
        f"\nScanner ready. Files shown: {count}"
    )