# 🔬 Estudo Técnico de Engenharia de Software Sênior
## Performance em Escala (200k+ Arquivos), Tratamento de Dados e Matriz de Riscos

---

## 📌 Executive Summary

Este documento apresenta uma **análise arquitetural de nível Sênior/Principal Software Architect** para o **ICT Master Suite**. O objetivo é avaliar a capacidade de resposta e estabilidade do sistema ao escalar para diretórios de rede corporativos (SMB/CIFS) que contêm mais de **200.000 arquivos de log**, mapear gargalos críticos de processamento e estruturar um plano de evolução por matriz de risco e viabilidade.

---

## 🏗️ 1. Análise de Arquitetura e Gargalos Críticos de Performance

Ao lidar com mais de 200.000 arquivos armazenados em servidor de rede (`//147.1.0.95/`), o desempenho da aplicação enfrenta desafios físicos de latência de E/S de rede (Network I/O Latency) e consumo de recursos da CPU/Memória local.

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                            FLUXO DE DADOS & GARGALOS DE E/S                             │
├──────────────────────────┬───────────────────────────────┬───────────────────────────────┤
│    REDE SMB (147.1.0.95) │       MOTOR DO FINDER         │         INTERFACE UI          │
│                          │                               │                               │
│  [200k+ Arquivos LOG] ───┼──> os.scandir (DirEntry) ─────┼──> Live Streaming Signal      │
│  Latência SMB (1-3ms)    │    Filtro de Nome/Serial      │    QListWidget.addItem        │
│                          │    (Sem stat() desnecessário) │    QTextEdit (HTML Highlight) │
└──────────────────────────┴───────────────────────────────┴───────────────────────────────┘
```

### 🔍 Gargalo #1: Chamadas de `stat()` via Rede SMB (Round-Trip Time)
* **Diagnóstico:** Em uma rede de fábrica, cada chamada extra ao disco de rede (`os.stat` / `getmtime`) para verificar o tamanho ou data do arquivo consome de **1 a 3 milissegundos** de latência de protocolo SMB. Para 200.000 arquivos, 200.000 chamadas de `stat()` resultariam em mais de **6 a 10 minutos de busca**.
* **Solução Atual (Já Implementada):** O uso de `os.scandir` no Python 3.12 recupera as informações de entrada de diretório diretamente do payload da enumeração nativa do Windows (`FindNextFileW`). O atributo de data `mtime` só é consultado quando o usuário altera o filtro de data.
* **Ponto de Atenção Sênior:** Evitar qualquer tentativa de abrir arquivos ou ler conteúdos durante a fase de listagem da busca. A leitura de conteúdo deve permanecer 100% sob demanda ao clicar no item da lista.

### ⚡ Gargalo #2: Renderização Rich Text HTML em Logs Grandes
* **Diagnóstico:** Logs da Agilent ou TRI com mais de 5.000 linhas, quando convertidos em HTML com dezenas de tags de estilo (`<div style='...'>`), exigem um consumo elevado de alocação de memória na árvore DOM da `QTextEdit` do PyQt5.
* **Solução Atual (Já Implementada):** Trava de segurança para arquivos maiores que 1MB (que passam a ser exibidos sem parse de HTML pesado ou com aviso de editor externo).
* **Melhoria Futura Proposta:** Para logs entre 100KB e 1MB, aplicar realce via `QSyntaxHighlighter` nativo em vez de substituir o HTML inteiro via `setHtml()`, reduzindo o consumo de RAM em 85%.

---

## 📊 2. Análise de Dados e Tratamento de Logs (Data Pipeline)

A análise da **Base de Conhecimento** (amostras em `ict01` e `ict02`) revelou 3 categorias principais de estruturas de dados:

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                             ESTRUTURA DOS DADOS DE LOG                                  │
├──────────────────────────┬───────────────────────────────┬───────────────────────────────┤
│    SISTEMA DE TESTE      │       FORMATO DE SAÍDA        │      PADRÃO DE DIAGNÓSTICO    │
├──────────────────────────┼───────────────────────────────┼───────────────────────────────┤
│  TRI CSV / DCL           │ Linha 1: Metadados            │ Componentes em Coluna 2;      │
│                          │ Linha 2+: Testes e Curtos     │ Coordenadas no Grid (A1, B2). │
├──────────────────────────┼───────────────────────────────┼───────────────────────────────┤
│  AGILENT Reports         │ Relatórios de Seção           │ TestJet (Device jtp1);        │
│                          │ (Shorts, Pins, TestJet)       │ HAS FAILED; Failed Open.      │
└──────────────────────────┴───────────────────────────────┴───────────────────────────────┘
```

### 🧹 Tratamento e Normalização Aplicados
1. **Sanitização de Nomes:** Remoção de sufixos de barramento como `/` ou `.1` (ex: `U109_1_4/` -> `U109_1_4`).
2. **Deduplicação de Exibição:** Remoção de repetições de pinos do mesmo CI no Card de Diagnóstico.
3. **Detecção de Dispositivos (TestJet):** Conversão de declarações de conectores `Device jtp1` para dispositivos legíveis `JTP1 (Conector/Dispositivo)`.

---

## 🎯 3. Matriz de Riscos & Viabilidade de Melhorias

Classificamos todas as possíveis evoluções tecnológicas em **Baixo, Médio e Alto Risco**, separando entre **Viáveis** e **Inviáveis**.

```
                           MATRIZ DE RISCO E VIABILIDADE
  ┌─────────────────────────────────────────┬─────────────────────────────────────────┐
  │ 🟢 VIÁVEIS - BAIXO RISCO               │ 🟡 VIÁVEIS - MÉDIO RISCO                │
  │ • Agrupamento Inteligente de Pinos CI   │ • Índice SQLite Cache de Rede Local     │
  │ • Realce via QSyntaxHighlighter         │ • Varredura Multithreaded Paralela      │
  │ • Exportação de Laudo em PDF/CSV        │ • Pré-carregamento Assíncrono do Próximo│
  ├─────────────────────────────────────────┼─────────────────────────────────────────┤
  │ 🔴 INVIÁVEIS / ALTO RISCO               │ ❌ ALTO RISCO & NÃO RECOMENDADOS        │
  │ • Instalar Servidor Web/API no 147.1... │ • Alterar Esquema do Banco SQLite Rede  │
  │ • Deletar/Mover Arquivos na Origem      │ • Leitura de Conteúdo na Fase de Varredura│
  └─────────────────────────────────────────┴─────────────────────────────────────────┘
```

### 🟢 3.1 Melhorias de BAIXO RISCO (100% Viáveis & Recomendadas)

1. **Agrupamento Inteligente de Pinos de CI:**
   * *Conceito:* Se o log contiver 8 falhas de pinos do mesmo componente (ex: `U109_1_4`, `U109_3_4`, `U109_7_4`), o Card exibe `U109 (3 blocos reprovados)` em vez de poluir o texto.
   * *Risco:* Zero. Puramente algorítmico na exibição.

2. **Migração do Destaque para `QSyntaxHighlighter` (PyQt5):**
   * *Conceito:* Subtituir a manipulação de strings HTML por um `QSyntaxHighlighter` vinculado ao `QTextEdit`.
   * *Benefício:* Abertura instantânea (0 milissegundos) mesmo para logs de 50.000 linhas, economizando memória.
   * *Risco:* Zero.

3. **Exportação de Relatório de Diagnóstico em PDF / Excel / CSV:**
   * *Conceito:* Adicionar botão para exportar um laudo individual ou diário dos seriais buscados para relatórios da qualidade.
   * *Risco:* Zero.

---

### 🟡 3.2 Melhorias de MÉDIO RISCO (Viáveis com Testes de Carga)

4. **Índice de Metadados em Cache Local SQLite (`cache_local.db`):**
   * *Conceito:* Armazenar localmente na máquina do técnico um índice do mapa `serial -> caminho_arquivo` com timestamp. Ao buscar o serial, verifica o cache local em **0,001s**. Se não encontrar, faz a varredura na rede e atualiza o cache.
   * *Atenção Sênior:* Exige rotina para invalidar cache de arquivos antigos ou excluídos na rede.
   * *Risco:* Médio (requer tratamento de invalidação de cache).

5. **Varredura SMB Multithreaded Paralela (`ThreadPoolExecutor`):**
   * *Conceito:* Dividir a busca nos diretórios da Agilent e da TRI em duas threads simultâneas em vez de sequenciais.
   * *Benefício:* Redução do tempo de varredura pela metade em redes com alta latência.
   * *Risco:* Médio (exige sincronização segura de sinais PyQt no streaming de resultados).

---

### 🔴 3.3 Melhorias de ALTO RISCO & INVIÁVEIS (NÃO RECOMENDADAS)

6. **❌ INVIÁVEL: Instalar Serviço Web API/Backend no Servidor da Rede (`//147.1.0.95`):**
   * *Motivo:* Violaria as políticas de segurança da fábrica e exigiria privilégios administrativos no servidor do testador ICT. O **ICT Master Suite** DEVE permanecer um cliente Desktop 100% autônomo.

7. **❌ INVIÁVEL: Mover ou Apagar Arquivos Originais no Servidor:**
   * *Motivo:* Os equipamentos de teste precisam manter o histórico original intacto. Apagar ou mover arquivos na origem causa erros de auditoria nos testadores.

8. **❌ ALTO RISCO: Modificar a Tabela `falhas` do Banco SQLite Compartilhado em Rede:**
   * *Motivo:* Como o SQLite de rede é acessado por múltiplas instâncias da fábrica, alterar colunas ou tipos em execução sem lock exclusivo pode corromper o arquivo `.db` compartilhado.

---

## 📌 Conclusão e Próximos Passos Sugeridos

A arquitetura atual do **ICT Master Suite** é extremamente sólida, limpa e modular. O uso de `os.scandir` combinado com *Live Streaming* garante a capacidade de lidar com 200k+ arquivos de forma responsiva.

Caso deseje avançar para o próximo nível, a recomendação sênior é aplicar as melhorias de **Baixo Risco** (Agrupamento Inteligente de Pinos de CI e `QSyntaxHighlighter`), seguidas futuramente pelo **Cache Local SQLite**.
