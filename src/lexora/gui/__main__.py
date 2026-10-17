"""Allow ``python -m lexora.gui`` to launch the GUI (same entry as lexora-gui)."""
from __future__ import annotations

import sys


def main() -> int:
    from lexora.gui.app import main as app_main
    return app_main()


if __name__ == "__main__":
    sys.exit(main())
