import sys
import os
import winreg
import time
import uuid
import re
import shutil
from datetime import datetime

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QListWidget, QTableWidget, QTableWidgetItem, QTextEdit, QFileDialog, QDialog, 
    QLabel, QHeaderView, QMessageBox, QFrame, QTabWidget, QSplitter, QSystemTrayIcon,
    QMenu, QAction, QStyle, QCheckBox, QGridLayout, QFileSystemModel, QTreeView, QSpinBox,
    QAbstractItemView
)
from PyQt5.QtCore import Qt, QTimer, QDir
from PyQt5.QtGui import QColor, QFont, QIcon
from PyQt5.QtChart import QChart, QChartView, QBarSet, QBarSeries, QBarCategoryAxis, QValueAxis, QPieSeries, QPieSlice

from models import carregar_config, salvar_config, salvar_falha_db, salvar_observacao, ler_observacao, obter_ultimas_analises, obter_estatisticas_progresso, limpar_analises_db, verificar_conexao_db, limpar_cache_local, buscar_historico_serial, validar_login, listar_usuarios, cadastrar_usuario, deletar_usuario
from threads import BuscaThread, FileLoaderThread, DashboardThread
import updater


def set_windows_startup(enable):
    # ... (código existente, sem alterações)
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

class LoginDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Login - ICT Suite")
        self.setFixedSize(300, 200)
        self.usuario_logado = None
        
        layout = QVBoxLayout(self)
        
        lbl_titulo = QLabel("Acesso ao Sistema")
        lbl_titulo.setAlignment(Qt.AlignCenter)
        lbl_titulo.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(lbl_titulo)
        
        self.input_login = QLineEdit()
        self.input_login.setPlaceholderText("Usuário (ex: admin)")
        layout.addWidget(self.input_login)
        
        self.input_senha = QLineEdit()
        self.input_senha.setPlaceholderText("Senha")
        self.input_senha.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.input_senha)
        
        self.btn_entrar = QPushButton("Entrar")
        self.btn_entrar.clicked.connect(self.tentar_login)
        layout.addWidget(self.btn_entrar)
        
    def tentar_login(self):
        login = self.input_login.text().strip()
        senha = self.input_senha.text().strip()
        
        if not login or not senha:
            QMessageBox.warning(self, "Aviso", "Preencha o usuário e a senha.")
            return
            
        usuario = validar_login(login, senha)
        if usuario:
            self.usuario_logado = usuario
            self.accept()
        else:
            QMessageBox.critical(self, "Acesso Negado", "Usuário ou senha inválidos.")

class MainApp(QWidget):
    def __init__(self, usuario_logado=None, start_minimized=False):
        super().__init__()
        self.setWindowTitle("ICT Master Suite - V5.3 (Polished UI)")
        self.setWindowIcon(QIcon('icon.ico'))
        self.setGeometry(100, 100, 1280, 800)
        self.config = carregar_config()
        
        # --- VERIFICAÇÃO DE ATUALIZAÇÕES ---
        versao_atual = updater.get_current_version()
        caminho_rede = self.config.get("caminho_update_rede", "")
        if updater.verificar_atualizacao(caminho_rede, versao_atual):
            resp = QMessageBox.question(self, "Atualização Disponível", 
                                        "Uma nova versão do sistema está disponível. Deseja atualizar agora?", 
                                        QMessageBox.Yes | QMessageBox.No)
            if resp == QMessageBox.Yes:
                import sys
                caminho_exe_rede = os.path.join(caminho_rede, os.path.basename(sys.argv[0]))
                if updater.aplicar_atualizacao(caminho_exe_rede):
                    sys.exit(0)
        
        # Executa o Garbage Collector do cache na inicialização
        limpar_cache_local()
        
        try:
            os.makedirs(self.config["backup_local_dir"], exist_ok=True)
        except OSError: pass
            
        self.arquivos_mapa = {} 
        self.thread_loader = None
        self.current_file_name = None
        self._last_purge_date = None
        
        self.usuario_logado = usuario_logado
        self.logout_solicitado = False
        
        self.init_ui()
        self.init_tray()
        self._maybe_purge_backups()
        
        # Timer para o Dashboard
        self.timer_dash = QTimer(self)
        self.timer_dash.timeout.connect(self.atualizar_estatisticas)
        self.timer_dash.start(60000) # 60 segundos
        self.atualizar_estatisticas() # Chama uma vez no início

        self.load_stylesheet()

        if start_minimized:
            self.hide()
            self.tray_icon.showMessage("ICT Suite", "Rodando em background.", QSystemTrayIcon.Information, 2000)
        else:
            self.show()

    def load_stylesheet(self):
        try:
            style_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "style.qss")
            with open(style_path, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())
        except Exception as e:
            print(f"Erro ao carregar style.qss: {e}")

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        h = QHBoxLayout()
        # ... (código do header existente)
        lbl_header = QLabel("ICT Technical Suite")
        lbl_header.setObjectName("lbl_header")
        h.addWidget(lbl_header)
        h.addStretch()
        
        # Perfil do Usuário e Logout
        nome_usuario = self.usuario_logado['nome'] if self.usuario_logado else "Local"
        lbl_perfil = QLabel(f"👤 Técnico: {nome_usuario}")
        lbl_perfil.setStyleSheet("font-weight: bold; color: #333; margin-right: 10px;")
        h.addWidget(lbl_perfil)
        
        btn_logout = QPushButton("Sair")
        btn_logout.setObjectName("btn_logout")
        btn_logout.setStyleSheet("background-color: #dc3545; color: white; border: none; padding: 5px 15px; border-radius: 4px; font-weight: bold;")
        btn_logout.clicked.connect(self.fazer_logout)
        h.addWidget(btn_logout)
        
        # Botão rápido para a aba (se admin) ou minimizar
        btn_hide = QPushButton("📥 Minimizar para Bandeja")
        btn_hide.clicked.connect(self.hide)
        btn_hide.setObjectName("btn_hide")
        h.addWidget(btn_hide)
        main_layout.addLayout(h)

        self.tabs = QTabWidget()
        # Aba Finder
        self.tab_finder = QWidget()
        self.setup_finder()
        self.tabs.addTab(self.tab_finder, "🔍 Finder Logs")
        # Aba Monitor removida.
        # Aba Dashboard
        self.tab_dash = QWidget()
        self.setup_dashboard()
        self.tabs.addTab(self.tab_dash, "📊 Dashboard")

        # Aba Histórico
        self.tab_history = QWidget()
        self.setup_history_tab()
        self.tabs.addTab(self.tab_history, "🗂️ Histórico Local")
        
        # Aba Gestão de Usuários (Apenas Admin)
        self.tab_admin = QWidget()
        self.setup_admin_tab()
        self.tabs.addTab(self.tab_admin, "🔒 Gestão de Usuários")
        
        # Aba Configurações do Sistema (Apenas Admin)
        self.tab_config = QWidget()
        self.setup_config_tab()
        self.tabs.addTab(self.tab_config, "⚙️ Configurações do Sistema")
        
        # Esconde as abas se não for admin
        is_admin = self.usuario_logado and self.usuario_logado.get('is_admin', False)
        if not is_admin:
            self.tabs.setTabVisible(self.tabs.indexOf(self.tab_admin), False)
            self.tabs.setTabVisible(self.tabs.indexOf(self.tab_config), False)
        
        main_layout.addWidget(self.tabs)

        # ... (código do footer existente)
        self.status_bar = QLabel("Pronto.")
        footer = QHBoxLayout()
        footer.addWidget(self.status_bar)
        footer.addStretch()
        lbl_credito = QLabel("Desenvolvido por Franklin Carvalho")
        lbl_credito.setObjectName("lbl_credito")
        footer.addWidget(lbl_credito)
        main_layout.addLayout(footer)

    def setup_config_tab(self):
        layout = QVBoxLayout(self.tab_config)
        
        frame = QFrame()
        frame.setStyleSheet("background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 5px; padding: 15px;")
        form_layout = QGridLayout(frame)
        form_layout.setSpacing(15)
        
        self.inputs_config = {}
        
        # Mapeamento dos campos: (chave_json, Label_UI)
        campos = [
            ("finder_tri", "Diretório Local/Rede - Finder TRI:"),
            ("finder_agilent", "Diretório Local/Rede - Finder Agilent:"),
            ("backup_local_dir", "Diretório Cópia/Cache (Backup Local):"),
            ("caminho_update_rede", "Caminho P/ Atualizações (Rede/OTA):"),
            ("caminho_banco_rede", "Caminho do Banco de Dados (.db):")
        ]
        
        row = 0
        for chave, texto in campos:
            form_layout.addWidget(QLabel(texto), row, 0)
            edt = QLineEdit(self.config.get(chave, ""))
            self.inputs_config[chave] = edt
            
            btn_browser = QPushButton("📁")
            btn_browser.setFixedWidth(40)
            # Dica: Se for o banco de dados, escolhe arquivo em vez de diretório
            if chave == "caminho_banco_rede":
                 btn_browser.clicked.connect(lambda _, e=edt: e.setText(QFileDialog.getOpenFileName(self, "Selecionar Banco de Dados", e.text(), "Banco SQLite (*.db);;Todos os Arquivos (*)")[0] or e.text()))
            else:
                 btn_browser.clicked.connect(lambda _, e=edt: e.setText(QFileDialog.getExistingDirectory(self, "Selecionar Pasta", e.text()) or e.text()))
            
            h = QHBoxLayout()
            h.addWidget(edt)
            h.addWidget(btn_browser)
            form_layout.addLayout(h, row, 1)
            row += 1
            
        # Spinbox: Dias de Retenção
        form_layout.addWidget(QLabel("Dias de Retenção (Backup Local):"), row, 0)
        self.spin_retencao = QSpinBox()
        self.spin_retencao.setMinimum(1)
        self.spin_retencao.setMaximum(365)
        self.spin_retencao.setValue(self.config.get("dias_retencao_cache", 30))
        h_spin = QHBoxLayout()
        h_spin.addWidget(self.spin_retencao)
        h_spin.addStretch()
        form_layout.addLayout(h_spin, row, 1)
        row += 1
        
        # Checkboxes 
        self.check_auto_start = QCheckBox("Iniciar sistema com o Windows (Oculto na Bandeja)")
        self.check_auto_start.setChecked(self.config.get("auto_start_windows", False))
        form_layout.addWidget(self.check_auto_start, row, 0, 1, 2)
        row += 1
        
        self.check_keep_tray = QCheckBox("Minimizar para bandeja ao fechar no 'X'")
        self.check_keep_tray.setChecked(self.config.get("keep_in_tray", True))
        form_layout.addWidget(self.check_keep_tray, row, 0, 1, 2)
        row += 1

        # Botão Salvar
        btn_salvar = QPushButton("💾 Salvar Configurações Globais")
        btn_salvar.setStyleSheet("background-color: #007bff; color: white; font-weight: bold; padding: 8px; font-size: 14px;")
        btn_salvar.clicked.connect(self.salvar_painel_config)
        form_layout.addWidget(btn_salvar, row, 0, 1, 2)
        
        layout.addWidget(frame)
        layout.addStretch()

    def salvar_painel_config(self):
        # Atualiza os caminhos de texto
        for chave, input_box in self.inputs_config.items():
            self.config[chave] = input_box.text().strip()
            
        # Atualiza valores extras
        self.config["dias_retencao_cache"] = self.spin_retencao.value()
        
        auto_start = self.check_auto_start.isChecked()
        self.config["auto_start_windows"] = auto_start
        set_windows_startup(auto_start)
        
        self.config["keep_in_tray"] = self.check_keep_tray.isChecked()
        
        # Persiste no JSON
        salvar_config(self.config)
        
        QMessageBox.information(self, "Sucesso", "Configurações Globais salvas com sucesso em 'ict_config.json'.\n\nPor favor, reinicie a aplicação para aplicar as novas rotas do Banco e Updater.")

    def setup_admin_tab(self):
        layout = QVBoxLayout(self.tab_admin)
        
        # Formulário de Cadastro
        frame_form = QFrame()
        frame_form.setStyleSheet("background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 5px; padding: 10px;")
        form_layout = QGridLayout(frame_form)
        
        form_layout.addWidget(QLabel("Nome do Técnico:"), 0, 0)
        self.input_novo_nome = QLineEdit()
        form_layout.addWidget(self.input_novo_nome, 0, 1)
        
        form_layout.addWidget(QLabel("Login de Acesso:"), 0, 2)
        self.input_novo_login = QLineEdit()
        form_layout.addWidget(self.input_novo_login, 0, 3)
        
        form_layout.addWidget(QLabel("Senha Segura:"), 1, 0)
        self.input_nova_senha = QLineEdit()
        self.input_nova_senha.setEchoMode(QLineEdit.Password)
        form_layout.addWidget(self.input_nova_senha, 1, 1)
        
        self.check_is_admin = QCheckBox("Privilégios de Administrador?")
        form_layout.addWidget(self.check_is_admin, 1, 2, 1, 2)
        
        btn_cadastrar = QPushButton("Cadastrar Técnico")
        btn_cadastrar.setStyleSheet("background-color: #28a745; color: white; font-weight: bold;")
        btn_cadastrar.clicked.connect(self.adicionar_usuario)
        form_layout.addWidget(btn_cadastrar, 2, 0, 1, 4)
        
        layout.addWidget(frame_form)
        
        # Tabela de Usuários
        self.table_usuarios = QTableWidget()
        self.table_usuarios.setColumnCount(5) # ID, Nome, Login, Perfil, Ação
        self.table_usuarios.setHorizontalHeaderLabels(["ID", "Nome", "Login", "Perfil", "Ações"])
        self.table_usuarios.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_usuarios.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_usuarios.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_usuarios.setAlternatingRowColors(True)
        layout.addWidget(self.table_usuarios)
        
        # Botão de atualizar tabela manual (opcional, já atualiza auto no cadastro)
        btn_atualizar = QPushButton("Atualizar Lista")
        btn_atualizar.clicked.connect(self.carregar_tabela_usuarios)
        layout.addWidget(btn_atualizar)
        
        self.carregar_tabela_usuarios()

    def carregar_tabela_usuarios(self):
        usuarios = listar_usuarios()
        self.table_usuarios.setRowCount(len(usuarios))
        for row, user in enumerate(usuarios):
            self.table_usuarios.setItem(row, 0, QTableWidgetItem(str(user['id'])))
            self.table_usuarios.setItem(row, 1, QTableWidgetItem(user['nome']))
            self.table_usuarios.setItem(row, 2, QTableWidgetItem(user['login']))
            
            perfil = "Administrador" if user['is_admin'] else "Técnico"
            item_perfil = QTableWidgetItem(perfil)
            if user['is_admin']:
                item_perfil.setForeground(QColor("blue"))
                item_perfil.setFont(QFont("Arial", weight=QFont.Bold))
            self.table_usuarios.setItem(row, 3, item_perfil)
            
            # Botão de Excluir
            btn_excluir = QPushButton("Excluir")
            btn_excluir.setStyleSheet("background-color: #dc3545; color: white; padding: 2px;")
            btn_excluir.clicked.connect(lambda _, id_user=user['id']: self.remover_usuario(id_user))
            self.table_usuarios.setCellWidget(row, 4, btn_excluir)

    def adicionar_usuario(self):
        nome = self.input_novo_nome.text().strip()
        login = self.input_novo_login.text().strip()
        senha = self.input_nova_senha.text().strip()
        is_admin = self.check_is_admin.isChecked()
        
        if not nome or not login or not senha:
            QMessageBox.warning(self, "Aviso", "Preencha todos os campos para cadastrar.")
            return
            
        if cadastrar_usuario(nome, login, senha, is_admin):
            QMessageBox.information(self, "Sucesso", "Usuário cadastrado com sucesso!")
            self.input_novo_nome.clear()
            self.input_novo_login.clear()
            self.input_nova_senha.clear()
            self.check_is_admin.setChecked(False)
            self.carregar_tabela_usuarios() # Atualiza a view
        else:
            QMessageBox.critical(self, "Erro", "Não foi possível cadastrar o usuário. Verifique se o login já existe.")

    def remover_usuario(self, id_usuario):
        resposta = QMessageBox.question(self, "Confirmação", "Tem certeza que deseja excluir este usuário?", QMessageBox.Yes | QMessageBox.No)
        if resposta == QMessageBox.Yes:
            if deletar_usuario(id_usuario):
                QMessageBox.information(self, "Sucesso", "Usuário excluído com sucesso.")
                self.carregar_tabela_usuarios()
            else:
                QMessageBox.warning(self, "Aviso", "Não foi possível excluir o usuário. (O último administrador não pode ser removido!)")

    def setup_history_tab(self):
        layout = QVBoxLayout(self.tab_history)

        # --- BARRA DE FERRAMENTAS ---
        tools_bar = QHBoxLayout()
        tools_bar.addStretch()
        
        tools_button = QPushButton("🛠️ Ferramentas")
        tools_menu = QMenu(self)
        clear_action = tools_menu.addAction("🗑️ Limpar Histórico Local...")
        clear_action.triggered.connect(self.limpar_historico_local)
        tools_button.setMenu(tools_menu)
        
        tools_bar.addWidget(tools_button)
        layout.addLayout(tools_bar)
        
        splitter = QSplitter(Qt.Horizontal)

        # Lado Esquerdo: Navegador de Arquivos
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self.fs_model = QFileSystemModel()
        self.fs_model.setRootPath(self.config["backup_local_dir"])
        self.fs_model.setFilter(QDir.NoDotAndDotDot | QDir.Files | QDir.AllDirs)

        self.tree_history = QTreeView()
        self.tree_history.setModel(self.fs_model)
        self.tree_history.setRootIndex(self.fs_model.index(self.config["backup_local_dir"]))
        
        # Ocultar colunas de tamanho, tipo e data
        self.tree_history.setColumnHidden(1, True) # Size
        self.tree_history.setColumnHidden(2, True) # Type
        self.tree_history.setColumnHidden(3, True) # Date Modified

        self.tree_history.clicked.connect(self.on_history_file_clicked)
        left_layout.addWidget(self.tree_history)
        
        splitter.addWidget(left_widget)

        # Lado Direito: Editor de Análise
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        lbl_log_viewer = QLabel("Conteúdo do Log:")
        right_layout.addWidget(lbl_log_viewer)
        
        self.txt_history_log_viewer = QTextEdit()
        self.txt_history_log_viewer.setReadOnly(True)
        self.txt_history_log_viewer.setObjectName("txt_history_log_viewer")
        right_layout.addWidget(self.txt_history_log_viewer)

        lbl_obs = QLabel("Observações / Análise Técnica:")
        lbl_obs.setObjectName("lbl_obs")
        right_layout.addWidget(lbl_obs)

        self.txt_history_obs = QTextEdit()
        self.txt_history_obs.setPlaceholderText("Digite sua análise sobre este log...")
        right_layout.addWidget(self.txt_history_obs)

        btn_salvar = QPushButton("💾 Atualizar Análise")
        btn_salvar.clicked.connect(self.salvar_edicao_historico)
        right_layout.addWidget(btn_salvar)
        
        splitter.addWidget(right_widget)
        
        splitter.setSizes([350, 750])
        layout.addWidget(splitter)


    def on_history_file_clicked(self, index):
        file_path = self.fs_model.filePath(index)
        
        if not self.fs_model.isDir(index):
            # Limpa os campos antes de carregar
            self.txt_history_log_viewer.clear()
            self.txt_history_obs.clear()

            # Carrega o conteúdo do arquivo de log
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                self.txt_history_log_viewer.setPlainText(content)
            except Exception as e:
                self.txt_history_log_viewer.setPlainText(f"--- ERRO AO LER O ARQUIVO ---\n\n{str(e)}")

            # Carrega a observação do banco de dados
            file_name = os.path.basename(file_path)
            observacao = ler_observacao(file_name)
            self.txt_history_obs.setPlainText(observacao)


    def salvar_edicao_historico(self):
        if not verificar_conexao_db():
            QMessageBox.critical(self, "Rede Offline", "O banco de dados na rede está inacessível.\n\n- Verifique sua conexão com a internet/rede da empresa.\n- Certifique-se de que o servidor de arquivos está online.\n\nTente novamente em alguns instantes.")
            return

        current_indexes = self.tree_history.selectedIndexes()
        if not current_indexes:
            QMessageBox.warning(self, "Nenhum Arquivo Selecionado", "Por favor, selecione um arquivo na árvore para poder salvar uma análise.")
            return

        index = current_indexes[0]
        file_path = self.fs_model.filePath(index)
        
        if self.fs_model.isDir(index):
            QMessageBox.warning(self, "Seleção Inválida", "Você selecionou uma pasta. Por favor, selecione um arquivo de log.")
            return
            
        file_name = os.path.basename(file_path)
        texto_analise = self.txt_history_obs.toPlainText().strip()
        nome_usuario = self.usuario_logado['nome'] if self.usuario_logado else "Local"

        if salvar_observacao(file_name, texto_analise, tecnico=nome_usuario):
            QMessageBox.information(self, "Sucesso", "Análise atualizada com sucesso!")
        else:
            QMessageBox.critical(self, "Erro no Banco de Dados", "Não foi possível salvar a análise. O banco de dados pode estar bloqueado por outro usuário. Tente novamente.")

    def limpar_historico_local(self):
        """Limpa o cache de logs locais e reseta as análises no banco de dados."""
        if not verificar_conexao_db():
            QMessageBox.critical(self, "Rede Offline", "O banco de dados na rede está inacessível.\n\nA limpeza de histórico não pode prosseguir sem acesso ao banco de dados.")
            return

        confirm = QMessageBox.warning(self, "Confirmação",
                                      "Você tem certeza que deseja limpar TODO o histórico local?\n\n"
                                      "Esta ação irá:\n"
                                      "1. Apagar todos os arquivos de log salvos localmente.\n"
                                      "2. Resetar todas as análises técnicas no banco de dados central (marcando-as como 'ABERTO').\n\n"
                                      "Esta ação não pode ser desfeita.",
                                      QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if confirm == QMessageBox.Yes:
            self.status_bar.setText("Limpando histórico local...")
            QApplication.processEvents() # Força atualização da UI

            # 1. Limpa o banco de dados
            if not limpar_analises_db():
                QMessageBox.critical(self, "Erro no Banco de Dados", "Não foi possível limpar as análises no banco de dados. Verifique a conexão de rede.")
                self.status_bar.setText("Falha ao limpar o histórico.")
                return

            # 2. Limpa o diretório de backup local
            backup_dir = self.config.get("backup_local_dir")
            try:
                if os.path.exists(backup_dir):
                    shutil.rmtree(backup_dir)
                    os.makedirs(backup_dir, exist_ok=True)
            except OSError as e:
                QMessageBox.critical(self, "Erro de Arquivo", f"Não foi possível apagar a pasta de backup local:\n{str(e)}")
                self.status_bar.setText("Falha ao limpar o histórico.")
                return

            # Limpa a visualização de qualquer arquivo aberto
            self.txt_history_log_viewer.clear()
            self.txt_history_obs.clear()
            
            QMessageBox.information(self, "Sucesso", "O histórico local foi limpo com sucesso.")
            self.status_bar.setText("Pronto.")



    def setup_dashboard(self):
        self.tab_dash.setObjectName("tab_dash")
        layout = QGridLayout(self.tab_dash)
        layout.setSpacing(25)
        layout.setContentsMargins(25, 25, 25, 25)

        # Card 1: Falhas Hoje
        card1 = QFrame()
        card1.setObjectName("dash_card")
        card1_layout = QVBoxLayout(card1)
        lbl_title1 = QLabel("FALHAS (HOJE)")
        lbl_title1.setObjectName("dash_title")
        lbl_title1.setAlignment(Qt.AlignCenter)
        self.lbl_dash_total_hoje = QLabel("...")
        self.lbl_dash_total_hoje.setObjectName("lbl_dash_total_hoje")
        self.lbl_dash_total_hoje.setAlignment(Qt.AlignCenter)
        card1_layout.addWidget(lbl_title1)
        card1_layout.addStretch()
        card1_layout.addWidget(self.lbl_dash_total_hoje)
        card1_layout.addStretch()
        layout.addWidget(card1, 0, 0)

        # Card 2: Top 5 Componentes Críticos
        card2 = QFrame()
        card2.setObjectName("dash_card")
        card2_layout = QVBoxLayout(card2)
        lbl_title2 = QLabel("TOP 5 COMPONENTES (HOJE)")
        lbl_title2.setObjectName("dash_title")
        lbl_title2.setAlignment(Qt.AlignCenter)
        card2_layout.addWidget(lbl_title2)

        chart_bar = QChart()
        chart_bar.setAnimationOptions(QChart.SeriesAnimations)
        chart_bar.legend().setVisible(False)
        
        self.chart_view_bar = QChartView(chart_bar)
        self.chart_view_bar.setObjectName("chart_view")
        card2_layout.addWidget(self.chart_view_bar)
        
        layout.addWidget(card2, 0, 1)

        # Card 3: Progresso de Análise (Donut Chart)
        card3 = QFrame()
        card3.setObjectName("dash_card")
        card3_layout = QVBoxLayout(card3)
        lbl_title3 = QLabel("PROGRESSO DE ANÁLISE (HOJE)")
        lbl_title3.setObjectName("dash_title")
        lbl_title3.setAlignment(Qt.AlignCenter)
        card3_layout.addWidget(lbl_title3)

        chart_donut = QChart()
        chart_donut.setAnimationOptions(QChart.SeriesAnimations)
        chart_donut.legend().setVisible(True)
        chart_donut.legend().setAlignment(Qt.AlignBottom)

        self.chart_view_donut = QChartView(chart_donut)
        self.chart_view_donut.setObjectName("chart_view")
        card3_layout.addWidget(self.chart_view_donut)

        layout.addWidget(card3, 0, 2)
        
        # Card 4: Atividade Recente
        card4 = QFrame()
        card4.setObjectName("dash_card")
        card4_layout = QVBoxLayout(card4)
        lbl_title4 = QLabel("ATIVIDADE RECENTE")
        lbl_title4.setObjectName("dash_title")
        lbl_title4.setAlignment(Qt.AlignCenter)
        card4_layout.addWidget(lbl_title4)

        self.table_recentes = QTableWidget()
        self.table_recentes.setColumnCount(4)
        self.table_recentes.setHorizontalHeaderLabels(["Data", "Serial", "Componente", "Status"])
        self.table_recentes.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_recentes.verticalHeader().setVisible(False)
        self.table_recentes.setAlternatingRowColors(True)
        self.table_recentes.setObjectName("table_recentes")
        # Bloqueia edição e seleciona a linha inteira
        self.table_recentes.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_recentes.setSelectionBehavior(QAbstractItemView.SelectRows)
        card4_layout.addWidget(self.table_recentes)

        layout.addWidget(card4, 1, 0, 1, 3) # Ocupa a largura de 3 colunas na linha de baixo

        layout.setRowStretch(0, 0)
        layout.setRowStretch(1, 1)

    def atualizar_tabela_recentes(self, dados):
        self.table_recentes.setRowCount(0)
        if not dados:
            return

        self.table_recentes.setRowCount(len(dados))
        bold_font = QFont()
        bold_font.setBold(True)

        for i, row in enumerate(dados):
            data_str, serial, componente, status = row
            
            # Formata a data
            try:
                data_dt = datetime.strptime(data_str, '%Y-%m-%d %H:%M:%S.%f')
                item_data = QTableWidgetItem(data_dt.strftime('%d/%m/%y %H:%M'))
            except ValueError:
                item_data = QTableWidgetItem(data_str) # Fallback para o formato original
            
            item_serial = QTableWidgetItem(serial)
            item_componente = QTableWidgetItem(componente)
            item_status = QTableWidgetItem(status)
            item_status.setTextAlignment(Qt.AlignCenter)

            # Colore o status para destaque visual
            if status == "ABERTO":
                item_status.setForeground(QColor("#e74c3c"))
                item_status.setFont(bold_font)
            elif status in ["TRATADO", "RESOLVIDO"]:
                item_status.setForeground(QColor("#27ae60"))

            self.table_recentes.setItem(i, 0, item_data)
            self.table_recentes.setItem(i, 1, item_serial)
            self.table_recentes.setItem(i, 2, item_componente)
            self.table_recentes.setItem(i, 3, item_status)

    def atualizar_grafico(self, top_5_data):
        chart = self.chart_view_bar.chart() # Alterado para chart_view_bar
        chart.removeAllSeries()
        for axis in chart.axes():
            chart.removeAxis(axis)
        if not top_5_data:
            chart.setTitle("Nenhuma falha registrada hoje.")
            return

        chart.setTitle("")
        
        series = QBarSeries()
        series.setLabelsVisible(True) # Mostra os valores acima das barras
        
        bar_set = QBarSet("Falhas")
        bar_set.setColor(QColor("#e74c3c"))
        
        nomes_componentes = []
        max_val = 0
        for comp, count in top_5_data:
            bar_set.append(count)
            nomes_componentes.append(comp)
            if count > max_val:
                max_val = count

        series.append(bar_set)
        chart.addSeries(series)

        axis_x = QBarCategoryAxis()
        axis_x.append(nomes_componentes)
        chart.addAxis(axis_x, Qt.AlignBottom)
        series.attachAxis(axis_x)

        axis_y = QValueAxis()
        # Aumenta a margem superior para 50% para a barra não tocar o teto
        axis_y.setRange(0, max_val * 1.5 if max_val > 0 else 10) 
        axis_y.setTickCount(min(max_val + 2, 12)) # Ajusta os ticks para serem inteiros
        axis_y.setLabelFormat("%d") # Garante que o eixo Y mostre números inteiros
        chart.addAxis(axis_y, Qt.AlignLeft)
        series.attachAxis(axis_y)

    def atualizar_estatisticas(self):
        self.dash_thread = DashboardThread()
        self.dash_thread.stats_updated.connect(self.on_stats_updated)
        self.dash_thread.start()

    def on_stats_updated(self, stats):
        # Card 1
        self.lbl_dash_total_hoje.setText(str(stats['total_hoje']))
        
        # Card 2
        self.atualizar_grafico(stats.get('top_5_componentes', []))

        # Card 3 (Donut) - busca novos dados
        progresso_stats = obter_estatisticas_progresso()
        self.atualizar_grafico_progresso(progresso_stats)

        # Status Bar
        db_status_text = "DB: 🟢 ONLINE" if stats['db_online'] else "DB: 🔴 OFFLINE"
        self.status_bar.setText(f"Pronto. | {db_status_text}")

        # Card 4
        ultimas_analises = obter_ultimas_analises(limite=15)
        self.atualizar_tabela_recentes(ultimas_analises)

    def atualizar_grafico_progresso(self, progresso_stats):
        chart = self.chart_view_donut.chart()
        chart.removeAllSeries()
        
        series = QPieSeries()
        series.setHoleSize(0.40)

        abertos = progresso_stats.get('abertos', 0)
        tratados = progresso_stats.get('tratados', 0)

        if abertos == 0 and tratados == 0:
            chart.setTitle("Nenhuma atividade hoje.")
            return
        else:
            chart.setTitle("")

        # Fatia de Abertos
        slice_abertos = QPieSlice(f"Abertos: {abertos}", abertos)
        slice_abertos.setColor(QColor("#f1c40f")) # Amarelo
        slice_abertos.setLabelVisible(True)
        
        # Fatia de Tratados
        slice_tratados = QPieSlice(f"Tratados: {tratados}", tratados)
        slice_tratados.setColor(QColor("#27ae60")) # Verde
        slice_tratados.setLabelVisible(True)

        series.append(slice_abertos)
        series.append(slice_tratados)
        
        chart.addSeries(series)

    def setup_finder(self):
        layout = QVBoxLayout(self.tab_finder)
        box_busca = QHBoxLayout()
        self.input_serial = QLineEdit()
        self.input_serial.setPlaceholderText("Serial da placa...")
        self.input_serial.setMinimumHeight(35)
        self.input_serial.setObjectName("input_serial")
        self.input_serial.returnPressed.connect(self.buscar)
        btn_go = QPushButton(" BUSCAR ")
        btn_go.setMinimumHeight(35)
        btn_go.setObjectName("btn_go")
        btn_go.clicked.connect(self.buscar)
        box_busca.addWidget(self.input_serial)
        box_busca.addWidget(btn_go)
        layout.addLayout(box_busca)
        splitter = QSplitter(Qt.Horizontal)
        frame_left = QFrame()
        l_left = QVBoxLayout(frame_left)
        l_left.setContentsMargins(0,0,0,0)
        lbl_hist = QLabel("Histórico (Recentes):")
        lbl_hist.setObjectName("lbl_hist")
        l_left.addWidget(lbl_hist)
        self.list_logs = QListWidget()
        self.list_logs.setObjectName("list_logs")
        self.list_logs.itemSelectionChanged.connect(self.carregar_arquivo)
        l_left.addWidget(self.list_logs)
        splitter.addWidget(frame_left)
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
        self.lbl_table_title = QLabel("Detalhamento de Defeitos (TRI):")
        self.lbl_table_title.setObjectName("lbl_table_title")
        self.l_right.addWidget(self.lbl_table_title)
        colunas = ["Step", "Part name", "Actual", "Standard", "High", "Low", "Mode", "Type", "High pin", "Low pin", "Location", "Measure", "Result"]
        self.table = QTableWidget()
        self.table.setColumnCount(len(colunas))
        self.table.setHorizontalHeaderLabels(colunas)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setMinimumHeight(200)
        # Bloqueia edição e seleciona a linha inteira
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.l_right.addWidget(self.table)

        # Alerta de Histórico Colaborativo
        self.lbl_historico_alerta = QLabel("")
        self.lbl_historico_alerta.setObjectName("lbl_historico_alerta")
        self.lbl_historico_alerta.setWordWrap(True)
        self.lbl_historico_alerta.setStyleSheet("background-color: #fff3cd; color: #856404; padding: 10px; border-radius: 5px; border: 1px solid #ffeeba; font-weight: bold; margin-bottom: 5px;")
        self.lbl_historico_alerta.setVisible(False)
        self.l_right.addWidget(self.lbl_historico_alerta)

        # Seção de Observações do Técnico
        lbl_obs_title = QLabel("Observações do Técnico:")
        lbl_obs_title.setObjectName("lbl_obs_title")
        self.l_right.addWidget(lbl_obs_title)

        self.txt_observacao = QTextEdit()
        self.txt_observacao.setPlaceholderText("Digite a análise técnica, causa da falha, solução aplicada, etc.")
        self.txt_observacao.setObjectName("txt_observacao")
        self.txt_observacao.setMinimumHeight(80)
        self.l_right.addWidget(self.txt_observacao)

        self.btn_salvar_obs = QPushButton("Salvar Análise")
        self.btn_salvar_obs.clicked.connect(self.salvar_analise_tecnico)
        self.l_right.addWidget(self.btn_salvar_obs)
        
        splitter.addWidget(frame_right)
        splitter.setSizes([300, 800])
        layout.addWidget(splitter)
        
        
    def buscar(self):
        self.current_file_name = None
        
        # Sanitização e feedback visual
        serial_limpo = self.input_serial.text().strip().upper()
        self.input_serial.setText(serial_limpo)
        termo = serial_limpo
        
        if not self.config.get("finder_tri") or not self.config.get("finder_agilent"):
            QMessageBox.information(self, "Caminhos Não Configurados", 
                                    "Os caminhos para a busca de logs na rede não estão configurados.\n\n"
                                    "Por favor, clique no botão '⚙️ Config' no canto superior direito para definir os diretórios do 'Finder TRI' e 'Finder Agilent'.")
            return

        if len(termo) not in [10, 23]:
            QMessageBox.warning(self, "Formato Inválido", "O serial deve ter exatamente 10 caracteres (Placa) ou 23 caracteres (Painel).")
            return

        self.list_logs.clear()
        self.text_raw.clear()
        self.table.setRowCount(0)
        self.lbl_historico_alerta.setVisible(False)
        self.lbl_info.setText("Buscando...")
        self.status_bar.setText("Aguarde...")
        dirs = [self.config["finder_tri"], self.config["finder_agilent"]]
        self.thread_busca = BuscaThread(termo, dirs)
        self.thread_busca.lista_arquivos.connect(self.popular_lista)
        self.thread_busca.start()
        
    def popular_lista(self, arquivos):
        # ... (código existente, sem alterações)
        self.arquivos_mapa.clear()
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
        # ... (código existente, sem alterações)
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
        self.table.setRowCount(0)
        self.lbl_historico_alerta.setVisible(False)
        self.txt_observacao.clear()
        self.current_file_name = nome
        self.thread_loader = FileLoaderThread(caminho, nome, self.config["backup_local_dir"])
        self.thread_loader.file_loaded.connect(self.on_file_loaded)
        self.thread_loader.file_load_error.connect(self.on_file_load_error)
        self.thread_loader.start()
        
    def on_file_loaded(self, meta, content):
        html = f"""<h3 style='margin-bottom:2px'>ICT Log: {meta['tipo']}</h3>
                   <b>Data:</b> {meta['data']} &nbsp;|&nbsp; 
                   <b>Serial:</b> {meta['serial']} &nbsp;|&nbsp; 
                   <b>Modelo:</b> {meta['modelo']}<br>"""
        self.lbl_info.setText(html)
        if len(content.encode('utf-8', errors='ignore')) > 1_000_000:
            self.text_raw.setPlainText("")
            self.text_raw.setPlaceholderText("Log muito grande para exibição direta (>1MB). Use um editor externo.")
        else:
            self.text_raw.setPlaceholderText("")
            self.text_raw.setPlainText(content)
        
        is_tri = meta['tipo'] == 'TRI'
        self.table.setVisible(is_tri)
        self.lbl_table_title.setVisible(is_tri)
        if is_tri:
            self.popular_tabela_tri(content)
        
        # REGISTRA A FALHA NO BANCO DE DADOS AO ABRIR O ARQUIVO
        falhas_salvas = self._registrar_falhas_no_db(meta, content)
        if falhas_salvas > 0:
            self.status_bar.setText("Arquivo carregado e registrado no Banco de Dados.")
        else:
            self.status_bar.setText("Arquivo carregado (sem novas falhas para registrar).")
            
        # Carrega a observação existente, se houver
        obs_existente = ler_observacao(self.current_file_name)
        self.txt_observacao.setPlainText(obs_existente)
        
        # Verifica histórico colaborativo da placa
        historico = buscar_historico_serial(meta.get("serial", ""))
        if historico:
            data_fmt = historico["data"][:16] # simplifica a data se tiver ms
            tecnico = historico.get("tecnico") or "Desconhecido"
            msg = f"⚠️ Placa já analisada por {tecnico}: {historico['texto']}\n(Em {data_fmt})"
            self.lbl_historico_alerta.setText(msg)
            self.lbl_historico_alerta.setVisible(True)
        else:
            self.lbl_historico_alerta.setVisible(False)
        
        # BUGFIX: Força a atualização do Dashboard e da árvore de Histórico
        self.atualizar_estatisticas()
        
        try:
            nome_arquivo = self.current_file_name
            data_hoje_str = datetime.now().strftime("%Y-%m-%d")
            caminho_backup = os.path.join(self.config['backup_local_dir'], 'abertos', data_hoje_str, nome_arquivo)
            
            # Força o foco da árvore no arquivo recém-criado
            index = self.fs_model.index(caminho_backup)
            if index.isValid():
                self.tree_history.setCurrentIndex(index)
                self.tree_history.expand(index.parent()) # Garante que o diretório pai esteja expandido
        except Exception:
            pass # A navegação automática é um bônus, não deve quebrar a aplicação
        
    def on_file_load_error(self, error_msg):
        # ... (código existente, sem alterações)
        self.current_file_name = None
        self.lbl_info.setText(f"<font color='red'><b>Erro:</b> {error_msg}</font>")
        self.text_raw.clear()
        self.table.setRowCount(0)
        self.status_bar.setText("Falha ao carregar arquivo.")

    def _registrar_falhas_no_db(self, meta, content):
        """
        Analisa o conteúdo de um log, extrai falhas e as salva no banco de dados.
        Retorna o número de falhas salvas.
        """
        if meta.get("status") != "FAIL":
            return 0
            
        caminho_arquivo = self.thread_loader.caminho
        nome_arquivo = self.current_file_name
        
        try:
            ts = os.path.getmtime(caminho_arquivo)
            data_falha_dt = datetime.fromtimestamp(ts)
        except OSError:
            data_falha_dt = datetime.now()

        serial = meta.get("serial", "N/A")
        modelo = meta.get("modelo", "N/A")
        
        falhas_encontradas = 0

        if meta['tipo'] == 'AGILENT':
            defeito = None
            content_lower = content.lower()

            # Prioridade 1: Curto-circuito
            if "shorts report" in content_lower or "shorts test failed" in content_lower:
                defeito = { "componente": "CURTO-CIRCUITO", "step": "SHORTS" }
            
            # Prioridade 2: Circuito Aberto
            elif "opens report" in content_lower or "pins report" in content_lower:
                defeito = { "componente": "CIRCUITO ABERTO", "step": "OPENS" }

            # Prioridade 3: Falha de Componente
            else:
                match = re.search(r'(?:Test of|Test Jet)\s+([A-Z0-9\-\.]+)\s+.*(?:FAILED|FAILURE)', content, re.IGNORECASE)
                if match:
                    componente = match.group(1).split('.')[0]
                    defeito = { "componente": componente, "step": "COMPONENT" }
                elif "failed" in content_lower or "failure" in content_lower:
                    defeito = { "componente": "FALHA DE COMPONENTE", "step": "ANALYSIS" }

            if defeito:
                defeito_completo = {
                    "id": f"{nome_arquivo}-AGILENT",
                    "data_registro": datetime.now(), "data_falha": data_falha_dt,
                    "arquivo": nome_arquivo, "serial": serial, "modelo": modelo,
                    "componente": defeito["componente"], "step": defeito["step"],
                }
                if salvar_falha_db(defeito_completo):
                    falhas_encontradas = 1

        elif meta['tipo'] == 'TRI':
            linhas_analise = [l for l in content.splitlines() if l.strip()]
            for linha in linhas_analise:
                defeito = None
                if ',' in linha:
                    parts = linha.split(',')
                    if len(parts) > 12 and parts[0].isdigit() and len(parts[0]) < 6:
                        resultado = parts[12].upper()
                        if "FAIL" in resultado or "HIGH" in resultado or "LOW" in resultado:
                            defeito = {
                                "id": f"{nome_arquivo}-{parts[0]}",
                                "data_registro": datetime.now(), "data_falha": data_falha_dt,
                                "arquivo": nome_arquivo, "serial": serial, "modelo": modelo,
                                "componente": parts[1], "step": parts[0],
                            }
                if defeito:
                    if salvar_falha_db(defeito):
                        falhas_encontradas += 1

        if falhas_encontradas == 0 and meta.get('status') == 'FAIL':
            componente_generico = "VERIFICAR LOG"
            step_generico = "FALHA GERAL"
            if meta['tipo'] == 'AGILENT':
                componente_generico = "FALHA GERAL AGILENT"
                step_generico = "UNKNOWN"

            defeito_generico = {
                "id": f"{nome_arquivo}-GERAL",
                "data_registro": datetime.now(), "data_falha": data_falha_dt,
                "arquivo": nome_arquivo, "serial": serial, "modelo": modelo,
                "componente": componente_generico, "step": step_generico,
            }
            if salvar_falha_db(defeito_generico):
                falhas_encontradas += 1
        
        return falhas_encontradas
        
    def popular_tabela_tri(self, content):
        # ... (código existente, sem alterações)
        self.table.setUpdatesEnabled(False)
        self.table.setSortingEnabled(False)
        self.table.clearContents()
        self.table.setRowCount(0)
        try:
            linhas = [l.strip() for l in content.splitlines() if l.strip()]
            dados = [cols[:13] for cols in (l.split(',') for l in linhas) if len(cols) >= 13 and cols[0].isdigit() and len(cols[0]) < 6]
            if dados: dados.pop(0)
            if len(dados) > 2000:
                msgBox = QMessageBox(self)
                msgBox.setIcon(QMessageBox.Warning)
                msgBox.setWindowTitle("Log Muito Grande")
                msgBox.setText(f"O log contém {len(dados)} linhas de falha.")
                msgBox.setInformativeText("Carregar todos os dados pode causar lentidão. Deseja carregar uma versão otimizada (500 linhas)?")
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
                    if j == 12:
                        val_upper = val.upper()
                        if "FAIL" in val_upper or "LOW" in val_upper or "HIGH" in val_upper:
                            item.setBackground(QColor("#ffcdd2")); item.setForeground(QColor("red")); item.setFont(QFont("Arial", weight=QFont.Bold))
                        elif "PASS" in val_upper:
                            item.setForeground(QColor("green"))
                    self.table.setItem(i, j, item)
        finally:
            self.table.setSortingEnabled(True)
            self.table.setUpdatesEnabled(True)
            QApplication.processEvents()

    def salvar_analise_tecnico(self):
        """Salva o texto de análise do técnico no banco de dados."""
        if not verificar_conexao_db():
            QMessageBox.critical(self, "Rede Offline", "O banco de dados na rede está inacessível.\n\n- Verifique sua conexão com a internet/rede da empresa.\n- Certifique-se de que o servidor de arquivos está online.\n\nTente novamente em alguns instantes.")
            return

        if not self.current_file_name:
            QMessageBox.warning(self, "Aviso", "Nenhum arquivo de log está aberto para salvar uma análise.")
            return

        texto = self.txt_observacao.toPlainText().strip()
        if not texto:
            QMessageBox.warning(self, "Aviso", "O campo de observação está vazio.")
            return
            
        nome_usuario = self.usuario_logado['nome'] if self.usuario_logado else "Local"
        if salvar_observacao(self.current_file_name, texto, tecnico=nome_usuario):
            QMessageBox.information(self, "Sucesso", "Observação salva com sucesso no banco de dados.")
            self.status_bar.setText("Observação salva.")
        else:
            QMessageBox.critical(self, "Erro de Banco de Dados", "Não foi possível salvar a observação. O banco de dados pode estar bloqueado por outro usuário. Tente novamente.")
            
    def purge_old_backups(self, days=14):
        # ... (código existente, sem alterações)
        base_dir = self.config.get("backup_local_dir")
        if not base_dir or not os.path.exists(base_dir): return
        cutoff_ts = time.time() - (days * 24 * 60 * 60)
        for root, dirs, files in os.walk(base_dir):
            for file in files:
                path = os.path.join(root, file)
                try:
                    if os.path.getmtime(path) < cutoff_ts:
                        os.remove(path)
                except OSError: pass
        for root, dirs, files in os.walk(base_dir, topdown=False):
            if not dirs and not files:
                try: os.rmdir(root)
                except OSError: pass
                
    def _maybe_purge_backups(self):
        # ... (código existente, sem alterações)
        today = datetime.now().strftime("%Y-%m-%d")
        if self._last_purge_date == today: return
        self._last_purge_date = today
        self.purge_old_backups(days=14)
        
        

        
    def init_tray(self):
        # ... (código existente, sem alterações)
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon('icon.ico'))
        menu = QMenu()
        menu.addAction(QAction("Abrir", self, triggered=self.showNormal))
        menu.addAction(QAction("Sair", self, triggered=QApplication.quit))
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(lambda r: self.showNormal() if r == QSystemTrayIcon.DoubleClick else None)
        self.tray_icon.show()
        
    def fazer_logout(self):
        """Prepara a aplicação para voltar à tela de login"""
        self.logout_solicitado = True
        self.close()

    def closeEvent(self, e):
        if self.logout_solicitado:
            e.accept()  # Permite que a janela feche para o loop do __main__ reiniciar
        elif self.config.get("keep_in_tray", True) and self.tray_icon.isVisible():
            self.hide()
            self.tray_icon.showMessage("ICT Suite", "Minimizado na bandeja", QSystemTrayIcon.Information, 1000)
            e.ignore()
        else:
            QApplication.quit()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    while True:
        # Evita que o app morra ao fechar o dialog de login
        app.setQuitOnLastWindowClosed(False)
        
        dialog_login = LoginDialog()
        if dialog_login.exec_() == QDialog.Accepted:
            # O usuário logou com sucesso. Libera o fechamento de janelas novamente.
            app.setQuitOnLastWindowClosed(True)

            # Instancia a janela principal passando os dados do login
            win = MainApp(usuario_logado=dialog_login.usuario_logado, start_minimized="--minimized" in sys.argv)
            
            app.exec_() # O aplicativo fica rodando aqui até a janela ser fechada
            
            # Verifica como a janela foi fechada
            if hasattr(win, 'logout_solicitado') and win.logout_solicitado:
                # Se foi via botão de logout, o loop reinicia e volta pro login
                continue 
            else:
                # Se clicou no X da janela principal, quebra o loop e encerra
                break 
        else:
            # Se fechou a tela de login no X ou cancelou, encerra
            break 
            
    sys.exit()