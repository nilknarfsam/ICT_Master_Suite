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
    QAbstractItemView, QRadioButton, QButtonGroup, QInputDialog, QListWidgetItem, QComboBox
)
from PyQt5.QtCore import Qt, QTimer, QDir
from PyQt5.QtGui import QColor, QFont, QIcon
from PyQt5.QtChart import QChart, QChartView, QBarSet, QBarSeries, QBarCategoryAxis, QValueAxis, QPieSeries, QPieSlice

from models import (carregar_config, salvar_config, salvar_falha_db, salvar_observacao, ler_observacao, 
                    obter_ultimas_analises, obter_estatisticas_progresso, limpar_analises_db, verificar_conexao_db, 
                    limpar_cache_local, buscar_historico_serial, validar_login, listar_usuarios, 
                    cadastrar_usuario, deletar_usuario, atualizar_usuario, adicionar_modelo, listar_modelos, adicionar_solucao_wiki, buscar_solucoes_wiki, editar_modelo, gerar_relatorio_excel)
from threads import BuscaThread, FileLoaderThread, DashboardThread
import updater

def get_resource_path(relative_path):
    """
    Retorna o caminho absoluto do recurso, compatível com PyInstaller --onefile
    """
    import sys
    import os
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

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
        
        self.chk_lembrar = QCheckBox("Manter conectado nesta máquina")
        layout.addWidget(self.chk_lembrar)
        
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
            
            from models import carregar_config, salvar_config
            config = carregar_config()
            config["lembrar_login"] = self.chk_lembrar.isChecked()
            config["ultimo_login"] = login if self.chk_lembrar.isChecked() else ""
            salvar_config(config)
            
            self.accept()
        else:
            QMessageBox.critical(self, "Acesso Negado", "Usuário ou senha inválidos.")

class DialogNovaSolucao(QDialog):
    def __init__(self, parent=None, modelo_nome=""):
        super().__init__(parent)
        self.setWindowTitle(f"Nova Solução - Modelo: {modelo_nome}")
        self.setFixedSize(500, 400)
        
        layout = QVBoxLayout(self)
        
        # Fase
        layout.addWidget(QLabel("Fase de Teste:"))
        self.combo_fase = QComboBox()
        self.combo_fase.addItems(["ICT", "FCT"])
        layout.addWidget(self.combo_fase)
        
        # Sintoma
        layout.addWidget(QLabel("Sintoma / Defeito (Resumo):"))
        self.input_sintoma = QLineEdit()
        self.input_sintoma.setPlaceholderText("Ex: Equipamento não liga / Led não acende")
        layout.addWidget(self.input_sintoma)
        
        # Solução
        layout.addWidget(QLabel("Solução Aplicada (Detalhes):"))
        self.text_solucao = QTextEdit()
        self.text_solucao.setPlaceholderText("Descreva os passos realizados, ex: Troca do capacitor C12, ressolda no pino 3 do U4...")
        layout.addWidget(self.text_solucao)
        
        # Botões
        h_btn = QHBoxLayout()
        h_btn.addStretch()
        
        btn_salvar = QPushButton("💾 Salvar")
        btn_salvar.setStyleSheet("background-color: #28a745; color: white; font-weight: bold; padding: 5px 15px;")
        btn_salvar.clicked.connect(self.aceitar)
        
        btn_cancelar = QPushButton("❌ Cancelar")
        btn_cancelar.setStyleSheet("background-color: #dc3545; color: white; padding: 5px 15px;")
        btn_cancelar.clicked.connect(self.reject)
        
        h_btn.addWidget(btn_salvar)
        h_btn.addWidget(btn_cancelar)
        layout.addLayout(h_btn)
        
    def aceitar(self):
        # Validação básica
        if not self.input_sintoma.text().strip() or not self.text_solucao.toPlainText().strip():
            QMessageBox.warning(self, "Aviso", "Preencha o sintoma e a solução.")
            return
        self.accept()

class MainApp(QWidget):
    def __init__(self, usuario_logado=None, start_minimized=False):
        super().__init__()
        self.setWindowTitle("ICT Master Suite - V5.3 (Polished UI)")
        self.setWindowIcon(QIcon(get_resource_path('icon.ico')))
        self.setGeometry(100, 100, 1280, 800)
        self.config = carregar_config()
        
        # --- VERIFICAÇÃO DE ATUALIZAÇÕES (Desativado temporariamente para otimização onedir) ---
        # versao_atual = updater.get_current_version()
        # caminho_rede = self.config.get("caminho_update_rede", "")
        # if updater.verificar_atualizacao(caminho_rede, versao_atual):
        #     resp = QMessageBox.question(self, "Atualização Disponível", 
        #                                 "Uma nova versão do sistema está disponível. Deseja atualizar agora?", 
        #                                 QMessageBox.Yes | QMessageBox.No)
        #     if resp == QMessageBox.Yes:
        #         import sys
        #         caminho_exe_rede = os.path.join(caminho_rede, os.path.basename(sys.argv[0]))
        #         if updater.aplicar_atualizacao(caminho_exe_rede):
        #             sys.exit(0)
        
        # --- CHECAGEM BLOQUEANTE DE BANCO DE DADOS ---
        # Removido para permitir inicialização offline
        
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
        if self.config.get("lembrar_login") and self.config.get("ultimo_login"):
            if not self.usuario_logado:
                from models import obter_usuario_por_login
                usr = obter_usuario_por_login(self.config["ultimo_login"])
                if usr:
                    self.usuario_logado = usr

        self.logout_solicitado = False
        
        # Motor de Sincronização (Store-and-Forward)
        self.timer_sync = QTimer(self)
        self.timer_sync.timeout.connect(self.processar_sincronizacao_background)
        self.timer_sync.start(15000)
        
        self.init_ui()
        self.init_tray()
        self._maybe_purge_backups()
        
        # Removido timer do Dashboard (Substituído por Wiki)
        pass

        self.load_stylesheet()

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
        # ... (código do header existente)
        lbl_header = QLabel("ICT Technical Suite")
        lbl_header.setObjectName("lbl_header")
        h.addWidget(lbl_header)
        h.addStretch()
        
        # Perfil do Usuário e Logout
        nome_usuario = self.usuario_logado['nome'] if self.usuario_logado else "Visitante (Somente Leitura)"
        self.lbl_perfil = QLabel(f"👤 Técnico: {nome_usuario}" if self.usuario_logado else f"👤 {nome_usuario}")
        self.lbl_perfil.setObjectName("lbl_perfil")
        self.lbl_perfil.setStyleSheet("font-weight: bold; color: #333; margin-right: 10px;")
        h.addWidget(self.lbl_perfil)
        
        texto_btn = "Sair" if self.usuario_logado else "Entrar"
        self.btn_logout = QPushButton(texto_btn)
        self.btn_logout.setObjectName("btn_logout")
        self.btn_logout.setStyleSheet("background-color: #dc3545; color: white; border: none; padding: 5px 15px; border-radius: 4px; font-weight: bold;")
        self.btn_logout.clicked.connect(self.fazer_logout)
        h.addWidget(self.btn_logout)
        
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
        # Aba Base de Conhecimento (Wiki)
        self.tab_dash = QWidget()
        self.setup_knowledge_base()
        self.tabs.addTab(self.tab_dash, "� Base de Conhecimento")

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
        is_admin = bool(self.usuario_logado and self.usuario_logado.get('is_admin', False))
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
            ("caminho_logs_tri", "Diretório Local/Rede - Finder TRI:"),
            ("caminho_logs_agilent", "Diretório Local/Rede - Finder Agilent:"),
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
            texto = input_box.text().strip()
            if chave in ["caminho_logs_tri", "caminho_logs_agilent", "backup_local_dir", "caminho_update_rede", "caminho_banco_rede"]:
                # Normaliza para barras simples (forward slashes) que o Windows e JSON interpretam perfeitamente sem 'escaping' duplicado
                texto = texto.replace('\\', '/')
            self.config[chave] = texto
            
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
        
        # Botões de Ação na Tabela
        h_buttons = QHBoxLayout()
        btn_atualizar = QPushButton("Atualizar Lista")
        btn_atualizar.clicked.connect(self.carregar_tabela_usuarios)
        h_buttons.addWidget(btn_atualizar)
        
        btn_editar = QPushButton("✏️ Editar Selecionado")
        btn_editar.clicked.connect(self.editar_usuario_selecionado)
        h_buttons.addWidget(btn_editar)
        
        layout.addLayout(h_buttons)
        
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

    def editar_usuario_selecionado(self):
        selected_items = self.table_usuarios.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Aviso", "Selecione um usuário na tabela para editar.")
            return

        row = selected_items[0].row()
        id_usuario = int(self.table_usuarios.item(row, 0).text())
        nome_atual = self.table_usuarios.item(row, 1).text()
        login_atual = self.table_usuarios.item(row, 2).text()

        dialog = QDialog(self)
        dialog.setWindowTitle("Editar Usuário")
        dialog.setFixedSize(300, 250)
        layout = QVBoxLayout(dialog)

        layout.addWidget(QLabel("Novo Nome:"))
        input_nome = QLineEdit(nome_atual)
        layout.addWidget(input_nome)

        layout.addWidget(QLabel("Novo Login:"))
        input_login = QLineEdit(login_atual)
        layout.addWidget(input_login)

        layout.addWidget(QLabel("Nova Senha (deixe em branco para manter):"))
        input_senha = QLineEdit()
        input_senha.setEchoMode(QLineEdit.Password)
        layout.addWidget(input_senha)

        h_buttons = QHBoxLayout()
        btn_salvar = QPushButton("Salvar")
        btn_salvar.clicked.connect(dialog.accept)
        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.clicked.connect(dialog.reject)
        h_buttons.addWidget(btn_salvar)
        h_buttons.addWidget(btn_cancelar)
        layout.addLayout(h_buttons)

        if dialog.exec_() == QDialog.Accepted:
            novo_nome = input_nome.text().strip()
            novo_login = input_login.text().strip()
            nova_senha = input_senha.text().strip()

            if not novo_nome or not novo_login:
                QMessageBox.warning(self, "Aviso", "Nome e Login não podem ficar vazios.")
                return

            if atualizar_usuario(id_usuario, novo_nome, novo_login, nova_senha if nova_senha else None):
                QMessageBox.information(self, "Sucesso", "Usuário atualizado com sucesso!")
                self.carregar_tabela_usuarios()
            else:
                QMessageBox.critical(self, "Erro", "Erro ao atualizar usuário. O login já pode estar em uso.")

    def setup_history_tab(self):
        layout = QVBoxLayout(self.tab_history)

        # --- BARRA DE FERRAMENTAS ---
        tools_bar = QHBoxLayout()
        tools_bar.addStretch()
        
        # Botão Exportar Excel
        self.btn_exportar_excel = QPushButton("📊 Exportar Relatório Excel")
        self.btn_exportar_excel.setStyleSheet("background-color: #198754; color: white; font-weight: bold; padding: 5px;")
        self.btn_exportar_excel.clicked.connect(self.exportar_dados_excel)
        tools_bar.addWidget(self.btn_exportar_excel)
        
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

        lbl_obs = QLabel("Histórico de Análises:")
        lbl_obs.setObjectName("lbl_obs")
        right_layout.addWidget(lbl_obs)

        self.txt_history_chat = QTextEdit()
        self.txt_history_chat.setReadOnly(True)
        self.txt_history_chat.setObjectName("txt_history_chat")
        right_layout.addWidget(self.txt_history_chat)

        self.txt_history_obs = QTextEdit()
        self.txt_history_obs.setPlaceholderText("Digite sua nova análise aqui...")
        self.txt_history_obs.setFixedHeight(60)
        right_layout.addWidget(self.txt_history_obs)

        btn_salvar = QPushButton("� Adicionar ao Histórico")
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
                import PyQt5.QtWidgets as QtWidgets
                QtWidgets.QMessageBox.warning(self, "Erro de Leitura", f"Não foi possível abrir o arquivo de log no caminho especificado.\nVerifique a conexão de rede.\n\nDetalhe do erro: {str(e)}")
                self.txt_history_log_viewer.setPlainText("")

            # Carrega a observação do banco de dados
            file_name = os.path.basename(file_path)
            observacao = ler_observacao(file_name)
            self.txt_history_chat.setPlainText(observacao)


    def salvar_edicao_historico(self):
        if not self.requerer_login(): return
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

        resultado = salvar_observacao(file_name, texto_analise, tecnico=nome_usuario)
        if resultado == "OFFLINE":
            self.txt_history_obs.clear()
            QMessageBox.warning(self, "Modo Offline", "Rede indisponível. Sua análise foi salva na fila local e será sincronizada assim que a rede voltar!")
            self.status_bar.setText("Aviso: Modo Offline.")
        elif resultado:
            self.txt_history_obs.clear()
            self.txt_history_chat.setPlainText(ler_observacao(file_name))
            QMessageBox.information(self, "Sucesso", "Análise atualizada com sucesso!")
        else:
            QMessageBox.critical(self, "Erro no Banco de Dados", "Não foi possível salvar a análise. O banco de dados pode estar bloqueado por outro usuário. Tente novamente.")

    def exportar_dados_excel(self):
        caminho_destino, _ = QFileDialog.getSaveFileName(self, "Salvar Relatório", "Relatorio_ICT_Master.xlsx", "Excel Files (*.xlsx)")
        
        if caminho_destino:
            if gerar_relatorio_excel(caminho_destino):
                QMessageBox.information(self, "Sucesso", f"O relatório foi exportado com sucesso para:\n{caminho_destino}")
            else:
                QMessageBox.critical(self, "Erro", "Houve um problema ao gerar o relatório Excel. Verifique se o arquivo destino não está aberto ou bloqueado pelo sistema.")

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



    def setup_knowledge_base(self):
        self.tab_dash.setObjectName("tab_knowledge_base")
        layout = QVBoxLayout(self.tab_dash)
        
        splitter = QSplitter(Qt.Horizontal)
        
        # --- Lado Esquerdo: Lista de Modelos (20%) ---
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        left_layout.addWidget(QLabel("🔍 Buscar Modelo:"))
        self.input_busca_modelo = QLineEdit()
        self.input_busca_modelo.setPlaceholderText("Ex: XYZ-1234")
        left_layout.addWidget(self.input_busca_modelo)
        
        self.lista_modelos = QListWidget()
        self.lista_modelos.itemSelectionChanged.connect(self.carregar_solucoes_do_modelo)
        left_layout.addWidget(self.lista_modelos)
        
        self.btn_novo_modelo = QPushButton("➕ Novo Modelo")
        self.btn_novo_modelo.setStyleSheet("background-color: #007bff; color: white; font-weight: bold; padding: 5px;")
        self.btn_novo_modelo.clicked.connect(self.adicionar_novo_modelo_ui)
        left_layout.addWidget(self.btn_novo_modelo)
        
        # Botão de Editar Modelo (Apenas Admin)
        self.btn_editar_modelo = QPushButton("✏️ Editar Modelo")
        self.btn_editar_modelo.setStyleSheet("background-color: #6c757d; color: white; padding: 5px;")
        self.btn_editar_modelo.clicked.connect(self.editar_modelo_selecionado)
        
        is_admin = bool(self.usuario_logado and self.usuario_logado.get('is_admin', False))
        self.btn_editar_modelo.setVisible(is_admin)
        left_layout.addWidget(self.btn_editar_modelo)
        
        splitter.addWidget(left_widget)
        
        # --- Lado Direito: Tabela de Soluções (80%) ---
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # Painel Superior (Filtros)
        painel_filtros = QFrame()
        painel_filtros.setStyleSheet("background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 5px; padding: 5px;")
        filtros_layout = QHBoxLayout(painel_filtros)
        
        filtros_layout.addWidget(QLabel("Fase:"))
        self.bg_fase = QButtonGroup(self)
        self.rb_todos = QRadioButton("Todos")
        self.rb_ict = QRadioButton("ICT")
        self.rb_fct = QRadioButton("FCT")
        
        self.rb_todos.setChecked(True)
        self.bg_fase.addButton(self.rb_todos)
        self.bg_fase.addButton(self.rb_ict)
        self.bg_fase.addButton(self.rb_fct)
        
        self.rb_todos.toggled.connect(self.aplicar_filtros_wiki)
        self.rb_ict.toggled.connect(self.aplicar_filtros_wiki)
        self.rb_fct.toggled.connect(self.aplicar_filtros_wiki)
        
        filtros_layout.addWidget(self.rb_todos)
        filtros_layout.addWidget(self.rb_ict)
        filtros_layout.addWidget(self.rb_fct)
        filtros_layout.addSpacing(20)
        
        filtros_layout.addWidget(QLabel("Busca Sintoma/Defeito:"))
        self.input_busca_sintoma = QLineEdit()
        self.input_busca_sintoma.setPlaceholderText("Ex: capacitor c12 em curto")
        self.input_busca_sintoma.textChanged.connect(self.aplicar_filtros_wiki)
        filtros_layout.addWidget(self.input_busca_sintoma)
        
        right_layout.addWidget(painel_filtros)
        
        # Tabela Wiki
        self.table_solucoes = QTableWidget()
        self.table_solucoes.setColumnCount(5)
        self.table_solucoes.setHorizontalHeaderLabels(["Fase", "Sintoma", "Solução", "Técnico", "Data"])
        self.table_solucoes.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_solucoes.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_solucoes.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_solucoes.setAlternatingRowColors(True)
        right_layout.addWidget(self.table_solucoes)
        
        # Botão Adicionar Solução
        self.btn_nova_solucao = QPushButton("💡 Adicionar Nova Solução")
        self.btn_nova_solucao.setStyleSheet("background-color: #28a745; color: white; font-weight: bold; padding: 8px;")
        self.btn_nova_solucao.clicked.connect(self.adicionar_nova_solucao_ui)
        right_layout.addWidget(self.btn_nova_solucao)
        
        splitter.addWidget(right_widget)
        splitter.setSizes([200, 800])
        layout.addWidget(splitter)
        
        # Popula a lista inicial
        self.carregar_lista_modelos()

    def carregar_lista_modelos(self):
        """Popula o QListWidget com os modelos do banco de dados na inicialização."""
        self.lista_modelos.clear()
        modelos = listar_modelos()
        for m in modelos:
            # Salvar o ID do modelo como userData é uma boa prática
            item = QListWidgetItem(m["nome"])
            item.setData(Qt.UserRole, m["id"])
            self.lista_modelos.addItem(item)
            
    def adicionar_novo_modelo_ui(self):
        if not self.requerer_login(): return
        nome_modelo, ok = QInputDialog.getText(self, "Novo Modelo", "Digite o nome do novo modelo:")
        if ok and nome_modelo.strip():
            nome_modelo_upper = nome_modelo.strip().upper()
            
            # Verifica localmente de forma rápida se já está na lista atual para diminuir queries (opcional, mas bom)
            existente = False
            for i in range(self.lista_modelos.count()):
                if self.lista_modelos.item(i).text().upper() == nome_modelo_upper:
                    existente = True
                    break
            
            if existente:
                QMessageBox.warning(self, "Aviso", f"O modelo '{nome_modelo_upper}' já está cadastrado.")
                return

            novo_id = adicionar_modelo(nome_modelo_upper)
            if novo_id:
                self.carregar_lista_modelos()
                # Seleciona o modelo recém criado
                items = self.lista_modelos.findItems(nome_modelo_upper, Qt.MatchExactly)
                if items:
                    self.lista_modelos.setCurrentItem(items[0])
            else:
                 QMessageBox.warning(self, "Erro", f"Não foi possível adicionar o modelo '{nome_modelo_upper}'. Ele já pode existir.")

    def editar_modelo_selecionado(self):
        currentItem = self.lista_modelos.currentItem()
        if not currentItem:
            QMessageBox.warning(self, "Aviso", "Selecione um modelo na lista para editar.")
            return

        id_modelo = currentItem.data(Qt.UserRole)
        nome_atual = currentItem.text()

        novo_nome, ok = QInputDialog.getText(self, "Editar Modelo", "Novo nome para o modelo:", QLineEdit.Normal, nome_atual)
        if ok and novo_nome.strip():
            novo_nome_upper = novo_nome.strip().upper()
            if novo_nome_upper == nome_atual.upper():
                return # Nenhuma alteração real
                
            if editar_modelo(id_modelo, novo_nome_upper):
                self.carregar_lista_modelos()
                # Tenta re-selecionar
                items = self.lista_modelos.findItems(novo_nome_upper, Qt.MatchExactly)
                if items:
                    self.lista_modelos.setCurrentItem(items[0])
            else:
                QMessageBox.critical(self, "Erro", "Erro ao atualizar o modelo. Verifique se o nome já está em uso.")

    def carregar_solucoes_do_modelo(self):
        """Apenas limpa a busca de texto e chama os filtros para recarregar do zero para o modelo atual"""
        self.input_busca_sintoma.blockSignals(True)
        self.input_busca_sintoma.clear()
        self.input_busca_sintoma.blockSignals(False)
        self.aplicar_filtros_wiki()

    def aplicar_filtros_wiki(self):
        currentItem = self.lista_modelos.currentItem()
        if not currentItem:
            self.table_solucoes.setRowCount(0)
            return
            
        modelo_id = currentItem.data(Qt.UserRole)
        
        self.table_solucoes.setRowCount(0)
        
        fase_filtro = "Todos"
        if self.rb_ict.isChecked(): fase_filtro = "ICT"
        if self.rb_fct.isChecked(): fase_filtro = "FCT"
        busca_texto = self.input_busca_sintoma.text().strip()

        solucoes = buscar_solucoes_wiki(modelo_id, fase_filtro if fase_filtro != "Todos" else None, busca_texto)
        
        if solucoes:
            self.table_solucoes.setRowCount(len(solucoes))
            for row, sol in enumerate(solucoes):
                # ["Fase", "Sintoma", "Solução", "Técnico", "Data"]
                item_fase = QTableWidgetItem(sol["fase"])
                if sol["fase"] == "ICT":
                    item_fase.setForeground(QColor("blue"))
                else:
                    item_fase.setForeground(QColor("purple"))
                item_fase.setTextAlignment(Qt.AlignCenter)
                
                self.table_solucoes.setItem(row, 0, item_fase)
                self.table_solucoes.setItem(row, 1, QTableWidgetItem(sol["sintoma"]))
                self.table_solucoes.setItem(row, 2, QTableWidgetItem(sol["solucao"]))
                self.table_solucoes.setItem(row, 3, QTableWidgetItem(sol["tecnico"] or "Desconhecido"))
                
                # Formata Data
                data_str = sol["data"]
                try:
                    data_dt = datetime.strptime(data_str, '%Y-%m-%d %H:%M:%S')
                    item_data = QTableWidgetItem(data_dt.strftime('%d/%m/%y %H:%M'))
                except ValueError:
                    item_data = QTableWidgetItem(data_str) # Fallback para o formato original
                self.table_solucoes.setItem(row, 4, item_data)
                
            self.table_solucoes.resizeColumnToContents(0) # Fase
            self.table_solucoes.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents) # Sintoma
            self.table_solucoes.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch) # Solução (Expande)
            self.table_solucoes.resizeColumnToContents(3) # Tecnico
            self.table_solucoes.resizeColumnToContents(4) # Data

    def adicionar_nova_solucao_ui(self):
        if not self.requerer_login(): return
        currentItem = self.lista_modelos.currentItem()
        if not currentItem:
            QMessageBox.warning(self, "Aviso", "Selecione um modelo na lista à esquerda antes de adicionar uma solução.")
            return

        modelo_id = currentItem.data(Qt.UserRole)
        modelo_nome = currentItem.text()
        
        dialog = DialogNovaSolucao(self, modelo_nome)
        if dialog.exec_() == QDialog.Accepted:
            fase = dialog.combo_fase.currentText()
            sintoma = dialog.input_sintoma.text().strip()
            solucao = dialog.text_solucao.toPlainText().strip()
            
            # Obtém o autor (logado ou Local)
            autor = self.usuario_logado['nome'] if self.usuario_logado else "Local"
            
            resultado = adicionar_solucao_wiki(modelo_id, fase, sintoma, solucao, autor)
            
            if resultado == "OFFLINE":
                QMessageBox.warning(self, "Modo Offline", "Rede indisponível. Sua solução foi salva na fila local e será sincronizada assim que a rede voltar!")
                self.carregar_solucoes_do_modelo()
            elif resultado:
                QMessageBox.information(self, "Sucesso", "Solução adicionada à Base de Conhecimento!")
                # Recarrega a tabela para mostrar a nova solução
                self.carregar_solucoes_do_modelo()
            else:
                QMessageBox.critical(self, "Erro", "Erro ao salvar a solução no banco de dados.")

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
        lbl_obs_title = QLabel("Histórico de Análises:")
        lbl_obs_title.setObjectName("lbl_obs_title")
        self.l_right.addWidget(lbl_obs_title)

        self.txt_historico_chat = QTextEdit()
        self.txt_historico_chat.setReadOnly(True)
        self.txt_historico_chat.setObjectName("txt_historico_chat")
        self.l_right.addWidget(self.txt_historico_chat)

        self.txt_observacao = QTextEdit()
        self.txt_observacao.setPlaceholderText("Digite sua nova análise aqui...")
        self.txt_observacao.setObjectName("txt_observacao")
        self.txt_observacao.setFixedHeight(60)
        self.l_right.addWidget(self.txt_observacao)

        self.btn_salvar_obs = QPushButton("📤 Adicionar ao Histórico")
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
        
        if not self.config.get("caminho_logs_tri") or not self.config.get("caminho_logs_agilent"):
            QMessageBox.information(self, "Caminhos Não Configurados", 
                                    "Os caminhos para a busca de logs na rede não estão configurados.\n\n"
                                    "Por favor, clique no botão '⚙️ Config' no canto superior direito para definir os diretórios do 'Finder TRI' e 'Finder Agilent'.")
            return

        if len(termo) < 5:
            QMessageBox.warning(self, "Formato Inválido", "Digite pelo menos 5 caracteres do serial para realizar a busca.")
            return

        self.list_logs.clear()
        self.text_raw.clear()
        self.table.setRowCount(0)
        self.lbl_historico_alerta.setVisible(False)
        self.lbl_info.setText("Buscando...")
        self.status_bar.setText("Aguarde...")
        dirs = [self.config.get("caminho_logs_tri", ""), self.config.get("caminho_logs_agilent", ""), self.config.get("backup_local_dir", "")]
    
        if hasattr(self, 'thread_busca') and self.thread_busca.isRunning():
            self.thread_busca.parar()
            self.thread_busca.wait(2000) # Aguarda até 2s para a thread antiga morrer em paz

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
        self.txt_historico_chat.setPlainText(obs_existente)
        
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
        
        # BUGFIX: O Dashboard foi removido na versão nova (substituído pela Wiki).
        # A árvore de Histórico (QFileSystemModel) se auto-atualiza via observador nativo.
        
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
        import PyQt5.QtWidgets as QtWidgets
        QtWidgets.QMessageBox.warning(self, "Erro de Leitura", f"Não foi possível abrir o arquivo de log no caminho especificado.\nVerifique a conexão de rede.\n\nDetalhe do erro: {error_msg}")
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
        if not self.requerer_login(): return
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
        
        resultado = salvar_observacao(self.current_file_name, texto, tecnico=nome_usuario)
        if resultado == "OFFLINE":
            self.txt_observacao.clear()
            QMessageBox.warning(self, "Modo Offline", "Rede indisponível. Sua observação foi salva na fila local e será sincronizada assim que a rede voltar!")
            self.status_bar.setText("Aviso: Modo Offline.")
        elif resultado:
            self.txt_observacao.clear()
            self.txt_historico_chat.setPlainText(ler_observacao(self.current_file_name))
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
        self.tray_icon.setIcon(QIcon(get_resource_path('icon.ico')))
        menu = QMenu()
        menu.addAction(QAction("Abrir", self, triggered=self.showNormal))
        menu.addAction(QAction("Sair", self, triggered=QApplication.quit))
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(lambda r: self.showNormal() if r == QSystemTrayIcon.DoubleClick else None)
        self.tray_icon.show()
        
    def processar_sincronizacao_background(self):
        try:
            from models import sincronizar_fila_offline
            sincronizar_fila_offline()
        except:
            pass

    def fazer_logout(self):
        """Prepara a aplicação para voltar à tela de login ou apenas entra"""
        if not self.usuario_logado:
            self.requerer_login()
            return
            
        self.usuario_logado = None
        self.config["lembrar_login"] = False
        from models import salvar_config
        salvar_config(self.config)
        
        self.lbl_perfil.setText("👤 Visitante (Somente Leitura)")
        self.btn_logout.setText("Entrar")
        
        self.tabs.setTabVisible(self.tabs.indexOf(self.tab_admin), False)
        self.tabs.setTabVisible(self.tabs.indexOf(self.tab_config), False)
        
    def requerer_login(self):
        """Impede o visitante de executar a ação a menos que consiga se logar."""
        if self.usuario_logado:
            return True
            
        dialog = LoginDialog()
        if dialog.exec_() == QDialog.Accepted:
            self.usuario_logado = dialog.usuario_logado
            
            # Atualiza interface
            self.lbl_perfil.setText(f"👤 Técnico: {self.usuario_logado['nome']}")
            self.btn_logout.setText("Sair")
            
            if self.usuario_logado.get('is_admin', False):
                self.tabs.setTabVisible(self.tabs.indexOf(self.tab_admin), True)
                self.tabs.setTabVisible(self.tabs.indexOf(self.tab_config), True)
                
            return True
        return False

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
    import traceback
    def global_exception_handler(exc_type, exc_value, exc_traceback):
        """Captura quedas silenciosas e escreve o erro no crash_log.txt"""
        log_path = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "crash_log.txt")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] CRASH CRÍTICO:\n")
            traceback.print_exception(exc_type, exc_value, exc_traceback, file=f)
    sys.excepthook = global_exception_handler

    app = QApplication(sys.argv)
    win = MainApp(start_minimized="--minimized" in sys.argv)
    sys.exit(app.exec_())