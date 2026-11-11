# VERT2GO — PLANO DE IMPLEMENTAÇÃO COM CODEX (MODO PLANEJAMENTO)

**Versão:** 0.1.1  
**Data:** 04/11/2026  
**Estado:** planejamento para revisão; **execução não autorizada**  
**Referências normativas:** PRD Vert2Go v1.2.0 e Especificação Técnica Alfredo v0.1.8, **revisão documental a validar pelo responsável**  
**Piloto:** referência Four Seasons, exclusivamente experimental  
**Motor:** Alfredo  
**Ferramentas de desenvolvimento futuras:** VS Code + Codex  

## 1. Objetivo e fronteiras

Planejar uma sequência verificável de implementação do agente vertical Alfredo, sem iniciar programação, executar comandos, acessar contas ou alterar serviços externos nesta etapa. O Codex deverá trabalhar primeiro em **modo planejamento e somente leitura**, apresentar o plano para aprovação e **jamais interpretar a aprovação documental como autorização automática para implementar**.

O produto é o **motor Alfredo**. Não desenvolver SaaS horizontal, painel, aplicativo de morador, sistema financeiro, VPS, webhook, WhatsApp, conexão com Lello ou Remota, nem modificar sistemas oficiais. As reservas, usuários, encaminhamentos e relatórios são exclusivamente simulados. Não modificar Emp2Go.

## 2. Decisões vinculantes

1. Python local, **uma instância**, inicialização manual no Windows; Telegram API oficial via long polling, inicialmente **texto** e somente chats privados.
2. OAuth 2.0 Desktop na conta Google experimental, escopos mínimos tecnicamente viáveis, primeiro diagnóstico somente leitura, reautorização manual se necessário.
3. Google Drive é origem documental; **OpenAI Vector Stores + File Search** para recuperação semântica em linguagem natural, sem índice local alternativo. Indexação depende de autorização explícita para transferência de cópias à OpenAI.
4. Google Agenda experimental é fonte única de reservas; SQLite registra estado e idempotência antes da escrita; exclusividade local, reconciliação de resultado incerto e conferência após criação; nenhuma promessa de proteção contra escrita externa simultânea.
5. Google Sheets é controle operacional; falha de atualização no Sheets não invalida reserva existente na Agenda; SQLite apoia memória, deduplicação, sincronização e auditoria, sem agenda paralela.
6. `config.yaml` reúne todos os parâmetros não secretos; `secrets.yaml` reúne segredos locais. Não usar `.env`, Gerenciador de Credenciais, nem segredos no código, Git, logs ou prompts.
7. Dois IDs Telegram distintos, um morador e uma síndica simulados; cadastro fechado no `config.yaml`; autorização determinística no Python e confirmação para ações sensíveis.
8. Retenção: contexto/deduplicação 30 dias; auditoria 90 dias; pendências até fechamento + 90 dias; preservar o necessário a incidentes não resolvidos.
9. Orçamento OpenAI operacional estimado de **R$ 30/mês**, alerta em R$ 24 e bloqueio de novas chamadas a partir de R$ 30 estimados. Não representa teto garantido de faturamento, inclusive pelo armazenamento indexado contínuo.
10. Dezoito cenários T01–T18 e coberturas complementares da especificação devem possuir evidência objetiva; nenhuma falha crítica pode ser tratada como aprovação do piloto.
11. Memória Operacional Administrativa: orientações do perfil `manager` por Telegram, gravadas no SQLite após confirmação explícita; vigência, correção, cancelamento, auditoria e uso contextual sob demanda. Sem broadcast, novo serviço, tela ou alteração das regras documentais.

## 3. Regras de trabalho do Codex

- Começar por auditoria **somente leitura** do workspace/repositório escolhido; não presumir diretórios, branches, dependências, contas, IDs, documentos ou tokens que ainda não foram fornecidos/verificados.
- Não realizar instalações, commits, edições, criação de arquivos, testes que escrevam, conexão OAuth, leitura do Drive ou chamadas externas enquanto estiver em modo planejamento.
- Observar a governança DevTOLAS/Fs\\Comum apenas caso os padrões estejam efetivamente disponíveis no ambiente e sejam autorizados; não inventá-los nem alterar outras aplicações.
- Apresentar antes de cada execução: arquivos a criar/alterar, comandos previstos, bibliotecas e versões a confirmar, efeitos externos, riscos, verificações de segurança, testes, rollback e custo potencial.
- Preferir implementações pequenas, determinísticas e testáveis, com mocks para APIs e sem arquitetura genérica antecipada.
- Nunca solicitar que o usuário cole tokens, senhas ou conteúdo de `secrets.yaml` no chat/Codex. Segredos deverão ser cadastrados **localmente pelo responsável**, na fase expressamente autorizada.
- A aprovação de uma fase não libera automaticamente a seguinte. Todo acesso/leitura/escrita em serviços externos requer autorização específica por recurso e operação.
- Separar fatos observados, hipóteses e verificações pendentes; não afirmar integração ou teste como concluído sem evidência.

## 4. Pré-condições antes de qualquer execução

Verificações a apresentar em plano de leitura (não executar agora):

- Local/repositório do Vert2Go e estado do Git, com confirmação de escopo de alterações; se inexistente, propor localização e criação para aprovação.
- Python/ambiente Windows e compatibilidade de versões; inventário de dependências e restrições locais.
- Existência e classificação dos arquivos de origem Google; IDs do Drive, Agenda e Sheets somente após autorização de leitura.
- Dois Telegram IDs de teste e unidade fictícia; não confundir conta de bot com conta de usuário.
- Permissão/autorização adequada para enviar cópias do regulamento e convenção à OpenAI; nunca presumir que acesso ao Drive autoriza essa transferência.
- Escopos OAuth viáveis, modelos/APIs OpenAI compatíveis e preços vigentes, a validar antes de chamadas faturáveis.
- Política de segredos: `.gitignore` e verificação de que `secrets.yaml` jamais foi versionado; proteger também banco operacional e eventuais arquivos auxiliares OAuth.
- Regras efetivamente documentadas de reservas; lacunas são bloqueios de automatização, não licença para inventar horários, taxas ou condições.

## 5. Etapas e portões de aprovação

### Fase P0 — Planejamento Codex / leitura exclusivamente

**Pode ser solicitado agora, sem programar.** O Codex analisa os dois documentos normativos e o workspace autorizado, se houver, e entrega: inventário de projeto, matriz PRD → especificação → módulos → testes, estrutura sugerida mínima, dependências a validar, riscos, sequência de commits, comandos propostos e pontos de autorização. **Não cria arquivos nem realiza chamadas externas.**

**Portão G0:** responsável revisa plano e autoriza expressamente a implementação local da fase seguinte. Se inexistir repositório ou faltar contexto, Codex registra pendência e não inventa dados.

### Fase I1 — Esqueleto local e segurança, sem rede

**Somente após G0.** Criar a estrutura Python mínima aprovada; leitor/validador estrito de `config.yaml` e `secrets.yaml` (sem cadastrar segredos reais); regras de `.gitignore` antes do primeiro commit; SQLite com migrações mínimas, trilha de auditoria e deduplicação; política de permissões, persistência de orientações administrativas com versões, vigência e auditoria, armazenamento de estados, orçamento estimado e logs sem segredos; interface de ferramentas simuladas. Testes locais com mocks/fixtures fictícias.

**Aceite:** validação de configuração, isolamento de perfis, persistência, idempotência e proteção contra vazamento testados sem serviços externos. **G1:** aprovação para conectar Telegram/realizar diagnóstico autorizado.

### Fase I2 — Canal Telegram de teste

**Somente após G1 + autorização específica de uso do bot e cadastramento local do token.** Implementar long polling, somente texto/chat privado, dois IDs distintos, limites de mensagens, deduplicação e retomada segura. Primeiro testar com mensagens falsas; só depois realizar envio/recebimento real no bot de testes com autorização separada.

**Aceite:** identificação por ID, negação a desconhecidos/grupos, contexto isolado e mensagens repetidas sem operações duplas. Fluxo de orientação administrativa pode ser simulado nesse estágio, sem ativação real antes de autorização. **G2:** autorização separada para leitura Google e modelos OpenAI.

### Fase I3 — Integração Google somente leitura

**Somente após G2 + consentimento OAuth.** Configurar OAuth Desktop, confirmar escopos mínimos viáveis, validar ID/permissão de Drive, Agenda e Sheets permitidos; testar leitura controlada, falha/expiração e reautorização. Não escrever na Agenda nem Sheets. Não copiar documentos à OpenAI ainda.

**Aceite:** leituras autorizadas, tratamento correto de acesso negado e nenhum efeito de escrita. **G3:** autorização específica para indexar documentos na OpenAI e incorrer em custos.

### Fase I4 — Conhecimento em linguagem natural

**Somente após G3 e autorização de transferência de cada documento.** Validar legibilidade e elegibilidade, sincronizar cópias autorizadas do Drive com uma Vector Store do piloto, consultar File Search e verificar evidências/referências. Registrar versões e estado de sincronização em SQLite, não criar índice documental local. Testar paráfrases e ausência de evidência; impedir uso de fonte desatualizada em decisão sensível. Não usar OCR sem autorização própria.

**Aceite:** perguntas naturais respondidas com base documental, rastreabilidade e falha segura quando busca/fonte não oferece evidência. A consulta a orientações administrativas vigentes é uma fonte operacional **distinta**, não indexada na Vector Store; sua implementação será integrada à orquestração conforme plano aprovado. **G4:** autorização específica para gravações na Agenda de simulação e planilha.

### Fase I5 — Operações simuladas e reconciliação

**Somente após G4 + confirmação de que recursos de destino são exclusivos do piloto.** Construir reserva com confirmação explícita, avaliação de regras documentadas, nova consulta sob exclusividade local, `operation_id` persistido, criação idempotente quando suportada, releitura e reconciliação. Adicionar registros Sheets com outbox SQLite e reprocessamento sem duplicações; solicitações, exceções, **Memória Operacional Administrativa (cadastro/correção/cancelamento e consulta contextual)** e relatórios sob demanda. Iniciar com mocks; gravações reais somente nos recursos experimentais autorizados.

**Aceite:** nenhuma confirmação de gravação incerta, nem conflitos confirmados no cenário de instância única; falha Sheets não invalida reserva na Agenda; sem cobrança ou alteração de sistemas oficiais. **G5:** aprovação para executar ensaios integrados.

### Fase I6 — Testes locais, Telegram e demonstração

**Somente após G5 + autorização das operações de teste.** Executar T01–T18, MO01–MO10, testes complementares de taxa/aceite, orçamento, OAuth e isolamento dos recursos; registrar evidências (`passed`, `failed`, `blocked`, `not_run`), logs seguros, referências externas e custo estimado. Executar ensaios de mensagens simultâneas, timeout após possível escrita, reinício e recuperação. Não aprovar piloto com falhas críticas nem afirmar que simulação é integração oficial.

**Aceite final:** conformidade com PRD e especificação, resultados verificados das operações externas de teste, nenhum cenário obrigatório pendente, documentação local de iniciar/parar e recuperação. **G6:** autorização específica para apresentação experimental; avaliação comercial e WhatsApp ficam fora desta entrega.

## 6. Matriz resumida de autorizações

| Portão | Ação que só poderá ocorrer depois | O que não está autorizado por padrão |
|---|---|---|
| G0 | Criar/alterar código local de I1 | Serviços externos, tokens reais, commits/publicações fora do escopo |
| G1 | Conectar e testar o bot Telegram experimental | Acesso Google, OpenAI, envio de documentos |
| G2 | Consentir OAuth e realizar **leitura** Google de recursos identificados | Escrita na Agenda/Sheets, transferência à OpenAI |
| G3 | Copiar **documentos especificamente autorizados** à OpenAI; criar Vector Store e realizar chamadas faturáveis | Indexar outros dados, OCR, consultas a documentos não autorizados |
| G4 | Escrever **somente em Agenda/Sheets simulados** após validação de ID e recurso | Sistemas oficiais, reservas reais, cobranças |
| G5 | Executar testes integrados reais autorizados | Demonstração pública ou implantação oficial automática |
| G6 | Demonstrar o piloto como **experimental** | WhatsApp, VPS, SaaS ou produção |

Cada portão exige confirmação humana explícita; a autorização pode especificar subconjuntos mais restritos. Para qualquer ação destrutiva (exclusão, revogação, cancelamento de eventos, remoção de arquivos indexados, limpeza de planilha), exigir aprovação específica adicional, mesmo após um portão aprovado.

## 7. Entregáveis solicitados ao Codex em P0

1. Inventário do workspace e indicação do que existe vs. está ausente, com evidências da inspeção somente leitura.
2. Árvore de módulos proposta, sem arquivos criados.
3. Mapa de contratos por camada (Telegram, políticas, IA/knowledge, Google, SQLite, observabilidade), sem interfaces públicas desnecessárias.
4. Lista mínima de bibliotecas e versão Python sugerida, marcadas como **a verificar** até inspeção técnica.
5. Fluxos e máquinas de estado para reservas, pendências, **orientações administrativas (draft/active/expired/cancelled e revisão)**, deduplicação, reconciliação e orçamento.
6. Matriz de testes T01–T18, **MO01–MO10** e subcenários obrigatórios com mocks e pontos de teste real.
7. Lista de segredos, escopos e IDs que o responsável terá de cadastrar localmente — **sem solicitar os valores**.
8. Lista de autorizações externas por operação, riscos, estimativa de consumo e bloqueios.
9. Sequência de mudanças pequenas/commits proposta, com pontos de validação e rollback.
10. Recomendações de simplificação e eventuais divergências normativas, sem modificar PRD ou especificação.

**Critérios obrigatórios P0 para Memória Operacional Administrativa:** identificar módulos/contratos e tabelas mínimas; diferenciar claramente orientação operacional de regulamento e de memória de conversa; modelar autorização `manager`, confirmação, ambiguidades de vigência, fuso, correção, cancelamento, expiração, idempotência, retenção e conflito documental; demonstrar que nenhum envio espontâneo a moradores será adicionado. Apontar claramente decisões pendentes, sem inventar detalhes.

## 8. Critério de encerramento desta etapa

Este documento só aprova **o planejamento do trabalho**. O estado permanece **não implementado** até autorização expressa para I1. A aprovação de P0, quando concedida, não autoriza execução de código, testes, integração, uso de tokens, transferência de dados ou alterações remotas.

**Princípio:** ENTENDER → CONSULTAR → DECIDIR → EXECUTAR → REGISTRAR → RESPONDER. **O MOTOR É O PRODUTO.**

---

## 9. Histórico de versões

| Versão | Data | Alterações |
|---|---|---|
| 0.1.0 | 03/11/2026 | Plano inicial P0–I6 e portões G0–G6 |
| 0.1.1 | 04/11/2026 | Inclusão da Memória Operacional Administrativa em P0, I1, I2, I4, I5 e I6, com testes MO01–MO10; referências normativas atualizadas |
