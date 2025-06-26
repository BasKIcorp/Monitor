from pathlib import Path
import logging
from datetime import datetime
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5 import QtGui
import platform
import os
import sys
import traceback

from src.gui import Ui_MainWindow, set_application_font  # Import the generated module

# Глобальный обработчик исключений
def global_exception_handler(exctype, value, tb):
    """
    Глобальный обработчик исключений, который логирует ошибки вместо завершения программы
    """
    # Получаем строку с трассировкой стека
    tb_str = ''.join(traceback.format_exception(exctype, value, tb))
    # Логируем ошибку
    logging.critical(f"Необработанное исключение: {exctype.__name__}: {value}\n{tb_str}")
    # Выводим сообщение в консоль
    print(f"КРИТИЧЕСКАЯ ОШИБКА: {exctype.__name__}: {value}")
    # Не завершаем программу, а продолжаем выполнение

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
    
    # Создаем форматтер
    formatter = logging.Formatter(log_format, date_format)
    
    # Получаем корневой логгер
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Очищаем все обработчики, если они есть
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Добавляем обработчик для файла
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # Добавляем обработчик для консоли
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    logging.info('Логгирование инициализировано')

class MyMainWindow(QMainWindow):
    def __init__(self):
        logging.info('Инициализация главного окна')
        super().__init__()

        # Create an instance of the generated UI class
        self.ui = Ui_MainWindow()
        logging.info('Настройка пользовательского интерфейса')
        self.ui.setupUi(self)
        
        # Устанавливаем иконку окна и шрифт
        try:
            self.setWindowIcon(QtGui.QIcon('logo.jpg'))
            # Устанавливаем шрифт Arial для главного окна
            font = QtGui.QFont("Arial")
            self.setFont(font)
            logging.info('Иконка окна и шрифт установлены')
        except Exception as e:
            logging.error(f'Ошибка при установке иконки окна или шрифта: {e}')

        # Добавляем информацию о разрядности Python
        logging.info(f"Python разрядность: {platform.architecture()}")
        dll_path = 'resources/drivers/GAS.dll'
        # Добавляем информацию о текущем пути к DLL
        logging.info(f"Текущий путь к DLL: {os.path.abspath(dll_path)}")
        logging.info(f"DLL существует: {os.path.exists(dll_path)}")

if __name__ == "__main__":
    # Инициализируем логгирование
    setup_logging()
    
    # Устанавливаем глобальный обработчик исключений
    sys.excepthook = global_exception_handler
    
    logging.info('Запуск приложения')
    try:
        app = QApplication([])
        set_application_font(app)
        
        # Применяем стиль из QSS-файла
        try:
            app.setStyleSheet(Path('resources/themes/light.qss').read_text())
            logging.info('Стиль QSS успешно применен')
        except Exception as e:
            logging.error(f'Ошибка при применении стиля QSS: {e}')
            
        window = MyMainWindow()
        logging.info('Открытие окна в полноэкранном режиме')
        window.showMaximized()
        logging.info('Запуск главного цикла приложения')
        
        # Запускаем главный цикл приложения в блоке try-except
        try:
            app.exec_()
        except Exception as e:
            logging.critical(f'Критическая ошибка в главном цикле приложения: {e}', exc_info=True)
    except Exception as e:
        logging.critical(f'Критическая ошибка при запуске приложения: {e}', exc_info=True)

