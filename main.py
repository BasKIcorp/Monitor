from pathlib import Path

from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5 import QtGui

from gui import Ui_MainWindow  # Import the generated module


class MyMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # Create an instance of the generated UI class
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setWindowIcon(QtGui.QIcon('logo.jpg'))


if __name__ == "__main__":
    app = QApplication([])
    window = MyMainWindow()
    window.showMaximized()
    app.exec_()

