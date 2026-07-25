import os
import sys
import shutil
import subprocess
from models import APP_VERSION

print("=========================================================")
print(f"Compilando ICT Master Suite v{APP_VERSION} (OneFile - Sem Console)...")
print("=========================================================")

# 1. Garantir fechamento de processos anteriores do EXE
try:
    subprocess.run(["taskkill", "/F", "/IM", "ICT_Master_Suite.exe"], capture_output=True)
except Exception:
    pass

# 2. Limpar pasta de build temporária
for folder in ['build', 'dist']:
    if os.path.exists(folder):
        try:
            shutil.rmtree(folder, ignore_errors=True)
        except Exception:
            pass

# 3. Executar PyInstaller via python
pyinstaller_cmd = [
    sys.executable, "-m", "PyInstaller",
    "--clean", "--onefile", "--noconsole",
    "--icon=icon.ico",
    "--add-data", "icon.ico;.",
    "--add-data", "style.qss;.",
    "-n", "ICT_Master_Suite",
    "ui_main.py"
]

result = subprocess.run(pyinstaller_cmd)

if result.returncode == 0:
    dist_exe = os.path.join("dist", "ICT_Master_Suite.exe")
    if os.path.exists(dist_exe):
        # 4. Criar diretório releases/ se não existir
        releases_dir = "releases"
        os.makedirs(releases_dir, exist_ok=True)
        
        # 5. Copiar executável renomeado com a versão para releases/
        version_exe_name = f"ICT_Master_Suite_v{APP_VERSION}.exe"
        release_target_path = os.path.join(releases_dir, version_exe_name)
        shutil.copy2(dist_exe, release_target_path)
        print(f"[SUCCESS] RELEASE GERADA EM: {release_target_path}")
        
        # 6. Atualizar a pasta dist/ com a versão e a raiz do projeto
        shutil.copy2(dist_exe, os.path.join("dist", version_exe_name))
        shutil.copy2(dist_exe, "ICT_Master_Suite.exe")
        print(f"[SUCCESS] COPIA PRINCIPAL ATUALIZADA EM: ICT_Master_Suite.exe")
        print("=========================================================")
        print(f"COMPILACAO v{APP_VERSION} CONCLUIDA COM EXITO!")
        print("=========================================================")
    else:
        print("[ERRO] O executavel compilado nao foi encontrado na pasta 'dist/'.")
else:
    print(f"[ERRO] A compilacao via PyInstaller falhou com codigo {result.returncode}.")
