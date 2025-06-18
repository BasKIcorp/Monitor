import unittest
import subprocess
import json


class TestExequant(unittest.TestCase):
    def test_exe(self):
        """
        exequant.exe --spectrum "11500,0.096772835;8408.412212,0.09712559;8407.412345,0.097467206;8406.412478,0.097798094;8405.412612,0.098119266;8404.412745,0.098430946;8403.412878,0.098732442;8402.413012,0.099023454;8401.413145,0.099304482;4001,0.099576272" --model 1.mmq --only_print
        """
        name_exe = 'exequant.exe'
        spectrum = '11500,0.096772835;8408.412212,0.09712559;8407.412345,0.097467206;8406.412478,0.097798094;8405.412612,0.098119266;8404.412745,0.098430946;8403.412878,0.098732442;8402.413012,0.099023454;8401.413145,0.099304482;4001,0.099576272'
        model = '1.mmq'
        conf_str = f"""{name_exe} --model {model} --only_print --spectrum "{spectrum}" """

        result = subprocess.run(conf_str, shell=True, capture_output=True, text=True)
        result_json = json.loads(result.stdout)
        check_json = json.loads('{"spectrum": {"Т": {"value": 2412.8439268433526, "unit": "1"}}}')


if __name__ == "__main__":
    unittest.main()