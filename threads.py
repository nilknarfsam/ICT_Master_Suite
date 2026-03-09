import os
import shutil
import time
import uuid
from datetime import datetime
from PyQt5.QtCore import QThread, pyqtSignal

# Funções migradas para o banco de dados SQLite
from models import (
    detectar_tipo_log,
    parse_metadata_inteligente,
    obter_estatisticas_ict,
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
    """Thread para buscar arquivos otimizada para rede (scandir)."""
    lista_arquivos = pyqtSignal(list)
    status_msg = pyqtSignal(str)

    def __init__(self, termo, diretorios):
        super().__init__()
        self.termo = termo.lower()
        self.diretorios = diretorios
        self.rodando = True

    def _scandir_recursivo(self, caminho):
        """Percorre todas as subpastas dinamicamente, sem depender de nomes específicos, usando scandir para performance máxima."""
        if not self.rodando: return []
        resultados = []
        
        try:
            # scandir iterador para baixo consumo de memória
            with os.scandir(caminho) as it:
                for entry in it:
                    if not self.rodando: break
                    
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            # Recursão para TODAS as subpastas agnosticamente
                            resultados.extend(self._scandir_recursivo(entry.path))
                        
                        elif entry.is_file(follow_symlinks=False):
                            nome_lower = entry.name.lower()
                            
                            # Filtro inicial: contém o Serial buscado e é um log válido?
                            if self.termo in nome_lower and nome_lower.endswith((".csv", ".dcl", ".txt", ".log")):
                                
                                # Filtro de Rejeição Rápida (PASS ou Aprovado)
                                if "pass" in nome_lower or nome_lower.startswith("p_"):
                                    continue
                                
                                # Aprovação Universal (FAIL): Se chegou aqui, é candidato de falha
                                ts = entry.stat().st_mtime
                                resultados.append((ts, entry.name, entry.path))
                                
                    except (PermissionError, OSError):
                        continue # Pula arquivos ou pastas sem acesso
        except (PermissionError, OSError):
            pass # Pula o diretório pai atual caso não possua acesso
            
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
            # Ordena por data (mais recente primeiro)
            encontrados.sort(key=lambda x: x[0], reverse=True)
            # Retorna lista de tuplas (nome, caminho) para a UI
            self.lista_arquivos.emit([(x[1], x[2]) for x in encontrados])

    def parar(self):
        self.rodando = False


class FileLoaderThread(QThread):
    """Thread para carregar o conteúdo de um arquivo sem travar a UI."""
    file_loaded = pyqtSignal(dict, str)
    file_load_error = pyqtSignal(str)

    def __init__(self, caminho, nome, backup_dir, parent=None):
        super().__init__(parent)
        self.caminho = caminho
        self.nome = nome
        self.backup_dir = backup_dir

    def run(self):
        try:
            self._backup_opened_file()
            # Blindagem de encodings e permissões: utf-8 com perdas controladas (ignore)
            with open(self.caminho, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            meta = parse_metadata_inteligente(self.caminho, self.nome, content)
            self.file_loaded.emit(meta, content)
        except PermissionError:
            self.file_load_error.emit("Acesso negado: O arquivo está sendo gravado pelo verificador (Agilent/TRI) ou bloqueado pelo Windows.")
        except Exception as e:
            self.file_load_error.emit(f"Erro ao carregar o arquivo: {str(e)}")

    def _backup_opened_file(self):
        if not self.caminho or not os.path.exists(self.caminho): return
        
        dt = datetime.now()
        nome_arquivo = os.path.basename(self.caminho)
        dst_dir = os.path.join(self.backup_dir, "abertos", dt.strftime("%Y-%m-%d"))
        dst = os.path.join(dst_dir, nome_arquivo)
        
        if os.path.exists(dst) and os.path.getsize(dst) == os.path.getsize(self.caminho): return
        
        if not _wait_file_stable(self.caminho): return
        
        _safe_copy(self.caminho, dst)

class DashboardThread(QThread):
    """Thread para buscar as estatísticas do dashboard sem travar a UI."""
    stats_updated = pyqtSignal(dict)

    def run(self):
        stats = obter_estatisticas_ict()
        self.stats_updated.emit(stats)