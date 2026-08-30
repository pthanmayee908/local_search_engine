"""
main.py
-------
Application entry point for the Local Search Engine.
"""

from controller import SearchEngineController, IntegrationError
from cli.interface import run_cli
from utils.helpers import setup_logging


def main() -> None:
    """Start the Local Search Engine."""
    setup_logging()

    controller = None

    try:
        controller = SearchEngineController()

        print("=" * 72)
        print("LOCAL SEARCH ENGINE")
        print("=" * 72)
        print()
        print("Search your files by what you remember,")
        print("not by what you named them.")
        print()

        run_cli(controller)

    except IntegrationError as exc:
        print()
        print(f"ERROR: {exc}")

    except KeyboardInterrupt:
        print("\n\nApplication interrupted.")

    except Exception:
        print()
        print("ERROR: The application could not start.")
        print("Check the application log for details.")

    finally:
        if controller is not None:
            controller.close()


if __name__ == "__main__":
    main()