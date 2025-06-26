import ctypes
import logging
import csv
import glob
from pathlib import Path
import os
import serial
import modbus_tk
import modbus_tk.defines as cst
from modbus_tk import modbus_rtu
from datetime import datetime
import numpy as np
import json
import time
import subprocess
import math
from PyQt5.QtCore import QObject, pyqtSignal

# Глобальные переменные
from src import fetch_data

first_start = True
int_max = 100000
simulation = 0  # Целочисленный тип (0 или 1)
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


# Класс для передачи сигналов ошибок в GUI
class ErrorSignalEmitter(QObject):
    error_signal = pyqtSignal(str)

    def emit_error(self, error_text):
        """Отправляет сигнал с текстом ошибки"""
        self.error_signal.emit(error_text)


# Создаем глобальный экземпляр эмиттера сигналов
error_emitter = ErrorSignalEmitter()


# Функция для отправки ошибки в GUI
def send_error_to_gui(error_text):
    logging.error(error_text)  # Логируем ошибку
    error_emitter.emit_error(error_text)  # Отправляем сигнал


# Функция для загрузки параметра simulation из конфиг-файла
def load_simulation_from_config():
    global simulation
    try:
        if os.path.exists('config/config.json'):
            with open('config/config.json', 'r', encoding="utf-8") as file:
                json_data = json.load(file)

            # Загружаем параметр simulation и приводим к int
            if "simulation" in json_data:
                simulation = int(json_data["simulation"])
                logging.info(f"Загружен параметр simulation: {simulation}")
    except Exception as e:
        send_error_to_gui(f"Ошибка при загрузке параметра simulation: {e}")
        # В случае ошибки используем значение по умолчанию
        simulation = 0

    return simulation


# Константы для работы с каналами
CHANNEL_REQUEST_REGISTER = 16400
CHANNEL_CONFIRM_REGISTER = 16401
CHANNELS_COUNT_REGISTER = 16402
STATUS_REGISTER = 16403

# Биты статуса
STATUS_INITIALIZED = 0
STATUS_READY = 1
STATUS_WORKING = 2
STATUS_ERROR = 3
STATUS_CHANNEL_ERROR = 8

# Битовые маски для статуса
STATUS_BITS = {
    'INITIALIZATION': 0,
    'READY': 1,
    'WORKING': 2,
    'GENERAL_ERROR': 3,
    'UPPER_SENSOR_ERROR': 4,
    'LOWER_SENSOR_ERROR': 5,
    'CELL_SENSOR_ERROR': 6,
    'POSITIONING_TIME_ERROR': 7,
    'CHANNEL_REQUEST_ERROR': 8,
    'UPPER_SENSOR': 13,
    'LOWER_SENSOR': 14,
    'CELL_SENSOR': 15
}

# GAS.dll functions below
dll_path = "./GAS.dll"
my_dll = ctypes.WinDLL(dll_path)

# Путь к exequant.exe
exequant_path = ""


class ChannelSwitcher:
    def __init__(self):
        self.is_initialized = False
        self.current_channel = None
        self.max_channels = 12

    def read_status(self):
        global master, device_num

        if not modbus_connected or master is None:
            logging.error("Нет соединения с ModBus для чтения статуса")
            return None

        try:
            status = master.execute(device_num, cst.READ_HOLDING_REGISTERS, STATUS_REGISTER, 1)[0]

            status_info = {
                'raw_value': status,
                'binary': bin(status),
                'initialization': bool(status & (1 << STATUS_BITS['INITIALIZATION'])),
                'ready': bool(status & (1 << STATUS_BITS['READY'])),
                'working': bool(status & (1 << STATUS_BITS['WORKING'])),
                'general_error': bool(status & (1 << STATUS_BITS['GENERAL_ERROR'])),
                'upper_sensor_error': bool(status & (1 << STATUS_BITS['UPPER_SENSOR_ERROR'])),
                'lower_sensor_error': bool(status & (1 << STATUS_BITS['LOWER_SENSOR_ERROR'])),
                'cell_sensor_error': bool(status & (1 << STATUS_BITS['CELL_SENSOR_ERROR'])),
                'positioning_time_error': bool(status & (1 << STATUS_BITS['POSITIONING_TIME_ERROR'])),
                'channel_request_error': bool(status & (1 << STATUS_BITS['CHANNEL_REQUEST_ERROR'])),
                'upper_sensor': bool(status & (1 << STATUS_BITS['UPPER_SENSOR'])),
                'lower_sensor': bool(status & (1 << STATUS_BITS['LOWER_SENSOR'])),
                'cell_sensor': bool(status & (1 << STATUS_BITS['CELL_SENSOR']))
            }

            logging.info(f"Статус устройства: {status_info['binary']} ({status_info['raw_value']})")
            return status_info

        except Exception as e:
            send_error_to_gui(f"Ошибка при чтении статуса: {e}")
            return None

    def wait_for_ready_state(self, timeout=60):
        logging.info(f"Ожидание готовности устройства (таймаут: {timeout} сек)...")
        start_time = time.time()

        while time.time() - start_time < timeout:
            status = self.read_status()
            if status and status['ready'] and not status['working']:
                logging.info("Устройство готово к работе")
                return True
            elif status and status['general_error']:
                send_error_to_gui("Обнаружена ошибка устройства")
                return False

            time.sleep(1)

        send_error_to_gui(f"Таймаут ожидания готовности устройства ({timeout} сек)")
        return False

    def request_channel_switch(self, target_channel):
        global master, device_num

        if target_channel < 0 or target_channel > self.max_channels:
            send_error_to_gui(
                f"Недопустимый номер канала: {target_channel}. Допустимый диапазон: 0-{self.max_channels}")
            return False

        if not modbus_connected or master is None:
            send_error_to_gui("Нет соединения с ModBus для переключения канала")
            return False

        try:
            # Значение записывается со смещением +1
            register_value = target_channel + 1
            logging.info(f"Запрос переключения на канал {target_channel} (значение регистра: {register_value})")

            master.execute(device_num, cst.WRITE_SINGLE_REGISTER, CHANNEL_REQUEST_REGISTER, output_value=register_value)
            logging.info(f"Запрос на переключение отправлен")
            return True

        except Exception as e:
            send_error_to_gui(f"Ошибка при отправке запроса переключения: {e}")
            return False

    def monitor_channel_switching(self, target_channel, timeout=60):
        logging.info(f"=== НАЧАЛО ПЕРЕКЛЮЧЕНИЯ НА КАНАЛ {target_channel} ===")
        start_time = time.time()

        # Определяем направление движения
        current = get_active_channel()
        if current == -1:
            return False

        if target_channel > current:
            direction = "вверх"
            logging.info(f"Направление движения: {direction} (от канала {current} к каналу {target_channel})")
        elif target_channel < current:
            direction = "вниз"
            logging.info(f"Направление движения: {direction} (от канала {current} к каналу {target_channel})")
        else:
            logging.info(f"Уже находимся на канале {target_channel}")
            return True

        # Ожидание начала работы
        logging.info("Ожидание деактивации бита 'Готов' и активации бита 'В работе'...")
        while time.time() - start_time < timeout:
            status = self.read_status()
            if status and not status['ready'] and status['working']:
                logging.info("✓ Переключение началось")
                break
            time.sleep(0.5)
        else:
            send_error_to_gui("Переключение не началось в ожидаемое время")
            return False

        # Мониторинг процесса переключения
        logging.info("Мониторинг процесса переключения...")
        last_channel = current

        while time.time() - start_time < timeout:
            status = self.read_status()
            if not status:
                continue

            # Проверяем текущий канал
            current_channel = get_active_channel()
            if current_channel != -1 and current_channel != last_channel:
                logging.info(f"✓ Переключение: канал {last_channel} → канал {current_channel}")
                last_channel = current_channel

                if current_channel == target_channel:
                    logging.info(f"✓ Достигнут целевой канал {target_channel}")
                    break

            # Проверяем ошибки
            if status['general_error']:
                send_error_to_gui("Обнаружена ошибка во время переключения")
                return False

            time.sleep(1)

        # Ожидание завершения переключения
        logging.info("Ожидание завершения переключения...")
        while time.time() - start_time < timeout:
            status = self.read_status()
            if status and status['ready'] and not status['working']:
                final_channel = get_active_channel()
                if final_channel == target_channel:
                    logging.info("✓ Переключение завершено успешно!")
                    self.current_channel = final_channel
                    return True
                else:
                    logging.error(
                        f"Переключение завершено, но канал не соответствует ожидаемому: {final_channel} != {target_channel}")
                    return False

            time.sleep(0.5)

        send_error_to_gui(f"Переключение не завершилось в течение {timeout} секунд")
        return False

    def switch_to_channel(self, target_channel, wait_time=30):
        logging.info(f"\n{'=' * 50}")
        logging.info(f"ЗАПРОС ПЕРЕКЛЮЧЕНИЯ НА КАНАЛ {target_channel}")
        logging.info(f"{'=' * 50}")

        # Проверяем готовность устройства
        if not self.wait_for_ready_state(timeout=10):
            send_error_to_gui("Устройство не готово к переключению")
            return False

        # Отправляем запрос на переключение
        if not self.request_channel_switch(target_channel):
            return False

        # Мониторим переключение канала
        return self.monitor_channel_switching(target_channel, timeout=wait_time)

    def monitor_initialization(self, timeout=120):
        logging.info("=== НАЧАЛО МОНИТОРИНГА ИНИЦИАЛИЗАЦИИ ===")
        start_time = time.time()

        # Ожидание завершения инициализации
        logging.info("Ожидание завершения инициализации...")

        while time.time() - start_time < timeout:
            status = self.read_status()
            if not status:
                continue

            # Проверяем биты статуса для определения завершения инициализации
            if status['initialization'] and status['ready'] and not status['working']:
                logging.info("✓ Инициализация завершена успешно!")

                # Проверяем количество найденных каналов
                count = get_channels_count()
                if count > 0:
                    logging.info(f"✓ Найдено каналов: {count}")

                # Проверяем текущий канал после инициализации
                current_channel = get_active_channel()
                logging.info(f"Текущий канал после инициализации: {current_channel}")

                self.is_initialized = True
                return True

            time.sleep(0.5)

        send_error_to_gui(f"Инициализация не завершилась в течение {timeout} секунд")
        return False


# Глобальный объект для работы с каналами
channel_switcher = ChannelSwitcher()


def check_modbus_connection():
    global modbus_connected, master, device_num, simulation

    # Если включен режим симуляции, считаем что соединение есть
    if simulation == 1:
        logging.info("Режим симуляции активен, проверка ModBus пропущена")
        return True

    if not modbus_connected or master is None:
        logging.info("ModBus не подключен или мастер не инициализирован")
        return False

    try:
        # Пытаемся прочитать статусный регистр
        status = master.execute(device_num, cst.READ_HOLDING_REGISTERS, STATUS_REGISTER, 1)[0]
        logging.info(f"ModBus соединение активно, статус устройства: {bin(status)}")
        return True
    except Exception as e:
        send_error_to_gui(f"Ошибка соединения ModBus: {e}")
        modbus_connected = False
        return False


def switch_to_channel(channel_number):
    global channel_switcher
    return channel_switcher.switch_to_channel(channel_number)


def get_active_channel():
    global master, device_num, simulation

    # В режиме симуляции возвращаем канал 1
    if simulation == 1:
        logging.info("Режим симуляции активен, возвращаем канал 1")
        return 1

    if not modbus_connected or master is None:
        error_msg = "Нет соединения с ModBus для получения активного канала"
        send_error_to_gui(error_msg)
        return -1

    try:
        # Канал возвращается со смещением +1
        channel = master.execute(device_num, cst.READ_HOLDING_REGISTERS, CHANNEL_CONFIRM_REGISTER, 1)[0] - 1
        logging.info(f"Текущий активный канал: {channel}")
        return channel
    except Exception as e:
        error_msg = f"Ошибка при получении активного канала: {e}"
        send_error_to_gui(error_msg)
        return -1


def get_channels_count():
    global master, device_num

    if not modbus_connected or master is None:
        send_error_to_gui("Нет соединения с ModBus для получения количества каналов")
        return -1

    try:
        count = master.execute(device_num, cst.READ_HOLDING_REGISTERS, CHANNELS_COUNT_REGISTER, 1)[0]
        logging.info(f"Количество доступных каналов: {count}")
        return count
    except Exception as e:
        send_error_to_gui(f"Ошибка при получении количества каналов: {e}")
        return -1


def get_status():
    global master, device_num

    if not modbus_connected or master is None:
        send_error_to_gui("Нет соединения с ModBus для получения статуса")
        return -1

    try:
        status = master.execute(device_num, cst.READ_HOLDING_REGISTERS, STATUS_REGISTER, 1)[0]
        logging.info(f"Статус устройства: {bin(status)}")
        return status
    except Exception as e:
        send_error_to_gui(f"Ошибка при получении статуса: {e}")
        return -1


def is_device_ready():
    status = get_status()
    if status == -1:
        return False

    # Проверяем бит готовности (бит 1)
    return (status & (1 << STATUS_READY)) != 0


def is_device_working():
    status = get_status()
    if status == -1:
        return False

    # Проверяем бит "в работе" (бит 2)
    return (status & (1 << STATUS_WORKING)) != 0


def has_error():
    status = get_status()
    if status == -1:
        return True

    # Проверяем бит общей ошибки (бит 3)
    return (status & (1 << STATUS_ERROR)) != 0


def wait_for_channel_switch(target_channel, timeout_sec):
    global channel_switcher
    return channel_switcher.monitor_channel_switching(target_channel, timeout=timeout_sec)


def load_channel_config():
    config = {
        "params": {
            "wait_time": 30,  # Время ожидания подтверждения (tп)
            "alarm_fix": False,  # Фиксация аварии системы (АСПК)
            "attempts": 3,  # Количество попыток переключения (k)
            "background_period": 60,  # Период измерения фонового спектра (tф)
            "measurements": 5  # Количество измерений канала (n)
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
        send_error_to_gui(f"Ошибка при загрузке настроек каналов: {e}")

    return config


def get_channel_name(channel_num):
    if channel_num < 0 or channel_num > 12:
        return f"Канал {channel_num}"

    config = load_channel_config()
    return config.get(f"channel_{channel_num}", {}).get("name", f"АТ-{channel_num}")


def read_fon_spe(spe_file="./Spectra/fon.spe"):
    binary_data = b""
    with open(spe_file, 'rb') as file:
        data = file.readlines()
        for line in data[37:-1]:
            binary_data += line
        x_first = float(data[33].decode("utf-8")[data[33].decode("utf-8").find("=") + 1:])
        x_last = float(data[34].decode("utf-8")[data[34].decode("utf-8").find("=") + 1:])
    with open("./Spectra/values_bin.txt", "wb") as newFile:
        newFile.write(binary_data)
    arr = np.fromfile("./Spectra/values_bin.txt", dtype=np.single)
    x_values = []

    # Используем файл previous_fon.spe вместо поиска в директории Original
    binary_data = b""
    previous_fon_file = "./Spectra/empty_fon.spe"

    if not os.path.exists(previous_fon_file):
        send_error_to_gui("Файл empty_fon.spe не найден")
        return [], [], []

    with open(previous_fon_file, 'rb') as file:
        data = file.readlines()
        for line in data[37:-1]:
            binary_data += line
    with open("./Spectra/values_bin.txt", "wb") as newFile:
        newFile.write(binary_data)

    second_arr = np.fromfile("./Spectra/values_bin.txt", dtype=np.single)
    for i in range(len(arr)):
        x_values.append(x_first + (i * ((x_last - x_first) / len(arr))))
    return x_values, arr, second_arr


def start_func():
    if my_dll is None:
        error_msg = "DLL не загружена, невозможно выполнить функцию Start"
        send_error_to_gui(error_msg)
        return -1, 0
        
    try:
        start_function = my_dll.Start
        start_function.argtypes = [ctypes.POINTER(ctypes.c_int)]
        start_function.restypes = [ctypes.c_int]
        warning = (ctypes.c_int * 1)()
        result = start_function(warning)
        return result, warning[0]
    except Exception as e:
        error_msg = f"Ошибка при вызове функции Start из DLL: {str(e)}"
        send_error_to_gui(error_msg)
        return -1, 0


def init_func():
    if my_dll is None:
        error_msg = "DLL не загружена, невозможно выполнить функцию Init"
        send_error_to_gui(error_msg)
        return -1, 0
        
    try:
        init_function = my_dll.Init
        init_function.argtypes = [ctypes.POINTER(ctypes.c_int)]
        init_function.restypes = [ctypes.c_int]
        warning = (ctypes.c_int * 1)()
        result = init_function(warning)
        return result, warning[0]
    except Exception as e:
        error_msg = f"Ошибка при вызове функции Init из DLL: {str(e)}"
        send_error_to_gui(error_msg)
        return -1, 0


def change_param_size(text):
    new_size = int(text)
    for i in range(16):
        parameter[i].change_size(new_size)


def is_device_initialized():
    status = get_status()
    if status == -1:
        return False

    # Проверяем бит инициализации (бит 0)
    return (status & (1 << STATUS_BITS['INITIALIZATION'])) != 0


# Функция для инициализации устройства
def initialize_device():
    global master, device_num

    if not modbus_connected or master is None:
        send_error_to_gui("Нет соединения с ModBus для инициализации устройства")
        return False

    try:
        # Для начала инициализации отправляем запрос на переключение на канал 1
        # В документации указано, что при первом запросе на переключение начинается инициализация
        master.execute(device_num, cst.WRITE_SINGLE_REGISTER, CHANNEL_REQUEST_REGISTER,
                       output_value=2)  # Канал 1 + смещение 1
        logging.info("✓ Запрос на инициализацию отправлен")
        return True
    except Exception as e:
        send_error_to_gui(f"Ошибка при запуске инициализации: {e}")
        return False


def spectrum_to_dat(x_values, y_values):
    count_value = len(y_values)

    if exequant_path:
        exequant_dir = os.path.dirname(exequant_path)

        # Определяем путь к файлу 1.dat
        dat_file_path = os.path.join(exequant_dir, "input.dat")

        try:
            with open(dat_file_path, 'w') as dat_file:
                for i in range(count_value):
                    dat_file.write(f"{x_values[i]:.6E}\t{y_values[i]:.7E}\n")
                dat_file.write(f"{12501.55:.6E}\t{y_values[count_value - 1]:.7E}\n")

            logging.info(f"Файл input.dat успешно создан по пути: {dat_file_path}")
            return 0
        except Exception as e:
            logging.error(f"Ошибка при записи файла input.dat: {e}")
    else:
        logging.error("Путь к exequant не задан, невозможно создать файл input.dat")

    return -1


def run_exequant():
    print(exequant_path)
    exequant_dir = os.path.dirname(exequant_path)
    input_spectrum_path = os.path.join(exequant_dir, "input.dat")
    model = os.path.join(exequant_dir, "1.mmq")

    if not exequant_path:
        logging.error("Путь к exequant.exe не указан")
        return None

    if not os.path.exists(exequant_path):
        logging.error(f"Файл exequant.exe не найден по указанному пути: {exequant_path}")
        return None

    if not os.path.exists(input_spectrum_path):
        logging.error(f"Файл спектра .dat не найден: {input_spectrum_path}")
        return None

    try:
        # Формируем команду
        cmd = f'"{exequant_path}" --model {model} --input "{input_spectrum_path}" --only_print'

        # Запускаем процесс с контролем ошибок
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        except subprocess.TimeoutExpired:
            logging.error("Превышено время ожидания выполнения exequant.exe (30 секунд)")
            return None
        except subprocess.SubprocessError as e:
            logging.error(f"Ошибка при запуске процесса exequant.exe: {str(e)}")
            return None

        # Проверяем код возврата
        if result.returncode != 0:
            logging.error(f"Ошибка выполнения exequant.exe, код возврата: {result.returncode}")
            logging.error(f"Сообщение об ошибке: {result.stderr}")
            return None

        # Проверяем наличие вывода
        if not result.stdout:
            logging.error("Пустой вывод от exequant.exe")
            return None

        try:
            # Парсим JSON из вывода
            result_json = json.loads(result.stdout)

            # Проверяем новую структуру JSON
            if "input.dat" not in result_json or "Цет. число" not in result_json["input.dat"] or "value" not in \
                    result_json["input.dat"]["Цет. число"]:
                logging.error(f"Неверная структура JSON от exequant.exe: {result.stdout}")
                return None

            # Извлекаем значение параметра "Цет. число"
            value = result_json["input.dat"]["Цет. число"]["value"]

            return value
        except json.JSONDecodeError as e:
            logging.error(f"Ошибка при разборе JSON от exequant.exe: {e}")
            logging.error(f"Полученный вывод: {result.stdout}")
            return None
    except Exception as e:
        logging.error(f"Ошибка при запуске exequant.exe: {e}")
        return None


def loadParam():
    if my_dll is None:
        error_msg = "DLL не загружена, невозможно выполнить функцию LoadParam"
        send_error_to_gui(error_msg)
        return False
        
    try:
        load_param_function = my_dll.LoadParam
        load_param_function.argtypes = []
        load_param_function.restype = None

        logging.info("Вызов LoadParam для загрузки параметров из ini-файлов")
        load_param_function()
        logging.info("Параметры успешно загружены из ini-файлов")
        return True
    except Exception as e:
        send_error_to_gui(f"Ошибка при вызове LoadParam: {str(e)}")
        return False


def getValueSpecFormula():
    binary_data = b""
    with open("./Spectra/empty_fon.spe", 'rb') as file:
        data = file.readlines()
        for line in data[37:-1]:
            binary_data += line
        x_first = float(data[33].decode("utf-8")[data[33].decode("utf-8").find("=") + 1:])
        x_last = float(data[34].decode("utf-8")[data[34].decode("utf-8").find("=") + 1:])
    with open("./Spectra/values_bin.txt", "wb") as newFile:
        newFile.write(binary_data)
    arr = np.fromfile("./Spectra/values_bin.txt", dtype=np.single)
    x_values = []

    latest_original_file = "./Spectra/fon.spe"
    binary_data = b""
    with open(latest_original_file, 'rb') as file:
        data = file.readlines()
        for line in data[37:-1]:
            binary_data += line
    with open("./Spectra/values_bin.txt", "wb") as newFile:
        newFile.write(binary_data)

    second_arr = np.fromfile("./Spectra/values_bin.txt", dtype=np.single)

    # Создаем массив x_values
    for i in range(len(arr)):
        x_values.append(x_first + (i * ((x_last - x_first) / len(arr))))

    # Расчет третьего списка по формуле D=-(log(Isam/Iref)*L)/(L+dL)
    # Константы
    L = fetch_data.cuv_length
    
    # Загружаем поправку на толщину кюветы из конфига
    try:
        with open('config/config.json', 'r', encoding="utf-8") as file:
            json_data = json.load(file)
        dL = json_data.get("cuv_correction", 0)
    except Exception as e:
        logging.error(f"Ошибка при загрузке поправки на толщину кюветы: {e}")
        dL = 0

    # Создаем выходной массив
    output_arr = []

    # Применяем формулу для каждого элемента
    for i in range(len(arr)):
        if i < len(second_arr) and arr[i] != 0:  # Проверка деления на ноль
            # Формула: D=-(log(Isam/Iref)*L)/(L+dL)
            D = -(np.log10(abs(second_arr[i] / arr[i])) * L) / (L + dL)
            output_arr.append(D)
        else:
            output_arr.append(0)  # Если данные некорректны, добавляем 0

    logging.info(f"Рассчитан массив поглощения из {len(output_arr)} элементов")

    return x_values, output_arr
