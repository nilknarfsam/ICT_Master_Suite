import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QListWidget, QTableWidget, QTableWidgetItem, QTextEdit, QFileDialog, QDialog, QLabel,
    QHeaderView, QMessageBox, QSizePolicy, QFrame
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon

def detectar_tipo_log(conteudo, nome_arquivo):
    if nome_arquivo.lower().endswith(('.csv', '.dcl')):
        linhas = [l.strip() for l in conteudo.splitlines() if l.strip()]
        if linhas and linhas[0].count(",") >= 4:
            return "TRI"
    return "AGILENT"

def tentar_ler_arquivo(filepath):
    for enc in ['utf-8', 'utf-16', 'latin1']:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                return f.read()
        except Exception:
            continue
    return None

class ConfigDiretoriosDialog(QDialog):
    def __init__(self, dir_agilent, dir_tri, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuração de Diretórios")
        self.setModal(True)
        self.dir_agilent_original = dir_agilent
        self.dir_tri_original = dir_tri

        self.edit_agilent = QLineEdit(dir_agilent)
        self.edit_tri = QLineEdit(dir_tri)
        btn_browse_agilent = QPushButton("Browser")
        btn_browse_tri = QPushButton("Browser")
        btn_browse_agilent.clicked.connect(self.browse_agilent)
        btn_browse_tri.clicked.connect(self.browse_tri)

        layout = QVBoxLayout(self)
        layout_agilent = QHBoxLayout()
        layout_agilent.addWidget(QLabel("LOG do ICT Agilent:"))
        layout.addLayout(layout_agilent)
        layout_campo_agilent = QHBoxLayout()
        layout_campo_agilent.addWidget(self.edit_agilent)
        layout_campo_agilent.addWidget(btn_browse_agilent)
        layout.addLayout(layout_campo_agilent)

        layout.addSpacing(12)
        layout_tri = QHBoxLayout()
        layout_tri.addWidget(QLabel("LOG do ICT TRI:"))
        layout.addLayout(layout_tri)
        layout_campo_tri = QHBoxLayout()
        layout_campo_tri.addWidget(self.edit_tri)
        layout_campo_tri.addWidget(btn_browse_tri)
        layout.addLayout(layout_campo_tri)

        layout.addSpacing(24)
        btn_salvar = QPushButton("Salvar")
        btn_salvar.clicked.connect(self.accept)
        btn_fechar = QPushButton("Fechar")
        btn_fechar.clicked.connect(self.on_close)
        layout_botoes = QHBoxLayout()
        layout_botoes.addWidget(btn_salvar)
        layout_botoes.addWidget(btn_fechar)
        layout.addLayout(layout_botoes)
        self.setMinimumWidth(540)
        self.salvou = False

    def browse_agilent(self):
        dir = QFileDialog.getExistingDirectory(self, "Escolha o diretório para LOG do ICT Agilent", self.edit_agilent.text())
        if dir:
            self.edit_agilent.setText(dir)

    def browse_tri(self):
        dir = QFileDialog.getExistingDirectory(self, "Escolha o diretório para LOG do ICT TRI", self.edit_tri.text())
        if dir:
            self.edit_tri.setText(dir)

    def accept(self):
        self.salvou = True
        super().accept()

    def on_close(self):
        if (self.edit_agilent.text() != self.dir_agilent_original or self.edit_tri.text() != self.dir_tri_original):
            resposta = QMessageBox.question(
                self, "Salvar alterações?",
                "Você fez modificações. Deseja salvar as alterações?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                QMessageBox.Cancel
            )
            if resposta == QMessageBox.Yes:
                self.salvou = True
                super().accept()
            elif resposta == QMessageBox.No:
                self.salvou = False
                super().reject()
            else:
                return
        else:
            self.salvou = False
            super().reject()

    def get_diretorios(self):
        return self.edit_agilent.text(), self.edit_tri.text()

class FinderLogsApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Análise Técnica - Logs ICT - V1.0")
        self.setGeometry(100, 100, 1200, 760)
        self.diretorios = [
            r"\\147.1.0.95\teste_ict\ict02\defeitos_tri",  # TRI
            r"\\147.1.0.95\teste_ict\ict01\defeitos"       # Agilent
        ]
        self.arquivos_encontrados = {}
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(5)

        # Linha de busca + botão de configuração
        barra_busca = QHBoxLayout()
        self.input_serial = QLineEdit()
        self.input_serial.setMaxLength(23)
        self.input_serial.setPlaceholderText("Serial (10 caracteres) ou (23 caracteres)...")
        barra_busca.addWidget(self.input_serial)
        btn_buscar = QPushButton("Buscar")
        btn_buscar.clicked.connect(self.buscar_logs)
        barra_busca.addWidget(btn_buscar)
        btn_limpar = QPushButton("Limpar")
        btn_limpar.clicked.connect(self.limpar_busca)
        barra_busca.addWidget(btn_limpar)
        btn_config = QPushButton("⚙️ Diretórios")
        btn_config.clicked.connect(self.abrir_config_diretorios)
        barra_busca.addWidget(btn_config)
        layout.addLayout(barra_busca)
        self.input_serial.returnPressed.connect(self.buscar_logs)

        # Áreas principais divididas horizontalmente (colunas)
        main_areas = QHBoxLayout()
        main_areas.setSpacing(10)

        # Coluna 1: Lista de arquivos encontrados + título
        left_col = QVBoxLayout()
        lbl_logs = QLabel("Logs encontrados")
        lbl_logs.setStyleSheet("font-weight: bold; font-size: 14px;")
        left_col.addWidget(lbl_logs)
        self.list_logs = QListWidget()
        self.list_logs.setMinimumWidth(330)
        self.list_logs.itemSelectionChanged.connect(self.visualizar_arquivo)
        left_col.addWidget(self.list_logs)
        main_areas.addLayout(left_col, 1)

        # Coluna 2: Conteúdo do arquivo aberto + título dinâmico
        center_col = QVBoxLayout()
        self.lbl_tipo_log = QLabel("Conteúdo do arquivo")
        self.lbl_tipo_log.setStyleSheet("font-weight: bold; font-size: 14px;")
        center_col.addWidget(self.lbl_tipo_log)
        self.text_file_content = QTextEdit()
        self.text_file_content.setReadOnly(True)
        self.text_file_content.setMinimumWidth(430)
        center_col.addWidget(self.text_file_content)
        main_areas.addLayout(center_col, 2)

        layout.addLayout(main_areas, 8)

        # Linha separadora
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)

        # Rodapé: Tabela TRI dos componentes
        rodape = QVBoxLayout()
        self.lbl_tabela = QLabel("Tabela de componentes")
        self.lbl_tabela.setStyleSheet("font-weight: bold; font-size: 14px;")
        rodape.addWidget(self.lbl_tabela)
        self.table_tri = QTableWidget()
        self.table_tri.setColumnCount(13)
        self.table_tri.setHorizontalHeaderLabels([
            "Step", "Part name", "Actual", "Standard", "High lim", "Low lim",
            "Mode", "Type", "High pin", "Low pin", "Location", "Measure", "Result"
        ])
        self.table_tri.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_tri.setMinimumHeight(180)
        rodape.addWidget(self.table_tri)
        layout.addLayout(rodape, 3)

        # Estado inicial: limpa a tabela
        self.table_tri.setRowCount(0)
        self.lbl_tabela.setVisible(False)
        self.table_tri.setVisible(False)

         # Rodapé de assinatura
        assinatura = QLabel("Desenvolvido por Franklin Carvalho – 2025 ")
        assinatura.setStyleSheet("color: gray; font-size: 11px; font-style: italic;")
        assinatura.setAlignment(Qt.AlignRight)  # Ou Qt.AlignCenter
        layout.addWidget(assinatura)

    def buscar_logs(self):
        termo = self.input_serial.text().strip()
        if len(termo) not in (10, 23):
            QMessageBox.warning(
                self,
                "Serial inválido",
                "O serial deve conter **exatamente 10 ou 23 caracteres**.\n\n"
                "Exemplo válido: ABCDE12345 (10) ou 12345678901234567890123 (23)"
            )
            return
        arquivos = []
        for diretorio in self.diretorios:
            for root, dirs, files in os.walk(diretorio):
                for file in files:
                    if (file.lower().endswith((".csv", ".dcl", ".txt"))) and termo in file:
                        arquivos.append(os.path.join(root, file))
        self.list_logs.clear()
        self.arquivos_encontrados.clear()
        for arquivo in arquivos:
            nome = os.path.basename(arquivo)
            self.list_logs.addItem(nome)
            self.arquivos_encontrados[nome] = arquivo
        self.text_file_content.clear()
        self.table_tri.setRowCount(0)
        self.lbl_tabela.setVisible(False)
        self.table_tri.setVisible(False)
        self.lbl_tipo_log.setText("Conteúdo do arquivo")
        if not arquivos:
            QMessageBox.information(self, "Resultado", "Nenhum arquivo encontrado.")

    def limpar_busca(self):
        self.input_serial.clear()
        self.list_logs.clear()
        self.text_file_content.clear()
        self.table_tri.setRowCount(0)
        self.lbl_tabela.setVisible(False)
        self.table_tri.setVisible(False)
        self.lbl_tipo_log.setText("Conteúdo do arquivo")

    def visualizar_arquivo(self):
        selected = self.list_logs.currentItem()
        if not selected:
            self.text_file_content.clear()
            self.table_tri.setRowCount(0)
            self.lbl_tabela.setVisible(False)
            self.table_tri.setVisible(False)
            self.lbl_tipo_log.setText("Conteúdo do arquivo")
            return
        nome_arquivo = selected.text()
        arquivo = self.arquivos_encontrados.get(nome_arquivo)
        conteudo = tentar_ler_arquivo(arquivo)
        if not conteudo:
            self.text_file_content.setPlainText("Não foi possível ler o arquivo.")
            self.table_tri.setRowCount(0)
            self.lbl_tabela.setVisible(False)
            self.table_tri.setVisible(False)
            self.lbl_tipo_log.setText("Conteúdo do arquivo")
            return

        # Descobre tipo de log e ajusta título do centro
        tipo = detectar_tipo_log(conteudo, nome_arquivo)
        if tipo == "TRI":
            self.lbl_tipo_log.setText("LOG do ICT TRI")
        else:
            self.lbl_tipo_log.setText("LOG do ICT AGILENT")

        self.text_file_content.setPlainText(conteudo)

        # Se for TRI, monta tabela de componentes válidos
        if tipo == "TRI":
            linhas = conteudo.splitlines()[1:]  # pula header
            self.table_tri.setRowCount(0)
            for linha in linhas:
                if not linha.strip():
                    continue
                dados = [v.strip() for v in linha.split(",")]
                # Para "componentes", filtra linhas que tenham o nome do componente no campo 1 (Part name)
                if len(dados) >= 2 and dados[1] and not dados[1].lower().startswith("open"): # "Open" é caso de short
                    while len(dados) < 13:
                        dados.append("")
                    row = self.table_tri.rowCount()
                    self.table_tri.insertRow(row)
                    for i, v in enumerate(dados[:13]):
                        self.table_tri.setItem(row, i, QTableWidgetItem(v))
            # Se não houver componentes, limpa a tabela
            if self.table_tri.rowCount() == 0:
                self.lbl_tabela.setVisible(False)
                self.table_tri.setVisible(False)
            else:
                self.lbl_tabela.setVisible(True)
                self.table_tri.setVisible(True)
        else:
            self.table_tri.setRowCount(0)
            self.lbl_tabela.setVisible(False)
            self.table_tri.setVisible(False)

    def abrir_config_diretorios(self):
        dir_tri = self.diretorios[0] if len(self.diretorios) > 0 else ""
        dir_agilent = self.diretorios[1] if len(self.diretorios) > 1 else ""
        dlg = ConfigDiretoriosDialog(dir_agilent, dir_tri, self)
        result = dlg.exec_()
        if dlg.salvou:
            novo_dir_agilent, novo_dir_tri = dlg.get_diretorios()
            self.diretorios = [novo_dir_tri, novo_dir_agilent]
            QMessageBox.information(self, "Configuração", "Diretórios salvos:\nAgilent: {}\nTRI: {}".format(novo_dir_agilent, novo_dir_tri))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon("icon.ico"))  # <- ESTA LINHA ADICIONA O ICONE
    window = FinderLogsApp()
    window.show()
    sys.exit(app.exec_())
