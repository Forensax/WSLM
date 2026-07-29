from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QStyle

from .main_window import MainWindow, configure_application_style


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("WSLM")
    app.setOrganizationName("WSLM")
    configure_application_style(app)
    app.setWindowIcon(app.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

