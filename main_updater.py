"""Open the PyAppify update manager for this checkout."""

if __name__ == '__main__':
    import sys
    from pathlib import Path

    from pyappify.updater_ui import main

    sys.exit(main(['--repo', str(Path(__file__).resolve().parent), *sys.argv[1:]]))
