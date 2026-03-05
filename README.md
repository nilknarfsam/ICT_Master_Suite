🏭 ICT Master Suite
Sistema Avançado de Gestão de Tratativa de Falhas (MES - Manufacturing Execution System)

🎯 Sobre o Projeto
O ICT Master Suite é uma solução de software desenvolvida sob medida para revolucionar a forma como a linha de produção gerencia, analisa e rastreia placas com falhas. Substituindo processos manuais e descentralizados, o sistema atua como um Cérebro Central na rede da fábrica, garantindo comunicação em tempo real entre os turnos e rastreabilidade total de cada componente testado.

✨ Principais Funcionalidades
🔐 1. Rastreabilidade e Controle de Acesso (RBAC)
Autenticação Segura: Sistema de login individual para cada técnico.

Assinatura Digital Automática: Toda análise salva no sistema é automaticamente vinculada ao usuário logado, garantindo 100% de responsabilidade e auditoria (Saber quem analisou, quando e o que foi feito).

Painel de Administração: Módulo exclusivo para a gerência cadastrar, editar e remover acessos de técnicos de forma intuitiva.

🔄 2. Comunicação Inter-Turnos (Histórico Colaborativo)
Alerta de Reincidência: Ao bipar o serial de uma placa, o sistema consulta o servidor em milissegundos. Se a placa já houver sido tratada por outro técnico em um turno anterior, um alerta visual destacará o histórico, evitando retrabalho e perda de tempo.

⚡ 3. Motor de Busca Assíncrono e Otimizado
Leitura de Logs Inteligente: O sistema varre diretórios de logs de teste instantaneamente sem congelar a tela do usuário.

Gestão de Cache: Sistema autolimpante que evita o acúmulo de arquivos desnecessários no disco local das máquinas da linha.

📈 4. Dashboard e Métricas em Tempo Real
Painel de visualização imutável (Read-Only) que apresenta o volume de placas tratadas, permitindo à gerência um acompanhamento rápido do fluxo de trabalho diário.

🚀 5. Atualização Automática (Over-The-Air / OTA)
Zero Downtime para a TI: O sistema possui um módulo de Auto-Update inteligente. Quando uma nova melhoria é lançada pela Engenharia, o software detecta, contorna os bloqueios de segurança do Windows (File Lock) e atualiza todas as máquinas da fábrica automaticamente com apenas um clique do operador.

🛠️ Arquitetura e Tecnologia
Construído com base nos mais altos padrões da Indústria 4.0:

Interface: Desenvolvida em PyQt5, oferecendo uma experiência de usuário (UX) moderna, fluida e à prova de erros de operação.

Banco de Dados (Cérebro Central): Utiliza SQLite em Rede com modo WAL (Write-Ahead Logging), garantindo que múltiplos técnicos possam salvar análises simultaneamente sem corromper os dados ou gerar travamentos no servidor.

Deploy: Empacotado em um executável autônomo (.exe), não exigindo instalação de bibliotecas ou Python nas máquinas da produção.

Desenvolvido por: Franklin Carvalho
Status: Pronto para Produção (V 1.0.0)