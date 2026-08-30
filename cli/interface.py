"""
cli/interface.py
----------------
Member 4: User-facing command-line interface.

This module talks ONLY to SearchEngineController.
It does not directly manipulate the scanner, indexer, search engine,
or SQLite database.
"""

from datetime import datetime
from typing import Optional

from controller import SearchEngineController, IntegrationError, IndexRunSummary
from utils.config import DEFAULT_RESULT_LIMIT
from utils.helpers import (
    format_duration,
    format_size,
    open_file,
)


# ==============================================================
# DISPLAY HELPERS
# ==============================================================

def print_header(title: str) -> None:
    """Print a consistent application header."""
    print()
    print("=" * 72)
    print(f"{title:^72}")
    print("=" * 72)


def pause() -> None:
    """Pause until the user presses Enter."""
    input("\nPress Enter to continue...")


def format_last_run(last_run: Optional[dict]) -> str:
    """Convert the database's last-run record into readable text."""
    if not last_run:
        return "Never"

    started_at = last_run.get("started_at")
    if not started_at:
        return "Unknown"

    try:
        return datetime.fromtimestamp(float(started_at)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    except (TypeError, ValueError, OSError):
        return "Unknown"


# ==============================================================
# INDEXING
# ==============================================================

def show_index_progress(
    discovered: int,
    indexed: int,
    errors: int,
) -> None:
    """
    Callback used by SearchEngineController.run_index().

    The controller calls this periodically while scanning.
    """
    print(
        f"\rScanning... discovered: {discovered:<7} "
        f"ready: {indexed:<7} errors: {errors:<5}",
        end="",
        flush=True,
    )


def run_indexing(controller: SearchEngineController) -> None:
    """Run initial indexing or update the existing index."""
    print_header("INDEX / UPDATE FILES")

    print("Scanning your accessible personal files...")
    print("This may take some time on the first run.")
    print()

    try:
        summary: IndexRunSummary = controller.run_index(
            progress_callback=show_index_progress
        )

        # Move to a fresh line after the progress callback.
        print()

        print("\nIndexing complete.")
        print("-" * 72)
        print(f"Files discovered : {summary.files_discovered}")
        print(f"Files indexed    : {summary.files_indexed}")
        print(f"Files skipped    : {summary.files_skipped}")
        print(f"Errors           : {summary.errors}")
        print(
            f"Duration         : "
            f"{format_duration(summary.duration_seconds)}"
        )
        print("-" * 72)

    except IntegrationError as exc:
        print()
        print(f"ERROR: {exc}")

    except KeyboardInterrupt:
        print()
        print("\nIndexing interrupted by user.")

    except Exception:
        # The controller is designed to translate normal integration
        # failures into IntegrationError. This is a final CLI safety net.
        print()
        print("ERROR: The indexing operation could not be completed.")

    pause()


# ==============================================================
# SEARCH
# ==============================================================

def display_search_result(number: int, result) -> None:
    """Display one SearchResult returned by SearchEngine."""
    print()
    print(f"[{number}] {result.filename}")
    print(f"    Relevance : {result.relevance_pct:.1f}%")
    print(f"    Type      : {result.file_type}")
    print(f"    Location  : {result.filepath}")

    if result.snippet:
        print()
        print("    Match:")
        print("    " + result.snippet.replace("\n", "\n    "))


def search_files(controller: SearchEngineController) -> None:
    """Handle the interactive search screen."""
    print_header("SEARCH YOUR FILES")

    if not controller.index_exists() or controller.document_count() == 0:
        print("No indexed documents were found.")
        print()
        print("Please choose 'Index / Scan Files' from the main menu first.")
        pause()
        return

    while True:
        print()
        query = input("Search (or type 'back' to return): ").strip()

        if query.lower() == "back":
            return

        if not query:
            print("Please enter something to search for.")
            continue

        try:
            results = controller.search(
                query,
                limit=DEFAULT_RESULT_LIMIT,
            )

        except IntegrationError as exc:
            print(f"\nERROR: {exc}")
            continue

        if not results:
            print()
            print("No matching documents were found.")
            print()
            print("Try:")
            print("  • using fewer keywords")
            print("  • using different wording")
            print("  • searching for a distinctive phrase")
            continue

        print_header("SEARCH RESULTS")

        print(f'Query: "{query}"')
        print(f"Showing up to {len(results)} result(s).")

        for number, result in enumerate(results, start=1):
            display_search_result(number, result)

        print()
        print("-" * 72)

        while True:
            choice = input(
                "\nEnter result number to open, "
                "'n' for new search, or 'b' to go back: "
            ).strip().lower()

            if choice == "b":
                return

            if choice == "n":
                break

            if not choice.isdigit():
                print("Please enter a valid result number, 'n', or 'b'.")
                continue

            result_number = int(choice)

            if not 1 <= result_number <= len(results):
                print(
                    f"Please choose a number between "
                    f"1 and {len(results)}."
                )
                continue

            selected = results[result_number - 1]

            print()
            print(f"Opening: {selected.filename}")

            error = open_file(selected.filepath)

            if error:
                print(f"Could not open file: {error}")
            else:
                print("File opened successfully.")

            break


# ==============================================================
# STATISTICS
# ==============================================================

def show_statistics(controller: SearchEngineController) -> None:
    """Display local index statistics."""
    print_header("INDEX STATISTICS")

    try:
        stats = controller.get_statistics()
    except Exception:
        print("Unable to read index statistics.")
        pause()
        return

    documents = stats.get("documents_indexed", 0)
    unique_terms = stats.get("unique_terms", 0)
    database_size = stats.get("database_size_bytes", 0)
    last_run = stats.get("last_run")

    print(f"Documents indexed : {documents:,}")
    print(f"Unique terms      : {unique_terms:,}")
    print(f"Database size     : {format_size(database_size)}")
    print(f"Last index run    : {format_last_run(last_run)}")

    if last_run:
        duration = last_run.get("duration_seconds", 0)
        discovered = last_run.get("files_discovered", 0)
        indexed = last_run.get("files_indexed", 0)
        skipped = last_run.get("files_skipped", 0)
        errors = last_run.get("errors", 0)

        print(f"Last duration     : {format_duration(duration)}")
        print(f"Last discovered   : {discovered:,}")
        print(f"Last indexed      : {indexed:,}")
        print(f"Last skipped      : {skipped:,}")
        print(f"Last errors       : {errors:,}")

    pause()


# ==============================================================
# MAIN MENU
# ==============================================================

def print_main_menu(controller: SearchEngineController) -> None:
    """Display the main application menu."""
    print_header("LOCAL SEARCH ENGINE")

    try:
        count = controller.document_count()
        exists = controller.index_exists()
    except Exception:
        count = 0
        exists = False

    if exists and count > 0:
        print(f"Indexed documents: {count:,}")
    else:
        print("Status: No documents indexed yet.")

    print()
    print("1. Index / Scan Files")
    print("2. Search")
    print("3. Update Index")
    print("4. Index Statistics")
    print("5. Exit")


def run_cli(controller: SearchEngineController) -> None:
    """Run the complete interactive CLI."""
    while True:
        print_main_menu(controller)

        choice = input("\nChoose an option: ").strip()

        if choice == "1":
            run_indexing(controller)

        elif choice == "2":
            search_files(controller)

        elif choice == "3":
            run_indexing(controller)

        elif choice == "4":
            show_statistics(controller)

        elif choice == "5":
            print("\nClosing Local Search Engine...")
            return

        else:
            print("\nInvalid option. Please choose 1, 2, 3, 4, or 5.")