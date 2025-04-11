import json

# чтение конфиг файла GAS.ini
with open(r'./GAS.ini', 'r') as f:
    data = f.read()
    cuv_length = float(data[data.find("Cuvette length=") + 15:data.find("Scans")].strip())
    scans = int(data[data.find("Scans=") + 6:data.find("Resolution")].strip())
    res = float(data[data.find("Resolution=") + 11:data.find("Spectra days")].strip())
