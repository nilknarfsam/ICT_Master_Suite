import os
import sys
import json
import sqlite3
import socket
import time
from datetime import datetime

def get_base_path():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

# --- Constantes ---
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ict_config.json')
DEFAULT_CONFIG = {
    "caminho_logs_tri": "//147.1.0.95/teste_ict/ict02/defeitos_tri",
    "caminho_logs_agilent": "//147.1.0.95/teste_ict/ict01/defeitos",
    "caminho_copia_origem": "//147.1.0.95/teste_ict/ict02",
    "caminho_copia_destino": "//147.1.0.95/teste_ict/ict02/defeitos_tri",
    "caminho_banco_rede": "//147.1.0.95/teste_ict/banco_dados_falhas.db",
    "auto_start_windows": False,
    "keep_in_tray": False,
    "auto_copia_tri_defeitos": True
}

# Inicializa o caminho do banco lendo do config.json se existir.
DB_PATH = "//147.1.0.95/teste_ict/banco_dados_falhas.db"
try:
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            _config_temp = json.load(f)
            if "caminho_banco_rede" in _config_temp:
                DB_PATH = _config_temp["caminho_banco_rede"]
except Exception:
    pass

def servidor_online(caminho, timeout=1):
    """Verifica rapidamente via socket se o IP está acessível para evitar travamentos do Windows."""
    if not caminho.startswith("//") and not caminho.startswith("\\\\"):
        return True # Caminho local
    
    partes = caminho.replace('\\\\', '/').split('/')
    if len(partes) > 2:
        ip_host = partes[2]
        try:
            with socket.create_connection((ip_host, 445), timeout=timeout):
                return True
        except OSError:
            return False
    return True

def conectar_banco(timeout=20, bypass_check=False):
    """Wrapper corporativo para conexões SQLite com trava anti-criação na raiz/local."""
    caminho_db = carregar_config().get("caminho_banco_rede", "//147.1.0.95/teste_ict/banco_dados_falhas.db")
    if not bypass_check:
        if not servidor_online(caminho_db) or not os.path.isfile(caminho_db):
            raise OSError("Banco de dados inacessível na rede devido a queda de conexão.")
            
    return sqlite3.connect(caminho_db, timeout=timeout)

def init_db():
    """Inicializa o banco de dados e cria a tabela 'falhas' se não existir."""
    caminho_db = carregar_config().get("caminho_banco_rede", DB_PATH)
    if not servidor_online(caminho_db):
        return

    try:
        with conectar_banco(timeout=20, bypass_check=True) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS falhas (
                    id TEXT PRIMARY KEY,
                    data_registro TIMESTAMP,
                    data_falha TIMESTAMP,
                    arquivo TEXT,
                    serial TEXT,
                    modelo TEXT,
                    componente TEXT,
                    step TEXT,
                    status_tratativa TEXT
                )
            """)
            
            # Garante a existência das colunas opcionais legadas
            cursor.execute("PRAGMA table_info(falhas)")
            columns = [info[1] for info in cursor.fetchall()]
            if 'observacao' not in columns:
                cursor.execute("ALTER TABLE falhas ADD COLUMN observacao TEXT")
            if 'tecnico' not in columns:
                cursor.execute("ALTER TABLE falhas ADD COLUMN tecnico TEXT")

            # Índices para otimizar as consultas mais comuns
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_data_registro ON falhas (data_registro);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_componente ON falhas (componente);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_arquivo ON falhas (arquivo);")
            conn.commit()
            
    except (sqlite3.OperationalError, OSError) as e:
        print(f"Erro ao inicializar o banco de dados: {e}")

def salvar_falha_db(falha_dict):
    """Salva um dicionário de falha no banco de dados SQLite com retentativa."""
    max_retries = 3
    retry_delay = 1
    for attempt in range(max_retries):
        try:
            with conectar_banco(timeout=20) as conn:
                cursor = conn.cursor()
                sql = """
                    INSERT OR IGNORE INTO falhas (id, data_registro, data_falha, arquivo, serial, modelo, componente, step, status_tratativa)
                    VALUES (:id, :data_registro, :data_falha, :arquivo, :serial, :modelo, :componente, :step, :status_tratativa)
                """
                falha_dict.setdefault("status_tratativa", "ABERTO")
                cursor.execute(sql, falha_dict)
                conn.commit()
                return True
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                return False
    return False

# --- Funções de Configuração (JSON) ---
def carregar_config():
    """Carrega a configuração do arquivo JSON, usando valores padrão para chaves ausentes."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                dados = json.load(f)
                for k, v in DEFAULT_CONFIG.items():
                    dados.setdefault(k, v)
                return dados
        except (json.JSONDecodeError, IOError):
            return DEFAULT_CONFIG.copy()
    
    config_padrao = DEFAULT_CONFIG.copy()
    salvar_config(config_padrao)
    return config_padrao

def salvar_config(dados):
    """Salva a configuração em um arquivo JSON."""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(dados, f, indent=4)
    except IOError:
        pass

# --- Funções de Análise de Log (Parser) ---
def detectar_tipo_log(nome_arquivo):
    """Define se é TRI ou AGILENT baseado na extensão e nome do arquivo."""
    nome = nome_arquivo.lower()
    if nome.endswith((".csv", ".dcl")):
        return "TRI"
    elif nome.endswith(".txt") and "report" in nome:
        return "AGILENT"
    if ".csv" in nome:
        return "TRI"
    return "AGILENT"

def parse_tri_csv(caminho_completo, nome_arquivo, conteudo):
    """Estratégia para ler logs da TRI no padrão CSV (...FAIL.csv / ...PASS.csv)"""
    dados = {"tipo": "TRI", "data": "N/A", "serial": "N/A", "modelo": "N/A", "status": "N/A", "cor": "black"}
    nome_sem_ext = os.path.splitext(nome_arquivo)[0]
    
    if nome_sem_ext[:14].isdigit():
        dt = datetime.strptime(nome_sem_ext[:14], "%Y%m%d%H%M%S")
        dados["data"] = dt.strftime("%d/%m/%Y %H:%M:%S")
        resto = nome_sem_ext[14:]
    else:
        resto = nome_sem_ext

    if nome_sem_ext.upper().endswith("FAIL"):
        dados["status"] = "FAIL"; dados["cor"] = "red"; resto = resto[:-4]
    elif nome_sem_ext.upper().endswith("PASS"):
        dados["status"] = "PASS"; dados["cor"] = "green"; resto = resto[:-4]
    
    dados["serial"] = resto[:10] if len(resto) >= 10 else resto
    if len(resto) > 10: dados["modelo"] = resto[10:].strip("_")
    
    return dados

def parse_tri_txt(caminho_completo, nome_arquivo, conteudo):
    """Estratégia para ler logs antigos da TRI no padrão TXT/LOG (f_...log / p_...log)"""
    dados = {"tipo": "TRI", "data": "N/A", "serial": "N/A", "modelo": "N/A", "status": "N/A", "cor": "black"}
    nome_lower = nome_arquivo.lower()
    nome_sem_ext = os.path.splitext(nome_arquivo)[0]
    
    try:
        ts_mod = os.path.getmtime(caminho_completo)
        dados["data"] = datetime.fromtimestamp(ts_mod).strftime("%d/%m/%Y %H:%M:%S")
    except OSError:
        pass
        
    if nome_lower.startswith("f_") or "fail" in nome_lower:
        dados["status"] = "FAIL"; dados["cor"] = "red"
    elif nome_lower.startswith("p_") or "pass" in nome_lower:
        dados["status"] = "PASS"; dados["cor"] = "green"
        
    resto = nome_sem_ext
    if resto.lower().startswith("f_") or resto.lower().startswith("p_"):
        resto = resto[2:]
        
    dados["serial"] = resto[:10] if len(resto) >= 10 else resto
    if len(resto) > 10: dados["modelo"] = resto[10:].strip("_")
        
    return dados

def parse_agilent_txt(caminho_completo, nome_arquivo, conteudo):
    """Estratégia para ler logs da Agilent (report_out.txt)"""
    dados = {"tipo": "AGILENT", "data": "N/A", "serial": "N/A", "modelo": "N/A", "status": "N/A", "cor": "black"}
    try:
        ts_mod = os.path.getmtime(caminho_completo)
        dados["data"] = datetime.fromtimestamp(ts_mod).strftime("%d/%m/%Y %H:%M:%S")
    except OSError:
        pass
        
    partes = nome_arquivo.split('_')
    if partes: dados["serial"] = partes[0]
    if "report_out_" in nome_arquivo:
         dados["modelo"] = nome_arquivo.split("report_out_")[-1].replace(".txt", "")
    
    conteudo_upper = conteudo.upper()
    if "FAILED" in conteudo_upper or "FAILURE" in conteudo_upper:
        dados["status"] = "FAIL"; dados["cor"] = "red"
    elif "PASSED" in conteudo_upper:
        dados["status"] = "PASS"; dados["cor"] = "green"
    else:
        dados["status"] = "INFO/ABORT"; dados["cor"] = "orange"
        
    return dados

def parse_metadata_inteligente(caminho_completo, nome_arquivo, conteudo):
    """Factory que delega a análise de metadados para a estratégia correta."""
    tipo = detectar_tipo_log(nome_arquivo)
    nome_lower = nome_arquivo.lower()
    
    try:
        if tipo == "TRI":
            if nome_lower.endswith(".csv"):
                return parse_tri_csv(caminho_completo, nome_arquivo, conteudo)
            else:
                return parse_tri_txt(caminho_completo, nome_arquivo, conteudo)
        elif tipo == "AGILENT":
            return parse_agilent_txt(caminho_completo, nome_arquivo, conteudo)
    except Exception as e:
        print(f"Erro no Factory do Parser: {e}")
        
    return {"tipo": tipo, "data": "N/A", "serial": "N/A", "modelo": "N/A", "status": "UNKNOWN", "cor": "black"}

# Inicializa o banco de dados na importação do módulo
init_db()