from pathlib import Path
import logging
from datetime import datetime
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5 import QtGui
import platform
import os

from src.gui import Ui_MainWindow  # Import the generated module

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

class MyMainWindow(QMainWindow):
    def __init__(self):
        logging.info('Инициализация главного окна')
        super().__init__()

        # Create an instance of the generated UI class
        self.ui = Ui_MainWindow()
        logging.info('Настройка пользовательского интерфейса')
        self.ui.setupUi(self)
        
        # Устанавливаем иконку окна
        try:
            self.setWindowIcon(QtGui.QIcon('logo.jpg'))
            logging.info('Иконка окна установлена')
        except Exception as e:
            logging.error(f'Ошибка при установке иконки окна: {e}')

        # Добавляем информацию о разрядности Python
        logging.info(f"Python разрядность: {platform.architecture()}")
        dll_path = 'resources/drivers/GAS.dll'
        # Добавляем информацию о текущем пути к DLL
        logging.info(f"Текущий путь к DLL: {os.path.abspath(dll_path)}")
        logging.info(f"DLL существует: {os.path.exists(dll_path)}")

if __name__ == "__main__":
    # Инициализируем логгирование
    setup_logging()
    
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

