# 🏭 ICT Master Suite
**Sistema Avançado de Gestão de Tratativa de Falhas (MES - Manufacturing Execution System)**

## 🎯 Sobre o Projeto
O **ICT Master Suite** é uma solução de software desenvolvida sob medida para revolucionar a forma como a linha de produção gerencia, analisa e rastreia placas com falhas. Substituindo planilhas descentralizadas e processos manuais, o sistema atua como o Cérebro Central da fábrica, garantindo comunicação em tempo real, retenção de conhecimento e rastreabilidade total de cada componente.

## ✨ Principais Funcionalidades

### 🔐 1. Rastreabilidade e Controle de Acesso (RBAC)
* **Autenticação Segura:** Login individual para cada técnico.
* **Assinatura Digital Automática:** Toda análise salva no sistema é vinculada ao usuário logado, garantindo 100% de responsabilidade e auditoria (Saber *quem* analisou, *quando* e *o que* foi feito).
* **Gestão de Usuários:** Módulo exclusivo para a gerência cadastrar, editar credenciais e resetar senhas de técnicos diretamente pelo sistema.

### 📚 2. Base de Conhecimento (Wiki de Reparos Colaborativa)
* **Retenção de Capital Intelectual:** Um motor de busca dinâmico onde os técnicos registram os sintomas (FCT/ICT) e as soluções aplicadas para cada modelo de placa (ex: M70Q5, M75Q5 SH).
* **Busca Instantânea:** Filtros inteligentes que permitem encontrar soluções anteriores em milissegundos, evitando retrabalho e transformando o conhecimento individual em patrimônio da empresa.

### 📊 3. Relatórios Gerenciais e Exportação (Data Analytics)
* **Exportação com 1 Clique:** Integração nativa com a biblioteca `pandas` para compilar todo o banco de dados e gerar relatórios em `.xlsx` formatados.
* **Métricas Reais:** Permite à gerência criar KPIs precisos de produção, incidência de falhas e desempenho de reparo.

### ⚙️ 4. Configurações Dinâmicas e Proteção de Infraestrutura
* **Painel Admin-Only:** O administrador pode reconfigurar IPs de servidores, caminhos de banco de dados e pastas de logs diretamente pela interface do sistema, tornando o software imune a mudanças repentinas na infraestrutura de TI.

### 🚀 5. Motor de Atualização Automática (OTA - Over-The-Air)
* **Zero Downtime para a TI:** O sistema detecta novas versões no servidor, desvia dos bloqueios do Windows e atualiza todas as máquinas da fábrica automaticamente, garantindo que toda a linha rode sempre a versão mais recente.

## 🛠️ Arquitetura e Tecnologia
* **Interface:** PyQt5 (Design responsivo e à prova de falhas operacionais).
* **Banco de Dados:** SQLite em Rede (Modo WAL) para concorrência múltipla.
* **Análise de Dados:** Pandas e OpenPyXL.
* **Deploy:** PyInstaller OneFile (Executável autônomo, não exige instalação).

---
**Desenvolvido por:** Franklin Carvalho
**Status:** Produção Ativa (V 1.1.0)