@echo off
:: Ajusta os caracteres para aceitar acentos
chcp 65001 >nul
echo =========================================================
echo         Sincronizando projeto com o GitHub
echo =========================================================
echo.

:: Pede para o usuario digitar o que ele alterou
set /p mensagem="Digite o que voce alterou (ex: 'criado botao de excel'): "

:: Se o usuario der enter sem digitar nada, usa uma mensagem padrao
if "%mensagem%"=="" set mensagem="Atualizacao rapida do sistema"

echo.
echo [1/3] Preparando arquivos...
git add .

echo [2/3] Criando o pacote de atualizacao (Commit)...
git commit -m "%mensagem%"

echo [3/3] Enviando para a nuvem (Push)...
git push

echo.
echo =========================================================
echo           Upload concluido com sucesso!
echo =========================================================
pause
