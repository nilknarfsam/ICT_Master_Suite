import sys
import os
import json
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QListWidget, QTableWidget, QTableWidgetItem, QTextEdit, QFileDialog, QDialog, QLabel,
    QHeaderView, QMessageBox, QFrame, QStatusBar, QProgressBar
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QIcon

# Nome do arquivo de configuração para salvar os diretórios
CONFIG_FILE = "config_ict.json"

def carregar_config():
    """Carrega diretórios do arquivo JSON ou retorna o padrão."""
    padrao = {
        "tri": r"\\147.1.0.95\teste_ict\ict02\defeitos_tri",
        "agilent": r"\\147.1.0.95\teste_ict\ict01\defeitos"
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except:
            return padrao
    return padrao

def salvar_config(diretorios):
    """Salva os diretórios no arquivo JSON."""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(diretorios, f, indent=4)
    except Exception as e:
        print(f"Erro ao salvar config: {e}")

def detectar_tipo_log(conteudo, nome_arquivo):
    if nome_arquivo.lower().endswith(('.csv', '.dcl')):
        linhas = [l.strip() for l in conteudo.splitlines() if l.strip()]
        # Verifica se a primeira linha tem estrutura de CSV do TRI
        if linhas and linhas[0].count(",") >= 4:
            return "TRI"
    return "AGILENT"

def tentar_ler_arquivo(filepath):
    for enc in ['utf-8', 'utf-16', 'latin1', 'cp1252']:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                return f.read()
        except Exception:
            continue
    return None

# --- WORKER THREAD PARA NÃO TRAVAR A TELA ---
class BuscaThread(QThread):
    # Sinais para comunicar com a interface principal
    arquivo_encontrado = pyqtSignal(str, str) # nome, caminho
    finalizado = pyqtSignal(int) # quantidade encontrada
    erro = pyqtSignal(str)

    def __init__(self, termo, diretorios):
        super().__init__()
        self.termo = termo
        self.diretorios = diretorios
        self.rodando = True

    def run(self):
        count = 0
        try:
            for diretorio in self.diretorios:
                if not os.path.exists(diretorio):
                    continue
                
                # Walk percorre todas as subpastas
                for root, dirs, files in os.walk(diretorio):
                    if not self.rodando: break # Permite cancelar a busca
                    
                    for file in files:
                        if (file.lower().endswith((".csv", ".dcl", ".txt"))) and self.termo in file:
                            caminho_completo = os.path.join(root, file)
                            self.arquivo_encontrado.emit(file, caminho_completo)
                            count += 1
            self.finalizado.emit(count)
        except Exception as e:
            self.erro.emit(str(e))

    def parar(self):
        self.rodando = False

# --- DIALOG DE CONFIGURAÇÃO ---
class ConfigDiretoriosDialog(QDialog):
    def __init__(self, dir_agilent, dir_tri, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuração de Diretórios")
        self.setModal(True)
        self.dir_agilent_original = dir_agilent
        self.dir_tri_original = dir_tri
        self.salvou = False
        self.novos_diretorios = {}

        self.edit_agilent = QLineEdit(dir_agilent)
        self.edit_tri = QLineEdit(dir_tri)
        btn_browse_agilent = QPushButton("...")
        btn_browse_agilent.setFixedWidth(40)
        btn_browse_tri = QPushButton("...")
        btn_browse_tri.setFixedWidth(40)

        btn_browse_agilent.clicked.connect(self.browse_agilent)
        btn_browse_tri.clicked.connect(self.browse_tri)

        layout = QVBoxLayout(self)
        
        # Grupo Agilent
        layout.addWidget(QLabel("<b>Diretório LOG Agilent:</b>"))
        h1 = QHBoxLayout()
        h1.addWidget(self.edit_agilent)
        h1.addWidget(btn_browse_agilent)
        layout.addLayout(h1)

        layout.addSpacing(10)

        # Grupo TRI
        layout.addWidget(QLabel("<b>Diretório LOG TRI:</b>"))
        h2 = QHBoxLayout()
        h2.addWidget(self.edit_tri)
        h2.addWidget(btn_browse_tri)
        layout.addLayout(h2)

        layout.addSpacing(20)

        # Botões
        btn_salvar = QPushButton("Salvar e Fechar")
        btn_salvar.clicked.connect(self.validar_e_salvar)
        layout.addWidget(btn_salvar)

        self.setMinimumWidth(600)

    def browse_agilent(self):
        d = QFileDialog.getExistingDirectory(self, "Selecionar Pasta Agilent", self.edit_agilent.text())
        if d: self.edit_agilent.setText(d)

    def browse_tri(self):
        d = QFileDialog.getExistingDirectory(self, "Selecionar Pasta TRI", self.edit_tri.text())
        if d: self.edit_tri.setText(d)

    def validar_e_salvar(self):
        self.salvou = True
        self.novos_diretorios = {
            "agilent": self.edit_agilent.text(),
            "tri": self.edit_tri.text()
        }
        super().accept()

# --- APLICAÇÃO PRINCIPAL ---
class FinderLogsApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Análise Técnica - Logs ICT - V2.0")
        self.setGeometry(100, 100, 1200, 800)
        
        # Carrega configuração do JSON ou usa padrão
        self.config = carregar_config()
        self.arquivos_encontrados = {}
        self.thread_busca = None
        
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # === TOPO: BUSCA E CONFIG ===
        top_frame = QFrame()
        top_frame.setFrameShape(QFrame.StyledPanel)
        top_layout = QHBoxLayout(top_frame)
        
        self.input_serial = QLineEdit()
        self.input_serial.setMaxLength(23)
        self.input_serial.setPlaceholderText("Digite o Serial (10 ou 23 dígitos)...")
        self.input_serial.setMinimumHeight(30)
        self.input_serial.setStyleSheet("font-size: 14px; padding: 2px;")
        
        self.btn_buscar = QPushButton("🔍 Buscar")
        self.btn_buscar.setMinimumHeight(30)
        self.btn_buscar.clicked.connect(self.iniciar_busca)
        
        btn_limpar = QPushButton("Limpar")
        btn_limpar.clicked.connect(self.limpar_tudo)
        
        btn_config = QPushButton("⚙️ Config")
        btn_config.clicked.connect(self.abrir_config)

        top_layout.addWidget(self.input_serial, 2)
        top_layout.addWidget(self.btn_buscar)
        top_layout.addWidget(btn_limpar)
        top_layout.addWidget(btn_config)
        
        layout.addWidget(top_frame)
        self.input_serial.returnPressed.connect(self.iniciar_busca)

        # === MEIO: LISTA E CONTEÚDO ===
        split_layout = QHBoxLayout()
        
        # Esquerda: Lista
        left_layout = QVBoxLayout()
        left_layout.addWidget(QLabel("<b>Arquivos Encontrados:</b>"))
        self.list_logs = QListWidget()
        self.list_logs.setFixedWidth(300)
        self.list_logs.itemSelectionChanged.connect(self.carregar_arquivo_selecionado)
        left_layout.addWidget(self.list_logs)
        split_layout.addLayout(left_layout)

        # Centro: Texto do Log
        center_layout = QVBoxLayout()
        self.lbl_tipo_log = QLabel("<b>Conteúdo do Arquivo:</b>")
        center_layout.addWidget(self.lbl_tipo_log)
        self.text_file_content = QTextEdit()
        self.text_file_content.setReadOnly(True)
        self.text_file_content.setStyleSheet("font-family: Consolas, Monospace; font-size: 12px;")
        center_layout.addWidget(self.text_file_content)
        split_layout.addLayout(center_layout)

        layout.addLayout(split_layout, stretch=2)

        # === RODAPÉ: TABELA E STATUS ===
        self.lbl_tabela = QLabel("<b>Detalhamento de Defeitos (TRI):</b>")
        layout.addWidget(self.lbl_tabela)
        
        self.table_tri = QTableWidget()
        colunas = ["Step", "Part name", "Actual", "Standard", "High lim", "Low lim",
                   "Mode", "Type", "High pin", "Low pin", "Location", "Measure", "Result"]
        self.table_tri.setColumnCount(len(colunas))
        self.table_tri.setHorizontalHeaderLabels(colunas)
        self.table_tri.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_tri.setAlternatingRowColors(True)
        self.table_tri.setMinimumHeight(200)
        layout.addWidget(self.table_tri)

        # Barra de Status e Progresso
        status_layout = QHBoxLayout()
        self.status_bar = QLabel("Pronto.")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0) # Indeterminado
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedWidth(200)
        
        assinatura = QLabel("Dev: Franklin Carvalho – 2025")
        assinatura.setStyleSheet("color: gray; font-size: 10px;")
        
        status_layout.addWidget(self.status_bar)
        status_layout.addWidget(self.progress_bar)
        status_layout.addStretch()
        status_layout.addWidget(assinatura)
        
        layout.addLayout(status_layout)

        # Estado inicial
        self.ocultar_tabela()

    def ocultar_tabela(self):
        self.lbl_tabela.setVisible(False)
        self.table_tri.setVisible(False)

    def iniciar_busca(self):
        termo = self.input_serial.text().strip()
        if len(termo) not in (10, 23):
            QMessageBox.warning(self, "Serial Inválido", "O serial deve ter exatamente 10 ou 23 caracteres.")
            return

        # Prepara UI
        self.limpar_interface_busca()
        self.status_bar.setText(f"Buscando por '{termo}' na rede...")
        self.progress_bar.setVisible(True)
        self.btn_buscar.setEnabled(False) # Evita duplo clique

        # Prepara diretórios (ordem: TRI, Agilent)
        dirs = [self.config["tri"], self.config["agilent"]]

        # Inicia Thread
        self.thread_busca = BuscaThread(termo, dirs)
        self.thread_busca.arquivo_encontrado.connect(self.adicionar_arquivo_na_lista)
        self.thread_busca.finalizado.connect(self.fim_busca)
        self.thread_busca.erro.connect(self.erro_busca)
        self.thread_busca.start()

    def adicionar_arquivo_na_lista(self, nome, caminho):
        self.list_logs.addItem(nome)
        self.arquivos_encontrados[nome] = caminho

    def fim_busca(self, total):
        self.progress_bar.setVisible(False)
        self.btn_buscar.setEnabled(True)
        if total == 0:
            self.status_bar.setText("Nenhum arquivo encontrado.")
            QMessageBox.information(self, "Busca", "Nenhum log encontrado para este serial.")
        else:
            self.status_bar.setText(f"Busca finalizada. {total} arquivos encontrados.")

    def erro_busca(self, msg):
        self.progress_bar.setVisible(False)
        self.btn_buscar.setEnabled(True)
        self.status_bar.setText("Erro na busca.")
        QMessageBox.critical(self, "Erro", f"Erro ao acessar diretórios:\n{msg}")

    def limpar_tudo(self):
        self.input_serial.clear()
        self.limpar_interface_busca()
        self.status_bar.setText("Pronto.")

    def limpar_interface_busca(self):
        self.list_logs.clear()
        self.arquivos_encontrados.clear()
        self.text_file_content.clear()
        self.table_tri.setRowCount(0)
        self.ocultar_tabela()
        self.lbl_tipo_log.setText("Conteúdo do Arquivo")

    def carregar_arquivo_selecionado(self):
        item = self.list_logs.currentItem()
        if not item: return
        
        nome = item.text()
        caminho = self.arquivos_encontrados.get(nome)
        
        conteudo = tentar_ler_arquivo(caminho)
        if not conteudo:
            self.text_file_content.setText("❌ Erro ao ler arquivo (encoding ou permissão).")
            return

        tipo = detectar_tipo_log(conteudo, nome)
        self.lbl_tipo_log.setText(f"Log: {tipo} - {nome}")
        self.text_file_content.setPlainText(conteudo)

        if tipo == "TRI":
            self.popular_tabela_tri(conteudo)
        else:
            self.ocultar_tabela()

    def popular_tabela_tri(self, conteudo):
        linhas = conteudo.splitlines()
        dados_relevantes = []
        
        # Pula cabeçalho se houver e filtra linhas vazias
        for linha in linhas:
            linha = linha.strip()
            if not linha: continue
            
            partes = [p.strip() for p in linha.split(',')]
            
            # Lógica simples para identificar linhas de medição válidas
            # Normalmente TRI tem muitas colunas, verificamos se tem pelo menos 5
            # E evitamos linhas que sejam apenas cabeçalhos repetidos
            if len(partes) > 5 and partes[0].isdigit(): 
                dados_relevantes.append(partes)

        if not dados_relevantes:
            self.ocultar_tabela()
            return

        self.lbl_tabela.setVisible(True)
        self.table_tri.setVisible(True)
        self.table_tri.setRowCount(len(dados_relevantes))

        for row_idx, row_data in enumerate(dados_relevantes):
            # Garante que tem 13 colunas para não dar erro de índice
            while len(row_data) < 13:
                row_data.append("")
                
            for col_idx in range(13):
                item = QTableWidgetItem(row_data[col_idx])
                item.setTextAlignment(Qt.AlignCenter)
                self.table_tri.setItem(row_idx, col_idx, item)

    def abrir_config(self):
        dlg = ConfigDiretoriosDialog(self.config["agilent"], self.config["tri"], self)
        if dlg.exec_():
            self.config = dlg.novos_diretorios
            salvar_config(self.config)
            self.status_bar.setText("Configurações salvas.")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    # app.setWindowIcon(QIcon("icon.ico")) 
    window = FinderLogsApp()
    window.show()
    sys.exit(app.exec_())