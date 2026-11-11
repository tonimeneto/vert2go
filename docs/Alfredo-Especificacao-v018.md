# VERT2GO — ESPECIFICAÇÃO TÉCNICA DO ALFREDO

**Versão:** 0.1.8  
**Data:** 04/11/2026  
**Status:** REVISÃO DOCUMENTAL CONSOLIDADA PARA VALIDAÇÃO — NÃO AUTORIZA IMPLEMENTAÇÃO  
**Documento normativo superior:** Vert2Go — PRD v1.2.0, de 04/11/2026  
**Piloto:** Four Seasons, ambiente exclusivamente experimental  
**Responsável pela implementação futura:** VS Code + Codex, somente após autorização explícita  

> **Regra de prevalência:** em caso de divergência, prevalece o PRD v1.2.0; a divergência deve ser resolvida e autorizada antes de desenvolver. Este documento descreve a arquitetura pretendida, não funcionalidades já implementadas ou integrações já testadas.

---

## 1. Controle do documento e governança

### 1.1 Objetivo

Consolidar as cinco decisões técnicas já aprovadas e os dez ajustes de auditoria A1–A10, incluindo a **revisão posterior do A4 para OpenAI Vector Stores + File Search** e a **revisão do A5 para `secrets.yaml`**, em uma especificação autossuficiente, revisável e utilizável como referência para futura implementação do Alfredo.

### 1.2 Limites obrigatórios

- Vert2Go é **IA vertical para operações condominiais**, independente de Emp2Go. **O motor é o produto.**
- Não desenvolver SaaS horizontal, plataforma multiempresa, painel administrativo, app próprio, sistema financeiro ou infraestrutura de produção.
- Não usar VPS, webhook público ou integrações Lello/Remota na fase piloto.
- Não modificar sistemas oficiais, reservas reais, cadastros de moradores reais ou recursos da administração/portaria.
- Não executar cobrança. Qualquer taxa identificada no regulamento será informativa e, quando aplicável, exigirá aceite explícito antes da reserva simulada.
- Nenhuma configuração Google, autorização OAuth, upload documental, indexação na OpenAI, escrita de reserva ou execução de código está autorizada por esta especificação.
- Não confundir o que foi **criado**, **especificado**, **simulado**, **integrado** e **validado**.

### 1.3 Inventário informado e não verificado

Conforme informado pelo responsável, já existem: conta Google experimental do Alfredo, regulamento e convenção no Google Drive, Agenda de reservas simuladas, planilha operacional e bot Telegram `@AlfredoVert2GoBot`. Os IDs, conteúdos, permissões e acessos via API **não foram auditados nem validados tecnicamente**. O uso da referência Four Seasons não representa implantação ou canal oficial do condomínio.

### 1.4 Decisões já aprovadas, imutáveis sem nova revisão

1. **Google:** OAuth 2.0 Desktop; escopos mínimos viáveis; renovação quando possível; reautorização manual quando necessária; primeiro acesso de validação somente leitura.
2. **Telegram:** API oficial; `long polling` local; mensagens de **texto** na primeira versão; arquitetura separada para permitir áudio futuro, não autorizado agora.
3. **Reservas:** uma instância do Alfredo; exclusividade local; Google Agenda experimental como fonte única; verificação após gravação; reconhecer a limitação diante de edições externas simultâneas.
4. **Retenção:** contexto e deduplicação 30 dias; auditoria 90 dias; pendências até encerramento + 90 dias; exceções para incidentes e operações ainda não resolvidas.
5. **Configuração e identidades:** `config.yaml` único para todos os parâmetros não secretos; duas contas Telegram distintas, identificadas por IDs numéricos e associadas aos perfis de morador e síndica simulados; cadastro fechado e permissões verificadas pelo Python.

### 1.5 Ajustes A1–A10 aprovados nesta rodada

| Ajuste | Resultado aprovado |
|---|---|
| A1 | Regras de reserva somente de fontes documentais autorizadas; parâmetros operacionais em YAML; Agenda para disponibilidade; sem inventar condições |
| A2 | Registro prévio SQLite, operação idempotente, exclusividade local, reconciliação após falha e nenhuma confirmação de resultado incerto |
| A3 | OAuth Desktop com escopos mínimos, renovação/reautorização, segredos separados e validação inicialmente somente leitura |
| A4 **revisado** | Google Drive como origem; **OpenAI Vector Stores + File Search** como recuperação semântica; sincronização controlada e referências documentais; **sem índice local de pesquisa** |
| A5 **revisado** | Dois arquivos YAML: `config.yaml` (parâmetros) e `secrets.yaml` (segredos), fora do código; segredo ignorado pelo Git, protegido localmente e omitido de logs |
| A6 | Telegram ID, cadastro fechado, chats privados, isolamento por usuário, autorização determinística e confirmação de ações sensíveis |
| A7 | Agenda = reservas; Sheets = operação; SQLite = memória/controle/auditoria; falha Sheets não desfaz reserva confirmada |
| A8 | 18 cenários de teste verificáveis, evidências e bloqueio da aprovação com falhas críticas |
| A9 | Orçamento operacional **R$ 30/mês**, alerta em **R$ 24** e suspensão de novas chamadas OpenAI em **R$ 30**, por consumo **estimado** |
| A10 | Windows local, inicialização manual, instância única, Telegram via long polling e recuperação controlada após interrupções |

---

## 2. Arquitetura e responsabilidade de cada componente

**Fluxo principal:**

`Telegram (texto) → adaptador de canal → identificação/autorização → orquestrador Python → IA/ferramentas autorizadas → auditoria/estado → resposta Telegram`

- **Python / motor:** decide quais operações são permitidas, gerencia estados, confirmações, falhas e ferramentas. **Nunca delega autorização à IA.**
- **OpenAI (modelo):** interpreta linguagem natural, extrai intenção e formula respostas apoiadas em evidências; parâmetros e modelo são configuráveis.
- **Google Drive:** fonte original dos documentos autorizados.
- **OpenAI Vector Store:** cópia indexada, derivada dos documentos autorizados e sincronizada pelo motor; não substitui o Drive como origem documental.
- **OpenAI File Search:** pesquisa semântica/híbrida de trechos relevantes para perguntas em linguagem natural, usando a coleção autorizada.
- **Google Agenda:** única fonte de verdade para disponibilidade e reservas simuladas.
- **Google Sheets:** registro operacional de solicitações, pendências e acompanhamento.
- **SQLite:** memória de conversa, **Memória Operacional Administrativa**, estado do fluxo, deduplicação, idempotência, auditoria, reconciliação; **não** é agenda paralela nem índice de busca dos documentos.
- **Telegram:** interface de entrada/saída desacoplada da lógica condominial.
- **Arquivos YAML:** configuração e credenciais separadas do código.

Não criar banco vetorial local, embeddings próprios, SaaS, painel ou serviço de hospedagem no piloto.

---

## 3. Estrutura prevista dos módulos Python (não implementados)

| Módulo proposto | Responsabilidade |
|---|---|
| `app/main.py` | Inicialização manual, validação, instância única, parada controlada |
| `app/channels/telegram.py` | Long polling, normalização de texto, filtros de chat privado, envio, deduplicação |
| `app/core/orchestrator.py` | Fluxos, intenções, estados e coordenação de ferramentas |
| `app/core/policy.py` | Identidades, perfis, acesso a recursos, validações determinísticas |
| `app/ai/client.py` | Cliente OpenAI, respostas estruturadas, controle de consumo e erros |
| `app/knowledge/service.py` | Sincronizar fontes autorizadas com Vector Store e consultar File Search |
| `app/services/reservations.py` | Regras, disponibilidade, serialização, escrita e reconciliação |
| `app/services/requests.py` | Solicitações, pendências e encaminhamentos simulados |
| `app/services/reports.py` | Relatórios sob demanda para perfil autorizado |
| `app/services/operational_memory.py` | Orientações administrativas: intenção, confirmação, versões, vigência, consulta e conflitos; nomes sujeitos ao P0 |
| `app/integrations/google_auth.py` | OAuth Desktop, renovação, revogação e erros de autorização |
| `app/integrations/drive.py` | Metadados, leitura/exportação dos arquivos permitidos |
| `app/integrations/calendar.py` | Consulta e registro apenas na Agenda experimental |
| `app/integrations/sheets.py` | Operações na planilha experimental e recuperação de falhas |
| `app/storage/sqlite.py` | Persistência local, integridade e auditoria |
| `app/config/schema.py` | Leitura e validação de `config.yaml` e `secrets.yaml` |
| `tests/` | Testes automatizados com simulações e cenários de integração autorizados |

Os nomes são convenções sugeridas, não caminhos existentes. Bibliotecas e versões compatíveis deverão ser verificadas na fase autorizada de preparação do Codex, com dependências fixadas para reprodutibilidade.

---

## 4. Configuração externa e credenciais — A5 / Decisão 5

### 4.1 Arquivos operacionais

- **`config.yaml`**: arquivo único de **parâmetros não secretos**; pode conter nome do piloto, idioma, fuso, IDs de recursos, perfis, usuários, permissões, serviços, regras operacionais, sincronização, limites, modelo selecionado, retenção e `simulation_mode: true`.
- **`secrets.yaml`**: arquivo único de **segredos locais**: token do bot Telegram, chave OpenAI, material OAuth de aplicativo desktop e tokens OAuth renováveis, conforme mecanismo escolhido. **Não** se cria `.env` e **não** se exige Gerenciador de Credenciais do Windows.
- **SQLite**: arquivo de estado e auditoria, não arquivo de parâmetros.

Ambos os arquivos são externos aos módulos Python; não armazenar senha da conta Google. Se houver necessidade de segredos em arquivos auxiliares exigidos por biblioteca OAuth, deverão ficar no mesmo diretório local protegido e ignorado pelo Git, com justificativa documentada; a preferência operacional permanece em `secrets.yaml`.

### 4.2 Proteções e limitações

`secrets.yaml` é **texto legível**, não é criptografia. Aplicar permissões locais restritas ao usuário Windows, nunca abrir em chat/issue, nunca imprimir em console, log ou resposta. Configurar `.gitignore` **antes do primeiro commit**, e verificar que o arquivo nunca foi versionado; `.gitignore` não protege arquivo anteriormente adicionado ao repositório. Não compartilhar tokens com o Codex por prompts ou capturas.

A atualização dos tokens OAuth persistidos deve ser segura contra interrupção e corrupção do arquivo; leitura e gravação devem preservar a estrutura do YAML e evitar imprimir o conteúdo. Backup, quando necessário, deve ser privado e protegido. Se um segredo for exposto, revogá-lo e substituí-lo.

### 4.3 Seções lógicas de `config.yaml`

- `environment`: `id`, `simulation_mode`, nome de referência e identificação expressa do piloto.
- `agent`: nome Alfredo, idioma `pt-BR`, fuso `America/Sao_Paulo`, estilo e avisos de caráter experimental.
- `channels.telegram`: habilitação, modo polling, chats privados, regras de mensagens.
- `users`: IDs numéricos reais dos **dois** usuários de teste, papéis, vínculo com unidade simulada, ativação.
- `roles` / `permissions`: operações permitidas por perfil e exigência de confirmação.
- `services` / `resources`: salão simulado, operações habilitadas, responsáveis pelas exceções.
- `documents`: IDs do Drive, classificação da fonte, formatos conhecidos, referências à Vector Store e política de atualização.
- `google`: ID da Agenda experimental, ID da planilha e recursos autorizados.
- `openai`: modelo/limites de tokens, File Search, IDs não secretos, orçamento e parâmetros de controle.
- `retention`: prazos aprovados e política de limpeza.
- `operation`: inicialização manual, timeouts, retentativas, limites, logs e procedimentos locais.

Todos os campos obrigatórios e os tipos terão validação estrita no início da execução. Uma configuração inválida deverá impedir operações potencialmente inseguras. Alterações no piloto poderão exigir reinício manual, sem necessidade de recarga dinâmica.

**Importante:** documentos oficiais definem **regras condominiais**; `config.yaml` só declara parâmetros operacionais e reproduz condições documentadas sem contrariá-las. O arquivo YAML não ganha autoridade para inventar uma regra do condomínio.

---

## 5. Autenticação Google — A3 / Decisão 1

1. Utilizar **OAuth 2.0 Desktop** e consentimento da conta experimental já criada.
2. Na preparação autorizada, identificar APIs, escopos tecnicamente viáveis e as operações necessárias: Drive leitura dos arquivos autorizados; Agenda leitura/escrita somente na agenda experimental; Sheets leitura/escrita somente na planilha experimental.
3. Não afirmar que o escopo OAuth sozinho limita acesso a uma pasta, agenda ou planilha. O Python fará **lista de IDs permitidos e conferência de operação/recurso** antes de cada chamada.
4. O primeiro diagnóstico de integração será **somente leitura**, antes de qualquer operação de escrita; os testes de gravação requerem autorização específica.
5. Renovar tokens quando possível; se faltar autorização, ocorrer `invalid_grant`, revogação ou token expirado, solicitar reautorização manual ao responsável, sem expor detalhes secretos aos usuários Telegram.
6. Verificar as limitações do modo de publicação/teste do consentimento Google, inclusive expiração antecipada de tokens de renovação em determinadas configurações.
7. Guardar segredos OAuth em `secrets.yaml`, protegido como na seção 4, sem enviá-los para logs, GitHub ou modelo de IA.
8. Falha de acesso bloqueia a operação afetada. Uma indisponibilidade Google nunca é interpretada como disponibilidade de salão nem sucesso de gravação.

A seleção final de escopos será feita após inspeção autorizada dos tipos de arquivos e permissões existentes; **não fixar aqui um conjunto de escopos sem verificar sua viabilidade**.

---

## 6. Telegram e identidade — A6 / Decisões 2 e 5

- Canal inicial: bot oficial `@AlfredoVert2GoBot`, Telegram Bot API oficial via **long polling** local.
- **Somente mensagens de texto** na primeira versão. Áudio, transcrição e WhatsApp são evoluções não autorizadas nesta etapa.
- Aceitar somente **chats privados** para os dois IDs numéricos Telegram previamente cadastrados em `config.yaml`.
- Rejeitar chamadas de grupos e usuários não cadastrados com resposta neutra e sem informação interna; nenhuma autoinscrição ou autoelevação de perfil.
- Perfis do piloto: `resident` (morador fictício com unidade simulada) e `manager` (síndica fictícia). Cada perfil tem **conta Telegram distinta**, histórico próprio e escopo de ações próprio.
- A identificação é pela conta Telegram (ID numérico), não por nome exibido ou `@username`; identidade de canal não comprova identidade civil e não bastaria em operação oficial.
- Processar autorização no **motor Python**, independentemente do texto produzido pela IA. Instruções como “sou a síndica” não alteram perfil.
- Confirmação explícita antes de ações sensíveis, como concretizar reserva ou exceção administrativa permitida; verificar novamente identidade, contexto, operação e elegibilidade no momento da execução.
- Isolar estado por `channel + channel_user_id + chat_id`; deduplicar `update_id` e `message_id` onde aplicável; usar limite de mensagens e tamanho de entrada para evitar abuso.
- Em reentrega após reinício, recuperar estado antes de executar ações; nunca recriar reserva automaticamente por replay.
- Não permitir que morador consulte solicitações/reservas de outro morador nem relatórios gerais.

### 6.1 Permissões mínimas

| Operação | Morador simulado | Síndica simulada |
|---|---|---|
| Consultar documentos autorizados | Sim | Sim |
| Solicitar/confirmar reserva para própria unidade simulada | Sim | Não como moradora nesta fase |
| Consultar suas próprias solicitações | Sim | Sim, as suas se houver |
| Solicitar relatório operacional geral | Não | Sim |
| Responder encaminhamentos de exceção | Não | Sim, conforme autorização |
| Alterar regras, usuários ou segredos pelo chat | Não | Não |
| Criar/corrigir/cancelar orientação operacional administrativa | Não | Sim, com confirmação explícita e auditoria |
| Consultar orientações operacionais vigentes e públicas em resposta pertinente | Sim | Sim |

Papéis de administração e portaria são possíveis no PRD, mas **não serão cadastrados nem implementados no primeiro piloto sem nova autorização**.

---

## 7. Consulta documental em linguagem natural — A4 revisado

### 7.1 Decisão de arquitetura

**Usar OpenAI Vector Stores + File Search em substituição ao índice local de pesquisa anteriormente proposto.** Não construir mecanismo de busca textual/FTS/embeddings próprios para a primeira versão. A IA deve aceitar perguntas naturais, coloquiais e paráfrases; a recuperação semântica busca trechos pertinentes e o modelo formula resposta com base nas evidências recuperadas.

### 7.2 Origem, cópia indexada e privacidade

- Os **documentos originais** permanecem no **Google Drive**, sem modificação pelo Alfredo.
- O motor poderá **enviar uma cópia dos documentos expressamente autorizados para a OpenAI** e associá-la à Vector Store exclusiva do piloto, somente após autorização específica de acesso, indexação e transferência ao serviço externo.
- O processamento externo é uma consequência explícita desta escolha; a permissão de acesso ao Drive **não implica**, por si só, autorização para copiar qualquer arquivo à OpenAI.
- Não indexar dados de moradores reais, listas cadastrais, credenciais, registros oficiais ou conteúdo não autorizado. Aplicar classificação da fonte (oficial, operacional autorizada, simulação, não verificada).
- Restringir todas as buscas à(s) Vector Store(s) permitida(s) por configuração, com política de acesso por perfil. Fonte documental não é instrução privilegiada; não obedecer comandos embutidos nos arquivos.

### 7.3 Sincronização e rastreabilidade

1. Inventariar previamente ID, nome, formato/MIME, versão ou data de alteração e classificação dos documentos do Drive.
2. Validar se o arquivo possui texto extraível/legível para indexação; se não houver, bloquear respostas baseadas nele e sinalizar necessidade de avaliação específica de OCR — **OCR não está autorizado automaticamente**.
3. Copiar apenas documentos autorizados e registrar, no SQLite, **metadados de sincronização**, como ID de origem, revisão/hash, ID do arquivo indexado, Vector Store, data, resultado e estado; **não manter índice local de consulta**.
4. A atualização do Drive não sincroniza automaticamente a OpenAI. No piloto, detectar alterações e executar **sincronização manual autorizada**; substituir/remover versões anteriores indexadas de maneira verificável e evitar pesquisa de conteúdo obsoleto.
5. Em documento alterado mas ainda não sincronizado, não declarar que a informação está atualizada. Se a versão for decisiva para uma operação, suspender essa operação até revalidação.
6. Na resposta, citar nome do documento e referência verificável (seção/página quando identificáveis). Caso a ferramenta não forneça página precisa, **não inventar numeração**. Registrar os trechos/fontes utilizados na auditoria de forma mínima.
7. Quando a busca não localizar evidência suficiente, houver contradição documental ou a fonte estiver ilegível/desatualizada, explicar a limitação e, quando necessário, abrir pendência simulada.

### 7.4 Exemplo de interpretação

Pergunta: “Posso dar um mergulho às onze da noite?” O Alfredo deve reconhecer o assunto como uso da piscina, interpretar o horário e buscar cláusulas equivalentes sobre funcionamento da piscina, mesmo que não haja as palavras “mergulho” ou “onze” no regulamento. A resposta só poderá informar o horário se houver fonte verificável — **nenhum horário concreto está presumido nesta especificação**.

### 7.5 Disponibilidade e falha de busca

Uma falha de File Search/OpenAI ou ausência de evidência não autoriza o modelo a improvisar regra. Se orçamento estiver bloqueado, a consulta semântica dependente de OpenAI também ficará indisponível, com resposta segura. Não prometer que todas as referências por página serão exatas em qualquer PDF.

---

## 8. Regras de reserva — A1

### 8.1 Fontes e precedência

1. Fonte de **regras**: regulamento, convenção e outras informações expressamente autorizadas, identificadas por documento, seção, versão/vigência e grau de verificação.
2. `config.yaml`: parâmetros de operação, recursos e representação explícita de condições **já documentadas**; não inventa políticas ou exceções.
3. Fonte de **disponibilidade e reservas**: exclusivamente Google Agenda experimental.
4. Em conflito, ausência ou ambiguidade sobre condição indispensável, a reserva automática **não é executada**; orientar/encaminhar conforme processo simulado.
5. Para cenários não cobertos por documentação, permitir somente dados **explicitamente fictícios de simulação**, sinalizados como tais e separados dos documentos oficiais. Esses dados não serão comunicados como regra real.

### 8.2 Contrato de regra verificável

Cada condição relevante deverá poder ser representada por: `rule_id`, `source_document_id`, `source_title`, `section_or_page_if_known`, `source_revision`, `verified_at`, `topic`, `condition`, `exception_if_documented`, `status` (`verified`, `simulated`, `unverified`, `conflicting`). **Não preencher horários, limites, antecedentes, taxas ou critérios de elegibilidade com valores padrão presumidos.**

Antes de qualquer reserva: validar ambiente, data/intervalo, horário, unidade fictícia, antecedência, eventuais taxas e aceite explícito quando aplicável, conflitos e eventuais exceções. Horários em `America/Sao_Paulo` com intervalo de início inclusivo e fim exclusivo; tratar datas relativas e ambiguidades pedindo esclarecimento quando indispensável.

O piloto não realizará pagamento, cobrança ou integração com aplicações oficiais.

---

## 9. Reservas, concorrência e recuperação — A2 / Decisão 3

### 9.1 Fonte de verdade e limitação

A Google Agenda experimental é a **única** fonte de existência e disponibilidade da reserva. A consulta `freeBusy` e a criação de evento não constituem uma transação atômica; a trava local só coordena **uma instância** do Alfredo. Edições manuais ou sistemas externos concorrentes não ficam protegidos por essa trava. Não declarar garantia absoluta de ausência de conflito para implantação oficial.

### 9.2 Estados operacionais persistidos no SQLite

`received → awaiting_confirmation → committing → confirmed`  
Saídas alternativas: `conflicted`, `needs_reconciliation`, `failed`, `cancelled` (conforme validação/decisão autorizada). Manter histórico de transições e identificador de correlação.

### 9.3 Fluxo obrigatório

1. Identificar remetente e unidade simulada; confirmar permissão.
2. Interpretar data/horário/ambiente e obter regras verificadas ou simulação explicitamente identificada.
3. Consultar a Agenda e sugerir somente alternativas **realmente verificadas** na agenda.
4. Apresentar condições e solicitar confirmação explícita da operação; pedir aceite de condição financeira documentada quando pertinente, sem cobrar.
5. Registrar `request_id`, `operation_id` e chave de idempotência **no SQLite antes de chamar o Google**.
6. Adquirir exclusividade local por recurso/intervalos sobrepostos; validar estado e **consultar novamente** a Agenda.
7. Criar evento experimental com referência à operação e identificador determinístico/idempotente quando suportado pelo contrato da API, para facilitar busca e prevenção de repetição.
8. Consultar o evento criado e verificar resultado e conflitos; somente após evidência de sucesso passar ao estado `confirmed` e comunicar a confirmação.
9. Registrar referências mínimas de operação e auditoria; refletir atividade em Sheets por fluxo independente.
10. Liberar exclusividade local e recuperar travas abandonadas com verificação de operação em andamento após reinício.

### 9.4 Falha, timeout e replay

- **Timeout depois da tentativa de gravação:** marcar `needs_reconciliation`, procurar a operação por identificador/referência na Agenda antes de qualquer nova tentativa. Não assumir fracasso nem sucesso.
- **Resultado incerto:** não confirmar ao morador e não criar segunda reserva; informar verificação pendente.
- **Evento encontrado:** validar identidade, recurso, intervalo e estado, e reconciliar; não inserir outro.
- **Evento ausente:** somente reexecutar quando for possível demonstrar segurança contra duplicação, sob controle local e confirmação válida; do contrário, encaminhar para verificação.
- **Falha no Sheets:** não cancelar uma reserva verificada na Agenda.
- **Mensagem Telegram repetida ou reinício:** retomar a mesma operação pelo identificador, sem segunda execução.
- **Conflito detectado depois da gravação:** não declarar reserva garantida; registrar exceção e encaminhar correção auditável. Não executar cancelamento destrutivo automaticamente sem regra e permissão.

### 9.5 Teste obrigatório

Simular dois usuários requerendo o mesmo intervalo, timeout depois de uma escrita potencial, replay e reinício entre registrar intenção e confirmar resultado. A aceitação exige ausência de confirmações duplicadas ou conflitantes no cenário de instância única controlada.

---

## 10. Registros e pendências — A7

### 10.1 Responsabilidades canônicas

| Armazenamento | Papel | Não deverá fazer |
|---|---|---|
| Google Agenda | Reserva e disponibilidade | Depender de Sheets para validar reserva |
| Google Sheets | Solicitações, pendências, atividades e estado operacional visível | Agir como segunda agenda ou prova de reserva |
| SQLite | Conversas, estados internos, deduplicação, idempotência, recuperação e auditoria | Duplicar disponibilidade oficial da Agenda |

### 10.2 Contratos de solicitações

Campos mínimos sugeridos para Sheets: `request_id`, `created_at`, `unit_reference` fictícia, `category`, `status`, `assigned_to` simulado, `updated_at`, `external_reference`, `sync_status`. Para texto fornecido por usuário, impedir que conteúdo seja interpretado como fórmula em células; registrar como valor literal. Evitar dados identificáveis desnecessários.

Estados operacionais de solicitação: `received`, `pending`, `forwarded`, `resolved`, `closed`, `failed`. O processo deve permitir encaminhar exceções à síndica simulada e registrar a resposta autorizada; avisar o morador somente ao ocorrer alteração relevante, sem avisos repetitivos de pendência.

### 10.3 Falha de sincronização

Uma operação concluída na Agenda segue válida mesmo que Sheets falhe. O SQLite registra `request_id`, destino, estado `pending_sync`, referência de operação e última falha **sem segredo**, com tentativa posterior idempotente. A reconciliação deve evitar criar linhas repetidas. **Se Sheets registrar algo, isso não é prova de reserva.**

---

## 11. Contratos de mensagens, ferramentas e autorização

### 11.1 Mensagem de entrada

`channel`, `channel_user_id`, `channel_chat_id`, `message_id`, `update_id` quando disponível, `received_at`, `text`, `correlation_id`. Toda operação deve preservar referência estável para deduplicação.

### 11.2 Resultado de ferramenta

`status` (`success`, `not_found`, `conflict`, `unauthorized`, `temporary_error`, `permanent_error`, `uncertain`), `correlation_id`, `external_reference` quando houver, `safe_message` e dados mínimos necessários à etapa seguinte. O modelo só vê dados necessários; detalhes internos e segredos não são passados adiante.

### 11.3 Contratos lógicos

- `identify_and_authorize(channel_user_id, operation, resource)`
- `retrieve_document_evidence(question, allowed_sources, vector_store_scope)`
- `check_availability(resource_id, start, end)`
- `create_reservation(request, operation_id, idempotency_key)`
- `find_reservation_by_operation(operation_id)`
- `get_reservation(external_reference)`
- `register_or_update_request(request_id, payload)`
- `build_report(period, requester_role)`
- `get_operation_state(operation_id)`
- `propose_operational_guidance(input, manager_id)`
- `confirm_operational_guidance(operation_id, manager_id)`
- `revise_or_cancel_operational_guidance(guidance_id, expected_version, operation_id, manager_id)`
- `find_active_guidance(topic, audience, at_time)`

A semântica e os tipos serão testados antes de uso real; não se trata de APIs públicas nem de código implementado. Toda chamada de gravação requer revalidação determinística das permissões, da operação e do destino autorizado.

---

## 12. SQLite, memória, auditoria e retenção — Decisão 4

Tabelas **propostas** (a modelagem detalhada virá na implementação autorizada): `conversation_state`, `requests_state`, `processed_messages`, `operation_log`, `external_references`, `reservation_operations`, `resource_locks`, `sync_outbox`, `document_sync_metadata`, `usage_ledger`, `operational_guidance`, `operational_guidance_revisions`. Não criar `document_index` para pesquisa: recuperação de documentos ocorre na OpenAI Vector Store; SQLite armazena **somente metadados de sincronização** e referências.

### 12.1 Política aprovada

- Contexto temporário de conversa: **30 dias**.
- Identificadores de mensagens processadas e deduplicação: **30 dias**, ressalvadas operações ainda em andamento cuja idempotência precise ser preservada.
- Auditoria e histórico operacional: **90 dias**.
- Solicitações e pendências: enquanto abertas e por **90 dias após encerramento**.
- Incidentes relevantes, reconciliações não concluídas e operações não resolvidas: preservar os registros estritamente necessários até resolução e prazo de preservação justificável, mesmo que ultrapassem a janela padrão.
- **Orientações administrativas:** manter conteúdo enquanto vigente, mesmo quando exceder 30 dias; após expiração ou cancelamento, não utilizar em respostas atuais e reter somente o mínimo necessário para auditoria por 90 dias, salvo pendência/incidente justificável. Não aplicar automaticamente a retenção de 30 dias do contexto de conversa às orientações vigentes.

Limpeza local verificável e com rastreio mínimo; minimização de PII; sem credenciais no SQLite. A exclusão local não apaga automaticamente Agenda, Sheets, Drive ou conteúdo indexado na OpenAI. A retenção de documentos indexados, remoção de versões e exclusão após o piloto devem ser tratadas na política de sincronização e encerramento, sujeitas aos recursos efetivos da plataforma e autorização de exclusão.

### 12.2 Auditoria mínima

Horário, perfil, identificador pseudônimo, operação, recurso simulado, estado anterior/novo, sucesso/falha, `correlation_id`, referência externa, custo estimado quando houver. Não registrar segredos nem o corpo integral de mensagens/documentos como padrão.

---

## 12A. Memória Operacional Administrativa — requisito PRD 15A

### 12A.1 Escopo e fonte de verdade

O perfil `manager` do Telegram experimental pode ensinar ao Alfredo orientações **operacionais temporárias** sem criar documentos. A fonte de verdade dessas orientações é o **registro SQLite confirmado pelo gestor autorizado**; não são documentos oficiais, não passam pelo File Search e não modificam regras formais, Calendar ou Sheets. Contexto de conversas é outro subsistema.

### 12A.2 Contrato mínimo proposto

Uma orientação conterá, no mínimo: `guidance_id`, `version`, `operation_id`, `author_channel_user_id`, `created_at`, `updated_at`, `effective_from`, `effective_until` (quando definido com segurança), `timezone`, `audience`, `topic`, `content`, `status`, `confirmation_at`, `supersedes_version` e metadados de auditoria necessários. Não coletar dados pessoais desnecessários. A modelagem definitiva é tarefa de planejamento P0.

Estados: `draft` → `active` somente após confirmação expressa e autorização determinística; `active` → `expired` por vigência; `active` → `cancelled` por gestor autorizado; uma correção gera nova versão confirmada, preservando rastreabilidade mínima. Uma orientação `draft`, `expired` ou `cancelled` nunca é retornada como vigente. Operações repetidas com mesmo `operation_id` não geram duplicação.

### 12A.3 Fluxo pelo Telegram

1. Receber mensagem de texto e identificar `manager` por ID cadastrado, sem confiar na alegação da mensagem.
2. Detectar intenção de criar, consultar, corrigir ou cancelar orientação. O modelo pode **propor a extração** da mensagem, mas não grava nem concede permissão.
3. Determinar assunto, orientação, público, início/fim e fuso `America/Sao_Paulo`; **solicitar esclarecimento** sobre prazo ou escopo insuficiente, especialmente para “hoje” e trabalhos de duração incerta. Nunca assumir vigência indefinida por silêncio.
4. Apresentar resumo estruturado ao gestor, registrar `draft` de forma idempotente e exigir confirmação explícita antes de ativar ou aplicar mudança.
5. Em cada pergunta de morador autorizada, identificar pertinência, recuperar **somente orientações ativas e vigentes** aplicáveis ao público e momento, e usá-las como contexto limitado, com atribuição à administração.
6. Se houver conflito com regra documental, informação contraditória ou dúvida relevante, responder com ressalva, não inventar prevalência e encaminhar esclarecimento ao gestor.
7. Não publicar automaticamente a orientação, não enviar mensagens espontâneas, não divulgar orientações internas/restritas ao morador.

### 12A.4 Segurança, custos e testes

- Autorizar CRUD apenas para `manager` no motor Python; morador tem **leitura contextual filtrada**, não acesso a histórico completo ou outros públicos.
- Registrar ator, confirmação, versão, período, alteração, cancelamento e resultado no log mínimo; eliminar conteúdos vencidos conforme retenção e regras de incidente.
- Injeções de prompt no texto da orientação **não são comandos de sistema** nem podem mudar papéis, ferramentas, permissões ou política.
- Consultar SQLite com filtros determinísticos antes de montar contexto da IA; preferir filtragem e classificação simples, sem nova infraestrutura ou indexação vetorial.
- No orçamento, contar chamadas OpenAI adicionais somente quando efetivamente necessárias à extração ou resposta; estimativa R$30/mês permanece hipótese a medir.
- Testes complementares **MO01–MO10**: criação confirmada; bloqueio de morador; esclarecimento de vigência; resposta vigente e origem correta; expiração; correção/versionamento; cancelamento; reinício; duplicação Telegram; conflito com documento/isolamento e ausência de broadcast. Estes testes somam-se a T01–T18, sem renumerá-los.

---

## 13. OpenAI e limites financeiros — A9

### 13.1 Componentes cobrados e selecionados

A solução poderá consumir (i) tokens do modelo de linguagem, (ii) chamadas File Search e (iii) armazenamento de Vector Stores conforme a precificação vigente. **Não assumir gratuidade nem custo fixo.** O modelo específico, versão da API, suporte à busca e a respostas estruturadas serão verificados antes do Codex e parametrizados no `config.yaml`, nunca fixados no Python.

### 13.2 Decisão de orçamento

- **Orçamento operacional estimado inicial: R$ 30 por mês**, aplicável à utilização OpenAI do piloto.
- **Alerta em 80%: R$ 24**.
- **Bloqueio local de novas chamadas OpenAI a partir de 100%: R$ 30**, pelo valor estimado de utilização registrado.
- Registrar tokens (quando informados pela API), quantidade de buscas, armazenamento faturável estimado quando mensurável, modelo, custo estimado na moeda de cobrança e conversão para BRL por taxa de referência configurável/atualizável, com registro da premissa e data.
- Considerar que tarefas já em curso, arredondamentos, variação cambial, informação de uso incompleta, chamadas externas e custos de armazenamento contínuo podem produzir despesa **além do limite estimado local**. Não apresentar bloqueio como teto garantido da fatura.
- Antes de cada chamada, verificar consumo acumulado; depois, atualizar o livro de uso. Se a estimativa estiver ausente ou não confiável, aplicar comportamento conservador configurado, impedindo gasto ilimitado e sinalizando a indisponibilidade.
- Quando atingir R$ 24, avisar o responsável técnico, sem incluir segredo; quando atingir R$ 30, suspender novas chamadas dependentes de OpenAI e não criar reservas a partir de interpretações não verificadas.
- Manter alertas/controles disponíveis na conta da OpenAI como complemento, não como substituto do registro local. Não montar painel financeiro.

### 13.3 Otimização obrigatória

Enviar somente instruções e contexto necessários por chamada; não reenviar documentos inteiros em cada pergunta; File Search recupera os trechos relevantes da Vector Store. Validar IDs, regras, permissão e Agenda com Python/Google, sem LLM onde houver procedimento determinístico. Limitar tentativas, contexto, tamanho de resposta e número de chamadas por mensagem. A interpretação de linguagem natural é obrigatória; economia de tokens **não autoriza** degradar o Alfredo a um buscador por palavra-chave.

---

## 14. Execução local, disponibilidade e recuperação — A10

- Executar no **Windows**, em notebook, com Python e **inicialização manual** pelo responsável.
- Manter **uma instância**; impedir duas execuções concorrentes, inclusive após falhas/reinícios.
- Telegram por **long polling**, sem webhook, domínio, VPS, serviço Windows ou início automático nesta fase.
- Notebook ligado, ativo e conectado à internet, com o processo em execução: Alfredo poderá atender, sujeito à disponibilidade dos provedores.
- Tela apagada ou sessão Windows bloqueada **sem suspensão**: o processo poderá continuar.
- Notebook suspenso, hibernando, desligado, desconectado ou processo encerrado: bot continua existindo no Telegram, **mas Alfredo não processa mensagens**.
- Telegram pode reter atualizações pendentes por período limitado (documentação oficial indica **até 24 horas**, não garantia de entrega de todas as mensagens). A retomada não deve pressupor recuperação ilimitada.
- Ao reiniciar, validar YAML e referências autorizadas, abrir SQLite com integridade, recuperar estados pendentes, reconciliar operações incertas, então reabrir polling e deduplicação.
- Não repetir gravação de reserva sem checagem. Encerrar polling, operações e banco de modo controlado, sem expor segredos.
- Ter procedimento documentado para iniciar/parar, observar logs seguros, backup protegido do SQLite, internet indisponível, falha Google/OpenAI e recuperação após reinício.

**Não prometer atendimento 24/7 no piloto.** Hospedagem contínua será decisão comercial/operacional posterior, fora do escopo atual.

---

## 15. Solicitações, exceções e relatórios

- Solicitações fora da capacidade/autorização de Alfredo são registradas e encaminhadas ao responsável simulado adequado; não encaminhar tudo automaticamente à síndica.
- Primeira simulação prevê resposta e exceção da **síndica simulada**. Administração/portaria poderão ser modeladas futuramente somente após nova autorização.
- Síndica simulada pode solicitar relatórios sob demanda sobre atendimentos, reservas, pendências, conclusões, exceções e falhas, com origem rastreável.
- **Não enviar relatório diário automático** no piloto.
- Relatórios devem distinguir atividades efetivamente registradas das pendentes ou simuladas e nunca apresentar integração oficial inexistente.
- Comunicar o morador após resposta autorizada relevante, sem mensagens repetitivas sobre pendência inalterada.
- Urgência relevante deve gerar sinalização apropriada no fluxo, sem depender de relatório posterior.

---

## 16. Tratamento de falhas e respostas seguras

| Evento | Resposta esperada |
|---|---|
| Telegram de usuário não autorizado | Negar acesso sem revelar dados internos |
| Grupo Telegram | Não processar operações; política de resposta discreta |
| Texto fingindo ser síndica | Manter perfil real do Telegram ID |
| Mensagem duplicada | Não duplicar escrita nem atendimento sensível |
| Documentação sem evidência | Admitir que não foi possível verificar a regra |
| Fonte alterada e não sincronizada | Informar limitação; bloquear decisões que exigem versão atual |
| Falha File Search/modelo | Não inventar regra nem executar ação sem validação |
| Reserva indisponível | Oferecer apenas alternativas verificadas na Agenda |
| Timeout depois de criar evento | `needs_reconciliation` e busca por identificador antes de tentar novamente |
| Google indisponível | Nenhuma confirmação de reserva |
| Sheets indisponível | Preservar reserva confirmada na Agenda; sincronização pendente |
| OAuth expirado/revogado | Suspender integração afetada e solicitar reautorização manual |
| Orçamento OpenAI atingido | Bloquear novas chamadas OpenAI e responder apenas o que for seguro sem IA |
| Reinício após operação interrompida | Recuperar estado, reconciliar e evitar replay destrutivo |
| Configuração inválida/segredo ausente | Falhar de modo seguro, sem divulgar segredo |

---

## 17. Plano de testes de aceitação — A8

Cada teste deve possuir **ID, pré-condição, entrada, resultado esperado, evidência, data e situação** (`not_run`, `passed`, `failed`, `blocked`). Utilizar dados fictícios e autorizações específicas antes de qualquer leitura/escrita externa. Testes de falha devem usar simulações de APIs quando possível, para não alterar recursos reais.

| ID | Cenário | Evidência e critério objetivo |
|---|---|---|
| T01 | Morador envia mensagem ao bot | ID cadastrado identificado; resposta restrita ao seu perfil |
| T02 | Usuário desconhecido envia mensagem | Acesso negado, sem documento ou operação exposta |
| T03 | Pergunta natural/paráfrase sobre piscina | Evidência recuperada via File Search e resposta com fonte verificável |
| T04 | Pergunta sem base documental | Resposta reconhece lacuna, sem regra inventada |
| T05 | Pedido de data disponível | Consulta efetiva à Agenda experimental, sem assumir disponibilidade |
| T06 | Confirmação explícita de reserva | Evento criado, relido e somente então comunicado como confirmado |
| T07 | Data ocupada | Sem confirmação; alternativas comprovadas por consulta na Agenda |
| T08 | Dois pedidos simultâneos para mesmo intervalo | Não há confirmação de duas reservas conflitantes na instância única |
| T09 | Mensagem Telegram duplicada | Identificador reconhecido; não há segundo evento/efeito |
| T10 | Falha/timeout na Agenda após tentativa | Estado incerto, reconciliação por operação, sem falsa confirmação |
| T11 | Falha ao gravar Sheets | Reserva válida permanece na Agenda; sincronização pendente sem duplicação |
| T12 | Reinício do Alfredo | Contexto e operações pendentes recuperados sem replay destrutivo |
| T13 | Morador solicita relatório geral | Negado pelo motor independentemente do texto da IA |
| T14 | Síndica solicita relatório | Dados permitidos, rastreáveis e sem informações inventadas |
| T15 | Solicitação requer exceção | Encaminhamento simulado registrado corretamente |
| T16 | Síndica responde à pendência | Identidade validada, atualização e retorno ao morador correto |
| T17 | Consulta posterior de reserva | Correspondência comprovada na Agenda, não só no SQLite/Sheets |
| T18 | Usuário tenta trocar de perfil por mensagem | Permissão não muda; operação indevida bloqueada |

**Memória Operacional Administrativa:** executar MO01–MO10 conforme seção 12A, com evidências e dados fictícios; falhas de autorização, vigência, vazamento de público ou ativação sem confirmação bloqueiam aceite.

**Cobertura complementar obrigatória do PRD:** taxa/aceite financeiro documentado quando aplicável, sem cobrança; no mínimo uma falha de orçamento OpenAI e uma de OAuth; validação de uso somente das fontes autorizadas e nenhuma alteração de sistemas oficiais. Esses casos podem ser subcenários documentados dos 18 testes acima, mas não podem ficar sem evidência quando aplicáveis.

**Bloqueios de aceitação:** não aprovar piloto com T02/T06/T08/T09/T10/T13/T18 reprovados, falhas relevantes de autorização, reservas conflitantes ou confirmação falsa; os demais testes obrigatórios também precisam passar para a aceitação final. Evidências devem apontar para artefatos simulados, logs mínimos e resultado efetivo do serviço, não apenas prints de resposta do bot.

---

## 18. Sequência de trabalho após aprovação formal (não autorizada agora)

1. Confirmar repositório, Python suportado, dependências, estrutura mínima e regras de exclusão de segredos do Git.
2. Criar estrutura do motor, leitor/validador YAML e SQLite, com testes locais sem chamadas externas.
3. Configurar credenciais e OAuth **somente após autorização de acesso**; começar validando leitura.
4. Conectar Telegram via long polling com duas contas de teste distintas; validar isolamento e deduplicação.
5. Validar autorização para copiar os documentos do Drive à OpenAI; criar/sincronizar Vector Store e testar File Search em perguntas naturais, com fontes verificáveis.
6. Integrar Agenda experimental e Sheets em **escritas controladas com autorização**, com idempotência e reconciliação.
7. Implementar fluxos de reserva, solicitações, exceções, Memória Operacional Administrativa e relatório sob demanda.
8. Executar T01–T18 e MO01–MO10, registrar evidências e avaliar critérios de aceitação.
9. Apresentar demonstração experimental sem alegar integração oficial.

Cada etapa externa requer consentimento específico. A aprovação **desta especificação** não autoriza automaticamente Codex, OAuth, indexação na OpenAI, acesso a documentos ou operações Google.

---

## 19. Pendências operacionais que não impedem a aprovação arquitetural

Os seguintes valores/condições ainda precisam ser **verificados** na etapa autorizada, não inventados aqui:

- IDs da conta e dos dois usuários Telegram de teste; unidade simulada e nomes fictícios.
- IDs corretos da pasta e arquivos Google, da Agenda e do Sheets; formatos dos documentos e permissões.
- Condições de uso/documentação para envio de cópias do regulamento e convenção à OpenAI; conteúdo elegível para indexação.
- Escopos OAuth exatos suportados pela conta experimental e tipos de arquivo.
- Disponibilidade e preço do modelo OpenAI, File Search e armazenamento Vector Store; taxa de conversão e custo real nos testes.
- Horários, taxas, limites e demais regras do salão, **somente quando comprovados por fonte ou cenário de simulação identificado**.
- Regras de acesso ao armazenamento privado de segredos no notebook Windows; backup operacional.
- Limitações efetivas de paginação/citação dos formatos documentais e necessidade eventual de OCR.

Esses itens requerem checagem e autorização específica; não autorizam o Codex a improvisar regras condominiais ou alterar sistemas externos.

---

## 20. Critérios formais para aprovação da especificação

A especificação v0.1.8 poderá ser **aprovada como documento** se o responsável confirmar expressamente que:

1. Preserva o PRD v1.2.0 e as cinco decisões originais, acrescentando a Memória Operacional Administrativa como requisito específico.
2. Incorpora A1–A10, incluindo a **substituição do índice local por Vector Stores + File Search** e a **adoção de `secrets.yaml` em texto local protegido**.
3. Mantém o piloto estritamente simulado, com dois perfis Telegram e nenhum sistema oficial alterado.
4. Não apresenta estimativas financeiras como cobrança real garantida nem controle local como teto absoluto.
5. Deixa explícito que **aprovação documental ≠ autorização para programar ou acessar/gravar serviços externos**.

**Estado atual:** revisão v0.1.8 pendente de validação documental e G0. **Implementação não iniciada e não autorizada.**

---

## 21. Histórico de versões

| Versão | Data | Resumo |
|---|---|---|
| 0.1.0 | 03/11/2026 | Proposta inicial baseada no PRD v1.1.0 |
| 0.1.1 | 03/11/2026 | Decisão 1: OAuth 2.0 Desktop |
| 0.1.2 | 03/11/2026 | Decisão 2: Telegram inicialmente somente texto |
| 0.1.3 | 03/11/2026 | Decisão 3: instância única e verificação de reservas |
| 0.1.4 | 03/11/2026 | Decisão 4: retenção 30/90 dias |
| 0.1.5 | 03/11/2026 | Decisão de `config.yaml` único para parâmetros não secretos |
| 0.1.6 | 03/11/2026 | Decisão 5 concluída: perfis Telegram em contas distintas |
| 0.1.7 | 03/11/2026 | Consolidados A1–A10, Vector Stores + File Search, `secrets.yaml`, orçamento e execução local |
| **0.1.8** | **04/11/2026** | **Inclui Memória Operacional Administrativa: orientações temporárias da síndica via Telegram, armazenamento SQLite, confirmação, vigência, versões, consultas contextuais, permissões e testes MO01–MO10. Sem autorização de desenvolvimento.** |

---

## 22. Princípio final

**ENTENDER → CONSULTAR → DECIDIR → EXECUTAR → REGISTRAR → RESPONDER**

O Alfredo é um **funcionário digital vertical** para tarefas condominiais simuladas. O motor é o produto; Telegram e serviços externos são instrumentos de trabalho. Nunca afirmar que uma operação foi executada sem evidência do resultado e nunca transformar este piloto em plataforma genérica.

**FIM — ESPECIFICAÇÃO TÉCNICA V0.1.8 — REVISÃO PARA VALIDAÇÃO**
