import sys

from PyQt6.QtWidgets import QApplication

from src.desktop.main_window import AdLensPKWindow
from src.core.scheduler import start_scheduler, stop_scheduler
from src.ml.scheduler_hook import schedule_weekly_retrain


def main() -> int:
    app = QApplication(sys.argv)

    scheduler = start_scheduler()
    schedule_weekly_retrain(scheduler)
    app.aboutToQuit.connect(stop_scheduler)

    window = AdLensPKWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
