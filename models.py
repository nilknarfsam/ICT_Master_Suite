import os
import sys
import json
import sqlite3
import socket
import time
import hashlib
from datetime import datetime
import collections
import pandas as pd
import ctypes

def get_base_path():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

# --- Constantes ---
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ict_config.json')
DEFAULT_CONFIG = {
    "caminho_logs_tri": "//147.1.0.95/teste_ict/ict02",
    "caminho_logs_agilent": "//147.1.0.95/teste_ict/ict01/defeitos",
    "backup_local_dir": os.path.join(get_base_path(), "backup_local").replace('\\', '/'),
    "caminho_update_rede": "//147.1.0.95/teste_ict/app_updates",
    "caminho_banco_rede": "//147.1.0.95/teste_ict/banco_dados_falhas.db",
    "auto_start_windows": False,
    "dias_retencao_cache": 30
}

# Inicializa o caminho do banco lendo do config.json se existir.
# Fallback SEMPRE para rede para evitar bancos locais fragmentados.
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
            
    # NUNCA usar caminhos relativos na string de conexão do SQLite em produção.
    return sqlite3.connect(caminho_db, timeout=timeout)

def init_db():
    """Inicializa o banco de dados, cria a tabela 'falhas' e adiciona a coluna 'observacao' se não existir."""
    caminho_db = carregar_config().get("caminho_banco_rede", DB_PATH)
    if not servidor_online(caminho_db):
        return

    pasta_db = os.path.dirname(DB_PATH)
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
            
            # Adiciona a coluna 'observacao' se ela não existir
            cursor.execute("PRAGMA table_info(falhas)")
            columns = [info[1] for info in cursor.fetchall()]
            if 'observacao' not in columns:
                cursor.execute("ALTER TABLE falhas ADD COLUMN observacao TEXT")
            if 'tecnico' not in columns:
                cursor.execute("ALTER TABLE falhas ADD COLUMN tecnico TEXT")

            # Tabela de Usuários (Mission 15)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS usuarios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome TEXT,
                    login TEXT UNIQUE,
                    senha_hash TEXT,
                    is_admin INTEGER
                )
            """)

            # Tabela de Modelos (Mission 28)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS modelos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome_modelo TEXT UNIQUE
                )
            """)

            # Tabela da Base de Conhecimento (Wiki) (Mission 28)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS wiki_reparos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    modelo_id INTEGER,
                    fase TEXT,
                    sintoma TEXT,
                    solucao TEXT,
                    tecnico_id TEXT,
                    data_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (modelo_id) REFERENCES modelos(id)
                )
            """)

            # Verifica se a tabela usuários está vazia e insere admin padrão
            cursor.execute("SELECT COUNT(*) FROM usuarios")
            if cursor.fetchone()[0] == 0:
                admin_hash = hashlib.sha256('admin123'.encode()).hexdigest()
                cursor.execute("""
                    INSERT INTO usuarios (nome, login, senha_hash, is_admin)
                    VALUES (?, ?, ?, ?)
                """, ('Administrador', 'admin', admin_hash, 1))

            # Índices para otimizar as consultas mais comuns
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_data_registro ON falhas (data_registro);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_componente ON falhas (componente);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_arquivo ON falhas (arquivo);")
            conn.commit()
            
            # Popula modelos iniciais se o DB for novo ou modelos não existirem
            popular_modelos_iniciais(cursor)
            
        sincronizar_espelho_local()
            
    except (sqlite3.OperationalError, OSError) as e:
        print(f"Erro ao inicializar o banco de dados: {e}")

def sincronizar_espelho_local():
    """Sincroniza os dados essenciais (usuários, modelos e wiki_reparos) para uso offline."""
    if not verificar_conexao_db(): return
    try:
        with conectar_banco(timeout=5) as conn_rede:
            usuarios_rede = conn_rede.cursor().execute("SELECT * FROM usuarios").fetchall()
            modelos_rede = conn_rede.cursor().execute("SELECT * FROM modelos").fetchall()
            wiki_rede = conn_rede.cursor().execute("SELECT * FROM wiki_reparos").fetchall()
            
        with sqlite3.connect(DB_ESPELHO_PATH) as conn_local:
            c = conn_local.cursor()
            
            # Espelha Usuários
            c.execute("CREATE TABLE IF NOT EXISTS usuarios (id INTEGER PRIMARY KEY, nome TEXT, login TEXT UNIQUE, senha_hash TEXT, is_admin INTEGER)")
            c.execute("DELETE FROM usuarios")
            c.executemany("INSERT INTO usuarios VALUES (?,?,?,?,?)", usuarios_rede)
            
            # Espelha Modelos
            c.execute("CREATE TABLE IF NOT EXISTS modelos (id INTEGER PRIMARY KEY AUTOINCREMENT, nome_modelo TEXT UNIQUE NOT NULL)")
            c.execute("DELETE FROM modelos")
            c.executemany("INSERT INTO modelos VALUES (?,?)", modelos_rede)
            
            # Espelha Wiki Reparos
            c.execute("""
                CREATE TABLE IF NOT EXISTS wiki_reparos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    modelo_id INTEGER,
                    fase TEXT,
                    sintoma TEXT,
                    solucao TEXT,
                    tecnico_id TEXT,
                    data_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (modelo_id) REFERENCES modelos(id)
                )
            """)
            c.execute("DELETE FROM wiki_reparos")
            c.executemany("INSERT INTO wiki_reparos VALUES (?,?,?,?,?,?,?)", wiki_rede)
            
            conn_local.commit()
    except Exception as e:
        print(f"Erro no espelho local: {e}")

def popular_modelos_iniciais(cursor):
    """Insere a lista inicial de modelos na base de conhecimento se não existirem."""
    modelos_iniciais = ['M70Q5', 'M70Q6', 'M70S5', 'M70S6', 'M75S5', 'M75Q5 SH', 'T14Gen6', 'T14Gen7', 'E14Gen7', 'LOQ IRX9', 'LOQ IAX9E']
    for modelo in modelos_iniciais:
        try:
            cursor.execute("INSERT OR IGNORE INTO modelos (nome_modelo) VALUES (?)", (modelo,))
        except sqlite3.Error as e:
            print(f"Erro ao inserir modelo inicial {modelo}: {e}")

def validar_login(login, senha_texto):
    """Valida o login e a senha (comparando o hash) no banco de dados."""
    try:
        with conectar_banco(timeout=5) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, nome, is_admin, senha_hash FROM usuarios WHERE login = ?", (login,))
            user = cursor.fetchone()
            if user:
                id_user, nome, is_admin, senha_hash_db = user
                senha_sujeito_hash = hashlib.sha256(senha_texto.encode()).hexdigest()
                if senha_sujeito_hash == senha_hash_db:
                    return {"id": id_user, "nome": nome, "login": login, "is_admin": bool(is_admin)}
            return None
    except (sqlite3.OperationalError, OSError) as e:
        print(f"Erro ao validar login na rede, tentando espelho local: {e}")
        try:
            with sqlite3.connect(DB_ESPELHO_PATH, timeout=5) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, nome, is_admin, senha_hash FROM usuarios WHERE login = ?", (login,))
                user = cursor.fetchone()
                if user:
                    id_user, nome, is_admin, senha_hash_db = user
                    senha_sujeito_hash = hashlib.sha256(senha_texto.encode()).hexdigest()
                    if senha_sujeito_hash == senha_hash_db:
                        return {"id": id_user, "nome": nome, "login": login, "is_admin": bool(is_admin)}
                return None
        except sqlite3.OperationalError as e_local:
            print(f"Erro ao validar login no espelho local: {e_local}")
            return None


def obter_usuario_por_login(login):
    """Busca um usuário no banco apenas pelo login, sem verificar a senha (Lembrar de Mim)."""
    try:
        with conectar_banco(timeout=5) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, nome, is_admin FROM usuarios WHERE login = ?", (login,))
            user = cursor.fetchone()
            if user:
                id_user, nome, is_admin = user
                return {"id": id_user, "nome": nome, "login": login, "is_admin": bool(is_admin)}
            return None
    except (sqlite3.OperationalError, OSError) as e:
        print(f"Erro ao tentar recuperar usuario por login na rede, tentando espelho: {e}")
        try:
            with sqlite3.connect(DB_ESPELHO_PATH, timeout=5) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, nome, is_admin FROM usuarios WHERE login = ?", (login,))
                user = cursor.fetchone()
                if user:
                    id_user, nome, is_admin = user
                    return {"id": id_user, "nome": nome, "login": login, "is_admin": bool(is_admin)}
                return None
        except sqlite3.OperationalError as e_local:
            print(f"Erro ao recuperar usuario por login no espelho: {e_local}")
            return None

def listar_usuarios():
    """Retorna uma lista com todos os usuários do banco de dados (sem a senha)."""
    try:
        with conectar_banco(timeout=5) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, nome, login, is_admin FROM usuarios ORDER BY nome")
            return [{"id": row[0], "nome": row[1], "login": row[2], "is_admin": bool(row[3])} for row in cursor.fetchall()]
    except (sqlite3.OperationalError, OSError) as e:
        print(f"Erro ao listar usuários do banco de dados: {e}")
        return []

def cadastrar_usuario(nome, login, senha, is_admin):
    """Cadastra um novo usuário no banco de dados. Retorna True se sucesso, False caso contrário."""
    senha_hash = hashlib.sha256(senha.encode()).hexdigest()
    try:
        with conectar_banco(timeout=5) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO usuarios (nome, login, senha_hash, is_admin)
                VALUES (?, ?, ?, ?)
            """, (nome, login, senha_hash, int(is_admin)))
            conn.commit()
            return True
    except sqlite3.IntegrityError:
        print(f"Erro: O login '{login}' já existe no banco de dados.")
        return False
    except sqlite3.OperationalError as e:
        print(f"Erro ao cadastrar usuário no banco de dados: {e}")
        return False

def deletar_usuario(id_usuario):
    """Deleta um usuário pelo ID. Impede a exclusão do último admin."""
    try:
        with conectar_banco(timeout=5) as conn:
            cursor = conn.cursor()
            
            # Verifica se é o último admin tentando ser excluído
            cursor.execute("SELECT is_admin FROM usuarios WHERE id = ?", (id_usuario,))
            user = cursor.fetchone()
            if user and user[0] == 1:
                cursor.execute("SELECT COUNT(*) FROM usuarios WHERE is_admin = 1")
                if cursor.fetchone()[0] <= 1:
                    print("Operação negada: Não é possível deletar o último administrador do sistema.")
                    return False
            
            cursor.execute("DELETE FROM usuarios WHERE id = ?", (id_usuario,))
            conn.commit()
            return True
    except sqlite3.OperationalError as e:
        print(f"Erro ao deletar usuário no banco de dados: {e}")
        return False

def atualizar_usuario(id_usuario, novo_nome, novo_login, nova_senha=None):
    """Atualiza um usuário existente. Se nova_senha for fornecida, atualiza a senha também."""
    try:
        with conectar_banco(timeout=5) as conn:
            cursor = conn.cursor()
            if nova_senha:
                senha_hash = hashlib.sha256(nova_senha.encode()).hexdigest()
                cursor.execute("""
                    UPDATE usuarios 
                    SET nome = ?, login = ?, senha_hash = ?
                    WHERE id = ?
                """, (novo_nome, novo_login, senha_hash, id_usuario))
            else:
                cursor.execute("""
                    UPDATE usuarios 
                    SET nome = ?, login = ?
                    WHERE id = ?
                """, (novo_nome, novo_login, id_usuario))
            conn.commit()
            return True
    except sqlite3.IntegrityError:
        print(f"Erro: O login '{novo_login}' já existe no banco de dados.")
        return False
    except sqlite3.OperationalError as e:
        print(f"Erro ao atualizar usuário no banco de dados: {e}")
        return False

def adicionar_modelo(nome_modelo):
    """Adiciona um novo modelo à base de conhecimento."""
    try:
        with conectar_banco(timeout=5) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO modelos (nome_modelo) VALUES (?)", (nome_modelo,))
            conn.commit()
            return cursor.lastrowid
    except sqlite3.IntegrityError:
        print(f"Erro: O modelo '{nome_modelo}' já existe.")
        return None
    except sqlite3.OperationalError as e:
        print(f"Erro ao adicionar modelo: {e}")
        return None

def editar_modelo(id_modelo, novo_nome):
    """Edita o nome de um modelo existente."""
    try:
        with conectar_banco(timeout=5) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE modelos 
                SET nome_modelo = ?
                WHERE id = ?
            """, (novo_nome, id_modelo))
            conn.commit()
            return True
    except sqlite3.IntegrityError:
        print(f"Erro: O modelo '{novo_nome}' já existe no banco de dados.")
        return False
    except sqlite3.OperationalError as e:
        print(f"Erro ao editar modelo no banco de dados: {e}")
        return False

def listar_modelos():
    """Retorna uma lista de todos os modelos cadastrados."""
    try:
        with conectar_banco(timeout=5) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, nome_modelo FROM modelos ORDER BY nome_modelo")
            return [{"id": row[0], "nome": row[1]} for row in cursor.fetchall()]
    except (sqlite3.OperationalError, OSError) as e:
        print(f"Rede offline. Lendo modelos do espelho local: {e}")
        try:
            with sqlite3.connect(DB_ESPELHO_PATH, timeout=5) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, nome_modelo FROM modelos ORDER BY nome_modelo")
                return [{"id": row[0], "nome": row[1]} for row in cursor.fetchall()]
        except Exception as ex:
            print(f"Erro ao ler modelos do espelho: {ex}")
            return []

def adicionar_solucao_wiki(modelo_id, fase, sintoma, solucao, tecnico_id):
    """Adiciona uma nova solução à base de conhecimento."""
    try:
        with conectar_banco(timeout=5) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO wiki_reparos (modelo_id, fase, sintoma, solucao, tecnico_id)
                VALUES (?, ?, ?, ?, ?)
            """, (modelo_id, fase, sintoma, solucao, tecnico_id))
            conn.commit()
            return True
    except (sqlite3.OperationalError, OSError) as e:
        print(f"Erro ao adicionar solução na rede, salvando na fila offline: {e}")
        try:
            with sqlite3.connect(DB_LOCAL_PATH) as conn_local:
                cursor_local = conn_local.cursor()
                tipo_acao = 'NOVA_SOLUCAO'
                payload_json = json.dumps({
                    "modelo_id": modelo_id, "fase": fase, 
                    "sintoma": sintoma, "solucao": solucao, "tecnico_id": tecnico_id
                })
                cursor_local.execute("INSERT INTO fila_sync (tipo_acao, payload_json) VALUES (?, ?)", (tipo_acao, payload_json))
                conn_local.commit()
            return "OFFLINE"
        except Exception as ex_local:
            print(f"Erro ao salvar solução na fila offline: {ex_local}")
            return False

def buscar_solucoes_wiki(modelo_id, fase=None, busca_texto=None):
    """Busca soluções na wiki com base nos filtros fornecidos."""
    try:
        with conectar_banco(timeout=5) as conn:
            cursor = conn.cursor()
            query = """
                SELECT w.id, m.nome_modelo, w.fase, w.sintoma, w.solucao, w.tecnico_id, w.data_registro
                FROM wiki_reparos w
                JOIN modelos m ON w.modelo_id = m.id
                WHERE 1=1
            """
            params = []
            if modelo_id:
                query += " AND w.modelo_id = ?"
                params.append(modelo_id)
            if fase and fase != 'Todos':
                query += " AND w.fase = ?"
                params.append(fase)
            if busca_texto:
                query += " AND (w.sintoma LIKE ? OR w.solucao LIKE ?)"
                params.extend([f"%{busca_texto}%", f"%{busca_texto}%"])
                
            query += " ORDER BY w.data_registro DESC"
            cursor.execute(query, params)
            
            return [{
                "id": row[0], "modelo": row[1], "fase": row[2], 
                "sintoma": row[3], "solucao": row[4], 
                "tecnico": row[5], "data": row[6]
            } for row in cursor.fetchall()]
    except (sqlite3.OperationalError, OSError) as e:
        print(f"Erro ao buscar soluções na rede, tentando espelho: {e}")
        try:
            with sqlite3.connect(DB_ESPELHO_PATH, timeout=5) as conn:
                cursor = conn.cursor()
                query = """
                    SELECT w.id, m.nome_modelo, w.fase, w.sintoma, w.solucao, w.tecnico_id, w.data_registro
                    FROM wiki_reparos w
                    JOIN modelos m ON w.modelo_id = m.id
                    WHERE 1=1
                """
                params = []
                if modelo_id:
                    query += " AND w.modelo_id = ?"
                    params.append(modelo_id)
                if fase and fase != 'Todos':
                    query += " AND w.fase = ?"
                    params.append(fase)
                if busca_texto:
                    query += " AND (w.sintoma LIKE ? OR w.solucao LIKE ?)"
                    params.extend([f"%{busca_texto}%", f"%{busca_texto}%"])
                    
                query += " ORDER BY w.data_registro DESC"
                cursor.execute(query, params)
                return [{
                    "id": row[0], "modelo": row[1], "fase": row[2], 
                    "sintoma": row[3], "solucao": row[4], 
                    "tecnico": row[5], "data": row[6]
                } for row in cursor.fetchall()]
        except Exception as ex:
            print(f"Erro ao buscar soluções no espelho: {ex}")
            return []

def gerar_relatorio_excel(caminho_destino):
    """Gera um arquivo Excel contendo todos os dados de falhas."""
    try:
        with conectar_banco(timeout=5) as conn:
            # Lemos a tabela falhas principal
            df = pd.read_sql_query("SELECT * FROM falhas", conn)
            # Salva no arquivo designado pelo usuário
            df.to_excel(caminho_destino, index=False)
            return True
    except Exception as e:
        print(f"Erro ao gerar relatório Excel: {e}")
        return False

def salvar_falha_db(falha_dict):
    """Salva um dicionário de falha no banco de dados SQLite com retentativa."""
    max_retries = 3
    retry_delay = 1  # segundos
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
                return True # Sucesso
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < max_retries - 1:
                print(f"Banco de dados bloqueado. Tentando novamente em {retry_delay}s... (Tentativa {attempt + 1})")
                time.sleep(retry_delay)
            else:
                print(f"Erro final ao salvar falha no DB: {e}")
                return False # Falha após todas as tentativas
    return False

def salvar_observacao(nome_arquivo, texto_obs, tecnico=None):
    """Salva a observação do técnico e atualiza o status de acordo em um Histórico Acumulativo."""
    if not texto_obs.strip():
        return True # Não salva observações vazias
        
    try:
        with conectar_banco(timeout=20) as conn:
            cursor = conn.cursor()
            
            # Pega a observação atual
            cursor.execute("SELECT observacao FROM falhas WHERE arquivo = ?", (nome_arquivo,))
            row = cursor.fetchone()
            obs_antiga = row[0] if row and row[0] else ""
            
            # Cria o bloco de texto novo formatado
            agora = datetime.now().strftime("%d/%m/%Y %H:%M")
            nome_tecnico = tecnico if tecnico else "Local"
            novo_bloco = f"[{agora}] Técnico: {nome_tecnico}\n{texto_obs}"
            
            # Concatena com a antiga, se houver
            texto_final = f"{obs_antiga.strip()}\n\n{novo_bloco}" if obs_antiga.strip() else novo_bloco
            status = 'TRATADO'
            
            if tecnico is not None:
                sql = "UPDATE falhas SET observacao = ?, status_tratativa = ?, tecnico = ? WHERE arquivo = ?"
                cursor.execute(sql, (texto_final, status, tecnico, nome_arquivo))
            else:
                sql = "UPDATE falhas SET observacao = ?, status_tratativa = ? WHERE arquivo = ?"
                cursor.execute(sql, (texto_final, status, nome_arquivo))
            conn.commit()
            return True
    except (sqlite3.OperationalError, OSError) as e:
        print(f"Erro ao salvar observação no DB: {e}")
        try:
            with sqlite3.connect(DB_LOCAL_PATH) as conn_local:
                cursor_local = conn_local.cursor()
                tipo_acao = 'NOVA_OBSERVACAO'
                payload_json = json.dumps({"arquivo": nome_arquivo, "texto": texto_obs, "tecnico": tecnico})
                cursor_local.execute("INSERT INTO fila_sync (tipo_acao, payload_json) VALUES (?, ?)", (tipo_acao, payload_json))
                conn_local.commit()
            return "OFFLINE"
        except Exception as ex_local:
            print(f"Erro ao salvar na fila offline: {ex_local}")
            return False

def sincronizar_fila_offline():
    """Processa a fila de ações salvas localmente quando a rede volta."""
    try:
        if not os.path.exists(DB_LOCAL_PATH):
            return
            
        with sqlite3.connect(DB_LOCAL_PATH) as conn_local:
            cursor = conn_local.cursor()
            cursor.execute("SELECT id, tipo_acao, payload_json FROM fila_sync ORDER BY data_registro ASC")
            registros = cursor.fetchall()
            
            if not registros:
                return
                
            if not verificar_conexao_db():
                return
                
            for reg in registros:
                id_reg, tipo_acao, payload_json = reg
                if tipo_acao == 'NOVA_OBSERVACAO':
                    dados = json.loads(payload_json)
                    sucesso = salvar_observacao(dados.get("arquivo"), dados.get("texto"), dados.get("tecnico"))
                    
                    if sucesso is True:
                        cursor.execute("DELETE FROM fila_sync WHERE id = ?", (id_reg,))
                        conn_local.commit()
                    else:
                        break # Interrompe se a rede cair ou ocorrer outro erro
                elif tipo_acao == 'NOVA_SOLUCAO':
                    dados = json.loads(payload_json)
                    sucesso = adicionar_solucao_wiki(
                        dados.get("modelo_id"), dados.get("fase"),
                        dados.get("sintoma"), dados.get("solucao"),
                        dados.get("tecnico_id")
                    )
                    
                    if sucesso is True:
                        cursor.execute("DELETE FROM fila_sync WHERE id = ?", (id_reg,))
                        conn_local.commit()
                    else:
                        break # Interrompe fluxo de rede
    except Exception as e:
        print(f"Erro no sincronizador offline: {e}")

def ler_observacao(nome_arquivo):
    """Lê a observação do técnico associada a um arquivo."""
    try:
        with conectar_banco(timeout=20) as conn:
            cursor = conn.cursor()
            sql = "SELECT observacao FROM falhas WHERE arquivo = ? AND observacao IS NOT NULL LIMIT 1"
            cursor.execute(sql, (nome_arquivo,))
            resultado = cursor.fetchone()
            return resultado[0] if resultado else ""
    except sqlite3.OperationalError as e:
        print(f"Erro ao ler observação do DB: {e}")
        return ""

def buscar_historico_serial(serial):
    """Busca o histórico de análise (última observação) de um determinado serial."""
    try:
        with conectar_banco(timeout=20) as conn:
            cursor = conn.cursor()
            sql = """
                SELECT data_registro, observacao, tecnico 
                FROM falhas 
                WHERE serial = ? AND observacao IS NOT NULL AND observacao != ''
                ORDER BY data_registro DESC 
                LIMIT 1
            """
            cursor.execute(sql, (serial,))
            resultado = cursor.fetchone()
            if resultado:
                return {"data": resultado[0], "texto": resultado[1], "tecnico": resultado[2] if len(resultado) > 2 else "Desconhecido"}
            return None
    except sqlite3.OperationalError as e:
        print(f"Erro ao buscar histórico do serial no DB: {e}")
        return None

def verificar_conexao_db():
    """Verifica se o arquivo do banco de dados está acessível na rede estipulada."""
    if not servidor_online(DB_PATH):
        return False

    pasta_db = os.path.dirname(DB_PATH)
    
    # Requisito rigoroso: se a pasta de rede não existe, aborta. NUNCA crie db local de fallback.
    if not os.path.exists(pasta_db):
        return False
        
    if not os.path.exists(DB_PATH):
        init_db() # Tenta inicializar apenas se o destino na rede estiver online
    
    if not os.path.exists(DB_PATH):
         return False

    try:
        # Tenta uma conexão simples para garantir que não está corrupto ou bloqueado
        with conectar_banco(timeout=5) as conn:
            conn.cursor().execute("PRAGMA quick_check")
        return True
    except (sqlite3.OperationalError, OSError):
        return False

def obter_estatisticas_ict():
    """Lê o banco de dados de falhas e retorna estatísticas do dia, incluindo o top 5 componentes."""
    stats = {
        'total_hoje': 0,
        'top_componente': 'N/A',
        'top_5_componentes': [],
        'db_online': False
    }

    pasta_db = os.path.dirname(DB_PATH)
    if not os.path.exists(pasta_db):
        return stats # Se a rede está offline, não tenta inicializar banco falso
        
    if not os.path.exists(DB_PATH):
        # Tenta inicializar o DB caso a rede exista mas o arquivo DB foi deletado
        init_db()
        if not os.path.exists(DB_PATH):
            return stats

    try:
        with conectar_banco(timeout=20) as conn:
            cursor = conn.cursor()
            stats['db_online'] = True
            hoje_str = datetime.now().strftime("%Y-%m-%d")

            # 1. Contar total de falhas hoje
            cursor.execute("SELECT COUNT(id) FROM falhas WHERE date(data_registro) = ?", (hoje_str,))
            total_hoje = cursor.fetchone()[0]
            stats['total_hoje'] = total_hoje

            # 2. Obter os 5 componentes com mais falhas hoje
            cursor.execute("""
                SELECT componente, COUNT(id) as qtd
                FROM falhas
                WHERE date(data_registro) = ? AND componente IS NOT NULL AND componente != ''
                GROUP BY componente
                ORDER BY qtd DESC
                LIMIT 5
            """, (hoje_str,))
            
            top_5 = cursor.fetchall()
            stats['top_5_componentes'] = top_5
            
            if top_5:
                stats['top_componente'] = top_5[0][0]

    except sqlite3.OperationalError as e:
        print(f"Erro ao consultar estatísticas no DB: {e}")
        stats['db_online'] = False

    return stats

def obter_ultimas_analises(limite=10):
    """Busca as últimas 'N' análises/falhas, calculando o status de tratativa."""
    try:
        with conectar_banco(timeout=20) as conn:
            cursor = conn.cursor()
            # O status é definido como 'TRATADO' se houver qualquer texto na observação.
            sql = """
                SELECT data_registro, serial, componente, 
                       CASE 
                           WHEN observacao IS NOT NULL AND observacao != '' THEN 'TRATADO'
                           ELSE status_tratativa 
                       END as status
                FROM falhas 
                ORDER BY data_registro DESC 
                LIMIT ?
            """
            cursor.execute(sql, (limite,))
            return cursor.fetchall()
    except (sqlite3.OperationalError, OSError) as e:
        print(f"Erro ao obter últimas análises do DB: {e}")
        return []

def obter_estatisticas_progresso():
    """Calcula o progresso de análise de falhas do dia (Abertos vs. Tratados)."""
    stats = {'abertos': 0, 'tratados': 0}
    try:
        with conectar_banco(timeout=20) as conn:
            cursor = conn.cursor()
            hoje_str = datetime.now().strftime("%Y-%m-%d")

            # Conta ARQUIVOS distintos que tiveram falha hoje e NÃO possuem observação
            cursor.execute("""
                SELECT COUNT(DISTINCT arquivo) 
                FROM falhas 
                WHERE date(data_registro) = ? 
                AND (observacao IS NULL OR observacao = '')
            """, (hoje_str,))
            stats['abertos'] = cursor.fetchone()[0]

            # Conta ARQUIVOS distintos que tiveram falha hoje e JÁ possuem observação
            cursor.execute("""
                SELECT COUNT(DISTINCT arquivo) 
                FROM falhas 
                WHERE date(data_registro) = ? 
                AND (observacao IS NOT NULL AND observacao != '')
            """, (hoje_str,))
            stats['tratados'] = cursor.fetchone()[0]
    except sqlite3.OperationalError as e:
        print(f"Erro ao obter estatísticas de progresso do DB: {e}")
    
    return stats


def limpar_analises_db():
    """Reseta todas as observações e status no banco de dados."""
    try:
        with conectar_banco(timeout=20) as conn:
            cursor = conn.cursor()
            # Limpa o texto da análise e reseta o status para ABERTO
            sql = "UPDATE falhas SET observacao = NULL, status_tratativa = 'ABERTO'"
            cursor.execute(sql)
            conn.commit()
            return True
    except sqlite3.OperationalError as e:
        print(f"Erro ao limpar análises no DB: {e}")
        return False


# --- Funções de Configuração (JSON) ---
def carregar_config():
    """Carrega a configuração do arquivo JSON, usando valores padrão para chaves ausentes."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                dados = json.load(f)
                # Garante que todas as chaves padrão existam
                for k, v in DEFAULT_CONFIG.items():
                    dados.setdefault(k, v)
                return dados
        except (json.JSONDecodeError, IOError):
            return DEFAULT_CONFIG.copy()
    
    # Se não existir, cria com os valores padrão
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

def limpar_cache_local():
    """Remove arquivos do diretório de backup local que sejam mais velhos que 'dias_retencao_cache'."""
    config = carregar_config()
    backup_dir = config.get("backup_local_dir", "")
    dias_retencao = config.get("dias_retencao_cache", 30)

    if not backup_dir or not os.path.exists(backup_dir):
        return

    agora = time.time()
    limite_idade_segundos = dias_retencao * 86400  # 1 dia = 86400 segundos

    for root, _, files in os.walk(backup_dir):
        for arquivo in files:
            caminho_completo = os.path.join(root, arquivo)
            try:
                idade_arquivo = agora - os.path.getmtime(caminho_completo)
                if idade_arquivo > limite_idade_segundos:
                    os.remove(caminho_completo)
            except (OSError, FileNotFoundError, PermissionError):
                # Ignora silenciosamente arquivos que não puderem ser deletados
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
    # A implementação é muito similar à extração do CSV, mas baseada no prefixo.
    dados = {"tipo": "TRI", "data": "N/A", "serial": "N/A", "modelo": "N/A", "status": "N/A", "cor": "black"}
    nome_lower = nome_arquivo.lower()
    nome_sem_ext = os.path.splitext(nome_arquivo)[0]
    
    # Tentativa de data via Modificação do arquivo (fallback)
    try:
        ts_mod = os.path.getmtime(caminho_completo)
        dados["data"] = datetime.fromtimestamp(ts_mod).strftime("%d/%m/%Y %H:%M:%S")
    except OSError:
        pass
        
    if nome_lower.startswith("f_") or "fail" in nome_lower:
        dados["status"] = "FAIL"; dados["cor"] = "red"
    elif nome_lower.startswith("p_") or "pass" in nome_lower:
        dados["status"] = "PASS"; dados["cor"] = "green"
        
    # Limpa prefixos conhecidos para achar o serial
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
    """Factory que delega a análise de metadados para a estratégia (Strategy) especializada correta."""
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
        print(f"Erro no Factory do Parser ao analisar metadados: {e}")
        
    # Retorno Fallback Padrão em caso de erro extremo na Factory
    return {"tipo": tipo, "data": "N/A", "serial": "N/A", "modelo": "N/A", "status": "UNKNOWN", "cor": "black"}

# --- Fila Offline e Espelho Local ---
DB_LOCAL_PATH = os.path.join(carregar_config().get("backup_local_dir", get_base_path()), "fila_offline.db").replace('\\', '/')
DB_ESPELHO_PATH = os.path.join(carregar_config().get("backup_local_dir", get_base_path()), "espelho_local.db").replace('\\', '/')

# Chama a inicialização do DB e do Espelho
init_db()

def init_db_local():
    """Inicializa localmente a fila de sincronizacao (Store-and-Forward)"""
    try:
        os.makedirs(os.path.dirname(DB_LOCAL_PATH), exist_ok=True)
        with sqlite3.connect(DB_LOCAL_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS fila_sync (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    tipo_acao TEXT, 
                    payload_json TEXT, 
                    data_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
    except (sqlite3.OperationalError, OSError) as e:
        print(f"Erro ao inicializar DB local offline: {e}")

    try:
        os.makedirs(os.path.dirname(DB_ESPELHO_PATH), exist_ok=True)
        with sqlite3.connect(DB_ESPELHO_PATH) as conn_espelho:
            c = conn_espelho.cursor()
            c.execute("CREATE TABLE IF NOT EXISTS usuarios (id INTEGER PRIMARY KEY, nome TEXT, login TEXT UNIQUE, senha_hash TEXT, is_admin INTEGER)")
            c.execute("CREATE TABLE IF NOT EXISTS modelos (id INTEGER PRIMARY KEY AUTOINCREMENT, nome_modelo TEXT UNIQUE NOT NULL)")
            c.execute("CREATE TABLE IF NOT EXISTS wiki_reparos (id INTEGER PRIMARY KEY AUTOINCREMENT, modelo_id INTEGER, fase TEXT, sintoma TEXT, solucao TEXT, tecnico_id TEXT, data_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")

            # Injeta o Admin de segurança caso o espelho local esteja vazio
            c.execute("SELECT COUNT(*) FROM usuarios")
            if c.fetchone()[0] == 0:
                admin_hash = hashlib.sha256('admin123'.encode()).hexdigest()
                c.execute("INSERT INTO usuarios (nome, login, senha_hash, is_admin) VALUES (?, ?, ?, ?)", ('Administrador Local', 'admin', admin_hash, 1))
            conn_espelho.commit()
    except Exception as e:
        print(f"Erro ao inicializar espelho de segurança: {e}")

init_db_local()