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

# Параметры подключения
MODBUS_PORT = "COM2"  # Измените на нужный COM-порт
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

def test_modbus_connection():
    """Тестирование подключения ModBus"""
    try:
        # Создаем соединение
        logging.info("Инициализация соединения ModBus...")
        master = modbus_rtu.RtuMaster(
            serial.Serial(
                port=MODBUS_PORT,
                baudrate=MODBUS_BAUDRATE,
                bytesize=MODBUS_BYTESIZE,
                parity=MODBUS_PARITY,
                stopbits=MODBUS_STOPBITS,
                xonxoff=0
            )
        )
        
        master.set_timeout(1.0)
        master.set_verbose(True)
        
        logging.info(f"Соединение установлено. Попытка связи с устройством {SLAVE_ADDRESS}...")
        
        # Чтение регистров
        try:
            logging.info("Чтение статусного регистра...")
            status = master.execute(SLAVE_ADDRESS, cst.READ_HOLDING_REGISTERS, STATUS_REGISTER, 1)[0]
            logging.info(f"Статус устройства: {bin(status)} (0b{bin(status)[2:].zfill(16)})")
            
            # Расшифровка битов статуса
            status_bits = {
                0: "Инициализация",
                1: "Готов",
                2: "В работе",
                3: "Общая ошибка",
                4: "Ошибка датчика верхнего уровня",
                5: "Ошибка датчика нижнего уровня",
                6: "Ошибка датчика ячейки",
                7: "Ошибка времени позиционирования",
                8: "Ошибка запроса номера канала",
                13: "Датчик верхнего уровня",
                14: "Датчик нижнего уровня",
                15: "Датчик ячейки"
            }
            
            logging.info("Расшифровка статуса:")
            for bit, description in status_bits.items():
                if status & (1 << bit):
                    logging.info(f"  Бит {bit}: {description} = ВКЛ")
                else:
                    logging.info(f"  Бит {bit}: {description} = ВЫКЛ")
            
            logging.info("Чтение регистра подтверждения канала...")
            channel = master.execute(SLAVE_ADDRESS, cst.READ_HOLDING_REGISTERS, CHANNEL_CONFIRM_REGISTER, 1)[0]
            logging.info(f"Текущий активный канал: {channel-1} (значение регистра: {channel})")
            
            logging.info("Чтение регистра количества каналов...")
            count = master.execute(SLAVE_ADDRESS, cst.READ_HOLDING_REGISTERS, CHANNELS_COUNT_REGISTER, 1)[0]
            logging.info(f"Количество доступных каналов: {count}")
            
            # Чтение всех регистров в диапазоне от 16400 до 16403
            logging.info("Чтение всех регистров управления каналами...")
            all_registers = master.execute(SLAVE_ADDRESS, cst.READ_HOLDING_REGISTERS, CHANNEL_REQUEST_REGISTER, 4)
            logging.info(f"Все регистры: {all_registers}")
            
            # # Попытка записи в регистр запроса канала
            # current_channel = channel - 1
            # target_channel = (current_channel + 1) % 13  # Следующий канал (с учетом максимума 12 каналов)
            #
            # logging.info(f"Попытка переключения с канала {current_channel} на канал {target_channel}...")
            # master.execute(SLAVE_ADDRESS, cst.WRITE_SINGLE_REGISTER, CHANNEL_REQUEST_REGISTER, output_value=target_channel + 1)
            # logging.info(f"Запрос на переключение на канал {target_channel} отправлен")
            
            # # Ожидание переключения
            # logging.info("Ожидание переключения канала...")
            # max_attempts = 30
            # for attempt in range(max_attempts):
            #     time.sleep(1)
            #     new_channel = master.execute(SLAVE_ADDRESS, cst.READ_HOLDING_REGISTERS, CHANNEL_CONFIRM_REGISTER, 1)[0] - 1
            #     new_status = master.execute(SLAVE_ADDRESS, cst.READ_HOLDING_REGISTERS, STATUS_REGISTER, 1)[0]
            #
            #     is_ready = bool(new_status & (1 << 1))
            #     is_working = bool(new_status & (1 << 2))
            #
            #     logging.info(f"Попытка {attempt+1}/{max_attempts}: Канал={new_channel}, Готов={is_ready}, В работе={is_working}")
            #
            #     if new_channel == target_channel and is_ready and not is_working:
            #         logging.info(f"Успешное переключение на канал {target_channel}")
            #         break
            #
            #     if attempt == max_attempts - 1:
            #         logging.warning(f"Не удалось переключиться на канал {target_channel} за {max_attempts} попыток")
            
        except modbus_tk.modbus.ModbusError as e:
            logging.error(f"Ошибка ModBus при чтении/записи регистров: {e}")
        
    except Exception as e:
        logging.error(f"Ошибка при подключении: {e}")
    finally:
        if 'master' in locals():
            master.close()
            logging.info("Соединение закрыто")

if __name__ == "__main__":
    print("Тестирование подключения ModBus")
    print(f"Порт: {MODBUS_PORT}, Скорость: {MODBUS_BAUDRATE}, Адрес устройства: {SLAVE_ADDRESS}")
    print("Для изменения порта отредактируйте переменную MODBUS_PORT в начале скрипта")
    
    test_modbus_connection() 