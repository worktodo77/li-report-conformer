"""Entry point for LI Report Conformer."""
import os
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont, QIcon

from conformer.ui.window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName('LI Report Conformer')
    app.setOrganizationName('Long International')
    _icon = QIcon(os.path.join(os.path.dirname(__file__), 'assets', 'LI icon.png'))
    if not _icon.isNull():
        app.setWindowIcon(_icon)

    window = MainWindow()
    window.setAcceptDrops(True)
    window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
