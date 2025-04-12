import struct
import sys
import time

import modbus_tk
import modbus_tk.defines as cst
from modbus_tk import modbus_rtu
import serial



def main():
    """main"""
    logger = modbus_tk.utils.create_logger(name="console", record_format="%(message)s")
    print("Введите порт:")
    PORT = input()
    server = modbus_rtu.RtuServer(serial.Serial(PORT))

    try:
        logger.info("running...")

        server.start()

        slave_1 = server.add_slave(1)
        slave_1.add_block('one', cst.HOLDING_REGISTERS, 0, 100)
        slave_1.add_block('two', cst.HOLDING_REGISTERS, 100, 110)
        while True:
            slave = server.get_slave(1)
            values = slave.get_values('one', 0, 32)
            for i in range(16):
                combined_value = (values[i * 2] << 16) | values[(i * 2) + 1]
                res = struct.unpack('>f', struct.pack('>I', combined_value))[0]
                sys.stdout.write('параметр %s: %s; ' % (str(i+1), str(res)))
            sys.stdout.write('\n')
            values = slave.get_values('two', 100, 2)
            sys.stdout.write('коды ошибки и предупреждений: %s\r\n' % (str(values)))
            time.sleep(10)
    finally:
        server.stop()

if __name__ == "__main__":
    main()