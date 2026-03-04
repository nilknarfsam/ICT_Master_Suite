@echo off
:: Ajusta os caracteres especiais (acentos) no terminal
chcp 65001 >nul

echo =========================================================
echo Iniciando a compilação do ICT Master Suite...
echo =========================================================

:: 1. Ativa o ambiente virtual (Se a sua pasta se chamar algo diferente de .venv, mude aqui)
echo Ativando ambiente virtual...
call .venv\Scripts\activate

:: 2. Garante que o pyinstaller está instalado neste ambiente
echo Verificando instalação do PyInstaller...
pip install pyinstaller

:: 3. Executa a compilação
echo Compilando o executável...
pyinstaller --onedir --noconsole --add-data "version.json;." ui_main.py

echo =========================================================
echo Compilação concluída!
echo Verifique se houve algum erro de compilação acima.
echo O executável gerado estará na pasta "dist\ui_main".
echo =========================================================
pause