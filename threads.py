import os
import shutil
import time
import socket
from datetime import datetime
from PyQt5.QtCore import QThread, pyqtSignal

from models import (
    detectar_tipo_log,
    parse_metadata_inteligente,
    salvar_falha_db,
    init_db
)

def _wait_file_stable(path, retries=6, delay=0.35):
    """Aguarda o tamanho de um arquivo se estabilizar."""
    for _ in range(retries):
        try:
            size1 = os.path.getsize(path)
            time.sleep(delay)
            size2 = os.path.getsize(path)
            if size1 == size2:
                return True
        except OSError:
            time.sleep(delay)
    return False

def _safe_copy(src, dst):
    """Copia um arquivo de forma segura, criando o diretório de destino se necessário."""
    try:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        return True
    except (IOError, OSError):
        return False

class BuscaThread(QThread):
    """Thread para buscar arquivos otimizada para rede (scandir) com controle de profundidade."""
    lista_arquivos = pyqtSignal(list)
    status_msg = pyqtSignal(str)

    def __init__(self, termo, diretorios):
        super().__init__()
        self.termo = termo.lower()
        self.diretorios = diretorios
        self.rodando = True

    def _scandir_recursivo(self, caminho, depth=0):
        # Otimização de Performance: Limite de profundidade para evitar recursão infinita na rede
        if not self.rodando or depth > 2: 
            return []
        resultados = []
        
        try:
            with os.scandir(caminho) as it:
                for entry in it:
                    if not self.rodando: break
                    
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            # Otimização: Pula a pasta de defeitos TRI para evitar duplicidade de resultados
                            if "defeitos_tri" in entry.name.lower():
                                continue
                            resultados.extend(self._scandir_recursivo(entry.path, depth + 1))
                        
                        elif entry.is_file(follow_symlinks=False):
                            nome_lower = entry.name.lower()
                            
                            if self.termo in nome_lower and nome_lower.endswith((".csv", ".dcl", ".txt", ".log")):
                                if "pass" in nome_lower or nome_lower.startswith("p_"):
                                    continue
                                
                                ts = entry.stat().st_mtime
                                resultados.append((ts, entry.name, entry.path))
                                
                    except (PermissionError, OSError):
                        continue
        except (PermissionError, OSError):
            pass
            
        return resultados

    def run(self):
        self.status_msg.emit("Iniciando varredura (Filtro: Apenas Falhas)...")
        encontrados = []
        
        for diretorio in self.diretorios:
            if not self.rodando: break
            if os.path.exists(diretorio):
                self.status_msg.emit(f"Varrendo: {diretorio}")
                encontrados.extend(self._scandir_recursivo(diretorio))
        
        if self.rodando:
            encontrados.sort(key=lambda x: x[0], reverse=True)
            self.lista_arquivos.emit([(x[1], x[2]) for x in encontrados])

    def parar(self):
        self.rodando = False


class FileLoaderThread(QThread):
    """Thread para carregar o conteúdo de um arquivo diretamente no caminho original sem travar a UI."""
    file_loaded = pyqtSignal(dict, str)
    file_load_error = pyqtSignal(str)

    def __init__(self, caminho, nome, parent=None):
        super().__init__(parent)
        self.caminho = caminho
        self.nome = nome

    def run(self):
        try:
            with open(self.caminho, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            meta = parse_metadata_inteligente(self.caminho, self.nome, content)
            self.file_loaded.emit(meta, content)
        except PermissionError:
            self.file_load_error.emit("Acesso negado: O arquivo está sendo gravado pelo verificador (Agilent/TRI) ou bloqueado pelo Windows.")
        except Exception as e:
            self.file_load_error.emit(f"Erro ao carregar o arquivo: {str(e)}")


class TRICopyThread(QThread):
    """Thread em segundo plano que varre a pasta de origem e copia falhas para a pasta de destino."""
    log_msg = pyqtSignal(str)
    status_changed = pyqtSignal(str) # "EXECUTANDO", "PAUSADO", "PARADO"

    def __init__(self, caminho_origem, caminho_destino, interval_seconds=30, parent=None):
        super().__init__(parent)
        self.caminho_origem = caminho_origem.replace('\\', '/') if caminho_origem else ""
        self.caminho_destino = caminho_destino.replace('\\', '/') if caminho_destino else ""
        self.interval_seconds = interval_seconds
        self.rodando = True
        self.pausado = False

    def pausar(self):
        self.pausado = True
        self.status_changed.emit("PAUSADO")

    def retomar(self):
        self.pausado = False
        self.status_changed.emit("EXECUTANDO")

    def is_pausado(self):
        return self.pausado

    def run(self):
        self.status_changed.emit("EXECUTANDO")
        while self.rodando:
            if not self.pausado:
                try:
                    if self.caminho_origem and os.path.exists(self.caminho_origem):
                        os.makedirs(self.caminho_destino, exist_ok=True)
                        
                        with os.scandir(self.caminho_origem) as it:
                            for entry in it:
                                if not self.rodando or self.pausado:
                                    break
                                if entry.is_file(follow_symlinks=False):
                                    # Pula arquivos se já estiverem dentro da pasta de destino para evitar loops
                                    if self.caminho_destino in entry.path.replace('\\', '/'):
                                        continue
                                        
                                    nome_lower = entry.name.lower()
                                    if nome_lower.endswith((".csv", ".dcl", ".txt", ".log")):
                                        if "pass" in nome_lower or nome_lower.startswith("p_"):
                                            continue
                                        
                                        dst_file = os.path.join(self.caminho_destino, entry.name).replace('\\', '/')
                                        
                                        if os.path.exists(dst_file):
                                            try:
                                                if os.path.getsize(dst_file) == entry.stat().st_size:
                                                    continue
                                            except OSError:
                                                pass
                                                
                                        if _wait_file_stable(entry.path):
                                            if _safe_copy(entry.path, dst_file):
                                                self.log_msg.emit(f"Copiado para defeitos_tri: {entry.name}")
                                            else:
                                                self.log_msg.emit(f"Falha de permissão ao copiar {entry.name} para defeitos_tri.")
                    elif self.caminho_origem and not os.path.exists(self.caminho_origem):
                        self.log_msg.emit(f"Diretório de origem TRI inacessível: {self.caminho_origem}")
                except Exception as e:
                    self.log_msg.emit(f"Erro na cópia automática de falhas TRI: {e}")
                
            for _ in range(self.interval_seconds):
                if not self.rodando:
                    break
                time.sleep(1)

    def parar(self):
        self.rodando = False
        self.status_changed.emit("PARADO")


class NetworkMonitorThread(QThread):
    """Thread para monitorar periodicamente o status da conexão de rede com o servidor principal."""
    network_status = pyqtSignal(bool, str)

    def __init__(self, target_host="147.1.0.95", interval_seconds=15, parent=None):
        super().__init__(parent)
        self.target_host = target_host
        self.interval_seconds = interval_seconds
        self.rodando = True
        self.last_status = None

    def check_connection(self):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1.5) # Otimização: Timeout agressivo de 1.5s
            res = sock.connect_ex((self.target_host, 445))
            sock.close()
            return res == 0
        except Exception:
            return False

    def run(self):
        while self.rodando:
            online = self.check_connection()
            if self.last_status is None or online != self.last_status:
                self.last_status = online
                if online:
                    self.network_status.emit(True, f"Conexão restabelecida com o servidor ({self.target_host}).")
                else:
                    self.network_status.emit(False, f"Queda de conexão detectada com o servidor ({self.target_host}).")
            
            for _ in range(self.interval_seconds):
                if not self.rodando:
                    break
                time.sleep(1)

    def parar(self):
        self.rodando = False