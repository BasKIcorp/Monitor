import json
import configparser
from pathlib import Path
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QVBoxLayout, QGridLayout, QHBoxLayout, QDialog, QFileDialog

from . import utility_functions, fetch_data


class SettingsWindow(QDialog):

    def choose_method(self):
        dlg = QFileDialog()
        utility_functions.method_path, _ = dlg.getOpenFileName(self, 'Открыть файл', './', "Файл метода (*.mtg *.mtz *.mtd)")
        self.path1_label.setText(utility_functions.method_path)

    def choose_exequant(self):
        dlg = QFileDialog()
        utility_functions.exequant_path, _ = dlg.getOpenFileName(self, 'Открыть файл', './', "Файл программы Exequant (*.exe)")
        self.exequant_path_label.setText(utility_functions.exequant_path)

    def save(self):
        self.close()

        if self.rb_off.isChecked():
            utility_functions.simulation = 0
        else:
            utility_functions.simulation = 1
        config = configparser.ConfigParser()
        config.read("./Device.ini")
        config.set('FSM', 'simulation', str(utility_functions.simulation))
        with open('./Device.ini', 'w') as configfile:
            config.write(configfile)

        utility_functions.plots_interval = int(self.combo1.currentText()[0:2])
        utility_functions.params_interval = self.combo2.currentText()
        max_val = "8000"
        min_val = "0"
        if self.max_entry.text() != '':
            if self.min_entry.text() != '':
                self.parent.plot2.setXRange(int(self.min_entry.text()), int(self.max_entry.text()))
                self.parent.plot1.setXRange(int(self.min_entry.text()), int(self.max_entry.text()))
                max_val = self.max_entry.text()
                min_val = self.min_entry.text()
            else:
                self.parent.plot2.setXRange(0, int(self.max_entry.text()))
                self.parent.plot1.setXRange(0, int(self.max_entry.text()))
                max_val = self.max_entry.text()
        elif self.min_entry.text() != '':
            self.parent.plot2.setXRange(int(self.min_entry.text()), 8000)
            self.parent.plot1.setXRange(int(self.min_entry.text()), 8000)
            min_val = self.min_entry.text()
        if self.save_entry != '':
            utility_functions.days_threshold = int(self.save_entry.text())
        else:
            utility_functions.days_threshold = 5
            
        # Получаем значение поправки на толщину кюветы
        cuv_correction = 0
        if self.cuv_correction_entry.text():
            try:
                cuv_correction = float(self.cuv_correction_entry.text())
            except ValueError:
                pass
                
        # Получаем значение смещения для параметра
        param_offset = 0
        if self.param_offset_entry.text():
            try:
                param_offset = float(self.param_offset_entry.text())
            except ValueError:
                pass
                
        with open('config/config.json', 'r', encoding="utf-8") as file:
            json_data = json.load(file)
        json_data["simulation"] = str(utility_functions.simulation)
        json_data["method_path"] = utility_functions.method_path
        json_data["exequant_path"] = utility_functions.exequant_path
        json_data["params_period"] = self.combo2.currentText()
        json_data["plots_period"] = self.combo1.currentText()
        json_data["days_threshold"] = utility_functions.days_threshold
        json_data["limits"]["min"] = min_val
        json_data["limits"]["max"] = max_val
        json_data["theme"] = utility_functions.theme
        json_data["cuv_correction"] = cuv_correction
        json_data["param_offset"] = param_offset
        with open('config/config.json', 'w') as f:
            json.dump(json_data, f)

    def load(self):
        with open('config/config.json', 'r', encoding="utf-8") as file:
            json_data = json.load(file)
        try:
            if int(json_data["simulation"]) == 1:
                self.rb_on.setChecked(True)
                utility_functions.simulation = 1
            else:
                self.rb_off.setChecked(True)
                utility_functions.simulation = 0
        except (ValueError, KeyError):
            # В случае ошибки используем значение по умолчанию
            self.rb_off.setChecked(True)
            utility_functions.simulation = 0
        self.path1_label.setText(json_data["method_path"])
        utility_functions.method_path = json_data["method_path"]
        
        # Загрузка пути к exequant.exe
        if "exequant_path" in json_data:
            self.exequant_path_label.setText(json_data["exequant_path"])
            utility_functions.exequant_path = json_data["exequant_path"]
        else:
            self.exequant_path_label.setText("")
            utility_functions.exequant_path = ""
        
        self.combo1.setCurrentText(json_data["plots_period"])
        utility_functions.plots_interval = int(json_data["plots_period"][0:2])
        self.combo2.setCurrentText(json_data["params_period"])
        utility_functions.params_interval = json_data["params_period"]
        for i in range(16):
            utility_functions.parameter_names[i] = json_data["param_names"][str(i + 1)]
        utility_functions.days_threshold = int(json_data["days_threshold"])
        self.save_entry.setText(str(utility_functions.days_threshold))
        self.min_entry.setText(json_data["limits"]["min"])
        self.max_entry.setText(json_data["limits"]["max"])
        self.parent.plot2.setXRange(int(json_data["limits"]["min"]), int(json_data["limits"]["max"]))
        self.parent.plot1.setXRange(int(json_data["limits"]["min"]), int(json_data["limits"]["max"]))
        utility_functions.theme = json_data["theme"]
        
        # Загрузка поправки на толщину кюветы
        if "cuv_correction" in json_data:
            self.cuv_correction_entry.setText(str(json_data["cuv_correction"]))
            
        # Загрузка смещения для параметра
        if "param_offset" in json_data:
            self.param_offset_entry.setText(str(json_data["param_offset"]))
            
        QtWidgets.QApplication.instance().setStyleSheet(Path(f'resources/themes/{utility_functions.theme}.qss').read_text())

    def modbus_settings(self):
        from .modbus_window import ModbusWindow
        self.modbus_popup = ModbusWindow(self)
        self.modbus_popup.show()

    def rename_params(self):
        from .params_window import RenameParamsWindow
        self.rename_popup = RenameParamsWindow(self, self.parent)
        self.rename_popup.show()

    def open_channel_params(self):
        from .channel_params_window import ChannelParamsWindow
        self.channel_params_window = ChannelParamsWindow(self)
        self.channel_params_window.show()

    def change_theme(self):
        app = QtWidgets.QApplication.instance()
        if utility_functions.theme == "light":
            app.setStyleSheet(Path('resources/themes/brand.qss').read_text())
            utility_functions.theme = "brand"
        else:
            app.setStyleSheet(Path('resources/themes/light.qss').read_text())
            utility_functions.theme = "light"

    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.setFixedSize(400, 650)
        self.setWindowTitle("Настройки")
        self.setModal(True)
        self.setWindowFlag(QtCore.Qt.WindowContextHelpButtonHint, False)
        self.setWindowIcon(QtGui.QIcon('resources/images/logo.jpg'))
        
        # Устанавливаем шрифт Arial для окна
        font = QtGui.QFont("Arial")
        font.setPointSize(5)
        self.setFont(font)
        
        layout = QVBoxLayout(self)
        label1 = QtWidgets.QLabel()
        label1.setText("Симуляция")
        layout.addWidget(label1)
        radio_layout = QHBoxLayout()
        self.rb_on = QtWidgets.QRadioButton('Вкл.', self)
        radio_layout.addWidget(self.rb_on)
        self.rb_off = QtWidgets.QRadioButton('Выкл.', self)
        radio_layout.addWidget(self.rb_off)
        spacer = QtWidgets.QSpacerItem(250, 20, QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        radio_layout.addItem(spacer)
        layout.addLayout(radio_layout)

        label2 = QtWidgets.QLabel()
        label2.setText("Путь к файлу метода")
        layout.addWidget(label2)

        path1_layout = QHBoxLayout()
        button1 = QtWidgets.QPushButton()
        button1.setText("Выбрать")
        button1.clicked.connect(self.choose_method)
        self.path1_label = QtWidgets.QLabel()
        path1_layout.addWidget(button1)
        path1_layout.addWidget(self.path1_label)
        layout.addLayout(path1_layout)

        # Добавляем выбор пути к exequant.exe
        label_exequant = QtWidgets.QLabel()
        label_exequant.setText("Путь к файлу Exequant")
        layout.addWidget(label_exequant)
        
        exequant_path_layout = QHBoxLayout()
        exequant_button = QtWidgets.QPushButton()
        exequant_button.setText("Выбрать")
        exequant_button.clicked.connect(self.choose_exequant)
        self.exequant_path_label = QtWidgets.QLabel()
        self.exequant_path_label.setText(utility_functions.exequant_path)
        exequant_path_layout.addWidget(exequant_button)
        exequant_path_layout.addWidget(self.exequant_path_label)
        layout.addLayout(exequant_path_layout)

        label4 = QtWidgets.QLabel()
        label4.setText("Период обновления графиков")
        layout.addWidget(label4)
        self.combo1 = QtWidgets.QComboBox()
        self.combo1.addItems(["10 с", "20 с", "30 с", "40 с", "50 с", "60 с"])
        layout.addWidget(self.combo1)

        label5 = QtWidgets.QLabel()
        label5.setText("Период обновления параметров")
        layout.addWidget(label5)
        self.combo2 = QtWidgets.QComboBox()
        self.combo2.addItems(["1 ч", "12 ч", "24 ч"])
        layout.addWidget(self.combo2)

        label7 = QtWidgets.QLabel()
        label7.setText("Границы спектров по оси Х")
        layout.addWidget(label7)
        limits_layout = QGridLayout()
        label8 = QtWidgets.QLabel()
        label8.setText("Левая граница")
        limits_layout.addWidget(label8, 0, 0)
        label9 = QtWidgets.QLabel()
        label9.setText("Правая граница")
        limits_layout.addWidget(label9, 0, 1)
        self.min_entry = QtWidgets.QLineEdit()
        self.min_entry.setValidator(QtGui.QIntValidator())
        limits_layout.addWidget(self.min_entry, 1, 0)
        self.max_entry = QtWidgets.QLineEdit()
        self.max_entry.setValidator(QtGui.QIntValidator())
        limits_layout.addWidget(self.max_entry, 1, 1)
        layout.addLayout(limits_layout)

        label10 = QtWidgets.QLabel()
        label10.setText("Удалять архивы старше чем, дней")
        layout.addWidget(label10)
        self.save_entry = QtWidgets.QLineEdit()
        self.save_entry.setValidator(QtGui.QIntValidator())
        layout.addWidget(self.save_entry)
        
        # Добавляем поле для ввода поправки на толщину кюветы
        cuv_correction_label = QtWidgets.QLabel()
        cuv_correction_label.setText("Поправка на толщину кюветы")
        layout.addWidget(cuv_correction_label)
        self.cuv_correction_entry = QtWidgets.QLineEdit()
        self.cuv_correction_entry.setValidator(QtGui.QDoubleValidator())
        layout.addWidget(self.cuv_correction_entry)
        
        # Добавляем поле для ввода смещения параметра
        param_offset_label = QtWidgets.QLabel()
        param_offset_label.setText("Смещение для параметра")
        layout.addWidget(param_offset_label)
        self.param_offset_entry = QtWidgets.QLineEdit()
        self.param_offset_entry.setValidator(QtGui.QDoubleValidator())
        layout.addWidget(self.param_offset_entry)

        # Добавляем информацию о последнем обновлении фона
        fon_date_layout = QHBoxLayout()
        fon_date_label = QtWidgets.QLabel("Дата обновления фона:")
        fon_date_label.setAlignment(QtCore.Qt.AlignLeft)
        fon_date_layout.addWidget(fon_date_label)
        
        self.last_updated = QtWidgets.QLabel()
        self.last_updated.setAlignment(QtCore.Qt.AlignRight)
        with open('config/config.json', 'r', encoding="utf-8") as file:
            json_data = json.load(file)
        self.last_updated.setText(json_data["fon_updated"])
        fon_date_layout.addWidget(self.last_updated)
        layout.addLayout(fon_date_layout)
        
        # Добавляем виджеты разрешения, числа сканов и толщины кюветы
        # Разрешение
        res_layout = QHBoxLayout()
        res_label = QtWidgets.QLabel("Разрешение:")
        res_label.setAlignment(QtCore.Qt.AlignLeft)
        res_layout.addWidget(res_label)
        
        res_value_layout = QHBoxLayout()
        self.res_value = QtWidgets.QLabel()
        self.res_value.setText(str(fetch_data.res))
        self.res_value.setAlignment(QtCore.Qt.AlignLeft)
        res_value_layout.addWidget(self.res_value)
        
        res_unit = QtWidgets.QLabel()
        res_unit.setText(" см⁻¹")
        # res_unit.setAlignment(QtCore.Qt.AlignLeft)
        res_value_layout.addWidget(res_unit)
        
        res_layout.addLayout(res_value_layout)
        layout.addLayout(res_layout)
        
        # Число сканов
        scans_layout = QHBoxLayout()
        scans_label = QtWidgets.QLabel("Число сканов:")
        scans_label.setAlignment(QtCore.Qt.AlignLeft)
        scans_layout.addWidget(scans_label)
        
        self.scans_value = QtWidgets.QLabel()
        # self.scans_value.setAlignment(QtCore.Qt.AlignCenter)
        self.scans_value.setText(str(fetch_data.scans))
        scans_layout.addWidget(self.scans_value)
        
        layout.addLayout(scans_layout)
        
        # Толщина кюветы
        cuv_layout = QHBoxLayout()
        cuv_label = QtWidgets.QLabel("Толщина кюветы:")
        cuv_label.setAlignment(QtCore.Qt.AlignLeft)
        cuv_layout.addWidget(cuv_label)
        
        cuv_value_layout = QHBoxLayout()
        self.cuv_value = QtWidgets.QLabel()
        self.cuv_value.setAlignment(QtCore.Qt.AlignLeft)
        self.cuv_value.setText(str(fetch_data.cuv_length))
        cuv_value_layout.addWidget(self.cuv_value)
        
        cuv_unit = QtWidgets.QLabel()
        cuv_unit.setText(" мм")
        cuv_unit.setAlignment(QtCore.Qt.AlignLeft)
        cuv_value_layout.addWidget(cuv_unit)
        
        cuv_layout.addLayout(cuv_value_layout)
        layout.addLayout(cuv_layout)

        # Добавляем кнопку для параметров переключения каналов
        channel_params_button = QtWidgets.QPushButton()
        channel_params_button.setText("Параметры переключения каналов")
        channel_params_button.clicked.connect(self.open_channel_params)
        layout.addWidget(channel_params_button)

        modbus_button = QtWidgets.QPushButton()
        modbus_button.setText("Настройки ModBus")
        modbus_button.clicked.connect(self.modbus_settings)
        layout.addWidget(modbus_button)

        self.load()

        # change_theme = QtWidgets.QPushButton()
        # change_theme.setText("Сменить тему")
        # change_theme.clicked.connect(self.change_theme)
        # layout.addWidget(change_theme)

        save_button = QtWidgets.QPushButton()
        save_button.setText("Сохранить")
        save_button.clicked.connect(self.save)
        layout.addWidget(save_button)

        if not utility_functions.stop_threads:
            button1.setEnabled(False)
            self.rb_on.setEnabled(False)
            self.rb_off.setEnabled(False) 