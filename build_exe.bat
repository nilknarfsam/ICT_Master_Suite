@echo off
chcp 65001 >nul

echo =========================================================
echo Iniciando a compilação do ICT Master Suite (OneDir)...
echo =========================================================

call .venv\Scripts\activate

echo Limpando builds antigos e compilando...
pyinstaller --clean --onedir --noconsole -n "ICT_Master_Suite" ui_main.py

echo =========================================================
echo Compilação concluída!
echo A pasta do sistema estará dentro de "dist".
echo =========================================================
pause