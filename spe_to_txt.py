import struct
import numpy as np
import os
import re

def read_spe_file(file_path):
    """
    Читает файл .spe и преобразует бинарные данные в читаемый вид
    
    Args:
        file_path (str): Путь к файлу .spe
        
    Returns:
        tuple: (header_info, x_values, y_values) - информация из заголовка и данные спектра
    """
    print(f"Чтение файла: {file_path}")
    
    # Проверка существования файла
    if not os.path.exists(file_path):
        print(f"Ошибка: Файл {file_path} не найден")
        return None, None, None
    
    header_info = {}
    x_values = []
    y_values = []
    
    try:
        with open(file_path, 'rb') as file:
            # Сначала читаем файл как текст для извлечения заголовка
            file.seek(0)
            text_content = file.read().decode('cp1251', errors='replace')
            
            # Извлекаем информацию из заголовка
            header_lines = text_content.split('##$YDATA=SINGLE(Y..Y)')[0].split('\n')
            
            for line in header_lines:
                if line.startswith('##'):
                    parts = line.split('=', 1)
                    if len(parts) == 2:
                        key = parts[0].strip('# ')
                        value = parts[1].strip()
                        header_info[key] = value
            
            # Получаем важные параметры из заголовка
            try:
                first_x = float(header_info.get('FIRSTX', 0))
                last_x = float(header_info.get('LASTX', 0))
                n_points = int(header_info.get('NPOINTS', 0))
                
                print(f"Параметры спектра:")
                print(f"  Начальная точка X: {first_x}")
                print(f"  Конечная точка X: {last_x}")
                print(f"  Количество точек: {n_points}")
                
                # Создаем массив значений X (длин волн)
                if n_points > 0:
                    x_values = np.linspace(first_x, last_x, n_points)
                
                # Находим позицию начала данных
                data_start = text_content.find('##$YDATA=SINGLE(Y..Y)') + len('##$YDATA=SINGLE(Y..Y)')
                
                # Преобразуем бинарные данные в числа с плавающей точкой
                file.seek(data_start)
                binary_data = file.read()
                
                # Определяем формат данных (4-байтовые числа с плавающей точкой)
                # Пропускаем символы новой строки после метки YDATA
                offset = 1  # Пропускаем символ новой строки
                
                # Читаем данные как 4-байтовые числа с плавающей точкой (IEEE 754)
                y_values = []
                for i in range(offset, len(binary_data), 4):
                    if i + 4 <= len(binary_data):
                        value = struct.unpack('f', binary_data[i:i+4])[0]
                        y_values.append(value)
                
                print(f"Прочитано {len(y_values)} значений Y")
                
                # Обрезаем массив Y до размера n_points, если необходимо
                if n_points > 0 and len(y_values) > n_points:
                    y_values = y_values[:n_points]
                
            except (ValueError, KeyError) as e:
                print(f"Ошибка при извлечении параметров: {e}")
        
        return header_info, x_values, y_values
    
    except Exception as e:
        print(f"Ошибка при чтении файла: {e}")
        return None, None, None

def display_spectrum_data(header_info, x_values, y_values, num_points=20):
    """
    Выводит информацию о спектре в консоль
    
    Args:
        header_info (dict): Информация из заголовка файла
        x_values (list): Значения X (длины волн)
        y_values (list): Значения Y (интенсивность)
        num_points (int): Количество точек для вывода
    """
    print("\n=== Информация о спектре ===")
    
    # Вывод основной информации из заголовка
    print("\nОсновные параметры:")
    important_keys = ['DATE', 'TIME', 'RESOLUTION', 'NSCANS', 'AMPLIFICATION']
    for key in important_keys:
        if key in header_info:
            print(f"  {key}: {header_info[key]}")
    
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
    file_path = "Spectra/fon.spe"
    
    # Чтение файла спектра
    header_info, x_values, y_values = read_spe_file(file_path)
    
    if header_info is not None and x_values is not None and y_values is not None:
        # Вывод информации о спектре
        display_spectrum_data(header_info, x_values, y_values)
        
        # Построение графика (раскомментируйте, если нужно)
        # plot_spectrum(x_values, y_values, f"Спектр из файла {file_path}")
        
        # Сохранение данных в текстовый файл
        output_file = "Spectra/fon_converted.txt"
        with open(output_file, 'w') as f:
            f.write("X\tY\n")
            for i in range(len(x_values)):
                f.write(f"{x_values[i]:.6f}\t{y_values[i]:.6f}\n")
        
        print(f"\nДанные сохранены в файл: {output_file}")

if __name__ == "__main__":
    main() 