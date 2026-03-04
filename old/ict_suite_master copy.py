import sys
import os
import json
import shutil
import time
import winreg
import uuid
from datetime import datetime

# --- CAMINHO DO BANCO DE DADOS (REDE) ---
PASTA_REDE_DB = r"\\147.1.0.95\teste_ict\ict02\ict banco de dados"

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QListWidget, QTableWidget, QTableWidgetItem, QTextEdit, QFileDialog, QDialog, 
    QLabel, QHeaderView, QMessageBox, QFrame, QGroupBox, QStyle, QSystemTrayIcon,
    QMenu, QAction, QTabWidget, QSplitter, QSizePolicy
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QColor, QFont

# --- CONFIGURAÇÕES ---
CONFIG_FILE = "ict_config.json"
DEFAULT_CONFIG = {
    "finder_tri": r"\\147.1.0.95\teste_ict\ict02\defeitos_tri",
    "finder_agilent": r"\\147.1.0.95\teste_ict\ict01\defeitos",
    "monitor_source": r"\\147.1.0.95\teste_ict\ict02",
    "monitor_dest": r"\\147.1.0.95\teste_ict\ict02\defeitos_tri",
    "backup_local_dir": r"C:\app_chamados\backup_logs",
    "backup_mode": "on_open",
    "auto_start_windows": False,
    "monitor_active": False
}

def carregar_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                dados = json.load(f)
                for k, v in DEFAULT_CONFIG.items():
                    if k not in dados: dados[k] = v
                return dados
        except: return DEFAULT_CONFIG.copy()
    return DEFAULT_CONFIG.copy()

def salvar_config(dados):
    try:
        with open(CONFIG_FILE, 'w') as f: json.dump(dados, f, indent=4)
    except: pass

def detectar_tipo_log(nome_arquivo):
    """Define se é TRI ou AGILENT baseado na extensão e nome."""
    nome = nome_arquivo.lower()
    if nome.endswith(".csv") or nome.endswith(".dcl"):
        return "TRI"
    elif nome.endswith(".txt") and "report" in nome:
        return "AGILENT"
    # Fallback: se tiver CSV no nome ou extensão
    if ".csv" in nome: return "TRI"
    return "AGILENT" # Padrão para .txt

def parse_metadata_inteligente(caminho_completo, nome_arquivo, conteudo):
    """
    Extrai dados do cabeçalho de forma híbrida (TRI vs Agilent).
    """
    tipo = detectar_tipo_log(nome_arquivo)
    
    dados = {
        "tipo": tipo,
        "data": "Desconhecida",
        "serial": "Desconhecido",
        "modelo": "Desconhecido",
        "status": "N/A",
        "cor": "black"
    }

    try:
        if tipo == "TRI":
            # Lógica TRI (Nome do arquivo tem Data e Serial)
            # Ex: 202512180959065C83001UV9m70q_gen5_intelFAIL.csv
            nome_sem_ext = os.path.splitext(nome_arquivo)[0]
            
            # Data (14 primeiros chars)
            if nome_sem_ext[:14].isdigit():
                dt = datetime.strptime(nome_sem_ext[:14], "%Y%m%d%H%M%S")
                dados["data"] = dt.strftime("%d/%m/%Y %H:%M:%S")
                resto = nome_sem_ext[14:]
            else:
                resto = nome_sem_ext

            # Status
            if nome_sem_ext.upper().endswith("FAIL"):
                dados["status"] = "FAIL"
                dados["cor"] = "red"
                resto = resto[:-4]
            elif nome_sem_ext.upper().endswith("PASS"):
                dados["status"] = "PASS"
                dados["cor"] = "green"
                resto = resto[:-4]
            
            # Serial e Modelo (Tentativa de split)
            # Assume serial de 10 digitos
            if len(resto) >= 10:
                dados["serial"] = resto[:10]
                dados["modelo"] = resto[10:].strip("_")
            else:
                dados["serial"] = resto

        elif tipo == "AGILENT":
            # Lógica Agilent (Nome: 5C83001QBR_report_out_p3-twr2.txt)
            # Data: Pega do sistema de arquivos (OS) pois não está no nome
            ts_mod = os.path.getmtime(caminho_completo)
            dt = datetime.fromtimestamp(ts_mod)
            dados["data"] = dt.strftime("%d/%m/%Y %H:%M:%S")
            
            # Serial: Antes do primeiro underscore
            partes = nome_arquivo.split('_')
            if len(partes) > 0:
                dados["serial"] = partes[0]
            
            # Modelo/Estação: Tenta pegar do fim do nome
            if "report_out_" in nome_arquivo:
                 dados["modelo"] = nome_arquivo.split("report_out_")[-1].replace(".txt", "")
            
            # Status: Varre o CONTEÚDO do texto
            conteudo_upper = conteudo.upper()
            if "FAILED" in conteudo_upper or "FAILURE" in conteudo_upper:
                dados["status"] = "FAIL"
                dados["cor"] = "red"
            elif "PASSED" in conteudo_upper:
                dados["status"] = "PASS"
                dados["cor"] = "green"
            else:
                dados["status"] = "INFO/ABORT"
                dados["cor"] = "orange"

    except Exception as e:
        print(f"Erro parser: {e}")
    
    return dados

def set_windows_startup(enable):
    app_path = os.path.abspath(sys.argv[0])
    cmd = f'"{sys.executable.replace("python.exe", "pythonw.exe")}" "{app_path}" --minimized' if app_path.endswith('.py') else f'"{app_path}" --minimized'
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
        if enable: winreg.SetValueEx(key, "ICTSuiteMaster", 0, winreg.REG_SZ, cmd)
        else: 
            try: winreg.DeleteValue(key, "ICTSuiteMaster")
            except: pass
        winreg.CloseKey(key)
    except: pass

def _wait_file_stable(path, retries=6, delay=0.35):
    for _ in range(retries):
        try:
            size1 = os.path.getsize(path)
            time.sleep(delay)
            size2 = os.path.getsize(path)
            if size1 == size2:
                return True
        except:
            time.sleep(delay)
    return False

def _safe_copy(src, dst):
    try:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        return True
    except:
        return False

# --- THREAD DE BUSCA ---
class BuscaThread(QThread):
    lista_arquivos = pyqtSignal(list)
    status_msg = pyqtSignal(str)

    def __init__(self, termo, diretorios):
        super().__init__()
        self.termo = termo
        self.diretorios = diretorios
        self.rodando = True

    def run(self):
        encontrados = []
        self.status_msg.emit("Varrendo diretórios...")
        termo_lower = self.termo.lower()
        for diretorio in self.diretorios:
            if not os.path.exists(diretorio): continue
            for root, dirs, files in os.walk(diretorio):
                if not self.rodando: break
                for file in files:
                    if not self.rodando: break
                    time.sleep(0.01) # Otimização: dá fôlego à CPU/Rede em buscas longas
                    if (file.lower().endswith((".csv", ".dcl", ".txt"))) and termo_lower in file.lower():
                        caminho = os.path.join(root, file)
                        # Tupla: (Timestamp para ordenar, Nome, Caminho)
                        try:
                            ts = os.path.getmtime(caminho)
                        except:
                            ts = 0
                        encontrados.append((ts, file, caminho))
        
        # Ordena pelo timestamp (mais novo primeiro)
        encontrados.sort(key=lambda x: x[0], reverse=True)
        
        # Retorna só (Nome, Caminho)
        resultado_limpo = [(x[1], x[2]) for x in encontrados]
        self.lista_arquivos.emit(resultado_limpo)

    def parar(self):
        self.rodando = False

# --- THREAD DE CARREGAMENTO DE ARQUIVO ---
class FileLoaderThread(QThread):
    file_loaded = pyqtSignal(dict, str)
    file_load_error = pyqtSignal(str)

    def __init__(self, caminho, nome, backup_dir, parent=None):
        super().__init__(parent)
        self.caminho = caminho
        self.nome = nome
        self.backup_dir = backup_dir

    def run(self):
        try:
            # 1. Backup do arquivo aberto
            self._backup_opened_file()
            
            # 2. Leitura do arquivo (operação de I/O de rede)
            with open(self.caminho, 'r', encoding='latin1') as f:
                content = f.read()

            # 3. Parse dos metadados
            meta = parse_metadata_inteligente(self.caminho, self.nome, content)

            # 4. Emite o sinal com os dados prontos
            self.file_loaded.emit(meta, content)
        except Exception as e:
            self.file_load_error.emit(f"Erro ao carregar o arquivo: {str(e)}")

    def _backup_opened_file(self):
        if not self.caminho or not os.path.exists(self.caminho):
            return
        try:
            dt = datetime.now()
            nome_arquivo = os.path.basename(self.caminho)
            dst_dir = os.path.join(self.backup_dir, "abertos", dt.strftime("%Y-%m-%d"))
            dst = os.path.join(dst_dir, nome_arquivo)
            
            if os.path.exists(dst) and os.path.getsize(dst) == os.path.getsize(self.caminho):
                return
            
            if not _wait_file_stable(self.caminho):
                # Não emitimos sinal aqui para não poluir a UI, é um best-effort
                print(f"Arquivo instável durante backup: {nome_arquivo}")
                return
            
            _safe_copy(self.caminho, dst)
        except Exception as e:
            print(f"Falha no backup em thread: {e}")


# --- THREAD MONITOR ---
class MonitorThread(QThread):
    log_msg = pyqtSignal(str)
    
    def __init__(self, source, dest, backup_local_dir, backup_mode="on_open"):
        super().__init__()
        self.source = source
        self.dest = dest
        self.backup_local_dir = backup_local_dir
        self.backup_mode = backup_mode
        self.running = True
        self.dest_available = True
        self.reconcile_interval_sec = 180
        self.last_reconcile_ts = 0
        self.last_scan_ts = 0
        self._last_organize_date = None
        # Buffer para evitar "Signal Flooding"
        self.log_buffer = []
        self.last_log_emit_ts = time.time()

    def _emit_log_buffer(self, force=False):
        """Emite o log em massa para não sobrecarregar a UI."""
        if not self.log_buffer: return
        
        time_since_last_emit = time.time() - self.last_log_emit_ts
        if force or len(self.log_buffer) >= 10 or time_since_last_emit > 2:
            try:
                # Junta as mensagens e emite um único sinal
                log_completo = "\n".join(self.log_buffer)
                if log_completo:
                    self.log_msg.emit(log_completo)
                self.log_buffer.clear()
                self.last_log_emit_ts = time.time()
            except: pass # Evita crash se a UI já foi fechada

    def wait_file_stable(self, path, retries=6, delay=0.35):
        return _wait_file_stable(path, retries=retries, delay=delay)

    def safe_copy(self, src, dst):
        ok = _safe_copy(src, dst)
        if not ok:
            self.log_buffer.append(f"Erro ao copiar: {os.path.basename(src)}")
        return ok

    def _is_relevant_file(self, file):
        file_upper = file.upper()
        is_fail = file_upper.endswith("FAIL.CSV")
        is_report = file_upper.endswith(".TXT") and "REPORT" in file_upper
        return is_fail or is_report

    def _get_backup_mirror_path(self, src):
        nome = os.path.basename(src)
        tipo = detectar_tipo_log(nome)
        try:
            ts = os.path.getmtime(src)
            dt = datetime.fromtimestamp(ts)
        except:
            dt = datetime.now()
        subdir = os.path.join(tipo, dt.strftime("%Y-%m"))
        return os.path.join(self.backup_local_dir, subdir, nome)

    def _copy_to_backup(self, src):
        dst = self._get_backup_mirror_path(src)
        try:
            if os.path.exists(dst) and os.path.getsize(dst) == os.path.getsize(src):
                return True
        except:
            pass
        if not self.wait_file_stable(src):
            self.log_buffer.append(f"Arquivo instavel (backup): {os.path.basename(src)}")
            return False
        return self.safe_copy(src, dst)

    def _should_backup_local(self):
        return self.backup_mode == "mirror"

    def _filter_walk_dirs(self, root, dirs):
        dest_norm = os.path.normcase(os.path.normpath(self.dest))
        db_norm = os.path.normcase(os.path.normpath(PASTA_REDE_DB))
        dirs[:] = [
            d for d in dirs
            if os.path.normcase(os.path.normpath(os.path.join(root, d))) not in (dest_norm, db_norm)
        ]

    def organize_mirror_by_day(self, dest_root):
        if not dest_root or not os.path.exists(dest_root):
            return
        for root, dirs, files in os.walk(dest_root):
            rel = os.path.relpath(root, dest_root)
            if rel != ".":
                first = rel.split(os.sep, 1)[0]
                if len(first) == 10 and first[4] == "-" and first[7] == "-":
                    continue
            for file in files:
                if not self._is_relevant_file(file):
                    continue
                src = os.path.join(root, file)
                try:
                    ts = os.path.getmtime(src)
                except:
                    continue
                day_dir = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
                dst_dir = os.path.join(dest_root, day_dir)
                dst = os.path.join(dst_dir, file)
                try:
                    if os.path.normcase(os.path.normpath(src)) == os.path.normcase(os.path.normpath(dst)):
                        continue
                    os.makedirs(dst_dir, exist_ok=True)
                    if os.path.exists(dst):
                        if os.path.getsize(dst) == os.path.getsize(src):
                            os.remove(src)
                            continue
                        base, ext = os.path.splitext(file)
                        n = 1
                        while True:
                            cand = os.path.join(dst_dir, f"{base}_{n}{ext}")
                            if not os.path.exists(cand):
                                dst = cand
                                break
                            n += 1
                    os.replace(src, dst)
                except:
                    continue
                time.sleep(0.01)
            self._emit_log_buffer()

    def _maybe_organize_mirror_by_day(self):
        today = datetime.now().strftime("%Y-%m-%d")
        if self._last_organize_date == today:
            return
        self._last_organize_date = today
        self.organize_mirror_by_day(self.dest)

    def reconcile_source_to_dest(self):
        if not os.path.exists(self.source):
            return
        self.log_buffer.append("Iniciando reconciliação de arquivos...")
        self._emit_log_buffer(force=True)
        
        for root, dirs, files in os.walk(self.source):
            self._filter_walk_dirs(root, dirs)
            for file in files:
                if not self.running: return
                
                if not self._is_relevant_file(file): continue
                
                src = os.path.join(root, file)
                if not self.dest_available:
                    if self._should_backup_local(): self._copy_to_backup(src)
                    continue
                    
                rel = os.path.relpath(src, self.source)
                dst = os.path.join(self.dest, rel)
                
                try:
                    dst_exists = os.path.exists(dst)
                    dst_size = os.path.getsize(dst) if dst_exists else -1
                    src_size = os.path.getsize(src)
                except: continue

                needs_copy = (not dst_exists) or (dst_size != src_size)
                if needs_copy:
                    if not self.wait_file_stable(src):
                        self.log_buffer.append(f"Arquivo instavel (espelho): {file}")
                        continue
                    if self.safe_copy(src, dst):
                        self.log_buffer.append(f"Reconciliado: {file}")
                        if not dst_exists:
                            self.registrar_falha_json(src)
                        if self._should_backup_local():
                            self._copy_to_backup(src)
                
                self._emit_log_buffer()
                time.sleep(0.05)

        self._maybe_organize_mirror_by_day()
        self.log_buffer.append("Reconciliação finalizada.")
        self._emit_log_buffer(force=True)

    def registrar_falha_json(self, caminho_arquivo):
        if not os.path.exists(PASTA_REDE_DB):
            try: os.makedirs(PASTA_REDE_DB)
            except: 
                self.log_buffer.append("ERRO: Pasta de rede do Banco de Dados inacessível!")
                return

        arquivo_db = os.path.join(PASTA_REDE_DB, "banco_dados_falhas.json")
        try:
            with open(caminho_arquivo, 'r', encoding='latin1') as f: content = f.read()
        except: return

        nome_arquivo = os.path.basename(caminho_arquivo)
        ts = os.path.getmtime(caminho_arquivo)
        data_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
        serial = nome_arquivo.split('_')[0] if '_' in nome_arquivo else nome_arquivo[:15]
        modelo = "GENERICO"
        novos_defeitos = []
        for linha in content.splitlines():
            if "FAIL" in linha.upper() or "HIGH" in linha.upper() or "LOW" in linha.upper():
                parts = linha.split(',')
                if len(parts) > 5 and len(parts[0]) < 10:
                    defeito = { "id": str(uuid.uuid4()), "data_registro": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "data_falha": data_str, "arquivo": nome_arquivo, "serial": serial, "modelo": modelo, "componente": parts[1] if len(parts) > 1 else "Unknown", "step": parts[0], "status_tratativa": "ABERTO", "tecnico_responsavel": "", "causa": "", "solucao": "" }
                    novos_defeitos.append(defeito)

        if not novos_defeitos: return
        
        try:
            lista_atual = []
            if os.path.exists(arquivo_db):
                try:
                    with open(arquivo_db, 'r') as f: lista_atual = json.load(f)
                except: pass
            
            lista_atual.extend(novos_defeitos)
            tmp_path = f"{arquivo_db}.tmp_{uuid.uuid4().hex}"
            with open(tmp_path, 'w') as f:
                json.dump(lista_atual, f, indent=4)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, arquivo_db)
            self.log_buffer.append(f"DB: +{len(novos_defeitos)} falhas salvas na rede.")
        except Exception as e:
            self.log_buffer.append(f"Erro ao salvar JSON: {e}")

    def run(self):
        self.log_buffer.append(f"Monitorando: {self.source}")
        if not os.path.exists(self.dest):
            self.dest_available = False
            self.log_buffer.append("Destino espelho indisponivel (UNC): sem acesso ou inexistente.")
        if not os.path.exists(self.backup_local_dir):
            try: os.makedirs(self.backup_local_dir)
            except: self.log_buffer.append("Erro ao criar backup local.")
        
        self._emit_log_buffer(force=True)

        while self.running:
            if time.time() - self.last_scan_ts > 30:
                try:
                    # Reconciliação periódica movida para dentro do timer
                    if time.time() - self.last_reconcile_ts >= self.reconcile_interval_sec:
                        self.reconcile_source_to_dest()
                        self.last_reconcile_ts = time.time()
                    
                    if os.path.exists(self.source):
                        for root, dirs, files in os.walk(self.source):
                            if not self.running: break
                            self._filter_walk_dirs(root, dirs)
                            for file in files:
                                if not self.running: break
                                if self._is_relevant_file(file):
                                    src = os.path.join(root, file)
                                    try:
                                        if not self.wait_file_stable(src):
                                            self.log_buffer.append(f"Arquivo instavel (novo): {file}")
                                            continue
                                        if self.dest_available:
                                            rel = os.path.relpath(src, self.source)
                                            dst = os.path.join(self.dest, rel)
                                            if not os.path.exists(dst):
                                                if self.safe_copy(src, dst):
                                                    self.log_buffer.append(f"Copiado: {rel}")
                                                    if self._should_backup_local(): self._copy_to_backup(src)
                                                    self.registrar_falha_json(src)
                                        elif self._should_backup_local():
                                            self._copy_to_backup(src)
                                    except Exception as e:
                                        self.log_buffer.append(f"Erro processamento {file}: {e}")
                                time.sleep(0.01)
                            self._emit_log_buffer()
                except Exception as e:
                    self.log_buffer.append(f"Erro fatal no loop de monitoramento: {e}")
                finally:
                    self.last_scan_ts = time.time()
                    self._emit_log_buffer(force=True)

            time.sleep(2)

    def stop(self):
        self.running = False
        self._emit_log_buffer(force=True)

# --- UI PRINCIPAL ---
class MainApp(QWidget):
    def __init__(self, start_minimized=False):
        super().__init__()
        self.setWindowTitle("ICT Master Suite - V4.2 (Optimized)")
        self.setGeometry(100, 100, 1280, 768)
        self.config = carregar_config()
        try:
            os.makedirs(self.config["backup_local_dir"], exist_ok=True)
        except:
            pass
        self.arquivos_mapa = {} 
        self.thread_loader = None
        self.current_file_name = None
        self._last_purge_date = None
        self.init_ui()
        self.init_tray()
        self._maybe_purge_backups()
        
        if self.config.get("monitor_active", False):
            self.toggle_monitor(force_start=True)
        if start_minimized:
            self.hide()
            self.tray_icon.showMessage("ICT Suite", "Rodando em background.", QSystemTrayIcon.Information, 2000)
        else: self.show()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        
        # Header
        h = QHBoxLayout()
        lbl_header = QLabel("ICT Technical Suite")
        lbl_header.setStyleSheet("font-size: 18px; font-weight: bold; color: #333;")
        h.addWidget(lbl_header)
        h.addStretch()
        
        btn_hide = QPushButton("📥 Minimizar para Bandeja")
        btn_hide.clicked.connect(self.hide)
        btn_hide.setStyleSheet("background-color: #e0e0e0;")
        h.addWidget(btn_hide)

        btn_cfg = QPushButton("⚙️ Config")
        btn_cfg.clicked.connect(self.abrir_config)
        h.addWidget(btn_cfg)
        main_layout.addLayout(h)

        self.tabs = QTabWidget()
        
        # ABA FINDER
        self.tab_finder = QWidget()
        self.setup_finder()
        self.tabs.addTab(self.tab_finder, "🔍 Finder Logs")
        
        # ABA MONITOR
        self.tab_monitor = QWidget()
        self.setup_monitor()
        self.tabs.addTab(self.tab_monitor, "🛡️ Monitor")
        
        main_layout.addWidget(self.tabs)
        self.status_bar = QLabel("Pronto.")
        footer = QHBoxLayout()
        footer.addWidget(self.status_bar)
        footer.addStretch()
        lbl_credito = QLabel("Desenvolvido por Franklin Carvalho")
        lbl_credito.setStyleSheet("color: #777; font-size: 11px;")
        footer.addWidget(lbl_credito)
        main_layout.addLayout(footer)

    def setup_finder(self):
        layout = QVBoxLayout(self.tab_finder)
        
        # Busca
        box_busca = QHBoxLayout()
        self.input_serial = QLineEdit()
        self.input_serial.setPlaceholderText("Serial da placa...")
        self.input_serial.setMinimumHeight(35)
        self.input_serial.setStyleSheet("font-size: 14px;")
        self.input_serial.returnPressed.connect(self.buscar)
        
        btn_go = QPushButton(" BUSCAR ")
        btn_go.setMinimumHeight(35)
        btn_go.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold;")
        btn_go.clicked.connect(self.buscar)
        
        box_busca.addWidget(self.input_serial)
        box_busca.addWidget(btn_go)
        layout.addLayout(box_busca)

        # Splitter Principal
        splitter = QSplitter(Qt.Horizontal)
        
        # ESQUERDA: Lista
        frame_left = QFrame()
        l_left = QVBoxLayout(frame_left)
        l_left.setContentsMargins(0,0,0,0)
        lbl_hist = QLabel("Histórico (Recentes):")
        lbl_hist.setStyleSheet("font-weight:bold")
        l_left.addWidget(lbl_hist)
        self.list_logs = QListWidget()
        self.list_logs.setStyleSheet("font-size: 12px;")
        self.list_logs.itemSelectionChanged.connect(self.carregar_arquivo)
        l_left.addWidget(self.list_logs)
        splitter.addWidget(frame_left)

        # DIREITA: Visualização
        frame_right = QFrame()
        self.l_right = QVBoxLayout(frame_right)
        self.l_right.setContentsMargins(0,0,0,0)
        
        # Cabeçalho Info
        self.lbl_info = QLabel("Selecione um arquivo.")
        self.lbl_info.setStyleSheet("background-color: #eceff1; padding: 10px; border-radius: 4px; border: 1px solid #cfd8dc;")
        self.lbl_info.setWordWrap(True)
        self.l_right.addWidget(self.lbl_info)

        # Conteúdo Texto (Log Bruto)
        lbl_log = QLabel("Log do Arquivo:")
        lbl_log.setStyleSheet("margin-top: 5px; font-weight:bold; color:#555;")
        self.l_right.addWidget(lbl_log)
        self.text_raw = QTextEdit()
        self.text_raw.setReadOnly(True)
        self.text_raw.setStyleSheet("font-family: Consolas, monospace; font-size: 12px;")
        self.l_right.addWidget(self.text_raw)

        # Tabela (Só aparece para TRI)
        self.lbl_table_title = QLabel("Detalhamento de Defeitos (TRI):")
        self.lbl_table_title.setStyleSheet("font-weight:bold; margin-top: 5px; color:#555;")
        self.l_right.addWidget(self.lbl_table_title)
        
        colunas = ["Step number", "Part name", "Actual", "Standard", "High", "Low", "Mode", "Type", "High pin", "Low pin", "Location", "Measure", "Result"]
        self.table = QTableWidget()
        self.table.setColumnCount(len(colunas))
        self.table.setHorizontalHeaderLabels(colunas)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setMinimumHeight(200)
        self.l_right.addWidget(self.table)
        
        splitter.addWidget(frame_right)
        splitter.setSizes([300, 800])
        layout.addWidget(splitter)

    def setup_monitor(self):
        layout = QVBoxLayout(self.tab_monitor)
        frame_ctrl = QFrame()
        frame_ctrl.setStyleSheet("background-color: #f1f8e9; border: 1px solid #c5e1a5; border-radius: 6px;")
        l_ctrl = QHBoxLayout(frame_ctrl)
        
        self.btn_mon = QPushButton("Iniciar Monitoramento")
        self.btn_mon.setCheckable(True)
        self.btn_mon.setMinimumHeight(40)
        self.btn_mon.setStyleSheet("font-weight: bold;")
        self.btn_mon.clicked.connect(self.toggle_monitor)
        
        self.lbl_mon_status = QLabel("STATUS: PARADO")
        self.lbl_mon_status.setStyleSheet("color: red; font-weight: bold; font-size: 14px; margin-left: 15px;")
        
        l_ctrl.addWidget(self.btn_mon)
        l_ctrl.addWidget(self.lbl_mon_status)
        l_ctrl.addStretch()
        layout.addWidget(frame_ctrl)

        layout.addWidget(QLabel("Log do Sistema:"))
        self.log_mon = QTextEdit()
        self.log_mon.setReadOnly(True)
        layout.addWidget(self.log_mon)

    def buscar(self):
        self.current_file_name = None # Reseta o arquivo atual
        termo = self.input_serial.text().strip()
        if not termo: return
        self.list_logs.clear()
        self.text_raw.clear()
        self.table.setRowCount(0)
        self.lbl_info.setText("Buscando...")
        self.status_bar.setText("Aguarde...")
        
        dirs = [self.config["finder_tri"], self.config["finder_agilent"]]
        self.thread_busca = BuscaThread(termo, dirs)
        self.thread_busca.lista_arquivos.connect(self.popular_lista)
        self.thread_busca.start()

    def popular_lista(self, arquivos):
        self.arquivos_mapa = {}
        self.list_logs.clear()
        if not arquivos:
            self.lbl_info.setText("Nenhum arquivo encontrado.")
            self.status_bar.setText("0 encontrados.")
            return
        for nome, caminho in arquivos:
            self.list_logs.addItem(nome)
            self.arquivos_mapa[nome] = caminho
        self.status_bar.setText(f"{len(arquivos)} arquivos encontrados.")

    def carregar_arquivo(self):
        item = self.list_logs.currentItem()
        if not item: return
        
        nome = item.text()
        if nome == self.current_file_name:
            return # Não faz nada se o mesmo arquivo for clicado novamente

        caminho = self.arquivos_mapa.get(nome)
        if not caminho:
            self.on_file_load_error("Caminho do arquivo não encontrado.")
            return

        # Garante que uma thread de carregamento anterior seja finalizada antes de iniciar uma nova
        if self.thread_loader and self.thread_loader.isFinished() == False:
            self.thread_loader.terminate()
            self.thread_loader.wait(2000) # Aguarda até 2s pela finalização

        # Indica que o carregamento começou
        self.lbl_info.setText("Carregando arquivo da rede...")
        self.text_raw.clear()
        self.table.setRowCount(0)

        self.current_file_name = nome # Define o novo arquivo como atual
        # Instancia e inicia a thread para carregar o arquivo
        self.thread_loader = FileLoaderThread(caminho, nome, self.config["backup_local_dir"])
        self.thread_loader.file_loaded.connect(self.on_file_loaded)
        self.thread_loader.file_load_error.connect(self.on_file_load_error)
        self.thread_loader.start()

    def on_file_loaded(self, meta, content):
        """Este slot é chamado quando a FileLoaderThread termina com sucesso."""
        html = f"""
        <h3 style='margin-bottom:2px'>ICT Log: {meta['tipo']}</h3>
        <b>Data:</b> {meta['data']} &nbsp;|&nbsp; 
        <b>Serial:</b> {meta['serial']} &nbsp;|&nbsp; 
        <b>Modelo:</b> {meta['modelo']}<br>
        """
        self.lbl_info.setText(html)
        
        # Otimização: Evita carregar logs gigantes no QTextEdit
        # Usamos encode para ter uma noção mais precisa do tamanho em bytes
        if len(content.encode('utf-8', errors='ignore')) > 1_000_000: # 1 MB
            self.text_raw.setPlainText("") # Limpa o conteúdo anterior
            self.text_raw.setPlaceholderText("Log muito grande para exibição direta (>1MB). Use um editor externo.")
        else:
            self.text_raw.setPlaceholderText("") # Limpa o placeholder se houver
            self.text_raw.setPlainText(content)

        if meta['tipo'] == "AGILENT":
            self.table.setVisible(False)
            self.lbl_table_title.setVisible(False)
        else:
            self.table.setVisible(True)
            self.lbl_table_title.setVisible(True)
            self.popular_tabela_tri(content)
        
        self.status_bar.setText("Arquivo carregado com sucesso.")

    def on_file_load_error(self, error_msg):
        """Este slot é chamado se a FileLoaderThread encontrar um erro."""
        self.current_file_name = None # Permite tentar carregar novamente
        self.lbl_info.setText(f"<font color='red'><b>Erro:</b> {error_msg}</font>")
        self.text_raw.clear()
        self.table.setRowCount(0)
        self.status_bar.setText("Falha ao carregar arquivo.")

    def popular_tabela_tri(self, content):
        self.table.setUpdatesEnabled(False)
        self.table.setSortingEnabled(False)
        self.table.clearContents()
        self.table.setRowCount(0)
        
        try:
            linhas = [l.strip() for l in content.splitlines() if l.strip()]
            dados = []
            for linha in linhas:
                cols = linha.split(',')
                if len(cols) >= 13 and cols[0].isdigit() and len(cols[0]) < 6:
                    dados.append(cols[:13])

            # Correção: Ignora a primeira linha (cabeçalho) de forma mais robusta
            if len(dados) > 0:
                dados = dados[1:]

            # Otimização: Trava de segurança para logs gigantes
            if len(dados) > 2000:
                msgBox = QMessageBox(self)
                msgBox.setIcon(QMessageBox.Warning)
                msgBox.setWindowTitle("Log Muito Grande")
                msgBox.setText(f"O log contém {len(dados)} linhas de falha.")
                msgBox.setInformativeText("Carregar todos os dados pode causar lentidão ou travar o aplicativo.\nDeseja carregar uma versão otimizada (500 linhas)?")
                btn_load_all = msgBox.addButton("Carregar Tudo", QMessageBox.DestructiveRole)
                btn_load_500 = msgBox.addButton("Carregar 500 Linhas", QMessageBox.AcceptRole)
                msgBox.setDefaultButton(btn_load_500)
                msgBox.exec_()
                
                if msgBox.clickedButton() == btn_load_500:
                    dados = dados[:500]

            self.table.setRowCount(len(dados))
            for i, row in enumerate(dados):
                for j, val in enumerate(row):
                    item = QTableWidgetItem(val)
                    item.setTextAlignment(Qt.AlignCenter)
                    
                    if j == 12: # Coluna de Resultado
                        val_upper = val.upper()
                        if "FAIL" in val_upper or "LOW" in val_upper or "HIGH" in val_upper:
                            item.setBackground(QColor("#ffcdd2"))
                            item.setForeground(QColor("red"))
                            item.setFont(QFont("Arial", weight=QFont.Bold))
                        elif "PASS" in val_upper:
                            item.setForeground(QColor("green"))
                    
                    self.table.setItem(i, j, item)
        finally:
            self.table.setSortingEnabled(True)
            self.table.setUpdatesEnabled(True)
            QApplication.processEvents() # Força a UI a redesenhar a tabela imediatamente

    def purge_old_backups(self, days=14):
        base_dir = self.config.get("backup_local_dir")
        if not base_dir or not os.path.exists(base_dir):
            return
        cutoff_ts = time.time() - (days * 24 * 60 * 60)
        for root, dirs, files in os.walk(base_dir):
            for file in files:
                path = os.path.join(root, file)
                try:
                    if os.path.getmtime(path) < cutoff_ts:
                        os.remove(path)
                except:
                    pass

        for root, dirs, files in os.walk(base_dir, topdown=False):
            if not dirs and not files:
                try:
                    os.rmdir(root)
                except:
                    pass

    def _maybe_purge_backups(self):
        today = datetime.now().strftime("%Y-%m-%d")
        if self._last_purge_date == today:
            return
        self._last_purge_date = today
        self.purge_old_backups(days=14)

    def toggle_monitor(self, force_start=False):
        ligar = True if force_start else self.btn_mon.isChecked()
        self.btn_mon.setChecked(ligar)
        
        if ligar:
            self.thread_mon = MonitorThread(
                self.config["monitor_source"],
                self.config["monitor_dest"],
                self.config["backup_local_dir"],
                self.config.get("backup_mode", "on_open")
            )
            self.thread_mon.log_msg.connect(self.log_mon.append)
            self.thread_mon.start()
            self.btn_mon.setText("PARAR Monitoramento")
            self.btn_mon.setStyleSheet("background-color: #ef5350; color: white; font-weight: bold;")
            self.lbl_mon_status.setText("RODANDO")
            self.lbl_mon_status.setStyleSheet("color: green; font-weight: bold; margin-left: 10px;")
            self.config["monitor_active"] = True
        else:
            if hasattr(self, 'thread_mon'): self.thread_mon.stop()
            self.btn_mon.setText("Iniciar Monitoramento")
            self.btn_mon.setStyleSheet("background-color: #66bb6a; color: white; font-weight: bold;")
            self.lbl_mon_status.setText("PARADO")
            self.lbl_mon_status.setStyleSheet("color: red; margin-left: 10px;")
            self.config["monitor_active"] = False
        salvar_config(self.config)

    def abrir_config(self):
        d = QDialog(self)
        d.setWindowTitle("Configurações")
        d.resize(560, 330)
        d.setMinimumSize(560, 330)
        d.setSizeGripEnabled(True)
        l = QVBoxLayout(d)
        l.setContentsMargins(12, 12, 12, 12)
        l.setSpacing(8)
        
        def add_row(txt, key):
            l.addWidget(QLabel(txt))
            edt = QLineEdit(self.config[key])
            btn = QPushButton("...")
            btn.clicked.connect(lambda: edt.setText(QFileDialog.getExistingDirectory() or edt.text()))
            h = QHBoxLayout()
            h.addWidget(edt)
            h.addWidget(btn)
            l.addLayout(h)
            return edt

        e_f_tri = add_row("Finder TRI:", "finder_tri")
        e_f_agi = add_row("Finder Agilent:", "finder_agilent")
        e_m_src = add_row("Monitor Origem:", "monitor_source")
        e_m_dst = add_row("Monitor Destino:", "monitor_dest")
        e_bkp = add_row("Backup Local:", "backup_local_dir")
        
        from PyQt5.QtWidgets import QCheckBox
        c_win = QCheckBox("Iniciar com Windows")
        c_win.setChecked(self.config["auto_start_windows"])
        l.addWidget(c_win)

        btn_ok = QPushButton("Salvar")
        btn_ok.clicked.connect(lambda: [
            self.config.update({
                "finder_tri": e_f_tri.text(),
                "finder_agilent": e_f_agi.text(),
                "monitor_source": e_m_src.text(),
                "monitor_dest": e_m_dst.text(),
                "backup_local_dir": e_bkp.text(),
                "auto_start_windows": c_win.isChecked()
            }),
            set_windows_startup(c_win.isChecked()),
            salvar_config(self.config),
            d.accept()
        ])
        l.addWidget(btn_ok)
        d.exec_()

    def init_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))
        menu = QMenu()
        menu.addAction(QAction("Abrir", self, triggered=self.showNormal))
        menu.addAction(QAction("Sair", self, triggered=QApplication.quit))
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(lambda r: self.showNormal() if r == QSystemTrayIcon.DoubleClick else None)
        self.tray_icon.show()

    def closeEvent(self, e):
        QApplication.quit()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    win = MainApp(start_minimized="--minimized" in sys.argv)
    sys.exit(app.exec_())
