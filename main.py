"""
main.py
-------
Application entry point for BlossomSearch Local Search Engine.

Usage:
    python main.py
        Starts the Web UI.

    python main.py --cli
        Starts the command-line interface.

Zero third-party runtime dependencies.
"""

import sys

from utils.helpers import setup_logging


def run_cli() -> None:
    """Start the command-line interface."""
    from controller import SearchEngineController, IntegrationError
    from cli.interface import run_cli as start_cli

    controller = None

    try:
        controller = SearchEngineController()

        print("=" * 72)
        print("BLOSSOMSEARCH - LOCAL SEARCH ENGINE (CLI)")
        print("=" * 72)

        start_cli(controller)

    except IntegrationError as exc:
        print(f"\nERROR: {exc}")

    except KeyboardInterrupt:
        print("\n\nApplication interrupted by user.")

    except Exception as exc:
        print(f"\nERROR: Application could not start: {exc}")

    finally:
        if controller is not None:
            controller.close()


def run_web() -> None:
    """Start the web application."""
    from web_app import start_web_app

    try:
        start_web_app()

    except KeyboardInterrupt:
        print("\n\nApplication interrupted by user.")

    except Exception as exc:
        print(f"\nERROR: Web application could not start: {exc}")


def main() -> None:
    """Application entry point."""
    setup_logging()

    if len(sys.argv) > 1 and sys.argv[1].lower() == "--cli":
        run_cli()
    else:
        run_web()


if __name__ == "__main__":
    main()