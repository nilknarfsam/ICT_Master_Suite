@echo off
chcp 65001 >nul

echo =========================================================
echo Iniciando a compilação do ICT Master Suite (OneFile)...
echo =========================================================

call .venv\Scripts\activate
pip install pyinstaller

echo Limpando builds antigos e compilando...
pyinstaller --clean --onefile --noconsole --add-data "style.qss;." --add-data "icon.ico;." -n "ICT_Master_Suite" ui_main.py

echo =========================================================
echo Compilação concluída!
echo O executável único estará na pasta "dist".
echo =========================================================
pause