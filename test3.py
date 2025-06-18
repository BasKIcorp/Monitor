#!/usr/bin/env python
# -*- coding: utf-8 -*-

import time
import logging
import serial
import modbus_tk
import modbus_tk.defines as cst
from modbus_tk import modbus_rtu

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Параметры подключения (используем рабочие настройки из test2.py)
MODBUS_PORT = "COM2"
MODBUS_BAUDRATE = 9600
MODBUS_BYTESIZE = 8
MODBUS_PARITY = serial.PARITY_NONE
MODBUS_STOPBITS = 1
SLAVE_ADDRESS = 16

# Константы для работы с каналами
CHANNEL_REQUEST_REGISTER = 16400
CHANNEL_CONFIRM_REGISTER = 16401
CHANNELS_COUNT_REGISTER = 16402
STATUS_REGISTER = 16403

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

class ChannelSwitcher:
    def __init__(self):
        self.master = None
        self.is_initialized = False
        self.current_channel = None
        self.max_channels = 12
        
    def connect(self):
        """Подключение к устройству ModBus"""
        try:
            logging.info("Инициализация соединения ModBus...")
            self.master = modbus_rtu.RtuMaster(
                serial.Serial(
                    port=MODBUS_PORT,
                    baudrate=MODBUS_BAUDRATE,
                    bytesize=MODBUS_BYTESIZE,
                    parity=MODBUS_PARITY,
                    stopbits=MODBUS_STOPBITS,
                    xonxoff=0
                )
            )
            
            self.master.set_timeout(2.0)
            self.master.set_verbose(True)
            
            logging.info(f"Соединение установлено с устройством {SLAVE_ADDRESS}")
            return True
            
        except Exception as e:
            logging.error(f"Ошибка при подключении: {e}")
            return False
    
    def disconnect(self):
        """Отключение от устройства"""
        if self.master:
            self.master.close()
            logging.info("Соединение закрыто")
    
    def read_status(self):
        """Чтение и расшифровка регистра статуса"""
        try:
            status = self.master.execute(SLAVE_ADDRESS, cst.READ_HOLDING_REGISTERS, STATUS_REGISTER, 1)[0]
            
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
            logging.info(f"  Инициализация: {status_info['initialization']}")
            logging.info(f"  Готов: {status_info['ready']}")
            logging.info(f"  В работе: {status_info['working']}")
            logging.info(f"  Общая ошибка: {status_info['general_error']}")
            logging.info(f"  Датчик верхнего уровня: {status_info['upper_sensor']}")
            logging.info(f"  Датчик нижнего уровня: {status_info['lower_sensor']}")
            logging.info(f"  Датчик ячейки: {status_info['cell_sensor']}")
            
            if status_info['general_error']:
                logging.warning("Обнаружена общая ошибка!")
                if status_info['channel_request_error']:
                    logging.warning("Ошибка запроса номера канала!")
            
            return status_info
            
        except Exception as e:
            logging.error(f"Ошибка при чтении статуса: {e}")
            return None
    
    def read_current_channel(self):
        """Чтение текущего активного канала"""
        try:
            channel_value = self.master.execute(SLAVE_ADDRESS, cst.READ_HOLDING_REGISTERS, CHANNEL_CONFIRM_REGISTER, 1)[0]
            # Значение в регистре хранится со смещением +1
            actual_channel = channel_value - 1
            logging.info(f"Текущий активный канал: {actual_channel} (значение регистра: {channel_value})")
            self.current_channel = actual_channel
            return actual_channel
        except Exception as e:
            logging.error(f"Ошибка при чтении текущего канала: {e}")
            return None
    
    def read_channels_count(self):
        """Чтение количества доступных каналов"""
        try:
            count = self.master.execute(SLAVE_ADDRESS, cst.READ_HOLDING_REGISTERS, CHANNELS_COUNT_REGISTER, 1)[0]
            logging.info(f"Количество доступных каналов: {count}")
            return count
        except Exception as e:
            logging.error(f"Ошибка при чтении количества каналов: {e}")
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
        if target_channel < 0 or target_channel > self.max_channels:
            logging.error(f"Недопустимый номер канала: {target_channel}. Допустимый диапазон: 0-{self.max_channels}")
            return False
        
        try:
            # Значение записывается со смещением +1
            register_value = target_channel + 1
            logging.info(f"Запрос переключения на канал {target_channel} (значение регистра: {register_value})")
            
            self.master.execute(SLAVE_ADDRESS, cst.WRITE_SINGLE_REGISTER, CHANNEL_REQUEST_REGISTER, output_value=register_value)
            logging.info(f"Запрос на переключение отправлен")
            return True
            
        except Exception as e:
            logging.error(f"Ошибка при отправке запроса переключения: {e}")
            return False
    
    def monitor_initialization(self, timeout=120):
        """Мониторинг процесса инициализации"""
        logging.info("=== НАЧАЛО МОНИТОРИНГА ИНИЦИАЛИЗАЦИИ ===")
        start_time = time.time()
        
        # Шаг 1: Ожидание активации бита "В работе"
        logging.info("Шаг 1: Ожидание активации бита 'В работе'...")
        working_bit_activated = False
        
        while time.time() - start_time < timeout:
            status = self.read_status()
            if status and status['working']:
                logging.info("✓ Бит 'В работе' активирован - инициализация началась")
                working_bit_activated = True
                break
            time.sleep(0.5)
        
        if not working_bit_activated:
            logging.error("Бит 'В работе' не был активирован в ожидаемое время")
            return False
        
        # Шаг 2: Мониторинг датчика верхнего уровня
        logging.info("Шаг 2: Мониторинг датчика верхнего уровня...")
        upper_sensor_active = None
        
        while time.time() - start_time < timeout:
            status = self.read_status()
            if not status:
                continue
                
            # Отслеживаем изменения датчика верхнего уровня
            current_upper_sensor = status['upper_sensor']
            
            if upper_sensor_active is None:
                upper_sensor_active = current_upper_sensor
                logging.info(f"Начальное состояние датчика верхнего уровня: {'замкнут (1)' if upper_sensor_active else 'разомкнут (0)'}")
            elif upper_sensor_active != current_upper_sensor:
                logging.info(f"✓ Изменение состояния датчика верхнего уровня: {'замкнут (1)' if current_upper_sensor else 'разомкнут (0)'}")
                upper_sensor_active = current_upper_sensor
                
                # Если датчик разомкнулся (0), это означает, что достигли верхнего положения
                if not current_upper_sensor:
                    logging.info("✓ Достигнуто верхнее положение - ожидаем начала движения вниз")
                    break
            
            time.sleep(0.5)
        
        # Шаг 3: Мониторинг движения вниз и подсчета каналов
        logging.info("Шаг 3: Мониторинг движения вниз и подсчета каналов...")
        channels_found = 0
        last_cell_sensor_state = None
        lower_sensor_active = None
        
        while time.time() - start_time < timeout:
            status = self.read_status()
            if not status:
                continue
            
            # Отслеживаем изменения датчика нижнего уровня
            current_lower_sensor = status['lower_sensor']
            
            if lower_sensor_active is None:
                lower_sensor_active = current_lower_sensor
                logging.info(f"Начальное состояние датчика нижнего уровня: {'замкнут (1)' if lower_sensor_active else 'разомкнут (0)'}")
            elif lower_sensor_active != current_lower_sensor:
                logging.info(f"✓ Изменение состояния датчика нижнего уровня: {'замкнут (1)' if current_lower_sensor else 'разомкнут (0)'}")
                lower_sensor_active = current_lower_sensor
                
                # Если датчик разомкнулся (0), это означает, что достигли нижнего положения
                if not current_lower_sensor:
                    logging.info("✓ Достигнуто нижнее положение")
                    break
            
            # Отслеживаем срабатывания датчика ячейки (бит 15: 0 - есть, 1 - нет)
            current_cell_sensor = status['cell_sensor']
            if last_cell_sensor_state is not None and last_cell_sensor_state != current_cell_sensor:
                if not current_cell_sensor:  # Обнаружена ячейка (0 - есть)
                    channels_found += 1
                    logging.info(f"✓ Обнаружена ячейка #{channels_found}")
            last_cell_sensor_state = current_cell_sensor
            
            # Проверяем количество каналов в регистре
            count = self.read_channels_count()
            if count and count > 0 and count != self.max_channels:
                logging.info(f"Регистр количества каналов обновлен: {count}")
            
            time.sleep(0.5)
        
        # Шаг 4: Ожидание завершения инициализации
        logging.info("Шаг 4: Ожидание завершения инициализации...")
        
        while time.time() - start_time < timeout:
            status = self.read_status()
            if not status:
                continue
                
            # Проверяем биты статуса для определения завершения инициализации
            if status['initialization'] and status['ready'] and not status['working']:
                logging.info("✓ Инициализация завершена успешно!")
                logging.info(f"  - Активирован бит 'Инициализация'")
                logging.info(f"  - Активирован бит 'Готов'")
                logging.info(f"  - Деактивирован бит 'В работе'")
                
                # Проверяем количество найденных каналов
                count = self.read_channels_count()
                if count and count > 0:
                    logging.info(f"✓ Найдено каналов: {count} (по регистру), обнаружено: {channels_found} (по датчику)")
                
                # Проверяем текущий канал после инициализации
                current_channel = self.read_current_channel()
                logging.info(f"Текущий канал после инициализации: {current_channel}")
                
                self.is_initialized = True
                return True
            
            time.sleep(0.5)
        
        logging.error(f"Инициализация не завершилась в течение {timeout} секунд")
        return False
    
    def monitor_channel_switching(self, target_channel, timeout=60):
        """Мониторинг процесса переключения канала"""
        logging.info(f"=== НАЧАЛО ПЕРЕКЛЮЧЕНИЯ НА КАНАЛ {target_channel} ===")
        start_time = time.time()
        
        # Определяем направление движения
        current = self.read_current_channel()
        if current is None:
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
            current_channel = self.read_current_channel()
            if current_channel is not None and current_channel != last_channel:
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
                final_channel = self.read_current_channel()
                if final_channel == target_channel:
                    logging.info("✓ Переключение завершено успешно!")
                    logging.info(f"  - Активирован бит 'Готов'")
                    logging.info(f"  - Деактивирован бит 'В работе'")
                    logging.info(f"  - Финальный канал: {final_channel}")
                    return True
                else:
                    logging.error(f"Переключение завершено, но канал не соответствует ожидаемому: {final_channel} != {target_channel}")
                    return False
            
            time.sleep(0.5)
        
        logging.error(f"Переключение не завершилось в течение {timeout} секунд")
        return False
    
    def switch_to_channel(self, target_channel):
        """Основная функция переключения канала"""
        logging.info(f"\n{'='*50}")
        logging.info(f"ЗАПРОС ПЕРЕКЛЮЧЕНИЯ НА КАНАЛ {target_channel}")
        logging.info(f"{'='*50}")
        
        # Проверяем готовность устройства
        if not self.wait_for_ready_state(timeout=10):
            logging.error("Устройство не готово к переключению")
            return False
        
        # Читаем текущее состояние
        self.read_current_channel()
        self.read_channels_count()
        
        # Отправляем запрос на переключение
        if not self.request_channel_switch(target_channel):
            return False
        
        # Если устройство не инициализировано, мониторим инициализацию
        status = self.read_status()
        if status and not status['initialization']:
            logging.info("Устройство не инициализировано - начинается процесс инициализации")
            if not self.monitor_initialization():
                return False
        
        # Мониторим переключение канала
        return self.monitor_channel_switching(target_channel)

    def start_initialization(self):
        """Запускает процесс инициализации устройства"""
        logging.info("Запуск процесса инициализации...")
        
        try:
            # Для начала инициализации отправляем запрос на переключение на канал 1
            # В документации указано, что при первом запросе на переключение начинается инициализация
            self.master.execute(SLAVE_ADDRESS, cst.WRITE_SINGLE_REGISTER, CHANNEL_REQUEST_REGISTER, output_value=2)  # Канал 1 + смещение 1
            logging.info("✓ Запрос на инициализацию отправлен")
            return True
        except Exception as e:
            logging.error(f"Ошибка при запуске инициализации: {e}")
            return False

def main():
    """Основная функция для тестирования"""
    switcher = ChannelSwitcher()
    
    try:
        # Подключение
        if not switcher.connect():
            return
        
        # Чтение начального состояния
        logging.info("\n=== ЧТЕНИЕ НАЧАЛЬНОГО СОСТОЯНИЯ ===")
        switcher.read_status()
        switcher.read_current_channel()
        switcher.read_channels_count()

        # Запуск и мониторинг инициализации
        logging.info("\n=== ЗАПУСК ИНИЦИАЛИЗАЦИИ ===")
        if switcher.start_initialization():
            success = switcher.monitor_initialization()
            if success:
                logging.info("✓ Инициализация успешно завершена")
            else:
                logging.error("✗ Ошибка при инициализации")
        
        # # Тестирование переключения каналов
        # test_channels = [1, 5, 0, 3, 7]
        #
        # for channel in test_channels:
        #     success = switcher.switch_to_channel(channel)
        #     if success:
        #         logging.info(f"✓ Успешное переключение на канал {channel}")
        #     else:
        #         logging.error(f"✗ Ошибка переключения на канал {channel}")
        #
        #     # Пауза между переключениями
        #     time.sleep(2)
        
    except KeyboardInterrupt:
        logging.info("Программа прервана пользователем")
    except Exception as e:
        logging.error(f"Неожиданная ошибка: {e}")
    finally:
        switcher.disconnect()

if __name__ == "__main__":
    print("Тестирование алгоритма переключения каналов ПР-103")
    print(f"Порт: {MODBUS_PORT}, Скорость: {MODBUS_BAUDRATE}, Адрес устройства: {SLAVE_ADDRESS}")
    print("Для изменения настроек отредактируйте соответствующие константы")
    print("\nНачинаем тестирование...")
    
    main()