import sys

from PyQt6.QtWidgets import QApplication

from src.desktop.main_window import AdLensPKWindow
from src.core.scheduler import start_scheduler, stop_scheduler


def main() -> int:
    app = QApplication(sys.argv)

    start_scheduler()
    app.aboutToQuit.connect(stop_scheduler)

    window = AdLensPKWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
