import os
import sys
import json
import subprocess

def get_current_version():
    try:
        if os.path.exists("version.json"):
            with open("version.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("versao", "1.0.0")
    except Exception:
        pass
    return "1.0.0"

def verificar_atualizacao(caminho_rede=None, versao_atual="1.0.0"):
    try:
        if not caminho_rede:
            try:
                from models import CONFIG_FILE
                if os.path.exists(CONFIG_FILE):
                    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        caminho_rede = data.get("caminho_update_rede", "")
            except ImportError:
                pass
                
        if not caminho_rede or not os.path.exists(caminho_rede):
            return False
            
        version_file = os.path.join(caminho_rede, "version.json")
        if not os.path.exists(version_file):
            return False
            
        with open(version_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            versao_rede = data.get("versao", "0.0.0")
            
        def parse_version(v):
            return tuple(map(int, v.split(".")))
            
        if parse_version(versao_rede) > parse_version(versao_atual):
            return True
    except Exception as e:
        print(f"Erro ao verificar atualização: {e}")
        
    return False

def aplicar_atualizacao(caminho_exe_rede):
    try:
        local_path = os.path.abspath(sys.argv[0])
        
        bat_content = f"""@echo off
timeout /t 3 /nobreak
copy /Y "{caminho_exe_rede}" "{local_path}"
start "" "ICT_Master_Suite.exe"
del "%~f0"
"""
        temp_dir = os.environ.get('TEMP', 'C:\\Windows\\Temp')
        bat_path = os.path.join(temp_dir, "update.bat")
        
        with open(bat_path, "w", encoding="utf-8") as f:
            f.write(bat_content)
            
        # Rodar o .bat de forma desanexada
        if sys.platform == "win32":
            subprocess.Popen([bat_path], creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:
            subprocess.Popen(["sh", bat_path])
            
        return True
    except Exception as e:
        print(f"Erro ao aplicar atualização: {e}")
        return False
