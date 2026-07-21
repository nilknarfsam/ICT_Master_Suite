# 🏭 ICT Master Suite
**Sistema Avançado de Gestão, Monitoramento e Busca de Falhas em Logs de Teste (ICT/Agilent/TRI)**

## 🎯 Sobre o Projeto
O **ICT Master Suite** é uma solução de software leve e de alto desempenho desenvolvida sob medida para a engenharia de teste e técnicos de reparo. Ele centraliza a busca de logs de falha na rede de forma instantânea, realiza a cópia automática de falhas do TRI em segundo plano para uma pasta centralizada e monitora continuamente a saúde da conexão de rede com os servidores de teste.

---

## ✨ Principais Funcionalidades

### 🔍 1. Finder Logs (Busca Inteligente e Rápida)
* **Varredura Otimizada:** Busca instantânea por número serial em múltiplos diretórios de rede configurados usando `os.scandir` recursivo de alta velocidade com limite seguro de profundidade de 2 níveis.
* **Leitura Direta na Rede:** Abre e lê os arquivos de log de teste diretamente de seus caminhos originais de rede, eliminando qualquer overhead de armazenamento local, acúmulo de cache ou duplicação de arquivos.
* **Filtro por Data Dinâmico:** Menu suspenso para filtrar instantaneamente os logs encontrados (*Todas as datas, Últimas 24 horas, Últimos 7 dias, Últimos 30 dias*).
* **Destaque Amarelo do Serial:** Destaca visualmente o serial pesquisado em fundo amarelo vibrante no visualizador de logs.
* **Destaques de Sintaxe Visual:** Termos cruciais de erro (`FAIL` / `FAILED` / `FAILURE`) são destacados em 🔴 vermelho, status de aprovação (`PASS` / `PASSED`) em 🟢 verde, e falhas físicas (`HIGH`/`LOW`/`SHORT`/`OPEN`) em 🟠 laranja.
* **Atalhos Rápidos:** Pressione `F5` para atualizar a busca do serial ou `ESC` para limpar a busca e a tela de logs.

### 🖥️ 2. Console do Sistema (Log em Tempo Real)
* **Monitor de Eventos:** Console integrado com timestamps registrando todas as ações ocorridas (buscas efetuadas, logs abertos, arquivos copiados e status da conexão).
* **💾 Exportar (.txt):** Exportação direta de todo o histórico do terminal do console para um arquivo de texto.

### 🔄 3. Serviço Background de Cópia de Falhas TRI
* **Autocópia de Defeitos:** Monitora a pasta raiz de logs da TRI e copia automaticamente apenas arquivos com falha (`FAIL`) para a subpasta `defeitos_tri`.
* **Controles Integrados:** Botões de **Pausar/Play** e **Reiniciar** o serviço de cópia TRI na própria aba de console.
* **Prevenção de Loops:** O algoritmo ignora a pasta de destino durante a varredura para garantir performance e evitar loops de cópia redundantes.

### 📡 4. Monitor de Rede Contínuo
* **Checagem de Ping:** Monitoramento periódico a cada 15 segundos da integridade da conexão de rede com o IP do servidor (`147.1.0.95`).
* **Visualização:** Rótulo em tempo real no rodapé (`🟢 Rede Online` / `🔴 Rede Offline`) e avisos coloridos de queda ou reconexão inseridos no console.

### ⚙️ 5. Configurações Dinâmicas e Customizáveis
* Caminhos de busca do Finder e caminhos de origem e destino da cópia automática do TRI 100% configuráveis e com seletores de pasta integrados.

---

## 🛠️ Arquitetura e Tecnologias
* **Interface Gráfica:** PyQt5 (Interface Desktop nativa, estilização moderna e design responsivo via `style.qss`).
* **Processamento Assíncrono:** Múltiplas QThreads para buscas, leitura de arquivos na rede, testes de conexão de rede e cópia background do TRI.
* **Compilação:** PyInstaller OneFile (`--noconsole`) gerando um executável autônomo de arquivo único.

---
**Desenvolvido por:** Franklin Carvalho  
**Status:** Produção Ativa (V 5.5.0)  