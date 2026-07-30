from __future__ import annotations

import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QStyle

from .main_window import MainWindow, configure_application_style
from .resources import APP_ICON_PATH


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("WSLM")
    app.setOrganizationName("WSLM")
    configure_application_style(app)
    icon = QIcon(str(APP_ICON_PATH))
    if icon.isNull():
        icon = app.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
    app.setWindowIcon(icon)

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
