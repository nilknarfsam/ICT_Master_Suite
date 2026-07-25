# 🧠 MEMÓRIA DO PROJETO - ICT MASTER SUITE
## Documento 000: Contexto Global, Regras de Arquitetura e Histórico de Evolução

> **INSTRUÇÃO PARA QUALQUER IA OU DESENVOLVEDOR:**
> Este diretório (`memoria_projeto/`) contém todo o histórico, regras de negócio, infraestrutura de rede, padrões de logs e decisões de arquitetura do **ICT Master Suite**.
> **Antes de realizar qualquer alteração ou novo desenvolvimento neste código, leia integralmente este documento e o arquivo `001_REGRAS_DE_DESENVOLVIMENTO_AI.md`.**

---

## 🎯 1. Visão Geral do Projeto & Propósito

O **ICT Master Suite** é um sistema desktop corporativo desenvolvido em **Python 3.12** e **PyQt5** para a engenharia de teste e técnicos de reparo de bancada. 

Ele resolve três problemas críticos de produção em fábrica de placas eletrônicas:
1. **Busca Ultrarrápida por Serial:** Varre diretórios de rede SMB com mais de **200.000 arquivos de log** de testes de placas eletrônicas em tempo real (*Live Streaming*), localizando todos os logs de uma placa específica via código de barras.
2. **Diagnóstico Visual Rápido:** Analisa os logs das máquinas **Agilent** e **TRI**, extraindo instantaneamente componentes defeituosos (CIs, capacitores, resistores, transistores, conectores) e suas coordenadas físicas no Grid da placa (`A1`, `B2`), exibindo um Card de Diagnóstico e laudo formatado.
3. **Serviço de Cópia Automática TRI:** Monitora em segundo plano a pasta raiz de testes da TRI e copia automaticamente arquivos reprovados (`FAIL`) para uma pasta centralizada `defeitos_tri` em 3 a 5 segundos (priorizando por `mtime` decrescente).

---

## 🌐 2. Infraestrutura e Caminhos de Rede Corporativa

O aplicativo conecta-se à rede da fábrica no IP do servidor de teste **`147.1.0.95`**:

| Recurso / Serviço | Caminho de Rede SMB (CIFS) | Descrição / Função |
| :--- | :--- | :--- |
| **Busca Finder - TRI** | `//147.1.0.95/teste_ict/ict02/defeitos_tri` | Diretório de busca dos logs de falha da TRI. |
| **Busca Finder - Agilent** | `//147.1.0.95/teste_ict/ict01/defeitos` | Diretório de busca dos logs de relatório Agilent. |
| **Cópia TRI (Origem)** | `//147.1.0.95/teste_ict/ict02` | Diretório raiz onde a máquina TRI gera os logs. |
| **Cópia TRI (Destino)** | `//147.1.0.95/teste_ict/ict02/defeitos_tri` | Pasta de destino para onde a thread de cópia move os logs `FAIL`. |
| **Banco de Dados Redundante**| `//147.1.0.95/teste_ict/banco_dados_falhas.db` | Banco SQLite corporativo com suporte WAL de rede. |

---

## 📜 3. Histórico Cronológico da Evolução do Sistema

* **v1.0 - v3.0 (Fase Inicial):** Criação da interface PyQt5 básica, leitor de arquivos locais e protótipos de busca.
* **v4.0 - v5.0 (Limpeza e Foco Absoluto no Serial):** 
  * Removidos módulos legados não utilizados (RBAC, Dashboard web, Wiki offline) para maximizar velocidade e leveza.
  * Implementação da busca 100% focada no Serial Number lido via scanner de código de barras.
  * Adicionado o motor de *Live Streaming* (`arquivo_encontrado` PyQt signal) que injeta itens na UI durante a varredura sem travar a tela.
  * Otimização do `TRICopyThread` ordenando por `mtime` decrescente (cópia em 3-5s).
* **v5.5.0 (Estudo de Análise de Logs):**
  * Criação da pasta `base de conhecimento/` contendo amostras reais de logs das máquinas `ict01` (Agilent) e `ict02` (TRI).
  * Elaboração dos documentos de planejamento de inteligência de logs (`PLANO_INTELIGENCIA_LOGS_ICT.md`).
* **v6.0.0 (Diagnóstico Inteligente & Filtros Visuais):**
  * Implementado o parser `extrair_diagnostico_inteligente` em `models.py`.
  * Criação do **Card de Diagnóstico Rápido** no topo do visualizador de logs.
  * Adição do botão **`👁️ Mostrar Apenas Falhas`** para filtrar ruídos `PASS` em logs extensos.
  * Adição do botão **`📋 Copiar Diagnóstico`** para gerar laudos formatados para Teams/Chamados.
* **v6.1.0 (Refinamento Sênior & Automação de Releases):**
  * **Realce de Sintaxe C++ Nativo (`QSyntaxHighlighter`):** Troca de HTML concatenado por realce de sintaxe nativo (0ms de overhead).
  * **Parser Agilent TestJet:** Leitura de `Device <name>` (ex: `JTP1`) e tratamento de seções (`TestJet`, `Shorts`, `CHEK-POINT/Pins`).
  * **Agrupamento Inteligente de CIs:** Agrupa sub-blocos do mesmo CI no Card (`U109 (3 blocos)`) sem alterar o log bruto.
  * **Exportação de Laudo Formal:** Botão `📄 Salvar Laudo (.txt)` para exportação formal.
  * **Sistema de Builds em `releases/`:** Script `build_release.py` compila e salva executáveis versionados em `releases/` (ignorado no Git pelo `.gitignore`).

---

## 🔒 4. Diretivas Não-Negociáveis do Projeto (Regras de Ouro)

1. **🔒 Exibição do Log Completo na Íntegra:** Nenhuma funcionalidade de diagnóstico ou filtro pode ocultar, alterar ou apagar dados do arquivo de log original ao ser carregado. O log deve ser exibido 100% na íntegra.
2. **🔒 Executável Único Sem Console:** O build principal deve ser gerado em arquivo único sem janela CMD (`--noconsole`).
3. **🔒 Preservação dos Servidores de Teste:** O sistema NUNCA deve alterar, mover ou deletar arquivos originais nos diretórios de origem dos testadores (`//147.1.0.95/teste_ict/ict01` e `ict02`).
4. **🔒 Versionamento Automático:** Toda compilação deve passar por `build_release.py` (ou `build_exe.bat`), gerando o executável renomeado em `releases/ICT_Master_Suite_vX.Y.Z.exe`. A pasta `releases/` NUNCA sobe para o Git (está no `.gitignore`).
5. **🔒 Isolamento de Exceções (Fallback Seguro):** Caso um arquivo de log venha em formato desconhecido ou corrompido, o parser DEVE capturar a exceção e exibir o texto bruto puro sem derrubar a aplicação.

---

## 📂 5. Estrutura Atual de Arquivos do Projeto

* `ui_main.py` -> Interface de usuário PyQt5, manipuladores de eventos e realce nativo (`LogSyntaxHighlighter`).
* `models.py` -> Configurações, constante `APP_VERSION`, parsers de log (`extrair_diagnostico_inteligente`, `agrupar_componentes_inteligente`) e SQLite.
* `threads.py` -> Workers assíncronos (`BuscaThread`, `FileLoaderThread`, `TRICopyThread`, `NetworkMonitorThread`).
* `build_release.py` -> Automador de compilação PyInstaller e gerador de versões na pasta `releases/`.
* `build_exe.bat` -> Script em lote do Windows que invoca `build_release.py`.
* `style.qss` -> Design system e estilização CSS moderna da UI.
* `memoria_projeto/` -> **Base de Memória e Regras do Projeto (Contexto Permanente para IAs e Desenvolvedores).**
