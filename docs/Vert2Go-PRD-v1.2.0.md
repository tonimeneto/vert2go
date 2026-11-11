# VERT2GO — PRODUCT REQUIREMENTS DOCUMENT (PRD)

**Produto:** Vert2Go
**Agente:** Alfredo
**Versão:** 1.2.0
**Data:** 04/11/2026
**Status:** Planejamento — Arquitetura conceitual definida
**Projeto piloto:** Condomínio Four Seasons
**Implementação:** Não iniciada
**Documento:** Fonte principal de requisitos do projeto

---

# 1. CONTROLE DO DOCUMENTO

## 1.1 Objetivo

Este documento estabelece os requisitos funcionais, técnicos, operacionais e arquiteturais do Vert2Go.

Deve orientar o planejamento, a implementação, os testes e a evolução do agente Alfredo.

É a referência principal para o desenvolvimento com VS Code e Codex.

Nenhuma decisão técnica posterior poderá contrariar este PRD sem revisão explícita.

## 1.2 Versionamento

O PRD utiliza versionamento semântico:

MAJOR.MINOR.PATCH

- MAJOR: mudança relevante no objetivo, escopo ou arquitetura.
- MINOR: inclusão de funcionalidades ou decisões arquiteturais compatíveis.
- PATCH: correções, esclarecimentos e ajustes documentais.

Toda alteração deverá atualizar:

- Número da versão.
- Data.
- Histórico de alterações.
- Seções afetadas.

O documento deverá permanecer completo e consolidado.

Não deverão existir instruções dependentes de versões anteriores para compreender os requisitos atuais.

## 1.3 Histórico de versões

| Versão | Data | Alterações |
|---|---|---|
| 1.0.0 | 03/11/2026 | Consolidação inicial do escopo, arquitetura e requisitos do Alfredo |
| 1.1.0 | 03/11/2026 | Inclusão da identidade Google do piloto, Telegram como primeiro canal real, estratégia de comunicação, organização das fontes e regras de versionamento |
| 1.2.0 | 04/11/2026 | Inclusão da Memória Operacional Administrativa: orientações do síndico pelo Telegram, vigência, correção, cancelamento, consulta sob demanda, auditoria e controles de autorização |

## 1.4 Governança

As seguintes regras são obrigatórias:

1. Planejar antes de implementar.
2. Não iniciar desenvolvimento sem autorização.
3. Manter foco exclusivo em IA vertical.
4. Não transformar o Vert2Go em SaaS horizontal.
5. Não criar painel administrativo sem necessidade comprovada e autorização explícita.
6. Não modificar o Emp2Go.
7. Separar configurações do código.
8. Utilizar ferramentas existentes sempre que possível.
9. Priorizar simplicidade, segurança e baixo custo.
10. Diferenciar funcionalidades planejadas, implementadas, simuladas e integradas.
11. Não afirmar que uma integração funciona sem validação técnica.
12. Preservar o isolamento entre dados reais e dados simulados.
13. Utilizar o mínimo necessário de contexto e chamadas aos modelos de IA.
14. Exigir autorização antes de alterar sistemas externos reais.

---

# 2. VISÃO DO PRODUTO

## 2.1 Definição

O Vert2Go é um projeto de inteligência artificial vertical.

Seu produto principal é o Alfredo, um agente especializado em executar atividades operacionais de condomínios.

O Alfredo deve funcionar como um funcionário digital que:

- Recebe solicitações.
- Compreende linguagem natural.
- Consulta informações.
- Identifica regras.
- Utiliza ferramentas.
- Executa operações autorizadas.
- Acompanha pendências.
- Comunica resultados.
- Presta contas à administração.

O objetivo não é construir um sistema de gestão condominial.

O objetivo é construir um agente que trabalhe utilizando ferramentas existentes.

## 2.2 Princípio fundamental

O MOTOR É O PRODUTO.

O Alfredo é o motor.

As ferramentas são instrumentos de trabalho.

O canal de comunicação é a interface com as pessoas.

O motor não deve depender de uma interface administrativa própria para executar suas atividades essenciais.

## 2.3 Diferenciação do Emp2Go

Emp2Go e Vert2Go são projetos independentes.

Emp2Go possui uma abordagem mais ampla de funcionário digital e consulta documental.

Vert2Go concentra-se em agentes especializados em atividades operacionais de um segmento específico.

No piloto, esse segmento será condomínios.

A existência de componentes semelhantes não autoriza misturar os projetos.

Eventual reaproveitamento técnico dependerá de análise e autorização posteriores.

## 2.4 Objetivo comercial

O Alfredo deverá ser demonstrável a um síndico como uma solução operacional com potencial de contratação.

A demonstração deverá evidenciar:

- Atendimento natural.
- Execução de tarefas.
- Redução de trabalho administrativo.
- Utilização de ferramentas existentes.
- Supervisão humana.
- Rastreabilidade das operações.

Não poderão ser apresentadas simulações como integrações reais.

---

# 3. ESCOPO DO PILOTO

## 3.1 Condomínio de referência

O piloto utilizará o condomínio Four Seasons como referência de processos e regras.

O piloto não constitui implantação oficial.

Não haverá alteração em:

- Reservas reais.
- Cadastros oficiais.
- Aplicativos do condomínio.
- Informações operacionais de moradores reais.
- Sistemas da administradora.
- Sistemas da portaria.

## 3.2 Fontes documentais

Serão utilizadas, mediante disponibilização e autorização:

- Convenção do condomínio.
- Regulamento interno.
- Informações documentadas sobre procedimentos.
- Informações autorizadas sobre Lello.
- Informações autorizadas sobre Remota.

As fontes deverão ser classificadas como:

1. Documento oficial.
2. Informação operacional autorizada.
3. Dado fictício de simulação.
4. Informação ainda não verificada.

O Alfredo não poderá apresentar dados fictícios como regras oficiais.

## 3.3 Funcionalidades iniciais

O piloto contemplará:

1. Reserva do salão de festas.
2. Consulta à convenção e ao regulamento.
3. Informações documentadas sobre serviços do condomínio.
4. Registro de solicitações.
5. Encaminhamento de exceções.
6. Atendimento diferenciado por perfil.
7. Acompanhamento de pendências.
8. Relatório de atividades sob demanda.
9. Memória Operacional Administrativa: orientação direta da síndica simulada pelo Telegram, sem documento, usada em respostas pertinentes aos moradores.

## 3.4 Funcionalidades fora do escopo inicial

Não serão implementados inicialmente:

- Aplicativo administrativo.
- Aplicativo próprio para moradores.
- SaaS multiempresa.
- Sistema financeiro.
- Gestão completa de condomínios.
- Integração com Lello.
- Integração com Remota.
- Operações em sistemas oficiais do condomínio.
- Infraestrutura de produção.
- VPS.
- Automações de câmeras ou controle físico de acesso.

---

# 4. ARQUITETURA DO ALFREDO

## 4.1 Componentes

O motor será composto por:

### 4.1.1 Inteligência

Responsável por compreender solicitações, interpretar contexto e produzir respostas.

Provedor inicial: OpenAI.

O modelo específico e a política de seleção serão definidos na especificação técnica.

### 4.1.2 Instruções

Definem:

- Identidade do Alfredo.
- Responsabilidades.
- Comportamento.
- Limites.
- Políticas de segurança.
- Regras de utilização das ferramentas.
- Tratamento de exceções.

### 4.1.3 Conhecimento

Responsável pela consulta às informações autorizadas.

Fonte documental padrão: Google Drive.

### 4.1.4 Ferramentas

Permitem ao Alfredo consultar e modificar dados operacionais autorizados.

Ferramentas iniciais:

- Google Drive.
- Google Agenda.
- Google Sheets.

### 4.1.5 Memória

Responsável por:

- Contexto das conversas.
- Histórico operacional.
- Solicitações.
- Pendências.
- Referências às operações executadas.
- Orientações operacionais administrativas fornecidas pelo perfil de síndica autorizado, com origem, vigência, revisão e cancelamento.

Tecnologia inicial: SQLite.

### 4.1.6 Orquestração

Responsável por coordenar:

- Recebimento de mensagens.
- Identificação do solicitante.
- Consulta de conhecimento.
- Validação de regras.
- Execução de ferramentas.
- Tratamento de falhas.
- Respostas.
- Continuidade de solicitações.

### 4.1.7 Segurança

Responsável por:

- Autenticação.
- Autorização.
- Controle de permissões.
- Proteção de credenciais.
- Validação das operações.
- Registro de auditoria.

### 4.1.8 Comunicação

Responsável por receber e enviar mensagens.

O canal de comunicação será independente da lógica principal do motor.

---

# 5. TECNOLOGIAS DEFINIDAS

| Componente | Tecnologia |
|---|---|
| Linguagem principal | Python |
| Inteligência | API OpenAI |
| Documentos | Google Drive |
| Reservas | Google Agenda |
| Registros operacionais | Google Sheets |
| Memória interna | SQLite |
| Configuração | YAML |
| Primeiro canal real | Telegram Bot API oficial |
| Canal comercial pretendido | WhatsApp Business Platform oficial |
| Desenvolvimento | VS Code + Codex |
| Execução inicial | Ambiente local |

As bibliotecas, versões, dependências e contratos de integração serão definidos na especificação técnica.

Nenhuma dessas escolhas exige criar um aplicativo administrativo.

---

# 6. IDENTIDADE DIGITAL DO PILOTO

## 6.1 Conta Google exclusiva

Será criada uma conta Google exclusiva para o ambiente experimental do Alfredo.

Essa conta será utilizada para organizar os recursos operacionais do piloto.

Não deverá utilizar identidade que sugira representar oficialmente o condomínio Four Seasons.

A conta será do projeto experimental, não da administração real.

## 6.2 Finalidades

A identidade Google permitirá:

- Centralizar documentos.
- Manter agenda de reservas simuladas.
- Manter planilhas operacionais.
- Organizar permissões.
- Autorizar integrações.
- Separar os testes das contas pessoais.

## 6.3 Organização sugerida do Drive

Pasta principal:

Vert2Go-Alfredo-Piloto

Subpastas:

01-Documentos-Oficiais
02-Informacoes-Operacionais
03-Dados-Simulados
04-Referencias

O PRD será mantido como fonte principal do projeto Vert2Go no ChatGPT.

Uma cópia versionada poderá ser mantida no repositório de desenvolvimento quando ele for criado.

Documentos oficiais deverão ser preservados sem alterações.

## 6.4 Autorização Google

O acesso às APIs Google deverá utilizar mecanismos oficiais de autenticação e autorização.

As permissões deverão seguir o princípio do menor privilégio.

O Alfredo não deverá receber acesso indiscriminado à conta Google.

Credenciais e tokens não poderão ser gravados no código-fonte ou em arquivos públicos.

A escolha entre OAuth e conta de serviço será realizada na especificação técnica, conforme a operação e as restrições das APIs.

---

# 7. CONFIGURAÇÃO DO MOTOR

## 7.1 Princípio

O código Python não poderá conter configurações específicas do condomínio.

O motor deverá utilizar um documento externo de parâmetros.

Formato inicial: YAML.

## 7.2 Configuração do condomínio

O documento deverá contemplar:

### Identidade

- Identificador do ambiente.
- Nome de referência do condomínio.
- Nome do agente.
- Fuso horário.
- Idioma.

### Serviços

- Serviços habilitados.
- Ambientes disponíveis.
- Operações permitidas.
- Políticas de encaminhamento.

### Pessoas e papéis

- Identificadores dos usuários.
- Perfis autorizados.
- Responsáveis por exceções.
- Permissões por operação.

### Conhecimento

- Identificadores das pastas.
- Identificadores dos documentos.
- Classificação das fontes.

### Google Agenda

- Identificador da agenda.
- Ambiente correspondente.
- Política de consulta.
- Política de registro.

### Google Sheets

- Identificadores das planilhas.
- Finalidade de cada planilha.
- Operações autorizadas.

### Comunicação

- Canal habilitado.
- Identificadores necessários.
- Política de mensagens.

### Segurança

- Operações sensíveis.
- Exigências de confirmação.
- Política de encaminhamento.
- Limites operacionais.

## 7.3 Credenciais

Credenciais deverão permanecer separadas do YAML.

Não deverão existir senhas ou chaves de API diretamente no documento de configuração.

## 7.4 Reutilização

Para utilizar o Alfredo em outro condomínio, será preparada uma configuração específica.

Não será necessário modificar o motor para alterar parâmetros do ambiente.

Isso não implica criar um SaaS, cadastro centralizado ou plataforma multiempresa.

O foco permanece em uma instalação ou configuração operacional por ambiente.

---

# 8. FERRAMENTAS GOOGLE

## 8.1 Google Drive

Será a fonte padrão de documentos e conhecimento.

O Alfredo deverá:

- Localizar documentos autorizados.
- Consultar conteúdo relevante.
- Identificar a fonte da informação.
- Responder com base no conteúdo encontrado.
- Reconhecer ausência de informação.
- Evitar inventar regras.

A estratégia de extração, indexação e atualização documental será definida tecnicamente.

## 8.2 Google Agenda

Será a ferramenta operacional padrão para reservas.

O Alfredo deverá:

- Consultar disponibilidade.
- Identificar conflitos.
- Sugerir alternativas.
- Registrar reservas.
- Consultar reservas anteriores.
- Informar o resultado efetivamente registrado.

A agenda de testes será independente das agendas oficiais do condomínio.

Não haverá reservas paralelas no SQLite.

O controle de concorrência deverá impedir confirmações conflitantes, inclusive quando houver solicitações simultâneas.

A solução técnica para garantir essa consistência será definida antes da implementação.

## 8.3 Google Sheets

Será utilizado para registros operacionais simples.

Exemplos:

- Solicitações.
- Pendências.
- Informações auxiliares.
- Registros de atendimento.
- Dados simulados de usuários autorizados.

O Sheets não deverá duplicar desnecessariamente os dados da Agenda.

## 8.4 SQLite

Será utilizado exclusivamente como armazenamento interno de apoio ao motor.

Responsabilidades:

- Memória Operacional Administrativa (orientações administrativas vigentes e seu ciclo de vida).
- Contexto persistente de conversa (funcionalidade distinta da Memória Operacional Administrativa).
- Histórico de ações.
- Estado das solicitações.
- Controle de processamento.
- Referências às operações externas.

O SQLite não será a fonte oficial de disponibilidade do salão.

---

# 9. COMUNICAÇÃO

## 9.1 Princípio

O Alfredo deverá funcionar independentemente do canal utilizado.

A lógica operacional não poderá depender diretamente do Telegram ou WhatsApp.

O canal recebe e entrega mensagens.

O motor interpreta e executa operações.

## 9.2 Telegram — Primeiro canal real

O Telegram será utilizado na primeira integração de mensagens.

Motivos:

- API oficial de bots.
- Utilização gratuita da API padrão.
- Integração relativamente simples com Python.
- Suporte a mensagens de texto.
- Suporte a mensagens de voz e arquivos.
- Possibilidade de testes locais.
- Possibilidade de simular diferentes usuários.

O Telegram permitirá validar o Alfredo em conversas reais sem depender inicialmente da infraestrutura do WhatsApp.

O processamento de áudio exigirá transcrição, cuja implementação e custos serão definidos posteriormente.

## 9.3 Identidade do bot

Será criada uma identidade de bot específica para o Alfredo.

O token de acesso deverá ser protegido.

O bot não deverá ser apresentado como canal oficial do condomínio.

## 9.4 WhatsApp — Canal comercial

O WhatsApp continuará sendo o canal pretendido para o uso comercial.

A integração deverá priorizar a API oficial do WhatsApp Business Platform.

Antes da implementação serão avaliados:

- Requisitos da Meta.
- Custos.
- Identidade do número.
- Autorização de mensagens.
- Regras para mensagens iniciadas pelo agente.
- Templates, quando necessários.
- Segurança.
- Operação e hospedagem.

## 9.5 APIs não oficiais

APIs não oficiais de WhatsApp poderão ser estudadas comparativamente.

Entretanto, não serão a base inicial do produto.

Motivos:

- Risco de bloqueio.
- Dependência de mecanismos não oficiais.
- Possíveis interrupções.
- Riscos operacionais.
- Incerteza de manutenção e conformidade.

Qualquer utilização futura exigirá análise e autorização explícita.

## 9.6 Simulação de participantes

No piloto haverá pelo menos dois perfis de teste:

- Morador.
- Síndica.

As conversas deverão ser independentes.

O Alfredo deverá reconhecer os perfis autorizados.

---

# 10. IDENTIFICAÇÃO E AUTORIZAÇÃO

## 10.1 Identificação

O Alfredo deverá reconhecer o usuário por uma identidade previamente vinculada a um cadastro autorizado.

No Telegram será utilizado o identificador da conta, não apenas o nome exibido.

No WhatsApp poderá ser utilizado o número associado a uma identificação previamente validada.

## 10.2 Perfis

### Morador

Pode:

- Consultar informações.
- Solicitar reservas.
- Consultar suas solicitações.
- Receber respostas.
- Registrar solicitações permitidas.

### Síndica

Pode, dentro das permissões definidas:

- Consultar atividades.
- Responder solicitações.
- Autorizar exceções.
- Solicitar relatórios.
- Corrigir orientações e operações quando permitido.
- Cadastrar, consultar, corrigir e cancelar orientações na Memória Operacional Administrativa, com confirmação e rastreabilidade.

### Administração e portaria

Poderão executar ou responder apenas assuntos correspondentes às atribuições autorizadas.

## 10.3 Segurança

A identidade do canal não será suficiente, isoladamente, para autorizar ações sensíveis.

As permissões deverão ser validadas pelo motor antes da execução.

---

# 11. RESERVA DO SALÃO DE FESTAS

## 11.1 Objetivo

Permitir que um morador solicite e confirme uma reserva por conversa natural.

## 11.2 Fluxo principal

1. O morador solicita uma data.
2. Alfredo identifica o morador.
3. Identifica a unidade.
4. Identifica o ambiente.
5. Identifica data e horário.
6. Consulta regras documentadas.
7. Consulta a Google Agenda de testes.
8. Verifica disponibilidade.
9. Identifica taxas ou condições.
10. Solicita confirmação financeira quando aplicável.
11. Executa a reserva quando permitido.
12. Confirma somente após o registro bem-sucedido.
13. Registra o histórico operacional.

## 11.3 Indisponibilidade

Se a data estiver ocupada, Alfredo deverá sugerir alternativas efetivamente disponíveis.

As alternativas deverão ser consultadas na agenda.

Não poderão ser inventadas.

## 11.4 Reserva automática

Reservas permitidas deverão ser confirmadas automaticamente.

Não será necessária aprovação rotineira da síndica.

A síndica participará apenas quando houver exceção que exija sua decisão.

## 11.5 Taxas

Quando houver taxa ou compromisso financeiro, Alfredo deverá informar as condições documentadas e solicitar confirmação explícita.

Não deverá executar cobrança financeira no piloto.

## 11.6 Concorrência

O motor deverá impedir que duas solicitações confirmem a mesma disponibilidade.

A consulta isolada de disponibilidade não será considerada suficiente para garantir ausência de conflitos.

A implementação deverá definir mecanismo de consistência e recuperação de falhas.

---

# 12. CONSULTA DOCUMENTAL

O Alfredo deverá responder perguntas sobre qualquer assunto documentado e autorizado.

Exemplos:

- Piscina.
- Salão de festas.
- Churrasqueira.
- Visitantes.
- Animais.
- Garagem.
- Mudanças.
- Obras.
- Barulho.
- Áreas comuns.
- Correspondências.
- Procedimentos administrativos.
- Informações sobre Lello e Remota.

As respostas deverão refletir as fontes disponíveis.

Horários, limites, taxas e regras não poderão ser presumidos.

Quando uma regra não estiver documentada, Alfredo deverá reconhecer a limitação.

---

# 13. SOLICITAÇÕES E PENDÊNCIAS

## 13.1 Encaminhamento

Quando não conseguir resolver uma solicitação, Alfredo deverá identificar o responsável adequado.

Nem tudo deverá ser encaminhado à síndica.

O encaminhamento poderá envolver administração, portaria ou outro responsável autorizado.

## 13.2 Acompanhamento

Alfredo deverá manter o estado da solicitação.

Quando receber uma resposta autorizada, deverá:

1. Identificar a solicitação correspondente.
2. Validar a origem da resposta.
3. Atualizar o estado.
4. Executar a ação permitida, quando aplicável.
5. Comunicar o morador.

## 13.3 Comunicação

O Alfredo não deverá enviar mensagens repetitivas informando que uma solicitação continua pendente.

Deverá comunicar mudanças relevantes e respostas efetivas.

## 13.4 Piloto

Encaminhamentos e respostas administrativas serão simulados.

Nenhuma pessoa da administração real será envolvida sem autorização.

---

# 14. SUPERVISÃO E RELATÓRIOS

## 14.1 Relatório sob demanda

A síndica poderá solicitar um relatório ao Alfredo.

Não haverá envio diário automático em horário fixo na versão inicial.

## 14.2 Conteúdo

O relatório poderá incluir:

- Quantidade de atendimentos.
- Reservas realizadas.
- Solicitações concluídas.
- Pendências.
- Encaminhamentos.
- Exceções.
- Falhas relevantes.

## 14.3 Correções

A síndica poderá fornecer orientações autorizadas para corrigir situações.

Alfredo deverá verificar permissões e limites antes de executar alterações.

Quando necessário, deverá comunicar o morador afetado.

## 14.4 Situações urgentes

Falhas graves ou situações urgentes não deverão aguardar a solicitação de relatório.

---

# 15. MEMÓRIA E CONTEXTO

O Alfredo deverá manter continuidade entre mensagens.

Exemplos:

- Não perguntar repetidamente o nome do morador identificado.
- Lembrar a unidade durante a conversa.
- Reconhecer uma reserva recém-criada.
- Relacionar respostas a solicitações pendentes.
- Permitir consulta ao histórico autorizado.

A memória deverá ser persistente quando necessário.

Informações temporárias não deverão ser armazenadas indefinidamente.

A política de retenção será definida na especificação técnica.

---

# 15A. MEMÓRIA OPERACIONAL ADMINISTRATIVA — REQUISITO FUNCIONAL

## 15A.1 Finalidade e distinção

A **Memória Operacional Administrativa** permite que a síndica simulada transmita ao Alfredo, diretamente por **mensagem de texto no Telegram**, informações e instruções sobre acontecimentos cotidianos do condomínio **sem criar documento, editar planilha ou alterar código**. O Alfredo pode utilizar uma orientação vigente para responder **quando um morador autorizado perguntar sobre o assunto**.

Não confundir com o contexto da conversa, histórico de atendimento, solicitações, memória de preferências pessoais ou busca documental. Trata-se de um conjunto controlado de **comunicados/instruções operacionais fornecidos pela administração**, não de alteração da convenção ou regulamento.

Exemplo: a síndica informa: “Hoje haverá serviço na fachada. As janelas devem permanecer fechadas durante o trabalho.” Mais tarde o morador pergunta se pode abrir a janela; Alfredo responde com a orientação vigente, atribuindo sua origem à administração, **sem alegar que consta do regulamento**.

## 15A.2 Operações e autorização

1. Somente o perfil `manager` previamente cadastrado poderá **criar, corrigir ou cancelar** orientações; validação feita deterministicamente no motor Python pelo Telegram ID, jamais pela alegação textual de identidade.
2. O síndico poderá **consultar** suas orientações vigentes ou anteriores dentro da retenção autorizada; morador poderá somente obter respostas sobre orientações **vigentes, pertinentes e destinadas aos moradores**, sem acesso ao cadastro interno, histórico ou dados restritos.
3. Antes de gravar, corrigir ou cancelar, Alfredo apresentará um **resumo e solicitará confirmação explícita**, incluindo o alcance, a orientação e a vigência. Mensagens ambíguas não serão aplicadas automaticamente.
4. Registrar autor identificado, instante de criação, texto original mínimo necessário, versão vigente, início e término de validade quando aplicáveis, público-alvo, status (`draft`, `active`, `expired`, `cancelled`), modificações, confirmação e identificador de operação para deduplicação.
5. A síndica poderá emitir nova orientação, alterar uma existente ou cancelá-la. Cancelamentos e correções não devem apagar a trilha de auditoria necessária.

## 15A.3 Vigência e segurança da resposta

- Interpretar datas relativas no fuso configurado do piloto (`America/Sao_Paulo`); quando “hoje”, “amanhã” ou a duração do serviço forem insuficientes para determinar a vigência, **perguntar ao síndico**. Não inventar horário final nem manter restrição temporária indefinidamente.
- Orientações expiradas, canceladas, não confirmadas ou restritas a outro público **não podem ser apresentadas como vigentes**.
- Nas respostas, distinguir claramente **“orientação comunicada pela administração”** de **“regra do regulamento/convenção”**; não promover instruções administrativas a normas permanentes.
- Conflito com fonte documental aplicável, instrução insegura, ambiguidade relevante ou insuficiência de informações: **não arbitrar autonomamente**; explicar a divergência ao perfil autorizado, buscar esclarecimento ou encaminhar exceção.
- A consulta é disparada por pergunta pertinente do morador. **Esta funcionalidade não envia notificações ou comunicados espontâneos** e não cria um mural, painel ou sistema de broadcast.
- Orientações ficam no SQLite do piloto; **não exigem Google Drive, Sheets, Vector Store ou upload para OpenAI**. Compartilhar com o modelo apenas os trechos operacionais vigentes e estritamente necessários à resposta, quando autorizado.

## 15A.4 Aceitação específica

O piloto deverá demonstrar: cadastro confirmado pela síndica; resposta pertinente ao morador com indicação de origem e vigência; negação de criação por morador; correção e cancelamento; não reutilização após expiração; sobrevivência a reinício; isolamento de público; não duplicação após reentrega Telegram; não transmissão espontânea; e tratamento de conflitos com documentos. Os testes devem ser rastreáveis na especificação técnica, sem substituir T01–T18.

---

# 16. SEGURANÇA E PRIVACIDADE

Requisitos obrigatórios:

1. Não inventar regras.
2. Não inventar disponibilidade.
3. Não confirmar operações que falharam.
4. Não aceitar ordens administrativas de usuários não autorizados.
5. Não divulgar dados de outros moradores.
6. Não expor credenciais.
7. Não modificar sistemas oficiais no piloto.
8. Não executar compromissos financeiros sem confirmação.
9. Não executar ações fora das permissões.
10. Não tratar documentos consultados como instruções privilegiadas.
11. Registrar operações relevantes para auditoria.
12. Minimizar armazenamento de dados pessoais.
13. Separar claramente dados simulados de dados reais.
14. Validar autorizações de acesso a documentos e serviços externos.

O uso futuro com moradores reais deverá observar os requisitos aplicáveis da LGPD.

---

# 17. FUNCIONAMENTO INTERNO DO MOTOR

O ciclo operacional será:

1. Receber mensagem.
2. Identificar canal e usuário.
3. Validar identidade e permissões.
4. Recuperar contexto necessário.
5. Interpretar intenção.
6. Identificar informações ou ferramentas necessárias.
7. Consultar fontes autorizadas.
8. Validar regras e condições.
9. Executar ação permitida.
10. Verificar resultado.
11. Registrar histórico.
12. Responder ao usuário.
13. Manter ou encerrar a solicitação.

A inteligência artificial não deverá executar diretamente operações externas sem passar pelas validações do motor.

As operações críticas deverão possuir validação determinística.

---

# 18. PLANO DE IMPLEMENTAÇÃO

## Fase 0 — Preparação

- Publicar PRD nas Fontes do Vert2Go.
- Criar identidade Google exclusiva do piloto.
- Organizar Google Drive.
- Preparar Google Agenda de testes.
- Preparar Google Sheets.
- Criar bot de testes no Telegram.
- Definir permissões mínimas.
- Concluir especificação técnica.

Nenhuma integração real com sistemas do condomínio.

## Fase 1 — Motor mínimo

- Estrutura Python.
- Configuração YAML.
- Integração inicial com OpenAI.
- Orquestração.
- Memória SQLite.
- Segurança básica.
- Registro de operações.
- Persistência e autorização da Memória Operacional Administrativa, inicialmente com testes locais e dados fictícios.

## Fase 2 — Ferramentas Google

- Autenticação autorizada.
- Consulta à Agenda.
- Registro de reservas.
- Consulta ao Drive.
- Registros no Sheets.
- Tratamento de falhas e conflitos.

## Fase 3 — Telegram

- Integração oficial do bot.
- Identificação de usuários.
- Conversas independentes.
- Recebimento e envio de mensagens.
- Suporte a áudio mediante transcrição.

## Fase 4 — Serviços do condomínio

- Reserva do salão.
- Consulta documental.
- Solicitações.
- Encaminhamentos.
- Respostas administrativas.
- Relatórios sob demanda.
- Cadastro, consulta, correção, cancelamento e expiração de orientações administrativas via Telegram, após autorização da fase correspondente.

## Fase 5 — Demonstração

- Testar como morador.
- Testar como síndica.
- Demonstrar reserva automática.
- Demonstrar indisponibilidade e alternativas.
- Demonstrar consulta ao regulamento.
- Demonstrar encaminhamento.
- Demonstrar relatório.
- Validar histórico e consistência dos registros.

## Fase 6 — Avaliação comercial

Após validação do piloto:

- Avaliar integração oficial com WhatsApp.
- Avaliar custos.
- Avaliar requisitos de operação contínua.
- Avaliar integração com sistemas existentes.
- Avaliar condições de contratação.
- Avaliar segurança e suporte operacional.

A Fase 6 não autoriza automaticamente desenvolvimento adicional.

---

# 19. CRITÉRIOS DE ACEITAÇÃO

O piloto será considerado funcional quando:

1. Alfredo receber mensagens reais pelo Telegram.
2. Reconhecer usuários de teste autorizados.
3. Consultar a Google Agenda de testes.
4. Identificar datas ocupadas.
5. Oferecer alternativas disponíveis.
6. Registrar uma reserva simulada na Agenda.
7. Confirmar somente após o registro.
8. Reconhecer a reserva em consulta posterior.
9. Evitar conflitos de reserva.
10. Consultar documentos autorizados no Drive.
11. Responder perguntas com base nos documentos.
12. Reconhecer ausência de informação.
13. Encaminhar exceções simuladas.
14. Receber respostas da síndica simulada.
15. Retornar ao morador quando houver resposta.
16. Produzir relatório sob demanda.
17. Preservar contexto entre mensagens.
18. Registrar histórico operacional.
19. Funcionar sem aplicativo administrativo.
20. Não modificar dados ou sistemas oficiais do condomínio.
21. Permitir à síndica simulada cadastrar/corrigir/cancelar orientações operacionais pelo Telegram com confirmação explícita.
22. Responder a perguntas pertinentes do morador usando somente orientações vigentes, corretamente atribuídas à administração.
23. Impedir acesso indevido, uso de orientações expiradas e disparo espontâneo de comunicados.

---

# 20. DECISÕES TÉCNICAS PENDENTES

Ainda deverão ser especificados:

- Estrutura definitiva dos módulos Python.
- Contratos das ferramentas.
- Formato detalhado do YAML.
- Modelo de dados SQLite.
- Autenticação Google.
- Estratégia de consulta documental.
- Estratégia de atualização das fontes.
- Tratamento de concorrência no Google Agenda.
- Estratégia de recuperação de falhas.
- Estrutura de auditoria.
- Política de retenção de dados.
- Transcrição de áudio.
- Configuração e execução local do Telegram.
- Política de custos e limites de chamadas de IA.
- Estratégia futura de integração oficial com WhatsApp.

Essas decisões serão tratadas na especificação técnica antes da programação.

---

# 21. REGRAS DE EVOLUÇÃO

O Alfredo deverá evoluir por capacidades operacionais.

Uma nova capacidade somente deverá ser incorporada quando:

1. Resolver uma necessidade concreta do segmento.
2. Estiver dentro do escopo vertical.
3. Puder ser executada com segurança.
4. Tiver fontes e ferramentas identificadas.
5. Possuir critérios de aceitação.
6. Não exigir desnecessariamente uma plataforma horizontal.

Não deverão ser introduzidos módulos administrativos genéricos apenas por conveniência de desenvolvimento.

A existência de configurações não justifica criar uma interface administrativa.

A existência de vários possíveis clientes não justifica antecipar arquitetura SaaS.

---

# 22. PRÓXIMA ETAPA

A próxima etapa será concluir a especificação técnica do motor Alfredo.

Deverão ser detalhados:

1. Estrutura interna.
2. Contratos das ferramentas.
3. Configuração externa.
4. Memória.
5. Segurança.
6. Integrações Google.
7. Integração Telegram.
8. Tratamento de erros.
9. Testes de aceitação.

A implementação somente será iniciada após revisão e autorização.

---

# 23. PRINCÍPIO FINAL

O Vert2Go não existe para criar mais um aplicativo.

Existe para criar um funcionário digital especializado que utilize ferramentas para realizar trabalho.

O Alfredo deve ser capaz de:

ENTENDER → CONSULTAR → DECIDIR → EXECUTAR → REGISTRAR → RESPONDER

Toda decisão de arquitetura deverá preservar esse princípio.

**O MOTOR É O PRODUTO.**

---

**FIM DO PRD — VERSÃO 1.2.0**