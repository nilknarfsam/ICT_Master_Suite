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

if __name__ == "__main__":
    unittest.main()
