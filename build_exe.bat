@echo off
echo =========================================================
echo Compilando ICT Master Suite (OneFile - Sem Console)...
echo =========================================================

call .venv\Scripts\activate

.venv\Scripts\pyinstaller.exe --clean --onefile --noconsole --icon=icon.ico --add-data "icon.ico;." --add-data "style.qss;." -n "ICT_Master_Suite" ui_main.py

if exist dist\ICT_Master_Suite.exe (
    copy /Y dist\ICT_Master_Suite.exe ICT_Master_Suite.exe
)

echo =========================================================
echo Compilacao concluida!
echo =========================================================