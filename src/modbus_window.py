import logging
import serial
import serial.tools.list_ports
import modbus_tk
import modbus_tk.defines as cst
from modbus_tk import modbus_rtu
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QVBoxLayout, QDialog
import json
import os

from . import utility_functions


def load_modbus_config():
    """Загрузка параметров Modbus из конфигурационного файла"""
    config_path = os.path.join('config', 'config.json')
    
    # Значения по умолчанию
    modbus_config = {
        "device_num": 1,
        "port": "",
        "baudrate": "9600",
        "timeout": 1
    }
    
    try:
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                
            # Если в конфиге есть секция modbus, используем её
            if 'modbus' in config:
                modbus_config = config['modbus']
    except Exception as e:
        logging.error(f"Ошибка при загрузке конфигурации Modbus: {e}")
    
    return modbus_config


def save_modbus_config(device_num, port, baudrate, timeout):
    """Сохранение параметров Modbus в конфигурационный файл"""
    config_path = os.path.join('config', 'config.json')
    
    try:
        # Загружаем текущий конфиг
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        else:
            config = {}
        
        # Обновляем или создаем секцию modbus
        config['modbus'] = {
            "device_num": device_num,
            "port": port,
            "baudrate": baudrate,
            "timeout": timeout
        }
        
        # Сохраняем обновленный конфиг
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
            
        logging.info("Конфигурация Modbus успешно сохранена")
    except Exception as e:
        logging.error(f"Ошибка при сохранении конфигурации Modbus: {e}")


class ModbusWindow(QDialog):
    def stop_client(self):
        logging.info("Отключение Modbus клиента")
        utility_functions.master = None
        utility_functions.modbus_connected = False
        self.error_label.setText("")
        self.connect_button.setText("Соединение")

    def start_client(self, device, PORT, baudrate, timeoutentry):
        logging.info(f"Попытка подключения Modbus клиента: порт={PORT}, скорость={baudrate}, таймаут={timeoutentry}")
        utility_functions.port = PORT
        if device == "" or utility_functions.timeout == "":
            utility_functions.modbus_connected = False
            self.error_label.setText("Соединение НЕ установлено")
            logging.error("Не указано устройство или таймаут")
        else:
            utility_functions.device_num = int(device)
            utility_functions.timeout = int(timeoutentry)
            try:
                try:
                    utility_functions.master = modbus_rtu.RtuMaster(
                        serial.Serial(port=PORT, baudrate=baudrate, bytesize=8, parity='N', stopbits=1, xonxoff=0)
                    )
                    utility_functions.master.set_timeout(int(utility_functions.timeout))
                    logging.info(f"Modbus клиент подключен: устройство={utility_functions.device_num}")
                    utility_functions.modbus_connected = True
                    self.error_label.setText("Соединение установлено")
                    self.connect_button.setText("Отключиться")
                    
                    # Сохраняем параметры в конфиг
                    save_modbus_config(device, PORT, baudrate, timeoutentry)
                except serial.serialutil.SerialException as e:
                    utility_functions.modbus_connected = False
                    self.error_label.setText("Соединение НЕ установлено")
                    logging.error(f"Ошибка подключения к порту: {e}")
            except modbus_tk.modbus.ModbusError as exc:
                utility_functions.modbus_connected = False
                logging.error(f"Ошибка Modbus - Code={exc.get_exception_code()}: {exc}")
                self.error_label.setText("Соединение НЕ установлено")

    def toggle_label_and_function(self, device, PORT, baudrate, timeoutentry):
        if self.connect_button.text() == "Соединение":
            self.start_client(device, PORT, baudrate, timeoutentry)
        else:
            self.stop_client()

    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.setFixedSize(400, 300)
        self.setWindowTitle("Настройки ModBus")
        self.setModal(True)
        self.setWindowFlag(QtCore.Qt.WindowContextHelpButtonHint, False)
        self.setWindowIcon(QtGui.QIcon('resources/images/logo.jpg'))
        
        # Устанавливаем шрифт Arial для окна
        font = QtGui.QFont("Arial")
        self.setFont(font)
        
        layout = QVBoxLayout(self)
        available_ports = [i.device for i in serial.tools.list_ports.comports()]
        label1 = QtWidgets.QLabel()
        label1.setText("Адрес устройства")
        layout.addWidget(label1)
        self.device_entry = QtWidgets.QLineEdit()
        self.device_entry.setValidator(QtGui.QIntValidator())

        # Загружаем параметры из конфига
        modbus_config = load_modbus_config()
        
        # Устанавливаем значения из конфига или из глобальных переменных
        if modbus_config.get("device_num"):
            self.device_entry.setText(str(modbus_config["device_num"]))
        elif utility_functions.device_num != 0:
            self.device_entry.setText(str(utility_functions.device_num))
        layout.addWidget(self.device_entry)

        label4 = QtWidgets.QLabel()
        label4.setText("Порт")
        layout.addWidget(label4)
        self.ports = QtWidgets.QComboBox()
        self.ports.addItems(available_ports)
        
        # Выбираем порт из конфига или из глобальных переменных
        if modbus_config.get("port") and modbus_config["port"] in available_ports:
            self.ports.setCurrentText(modbus_config["port"])
        elif utility_functions.port != '' and utility_functions.port in available_ports:
            self.ports.setCurrentText(utility_functions.port)
        layout.addWidget(self.ports)

        label2 = QtWidgets.QLabel()
        label2.setText("Скорость обмена, бит/с")
        layout.addWidget(label2)
        self.combo = QtWidgets.QComboBox()
        self.combo.addItems(["1200", "2400", "4800", "9600", "19200", "38400", "57600", "115200"])
        
        # Выбираем скорость из конфига или устанавливаем по умолчанию
        if modbus_config.get("baudrate"):
            self.combo.setCurrentText(modbus_config["baudrate"])
        else:
            self.combo.setCurrentText("9600")
        layout.addWidget(self.combo)

        label3 = QtWidgets.QLabel()
        label3.setText("Таймаут, с")
        layout.addWidget(label3)
        self.timeout_entry = QtWidgets.QLineEdit()
        self.timeout_entry.setValidator(QtGui.QIntValidator())
        
        # Устанавливаем таймаут из конфига или из глобальных переменных
        if modbus_config.get("timeout"):
            self.timeout_entry.setText(str(modbus_config["timeout"]))
        elif utility_functions.timeout != 0:
            self.timeout_entry.setText(str(utility_functions.timeout))
        layout.addWidget(self.timeout_entry)

        self.connect_button = QtWidgets.QPushButton()
        self.error_label = QtWidgets.QLabel()
        self.error_label.setText("")
        if utility_functions.modbus_connected:
            self.connect_button.setText("Отключиться")
            self.error_label.setText("Соединение установлено")
        else:
            self.connect_button.setText("Соединение")
        self.connect_button.clicked.connect(lambda: self.toggle_label_and_function(self.device_entry.text(),
                                                                                   self.ports.currentText(),
                                                                                   self.combo.currentText(),
                                                                                   self.timeout_entry.text()))
        layout.addWidget(self.connect_button)

        layout.addWidget(self.error_label) 