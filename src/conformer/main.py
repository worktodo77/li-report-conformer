"""Entry point for LI Report Conformer."""
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont

from conformer.ui.window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName('LI Report Conformer')
    app.setOrganizationName('Long International')

    window = MainWindow()
    window.setAcceptDrops(True)
    window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
