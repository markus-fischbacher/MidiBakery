"""The packaged app's entry point (PyInstaller): the `midibakery` command line."""

import sys

from midibakery.cli import main

if __name__ == "__main__":
    sys.exit(main())
