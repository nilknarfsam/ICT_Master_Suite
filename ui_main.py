import sys
import os
import winreg
import time
import re
import html
from datetime import datetime

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QListWidget, QTextEdit, QFileDialog, QLabel, QMessageBox, QFrame, QTabWidget,
    QSplitter, QSystemTrayIcon, QMenu, QAction, QCheckBox, QGridLayout, QComboBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon

from models import carregar_config, salvar_config
from threads import BuscaThread, FileLoaderThread, TRICopyThread, NetworkMonitorThread

def get_resource_path(relative_path):
    """
    Retorna o caminho absoluto do recurso, compatível com PyInstaller --onefile
    """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

def set_windows_startup(enable):
    app_path = os.path.abspath(sys.argv[0])
    cmd = f'"{sys.executable.replace("python.exe", "pythonw.exe")}" "{app_path}" --minimized' if app_path.endswith('.py') else f'"{app_path}" --minimized'
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
        if enable:
            winreg.SetValueEx(key, "ICTSuiteMaster", 0, winreg.REG_SZ, cmd)
        else:
            try: winreg.DeleteValue(key, "ICTSuiteMaster")
            except FileNotFoundError: pass
        winreg.CloseKey(key)
    except OSError: pass

class MainApp(QWidget):
    def __init__(self, start_minimized=False):
        super().__init__()
        self.setWindowTitle("ICT Master Suite")
        self.setWindowIcon(QIcon(get_resource_path('icon.ico')))
        self.setGeometry(100, 100, 1280, 800)
        self.config = carregar_config()
        
        self.arquivos_mapa = {} 
        self.todos_arquivos = []
        self.thread_loader = None
        self.thread_busca = None
        self.thread_copy_tri = None
        self.thread_net_monitor = None
        self.current_file_name = None
        
        self.init_ui()
        self.init_tray()
        self.atualizar_servico_copia_tri()
        self.init_network_monitor()
        self.load_stylesheet()

        self.log_console("Sistema inicializado e pronto para operação.", nivel="INFO")

        if start_minimized:
            self.hide()
            self.tray_icon.showMessage("ICT Suite", "Rodando em background.", QSystemTrayIcon.Information, 2000)
        else:
            self.show()

    def load_stylesheet(self):
        try:
            style_path = get_resource_path("style.qss")
            with open(style_path, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())
        except Exception as e:
            print(f"Erro ao carregar style.qss: {e}")

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        h = QHBoxLayout()
        lbl_header = QLabel("ICT Technical Suite")
        lbl_header.setObjectName("lbl_header")
        h.addWidget(lbl_header)
        h.addStretch()
        
        btn_hide = QPushButton("📥 Minimizar para Bandeja")
        btn_hide.clicked.connect(self.hide)
        btn_hide.setObjectName("btn_hide")
        h.addWidget(btn_hide)
        main_layout.addLayout(h)

        self.tabs = QTabWidget()
        
        # Aba Finder Logs
        self.tab_finder = QWidget()
        self.setup_finder()
        self.tabs.addTab(self.tab_finder, "🔍 Finder Logs")

        # Aba Console do Sistema
        self.tab_console = QWidget()
        self.setup_console_tab()
        self.tabs.addTab(self.tab_console, "🖥️ Console do Sistema")
        
        # Aba Configurações do Sistema
        self.tab_config = QWidget()
        self.setup_config_tab()
        self.tabs.addTab(self.tab_config, "⚙️ Configurações do Sistema")
        
        main_layout.addWidget(self.tabs)

        self.status_bar = QLabel("Pronto.")
        self.status_bar_net = QLabel("🔍 Verificando Rede...")
        self.status_bar_net.setStyleSheet("font-weight: bold; padding: 2px 8px; border-radius: 3px;")

        footer = QHBoxLayout()
        footer.addWidget(self.status_bar)
        footer.addStretch()
        footer.addWidget(self.status_bar_net)
        footer.addSpacing(20)
        lbl_credito = QLabel("Desenvolvido por Franklin Carvalho")
        lbl_credito.setObjectName("lbl_credito")
        footer.addWidget(lbl_credito)
        main_layout.addLayout(footer)

    def init_network_monitor(self):
        """Inicializa a thread de monitoramento contínuo da saúde da rede."""
        self.thread_net_monitor = NetworkMonitorThread(target_host="147.1.0.95", interval_seconds=15)
        self.thread_net_monitor.network_status.connect(self.on_network_status_change)
        self.thread_net_monitor.start()

    def on_network_status_change(self, online, msg):
        if online:
            self.status_bar_net.setText("🟢 Rede Online")
            self.status_bar_net.setStyleSheet("color: #198754; font-weight: bold;")
            self.log_console(msg, nivel="REDE ONLINE")
        else:
            self.status_bar_net.setText("🔴 Rede Offline")
            self.status_bar_net.setStyleSheet("color: #dc3545; font-weight: bold;")
            self.log_console(msg, nivel="REDE OFFLINE")

    def log_console(self, mensagem, nivel="INFO"):
        """Registra uma mensagem formatada com timestamp no mini console."""
        now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        cores = {
            "INFO": "#007bff",
            "ABERTURA": "#198754",
            "BUSCA": "#6f42c1",
            "CÓPIA": "#20c997",
            "ERRO": "#dc3545",
            "REDE ONLINE": "#198754",
            "REDE OFFLINE": "#dc3545"
        }
        cor = cores.get(nivel.upper(), "#007bff")
        line_html = f"<span style='color:#6c757d;'>[{now_str}]</span> <b style='color:{cor};'>[{nivel.upper()}]</b> {mensagem}"
        if hasattr(self, 'txt_console_output'):
            self.txt_console_output.append(line_html)

    def setup_console_tab(self):
        layout = QVBoxLayout(self.tab_console)
        
        # Cabeçalho do Console com Botões de Controle de Serviço
        header_box = QHBoxLayout()
        
        lbl_title = QLabel("🖥️ Console do Sistema (Eventos & Cópia TRI)")
        lbl_title.setStyleSheet("font-weight: bold; font-size: 14px; color: #333;")
        header_box.addWidget(lbl_title)
        
        header_box.addSpacing(15)
        self.lbl_tri_status = QLabel("🟢 Serviço TRI: Executando")
        self.lbl_tri_status.setStyleSheet("font-weight: bold; color: #198754; background: #e8f5e9; padding: 4px 8px; border-radius: 4px;")
        header_box.addWidget(self.lbl_tri_status)
        
        header_box.addStretch()

        # Botões Pausar, Reiniciar, Exportar e Limpar
        self.btn_toggle_tri = QPushButton("⏸️ Pausar Cópia")
        self.btn_toggle_tri.clicked.connect(self.toggle_copia_tri)
        header_box.addWidget(self.btn_toggle_tri)

        btn_restart_tri = QPushButton("🔄 Reiniciar Serviço")
        btn_restart_tri.clicked.connect(self.reiniciar_servico_tri)
        header_box.addWidget(btn_restart_tri)

        btn_export = QPushButton("💾 Exportar Log (.txt)")
        btn_export.clicked.connect(self.exportar_log_console)
        header_box.addWidget(btn_export)

        btn_clear = QPushButton("🗑️ Limpar Console")
        btn_clear.clicked.connect(lambda: self.txt_console_output.clear())
        header_box.addWidget(btn_clear)

        layout.addLayout(header_box)

        self.txt_console_output = QTextEdit()
        self.txt_console_output.setReadOnly(True)
        self.txt_console_output.setStyleSheet(
            "background-color: #1e1e1e; color: #d4d4d4; font-family: Consolas, 'Courier New', monospace; font-size: 13px; padding: 10px; border-radius: 5px;"
        )
        layout.addWidget(self.txt_console_output)

    def toggle_copia_tri(self):
        if not self.thread_copy_tri or not self.thread_copy_tri.isRunning():
            self.atualizar_servico_copia_tri()
            return
            
        if self.thread_copy_tri.is_pausado():
            self.thread_copy_tri.retomar()
            self.btn_toggle_tri.setText("⏸️ Pausar Cópia")
            self.lbl_tri_status.setText("🟢 Serviço TRI: Executando")
            self.lbl_tri_status.setStyleSheet("font-weight: bold; color: #198754; background: #e8f5e9; padding: 4px 8px; border-radius: 4px;")
            self.log_console("Serviço de cópia TRI retomado.", nivel="INFO")
        else:
            self.thread_copy_tri.pausar()
            self.btn_toggle_tri.setText("▶️ Retomar Cópia")
            self.lbl_tri_status.setText("🟡 Serviço TRI: Pausado")
            self.lbl_tri_status.setStyleSheet("font-weight: bold; color: #856404; background: #fff3cd; padding: 4px 8px; border-radius: 4px;")
            self.log_console("Serviço de cópia TRI pausado pelo usuário.", nivel="INFO")

    def reiniciar_servico_tri(self):
        self.log_console("Reiniciando serviço de cópia TRI...", nivel="INFO")
        if self.thread_copy_tri and self.thread_copy_tri.isRunning():
            self.thread_copy_tri.parar()
            self.thread_copy_tri.wait(2000)
            self.thread_copy_tri = None
            
        self.atualizar_servico_copia_tri()
        self.btn_toggle_tri.setText("⏸️ Pausar Cópia")
        self.lbl_tri_status.setText("🟢 Serviço TRI: Executando")
        self.lbl_tri_status.setStyleSheet("font-weight: bold; color: #198754; background: #e8f5e9; padding: 4px 8px; border-radius: 4px;")

    def exportar_log_console(self):
        conteudo = self.txt_console_output.toPlainText()
        if not conteudo.strip():
            QMessageBox.information(self, "Console Vazio", "Não há registros no console para exportar.")
            return
            
        nome_sugerido = f"log_console_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        path, _ = QFileDialog.getSaveFileName(self, "Salvar Log do Console", nome_sugerido, "Arquivos de Texto (*.txt)")
        if path:
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(conteudo)
                self.log_console(f"Log do console exportado com sucesso para: {path}", nivel="INFO")
                QMessageBox.information(self, "Sucesso", "Log exportado com sucesso!")
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Não foi possível salvar o arquivo: {e}")

    def setup_config_tab(self):
        layout = QVBoxLayout(self.tab_config)
        
        frame = QFrame()
        frame.setStyleSheet("background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 5px; padding: 15px;")
        form_layout = QGridLayout(frame)
        form_layout.setSpacing(15)
        
        self.inputs_config = {}
        
        campos = [
            ("caminho_logs_tri", "Diretório Logs - Finder TRI (Busca):"),
            ("caminho_logs_agilent", "Diretório Logs - Finder Agilent (Busca):"),
            ("caminho_copia_origem", "Diretório Origem Varredura TRI (Cópia):"),
            ("caminho_copia_destino", "Diretório Destino Varredura TRI (Cópia):"),
            ("caminho_banco_rede", "Caminho do Banco de Dados (.db):")
        ]
        
        row = 0
        for chave, texto in campos:
            form_layout.addWidget(QLabel(texto), row, 0)
            edt = QLineEdit(self.config.get(chave, ""))
            self.inputs_config[chave] = edt
            
            btn_browser = QPushButton("📁")
            btn_browser.setFixedWidth(40)
            if chave == "caminho_banco_rede":
                btn_browser.clicked.connect(lambda _, e=edt: e.setText(QFileDialog.getOpenFileName(self, "Selecionar Banco de Dados", e.text(), "Banco SQLite (*.db);;Todos os Arquivos (*)")[0] or e.text()))
            else:
                btn_browser.clicked.connect(lambda _, e=edt: e.setText(QFileDialog.getExistingDirectory(self, "Selecionar Pasta", e.text()) or e.text()))
            
            h = QHBoxLayout()
            h.addWidget(edt)
            h.addWidget(btn_browser)
            form_layout.addLayout(h, row, 1)
            row += 1
        
        self.check_auto_copia_tri = QCheckBox("Copiar automaticamente arquivos de falha do TRI para a pasta 'defeitos_tri'")
        self.check_auto_copia_tri.setChecked(self.config.get("auto_copia_tri_defeitos", True))
        form_layout.addWidget(self.check_auto_copia_tri, row, 0, 1, 2)
        row += 1

        self.check_auto_start = QCheckBox("Iniciar sistema com o Windows (Oculto na Bandeja)")
        self.check_auto_start.setChecked(self.config.get("auto_start_windows", False))
        form_layout.addWidget(self.check_auto_start, row, 0, 1, 2)
        row += 1
        
        self.check_keep_tray = QCheckBox("Minimizar para bandeja ao fechar no 'X'")
        self.check_keep_tray.setChecked(self.config.get("keep_in_tray", True))
        form_layout.addWidget(self.check_keep_tray, row, 0, 1, 2)
        row += 1

        btn_salvar = QPushButton("💾 Salvar Configurações Globais")
        btn_salvar.setStyleSheet("background-color: #007bff; color: white; font-weight: bold; padding: 8px; font-size: 14px;")
        btn_salvar.clicked.connect(self.salvar_painel_config)
        form_layout.addWidget(btn_salvar, row, 0, 1, 2)
        
        layout.addWidget(frame)
        layout.addStretch()

    def salvar_painel_config(self):
        for chave, input_box in self.inputs_config.items():
            texto = input_box.text().strip()
            if chave in ["caminho_logs_tri", "caminho_logs_agilent", "caminho_copia_origem", "caminho_copia_destino", "caminho_banco_rede"]:
                texto = texto.replace('\\', '/')
            self.config[chave] = texto
            
        self.config["auto_copia_tri_defeitos"] = self.check_auto_copia_tri.isChecked()
        
        auto_start = self.check_auto_start.isChecked()
        self.config["auto_start_windows"] = auto_start
        set_windows_startup(auto_start)
        
        self.config["keep_in_tray"] = self.check_keep_tray.isChecked()
        
        salvar_config(self.config)
        self.atualizar_servico_copia_tri()
        self.log_console("Configurações salvas e aplicadas.", nivel="INFO")
        
        QMessageBox.information(self, "Sucesso", "Configurações salvas com sucesso em 'ict_config.json'.")

    def atualizar_servico_copia_tri(self):
        ativo = self.config.get("auto_copia_tri_defeitos", True)
        origem = self.config.get("caminho_copia_origem", "")
        destino = self.config.get("caminho_copia_destino", "")
        
        if ativo and origem and destino:
            if not self.thread_copy_tri or not self.thread_copy_tri.isRunning():
                self.thread_copy_tri = TRICopyThread(origem, destino)
                self.thread_copy_tri.log_msg.connect(lambda msg: self.log_console(msg, nivel="CÓPIA"))
                self.thread_copy_tri.start()
                self.log_console(f"Serviço de cópia TRI ativado de '{origem}' para '{destino}'", nivel="INFO")
                if hasattr(self, 'lbl_tri_status'):
                    self.lbl_tri_status.setText("🟢 Serviço TRI: Executando")
                    self.lbl_tri_status.setStyleSheet("font-weight: bold; color: #198754; background: #e8f5e9; padding: 4px 8px; border-radius: 4px;")
        else:
            if self.thread_copy_tri and self.thread_copy_tri.isRunning():
                self.thread_copy_tri.parar()
                self.thread_copy_tri.wait(2000)
                self.thread_copy_tri = None
                self.log_console("Serviço de cópia TRI desativado.", nivel="INFO")
                if hasattr(self, 'lbl_tri_status'):
                    self.lbl_tri_status.setText("🔴 Serviço TRI: Desativado")
                    self.lbl_tri_status.setStyleSheet("font-weight: bold; color: #dc3545; background: #f8d7da; padding: 4px 8px; border-radius: 4px;")

    def setup_finder(self):
        layout = QVBoxLayout(self.tab_finder)
        box_busca = QHBoxLayout()
        self.input_serial = QLineEdit()
        self.input_serial.setPlaceholderText("Serial da placa (Pressione ENTER ou F5 para buscar)...")
        self.input_serial.setMinimumHeight(35)
        self.input_serial.setObjectName("input_serial")
        self.input_serial.returnPressed.connect(self.buscar)
        
        btn_go = QPushButton(" BUSCAR (F5) ")
        btn_go.setMinimumHeight(35)
        btn_go.setObjectName("btn_go")
        btn_go.clicked.connect(self.buscar)
        
        box_busca.addWidget(self.input_serial)
        box_busca.addWidget(btn_go)
        layout.addLayout(box_busca)

        splitter = QSplitter(Qt.Horizontal)
        
        # Painel Esquerdo: Lista de Logs encontrados
        frame_left = QFrame()
        l_left = QVBoxLayout(frame_left)
        l_left.setContentsMargins(0,0,0,0)
        
        lbl_hist = QLabel("Arquivos Encontrados:")
        lbl_hist.setObjectName("lbl_hist")
        l_left.addWidget(lbl_hist)

        # Filtro por Data
        self.combo_filtro_data = QComboBox()
        self.combo_filtro_data.addItems(["Todas as Datas", "Últimas 24 Horas", "Últimos 7 Dias", "Últimos 30 Dias"])
        self.combo_filtro_data.currentIndexChanged.connect(self.aplicar_filtro_data)
        l_left.addWidget(self.combo_filtro_data)

        self.list_logs = QListWidget()
        self.list_logs.setObjectName("list_logs")
        self.list_logs.itemSelectionChanged.connect(self.carregar_arquivo)
        l_left.addWidget(self.list_logs)
        splitter.addWidget(frame_left)

        # Painel Direito: Exibição do Log selecionado
        frame_right = QFrame()
        self.l_right = QVBoxLayout(frame_right)
        self.l_right.setContentsMargins(0,0,0,0)
        self.lbl_info = QLabel("Selecione um arquivo.")
        self.lbl_info.setObjectName("lbl_info")
        self.lbl_info.setWordWrap(True)
        self.l_right.addWidget(self.lbl_info)

        lbl_log = QLabel("Log do Arquivo:")
        lbl_log.setObjectName("lbl_log")
        self.l_right.addWidget(lbl_log)
        
        self.text_raw = QTextEdit()
        self.text_raw.setReadOnly(True)
        self.text_raw.setObjectName("text_raw")
        self.l_right.addWidget(self.text_raw)
        
        splitter.addWidget(frame_right)
        splitter.setSizes([300, 800])
        layout.addWidget(splitter)

    def keyPressEvent(self, event):
        """Intercepta teclas F5 e ESC para atalhos globais."""
        if event.key() == Qt.Key_F5:
            if self.input_serial.text().strip():
                self.buscar()
                event.accept()
                return
        elif event.key() == Qt.Key_Escape:
            self.input_serial.clear()
            self.list_logs.clear()
            self.text_raw.clear()
            self.lbl_info.setText("Selecione um arquivo.")
            self.status_bar.setText("Busca limpa.")
            self.log_console("Busca e tela de log limpas via tecla ESC.", nivel="INFO")
            event.accept()
            return
        super().keyPressEvent(event)
        
    def buscar(self):
        self.current_file_name = None
        
        serial_limpo = self.input_serial.text().strip().upper()
        self.input_serial.setText(serial_limpo)
        termo = serial_limpo
        
        if not self.config.get("caminho_logs_tri") or not self.config.get("caminho_logs_agilent"):
            QMessageBox.information(self, "Caminhos Não Configurados", 
                                    "Os caminhos para a busca de logs na rede não estão configurados.\n\n"
                                    "Por favor, acesse a aba '⚙️ Configurações do Sistema' para definir os diretórios de busca.")
            return

        if len(termo) < 5:
            QMessageBox.warning(self, "Formato Inválido", "Digite pelo menos 5 caracteres do serial para realizar a busca.")
            return

        self.list_logs.clear()
        self.text_raw.clear()
        self.lbl_info.setText("Buscando...")
        self.status_bar.setText("Aguarde...")
        
        dirs = [self.config.get("caminho_logs_tri", ""), self.config.get("caminho_logs_agilent", "")]
    
        if hasattr(self, 'thread_busca') and self.thread_busca and self.thread_busca.isRunning():
            self.thread_busca.parar()
            self.thread_busca.wait(2000)

        self.thread_busca = BuscaThread(termo, dirs)
        self.thread_busca.lista_arquivos.connect(self.popular_lista)
        self.thread_busca.start()
        
    def popular_lista(self, arquivos):
        self.todos_arquivos = arquivos or []
        self.log_console(f"Busca efetuada para serial '{self.input_serial.text().strip()}'. Encontrados: {len(self.todos_arquivos)} arquivo(s).", nivel="BUSCA")
        self.aplicar_filtro_data()

    def aplicar_filtro_data(self):
        self.arquivos_mapa.clear()
        self.list_logs.clear()
        
        if not self.todos_arquivos:
            self.lbl_info.setText("Nenhum arquivo encontrado.")
            self.status_bar.setText("0 encontrados.")
            return

        idx = self.combo_filtro_data.currentIndex()
        agora = time.time()
        
        limites_segundos = {
            1: 24 * 3600,       # 24h
            2: 7 * 24 * 3600,   # 7 dias
            3: 30 * 24 * 3600   # 30 dias
        }
        max_idade = limites_segundos.get(idx, None)

        filtrados = []
        for nome, caminho in self.todos_arquivos:
            if max_idade:
                try:
                    mtime = os.path.getmtime(caminho)
                    if (agora - mtime) > max_idade:
                        continue
                except OSError:
                    pass
            filtrados.append((nome, caminho))

        for nome, caminho in filtrados:
            self.list_logs.addItem(nome)
            self.arquivos_mapa[nome] = caminho

        self.lbl_info.setText("Selecione um arquivo da lista.")
        self.status_bar.setText(f"{len(filtrados)} arquivo(s) exibido(s).")
        
    def carregar_arquivo(self):
        item = self.list_logs.currentItem()
        if not item: return
        nome = item.text()
        if nome == self.current_file_name: return
        caminho = self.arquivos_mapa.get(nome)
        if not caminho:
            self.on_file_load_error("Caminho do arquivo não encontrado.")
            return
        if self.thread_loader and not self.thread_loader.isFinished():
            self.thread_loader.terminate()
            self.thread_loader.wait(2000)
        self.lbl_info.setText("Carregando arquivo da rede...")
        self.text_raw.clear()
        self.current_file_name = nome
        self.thread_loader = FileLoaderThread(caminho, nome)
        self.thread_loader.file_loaded.connect(self.on_file_loaded)
        self.thread_loader.file_load_error.connect(self.on_file_load_error)
        self.thread_loader.start()

    def formatar_log_destaque(self, content):
        """Aplica realce de sintaxe em HTML simples para destacar falhas, aprovações e o serial pesquisado."""
        escaped = html.escape(content)
        
        # Destacar o serial pesquisado em Amarelo Destaque
        termo_serial = self.input_serial.text().strip()
        if termo_serial and len(termo_serial) >= 3:
            escaped = re.sub(re.escape(termo_serial), r'<mark style="background-color: #fff3cd; color: #856404; font-weight: bold; padding: 1px 4px; border-radius: 3px;">\g<0></mark>', escaped, flags=re.IGNORECASE)

        # Realce de termos de falha e aprovação
        escaped = re.sub(r'\b(FAIL|FAILED|FAILURE)\b', r'<b style="color: #dc3545; background-color: #f8d7da; padding: 1px 3px; border-radius: 2px;">\1</b>', escaped, flags=re.IGNORECASE)
        escaped = re.sub(r'\b(PASS|PASSED)\b', r'<b style="color: #198754; background-color: #d1e7dd; padding: 1px 3px; border-radius: 2px;">\1</b>', escaped, flags=re.IGNORECASE)
        escaped = re.sub(r'\b(HIGH|LOW|SHORT|OPEN)\b', r'<b style="color: #fd7e14;">\1</b>', escaped, flags=re.IGNORECASE)
        
        lines = escaped.splitlines()
        formatted_lines = []
        for line in lines:
            if "fail" in line.lower():
                formatted_lines.append(f"<div style='background-color: #fff5f5;'>{line}</div>")
            elif "pass" in line.lower():
                formatted_lines.append(f"<div style='background-color: #f6fff9;'>{line}</div>")
            else:
                formatted_lines.append(f"<div>{line}</div>")
                
        return f"<pre style='font-family: Consolas, \"Courier New\", monospace; font-size: 12px; line-height: 1.45; white-space: pre-wrap;'>{''.join(formatted_lines)}</pre>"
        
    def on_file_loaded(self, meta, content):
        html_info = f"""<h3 style='margin-bottom:2px'>ICT Log: {meta['tipo']}</h3>
                       <b>Data:</b> {meta['data']} &nbsp;|&nbsp; 
                       <b>Serial:</b> {meta['serial']} &nbsp;|&nbsp; 
                       <b>Modelo:</b> {meta['modelo']}<br>"""
        self.lbl_info.setText(html_info)
        
        if len(content.encode('utf-8', errors='ignore')) > 1_000_000:
            self.text_raw.setPlainText("")
            self.text_raw.setPlaceholderText("Log muito grande para exibição direta (>1MB). Use um editor externo.")
        else:
            self.text_raw.setPlaceholderText("")
            log_html = self.formatar_log_destaque(content)
            self.text_raw.setHtml(log_html)
            
        self.status_bar.setText("Arquivo carregado com sucesso.")
        self.log_console(f"Log aberto: '{self.current_file_name}' (Tipo: {meta['tipo']}, Status: {meta['status']}) - Caminho: {self.thread_loader.caminho}", nivel="ABERTURA")

    def on_file_load_error(self, error_msg):
        import PyQt5.QtWidgets as QtWidgets
        QtWidgets.QMessageBox.warning(self, "Erro de Leitura", f"Não foi possível abrir o arquivo de log no caminho especificado.\nVerifique a conexão de rede.\n\nDetalhe do erro: {error_msg}")
        self.log_console(f"Erro ao abrir arquivo '{self.current_file_name}': {error_msg}", nivel="ERRO")
        self.current_file_name = None
        self.lbl_info.setText(f"<font color='red'><b>Erro:</b> {error_msg}</font>")
        self.text_raw.clear()
        self.status_bar.setText("Falha ao carregar arquivo.")

    def init_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon(get_resource_path('icon.ico')))
        menu = QMenu()
        menu.addAction(QAction("Abrir", self, triggered=self.showNormal))
        menu.addAction(QAction("Sair", self, triggered=QApplication.quit))
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(lambda r: self.showNormal() if r == QSystemTrayIcon.DoubleClick else None)
        self.tray_icon.show()

    def closeEvent(self, e):
        if self.config.get("keep_in_tray", True) and self.tray_icon.isVisible():
            self.hide()
            self.tray_icon.showMessage("ICT Suite", "Minimizado na bandeja", QSystemTrayIcon.Information, 1000)
            e.ignore()
        else:
            QApplication.quit()

if __name__ == "__main__":
    import traceback
    def global_exception_handler(exc_type, exc_value, exc_traceback):
        log_path = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "crash_log.txt")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] CRASH CRÍTICO:\n")
            traceback.print_exception(exc_type, exc_value, exc_traceback, file=f)
    sys.excepthook = global_exception_handler

    app = QApplication(sys.argv)
    win = MainApp(start_minimized="--minimized" in sys.argv)
    sys.exit(app.exec_())