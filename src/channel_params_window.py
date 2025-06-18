import json
import os
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QVBoxLayout, QGridLayout, QHBoxLayout, QDialog, QFileDialog, QGroupBox, QLabel, QLineEdit, QComboBox, QCheckBox, QPushButton, QSpinBox, QDoubleSpinBox, QRadioButton, QButtonGroup

from . import utility_functions


class ChannelParamsWindow(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setFixedSize(600, 600)  # Уменьшаем размер окна, т.к. убрали раздел
        self.setWindowTitle("Параметры переключения каналов")
        self.setModal(True)
        self.setWindowFlag(QtCore.Qt.WindowContextHelpButtonHint, False)
        self.setWindowIcon(QtGui.QIcon('resources/images/logo.jpg'))
        
        # Устанавливаем шрифт Arial для окна
        font = QtGui.QFont("Arial")
        self.setFont(font)
        
        # Загрузка настроек из файла конфигурации
        self.config = self.load_channel_config()
        
        main_layout = QVBoxLayout(self)
        
        # Группа настроек для переключения каналов
        channels_group = QGroupBox("Настройки каналов")
        channels_layout = QGridLayout()
        
        # Заголовки столбцов
        headers = ["Канал", "Имя канала", "Состояние"]
        for i, header in enumerate(headers):
            label = QLabel(header)
            label.setAlignment(QtCore.Qt.AlignCenter)
            font = QtGui.QFont("Arial")
            font.setBold(True)
            label.setFont(font)
            channels_layout.addWidget(label, 0, i)
        
        # Создание строк для каждого канала
        self.channel_widgets = []
        for i in range(12):  # 12 каналов
            row = []
            
            # Номер канала
            channel_label = QLabel(f"Канал {i+1}")
            channel_label.setAlignment(QtCore.Qt.AlignCenter)
            channels_layout.addWidget(channel_label, i+1, 0)
            row.append(channel_label)
            
            # Имя канала (изменяемое)
            channel_name = QLineEdit()
            channel_name.setText(self.config.get(f"channel_{i+1}", {}).get("name", f"АТ-{i+1}"))
            channel_name.setFixedWidth(150)
            channel_name.setAlignment(QtCore.Qt.AlignCenter)
            channels_layout.addWidget(channel_name, i+1, 1)
            row.append(channel_name)
            
            # Состояние канала (вкл/выкл)
            state_layout = QHBoxLayout()
            
            # Создаем группу радиокнопок
            state_group = QButtonGroup(self)
            
            # Радиокнопка "Вкл"
            radio_on = QRadioButton("Вкл")
            state_layout.addWidget(radio_on)
            state_group.addButton(radio_on)
            
            # Радиокнопка "Выкл"
            radio_off = QRadioButton("Выкл")
            state_layout.addWidget(radio_off)
            state_group.addButton(radio_off)
            
            # Устанавливаем состояние из конфигурации
            if self.config.get(f"channel_{i+1}", {}).get("active", False):
                radio_on.setChecked(True)
            else:
                radio_off.setChecked(True)
                
            # Добавляем радиокнопки в строку
            channels_layout.addLayout(state_layout, i+1, 2)
            row.append(state_group)
            row.append(radio_on)  # Сохраняем ссылку на радиокнопку "Вкл"
            
            self.channel_widgets.append(row)
        
        channels_group.setLayout(channels_layout)
        main_layout.addWidget(channels_group)
        
        # Группа общих параметров
        params_group = QGroupBox("Общие параметры")
        params_layout = QGridLayout()
        
        # Время ожидания подтверждения
        wait_time_label = QLabel("Время ожидания подтверждения, сек (tп):")
        params_layout.addWidget(wait_time_label, 0, 0)
        
        self.wait_time = QSpinBox()
        self.wait_time.setRange(0, 1000)
        self.wait_time.setValue(self.config.get("params", {}).get("wait_time", 30))
        params_layout.addWidget(self.wait_time, 0, 1)
        
        # Фиксация аварии системы переключения каналов
        alarm_fix_label = QLabel("Фиксация аварии системы переключения каналов (АСПК):")
        params_layout.addWidget(alarm_fix_label, 1, 0)
        
        self.alarm_fix = QCheckBox()
        self.alarm_fix.setChecked(self.config.get("params", {}).get("alarm_fix", False))
        params_layout.addWidget(self.alarm_fix, 1, 1)
        
        # Количество попыток переключения каналов
        attempts_label = QLabel("Количество попыток переключения каналов (k):")
        params_layout.addWidget(attempts_label, 2, 0)
        
        self.attempts = QSpinBox()
        self.attempts.setRange(0, 1000)
        self.attempts.setValue(self.config.get("params", {}).get("attempts", 3))
        params_layout.addWidget(self.attempts, 2, 1)
        
        # Период измерения фонового спектра
        background_period_label = QLabel("Период измерения фонового спектра, мин (tф):")
        params_layout.addWidget(background_period_label, 3, 0)
        
        self.background_period = QSpinBox()
        self.background_period.setRange(0, 1000)
        self.background_period.setValue(self.config.get("params", {}).get("background_period", 60))
        params_layout.addWidget(self.background_period, 3, 1)
        
        # Количество измерений канала
        measurements_label = QLabel("Количество измерений канала (n):")
        params_layout.addWidget(measurements_label, 4, 0)
        
        self.measurements = QSpinBox()
        self.measurements.setRange(0, 1000)
        self.measurements.setValue(self.config.get("params", {}).get("measurements", 5))
        params_layout.addWidget(self.measurements, 4, 1)
        
        params_group.setLayout(params_layout)
        main_layout.addWidget(params_group)
        
        # Кнопки
        buttons_layout = QHBoxLayout()
        
        save_button = QPushButton("Сохранить")
        save_button.clicked.connect(self.save_settings)
        buttons_layout.addWidget(save_button)
        
        cancel_button = QPushButton("Отмена")
        cancel_button.clicked.connect(self.close)
        buttons_layout.addWidget(cancel_button)
        
        main_layout.addLayout(buttons_layout)
    
    def load_channel_config(self):
        """Загружает настройки каналов из файла конфигурации"""
        config = {
            "params": {
                "wait_time": 30,       # Время ожидания подтверждения (tп)
                "alarm_fix": False,     # Фиксация аварии системы (АСПК)
                "attempts": 3,         # Количество попыток переключения (k)
                "background_period": 60, # Период измерения фонового спектра (tф)
                "measurements": 5       # Количество измерений канала (n)
            }
        }
        
        # Настройки по умолчанию для каждого канала
        for i in range(1, 13):  # 12 каналов
            config[f"channel_{i}"] = {
                "active": i == 1,  # По умолчанию активен только первый канал
                "name": f"АТ-{i}"  # Имя канала по умолчанию
            }
        
        # Пытаемся загрузить существующие настройки
        try:
            if os.path.exists('config/channel_config.json'):
                with open('config/channel_config.json', 'r', encoding="utf-8") as file:
                    saved_config = json.load(file)
                    # Обновляем конфигурацию загруженными значениями
                    for key, value in saved_config.items():
                        if key in config:
                            config[key].update(value)
                        else:
                            config[key] = value
        except Exception as e:
            print(f"Ошибка при загрузке настроек каналов: {e}")
        
        return config
    
    def save_settings(self):
        """Сохраняет настройки каналов в файл конфигурации"""
        # Обновляем параметры
        self.config["params"]["wait_time"] = self.wait_time.value()
        self.config["params"]["alarm_fix"] = self.alarm_fix.isChecked()
        self.config["params"]["attempts"] = self.attempts.value()
        self.config["params"]["background_period"] = self.background_period.value()
        self.config["params"]["measurements"] = self.measurements.value()
        
        # Обновляем настройки каналов
        for i, widgets in enumerate(self.channel_widgets):
            channel_num = i + 1
            self.config[f"channel_{channel_num}"]["active"] = widgets[3].isChecked()  # Проверяем состояние радиокнопки "Вкл"
            self.config[f"channel_{channel_num}"]["name"] = widgets[1].text()  # Обновляем имя канала
        
        # Сохраняем в файл
        try:
            # Создаем директорию config, если она не существует
            if not os.path.exists('config'):
                os.makedirs('config')
                
            with open('config/channel_config.json', 'w', encoding="utf-8") as file:
                json.dump(self.config, file, indent=4)

            self.close()
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, 
                "Ошибка", 
                f"Не удалось сохранить настройки: {e}",
                QtWidgets.QMessageBox.Ok
            ) 