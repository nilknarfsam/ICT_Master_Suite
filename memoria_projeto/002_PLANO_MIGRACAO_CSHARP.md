# 🔷 PLANO DE MIGRAÇÃO PARA C# / .NET 8
## Documento 002: Plano de Execução Minucioso — ICT Master Suite v7.0.0

> **INSTRUÇÃO PARA A IA EXECUTORA (ANTIGRAVITY):**
> Este documento é o seu roteiro de execução. Leia-o integralmente, junto com `000_CONTEXTO_GLOBAL_E_HISTORICO.md` e `001_REGRAS_DE_DESENVOLVIMENTO_AI.md`, **antes de escrever qualquer linha de código**.
> Execute **uma fase por vez**, na ordem. Ao final de cada fase, PARE e reporte os critérios de aceite. Não avance sem validação.

---

## 👥 0. Papéis e Protocolo de Trabalho

| Papel | Quem | Responsabilidade |
| :--- | :--- | :--- |
| **Product Owner / Decisor** | Franklin | Define prioridade, valida em bancada, aprova cada fase. |
| **Analista Sênior / Revisor** | Claude | Arquitetura, caça de bugs, revisão de código, testes de paridade. |
| **Executor / Implementador** | Antigravity | Escreve o código C#, roda os testes, gera os builds. |

**Regra de ouro do fluxo:** Antigravity implementa uma fase → Franklin traz o diff/resultado para revisão → Claude revisa e aponta defeitos → Antigravity corrige → só então avança.

---

## 🎯 1. Objetivo e Justificativa Técnica

Reescrever o ICT Master Suite em **C# / .NET 8 / WPF**, mantendo **paridade funcional 100%** com a v6.1.0 em Python.

### Por que migrar (ganhos mensuráveis)

| Ganho | Hoje (Python/PyQt5) | Alvo (C#/.NET 8) |
| :--- | :--- | :--- |
| **Startup** | EXE onefile 38 MB descompacta no `%TEMP%` a cada execução: **3–8 s no frio** | Single-file trimmed ~15 MB: **< 500 ms** |
| **Varredura SMB** | `entry.stat().st_mtime` = **1 round-trip de rede por arquivo** | `FileSystemEnumerable` lê `mtime`/size do `WIN32_FIND_DATA`: **custo zero** |
| **Paralelismo** | `QThread` real, mas o **GIL serializa** parsing/regex | `Parallel`/`Channel<T>`: paralelismo verdadeiro |
| **Antivírus corporativo** | PyInstaller onefile é rotineiramente **quarentenado** | .NET assinado passa limpo |
| **Memória (tray 24/7)** | ~120–180 MB RSS | ~40–60 MB |
| **Cópia TRI** | Polling de **15 s** re-escaneando o diretório inteiro | `FileSystemWatcher`: **cópia em < 1 s** |
| **Limite do visualizador** | `QTextEdit` engasga → logs > 1 MB são **bloqueados** | AvalonEdit virtualizado: **abre 50 MB+** |
| **Regex** | `re` interpretado, recompilado a cada bloco | `[GeneratedRegex]` compilado em IL |

### Onde o ganho é ~zero (não gastar esforço prometendo isso)
SQLite (`Microsoft.Data.Sqlite` é equivalente), leitura de um log individual (I/O puro), e velocidade de desenvolvimento — C# é mais verboso.

---

## 🐛 2. ACHADOS DA AUDITORIA (corrigir ANTES de portar)

> Estes defeitos existem **hoje, em produção**. Portar o código sem corrigi-los significa **replicar bugs em C#**.

### 🔴 BUG-01 — CRÍTICO: configuração perdida a cada reinício do EXE
**Arquivo:** `models.py:19`
```python
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ict_config.json')
```
A função `get_base_path()` (`models.py:13`) foi escrita **exatamente** para tratar o modo `frozen` do PyInstaller — **e nunca é usada em lugar nenhum**. No EXE `--onefile`, `__file__` aponta para a pasta temporária `_MEIxxxxx`. Resultado: **o `ict_config.json` é gravado no `%TEMP%` e se perde a cada reinício.** O operador reconfigura os caminhos de rede e perde tudo na próxima abertura.
**Correção:** `CONFIG_FILE = os.path.join(get_base_path(), 'ict_config.json')`.
**No C#:** usar `AppContext.BaseDirectory` (ou `%ProgramData%\ICTMasterSuite\` se o EXE ficar em `Program Files`, que é somente-leitura).

### 🔴 BUG-02 — Data exibida do log Agilent está errada
**Arquivo:** `models.py:216-220` (`parse_agilent_txt`)
A data vem de `os.path.getmtime()` — ou seja, **quando o arquivo foi copiado/tocado**, não quando a placa foi testada. O log real contém a data verdadeira do teste na linha 4:
```
Wed Jan 05 03:47:06 2005
```
O técnico vê a data errada no Card de Diagnóstico. Para TRI CSV a data é extraída corretamente do nome do arquivo.
**Correção:** fazer parse da linha de data do cabeçalho Agilent (formato `ddd MMM dd HH:mm:ss yyyy`, `CultureInfo.InvariantCulture`) com **fallback** para `mtime` se ausente/corrompida.

### 🟠 BUG-03 — Serial vira `"f"` em logs `.log` da Agilent
**Arquivo:** `models.py:222-223`
```python
partes = nome_arquivo.split('_')
if partes: dados["serial"] = partes[0]
```
Os arquivos na **raiz** de `ict01` seguem o padrão `f_6783001K4A_050724065834ICT02651.log` (formato BTEST bruto da máquina). `split('_')[0]` retorna **`"f"`** como serial. Hoje isso está latente porque a busca aponta para `ict01/defeitos`, mas `BuscaThread` aceita `.log` (`threads.py:69`) — **basta alguém apontar o caminho para a raiz de `ict01` e o parser quebra silenciosamente.**
**Correção:** detectar o prefixo `f_`/`p_` e o formato BTEST (`{@BATCH|`) como um terceiro tipo de log, ou no mínimo pular o prefixo antes do `split`.

### 🟠 BUG-04 — Toda a camada SQLite é código morto
`salvar_falha_db` e `init_db` são importados em `threads.py:11-12` e **nunca chamados por ninguém**. O banco é criado na rede (`init_db()` roda no import, `models.py:365`) e **permanece vazio para sempre**. Pior: esse `init_db()` no import **bloqueia o startup por ~1 s** quando a rede está fora (timeout do socket).
**Decisão necessária do Franklin:** ➊ implementar de fato a persistência de falhas (histórico/BI), ou ➋ remover a camada inteira. **Não portar código morto para C#.**

### 🟡 BUG-05 — `conectar_banco()` relê o JSON do disco a cada conexão
`models.py:59` chama `carregar_config()` dentro de cada abertura de conexão.
**Correção:** carregar a config uma vez em memória (no C#: `IOptionsMonitor<T>` singleton).

### 🟡 BUG-06 — Limite de profundidade `depth > 2` esconde logs
`threads.py:51` — gambiarra de performance que faz a busca **ignorar silenciosamente** logs em subpastas mais profundas. O `FileSystemEnumerable` do .NET torna isso desnecessário.

### 🟡 BUG-07 — `terminate()` em thread de I/O
`ui_main.py:726` mata a `FileLoaderThread` à força, podendo deixar handle de arquivo aberto.
**Correção:** `CancellationToken` cooperativo.

### 🟡 BUG-08 — Teste que não testa nada
`test_threads.py:106` (`test_copy_fail_files`) **reimplementa a lógica de cópia inline** dentro do próprio teste, em vez de exercitar `TRICopyThread`. Ele passaria mesmo que `TRICopyThread` estivesse completamente quebrada. **Falso senso de segurança.**

---

## 🏛️ 3. Arquitetura Alvo

**Stack:** .NET 8 · WPF · AvalonEdit · Microsoft.Data.Sqlite · System.Text.Json · CommunityToolkit.Mvvm

> **Por que WPF** e não WinForms/Avalonia: o `style.qss` mapeia quase 1:1 para `ResourceDictionary`/`Style` XAML (WinForms não tem equivalente) e o `QSplitter` vira `GridSplitter` nativo. Avalonia só se um dia precisar de Linux — o alvo é Windows, então WPF é o caminho mais curto e o de menor startup.

### Estrutura da Solution
```
ICTMasterSuite.sln
├── src/
│   ├── ICTMasterSuite.Core/            ← SEM dependência de UI. 100% testável.
│   │   ├── Models/         LogMetadata.cs, Diagnostico.cs, AppConfig.cs, LogHit.cs
│   │   ├── Parsing/        LogTypeDetector.cs, TriCsvParser.cs, TriTxtParser.cs,
│   │   │                   AgilentReportParser.cs, AgilentBtestParser.cs,
│   │   │                   DiagnosticoExtractor.cs, ComponentGrouper.cs
│   │   ├── Services/       LogSearchService.cs, TriCopyService.cs,
│   │   │                   NetworkMonitorService.cs, ConfigService.cs,
│   │   │                   FalhaRepository.cs, LaudoBuilder.cs
│   │   └── Abstractions/   IFileSystem.cs, IClock.cs   ← testabilidade
│   └── ICTMasterSuite.App/             ← WPF
│       ├── Views/          MainWindow, FinderView, ConsoleView, ConfigView
│       ├── ViewModels/     MainViewModel, FinderViewModel, ...
│       ├── Highlighting/   LogColorizer.cs (AvalonEdit)
│       ├── Themes/         Styles.xaml  ← porte do style.qss
│       └── Infra/          TrayIconManager.cs, StartupRegistry.cs, CrashLogger.cs
└── tests/
    └── ICTMasterSuite.Tests/           ← xUnit + FluentAssertions
        ├── Parity/         Testes de paridade contra o golden dataset
        └── Fixtures/
```

### Mapeamento função a função (Python → C#)

| Python | C# |
| :--- | :--- |
| `QThread` + `pyqtSignal` | `async Task` + `IProgress<T>` / `Channel<T>` |
| `BuscaThread._scandir_recursivo` | `FileSystemEnumerable<LogHit>` com `RecurseSubdirectories`, `IgnoreInaccessible`, `AttributesToSkip` |
| `arquivo_encontrado.emit()` | `IAsyncEnumerable<LogHit>` consumido com `await foreach` |
| `self.rodando = False` / `parar()` | `CancellationToken` |
| `TRICopyThread` (polling 15 s) | `FileSystemWatcher` + `Channel` com debounce |
| `_wait_file_stable` (6×350 ms cego) | `File.Open(..., FileShare.None)` — detecta lock direto |
| `NetworkMonitorThread` | `PeriodicTimer` + `TcpClient.ConnectAsync` c/ timeout |
| `QSyntaxHighlighter` | AvalonEdit `DocumentColorizingTransformer` (**virtualizado**) |
| `dict` de `meta`/`diagnostico` | `record LogMetadata(...)` / `record Diagnostico(...)` |
| `re.findall/search` | `[GeneratedRegex(...)] private static partial Regex` |
| `winreg` (`ui_main.py:30`) | `Microsoft.Win32.Registry` — API quase idêntica |
| `QSystemTrayIcon` | `System.Windows.Forms.NotifyIcon` (via `UseWindowsForms=true`) |
| `sqlite3` | `Microsoft.Data.Sqlite` (mesmo engine, mesmo WAL) |
| `json` + `DEFAULT_CONFIG` | `System.Text.Json` source-generated + `record` com defaults |
| `QMessageBox` / `QFileDialog` | `MessageBox` / `Microsoft.Win32.OpenFileDialog` |
| `sys.excepthook` | `AppDomain.UnhandledException` + `DispatcherUnhandledException` |
| PyInstaller `.spec` | `dotnet publish -r win-x64 -p:PublishSingleFile=true` |

---

## 🔒 4. Diretivas Não-Negociáveis (herdadas + novas)

As 5 Regras de Ouro do documento 000 **permanecem válidas e obrigatórias** na versão C#:

1. **🔒 Log completo na íntegra** — nenhum filtro pode alterar/ocultar o arquivo original ao carregar.
2. **🔒 Executável único sem console** — `PublishSingleFile`, `OutputType=WinExe`.
3. **🔒 Preservação dos servidores de teste** — **NUNCA** alterar, mover ou deletar em `ict01`/`ict02`. Só leitura e cópia.
4. **🔒 Versionamento automático** — build gera `releases/ICT_Master_Suite_vX.Y.Z.exe`.
5. **🔒 Isolamento de exceções** — log em formato desconhecido exibe texto bruto, nunca derruba o app.

**Novas diretivas para o C#:**

6. **🔒 `ICTMasterSuite.Core` não referencia WPF.** Nenhum `using System.Windows` no Core. Se precisar, a arquitetura está errada.
7. **🔒 Zero I/O de rede na UI thread.** Todo acesso a `//147.1.0.95` é `async` com `CancellationToken`.
8. **🔒 Nenhum `catch { }` silencioso.** Toda exceção engolida vai para o Console do Sistema com nível `ERRO`.
9. **🔒 Paridade provada por teste, não por inspeção visual.** Ver Fase 1.

---

## 🚦 5. FASES DE EXECUÇÃO

### ▶️ FASE 0 — Estabilizar o Python (baseline confiável) — *~0,5 dia*

> **Por quê primeiro:** não se mede paridade contra uma referência com bugs. E o BUG-01 prejudica seus usuários **hoje** — corrigir custa 1 linha.

**Tarefas:**
1. Corrigir **BUG-01** (`CONFIG_FILE` usando `get_base_path()`).
2. Corrigir **BUG-05** (cache da config em memória).
3. Mover `init_db()` do import para chamada preguiçosa (**BUG-04**), eliminando o travamento de 1 s no startup.
4. Decidir com o Franklin: SQLite vira funcionalidade real ou é removido?
5. Bump `APP_VERSION` → `"6.2.0"`, atualizar doc 000, rodar testes, `build_release.py`, commit.

**Critério de aceite:** o EXE em `releases/` preserva `ict_config.json` entre reinícios (testar: abrir → mudar um caminho → salvar → fechar → reabrir → caminho persistiu).

---

### ▶️ FASE 1 — Golden Dataset e Testes de Paridade — *~1 dia*

> **Esta é a fase mais importante do plano.** É o que transforma "ficou igual, eu acho" em "ficou igual, está provado". Sem ela, a migração é um salto no escuro.

Você tem **8.814 arquivos reais** em `base de conhecimento/` (`ict02/` = TRI CSV, `ict01/defeitos/` = Agilent report_out, `ict01/*.log` = BTEST bruto). É um corpus de teste excepcional — use-o.

**Tarefas:**
1. Escrever `gerar_golden.py` (Python) que, para **cada** arquivo do corpus, executa `parse_metadata_inteligente` + `extrair_diagnostico_inteligente` + `agrupar_componentes_inteligente` e serializa o resultado em `tests/golden/<nome>.json`.
2. Commitar `tests/golden/` no Git. **Este é o contrato de paridade.**
3. Na Fase 3, o C# roda o mesmo corpus e **cada JSON deve bater byte a byte** (salvo divergências intencionais documentadas, ex.: correção do BUG-02).

**Formatos reais confirmados (use como fixtures nomeadas):**

*TRI CSV* — `202607240724386783001TDBips3_15_ian8FAIL.csv`:
```
1,176,ips3_15_ian8,6783001TDB,20260724,072438,F,0,1,,FPPFPPPPPPNN,1,F,3,20260724,072430,0,,,0,0

 564, PC1100,     1.00uF,    24.10uF,  80.0,  80.0, 0, C, 654, 613, A1, 0.0127637uF, 1
 1357, PR1101,    1.000  ,    1.000  ,  10.0,  10.0, 0, J, 798, 613, A1, 4.0000000  , 1
```
→ linha 0 = metadados (modelo `[2]`, serial `[3]`, data `[4]`, hora `[5]`, status `[6]`); demais = falhas (componente `[1]`, coordenada `[10]`).
⚠️ Note que o parser atual **ignora o conteúdo** e extrai tudo do nome do arquivo. Funciona para o padrão atual, mas a linha 0 é a fonte autoritativa — considerar usá-la como fallback.

*Agilent report_out* — `6783000Z6C_report_out_loq15_irx9.txt`:
```
DIGIBOARD-LOQ 15 IRX9-ATESS-JUL 2024-BRAZIL-JCS
Board Version:  5b21d46524
Wed Jan 05 03:47:06 2005          ← data REAL do teste (hoje ignorada, BUG-02)
h20_sp HAS FAILED
Measured:   1.8811M
Serial #: 6783000Z6C
```

*Agilent BTEST bruto* — `f_6783001K4A_050724065834ICT02651.log`:
```
{@BATCH|t14_gen6_intel||4086|1||btest|050724065740~16|...
{@BTEST|6783001K4A|06|050724065810|...
{@BLOCK|c15038|00
```
→ formato totalmente diferente, hoje mal-parseado (BUG-03).

**Casos de borda obrigatórios no conjunto de testes:**
- Arquivo vazio / só whitespace
- Arquivo com BOM UTF-8
- CSV com linha 0 malformada
- Nome sem os 14 dígitos de timestamp
- Serial com menos de 10 caracteres
- Log > 1 MB e log > 10 MB
- Componente terminando em `/` (o `rstrip('/')` de `models.py:312`)
- Coordenada fora do padrão `^[A-Z][0-9]+$`

**Critério de aceite:** `tests/golden/` commitado com ≥ 8.000 JSONs; script reprodutível.

---

### ▶️ FASE 2 — Esqueleto da Solution + Core sem UI — *~1 dia*

**Tarefas:**
1. `dotnet new sln`; criar `ICTMasterSuite.Core` (classlib, `net8.0`), `ICTMasterSuite.App` (WPF, `net8.0-windows`), `ICTMasterSuite.Tests` (xUnit).
2. `Directory.Build.props`: `<Nullable>enable</Nullable>`, `<TreatWarningsAsErrors>true</TreatWarningsAsErrors>`, `<LangVersion>latest</LangVersion>`.
3. Definir os `record` de domínio — **imutáveis, substituindo os `dict`**:
   ```csharp
   public record LogMetadata(string Tipo, string Data, string Serial,
                             string Modelo, string Status, string Cor);
   public record Diagnostico(string Status, IReadOnlyList<string> Componentes,
                             IReadOnlyList<string> Coordenadas, IReadOnlyList<string> Curtos,
                             IReadOnlyList<string> PinosAbertos, IReadOnlyList<string> Secoes,
                             int TotalErros);
   ```
4. `ConfigService` com `AppConfig` record + defaults idênticos ao `DEFAULT_CONFIG`, gravando em `AppContext.BaseDirectory` (**BUG-01 já corrigido por construção**).
5. Abstrair `IFileSystem`/`IClock` para os testes não dependerem de rede.

**Critério de aceite:** `dotnet build` limpo, zero warnings; `dotnet test` roda (mesmo sem testes ainda).

---

### ▶️ FASE 3 — Portar os Parsers + Provar Paridade — *~2 dias*

> **Fase de maior risco.** `extrair_diagnostico_inteligente` (`models.py:282`) tem regras densas e frágeis: índices fixos de CSV (`partes[10]`), fatias posicionais (`resto[:10]`), `rstrip('/')`. É onde uma migração quebra silenciosamente.

**Tarefas:**
1. Portar, na ordem: `LogTypeDetector` → `TriCsvParser` → `TriTxtParser` → `AgilentReportParser` → `ComponentGrouper` → `DiagnosticoExtractor`.
2. Todos os regex como `[GeneratedRegex]`.
3. **Atenção a armadilhas de tradução Python → C#:**
   - `resto[:10]` em Python **não estoura** se a string for menor; `Substring(0,10)` em C# **lança exceção**. Usar `..Math.Min(10, s.Length)`.
   - `str.isdigit()` do Python é Unicode-aware (aceita `²`, `٣`); use `char.IsAsciiDigit` para o comportamento pretendido.
   - `re.IGNORECASE` + `.upper()` do Python é culture-invariant; em C# use `StringComparison.OrdinalIgnoreCase` — **nunca** `ToUpper()` sem cultura (o famoso problema do `i` turco).
   - `splitlines()` do Python quebra em `\r\n`, `\n`, `\r`, `\v`, `\f`, `\x1c`… `Split('\n')` **não**. Usar leitor de linhas equivalente.
   - Ordem de inserção: o Python preserva a ordem dos `dict`/listas e o Card depende disso. Usar `List<T>` + checagem de duplicata, **não** `HashSet`.
4. Escrever `ParityTests.cs`: itera o golden dataset, compara campo a campo, **falha listando o arquivo divergente**.

**Critério de aceite:** **100% dos golden JSONs batem**, exceto divergências intencionais explicitamente listadas e aprovadas (BUG-02 e BUG-03 mudam saída — documentar cada uma).

---

### ▶️ FASE 4 — Serviços (busca, cópia, rede) — *~2 dias*

**Tarefas:**
1. `LogSearchService` com `IAsyncEnumerable<LogHit>` — **aqui mora o maior ganho de performance**:
   ```csharp
   var opts = new EnumerationOptions {
       RecurseSubdirectories = true,      // elimina BUG-06
       IgnoreInaccessible = true,
       AttributesToSkip = FileAttributes.System | FileAttributes.ReparsePoint,
       BufferSize = 65536
   };
   // FindTransform lê nome + mtime + size do WIN32_FIND_DATA: ZERO round-trip extra
   ```
   Manter as regras atuais: extensões `.csv/.dcl/.txt/.log`, pular `pass`/`p_`, pular `defeitos_tri` aninhado, ordenar por `mtime` decrescente.
2. `TriCopyService` com `FileSystemWatcher` (+ varredura inicial de reconciliação, pois o Watcher perde eventos se o buffer estourar). Pausar/retomar/reiniciar preservados.
3. `NetworkMonitorService` com `PeriodicTimer`, emitindo só na **mudança** de estado (como hoje).
4. Testes: busca em diretório temporário, cópia respeitando **Regra de Ouro nº 3** (assertar que a origem permanece intacta).

**Critério de aceite:** benchmark documentado da varredura Python vs C# no mesmo caminho de rede (esperado 3–10×). Teste provando que nenhum arquivo de origem é alterado/removido.

---

### ▶️ FASE 5 — UI WPF — *~4 dias*

**Tarefas:**
1. `MainWindow` com `TabControl`: 🔍 Finder Logs · 🖥️ Console do Sistema · ⚙️ Configurações. Layout idêntico, `GridSplitter` 300/800.
2. Porte de `style.qss` → `Themes/Styles.xaml`. Manter a paleta exata (`#d63384`, `#0d6efd`, `#fd7e14`, `#6f42c1`, `#20c997`, `#dc3545`, `#198754`, `#856404`).
3. **Card de Diagnóstico:** hoje é HTML num `QLabel` (`ui_main.py:814`). Em WPF vira **XAML nativo com data binding** — mais rápido e sem risco de injeção de HTML (o conteúdo do log hoje entra sem escape; note que `html` é importado em `models.py:8` e `ui_main.py:6` e **nunca usado**).
4. **Visualizador:** AvalonEdit + `LogColorizer`. Portar os 7 padrões de realce + destaque do serial buscado.
   → **Remover o limite de 1 MB** (`ui_main.py:829`): AvalonEdit virtualiza. Confirmar com Franklin — é uma melhoria funcional, não uma quebra de paridade.
5. Filtro "👁️ Mostrar Apenas Falhas" — portar a lógica de `renderizar_conteudo_log` (`ui_main.py:736`) **exatamente**, incluindo o tratamento distinto TRI vs Agilent.
6. Laudo/Exportação: `LaudoBuilder` no Core gerando **string idêntica** à atual (com o cabeçalho `====`). Testar com comparação exata de string.
7. Atalhos F5/ESC, tray icon, `closeEvent` → minimizar para bandeja, auto-start via registro.

**Critério de aceite:** comparação lado a lado (screenshot Python vs C#) dos 3 tabs. Laudo gerado pelo C# **idêntico** ao do Python para os mesmos 20 logs de amostra.

---

### ▶️ FASE 6 — Build, Publish e Release — *~1 dia*

```bash
dotnet publish src/ICTMasterSuite.App -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true -p:EnableCompressionInSingleFile=true
```

**Tarefas:**
1. Script `build_release.ps1` espelhando o `build_release.py`: mata o processo, limpa, publica, copia para `releases/ICT_Master_Suite_vX.Y.Z.exe`.
2. Versão única em `Directory.Build.props` (`<Version>7.0.0</Version>`), lida em runtime via `Assembly` — substitui `APP_VERSION`.
3. Ícone `icon.ico` embutido; `ApplicationIcon` no csproj.
4. ⚠️ **Não usar Native AOT nesta versão** — WPF não suporta. Trimming em WPF também exige cautela (reflexão do XAML): comece **sem** `PublishTrimmed`, meça, só então avalie.
5. Avaliar assinatura de código (resolve de vez o atrito com o antivírus corporativo).

**Critério de aceite:** EXE único, sem console, iniciando em < 1 s em máquina de bancada fria.

---

### ▶️ FASE 7 — Validação em Bancada e Cutover — *~1 dia*

> **Regra:** rodar as duas versões **em paralelo** por pelo menos uma semana. Não desligue o Python no dia do lançamento.

**Checklist de validação com o operador real:**
- [ ] Busca por serial via **leitor de código de barras** (o fluxo real de uso)
- [ ] Streaming aparece durante a varredura, sem congelar
- [ ] Filtro por data (24 h / 7 d / 30 d) confere com o Python
- [ ] Card de Diagnóstico idêntico em 20 logs FAIL reais
- [ ] Cópia TRI funcionando (agora < 1 s em vez de 15 s)
- [ ] Comportamento com a **rede caindo no meio da busca**
- [ ] Config persistindo entre reinícios
- [ ] Auto-start com Windows + bandeja
- [ ] Rodar 24 h em bandeja e conferir memória (não deve crescer)

---

## 📅 6. Cronograma

| Fase | Descrição | Esforço |
| :--- | :--- | :--- |
| 0 | Estabilizar Python | 0,5 dia |
| 1 | Golden dataset + paridade | 1 dia |
| 2 | Esqueleto + Core | 1 dia |
| 3 | Parsers + paridade provada | 2 dias |
| 4 | Serviços | 2 dias |
| 5 | UI WPF | 4 dias |
| 6 | Build/Release | 1 dia |
| 7 | Validação em bancada | 1 dia |
| | **TOTAL** | **~12,5 dias** |

---

## ⚠️ 7. Matriz de Riscos

| Risco | Prob. | Impacto | Mitigação |
| :--- | :--- | :--- | :--- |
| Parser C# diverge sutilmente do Python | **Alta** | **Alto** | Golden dataset da Fase 1 — inegociável |
| Diferença de encoding (logs em cp1252?) | Média | Alto | Testar detecção de encoding no corpus; Python usa `errors='ignore'` |
| AvalonEdit com curva de aprendizado | Média | Médio | Fallback: `TextBox` simples na v7.0, realce na v7.1 |
| WPF + trimming quebrando por reflexão | Média | Médio | Não usar `PublishTrimmed` na primeira versão |
| Antivírus bloqueia o EXE novo | Baixa | Alto | Assinar o código; homologar com TI antes |
| Escopo inflar ("já que estamos reescrevendo…") | **Alta** | **Alto** | **Paridade primeiro.** Toda ideia nova vai para backlog v7.1 |

> **Sobre o último risco:** é o que mais mata reescritas. A v7.0.0 deve fazer **exatamente** o que a v6.1.0 faz — nada a mais. Melhorias entram na v7.1.

---

## 📌 8. Decisões Pendentes do Franklin

1. **SQLite (BUG-04):** implementar de verdade ou remover? *(recomendação: remover na v7.0, reintroduzir na v7.1 se houver demanda real de histórico/BI)*
2. **Limite de 1 MB no visualizador:** remover na migração? *(recomendação: sim — é limitação do QTextEdit, não regra de negócio)*
3. **BUG-02 (data do Agilent):** corrigir? Muda a saída e **quebra paridade de propósito**. *(recomendação: sim, corrigir — é dado errado na tela do técnico)*
4. **Serviço de cópia TRI:** continua dentro do app ou vira **Windows Service** independente? *(recomendação: manter no app na v7.0; Windows Service é candidato forte para v7.1, pois hoje a cópia só roda se alguém abriu o programa)*

---

## 🤖 9. Protocolo para o Antigravity

**Ao iniciar cada fase, o Antigravity deve:**
1. Reler este documento + docs 000 e 001.
2. Declarar qual fase vai executar e o que **não** vai fazer (escopo negativo).
3. Implementar **somente** aquela fase.
4. Rodar `dotnet build` (zero warnings) e `dotnet test` (tudo verde).
5. Reportar os critérios de aceite, com evidências (saída dos testes, benchmark, screenshot).
6. **PARAR** e aguardar revisão do Claude antes da fase seguinte.

**Proibido ao Antigravity:**
- ❌ Pular a Fase 1 (golden dataset) — sem ela não há como provar paridade.
- ❌ "Melhorar" a lógica de parsing durante o porte. Porte fiel; melhorias em fase própria.
- ❌ Adicionar funcionalidades não descritas aqui.
- ❌ Mexer em qualquer coisa dentro de `//147.1.0.95/teste_ict/ict01` ou `ict02` além de leitura/cópia.
- ❌ Deletar o código Python. Ele é a referência viva até a Fase 7 terminar.
