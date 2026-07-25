# 🏭 ICT Master Suite

![Version](https://img.shields.io/badge/version-6.0.0-blue.svg)
![Python](https://img.shields.io/badge/Python-3.12-green.svg)
![PyQt5](https://img.shields.io/badge/UI-PyQt5-orange.svg)
![Platform](https://img.shields.io/badge/platform-Windows%20x64-lightgrey.svg)
![Status](https://img.shields.io/badge/status-Production-brightgreen.svg)

> **Sistema Corporativo de Gestão, Diagnóstico Inteligente, Monitoramento e Busca de Falhas em Logs de Teste ICT (Agilent & TRI)**

O **ICT Master Suite** é uma solução desktop de alto desempenho desenvolvida para engenharia de teste, técnicos de reparo e operadores de bancada. Ele centraliza a busca de logs de falha na rede corporativa em tempo real (varrendo repositórios com mais de 200 mil arquivos), extrai diagnósticos inteligentes de componentes defeituosos e gerencia a cópia contínua de defeitos da TRI em segundo plano.

---

## 📸 Demonstração Visual & Diagnóstico Inteligente

```
+---------------------------------------------------------------------------------------+
|  ICT Log: AGILENT   🔴 REPROVADO (FAIL)                                               |
|  Data: 25/07/2026 12:22:53 | Serial: 6783001KHU | Modelo: t14gen6_lnl | Seção: TestJet   |
|                                                                                       |
|  🔴 Card de Diagnóstico Rápido:                                                       |
|  Componentes Afetados: JTP1 (Conector/Dispositivo)                                    |
|  Setores / Coordenadas na Placa: N/A                                                  |
+---------------------------------------------------------------------------------------+
| [👁️ Mostrar Apenas Falhas]  [📋 Copiar Diagnóstico]                                  |
+---------------------------------------------------------------------------------------+
| TestJet Report for "testjet".                                                         |
| Open #1 Device jtp1                                                                   |
|   Pin 2 Node TP4DATA Measured 57.6 (BRC 210141)                                       |
+---------------------------------------------------------------------------------------+
```

---

## ✨ Principais Funcionalidades

### 🔍 1. Finder Logs (Busca em Tempo Real & Live Streaming)
* **Varredura Ultrarrápida:** Pesquisa instantânea por número serial da placa (leitor de código de barras ou teclado) varrendo diretórios de rede SMB com limites otimizados de profundidade.
* **Streaming de Resultados (Live Output):** Os arquivos encontrados aparecem em tempo real na lista da interface enquanto a varredura prossegue, sem travar ou congelar a UI.
* **Filtro por Data Dinâmico:** Seleção rápida para filtrar logs (*Todas as datas, Últimas 24 horas, Últimos 7 dias, Últimos 30 dias*).
* **Atalhos Globais:** Pressione `F5` para buscar ou `ESC` para limpar a busca e o visualizador de logs.

### 🔴 2. Diagnóstico Inteligente & Card Rápido (`extrair_diagnostico_inteligente`)
* **Leitura Automática de Erros:** O parser dedicado analisa a anatomia do log carregado e exibe no topo da tela um Card de Diagnóstico contendo:
  * **Componentes Afetados:** Lista direta de CI's, Resistores, Capacitores, Transistores e Connectores/Devices (`JTP1`, `PU1600`, `PR1014`, `C892`).
  * **Coordenadas na Placa:** Localização física do componente no Grid da bancada (`A1`, `B2`, `C4`).
  * **Seção de Falha:** Identificação precisa do bloco do teste Agilent (`TestJet`, `Shorts`, `CHEK-POINT/Pins`).

### 👁️ 3. Filtro Alternável "Mostrar Apenas Falhas"
* **Remoção de Ruído Visual:** Em arquivos extensos (ex: 1.500 a 50.000 linhas), oculta automaticamente as centenas de linhas de aprovação (`PASS`) para focar exclusivamente nos trechos de erro e componentes falhados.
* **Preservação de Contexto:** Nos logs CSV da TRI e relatórios da Agilent, mantém sempre visíveis as linhas de metadados e cabeçalhos de seção.

### 📋 4. Laudo de Reparo em 1 Clique (`📋 Copiar Diagnóstico`)
* Copia para a Área de Transferência do Windows um resumo de diagnósticos formatado, pronto para envio no Teams, WhatsApp Corporativo ou abertura de chamados:
  ```text
  =========================================================
  [DIAGNÓSTICO DE FALHA - ICT MASTER SUITE]
  =========================================================
  • Tipo de Teste : TRI / AGILENT
  • Serial Placa  : 67830026EF
  • Modelo        : m75q2_cez_rev1_3
  • Data do Teste : 25/07/2026 10:36:56
  • Status Geral  : FAIL
  ---------------------------------------------------------
  • Componentes Afetados : C892, U109_1_4, U109_3_4
  • Setores / Coordenadas: A1, B2
  =========================================================
  ```

### 🎨 5. Realce de Sintaxe Colorido por Categoria
* 💖 **Circuitos Integrados / CIs (`PU...`, `U...`):** Destaque em Rosa/Magenta.
* 💙 **Capacitores (`CC...`, `PC...`, `C...`):** Destaque em Azul.
* 🧡 **Resistores (`PR...`, `RE...`, `R...`):** Destaque em Laranja.
* 💜 **Transistores / FETs (`PQ...`, `Q...`):** Destaque em Roxo.
* 💚 **Connectores / Devices (`JTP...`, `J...`):** Destaque em Verde Água.
* 🔴 **Falhas & Curtos (`FAIL`, `Short`, `Failed Open`):** Fundo vermelho de alerta.
* 🟡 **Serial Pesquisado:** Amarelo vibrante.

### 🔄 6. Serviço Background de Cópia de Falhas TRI
* **Monitoramento Contínuo:** Monitora o diretório raiz da TRI e copia automaticamente arquivos reprovados (`FAIL`) para a pasta centralizada `defeitos_tri`.
* **Cópia Instantânea (3 a 5s):** Priorização por timestamp de modificação (`mtime` decrescente), copiando os logs gerados mais recentes em milissegundos sem alterar ou deletar arquivos da origem.
* **Controles no Terminal:** Botões de **Pausar**, **Retomar** e **Reiniciar** o serviço diretamente na aba Console do Sistema.

### 📡 7. Monitor de Saúde de Conexão de Rede
* Checagem periódica a cada 15 segundos via socket TCP (Porta 445 SMB) para o IP do servidor (`147.1.0.95`).
* Exibição visual de status no rodapé (`🟢 Rede Online` / `🔴 Rede Offline`) evitando travamentos por desconexão de mapeamento de rede no Windows.

---

## 📂 Formatos de Logs Suportados

| Fabricante | Formato de Arquivo | Padrão de Erro Identificado |
| :--- | :--- | :--- |
| **TRI (Test Research Inc.)** | `.csv`, `.dcl`, `.log` | `Short <ID>`, medições de componentes fora da tolerância com coordenadas no Grid (`A1`, `B2`), status `FAIL` em metadados. |
| **Agilent / Keysight** | `.txt` (`report_out_*.txt`) | `Shorts Report`, `CHEK-POINT Report` (`Failed Open`), `TestJet Report` (`Open #N Device <Name>`), `HAS FAILED`. |

---

## 🛠️ Arquitetura do Sistema

```
c:\finder_logs\
├── ui_main.py             # Interface Gráfica PyQt5 e Eventos do Usuário
├── models.py              # Parsers de Log, Diagnóstico Inteligente, DB SQLite e Configs
├── threads.py             # QThreads Assíncronas (Busca, Loader, Cópia TRI, Network Monitor)
├── style.qss              # Design System e Estilização CSS Moderna
├── build_exe.bat          # Script de Compilação PyInstaller OneFile (--noconsole)
├── ict_config.json        # Arquivo de Configuração Global de Caminhos
└── base de conhecimento/  # Base de dados de amostragem de logs reais (ICT01 e ICT02)
```

---

## 🚀 Como Executar e Compilar

### Requisitos
* Python 3.12+ (64-bit)
* Windows 10 / 11

### Instalação das Dependências
```bash
python -m venv .venv
.venv\Scripts\activate
pip install pyqt5 pyinstaller
```

### Executar em Modo de Desenvolvedor
```bash
python ui_main.py
```

### Compilar Executável de Arquivo Único (Sem Tela de Console CMD)
Execute o utilitário em lote incluído no projeto:
```cmd
build_exe.bat
```
O executável final **`ICT_Master_Suite.exe`** será gerado na raiz do projeto.

---

## 👤 Créditos & Autoria

* **Desenvolvimento:** Franklin Carvalho
* **Repositório Oficial:** [GitHub - ICT_Master_Suite](https://github.com/nilknarfsam/ICT_Master_Suite.git)
* **Licença:** Uso Interno Corporativo / Engenharia de Teste ICT