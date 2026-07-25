# 🤖 REGRAS DE DESENVOLVIMENTO E DIRETRIZES DE IA
## Documento 001: Manual de Continuidade de Contexto para Inteligências Artificiais e Desenvolvedores

> **MENSAGEM PARA A IA:**
> Você está trabalhando no repositório **ICT Master Suite**. Este documento define o protocolo obrigatório que você deve seguir para manter a consistência, a segurança do código e a memória permanente do projeto.

---

## 📋 1. Checklist Inicial ao Iniciar uma Tarefa

Antes de sugerir qualquer alteração de código ou arquitetura, você DEVE:
1. [x] Ler o arquivo `memoria_projeto/000_CONTEXTO_GLOBAL_E_HISTORICO.md` para absorver a história, os caminhos de rede e o estado atual do software (`v6.1.0`).
2. [x] Inspecionar os arquivos envolvidos usando ferramentas de leitura (`view_file`), evitando supor definições ou assinaturas de funções.
3. [x] Garantir que sua alteração respeite o principio de **Zero Quebra de Compatibilidade** com os motores de busca e cópia assíncrona.

---

## 🛠️ 2. Regras de Código & Padrões Técnicos

1. **Interface PyQt5 e Threading:**
   * NUNCA faça chamadas de I/O de rede ou disco diretamente na Thread principal da UI (Looper principal).
   * Mantenha as pesquisas, carregamentos de arquivo e varreduras de rede encapsuladas em workers `QThread` (localizados em `threads.py`).
   * Utilize sinais e slots do PyQt5 (`pyqtSignal`) para atualizar elementos visuais na tela.

2. **Parsing de Logs e Resiliência:**
   * Qualquer nova lógica de extração de componentes ou diagnóstico em `models.py` deve conter blocos `try/except` com fallback seguro.
   * Se o arquivo de log contiver formatos inéditos ou linhas corrompidas, a aplicação deve falhar silenciosamente e exibir o texto puro no `QTextEdit` sem fechar ou exibir crash ao operador.

3. **Leitura na Íntegra:**
   * O visualizador de log na interface (`text_raw`) deve exibir o texto bruto 100% na íntegra.
   * O realce de sintaxe é feito pelo `LogSyntaxHighlighter` (nativamente vinculado ao documento) para não poluir o conteúdo textual original.

---

## 🚀 3. Protocolo Obrigatório de Atualização de Versão e Memória

Sempre que você implementar uma nova funcionalidade, correção de bug ou refatoração:

1. **Atualize o Número de Versão:**
   * Atualize a constante `APP_VERSION` em `models.py` (ex: de `"6.1.0"` para `"6.2.0"`).
2. **Atualize a Memória do Projeto:**
   * Adicione uma breve descrição da nova funcionalidade e versão no histórico em `memoria_projeto/000_CONTEXTO_GLOBAL_E_HISTORICO.md`.
3. **Execute os Testes de Sintaxe e Unidade:**
   ```bash
   python -m py_compile ui_main.py models.py threads.py test_threads.py
   python -m unittest test_threads.py
   ```
4. **Gere a Release Versionada:**
   ```bash
   python build_release.py
   ```
   * Verifique se o executável foi gerado com sucesso em `releases/ICT_Master_Suite_vX.Y.Z.exe`.
5. **Realize Commit e Push com Mensagem Descritiva em Português:**
   ```bash
   git add -A
   git commit -m "Descrição clara da melhoria implementada (vX.Y.Z)"
   git push origin main
   ```

---

## 💡 4. Comunicação com o Usuário

* Responda ao usuário em **Português do Brasil**, de forma clara, profissional e sucinta.
* Sempre confirme quando os documentos de memória em `memoria_projeto/` forem atualizados.
