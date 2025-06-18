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

# Глобальные переменные
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
dll_path = "resources/drivers/GAS.dll"
my_dll = ctypes.WinDLL(dll_path)


class ChannelSwitcher:
    def __init__(self):
        """Инициализация объекта для управления переключением каналов"""
        self.is_initialized = False
        self.current_channel = None
        self.max_channels = 12
        
    def read_status(self):
        """Чтение и расшифровка регистра статуса"""
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
            logging.error(f"Ошибка при чтении статуса: {e}")
            return None
    
    def wait_for_ready_state(self, timeout=60):
        """Ожидание готовности устройства"""
        logging.info(f"Ожидание готовности устройства (таймаут: {timeout} сек)...")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            status = self.read_status()
            if status and status['ready'] and not status['working']:
                logging.info("Устройство готово к работе")
                return True
            elif status and status['general_error']:
                logging.error("Обнаружена ошибка устройства")
                return False
            
            time.sleep(1)
        
        logging.error(f"Таймаут ожидания готовности устройства ({timeout} сек)")
        return False
    
    def request_channel_switch(self, target_channel):
        """Запрос переключения на указанный канал"""
        global master, device_num
        
        if target_channel < 0 or target_channel > self.max_channels:
            logging.error(f"Недопустимый номер канала: {target_channel}. Допустимый диапазон: 0-{self.max_channels}")
            return False
        
        if not modbus_connected or master is None:
            logging.error("Нет соединения с ModBus для переключения канала")
            return False
        
        try:
            # Значение записывается со смещением +1
            register_value = target_channel + 1
            logging.info(f"Запрос переключения на канал {target_channel} (значение регистра: {register_value})")
            
            master.execute(device_num, cst.WRITE_SINGLE_REGISTER, CHANNEL_REQUEST_REGISTER, output_value=register_value)
            logging.info(f"Запрос на переключение отправлен")
            return True
            
        except Exception as e:
            logging.error(f"Ошибка при отправке запроса переключения: {e}")
            return False
    
    def monitor_channel_switching(self, target_channel, timeout=60):
        """Мониторинг процесса переключения канала"""
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
            logging.error("Переключение не началось в ожидаемое время")
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
                logging.error("Обнаружена ошибка во время переключения")
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
                    logging.error(f"Переключение завершено, но канал не соответствует ожидаемому: {final_channel} != {target_channel}")
                    return False
            
            time.sleep(0.5)
        
        logging.error(f"Переключение не завершилось в течение {timeout} секунд")
        return False
    
    def switch_to_channel(self, target_channel, wait_time=30):
        """Основная функция переключения канала"""
        logging.info(f"\n{'='*50}")
        logging.info(f"ЗАПРОС ПЕРЕКЛЮЧЕНИЯ НА КАНАЛ {target_channel}")
        logging.info(f"{'='*50}")
        
        # Проверяем готовность устройства
        if not self.wait_for_ready_state(timeout=10):
            logging.error("Устройство не готово к переключению")
            return False
        
        # Отправляем запрос на переключение
        if not self.request_channel_switch(target_channel):
            return False
        
        # Мониторим переключение канала
        return self.monitor_channel_switching(target_channel, timeout=wait_time)

    def monitor_initialization(self, timeout=120):
        """Мониторинг процесса инициализации"""
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
        
        logging.error(f"Инициализация не завершилась в течение {timeout} секунд")
        return False

# Глобальный объект для работы с каналами
channel_switcher = ChannelSwitcher()


def check_modbus_connection():
    """Проверяет соединение с ModBus"""
    global modbus_connected, master, device_num, simulation
    
    # Если включен режим симуляции, считаем что соединение есть
    if simulation == "1":
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
        logging.error(f"Ошибка соединения ModBus: {e}")
        modbus_connected = False
        return False


def switch_to_channel(channel_number):
    """
    Отправляет запрос на переключение на указанный канал
    
    Args:
        channel_number: Номер канала (0-12)
        
    Returns:
        bool: True если запрос отправлен успешно, False в случае ошибки
    """
    global channel_switcher
    return channel_switcher.switch_to_channel(channel_number)


def get_active_channel():
    """
    Получает номер активного канала
    
    Returns:
        int: Номер активного канала (0-12) или -1 в случае ошибки
    """
    global master, device_num
    
    if not modbus_connected or master is None:
        logging.error("Нет соединения с ModBus для получения активного канала")
        return -1
    
    try:
        # Канал возвращается со смещением +1
        channel = master.execute(device_num, cst.READ_HOLDING_REGISTERS, CHANNEL_CONFIRM_REGISTER, 1)[0] - 1
        logging.info(f"Текущий активный канал: {channel}")
        return channel
    except Exception as e:
        logging.error(f"Ошибка при получении активного канала: {e}")
        return -1


def get_channels_count():
    """
    Получает количество доступных каналов
    
    Returns:
        int: Количество доступных каналов или -1 в случае ошибки
    """
    global master, device_num
    
    if not modbus_connected or master is None:
        logging.error("Нет соединения с ModBus для получения количества каналов")
        return -1
    
    try:
        count = master.execute(device_num, cst.READ_HOLDING_REGISTERS, CHANNELS_COUNT_REGISTER, 1)[0]
        logging.info(f"Количество доступных каналов: {count}")
        return count
    except Exception as e:
        logging.error(f"Ошибка при получении количества каналов: {e}")
        return -1


def get_status():
    """
    Получает статус устройства
    
    Returns:
        int: Битовая маска статуса или -1 в случае ошибки
    """
    global master, device_num
    
    if not modbus_connected or master is None:
        logging.error("Нет соединения с ModBus для получения статуса")
        return -1
    
    try:
        status = master.execute(device_num, cst.READ_HOLDING_REGISTERS, STATUS_REGISTER, 1)[0]
        logging.info(f"Статус устройства: {bin(status)}")
        return status
    except Exception as e:
        logging.error(f"Ошибка при получении статуса: {e}")
        return -1


def is_device_ready():
    """
    Проверяет, готово ли устройство к переключению канала
    
    Returns:
        bool: True если устройство готово, False в противном случае
    """
    status = get_status()
    if status == -1:
        return False
    
    # Проверяем бит готовности (бит 1)
    return (status & (1 << STATUS_READY)) != 0


def is_device_working():
    """
    Проверяет, находится ли устройство в процессе работы
    
    Returns:
        bool: True если устройство в работе, False в противном случае
    """
    status = get_status()
    if status == -1:
        return False
    
    # Проверяем бит "в работе" (бит 2)
    return (status & (1 << STATUS_WORKING)) != 0


def has_error():
    """
    Проверяет наличие ошибок
    
    Returns:
        bool: True если есть ошибка, False в противном случае
    """
    status = get_status()
    if status == -1:
        return True
    
    # Проверяем бит общей ошибки (бит 3)
    return (status & (1 << STATUS_ERROR)) != 0


def wait_for_channel_switch(target_channel, timeout_sec):
    """
    Ожидает переключения на целевой канал с таймаутом
    
    Args:
        target_channel: Целевой канал
        timeout_sec: Таймаут в секундах
        
    Returns:
        bool: True если переключение успешно, False в случае таймаута или ошибки
    """
    global channel_switcher
    return channel_switcher.monitor_channel_switching(target_channel, timeout=timeout_sec)


def load_channel_config():
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
            "active": i == 1  # По умолчанию активен только первый канал
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
        logging.error(f"Ошибка при загрузке настроек каналов: {e}")
    
    return config


def read_fon_spe():
    binary_data = b""
    with open('Spectra/fon.spe', 'rb') as file:
        data = file.readlines()
        for line in data[36:-1]:
            binary_data += line
        x_first = float(data[32].decode("utf-8")[data[32].decode("utf-8").find("=") + 1:])
        x_last = float(data[33].decode("utf-8")[data[33].decode("utf-8").find("=") + 1:])
    with open("Spectra/values_bin.txt", "wb") as newFile:
        newFile.write(binary_data)
    arr = np.fromfile("Spectra/values_bin.txt", dtype=np.single)
    x_values = []
    binary_data = b""
    with open('Spectra/original.spe', 'rb') as file:
        data = file.readlines()
        for line in data[36:-1]:
            binary_data += line
    with open("Spectra/values_bin.txt", "wb") as newFile:
        newFile.write(binary_data)

    second_arr = np.fromfile("Spectra/values_bin.txt", dtype=np.single)
    for i in range(len(arr)):
        x_values.append(x_first + (i * ((x_last - x_first) / len(arr))))
    return x_values, arr, second_arr


def start_func():
    # pass
    start_function = my_dll.Start
    start_function.argtypes = [ctypes.POINTER(ctypes.c_int)]
    start_function.restypes = [ctypes.c_int]
    warning = (ctypes.c_int * 1)()
    result = start_function(warning)
    return result, warning[0]


def init_func():
    # pass
    init_function = my_dll.Init
    init_function.argtypes = [ctypes.POINTER(ctypes.c_int)]
    init_function.restypes = [ctypes.c_int]
    warning = (ctypes.c_int * 1)()
    result = init_function(warning)
    return result, warning[0]


def get_value_func():
    getValue_function = my_dll.GetValueFile
    getValue_function.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.POINTER(ctypes.c_double),
                                  ctypes.c_char_p]
    getValue_function.restypes = [ctypes.c_int]
    method = ctypes.c_char_p(method_path.encode('utf-8'))
    list_of_files = glob.glob('Spectra/*')[-4:][0]
    spectre = ctypes.c_char_p(str(list_of_files).encode('utf-8'))
    conc = (ctypes.c_double * 16)()
    password = b""
    result = getValue_function(method, spectre, conc, password)
    return result, list(conc)


def get_spectr_func():
    binary_data = b""
    with open('Spectra/fon.spe', 'rb') as file:
        data = file.readlines()
        for line in data[36:-1]:
            binary_data += line
        x_first = float(data[32].decode("utf-8")[data[32].decode("utf-8").find("=") + 1:])
        x_last = float(data[33].decode("utf-8")[data[33].decode("utf-8").find("=") + 1:])
    with open("Spectra/values_bin.txt", "wb") as newFile:
        newFile.write(binary_data)
    arr = np.fromfile("Spectra/values_bin.txt", dtype=np.single)
    x_values = []
    binary_data = b""
    with open('Spectra/original.spe', 'rb') as file:
        data = file.readlines()
        for line in data[36:-1]:
            binary_data += line
    with open("Spectra/values_bin.txt", "wb") as newFile:
        newFile.write(binary_data)

    second_arr = np.fromfile("Spectra/values_bin.txt", dtype=np.single)
    for i in range(len(arr)):
        arr[i] = abs(arr[i] - second_arr[i])
    for i in range(len(arr)):
        x_values.append(x_first + (i * ((x_last - x_first) / len(arr))))
    return x_values, list(arr)


def change_param_size(text):
    new_size = int(text)
    for i in range(16):
        parameter[i].change_size(new_size)


def is_device_initialized():
    """
    Проверяет, инициализировано ли устройство
    
    Returns:
        bool: True если устройство инициализировано, False в противном случае
    """
    status = get_status()
    if status == -1:
        return False
    
    # Проверяем бит инициализации (бит 0)
    return (status & (1 << STATUS_BITS['INITIALIZATION'])) != 0


# Функция для инициализации устройства
def initialize_device():
    """
    Запускает процесс инициализации устройства
    
    Returns:
        bool: True если запрос на инициализацию отправлен успешно, False в случае ошибки
    """
    global master, device_num
    
    if not modbus_connected or master is None:
        logging.error("Нет соединения с ModBus для инициализации устройства")
        return False
    
    try:
        # Для начала инициализации отправляем запрос на переключение на канал 1
        # В документации указано, что при первом запросе на переключение начинается инициализация
        master.execute(device_num, cst.WRITE_SINGLE_REGISTER, CHANNEL_REQUEST_REGISTER, output_value=2)  # Канал 1 + смещение 1
        logging.info("✓ Запрос на инициализацию отправлен")
        return True
    except Exception as e:
        logging.error(f"Ошибка при запуске инициализации: {e}")
        return False 