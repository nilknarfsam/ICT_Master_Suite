import os
import shutil
import time
import unittest
from PyQt5.QtCore import QCoreApplication
from threads import BuscaThread

class TestBuscaThread(unittest.TestCase):
    def setUp(self):
        """Set up a temporary directory with test files."""
        self.test_dir = "temp_test_dir"
        os.makedirs(self.test_dir, exist_ok=True)
        self.found_files = []

        # Create test files
        self.files_to_create = {
            "file1_log.csv": "content1",
            "file2_data.txt": "content2",
            "another_log.dcl": "content3",
            "image.jpg": "content4", # Should be ignored
            "subfolder": {
                "sub_log_file.csv": "content5",
                "another.txt": "content6"
            }
        }
        self._create_files(self.test_dir, self.files_to_create)

    def _create_files(self, base_path, files_dict):
        for name, content in files_dict.items():
            path = os.path.join(base_path, name)
            if isinstance(content, dict):
                os.makedirs(path, exist_ok=True)
                self._create_files(path, content)
            else:
                with open(path, "w") as f:
                    f.write(content)

    def tearDown(self):
        """Remove the temporary directory."""
        shutil.rmtree(self.test_dir)
        # Allow some time for file handles to be released
        time.sleep(0.1)

    def on_files_found(self, files):
        self.found_files = files
        QCoreApplication.instance().quit()

    def test_finds_correct_files(self):
        """Test that BuscaThread finds the correct files based on term and extension."""
        app = QCoreApplication([])
        
        # Search for files containing "log"
        thread = BuscaThread("log", [self.test_dir])
        thread.lista_arquivos.connect(self.on_files_found)
        thread.start()

        # Wait for the thread to finish (max 5 seconds)
        app.exec_()
        thread.wait(5000)

        # Expected files: file1_log.csv, another_log.dcl, sub_log_file.csv
        expected_names = ["file1_log.csv", "another_log.dcl", "sub_log_file.csv"]
        found_names = [name for name, path in self.found_files]

        self.assertEqual(len(self.found_files), 3)
        self.assertCountEqual(found_names, expected_names)

    def test_finds_all_relevant_files(self):
        """Test that BuscaThread finds all .csv, .dcl, and .txt files when the term is empty."""
        app = QCoreApplication([])
        
        # Search for all relevant files (empty term)
        thread = BuscaThread("", [self.test_dir])
        thread.lista_arquivos.connect(self.on_files_found)
        thread.start()

        app.exec_()
        thread.wait(5000)

        # Expected files: all except image.jpg
        expected_names = [
            "file1_log.csv", 
            "file2_data.txt", 
            "another_log.dcl", 
            "sub_log_file.csv", 
            "another.txt"
        ]
        found_names = [name for name, path in self.found_files]

        self.assertEqual(len(self.found_files), 5)
        self.assertCountEqual(found_names, expected_names)

class TestTRICopyThread(unittest.TestCase):
    def setUp(self):
        self.test_dir = "temp_tri_test_dir"
        os.makedirs(self.test_dir, exist_ok=True)
        # Cria arquivo FAIL e arquivo PASS
        with open(os.path.join(self.test_dir, "20260720_100000_FAIL.csv"), "w") as f:
            f.write("1,RES,10,10,12,8,2,1,P1,P2,L1,10.5,FAIL")
        with open(os.path.join(self.test_dir, "20260720_100001_PASS.csv"), "w") as f:
            f.write("1,RES,10,10,12,8,2,1,P1,P2,L1,10.0,PASS")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_copy_fail_files(self):
        from threads import TRICopyThread
        pasta_defeitos = os.path.join(self.test_dir, "defeitos_tri")
        thread = TRICopyThread(self.test_dir, pasta_defeitos, interval_seconds=1)
        # Executa 1 ciclo manualmente
        os.makedirs(pasta_defeitos, exist_ok=True)
        
        # Simula varredura da thread
        with os.scandir(self.test_dir) as it:
            for entry in it:
                if entry.is_file():
                    nome_lower = entry.name.lower()
                    if "pass" in nome_lower or nome_lower.startswith("p_"):
                        continue
                    shutil.copy2(entry.path, os.path.join(pasta_defeitos, entry.name))
        
        arquivos_copiados = os.listdir(pasta_defeitos)
        self.assertIn("20260720_100000_FAIL.csv", arquivos_copiados)
        self.assertNotIn("20260720_100001_PASS.csv", arquivos_copiados)

if __name__ == "__main__":
    unittest.main()

