import logging
import csv
import os
import subprocess
import threading
import time
from datetime import datetime

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QVBoxLayout, QGridLayout, QHBoxLayout, QDialog, QFileDialog
import json
import pyqtgraph as pg
import serial
import modbus_tk
import modbus_tk.defines as cst
from modbus_tk import modbus_rtu

from . import fetch_data
from . import transmissionPlot
from . import intensityPlot
from . import param_plot
from . import utility_functions
from .settings_window import SettingsWindow
from .modbus_window import ModbusWindow

first_start = True
int_max = 100000
simulation = 1
theme = ""
method_path = "resources/data/test-2.mtg"
fspec_path = "Не выбран"
plots_interval = 10
params_interval = "1 ч"
stop_threads = True
parameter = []
parameter_names = [""] * 16
days_threshold = 0
modbus_connected = False
device_num = 0
port = ''
timeout = 0
zoom = True

master = None


class Ui_MainWindow(object):
    def __init__(self):
        self.stop_event = threading.Event()

    def change_color(self):
        self.parent.setStyleSheet('background-color: red;')

    def save_to_archive(self, conc, y):
        date_now = datetime.today().strftime('%y_%m_%d')
        archive_name = f'Archive/{date_now}.csv'
        logging.info(f"Сохранение данных в архив: {archive_name}")

        try:
            if os.path.exists(archive_name):
                mode = 'a'
            else:
                mode = 'w'
            with open(archive_name, mode=mode) as employee_file:
                employee_writer = csv.writer(employee_file, delimiter=';', quotechar='"',
                                             quoting=csv.QUOTE_MINIMAL)
                result_to_write = [datetime.today().strftime('%y_%m_%d_%H_%M_%S')] + conc + y
                employee_writer.writerow(result_to_write)
            logging.info("Данные успешно сохранены в архив")
        except Exception as e:
            logging.error(f"Ошибка при сохранении в архив: {e}")

        # Очистка старых файлов
        current_time = datetime.now()
        directories = ["Archive/", "Reports/", "Spectra/"]
        extensions = [".csv", ".txt", ".spe"]
        logging.info(f"Начало очистки старых файлов (старше {utility_functions.days_threshold} дней)")

        for i in range(len(directories)):
            for filename in os.listdir(directories[i]):
                file_path = os.path.join(directories[i], filename)
                if filename.endswith(extensions[i]):
                    try:
                        date_str = filename[0:8]
                        file_date = datetime.strptime(date_str, '%y_%m_%d')
                        days_difference = (current_time - file_date).days
                        if days_difference > utility_functions.days_threshold:
                            os.remove(file_path)
                            logging.info(f"Удален старый файл: {file_path}")
                    except ValueError:
                        logging.warning(f"Невозможно определить дату файла: {filename}")

    def run_thread(self):
        utility_functions.stop_threads = False
        self.stop_event.clear()  # Сбрасываем событие остановки
        if self.thread is not None and self.thread.is_alive():
            self.stop_event.set()  # Сигнализируем старому потоку завершиться
            self.thread.join()  # Ждём завершения старого потока
        
        # Проверяем режим симуляции
        if utility_functions.simulation == "1":
            logging.info("Запуск в режиме симуляции")
            self.thread = threading.Thread(target=self.update_trans_plot, daemon=True)
            logging.info("Запускаем поток обычного измерения в режиме симуляции")
        else:
            # Если не режим симуляции, проверяем соединение ModBus
            if utility_functions.modbus_connected and utility_functions.master is not None:
                logging.info(f"Используем существующее соединение ModBus:")
                logging.info(f"Порт={utility_functions.port}, Адрес={utility_functions.device_num}, Таймаут={utility_functions.timeout}")
                
                # Запускаем поток измерения по каналам
                self.thread = threading.Thread(target=self.channel_measurement_thread, daemon=True)
                logging.info("Запускаем поток измерения по каналам")
            else:
                # Если нет соединения с ModBus и не режим симуляции, показываем ошибку и не запускаем измерение
                logging.error("Нет соединения ModBus. Необходимо настроить соединение в окне настроек ModBus.")
                QtWidgets.QMessageBox.warning(
                    self.parent, 
                    "Предупреждение", 
                    "Нет соединения ModBus. Необходимо настроить соединение в окне настроек ModBus.",
                    QtWidgets.QMessageBox.Ok
                )
                return  # Выходим из метода без запуска потока
        
        # Запускаем поток, если он был создан
        if hasattr(self, 'thread') and self.thread is not None:
            self.thread.start()
            self.start_button.setText("Остановить\nизмерение")
            self.start_button.clicked.connect(self.stop_thread)
            # Обновляем доступность кнопки взятия спектра пустой кюветы в окне настроек, если оно открыто
            if hasattr(self, 'modal_popup') and self.settings_window.isVisible():
                self.settings_window.fon_update_settings.setEnabled(False)
            self.plot1.clear()
            self.plot2.clear()

    def stop_thread(self):
        utility_functions.stop_threads = True
        self.stop_event.set()  # Устанавливаем событие остановки
        if self.thread is not None and self.thread.is_alive():
            self.thread.join(timeout=2)  # Ожидаем завершения с таймаутом
            if self.thread.is_alive():
                print("Поток не завершился вовремя, принудительное завершение невозможно (daemon)")
        self.start_button.setText("Начать\nизмерение")
        self.start_button.clicked.connect(self.run_thread)
        # Обновляем доступность кнопки взятия спектра пустой кюветы в окне настроек, если оно открыто
        if hasattr(self, 'modal_popup') and self.settings_window.isVisible():
            self.settings_window.fon_update_settings.setEnabled(True)
        self.plot1.clear()
        self.plot2.clear()
        
    def channel_measurement_thread(self):
        """Поток для измерения по каналам с переключением через ModBus"""
        self.icon_label.hide()
        self.fspec_error.setText("")
        logging.info("\n" + "="*50)
        logging.info("ЗАПУСК ПОТОКА ИЗМЕРЕНИЯ ПО КАНАЛАМ")
        logging.info("="*50)
        
        # Загружаем настройки каналов
        channel_config = utility_functions.load_channel_config()
        
        # Получаем параметры
        wait_time = channel_config["params"]["wait_time"]
        alarm_fix = channel_config["params"]["alarm_fix"]
        max_attempts = channel_config["params"]["attempts"]
        background_period = channel_config["params"]["background_period"] * 60  # Переводим в секунды
        measurements_per_channel = channel_config["params"]["measurements"]
        
        logging.info(f"Параметры измерения:")
        logging.info(f"- Время ожидания переключения (tп): {wait_time} сек")
        logging.info(f"- Фиксация аварии системы (АСПК): {'Да' if alarm_fix else 'Нет'}")
        logging.info(f"- Количество попыток переключения (k): {max_attempts}")
        logging.info(f"- Период измерения фона (tф): {background_period/60} мин")
        logging.info(f"- Количество измерений на канал (n): {measurements_per_channel}")
        
        # Время начала для отслеживания периода фонового спектра
        start_time = time.time()
        
        # Счетчик неудачных попыток переключения
        failed_attempts = 0
        
        # Проверяем соединение с ModBus
        if not utility_functions.check_modbus_connection():
            logging.error("Нет соединения с ModBus для измерения по каналам")
            QtWidgets.QMessageBox.warning(
                self.parent, 
                "Предупреждение", 
                "Нет соединения с ModBus. Переключение каналов невозможно.",
                QtWidgets.QMessageBox.Ok
            )
            self.error_out(-106)  # Код ошибки для отсутствия соединения
            return
            
        # Создаем объект для работы с каналами
        switcher = utility_functions.ChannelSwitcher()
        
        # Проверяем, инициализировано ли устройство
        status = switcher.read_status()
        if not status:
            logging.error("Не удалось получить статус устройства")
            self.error_out(-106)
            return
            
        is_initialized = status['initialization']
        logging.info(f"Статус инициализации устройства: {'инициализировано' if is_initialized else 'не инициализировано'}")
        
        if not is_initialized:
            logging.info("\n=== ЗАПУСК ИНИЦИАЛИЗАЦИИ УСТРОЙСТВА ===")
            
            # Запрос на инициализацию
            if not switcher.request_channel_switch(1):
                logging.error("Не удалось отправить запрос на инициализацию")
                self.error_out(-104)  # Код ошибки для неудачной инициализации
                return
                
            # Мониторим процесс инициализации
            if not switcher.monitor_initialization():
                logging.error("Ошибка инициализации устройства")
                self.error_out(-105)  # Код ошибки для неудачной инициализации
                return
                
            logging.info("✓ Инициализация устройства успешно завершена")
        else:
            logging.info("✓ Устройство уже инициализировано")
        
        # Проверяем готовность устройства
        if not switcher.wait_for_ready_state(timeout=10):
            logging.error("Устройство не готово к измерениям")
            self.error_out(-107)  # Код ошибки для неготовности устройства
            return
            
        # Переключаемся на канал 0 (пустая ячейка) в начале для измерения фона
        logging.info("\n=== ПЕРЕКЛЮЧЕНИЕ НА КАНАЛ 0 (ПУСТАЯ ЯЧЕЙКА) ДЛЯ ИЗМЕРЕНИЯ ФОНА ===")
        if not switcher.switch_to_channel(0, wait_time):
            logging.error("Не удалось переключиться на канал 0")
            self.error_out(-101)  # Используем код ошибки -101 для таймаута переключения
            return
            
        # Измеряем фоновый спектр перед началом цикла по каналам
        logging.info("Измерение начального фонового спектра")
        self.set_fixed_fon()
        
        # Основной цикл измерения
        logging.info("\n=== НАЧАЛО ЦИКЛА ИЗМЕРЕНИЙ ПО КАНАЛАМ ===")
        while not utility_functions.stop_threads:
            try:
                # Проверяем, не пора ли измерить фоновый спектр
                current_time = time.time()
                if current_time - start_time >= background_period:
                    logging.info(f"\n=== ПЕРИОДИЧЕСКОЕ ИЗМЕРЕНИЕ ФОНА (ПРОШЛО {background_period/60:.1f} МИН) ===")
                    
                    # Переключаемся на канал 0
                    logging.info("Переключение на канал 0 для измерения фона")
                    if not switcher.switch_to_channel(0, wait_time):
                        logging.error("Не удалось переключиться на канал 0")
                        if alarm_fix:
                            failed_attempts += 1
                            if failed_attempts >= max_attempts:
                                logging.error(f"Превышено количество попыток переключения ({max_attempts})")
                                self.error_out(-102)  # Используем код ошибки -102 для превышения попыток
                                break
                        continue
                    
                    # Выполняем измерение фона
                    logging.info("Измерение фонового спектра")
                    self.set_fixed_fon()
                    
                    # Сбрасываем счетчик времени
                    start_time = time.time()
                
                # Проходим по всем каналам
                for channel_num in range(1, 13):  # Каналы от 1 до 12
                    # Проверяем, активен ли канал
                    if not channel_config.get(f"channel_{channel_num}", {}).get("active", False):
                        logging.info(f"Канал {channel_num} неактивен, пропускаем")
                        continue
                        
                    # Переключаемся на канал
                    logging.info(f"\n=== ПЕРЕКЛЮЧЕНИЕ НА КАНАЛ {channel_num} ===")
                    if not switcher.switch_to_channel(channel_num, wait_time):
                        logging.error(f"Не удалось переключиться на канал {channel_num}")
                        if alarm_fix:
                            failed_attempts += 1
                            if failed_attempts >= max_attempts:
                                logging.error(f"Превышено количество попыток переключения ({max_attempts})")
                                self.error_out(-102)
                                break
                            continue
                        else:
                            # Если АСПК=нет, продолжаем измерение текущего канала
                            logging.info("АСПК=нет, продолжаем измерение текущего канала")
                            # Получаем текущий канал
                            current_channel = utility_functions.get_active_channel()
                            if current_channel >= 0:
                                channel_num = current_channel  # Используем текущий канал
                                logging.info(f"Используем текущий канал: {channel_num}")
                            else:
                                logging.error("Не удалось определить текущий канал")
                                continue
                    
                    # Выполняем измерения для текущего канала
                    logging.info(f"Начало измерений для канала {channel_num}")
                    for measurement in range(measurements_per_channel):
                        if utility_functions.stop_threads:
                            break
                            
                        logging.info(f"Измерение {measurement+1}/{measurements_per_channel} для канала {channel_num}")
                        # Выполняем измерение
                        self.update_trans_plot_single()
                        
                        # Пауза между измерениями
                        time.sleep(1)
                    
                    # Сбрасываем счетчик неудачных попыток после успешного измерения канала
                    failed_attempts = 0
                    
                    if utility_functions.stop_threads:
                        break
                
                # Проверяем сигнал остановки
                if self.stop_event.wait(timeout=1):
                    logging.info("Получен сигнал остановки")
                    break
                    
            except Exception as e:
                logging.error(f"Ошибка в потоке измерения каналов: {e}")
                self.error_out(-103)  # Используем код ошибки -103 для общей ошибки
                break
        
        logging.info("\n=== ЗАВЕРШЕНИЕ ПОТОКА ИЗМЕРЕНИЯ ПО КАНАЛАМ ===")

    def update_trans_plot_single(self):
        """Выполняет одно измерение (вынесено из update_trans_plot)"""
        # Обновляем значения в окне настроек, если оно открыто
        if hasattr(self, 'modal_popup') and self.settings_window.isVisible():
            self.settings_window.res_value.setText(str(fetch_data.res))
            self.settings_window.scans_value.setText(str(fetch_data.scans))
            self.settings_window.cuv_value.setText(str(fetch_data.cuv_length))

        if utility_functions.first_start:
            logging.info("Первый запуск - инициализация")
            self.plot1.enableAutoRange(axis=pg.ViewBox.YAxis)
            self.plot2.enableAutoRange(axis=pg.ViewBox.YAxis)
            res, warn = utility_functions.start_func()
            logging.info(f"Результат start_func: res={res}, warn={warn}")

            if res == 0:
                res, warn = utility_functions.init_func()
                logging.info(f"Результат init_func: res={res}, warn={warn}")

                if res == 0:
                    try:
                        x, y, y2 = utility_functions.read_fon_spe()
                        logging.info("Фоновый спектр успешно прочитан")
                        self.plot1.update(x, y, y2)

                        res, conc = utility_functions.get_value_func()
                        logging.info(f"Получены значения концентраций: res={res}, conc={conc}")

                        if res == 0:
                            # conc = [number for number in conc if number != 0]
                            # self.param_plots(conc, False)

                            self.generate_warnings(warn)
                            x, y = utility_functions.get_spectr_func()
                            self.save_to_archive(conc, y)
                            self.plot2.update(x, y)
                            logging.info("Графики успешно обновлены")
                        else:
                            logging.error(f"Ошибка получения значений: {res}")
                            self.error_out(res)
                            return False
                    except Exception as e:
                        logging.error(f"Ошибка при обработке данных: {e}")
                        return False
                else:
                    logging.error(f"Ошибка инициализации: {res}")
                    self.error_out(res)
                    return False
            else:
                logging.error(f"Ошибка запуска: {res}")
                self.error_out(res)
                return False

            utility_functions.zoom = False
            utility_functions.first_start = False
            self.timer1.start()
            logging.info("Первый запуск завершен успешно")
        else:
            logging.info("Обновление графиков")
            res, warn = utility_functions.init_func()
            if res == 0:
                x, y, y2 = utility_functions.read_fon_spe()
                self.plot1.update(x, y, y2)
                res, conc = utility_functions.get_value_func()
                if res == 0:
                    # conc = [number for number in conc if number != 0]
                    # self.param_plots(conc, False)
                    self.generate_warnings(warn)
                    x, y = utility_functions.get_spectr_func()
                    self.save_to_archive(conc, y)
                    self.plot2.update(x, y)
                else:
                    self.error_out(res)
                    return False
            else:
                self.error_out(res)
                return False
            self.timer1.restart()
        
        return True

    def run_fix_fon_thread(self):
        self.thread = threading.Thread(target=self.set_fixed_fon, daemon=True)
        self.thread.start()

    def generate_warnings(self, warning):
        self.warnings_box.clear()
        with open('config/config.json', 'r', encoding="utf-8") as file:
            json_data = json.load(file)
        warnings = str(bin(warning))
        warnings = warnings[::-1]
        for i in range(len(warnings)):
            if warnings[i] == '1':
                self.warnings_box.addItem(str(json_data["warnings"].get(str(i))))

    def error_out(self, res):
        with open('config/config.json', 'r', encoding="utf-8") as file:
            json_data = json.load(file)
        if res > 0:
            res = -500
        self.fspec_error.setText("Ошибка! " + str(json_data["errors"].get(str(res))))
        self.icon_label.show()
        self.stop_thread()

    def update_trans_plot(self):
        self.icon_label.hide()
        self.fspec_error.setText("")
        logging.info("Запуск обновления графиков")

        while not utility_functions.stop_threads:
            # Обновляем значения в окне настроек, если оно открыто
            if hasattr(self, 'modal_popup') and self.settings_window.isVisible():
                self.settings_window.res_value.setText(str(fetch_data.res))
                self.settings_window.scans_value.setText(str(fetch_data.scans))
                self.settings_window.cuv_value.setText(str(fetch_data.cuv_length))

            if utility_functions.first_start or self.timer1.hasExpired(utility_functions.plots_interval * 1000):
                if utility_functions.first_start:
                    logging.info("Первый запуск - инициализация")
                    self.plot1.enableAutoRange(axis=pg.ViewBox.YAxis)
                    self.plot2.enableAutoRange(axis=pg.ViewBox.YAxis)
                    res, warn = utility_functions.start_func()
                    logging.info(f"Результат start_func: res={res}, warn={warn}")

                    if res == 0:
                        res, warn = utility_functions.init_func()
                        logging.info(f"Результат init_func: res={res}, warn={warn}")

                        if res == 0:
                            try:
                                x, y, y2 = utility_functions.read_fon_spe()
                                logging.info("Фоновый спектр успешно прочитан")
                                self.plot1.update(x, y, y2)

                                res, conc = utility_functions.get_value_func()
                                logging.info(f"Получены значения концентраций: res={res}, conc={conc}")

                                if res == 0:
                                    # conc = [number for number in conc if number != 0]
                                    # self.param_plots(conc, False)

                                    self.generate_warnings(warn)
                                    x, y = utility_functions.get_spectr_func()
                                    self.save_to_archive(conc, y)
                                    self.plot2.update(x, y)
                                    logging.info("Графики успешно обновлены")
                                else:
                                    logging.error(f"Ошибка получения значений: {res}")
                                    self.error_out(res)
                                    break
                            except Exception as e:
                                logging.error(f"Ошибка при обработке данных: {e}")
                                break
                        else:
                            logging.error(f"Ошибка инициализации: {res}")
                            self.error_out(res)
                            break
                    else:
                        logging.error(f"Ошибка запуска: {res}")
                        self.error_out(res)
                        break

                    utility_functions.zoom = False
                    utility_functions.first_start = False
                    self.timer1.start()
                    logging.info("Первый запуск завершен успешно")
                else:
                    logging.info("Обновление графиков")
                    res, warn = utility_functions.init_func()
                    if res == 0:
                        x, y, y2 = utility_functions.read_fon_spe()
                        self.plot1.update(x, y, y2)
                        res, conc = utility_functions.get_value_func()
                        if res == 0:
                            self.generate_warnings(warn)
                            x, y = utility_functions.get_spectr_func()
                            self.save_to_archive(conc, y)
                            self.plot2.update(x, y)
                        else:
                            self.error_out(res)
                            break
                    else:
                        self.error_out(res)
                        break
                    self.timer1.restart()
            if self.stop_event.wait(timeout=1):
                logging.info("Получен сигнал остановки")
                break

    def set_fixed_fon(self):
        logging.info("Начало установки фиксированного фона")
        self.start_button.setEnabled(False)

        try:
            if utility_functions.first_start:
                res, warn = utility_functions.start_func()
                logging.info(f"Результат start_func: res={res}, warn={warn}")

                if res == 0:
                    res, warn = utility_functions.init_func()
                    logging.info(f"Результат init_func: res={res}, warn={warn}")

                    if res == 0:
                        if os.path.exists("Spectra/original.spe"):
                            os.remove("Spectra/original.spe")
                            logging.info("Удален старый файл original.spe")

                        os.rename("Spectra/fon.spe", "Spectra/original.spe")
                        logging.info("Фоновый спектр сохранен как original.spe")

                        utility_functions.first_start = False
                        date = datetime.today().strftime('%d.%m.%y %H:%M:%S')
                        # Обновляем дату в окне настроек, если оно открыто
                        if hasattr(self, 'modal_popup') and self.settings_window.isVisible():
                            self.settings_window.last_updated.setText("Дата обновления фона:\n" + date)

                        with open('config/config.json', 'r', encoding="utf-8") as file:
                            json_data = json.load(file)
                        json_data["fon_updated"] = date
                        with open('config/config.json', 'w') as f:
                            json.dump(json_data, f)
                        logging.info("Дата обновления фона сохранена в конфигурации")
                    else:
                        logging.error(f"Ошибка инициализации: {res}")
                        self.error_out(res)
                else:
                    logging.error(f"Ошибка запуска: {res}")
                    self.error_out(res)
            else:
                res, warn = utility_functions.init_func()
                if res == 0:
                    date = datetime.today().strftime('%d.%m.%y %H:%M:%S')
                    # Обновляем дату в окне настроек, если оно открыто
                    if hasattr(self, 'modal_popup') and self.settings_window.isVisible():
                        self.settings_window.last_updated.setText("Дата обновления фона:\n" + date)

                    with open('config/config.json', 'r', encoding="utf-8") as file:
                        json_data = json.load(file)
                    json_data["fon_updated"] = date
                    with open('config/config.json', 'w') as f:
                        json.dump(json_data, f)
                    if os.path.exists("Spectra/original.spe"):
                        os.remove("Spectra/original.spe")
                    os.rename("Spectra/fon.spe", "Spectra/original.spe")
                else:
                    self.error_out(res)

        except Exception as e:
            logging.error(f"Ошибка при установке фиксированного фона: {e}")
        finally:
            self.start_button.setEnabled(True)
            logging.info("Установка фиксированного фона завершена")

    def update_param_names(self):
        for i in range(16):
            self.params_labels[i].setText(utility_functions.parameter_names[i])

    def param_plots(self, conc, build):
        conc = [number for number in conc if utility_functions.int_max > number > -utility_functions.int_max]
        if build:
            layout = QGridLayout(self.scrollAreaWidgetContents)
            self.params_labels = [None] * 1
            for i in range(len(conc)):
                self.params_labels[i] = QtWidgets.QLabel()
                self.params_labels[i].setAlignment(QtCore.Qt.AlignCenter)
                self.params_labels[i].setText(utility_functions.parameter_names[i])
                param_value = QtWidgets.QLabel()
                self.param_values.append(param_value)
                font = QtGui.QFont("Arial", 16)
                param_value.setFont(font)
                param_value.setAlignment(QtCore.Qt.AlignCenter)
                param_value.setText("{:.2f}".format(conc[i]))

                param_layout = QGridLayout()

                spacer = QtWidgets.QSpacerItem(10, 800)
                param_layout.addItem(spacer, 0, 0, QtCore.Qt.AlignTop)
                param_layout.addWidget(self.params_labels[i], 1, 0)
                param_layout.addWidget(param_value, 2, 0)

                widget = pg.GraphicsLayoutWidget()
                widget.setFixedHeight(150)
                plot = param_plot.ParameterPlot(period=utility_functions.params_interval)
                plot.disableAutoRange(pg.ViewBox.XAxis)
                plot.setMouseEnabled(x=False, y=False)
                plot.hideButtons()
                utility_functions.parameter.append(plot)
                widget.addItem(plot)
                widget.setBackground("w")

                layout.addLayout(param_layout, i, 0, QtCore.Qt.AlignTop)
                layout.addWidget(widget, i, 1, QtCore.Qt.AlignTop)

        else:
            for i in range(len(conc)):
                self.param_values[i].setText("{:.2f}".format(conc[i]))
                utility_functions.parameter[i].update(conc[i], utility_functions.params_interval)
                utility_functions.parameter[i].show()

    def open_settings(self):
        self.settings_window = SettingsWindow(self)
        self.settings_window.show()

    def open_modbus_settings(self):
        self.modbus_window = ModbusWindow(self)
        self.modbus_window.show()

    def start_fspec(self):
        if os.path.exists(utility_functions.fspec_path):
            result = subprocess.run([utility_functions.fspec_path])
        else:
            self.fspec_error.setText("Неверный путь")

    def setupUi(self, MainWindow):
        self.thread = None
        self.timer1 = QtCore.QElapsedTimer()
        MainWindow.setObjectName("MainWindow")
        self.parent = MainWindow
        
        # Устанавливаем шрифт Arial для главного окна
        font = QtGui.QFont("Arial")
        MainWindow.setFont(font)
        
        # Шрифт для элементов с большим размером текста
        large_font = QtGui.QFont("Arial", 16)
        
        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.main_layout = QVBoxLayout(self.centralwidget)
        self.upper_left = QHBoxLayout()
        self.upper_right = QHBoxLayout()
        self.settings = QHBoxLayout()
        self.settings.setObjectName("settings")

        button_font = QtGui.QFont("Arial", 7)

        start_layout = QGridLayout()
        self.start_button = QtWidgets.QPushButton()
        self.start_button.setFixedSize(130, 100)
        self.start_button.setFont(button_font)
        self.start_button.setObjectName("start_button")
        self.start_button.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.start_button.clicked.connect(self.run_thread)
        if not os.path.exists("Spectra/original.spe"):
            self.start_button.setEnabled(False)
        start_layout.addWidget(self.start_button, 0, 0)

        group_box = QtWidgets.QGroupBox("Окно предупреждений")
        group_box.setFixedHeight(120)
        self.warnings_box = QtWidgets.QListWidget()
        self.warnings_box.setFixedHeight(80)
        group_layout = QVBoxLayout(group_box)
        group_layout.addWidget(self.warnings_box)
        start_layout.addWidget(group_box, 0, 2)

        logo_label = QtWidgets.QLabel()
        pixmap = QtGui.QPixmap("resources/images/logo_big.jpg")
        logo_label.setPixmap(pixmap)

        start_layout.addWidget(logo_label, 0, 1)

        error_font = QtGui.QFont("Arial", 6)
        error_font.setBold(True)
        self.label_layout = QHBoxLayout()
        self.icon_label = QtWidgets.QLabel()
        self.icon_label.setPixmap(
            QtWidgets.QApplication.style().standardIcon(QtWidgets.QStyle.SP_MessageBoxWarning).pixmap(32))
        self.icon_label.hide()
        self.label_layout.addStretch()

        self.label_layout.addWidget(self.icon_label)
        self.fspec_error = QtWidgets.QLabel()
        self.fspec_error.setText("")
        self.fspec_error.setFont(error_font)
        self.fspec_error.setAlignment(QtCore.Qt.AlignCenter)
        self.label_layout.addWidget(self.fspec_error)

        start_layout.addLayout(self.label_layout, 1, 0, 1, 3)
        self.upper_left.addLayout(start_layout)

        self.settings_button = QtWidgets.QPushButton()
        self.settings_button.setFixedSize(130, 100)
        self.settings_button.setFont(button_font)
        self.settings_button.clicked.connect(self.open_settings)
        set_layout = QVBoxLayout()
        set_layout.addWidget(self.settings_button)

        
        spacer = QtWidgets.QSpacerItem(0, 20, QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        set_layout.addItem(spacer)
        self.upper_right.addLayout(set_layout)
        self.graphs = QHBoxLayout()

        self.params_layout = QHBoxLayout()

        self.scrollArea = QtWidgets.QScrollArea()
        self.scrollArea.setWidgetResizable(True)
        self.params_layout.addWidget(self.scrollArea)

        self.scrollAreaWidgetContents = QtWidgets.QWidget()
        self.scrollArea.setWidget(self.scrollAreaWidgetContents)

        self.param_values = []

        self.plots_layout = QVBoxLayout()

        self.transmission = pg.GraphicsLayoutWidget()
        self.transmission.setBackground("w")
        self.plot1 = intensityPlot.IntensityPlot()
        self.transmission.addItem(self.plot1)
        self.plots_layout.addWidget(self.transmission)

        self.intensity = pg.GraphicsLayoutWidget()
        self.intensity.setBackground("w")
        self.plot2 = transmissionPlot.TransmissionPlot()
        self.intensity.addItem(self.plot2)
        self.plots_layout.addWidget(self.intensity)

        self.graphs.addLayout(self.params_layout)
        self.graphs.addLayout(self.plots_layout)

        self.settings.addLayout(self.upper_left)
        self.settings.addLayout(self.upper_right)

        self.main_layout.addLayout(self.settings)
        self.main_layout.addLayout(self.graphs)
        
        # Проверяем и обновляем config.json для добавления новых кодов ошибок
        try:
            config_path = 'config/config.json'
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding="utf-8") as file:
                    json_data = json.load(file)
                
                # Добавляем новые коды ошибок для переключения каналов, если их нет
                errors = json_data.get("errors", {})
                new_errors = {
                    "-100": "Ошибка отправки запроса на переключение канала",
                    "-101": "Таймаут ожидания переключения канала",
                    "-102": "Превышено количество попыток переключения канала",
                    "-103": "Общая ошибка при переключении каналов",
                    "-104": "Ошибка запроса на инициализацию устройства",
                    "-105": "Ошибка процесса инициализации устройства",
                    "-106": "Нет соединения с ModBus",
                    "-107": "Устройство не готово к измерениям"
                }
                
                updated = False
                for code, message in new_errors.items():
                    if code not in errors:
                        errors[code] = message
                        updated = True
                
                if updated:
                    json_data["errors"] = errors
                    with open(config_path, 'w', encoding="utf-8") as f:
                        json.dump(json_data, f, indent=4)
                    logging.info("Добавлены новые коды ошибок для переключения каналов в config.json")
        except Exception as e:
            logging.error(f"Ошибка при обновлении кодов ошибок в config.json: {e}")
        
        SettingsWindow(self).load()

        self.param_plots([0], True)
        MainWindow.setCentralWidget(self.centralwidget)

        self.retranslateUi(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "Приложение"))
        self.start_button.setText(_translate("MainWindow", "Начать\nизмерение"))
        self.settings_button.setText(_translate("MainWindow", "Настройки"))


def set_application_font(app):
    """
    Sets Arial font for the entire application
    
    Args:
        app: QApplication instance
    """
    font = QtGui.QFont("Arial")
    font.setPointSize(8)
    app.setFont(font)
