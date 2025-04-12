from pathlib import Path
import logging
from datetime import datetime
import os
import platform
import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QGroupBox, QStatusBar, QErrorMessage, QDialog, QRadioButton, QPushButton, QLabel, QComboBox, QSizePolicy
from PyQt5 import QtGui
from src.gui import Ui_MainWindow
from src import fetch_data
from src import transmissionPlot
from src import intensityPlot
from src import param_plot

# Настройка логгирования
def setup_logging():
    # Создаем директорию для логов, если её нет
    log_dir = Path('Log')
    log_dir.mkdir(exist_ok=True)

    # Формируем имя файла лога с текущей датой
    log_file = log_dir / f'app_{datetime.now().strftime("%Y%m%d")}.log'

    # Настраиваем формат логов
    log_format = '%(asctime)s - %(levelname)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'

    # Настраиваем корневой логгер
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        datefmt=date_format,
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

    logging.info('Логгирование инициализировано')

# Проверка наличия DLL и её доступности
def check_dll():
    dll_path = os.path.abspath("resources/drivers/GAS.dll")
    logging.info(f"Путь к DLL: {dll_path}")

    if not os.path.exists(dll_path):
        logging.error(f"DLL файл не найден по пути: {dll_path}")
        return False

    logging.info(f"DLL файл найден: {dll_path}")
    return True

class MyMainWindow(QMainWindow):
    def __init__(self):
        logging.info('Инициализация главного окна')
        super().__init__()

        # Создаем экземпляр сгенерированного UI класса
        self.ui = Ui_MainWindow()
        logging.info('Настройка пользовательского интерфейса')
        self.ui.setupUi(self)

        # Создаем основной макет
        self.main_layout = QVBoxLayout()
        self.setLayout(self.main_layout)

        # Устанавливаем иконку окна
        try:
            self.setWindowIcon(QtGui.QIcon('resources/images/logo.jpg'))
            logging.info('Иконка окна установлена')
        except Exception as e:
            logging.error(f'Ошибка при установке иконки окна: {e}')

        # Создаем кнопку "Старт"
        self.start_button = QPushButton("Старт")
        self.start_button.setToolTip("Нажмите, чтобы начать процесс")
        self.start_button.setIcon(QtGui.QIcon('resources/icons/start.png'))
        self.main_layout.addWidget(self.start_button)

        # Создаем кнопку "Настройки"
        self.settings_button = QPushButton("Настройки")
        self.settings_button.setToolTip("Открыть настройки приложения")
        self.settings_button.setIcon(QtGui.QIcon('resources/icons/settings.png'))
        self.main_layout.addWidget(self.settings_button)

        # Пример улучшенного макета с использованием QGroupBox
        group_box = QGroupBox("Настройки графиков")
        layout = QVBoxLayout(group_box)

        label1 = QLabel("Период обновления графиков:")
        layout.addWidget(label1)

        self.combo1 = QComboBox()
        self.combo1.addItems(["10 с", "20 с", "30 с", "40 с", "50 с", "60 с"])
        layout.addWidget(self.combo1)

        self.main_layout.addWidget(group_box)

        self.statusbar = QStatusBar(self)
        self.setStatusBar(self.statusbar)
        self.statusbar.showMessage("Приложение готово.")

        self.start_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def show_error(self, message):
        error_dialog = QErrorMessage()
        error_dialog.setWindowTitle("Ошибка")
        error_dialog.showMessage(message)
        error_dialog.exec_()

class ModalPopup(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setFixedSize(400, 700)
        self.setWindowTitle("Настройки")
        self.setModal(True)
        self.setWindowIcon(QtGui.QIcon('resources/images/logo.jpg'))

        layout = QVBoxLayout(self)

        group_box = QGroupBox("Настройки")
        group_layout = QVBoxLayout(group_box)

        label1 = QLabel("Симуляция:")
        self.rb_on = QRadioButton('Включить')
        self.rb_off = QRadioButton('Выключить')
        group_layout.addWidget(label1)
        group_layout.addWidget(self.rb_on)
        group_layout.addWidget(self.rb_off)

        layout.addWidget(group_box)

        save_button = QPushButton("Сохранить")
        save_button.setIcon(QtGui.QIcon('resources/icons/save.png'))
        save_button.setToolTip("Сохранить изменения")
        layout.addWidget(save_button)

        self.setLayout(layout)

if __name__ == "__main__":
    # Инициализируем логгирование
    setup_logging()

    # Логируем информацию о системе
    logging.info(f"Python версия: {sys.version}")
    logging.info(f"Python разрядность: {platform.architecture()}")
    logging.info(f"Операционная система: {platform.system()} {platform.release()}")

    # Проверяем наличие DLL
    if not check_dll():
        logging.critical("Невозможно запустить приложение - DLL не найдена")
        sys.exit(1)
    
    logging.info('Запуск приложения')
    try:
        app = QApplication([])
        window = MyMainWindow()
        logging.info('Открытие окна в полноэкранном режиме')
        window.showMaximized()
        logging.info('Запуск главного цикла приложения')
        app.exec_()
    except Exception as e:
        logging.critical(f'Критическая ошибка при запуске приложения: {e}')

