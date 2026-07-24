# 📘 Plano de Inteligência e Diagnóstico de Logs ICT (Agilent & TRI)

Este documento reúne a análise técnica aprofundada dos arquivos reais de log presentes na **Base de Conhecimento** (`base de conhecimento/ict01` e `base de conhecimento/ict02`) e o planejamento detalhado das melhorias de visualização e extração de dados para o **ICT Master Suite**.

---

## 🔬 1. Anatomia e Estrutura dos Arquivos de Log ICT

Após a inspeção minuciosa dos logs reais utilizados na linha de produção, mapeamos com precisão como cada sistema registra suas informações de teste:

### A. Logs do TRI (`ict02`) - Padrão CSV (`...FAIL.csv` / `...PASS.csv`)
Os logs do TRI utilizam uma estrutura CSV tabulada de alta densidade de dados:

1. **Estrutura do Nome do Arquivo:**  
   `[DataHora_14dígitos][Serial][Modelo]_[PASS/FAIL].csv`  
   * *Exemplo:* `202607222134526783001JY2V14V15_GEN5_IRLFAIL.csv`

2. **Linha 1 (Cabeçalho de Metadados Principais):**
   ```csv
   1, 1128, V14V15_GEN5_IRL, 6783001JY2, 20260722, 213452, F, 0, 1, , FF..., 1, F, 2, ...
   ```
   * **Campo 3:** Modelo da Placa (`V14V15_GEN5_IRL`).
   * **Campo 4:** Serial da Placa (`6783001JY2`).
   * **Campos 5 e 6:** Data de Teste (`2026-07-22`) e Hora (`21:34:52`).
   * **Campo 7:** Status Geral de Aprovação (`F` = Reprovado/Fail, `P` = Aprovado/Pass).

3. **Linhas Subsequentes (Detalhamento dos Erros):**
   * **Se for Curto Elétrico (Short):**
     `Short < 37>-1P1V_VDD_UG -> Parts:PU1600.1 < 116 >-1P1V_VDD_SENS ...`
     *(Identifica a malha em curto e o componente físico responsável, ex: `PU1600.1`)*.
   * **Se for Falha de Componente Físico:**
     `77, PR1014, 1.000, 1.000, 10.0, 10.0, 0, J, 531, 31, A2, 4.0000000, 1`
     * `PR1014`: Identificador do componente na serigrafia da placa (Resistor/Capacitor/CI).
     * `1.000`: Valor Nominal / Esperado.
     * `10.0`: Tolerância Mínima e Máxima (%).
     * `J` / `R` / `C` / `QF` / `U`: Tipo do componente (`R` = Resistor, `C` = Capacitor, `U` = Circuito Integrado, `QF` = Transistor FET, `J` = Jumper/Trilha).
     * `A2` / `C4`: **Coordenada física da localização na placa** para o técnico de reparo.
     * `4.0000000`: Valor real medido na bancada (mostrando a discrepância).

---

### B. Logs do Agilent (`ict01`) - Padrão Text Report (`...report_out_...txt`)
Os logs do Agilent focam em relatórios descritivos organizados por seções de teste:

1. **Estrutura do Nome do Arquivo:**  
   `[Serial]_report_out_[Modelo].txt` (Ex: `6783000UXG_report_out_loq15_irx9.txt`).

2. **Seção de Curtos (`Shorts Report`):**
   ```text
   Short #1, Thresh 9, Delay 50us      Ohms
   From: espi_rst_               20375    4
   To:   ESPI_IO2_R             219157    4
   ```
   *(Mostra os nós e sinais de origem e destino em curto com o valor de resistência em Ohms)*.

3. **Seção de Pinos Abertos (`CHEK-POINT Report for "pins"`):**
   ```text
   Failed Open #1
   (202118) N77290809
                    cv3.2
                    cv4.2
                    qh2.G
                    rt4.1
   ```
   *(Lista a malha desconectada e os pinos exatos dos componentes sem contato elétrico, ex: pino `G` do transistor `qh2`, pino `1` do resistor `rt4`)*.

4. **Rodapé:**  
   Contém a confirmação do número serial (`Serial #: 6783000UXG`).

---

## 📊 2. Quadro Comparativo Técnico

| Característica | Logs TRI (CSV) | Logs Agilent (TXT) |
| :--- | :--- | :--- |
| **Identificação do Serial** | No nome do arquivo e na Linha 1 do CSV | No nome do arquivo e no rodapé (`Serial #:`) |
| **Identificação da Data** | Timestamp no nome + Colunas 5 e 6 | Data de modificação do arquivo + Cabeçalho do relatório |
| **Localização do Defeito** | Coordenada gráfica de matriz (`A2`, `C4`, `D5`) | Pinos específicos dos componentes (`qh2.G`, `rt4.1`) |
| **Tipos de Medição** | Curtos, Resistência, Capacitância, CIs | Curtos (Shorts) e Pinos Abertos (Failed Open) |

---

## 💡 3. Plano de Melhorias de Inteligência & Visualização (Sem Riscos)

Para agregar o máximo de valor ao técnico de reparo **sem alterar a arquitetura de busca ou cópia** (garantindo zero risco de regressão):

### 💡 Melhoria 1: "Card de Diagnóstico Rápido" no Topo do Log
* **Como funciona:** Quando o técnico clica em um log na lista, o parser lê o arquivo e gera um resumo sintético em destaque no topo da tela.
* **O que exibe:**
  * 🔴 **Componentes Afetados:** Lista direta dos componentes com falha (ex: `PR1014, RE2, CC38` no TRI ou `Failed Open em qh2.G` no Agilent).
  * 📍 **Setor de Localização na Placa:** Exibe as coordenadas físicas (ex: `Setores: A2, C4`).
* **Benefício Real:** O técnico não precisa procurar a linha do erro no meio de centenas de linhas de código.

### 💡 Melhoria 2: Botão Alternável "👁️ Mostrar Apenas Linhas de Falha"
* **Como funciona:** Um pequeno botão de alternância (*toggle*) no visualizador de logs.
* **Benefício Real:** Em logs extensos com 1.500 linhas de componentes aprovados (`PASS`) e apenas 2 reprovados (`FAIL`), o técnico clica no botão e o sistema oculta as 1.498 linhas limpas, exibindo **apenas as 2 linhas que interessam para o reparo**.

### 💡 Melhoria 3: Botão "📋 Copiar Resumo para Laudo / Teams"
* **Como funciona:** Um clique gera um texto formatado pronto para a área de transferência:
  ```text
  [DIAGNÓSTICO ICT - TRI]
  Serial: 6783001JY2 | Modelo: V14V15_GEN5_IRL
  Data do Teste: 22/07/2026 21:34:52
  Status: REPROVADO (FAIL)
  Defeitos: PR1014 (Setor A2), CC38 (Setor C4)
  ```
* **Benefício Real:** Agiliza a comunicação com a engenharia de processo e colagem em chamados de manutenção.

### 💡 Melhoria 4: Realce de Sintaxe Colorido por Tipo de Componente
* **Como funciona:** Destaque visual por cores amigáveis:
  * 🔴 **Curtos e Erros:** Fundo vermelho suave.
  * 🟠 **Componentes Físicos:** Laranja para CIs (`PU...`, `U...`), Capacitores (`CC...`, `C...`) e Resistores (`PR...`, `R...`).
  * 🟡 **Serial Buscado:** Amarelo vibrante.

---

## 🔒 4. Garantia de Segurança e Estabilidade do Sistema

1. **Zero Alteração no Motor de Busca e Cópia:** As threads `BuscaThread`, `TRICopyThread` e os arquivos de configuração de rede permanecem 100% intactos.
2. **Camada Visual Isolada:** Todas as melhorias atuam **exclusivamente na renderização visual do texto** (`formatar_log_destaque` e `on_file_loaded`). Se um log tiver um formato fora do padrão, o sistema exibe o texto bruto sem qualquer falha ou erro.

---

*Documento gerado para o ICT Master Suite.*
