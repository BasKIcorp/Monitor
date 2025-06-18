import json
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QGridLayout, QDialog

from . import utility_functions


class RenameParamsWindow(QDialog):
    def save_params(self):
        for i in range(16):
            utility_functions.parameter_names[i] = self.entries[i].text()[:50]
        with open('config/config.json', 'r', encoding="utf-8") as file:
            json_data = json.load(file)
        for i in range(16):
            json_data["param_names"][str(i + 1)] = utility_functions.parameter_names[i]
        with open('config/config.json', 'w') as f:
            json.dump(json_data, f)
        self.big_parent.update_param_names()
        self.close()

    def __init__(self, parent, big_parent):
        super().__init__(parent)
        self.parent = parent
        self.big_parent = big_parent
        self.setFixedSize(600, 600)
        self.setWindowTitle("Изменение названий параметров")
        self.setModal(True)
        self.setWindowFlag(QtCore.Qt.WindowContextHelpButtonHint, False)
        self.setWindowIcon(QtGui.QIcon('resources/images/logo.jpg'))
        
        # Устанавливаем шрифт Arial для окна
        font = QtGui.QFont("Arial")
        self.setFont(font)
        
        layout = QGridLayout(self)
        self.entries = []
        for i in range(8):
            label = QtWidgets.QLabel()
            label.setText(f"Параметр {i + 1}")
            layout.addWidget(label, i * 2, 0)
            self.entries.append(QtWidgets.QLineEdit())
            layout.addWidget(self.entries[i], 1 + i * 2, 0)
            self.entries[i].setText(utility_functions.parameter_names[i])
        for i in range(8):
            label = QtWidgets.QLabel()
            label.setText(f"Параметр {i + 9}")
            layout.addWidget(label, i * 2, 1)
            self.entries.append(QtWidgets.QLineEdit())
            layout.addWidget(self.entries[i + 8], 1 + i * 2, 1)
            self.entries[i + 8].setText(utility_functions.parameter_names[i + 8])
            
        save_button = QtWidgets.QPushButton()
        save_button.setText("Сохранить")
        save_button.clicked.connect(self.save_params)

        spacer = QtWidgets.QSpacerItem(20, 50, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)
        layout.addItem(spacer)
        layout.addWidget(save_button, 17, 0, 1, 2)