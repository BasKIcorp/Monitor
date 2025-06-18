import struct
import numpy as np
import os
import re
import io
import traceback

def read_spc_file(file_path):
    """
    Читает файл .spc и преобразует бинарные данные в читаемый вид
    
    Args:
        file_path (str): Путь к файлу .spc
        
    Returns:
        tuple: (x_values, y_values) - данные спектра
    """
    print(f"Чтение файла: {file_path}")
    
    # Проверка существования файла
    if not os.path.exists(file_path):
        print(f"Ошибка: Файл {file_path} не найден")
        return None, None
    
    try:
        # Сначала пробуем первый метод чтения
        result = read_spc_method1(file_path)
        if result[0] is not None:
            return result
        
        # Если первый метод не сработал, пробуем второй
        print("Первый метод чтения не удался, пробуем второй метод...")
        result = read_spc_method2(file_path)
        if result[0] is not None:
            return result
        
        # Если второй метод не сработал, пробуем третий
        print("Второй метод чтения не удался, пробуем третий метод...")
        return read_spc_method3(file_path)
    
    except Exception as e:
        print(f"Ошибка при чтении файла: {e}")
        traceback.print_exc()
        return None, None

def read_spc_method1(file_path):
    """
    Первый метод чтения файла .spc
    """
    try:
        with open(file_path, 'rb') as file:
            # Чтение заголовка файла .spc
            # Формат SPC отличается от SPE, поэтому используем другой подход
            
            # Чтение первых 512 байт заголовка
            header = file.read(512)
            
            # Извлечение версии файла (первые 2 байта)
            file_version = struct.unpack('B', header[0:1])[0]
            print(f"Версия файла SPC: {file_version}")
            
            # Извлечение количества точек (байты 22-24)
            n_points = struct.unpack('<H', header[22:24])[0]
            print(f"Количество точек: {n_points}")
            
            # Извлечение начальной и конечной точки X (байты 16-20)
            first_x = struct.unpack('<f', header[16:20])[0]
            
            # Извлечение шага по X (байты 24-28)
            x_step = struct.unpack('<f', header[24:28])[0]
            
            # Вычисление конечной точки X
            last_x = first_x + (n_points - 1) * x_step
            
            print(f"Параметры спектра:")
            print(f"  Начальная точка X: {first_x}")
            print(f"  Шаг по X: {x_step}")
            print(f"  Конечная точка X: {last_x}")
            
            # Создаем массив значений X
            x_values = np.linspace(first_x, last_x, n_points)
            
            # Переходим к данным (после заголовка)
            file.seek(512)
            
            # Чтение данных Y
            y_values = []
            
            # Определяем формат данных (обычно 4-байтовые float)
            for i in range(n_points):
                try:
                    value = struct.unpack('<f', file.read(4))[0]
                    y_values.append(value)
                except struct.error:
                    print(f"Ошибка чтения данных в позиции {i}")
                    break
            
            print(f"Прочитано {len(y_values)} значений Y")
            
            # Проверяем, что количество прочитанных значений соответствует ожидаемому
            if len(y_values) != n_points:
                print(f"Предупреждение: прочитано {len(y_values)} значений, ожидалось {n_points}")
                return None, None
                
            return x_values, y_values
    
    except Exception as e:
        print(f"Ошибка при чтении файла методом 1: {e}")
        return None, None

def read_spc_method2(file_path):
    """
    Второй метод чтения файла .spc
    Этот метод предполагает другую структуру файла
    """
    try:
        with open(file_path, 'rb') as file:
            # Чтение всего файла в память
            data = file.read()
            
            # Пытаемся найти начало данных
            # В некоторых форматах SPC данные могут начинаться после определенной сигнатуры
            
            # Предположим, что заголовок имеет фиксированный размер 256 байт
            header_size = 256
            
            # Чтение информации о количестве точек (предположительно в байтах 4-8)
            n_points = struct.unpack('<I', data[4:8])[0]
            if n_points > 10000:  # Проверка на разумное значение
                n_points = struct.unpack('<H', data[4:6])[0]
            
            print(f"Метод 2 - Количество точек: {n_points}")
            
            # Чтение начальной точки X и шага (предположительно в байтах 8-16)
            first_x = struct.unpack('<f', data[8:12])[0]
            x_step = struct.unpack('<f', data[12:16])[0]
            
            # Вычисление конечной точки X
            last_x = first_x + (n_points - 1) * x_step
            
            print(f"Метод 2 - Параметры спектра:")
            print(f"  Начальная точка X: {first_x}")
            print(f"  Шаг по X: {x_step}")
            print(f"  Конечная точка X: {last_x}")
            
            # Создаем массив значений X
            x_values = np.linspace(first_x, last_x, n_points)
            
            # Чтение данных Y
            y_values = []
            
            # Данные начинаются после заголовка
            for i in range(n_points):
                offset = header_size + i * 4
                if offset + 4 <= len(data):
                    try:
                        value = struct.unpack('<f', data[offset:offset+4])[0]
                        y_values.append(value)
                    except struct.error:
                        print(f"Ошибка чтения данных в позиции {i}")
                        break
            
            print(f"Метод 2 - Прочитано {len(y_values)} значений Y")
            
            # Если мы не смогли прочитать достаточно данных, попробуем другой формат
            if len(y_values) < n_points / 2:
                print("Недостаточно данных прочитано, пробуем другой формат...")
                
                # Попробуем прочитать данные как 2-байтовые целые числа
                y_values = []
                for i in range(n_points):
                    offset = header_size + i * 2
                    if offset + 2 <= len(data):
                        try:
                            value = struct.unpack('<h', data[offset:offset+2])[0]
                            y_values.append(float(value))
                        except struct.error:
                            print(f"Ошибка чтения данных в позиции {i}")
                            break
                
                print(f"Метод 2 (альтернативный формат) - Прочитано {len(y_values)} значений Y")
            
            # Проверяем, что мы прочитали достаточно данных
            if len(y_values) < n_points / 2:
                print(f"Метод 2: Недостаточно данных прочитано ({len(y_values)} из {n_points})")
                return None, None
                
            return x_values, y_values
    
    except Exception as e:
        print(f"Ошибка при чтении файла методом 2: {e}")
        return None, None

def read_spc_method3(file_path):
    """
    Третий метод чтения файла .spc
    Использует более общий подход к чтению бинарных данных
    """
    try:
        # Чтение файла как бинарные данные
        with open(file_path, 'rb') as file:
            data = file.read()
        
        # Пробуем найти сигнатуру данных
        # В некоторых форматах SPC используется определенная сигнатура для обозначения начала данных
        
        # Пробуем разные смещения для заголовка
        header_sizes = [128, 256, 512, 1024]
        
        for header_size in header_sizes:
            if header_size >= len(data):
                continue
                
            print(f"Метод 3 - Пробуем заголовок размером {header_size} байт")
            
            # Пробуем разные форматы для количества точек
            try:
                # Предполагаем, что количество точек находится в начале файла (4-8 байт)
                n_points = struct.unpack('<I', data[4:8])[0]
                
                # Проверка на разумное значение
                if n_points > 10000 or n_points < 10:
                    # Пробуем другой формат
                    n_points = struct.unpack('<H', data[4:6])[0]
                
                print(f"Метод 3 - Количество точек: {n_points}")
                
                # Предполагаем, что данные начинаются после заголовка
                # Пробуем разные форматы данных
                
                # Формат 1: 4-байтовые float
                y_values_float = []
                for i in range(n_points):
                    offset = header_size + i * 4
                    if offset + 4 <= len(data):
                        try:
                            value = struct.unpack('<f', data[offset:offset+4])[0]
                            y_values_float.append(value)
                        except:
                            pass
                
                # Формат 2: 2-байтовые int
                y_values_int = []
                for i in range(n_points):
                    offset = header_size + i * 2
                    if offset + 2 <= len(data):
                        try:
                            value = struct.unpack('<h', data[offset:offset+2])[0]
                            y_values_int.append(float(value))
                        except:
                            pass
                
                # Выбираем формат, который дал больше данных
                if len(y_values_float) >= len(y_values_int) and len(y_values_float) >= n_points / 2:
                    y_values = y_values_float
                    print(f"Метод 3 - Используем 4-байтовые float, прочитано {len(y_values)} значений")
                elif len(y_values_int) >= n_points / 2:
                    y_values = y_values_int
                    print(f"Метод 3 - Используем 2-байтовые int, прочитано {len(y_values)} значений")
                else:
                    continue  # Пробуем следующий размер заголовка
                
                # Создаем массив значений X
                # Предполагаем, что данные равномерно распределены от 0 до n_points-1
                x_values = np.linspace(0, n_points-1, len(y_values))
                
                print(f"Метод 3 - Успешно прочитано {len(y_values)} значений")
                return x_values, y_values
                
            except Exception as e:
                print(f"Метод 3 - Ошибка при обработке заголовка размером {header_size}: {e}")
                continue
        
        # Если ни один из подходов не сработал, пробуем самый простой подход
        print("Метод 3 - Пробуем простой подход без анализа заголовка")
        
        # Предполагаем, что данные начинаются с определенного смещения
        # и представляют собой последовательность 4-байтовых float
        header_size = 512  # Предполагаемый размер заголовка
        
        # Определяем количество точек как (размер_файла - размер_заголовка) / размер_float
        n_points = (len(data) - header_size) // 4
        
        if n_points > 0:
            print(f"Метод 3 - Простой подход, предполагаемое количество точек: {n_points}")
            
            # Чтение данных Y
            y_values = []
            for i in range(n_points):
                offset = header_size + i * 4
                if offset + 4 <= len(data):
                    try:
                        value = struct.unpack('<f', data[offset:offset+4])[0]
                        # Проверка на разумное значение
                        if -1e10 < value < 1e10:  # Отфильтровываем очень большие/маленькие значения
                            y_values.append(value)
                        else:
                            y_values.append(0.0)  # Заменяем некорректные значения на 0
                    except:
                        y_values.append(0.0)
            
            # Создаем массив значений X
            x_values = np.linspace(0, len(y_values)-1, len(y_values))
            
            print(f"Метод 3 - Простой подход, прочитано {len(y_values)} значений")
            return x_values, y_values
        
        print("Метод 3 - Не удалось прочитать данные")
        return None, None
        
    except Exception as e:
        print(f"Ошибка при чтении файла методом 3: {e}")
        traceback.print_exc()
        return None, None

def display_spectrum_data(x_values, y_values, num_points=20):
    """
    Выводит информацию о спектре в консоль
    
    Args:
        x_values (list): Значения X (длины волн)
        y_values (list): Значения Y (интенсивность)
        num_points (int): Количество точек для вывода
    """
    print("\n=== Информация о спектре ===")
    
    # Вывод первых и последних точек данных
    if len(x_values) > 0 and len(y_values) > 0:
        half_points = num_points // 2
        
        print(f"\nПервые {half_points} точек данных:")
        for i in range(min(half_points, len(x_values))):
            print(f"  X[{i}] = {x_values[i]:.6f}, Y[{i}] = {y_values[i]:.6f}")
        
        print(f"\n...")
        
        print(f"\nПоследние {half_points} точек данных:")
        for i in range(max(0, len(x_values) - half_points), len(x_values)):
            print(f"  X[{i}] = {x_values[i]:.6f}, Y[{i}] = {y_values[i]:.6f}")
        
        # Вывод статистики
        print("\nСтатистика данных:")
        print(f"  Минимальное значение Y: {min(y_values):.6f}")
        print(f"  Максимальное значение Y: {max(y_values):.6f}")
        print(f"  Среднее значение Y: {sum(y_values) / len(y_values):.6f}")

def main():
    """
    Основная функция программы
    """
    file_path = "Spectra/26_10_38_24137269_1.spc"
    
    # Чтение файла спектра
    x_values, y_values = read_spc_file(file_path)
    
    if x_values is not None and y_values is not None:
        # Вывод информации о спектре
        display_spectrum_data(x_values, y_values)
        
        # Сохранение данных в текстовый файл
        output_file = "Spectra/26_10_38_24137269_1_converted.txt"
        with open(output_file, 'w') as f:
            f.write("X\tY\n")
            for i in range(len(x_values)):
                f.write(f"{x_values[i]:.6f}\t{y_values[i]:.6f}\n")
        
        print(f"\nДанные сохранены в файл: {output_file}")
    else:
        print("Не удалось прочитать данные из файла.")

if __name__ == "__main__":
    main() 