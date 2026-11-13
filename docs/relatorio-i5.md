# Relatório I5 — implementação local

## Estado vigente — cancelamento autorizado no Telegram — 13/11/2026

Responsável: Codex, após retorno do proprietário. Toninho recebeu a lista, escolheu
a opção 1, recebeu o resumo da reserva de 16/11/2026 das 16h às 19h e respondeu
“Autorizo”. O Alfredo informou sucesso. A conferência independente, somente leitura,
confirmou o evento escolhido como `cancelled` na Agenda e a reserva adjacente,
das 19h às 22h, como `confirmed`. Nenhum cancelamento parcial foi inferido.

O diário contém uma nova operação de cancelamento `confirmed`, às 15h16min44s de
Brasília. A reserva original permanece no SQLite, com proposta, referência externa
e auditoria preservadas. O recibo da resposta `reservation_cancelled` está `sent`;
o proprietário também confirmou seu recebimento pelo texto da conversa.
**Este percurso real de cancelamento passou.** A proposta antiga expirada permanece
como histórico separado e não foi reutilizada como autorização.

Há uma única atividade desse cancelamento na outbox, ainda `pending`. O total atual
é **três atividades pendentes e oito sincronizadas**. Não foi executada escrita na
planilha pelo agente de desenvolvimento. Próxima ação operacional: sincronização
autorizada pelo fluxo existente e conferência da atividade de cancelamento.

O painel está ATIVO, no modo `operations`. O contador agora registra uma falha e
duas notificações de prontidão, com última transição às 16h09 de Brasília. Portanto
houve uma reconexão posterior à janela de 90 segundos registrada abaixo; a ausência
de falhas naquela janela não significa estabilidade prolongada. Não se declara
resolvida toda a oscilação nem aceite integral da I5. O percurso real de Maria como
moradora, a sincronização pendente e o aceite aplicável permanecem pendentes.
I6 não autorizada; sem alterações de código, escritas Git ou publicação nesta
conferência. Os 538 testes locais anteriores não foram repetidos por esta atualização
somente documental. [Evidência do teste e leituras](evidencias/i5-reservation-cancellation-human-20261113.json).

Este estado substitui especificamente a pendência de conclusão humana do
cancelamento nos registros anteriores; os demais limites e históricos permanecem.

## Histórico da correção — oscilação de conexão e resposta à escolha 1 — 13/11/2026

Responsável: Codex. O proprietário relatou que o painel alternava ATIVO e SEM
CONEXÃO e não recebeu o resumo após escolher a primeira reserva. A leitura do
SQLite confirmou: a escolha foi processada, a proposta de cancelamento foi criada,
mas a resposta Telegram ficou `uncertain`. A reserva não foi cancelada pelo agente
de desenvolvimento e essa resposta não foi reenviada por suposição.

O proprietário esclareceu que os ensaios reais anteriores não apresentavam quedas.
A comparação de AST do cliente `TelegramAPI` e do conector TCP com o commit de
aceite I4 confirmou que eram iguais antes desta correção. Isso não determina uma
causa externa: a diferença observável foi medida em chamadas reais, e a oscilação
não foi atribuída definitivamente à rede/provedor. Houve encerramento prematuro
da investigação quando um estado ATIVO isolado foi tratado como recuperação final.

Correção aplicada: manter a conexão TLS saudável entre chamadas. Antes, cada método
abria e fechava outra conexão, inclusive a resposta imediatamente após o polling.
Agora o cliente só descarta a conexão quando o servidor indica fechamento, em erro
ou na parada. A abertura TCP/TLS é explícita e ocorre antes do envio HTTP. Uma falha
nessa fase comprova que `sendMessage` não saiu e conserva a resposta pendente com
o intervalo externo de nova tentativa. Após início do envio, continua `uncertain`,
sem repetição automática. O resumo antigo incerto não foi reclassificado como não
enviado nem foi usada sua escolha como confirmação do cancelamento.

**538 testes locais aprovados**, zero falhas/erros/ignorados, fontes protegidas e
hashes conferidos. As provas anteriores de 531 e 525 testes foram preservadas.
Novas coberturas: conexão reutilizada, fechamento pelo servidor, encerramento
explícito, distinção pré/pós-transmissão, resposta não enviada que pode ser tentada
novamente sem duplicar, registro seguro do controlador e launcher manual.

O teste real somente leitura encontrou falhas ao abrir a conexão, mas depois obteve
12 respostas `getMe` seguidas na mesma conexão. A prova mais longa passou com seis
respostas ao longo de 71,33 segundos, incluindo pausa de 30 segundos, sem consumir
mensagens ou enviar conteúdo. Evidências:
[chamadas seguidas](evidencias/i5-telegram-keepalive-readonly-20261113.json) e
[intervalos de inatividade](evidencias/i5-telegram-keepalive-soak-20261113.json).
Não comprovam sozinhas estabilidade prolongada de polling, entrega ou cancelamento.

O controlador registra somente estado/código/mode/PID/data e contadores em um
arquivo local, permitindo acompanhar a próxima partida sem novas verificações
manuais repetidas. O launcher mantém o painel canônico e aceita uma solicitação
manual `--start`; o atalho normal continua sem ligar automaticamente. O controle
remoto Windows permaneceu indisponível, portanto foi solicitado o fechamento
cooperativo da janela antiga antes de reabrir com o código atual. Estado dessa
recarga: o proprietário confirmou o fechamento, o painel foi reaberto e ligado
pelo mesmo controlador, em modo `operations`. O processo filho foi conferido e a
trava do consumidor permaneceu ocupada. Entre 15h11 e 15h13 de Brasília, foram
observados **90,06 segundos contínuos em ATIVO, com zero falhas de conexão**.
Não houve envio de mensagens nem escrita Google pelo observador.
[Observação do painel em execução](evidencias/i5-telegram-keepalive-panel-verified-20261113.json).
O primeiro monitor usou equivocadamente o PID do launcher em lugar do processo
filho; seu resultado foi preservado e anotado como erro do observador, sem
interpretá-lo como queda. A observação corrigida usa o PID do processo filho.

A leitura posterior do diário encontrou uma proposta encerrada (`cancelled`)
pela expiração na partida, sem cancelamento confirmado ou em execução. Esse estado
encerra a proposta antiga, não a reserva. Não foi reenviado o resumo incerto nem
enviada autorização pelo agente de desenvolvimento. A retomada do cancelamento
depende de uma nova proposta entregue e da autorização do participante.

Arquivos alterados nesta continuidade: `app/channels/telegram.py`,
`app/desktop/control.py`, `app/desktop/panel.py`, `scripts/alfredo_control.py`,
`tests/test_telegram.py`, `tests/test_desktop.py`, README e documentos pertinentes.
Não houve mudança de token, sistema de rede, firewall, TLS, banco/esquema,
permissões ou destinos Google, nem Git de escrita/publicação. I6 não autorizada.
I5 continua sem aceite formal; a estabilidade de ponta a ponta e a conclusão
humana do cancelamento continuam pendentes. A observação de 90 segundos é uma
verificação limitada de transporte, sem garantir estabilidade futura ou entrega
ao participante. Este registro substitui a conclusão
anterior de recuperação completa baseada somente em ATIVO.

## Histórico superado — partida pelo painel e conexão Telegram — 13/11/2026

Atualização às 14h50 de Brasília: o proprietário confirmou **ATIVO** após as
tentativas automáticas. As travas locais confirmaram painel e consumidor em
execução. A conexão foi restabelecida; isso substitui a pendência de conexão
descrita no diagnóstico abaixo. [Registro observado](evidencias/i5-desktop-active-20261113.json).
A conferência ainda não encontrou recibos Telegram novos de 13/11 nem cancelamentos
operacionais: resposta ao pedido e validação real do fluxo continuam pendentes.

Responsável: Codex, por solicitação de correção do erro `telegram_transport_error`
mostrado no controle Windows. O painel ainda iniciava somente I4; foi corrigido
para iniciar o runtime I5 quando as operações já estão configuradas e autorizadas.
Sem operações autorizadas conserva o modo anterior. Não houve alteração de unidades,
destinos, credenciais, permissões, banco/esquema ou autorização da I6 nesta correção.

A falha temporária durante `getMe`/`getWebhookInfo` encerrava o consumidor antes de
ATIVO. A partida agora mostra SEM CONEXÃO e aguarda nova tentativa usando o intervalo
existente, com parada cooperativa. Somente leituras de inicialização são repetidas;
envios e escritas incertas continuam sem repetição automática. Falhas de
autenticação/identidade continuam fatais, sem anunciar prontidão indevida.

**531 testes aprovados**, incluindo seis cenários novos de partida/autorização,
recuperação, parada e erro fatal. A evidência anterior de 525 testes foi preservada
em `evidencias/i5-tests-before-desktop-recovery-20261113.json` e transcript correspondente.
Arquivos de código alterados: `app/desktop/control.py`, `app/channels/telegram.py`,
`tests/test_desktop.py` e `tests/test_telegram.py`; documentação de controle,
implementação, README e este relatório reconciliados. Não houve operação Git de
escrita, publicação ou modificação de infraestrutura/rede.

Diagnóstico real: houve conexão TLS válida ao host oficial e uma resposta `getMe`
200 com identidade correta, intercaladas com timeouts de TCP em IPv4/IPv6. Google
e Microsoft responderam normalmente nos testes comparativos; o próprio Telegram
alternou sucesso e timeout tanto com o conector padrão quanto com o conector de
endereços concorrentes. Isso não prova uma causa específica no provedor, rede ou
equipamento. Não foram desabilitados TLS, verificação de certificado ou proteções.
O teste canônico de partida foi interrompido após falhas de transporte, antes de
qualquer polling/envio: [evidência](evidencias/i5-desktop-startup-readonly-20261113.json).

O controle remoto Windows desta sessão falhou por indisponibilidade do helper.
O proprietário fechou a janela antiga; o launcher existente abriu o painel novo
e o proprietário clicou Ligar. O resultado humano informado foi **SEM CONEXÃO**.
As travas locais confirmaram painel e consumidor em execução, mas isso não foi
tratado como prova de conexão: a última observação humana ainda não era ATIVO.
O painel permanece aberto e tenta reconectar. Não foi enviado comando de
cancelamento nem confirmação pelo agente de desenvolvimento.

Pendência após a atualização acima: comprovar a resposta ao pedido pendente.
Não afirmar serviço conectado apenas por PID,
trava ocupada ou testes automatizados. A validação real de cancelamentos,
pendências anteriores de Sheets e aceite integral da I5 continuam pendentes.
I6 permanece não autorizada. Este estado substitui o estado operacional anterior
de bot encerrado, preservando abaixo o histórico das implementações.

## Estado vigente — EXECUTE de cancelamento e herança de perfis — 13/11/2026

Responsável: Codex. Situação: **as duas correções foram implementadas e validadas
automaticamente; a I5 continua sem aceite formal integral**. A autorização explícita
recebida no anexo desta data restringe o trabalho a cancelamento e herança de
perfis. Substitui, para esta execução, a autorização anterior de sincronização:
nenhum commit, push, pull, merge, sincronização ou publicação foi executado.
Somente leituras locais Git identificaram raiz, branch e arquivos alterados.
I6 continua não autorizada. Os estados anteriores abaixo são históricos.

### Correções concluídas

- Cancelamento em linguagem natural das próprias reservas, com conferência de
  titularidade por ID Telegram, unidade e destino. O horário 18h–20h, cruzando
  reservas 16h–19h e 19h–22h, apresenta as duas opções. Escolher uma delas apenas
  prepara o resumo: outra confirmação explícita é necessária antes de cancelar.
- Proposta íntegra e com prazo; mesma pessoa/conversa; consulta da versão atual;
  PATCH condicional de estado cancelado; GET posterior antes de afirmar sucesso.
  Repetições, propostas concorrentes, estado já cancelado e falhas parciais não
  repetem efeitos. Reinício recupera operações em processamento por leitura.
  Uma nova tentativa de escrita após falha exige nova solicitação, proposta e
  autorização. Falha local depois da alteração remota conserva o diário para
  recuperação, sem repetir PATCH. Não existe chamada DELETE ou exclusão SQL.
- Histórico original, IDs, proposta e vínculos preservados. A mudança de estado
  da reserva, o diário do cancelamento e a auditoria são concluídos em uma única
  transação. Sheets recebe uma atividade de cancelamento pela outbox independente,
  preservando a criação original. A Agenda é a fonte de disponibilidade; eventos
  cancelados deixam de bloquear. Relatório distingue cancelamento efetivo de
  proposta encerrada sem execução.
- `manager` recebe a união das funções configuradas para `resident` e suas
  funções administrativas. Reserva, consulta e cancelamento próprios funcionam
  sem outra conta Telegram. A herança depende do perfil, não de nome ou ID fixo;
  também foi testada com outro ID. Não há autorização automática de cancelar
  reserva de outro participante/unidade, nem elevação de resident para manager.

O proprietário informou os vínculos: **Maria/unidade 52; Toninho/unidade 62**.
Foram aplicados no YAML privado, mantendo contas, IDs, destinos, condições,
orçamento e demais campos. A unidade fictícia anterior de Toninho permanece
como `legacy_units` exclusivamente para o mesmo ID, permitindo tratar seus
registros históricos sem reescrevê-los. Propostas validam também a unidade atual;
mudança não autorizada de vínculo bloqueia a confirmação. Acrescentadas a permissão
`reservation.cancel` e a autorização externa `calendar_cancel` para o destino já
existente. Não houve mudança de escopos OAuth ou leitura/alteração de segredos.

### Banco e configuração efetivamente atualizados

Destino: **SQLite local `data/i2.sqlite3`**, versão **4 → 5**. Migration aplicada:
`app/storage/migrations/005_reservation_cancellations.sql`, exclusivamente aditiva
(nova tabela/índice). Backup anterior em
`data/backups/before-i5-20261113T164147-e841eed7af9b48259701cb1833a604dd.sqlite3`.
O YAML anterior foi preservado em
`data/backups/i5-cancellation-manager-20261113/config-20261113T164147177155Z.yaml`.
Backups/configuração/dados privados continuam fora do Git.

A comparação de conteúdo de **todas as tabelas preexistentes** confirmou os
mesmos registros antes e depois; verificação de integridade e de chaves estrangeiras
aprovada. O diário de cancelamento operacional foi criado vazio: nenhuma reserva
Google foi alterada ou cancelada nesta entrega. Não há Supabase neste fluxo e
nenhuma migration remota foi executada. Leitores I4 e inspeção foram compatibilizados
com esquema 5, conservando os modos anteriores e sem iniciar o painel/bot.

### Validação executada e evidências

**525 testes aprovados**, zero falhas, erros ou ignorados, incluindo **26 novos**
para estas correções. Cinco configurações de inicialização, demonstrações I1/I2/I4/I5
e hashes das fontes protegidas aprovados. A evidência anterior de **499 testes**
foi preservada em `evidencias/i5-tests-before-cancellation-manager-20261113.json`
e no transcript correspondente. A regressão identificou duas incompatibilidades
(cancelamento administrativo e conferência privilegiada da síndica), corrigidas
antes da execução final. Fontes normativas originais não foram reescritas; a
autorização nova e o comportamento que substitui a restrição de perfil anterior
estão na implementação e na definição vigente do agente.

Cobertura: própria reserva; outra unidade; sobreposição ambígua; recusa/ausência
de confirmação; confirmação válida; já cancelada; mensagem repetida; propostas
duplicadas; timeout antes/depois de PATCH; falha SQLite após efeito remoto;
reinício; concorrência/ETag; disponibilidade liberada; falha independente Sheets;
auditoria/retenção; manager criando e cancelando; identidade alternativa;
mudança de unidade; compatibilidade de vínculo antigo; resident sem privilégios
administrativos; interpretação semântica; ajuda e novo pedido durante esclarecimento.

A reprodução completa usando o **YAML vigente, unidades 52/62, rede bloqueada,
Google/Telegram fictícios e SQLite temporário** também passou. Houve dois
cancelamentos simulados, seleção explícita do primeiro entre dois intervalos
cruzados, preservação da reserva não escolhida, negativa de cancelamento de outra
unidade pelo manager, cinco atividades sincronizadas no Sheets fictício e zero
duplicações após replay. Isso não é uma gravação Google real nem aceite humano.

Evidências:

- [Consolidação desta entrega](evidencias/i5-cancellation-manager-20261113.json).
- [Migration, backups e preservação de registros](evidencias/i5-cancellation-manager-local-migration-20261113.json).
- [Percurso isolado com configuração vigente](evidencias/i5-cancellation-manager-config-replay-20261113.json).
- [Suíte final](evidencias/i5-tests.json) e [transcript](evidencias/i5-unittest.txt).

### Arquivos e responsabilidades alterados

- Domínio: `app/services/reservation_cancellations.py`, `app/services/operations.py`.
- Conversa: `app/channels/reservation_cancellation.py`, `operations.py`,
  `operation_dialog.py`, `operation_messages.py`, `reservation_conversation.py`.
- Interpretação: `app/ai/operation_intent.py`.
- Configuração/autorização: `app/config/schema.py`, `app/config/operations.py`,
  `config.operations.example.yaml`, `scripts/setup_operations_i5.py`; YAML privado.
- Integrações: `app/integrations/operations.py`.
- Persistência/compatibilidade: `app/storage/sqlite.py`, `backup.py`,
  `migrations/005_reservation_cancellations.sql`, `app/services/knowledge.py`,
  `scripts/inspect_telegram_i2.py`, `scripts/knowledge_i4.py`.
- Testes: `tests/test_reservation_cancellations.py`, `tests/test_operations.py`,
  `tests/test_reservation_conversation.py`.
- Documentação: `README.md`, este relatório, `docs/implementacao-i5.md`,
  `docs/agentes/alfredo-i5.md` e as evidências acima/históricas preservadas.
  `docs/evidencias/i5-natural-dialog.json` foi identificado como evidência histórica
  substituída pela consolidação desta entrega, sem remover os resultados anteriores.

Estratégia de fechamento: ampliar os consumidores canônicos existentes e criar
um diário aditivo de cancelamento, sem substituir reservas ou criar agenda paralela.
A seleção conversa com o mesmo motor; confirmação, migração, integração, leitores,
testes e documentação foram reconciliados. Atalhos anteriores continuam compatíveis.

### Lacuna documental, limites e pendências reais

Não foi encontrada política específica de cancelamento nas fontes locais consultadas.
Não foram inventados prazo, multa, penalidade ou restrição condominial. Esta entrega
aplica titularidade/unidade, integridade, destino autorizado e confirmação. Uma
futura política aprovada deverá ser incorporada explicitamente às condições externas.
O Google pode remover posteriormente os detalhes de eventos com estado cancelado;
o histórico durável e os identificadores ficam preservados no SQLite conforme a
retenção existente, como detalhado na implementação com fontes oficiais.

**Não executados nesta entrega:** cancelamento/alteração de eventos preexistentes,
escrita Google real, nova sessão Telegram, testes humanos das duas correções,
reconciliação das pendências operacionais anteriores, sincronização GitHub ou
publicação Lovable. O bot permanece encerrado, sem alteração do modo do painel I4.
O próximo passo de validação é um ensaio integrado com reserva descartável
identificada e autorização específica para seu cancelamento, preservando os eventos
preexistentes. Nenhuma informação cadastral segue pendente após a resposta 52/62.
Na conferência final somente leitura do SQLite, permanecem **duas atividades
operacionais pendentes e oito já sincronizadas**; esses registros foram preservados.
**Implementação e validação automatizada concluídas no escopo; validação real
integrada e aceite formal integral da I5 pendentes. I6 não autorizada.**

## Estado para sincronização com GitHub/Lovable — 13/11/2026

A invocação explícita de `local-para-lovable` autoriza nesta entrega o commit,
a integração e o push do trabalho versionável, substituindo a restrição anterior
a Git para essa finalidade. Não autoriza ativação de funções ou publicação manual
do aplicativo. A regressão offline foi novamente executada: **499 testes aprovados**.

O aceite integral da I5 continua pendente. Além das pendências abaixo, foi
diagnosticada a ausência da operação de cancelamento de reservas confirmadas:
o pedido proposital de 16/11, das 18h às 20h, cruzava reservas registradas de
16h–19h e 19h–22h, mas recebeu erro genérico. O fluxo precisa identificar a
ambiguidade, verificar titularidade e regra, esclarecer o alvo e pedir autorização
antes de executar e conferir o cancelamento. Nenhuma regra de cancelamento foi
encontrada nos documentos locais consultados. Não houve implementação nem
cancelamento por essa investigação. Também não foi implementado o acúmulo das
funções de moradora e síndica na conta de Maria. A sincronização do repositório
não equivale à conclusão desses fluxos, aceite da I5 ou publicação pelo Lovable.

As contagens de Agenda/Sheets abaixo são fotografias das conferências indicadas,
não totais atuais: depois da conferência de cinco eventos, o banco registrou
outra reserva para 16/11, das 19h às 22h. Esta sincronização não consultou nem
modificou os serviços operacionais. Configuração, credenciais e dados locais
permanecem fora do Git; as evidências sanitizadas e históricas são versionáveis.

## Estado vigente — reserva humana confirmada e consulta após correção de data — 12/11/2026

Responsável: Codex. A reserva do morador para **16/11/2026, das 16h às 19h**, passou
pelo Telegram real com autorização natural “Pode confirmar”. A imagem enviada
pelo responsável mostra o evento. A conferência independente em somente leitura
validou ID, estado confirmado, propriedades privadas, início/fim, ocorrência única
e ausência de sobreposição. O banco foi aberto somente para leitura nessa conferência.
Evidência: [reserva real](evidencias/i5-reservation-human-20261112-1600-1900.json).

A conferência Google posterior encontrou **cinco eventos e oito linhas**. A nova
atividade tem uma outbox **pendente, com zero tentativas de sincronização**. A
autorização da reserva não foi reutilizada como autorização de planilha. Nenhum
evento foi cancelado/excluído, nem houve sincronização ou outra gravação externa
pelo agente de desenvolvimento nesta conferência. A reserva real foi executada
pelo bot somente após a autorização do morador.

Foi observada outra falha de conversa: “Quais os horários para reserva...” não
preservava a consulta quando o morador corrigia 2016 para 2026. O objetivo de
consulta agora fica no contexto existente, inclusive após data inválida/reinício;
a correção da data consulta a Agenda em vez de exigir os horários de uma reserva.
O caminho de coleta e o de consulta compartilham a mesma validação de dia. A
consulta usa somente a permissão de leitura; criação continua separada e exige
proposta completa e autorização. As três regressões novas reproduziram falha
antes da correção; o verificador local canônico registra o resultado final vigente.

A reprodução isolada com a configuração vigente e uma leitura da Agenda real
passou sem proposta ou gravação. Após corrigir o ano, apresentou as faixas atuais
08h–10h, 11h–16h e 19h–22h, respeitando também a nova reserva. Evidência:
[consulta corrigida](evidencias/i5-availability-year-correction-readonly.json).
Não é nova confirmação de recebimento humano nem aceite de usabilidade.

O responsável também perguntou por que Maria, sendo moradora e síndica, não pode
reservar. Diagnóstico somente leitura: o modelo atual usa um perfil por conta;
`manager` não tem `reservation.create`/`reservation.read`, e somente o morador possui
unidade de reserva cadastrada. O planejamento descreve funções separadas, sem
definir o acúmulo pela mesma conta. **Habilitação de múltiplas funções permanece
como decisão pendente**, incluindo vínculo explícito de Maria à própria unidade;
nenhum privilégio, cadastro, plano ou regra foi alterado por essa consulta.

Continuam pendentes a sincronização dessa atividade, a observação humana da
consulta corrigida, a decisão sobre acúmulo de funções e o aceite integral I5.
O estado da sessão finita e a regressão final estão em
`evidencias/i5-natural-dialog.json` e `evidencias/i5-tests.json`. Sem Git ou publicação.
Este estado substitui os estados anteriores abaixo, preservados como histórico.

## Estado vigente — falso bloqueio após conflito corrigido — 12/11/2026, 19h15

Responsável: Codex. Objetivo ativo: concluir o atendimento de reserva com coleta,
consulta e autorização conduzidas pelo Alfredo, preservando dados e fronteiras.
O responsável relatou outra falha real e exigiu qualidade de atendimento compatível
com produção. Essa exigência orienta o tratamento do incidente; não altera destinos,
regras, classificação experimental, autorizações ou aceite formal.

Diagnóstico reproduzido antes da correção: uma reserva válida quanto às condições,
mas ocupada na Agenda (16/11 das 08h às 12h), disparava a busca de alternativas em
17, 18 e 19/11. A primeira ultrapassava a validade da regra (17/11 às 00h). O erro
`document_rule_outdated` da alternativa escondia o conflito do pedido original.
Os testes anteriores usavam validade até dezembro, diferente da configuração real,
e não detectavam a falha. A mesma validade real agora integra a regressão.

O motor descarta sugestões fora do período de validade ou das condições antes
de consultar a respectiva fonte. Não ignora `document_rule_outdated`: mudança
real de revisão/hash durante a consulta e regra efetivamente vencida continuam
bloqueando, com testes próprios. O caminho de conflito foi modificado no motor
canônico e permanece integrado à disponibilidade existente, sem caminho alternativo
de execução ou afrouxamento de validação.

A coleta reconhece “ao meio-dia” e o imperativo “reserva”. Um dia sem mês/ano usa
a data já conhecida ou uma única data compatível com o período externo autorizado;
se houver duas possibilidades, pede a data completa. Uma permissão como “pode
reservar” continua respondendo à pergunta de autorização, sem iniciar outro pedido.
As mensagens rotineiras de coleta/condições não usam a condição experimental como
explicação de falha. A identificação de simulação continua no resumo da operação.

**496 testes aprovados**, zero falhas/erros/ignorados; cinco inicializações e
demonstrações I1/I2/I4/I5 aprovadas, fontes protegidas e hashes conferidos. Incluem
29 testes de coleta/disponibilidade, 25 de autorização e a regressão de revisão
real alterada durante busca de alternativa. A evidência anterior de 490 testes foi
preservada em `evidencias/i5-tests-before-conflict-repair-20261112.json`.

A reprodução reutilizável em `scripts/check_reservation_dialog_i5.py` passou com
o YAML vigente sem adaptação, banco temporário e dez leituras reais da Agenda.
Percurso: pedido “dia 16 das 14 às 20”, repetição da data, disponibilidade,
08h–12h, pergunta de recuperação, “ao meio-dia”, escolha válida 14h–18h, autorização
e repetição dessa autorização. Houve uma criação e leitura de retorno **simuladas
em memória**, nenhuma gravação Google ou mensagem Telegram real; o banco operacional
não foi aberto por essa reprodução e nenhuma LLM foi usada. Isso valida o caminho
do código e das leituras, não equivale a novo aceite humano nem a nova reserva real.
Evidência: [reprodução com configuração real](evidencias/i5-reservation-conflict-replay-20261112T221451910768Z.json).

A conferência Google final preservou quatro eventos e oito linhas. A leitura do
banco operacional confirmou o contexto de Toninho ainda em 16/11, das 08h às 12h,
sem nova reserva. Não foi reescrito nem semeado contexto para fazer o teste passar.
O consumidor antigo foi encerrado cooperativamente às 19h07 e a versão corrigida
é reaberta por sessão finita; seu estado observado fica em
`evidencias/i5-natural-dialog.json`. Painel I4, configuração, dados, PLAN, PRD e
especificação preservados. Sem Git, publicação, migração ou exclusão Google.

Próxima ação: continuar o atendimento na mesma conversa; o responsável não precisa
repetir o cadastro nem copiar comandos. Codex deve conferir o que de fato ocorrer,
sem escolher ou confirmar uma reserva pelo morador. **Usabilidade anteriormente
rejeitada, observação humana do percurso corrigido e aceite integral I5 pendentes.**
Este estado substitui os estados anteriores, preservados abaixo como histórico.

## Estado vigente — correção da reserva após rejeição real — 12/11/2026

Responsável: Codex, por continuidade autorizada pelo responsável do projeto.
O teste humano da conversa de reserva falhou: a extração assumiu um intervalo
de dia inteiro quando só havia data, perdeu respostas parciais e devolveu uma
recusa genérica. Os 462 testes anteriores não cobriam esse percurso: algumas
simulações forneciam intenções completas para mensagens que não tinham horários.
A rejeição do responsável permanece registrada; não houve aceite de usabilidade.

O caminho canônico agora coleta recurso, data e horários de forma progressiva no
contexto existente. Não preenche meia-noite por ausência de horário. Respostas
curtas conservam a data já informada, e um fim inválido não apaga o início válido.
A disponibilidade é uma consulta somente leitura à Agenda, separada da proposta
e da autorização de gravação. A explicação e o motor compartilham as validações
dos parâmetros externos; nenhuma condição experimental foi ampliada.

Em 16/11 o piloto permite horários entre 08h e 22h e no máximo quatro horas por
reserva; são condições fictícias existentes, não regras condominiais. A leitura
real encontrou faixas livres 08h–10h e 11h–22h. Esse resultado é pontual e será
consultado novamente antes de propor e confirmar. O pedido 08h–23h deve receber
a explicação dos limites e uma pergunta para escolher outro intervalo.

Validação: **490 testes locais aprovados**, sem falhas, erros ou ignorados; fontes
protegidas, cinco inicializações e demonstrações I1/I2/I4/I5 aprovadas. Incluem
24 testes de coleta/disponibilidade e 25 de autorização natural. Hashes da evidência
conferem com o código. Foram corrigidas as simulações que inventavam horários.
Passou também a reprodução das mensagens relatadas usando banco temporário,
Telegram fictício e três leituras da Agenda real: zero gravações Google, zero
mensagens Telegram reais, zero chamadas de modelo e nenhuma abertura do banco
operacional nessa reprodução. Evidências: [regressão](evidencias/i5-tests.json),
[reprodução](evidencias/i5-reservation-conversation-real-calendar-replay.json) e
[diálogo](evidencias/i5-natural-dialog.json). A etapa de 462 testes foi preservada
em `evidencias/i5-tests-before-reservation-repair-20261112.json`.

Estratégia: modificar os consumidores existentes, compartilhar a validação de
intervalo e manter comandos antigos apenas como compatibilidade. PLAN, PRD,
especificação, credenciais, regras, destinos, esquema e dados foram preservados.
Sem Git, publicação, instalação ou cancelamento/exclusão de evento Google.
O consumidor foi encerrado para a correção; a situação da sessão finita reaberta
fica registrada em `evidencias/i5-natural-dialog.json`, não constitui ativação permanente.

Próximo passo: Toninho iniciar um novo pedido em suas próprias palavras, com o
Alfredo conduzindo coleta e autorização. Depois, conferir o resultado realmente
ocorrido, sem executar ou preencher o pedido em nome do morador. **Reteste humano,
usabilidade e aceite integral continuam pendentes.** Este estado substitui os
estados operacionais anteriores abaixo, preservados como histórico.

## Retomada — autorização conduzida pelo Alfredo — 12/11/2026

O responsável pediu continuar, revogando a pausa. A mudança autorizada foi
implementada na camada de conversa existente, sem alterar o PLAN, PRD, regras,
modelo, credenciais, destinos ou esquema SQLite. Codex é desenvolvimento/validação;
Toninho e Maria passam pelo atendimento do Alfredo sem instruções externas a cada passo.

Alfredo apresenta os dados em português e faz a pergunta de autorização pertinente,
por exemplo: “Posso enviar essa resposta ao morador?”. Respostas naturais explícitas
são vinculadas à pergunta realmente enviada, ao participante, à conversa, à função,
ao hash e ao prazo. Uma permissão para ação diferente não executa a proposta.
Recusa encerra apenas a proposta ainda não executada, preservando histórico; não
cancela eventos Google. Aceite de taxa continua separado e obrigatório quando aplicável.
O modelo continua sem poder confirmar operações.

As perguntas usam a resposta nativa do Telegram. A associação ao pedido e à versão
é persistida no contexto existente somente após envio aceito. O aviso à administração
inclui o pedido e pergunta que mensagem deve responder; o texto de Maria é conteúdo,
não autorização automática. O bot mostra essa resposta e pede permissão para enviá-la.
Depois, propõe separadamente conferir as atividades na planilha. Essa autorização é
consumida uma vez, com permissão e destinos revalidados, usando a mesma outbox.
Nenhuma sincronização acontece só porque a resposta foi autorizada.

Estratégia de fechamento preventivo: modificar o caminho canônico de conversa e
coexistir com os atalhos anteriores por compatibilidade. O caminho principal não
exibe comandos/UUIDs/versões como passos. A prova de proposta entregue passou de
texto contendo comando a metadados vinculados ao recibo `sent`; o formato anterior
é aceito apenas para propostas já apresentadas. Identidade, regras, confirmação,
idempotência e integrações I1–I4 permanecem nos componentes existentes.

Passaram **462 testes locais**, incluindo **21 cenários do novo diálogo**, sem
falhas/erros/ignorados. Coberturas: ciclo completo entre as contas sem referências
fornecidas pelo desenvolvedor; envio sem autorização bloqueado; recusa; frase de
ação diferente; taxa; alteração antes de executar; múltiplos pedidos; troca de perfil;
prazo; reinício; duplicação; envio incerto; destino alterado; sincronização independente.
Evidência: [novo diálogo](evidencias/i5-natural-dialog.json). A evidência anterior de
441 testes foi preservada em `evidencias/i5-tests-before-natural-dialog-20261112.json`.

A conferência Google em somente leitura passou com conta/escopos existentes,
quatro eventos e oito linhas preservados. Uma sessão finita de uma hora atingiu
`ready` no mesmo bot e banco para o teste humano. Não houve Git, publicação, serviço
novo, migração ou gravação Google automática por esse ajuste. Implementação local
aprovada nos testes; **novo percurso real e usabilidade ainda pendentes de avaliação**.
I5 continua sem aceite integral. Esta retomada substitui a pausa e os pontos abaixo.

## Pausa solicitada — 12/11/2026, 16h59 de Brasília

Situação vigente: **pausada por solicitação explícita do responsável**. A sessão
temporária já estava encerrada; foi conferido que nenhum consumidor I5 de teste
continua ativo. Recursos, dados e evidências foram preservados, sem Git ou publicação.

O responsável reprovou a experiência conversacional: Codex, Toninho e Maria ficaram
dependentes de coordenação externa e comandos. Em seguida, autorizou expressamente
fazer o próprio Alfredo pedir autorização, sem depender de comandos. A confirmação
explícita antes de gravar continua obrigatória; o formato conversacional deverá ser
revisto. Esse novo ajuste **ainda não foi implementado**: até a pausa houve somente
leitura dos componentes e da norma de uso de LLM, sem nova mudança de código após
a regressão de 441 testes. Nenhuma solução de interface nova foi definida como decisão.

Ponto de retomada: revisar o fluxo de autorização no Telegram para que Toninho e
Maria tratem diretamente com Alfredo, com perguntas claras e contexto, deixando
comandos, IDs e versões como detalhes internos ou atalhos opcionais. Reutilizar os
componentes I5 existentes, preservar permissões, confirmação, idempotência, dados,
parametrização externa e I1–I4. Em seguida, testar o fluxo de usuário corrigido.
Antes de novos ensaios reais, conferir a janela Google vigente (até 17/11/2026 às
00h de Brasília, fim exclusivo); a revisão local de UX não depende dessa janela.

Os resultados técnicos anteriores continuam válidos como evidências dos cenários
executados, mas não representam aprovação da conversa. **I5 sem aceite e sem
declaração de validação integral.** Esta pausa e a rejeição de usabilidade substituem
os pontos de retomada e a avaliação pendente dos registros abaixo.

## Estado vigente — 12/11/2026, após conferência final

Responsável pelo registro: Codex, por execução autorizada pelo responsável do projeto.
Configuração I5 concluída com os recursos existentes, OAuth de escrita autorizado
e parâmetros externos preservados. A sessão temporária foi encerrada cooperativamente
às 16h53 de Brasília; painel Windows e modo I4 foram preservados. Não houve Git,
publicação, instalação de serviço, exclusão ou cancelamento de evento Google.

Passaram **441 testes locais**, sem falhas/erros/ignorados, com hashes do código e
fontes normativas conferidos. Nos ensaios reais selecionados passaram reserva com
confirmação/releitura, idempotência, conflito, timeout e recuperação; sincronização
independente; ajuda nas duas contas; ciclo administrativo; solicitação/resposta e
relatório da síndica. Os casos com falhas durante o ensaio foram preservados abaixo.
O cadastro administrativo e a resposta foram repetidos pelo fluxo humano normal
após as correções, sem recuperação manual nos últimos retestes.

A conferência final em somente leitura encontrou **quatro eventos** esperados na
Agenda, **oito linhas distintas** no Sheets e **zero pendências**. Duas solicitações
estão resolvidas. A sincronização final verificou dois registros, linhas 7 e 8,
preservando as seis anteriores. Orçamento local acumulado estimado: **R$ 3,129804**;
é estimativa com preços configurados, não garantia de valor da fatura. Evidências:
[regressão](evidencias/i5-tests.json), [Telegram](evidencias/i5-telegram-live.json) e
[conferência final](evidencias/i5-final-readonly-recheck-after-retests.json).

O responsável confirmou o recebimento único da última resposta na conta do morador.
Os retestes técnicos executados nesta sessão estão concluídos e aprovados, incluindo
os dois fluxos refeitos sem recuperação supervisionada. Não resta atividade pendente
na outbox nem comando de gravação a executar para esse subconjunto autorizado.

Pendências: avaliação da usabilidade pelo responsável e aceite formal aplicável.
Não se declara aceite integral do piloto nem conclusão automática de I6/G6 a
partir destes cenários selecionados. **I5 não está integralmente validada.**
Próxima ação: o responsável revisar os resultados e a experiência conversacional.
I6, apresentação e publicação não são iniciadas automaticamente por esse fechamento.
Este estado substitui contagens e pontos de retomada dos registros históricos abaixo.

## Reteste detectou omissão de data explícita — 12/11/2026

No novo cadastro humano às 16h30, o texto foi conferido por hash e correspondia
integralmente ao solicitado: vigência de 12/11/2026 às 16h até 12/11/2026 às 18h,
horário de Brasília. A extração reconheceu `guidance_create` e o início, mas deixou
o fim vazio. O bot voltou a pedir a data final. O reteste falhou; nenhuma orientação
do assunto `reteste_i5` foi ativada nessa tentativa.

Foi adicionado um parser determinístico compartilhado para intervalos brasileiros
completos e explicitamente informados: duas datas com ano, dois horários, ligação
`até` e indicação de Brasília. Essa gramática não infere ano ou data, preserva anos
antigos, rejeita datas/horas inválidas e não escolhe entre intervalos alternativos.
Os valores literais substituem os campos probabilísticos de data de uma reserva
ou orientação; autorização e confirmação permanecem separadas. Linguagem fora
dessa gramática continua exigindo interpretação e esclarecimento quando necessário.

Passaram 51 testes de conversa/datas e a regressão completa de **441 testes**, sem
falhas, erros ou testes ignorados. O intervalo da mensagem humana foi extraído sem
chamada paga ou gravação operacional. O reteste humano integral continua pendente.
A sessão foi encerrada cooperativamente durante o ajuste. Evidência:
[regressão de data explícita](evidencias/i5-explicit-interval-regression.json).
**I5 continua sem validação integral.**

Após a reabertura, a síndica enviou novo pedido completo às 16h40. O fluxo normal
gerou e entregou a proposta com os dois horários; a síndica confirmou às 16h41 e
recebeu a confirmação. A orientação `3a6a7fdf-dea4-43b7-bb18-037d915e73bb`,
assunto `reteste_i5`, ficou ativa na versão 1, para moradores, em 12/11/2026 das
16h às 18h de Brasília. Não houve replay, preenchimento manual de campos ou
recuperação supervisionada nesse reteste: mensagens reais `436624778` e
`436624779`, ambas respondidas pelo canal. O cadastro novo passou. Foi solicitado
o novo pedido do morador para retestar a resposta administrativa sem recuperação.

No reteste seguinte, o morador confirmou pelo Telegram a solicitação
`73698aeb-a9c7-5a68-9f9f-c591d334e775`, categoria `excecao`, sem urgência. Ela ficou
`forwarded`, versão 1, e um aviso foi entregue à administração. O responsável
colou a confirmação do morador e o aviso recebido pela síndica. Não houve
recuperação manual. Foi preparada a resposta à referência e versão corretas
para concluir esse fluxo pelo caminho normal do bot.

Às 16h48, a administração enviou a resposta completa e confirmou a proposta
`bfdcc836-fbef-5290-9480-97f9fe7e4d85` pelo Telegram. O bot apresentou o texto
correto sem pedir novamente a resposta. A solicitação ficou `resolved`, versão 2,
e uma notificação de resposta foi enviada ao morador. O responsável colou a proposta,
a confirmação e o recibo final da administração. Não houve recuperação manual nem
preenchimento externo de contexto. Faltam a confirmação humana de recebimento único
no morador e a sincronização das duas novas atividades para fechar esse reteste.

## Ajuste da resposta administrativa e do contexto — 12/11/2026

O pedido humano de resposta das 16h10 continha referência, versão e texto completos.
A extração colocou o texto em `content`, deixando `response` vazio. O bot perguntou
novamente qual seria a resposta. Às 16h11, a síndica respondeu `Ok`; sem contexto
estruturado desse esclarecimento, o bot repetiu a pergunta. Os hashes das duas
mensagens originais foram conferidos. A solicitação permaneceu `forwarded`, versão
1, sem resposta nem envio ao morador; não houve confirmação falsa.

O roteamento passou a normalizar o texto inequívoco de resposta, preservar contexto
mínimo de esclarecimento na tabela existente, isolar ambiente/canal/usuário/conversa
e perfil, e expirar esse contexto pelo prazo externo de confirmação. Novo pedido
independente substitui o contexto; autorização, versão e confirmação continuam
validadas localmente. O texto literal `Ok`, quando responde ao campo de resposta
pendente, preenche esse campo sem chamada ao modelo e produz somente uma proposta.

Os ensaios adicionais no modelo real passaram para resposta completa e resposta
ausente. O modelo ainda tratou `Ok` como esclarecimento mesmo com contexto; por
isso esse caso recebeu tratamento determinístico, sem repetir a chamada paga.
Quarenta testes de conversa e a regressão completa de **430 testes** passaram,
sem falhas, erros ou testes ignorados. A proposta de resposta `Ok` foi recuperada
de forma supervisionada, usando as duas mensagens humanas conferidas por hash,
e entregue à mesma conta de síndica pela fila existente, válida até 16h25.
Nenhuma chamada paga foi feita para essa recuperação. A confirmação da síndica e
o recebimento pelo morador continuam pendentes. Evidência:
[extração da resposta](evidencias/i5-response-extraction-after.json).

O responsável apontou que a conversa está pouco natural e perguntou por que exige
`confirmo`. Foi explicado que o PLAN exige confirmação explícita antes de gravar,
enquanto a expressão adotada e as perguntas repetidas são características ou falhas
da implementação. Essa observação de usabilidade permanece aberta para avaliação;
os resultados locais não representam aceite humano do fluxo.

Às 16h21, a síndica confirmou pelo Telegram a proposta de resposta `Ok`. A
solicitação passou a `resolved`, versão 2, e foi enviada uma única notificação
à conta do morador. O responsável confirmou que Toninho recebeu a resposta uma
única vez. Esse fluxo passou com recuperação supervisionada das mensagens reais,
não como reenvio integral de um pedido humano após a correção. As duas atividades
geraram registros independentes na outbox Sheets; foi solicitada sua sincronização
pela síndica. A seguir será conferido o relatório de gestão sob demanda.

Às 16h25, a síndica sincronizou as duas atividades: linhas 5 e 6, dois registros
verificados, zero pendências. Uma conferência independente em somente leitura
encontrou os quatro eventos esperados na Agenda e seis linhas distintas no Sheets,
todas correspondentes à outbox, preservando as quatro linhas anteriores. Os hashes
das fontes correspondem à regressão de 430 testes; fontes normativas preservadas.
O orçamento local acumulado estimado era R$ 3,018789, sem garantia de valor da fatura.
Evidência: [conferência real](evidencias/i5-final-readonly-recheck.json).

Foi solicitada a consulta do relatório pela síndica. Antes de declarar validação
integral, permanecem necessários o reteste completo, sem recuperação supervisionada,
dos fluxos de cadastro administrativo e resposta que falharam durante esta sessão,
a avaliação da usabilidade apontada pelo responsável e o aceite formal aplicável.

O relatório solicitado pela conta de síndica foi enviado às 16h27 e recebido pelo
responsável. Os totais correspondem ao banco: quatro reservas confirmadas, uma
proposta em conflito, uma proposta de reserva expirada sem execução, uma solicitação
resolvida, uma resposta confirmada e seis atividades sincronizadas. O item
`reservation cancelled=1` é a proposta `da955a5f-4e53-5a09-a4b0-e76d35892bf5`,
sem referência externa; não houve cancelamento de evento na Agenda. Foi solicitado
novo cadastro humano de orientação para o assunto `reteste_i5`, sem recuperação
manual, seguido do reteste humano completo de solicitação/resposta.
**I5 não está integralmente validada.**

## Correção da pergunta redundante e recuperação — 12/11/2026

Na tentativa humana das 15h27, ambas as datas estavam em 2026. O texto completo
foi conferido com o hash da mensagem Telegram original: a entrada correspondia
exatamente ao modelo corrigido solicitado. A extração preencheu corretamente os
dois limites da vigência, mas retornou `clarify` para o prazo final já preenchido.
Essa última falha era do sistema, distinta das tentativas anteriores com 2016.

O contrato agora separa a finalidade solicitada da sinalização de esclarecimento.
A conversa confere localmente os campos necessários antes de perguntar: dados
ausentes ou ambíguos continuam bloqueados; intervalo inválido continua rejeitado;
autorização e confirmação explícita permanecem obrigatórias. Resultados de um
contrato de extração anterior não são reutilizados por uma versão corrigida.

Passaram **420 testes locais** e três ensaios adicionais no mesmo modelo real:
pedido completo, prazo final ausente e fim em 2016 anterior ao início em 2026.
Para evitar outro cadastro humano, o pedido já enviado foi reprocessado de forma
supervisionada após a conferência do hash. A proposta recuperada foi entregue à
mesma conta da síndica pela fila Telegram existente, com nova referência técnica
e vínculo com a mensagem original; a resposta anterior foi preservada. Não houve
ativação nem confirmação automática. Foi solicitada apenas a conferência e a
confirmação do novo resumo, válido até 15h41. Evidência:
[decisão e recuperação](evidencias/i5-guidance-decision-after.json).

A proposta das 15h36 venceu sem confirmação. Após o responsável avisar que estava
com a conversa Telegram aberta, uma nova proposta do mesmo pedido verificado foi
entregue às 15h54, válida até 15h59, sem repetir a chamada ao modelo e sem ativar
a orientação. Foi solicitado somente conferir a última mensagem do bot e enviar
a confirmação no próprio Telegram. Esse é o ponto de retomada vigente.

Às 15h55, a síndica confirmou a proposta renovada pelo Telegram. O banco registra
a orientação `84827e89-72fa-493e-a29f-25f19d427841`, versão 1, ativa para moradores,
com vigência em 12/11/2026 das 14h às 18h de Brasília. A confirmação foi enviada
pelo canal e o responsável confirmou seu recebimento. Esse cadastro passou com
recuperação supervisionada da proposta; não foi um novo cadastro humano completo
após a última correção. Não houve broadcast da orientação. O ponto de retomada
passa a ser a consulta dessa orientação pela conta de morador, seguida dos demais
ensaios administrativos pendentes.

Às 15h56, a conta de morador consultou o assunto `teste_i5` em linguagem natural.
A extração reconheceu `guidance_read`, e a resposta com o conteúdo vigente da
versão 1 foi enviada pela API Telegram. O responsável colou o pedido do morador,
mas ainda não confirmou visualmente o recebimento da resposta. Foi solicitado
o ensaio de correção pela síndica, informando referência e versão atual 1,
preservando a vigência e exigindo nova confirmação explícita.

A síndica enviou o pedido de correção e confirmou pelo Telegram às 16h00. A
versão 2 ficou ativa, a versão 1 foi preservada, e a resposta de confirmação foi
enviada e recebida pelo responsável. Não houve recuperação manual nessa correção.
A sessão anterior foi encerrada cooperativamente às 16h01; uma nova sessão finita
atingiu `ready` no mesmo bot e banco. O teste seguinte solicitado é o cancelamento
somente dessa orientação fictícia, pela síndica, com referência, versão atual 2
e confirmação explícita. Reservas e dados Google não participam desse cancelamento.

Às 16h04, o cancelamento foi confirmado pela conta da síndica. A versão 3 registra
`cancelled`, preservando as versões 1 e 2. A confirmação foi enviada pelo Telegram,
e o responsável informou que confirmou a ação. Uma consulta sintética do perfil
morador pelo serviço existente, contra o banco real em somente leitura, retornou
zero orientações vigentes para `teste_i5`; não se trata de uma nova consulta humana
Telegram. Foi solicitado o teste de solicitação fictícia do morador, categoria
`excecao`, sem urgência, com confirmação e verificação do aviso à síndica.

Às 16h07, o morador confirmou a solicitação fictícia
`a8184129-dbb9-5c71-9c65-182c688cd366`. Ela foi registrada na versão 1, categoria
`excecao`, sem urgência, atribuída a `manager`, com estado `forwarded`. A confirmação
foi enviada ao morador e um aviso foi enviado à síndica pela fila existente.
O responsável informou que realizou o passo. O teste seguinte solicitado é a
resposta da síndica à referência e versão 1, com confirmação explícita e
verificação, pelo responsável, de recebimento único na conta do morador.

Este registro substitui a contagem e o ponto de retomada abaixo. O ciclo
administrativo humano e demais critérios obrigatórios permanecem pendentes.
**I5 não está integralmente validada.** Não houve Git, publicação ou exclusão.

## Ajuste após ensaio administrativo — 12/11/2026

O primeiro pedido humano de orientação foi rejeitado sem criar ou ativar uma
orientação. A extração retornou esclarecimento, com datas em `start/end`, sem
vigência administrativa; o ano final extraído foi 2016. Dois ensaios controlados
com o modelo real também demonstraram a mistura entre os campos de reserva e de
vigência. O contrato e o prompt agora distinguem esses campos, identificam o campo
que exige esclarecimento e proíbem corrigir automaticamente anos explícitos.
O motor rejeita vigência final anterior ou igual ao início antes de escrever.

Passaram cinco ensaios no mesmo modelo real: dois cadastros completos, prazo final
ausente, cancelamento sem nova vigência e fim em 2016 anterior ao início em 2026.
Esses ensaios verificaram somente extração, sem criar propostas ou efeitos
administrativos. Evidências: [antes](evidencias/i5-guidance-extraction-before.json)
e [depois](evidencias/i5-guidance-extraction-after.json).

A regressão vigente passou com **415 testes**, sem falhas, erros ou testes
ignorados. Comandos I5 incompletos recebem orientação I5, preservando os comandos
legados. A sessão anterior foi encerrada cooperativamente e uma sessão finita
foi aberta às 15h14 de Brasília, no mesmo bot e banco, por até trinta minutos.
O reteste humano da síndica foi solicitado. Memória administrativa pelo Telegram,
solicitações/respostas e aceite formal continuam pendentes; **I5 não está
integralmente validada**. Modelo, permissões e destinos permanecem os mesmos.
Nenhuma operação Git, publicação ou exclusão foi executada.

No reteste humano às 15h20, o bot pediu o prazo final. O registro da extração
contém início em 12/11/2026 às 14h e fim em 12/11/2016 às 18h, sem orientação
criada. O responsável forneceu o texto exato: ele contém explicitamente o ano
2016 no fim da vigência, nas duas tentativas. Portanto, a pergunta específica
após o ajuste preservou corretamente a entrada e impediu ativação com intervalo
inválido. Foi solicitado novo cadastro com início e fim em 2026. O fluxo humano
com datas válidas continua pendente; os ensaios controlados não o substituem.

Este estado substitui as contagens e pendências históricas abaixo quando houver
divergência. Reserva humana e sincronização Sheets já passaram, conforme retomada.

## Retomada autorizada — 12/11/2026

O responsável solicitou continuar, revogando a pausa anterior. Conta, três escopos,
janela experimental e exclusividade local do banco foram conferidos. A leitura
real encontrou os três eventos e as três linhas dos ensaios anteriores; nenhum
evento foi recriado. OAuth permaneceu válido, sem novo consentimento humano.

A sessão finita Telegram I5 foi reaberta às 14h47 de Brasília, com duração máxima
de trinta minutos, no mesmo bot e banco. O consumidor atingiu `ready`. O responsável
recebeu o pedido completo para repetir a reserva fictícia de 16/11, das 10h às 11h,
e confirmá-la diretamente no bot. O morador confirmou a proposta, recebeu a
confirmação e o evento foi relido na Agenda: reserva de 16/11, das 10h às 11h,
referência `b6d53ab8-2395-5668-9465-ca42fe5abe8d`, validada. O registro Sheets
ficou pendente de sincronização independente, conforme projeto. A síndica
executou a sincronização pelo Telegram: um registro verificado, zero pendências,
linha 4 confirmada pelo motor e pelo responsável com imagem da planilha.
Memória administrativa, solicitações/respostas e
aceite formal permanecem pendentes. Os resultados anteriores e os testes
locais foram preservados; nenhuma operação Git ou publicação foi executada.

Esta retomada substitui a pausa abaixo. Estado instantâneo da sessão em
`data/i5-telegram-test-runtime.json`; a sessão encerra cooperativamente ao fim
do prazo ou mediante solicitação de parada.

## Histórico — pausa solicitada pelo responsável — 12/11/2026

O responsável interrompeu os ensaios para retornar depois. A sessão temporária
Telegram I5 foi encerrada cooperativamente, com banco fechado e estado `closed`.
OAuth e configuração I5 permanecem cadastrados; eventos, planilha, dados anteriores,
evidências e correções foram preservados. Nenhuma reserva do pedido humano de
16/11 às 10h foi confirmada. A proposta anterior expirou e não será reexecutada.

Ponto de retomada: conferir validade da janela Google e das condições fictícias
(atualmente até 17/11/2026, início desse dia exclusivo do intervalo), conferir
OAuth, iniciar a sessão finita I5 e repetir o pedido do morador com confirmação
explícita. Em seguida, validar os fluxos administrativos ainda pendentes e obter
aceite formal. Ajuda nas duas contas e cenários Google selecionados já passaram;
412 testes locais passaram. **I5 não está integralmente validada.**

Este registro de pausa foi substituído pela retomada acima.

## Estado vigente em 12/11/2026 — Google validado em cenários selecionados

O novo consentimento OAuth concluiu com conta e três escopos conferidos. A
configuração candidata foi promovida, reutilizando os mesmos destinos e a unidade
fictícia existente; as credenciais Telegram/OpenAI e os demais campos anteriores
foram preservados. O prazo ampliado resolveu o retorno local recusado da tentativa
anterior. Nenhuma URL/código de autorização foi armazenado nas evidências.

Passaram nas APIs reais a criação e releitura de reserva, o replay da mesma
confirmação, o bloqueio do segundo pedido no mesmo intervalo, a consulta posterior
e a recuperação da escrita após timeout. Uma interrupção local foi injetada depois
de um POST efetivo; outro processo retomou a intenção e confirmou o mesmo evento,
sem novo POST. Há exatamente três eventos fictícios esperados na janela do piloto.

Também passaram a escrita RAW e a conferência no Sheets, o timeout injetado após
PUT e a reconciliação por leitura sem segunda escrita. Foram sincronizadas três
linhas de atividades. A indisponibilidade Sheets foi injetada antes da escrita,
enquanto a reserva existente continuou comprovada na Agenda. Esses ensaios misturam
entradas sintéticas do motor e APIs Google reais; não são mensagens humanas Telegram.

A adaptação ao contrato real do Sheets passou a reconhecer células vazias finais
omitidas pelo `ValueRange`, sem aceitar alteração de valores ou coluna extra. Dois
testes de regressão cobrem a releitura e o timeout nesse formato.

O ensaio semântico real já aprovado não foi repetido nem cobrado novamente.
A regressão vigente passou com **412 testes**, zero falhas/erros/ignorados,
quatro demonstrações e cinco inicializações aprovadas. Fontes normativas preservadas.

Foi iniciada uma sessão temporária de testes Telegram I5 pelo mesmo `app.main`,
bot e banco, com encerramento cooperativo e duração máxima de trinta minutos.
Identidade do bot e ausência de webhook foram conferidas; o consumidor atingiu
`ready`. A ajuda I5 foi enviada pelas APIs reais aos perfis de morador e síndica,
e o responsável confirmou recebimento nas duas contas. Evidência:
[Telegram real](evidencias/i5-telegram-live.json). Os fluxos I5 de reserva,
solicitações/memória administrativa pelo Telegram e o aceite formal ainda estão pendentes.
O painel Windows conserva seu modo I4 e não foi substituído.

No primeiro ensaio de reserva pelo morador, a proposta foi entregue, mas foi
recebido apenas o comando de confirmação sem referência. A operação foi rejeitada
sem criação de reserva. A orientação genérica e os horários UTC do resumo foram
corrigidos: o piloto apresenta o horário de Brasília e destaca a confirmação
natural quando houver uma única proposta válida. O comando completo por ID
continua disponível, inclusive com espaços não separáveis vindos da cópia Telegram.
A proposta anterior expirou durante o ajuste; o reteste foi solicitado sem
reexecutar automaticamente a operação. Os 22 testes de conversa e a regressão
completa passaram. Ainda não há confirmação de reserva humana nesse ensaio.

Evidências: [autorização e consentimento](evidencias/i5-live-authorizations.json),
[Google/modelo e preservação](evidencias/i5-live-validation.json) e
[regressão local](evidencias/i5-tests.json).
**I5 continua sem validação integral. Não houve Git, publicação ou exclusão.**

As seções seguintes preservam as etapas anteriores; o estado vigente acima
substitui as afirmações de consentimento/escrita ainda pendentes dessas etapas.

## Continuidade de 12/11/2026 — consentimento de escrita pendente

Diagnóstico posterior do retorno local: o responsável informou conexão recusada
na página de retorno depois de consentir no Google. O receptor da primeira
tentativa já havia encerrado após 180 segundos, portanto aquele retorno não podia
ser recebido. A URL contém código temporário e não foi reproduzida nem utilizada
em nova tentativa. O prazo I5 passou a ser configurável, com padrão de 600 segundos
e limite máximo de 1800; o padrão da I3 permanece 180. A nova tentativa usa novo
estado/PKCE/porta e preserva os cadastros até conferir conta e escopos. Referência:
[retorno OAuth local do Google](https://developers.google.com/identity/protocols/oauth2/native-app#redirect-uri_loopback).

O responsável autorizou concluir a configuração, reutilizar os recursos existentes
e executar os testes reais previstos, sem Git ou publicação. Foram verificados nas
APIs reais a conta, a Agenda cadastrada (vazia na janela autorizada) e o intervalo
já autorizado da planilha (vazio). Evidência: [preflight real](evidencias/i5-live-preflight.json).

A configuração candidata reutiliza os mesmos IDs, intervalo e unidade fictícia
do morador. As condições de teste ficam explicitamente classificadas como
`simulated`, sem alegar que são regras reais do condomínio. O cadastro ativo não
foi substituído. Os cadastros foram copiados para backups privados antes da tentativa
de consentimento; segredos nunca foram exibidos.

O primeiro consentimento OAuth encerrou com `google_oauth_consent_failed`, sem
emitir/persistir o token de escrita ou promover a configuração. Os dois escopos
anteriores e os parâmetros I1–I4 foram preservados. O helper agora registra somente
etapa e classe segura de falha, sem URLs/códigos/tokens. A ação humana pendente é
concluir o consentimento Google no navegador; o responsável já foi consultado
sobre a abertura da janela/erro. Evidência: [preparação e autorização](evidencias/i5-live-authorizations.json).

O ensaio de extração semântica no modelo real `gpt-4o-2024-08-06` passou para
recurso, data relativa e horários. Não houve File Search, nova indexação, evento
ou célula criados por esse ensaio. O livro de orçamento estimado passou de
R$ 2,580846 para R$ 2,592221, acréscimo estimado de R$ 0,011375 com os preços já
configurados. Isso não representa valor garantido da fatura.

O banco existente recebeu a migração aditiva I5 para versão 4, depois de backup
privado. Todas as linhas preexistentes foram conferidas por hashes e preservadas.
Evidência: [validação real parcial](evidencias/i5-live-validation.json).

A regressão desta continuidade passou com **406 testes**, zero falhas, erros ou
testes ignorados. Também passaram as quatro demonstrações e as cinco inicializações
locais. O resultado de 402 testes da entrega anterior foi preservado em
`evidencias/i5-tests-before-live-20261112.json` e no transcript correspondente.
Não foi executado `git diff --check` nem qualquer outro comando Git nesta continuidade.

Permanecem pendentes as gravações/releituras na Agenda e no Sheets, os ensaios reais
de reconciliação/retomada, o fluxo I5 nas duas contas Telegram, a confirmação humana
e o aceite formal. Os scripts de ensaio retomam identificadores persistidos e não
executam exclusões. Falhas injetadas serão diferenciadas de indisponibilidade real.
**I5 não está integralmente validada. Nenhuma operação Git ou publicação ocorreu.**

O texto seguinte preserva a entrega local de 11/11/2026. Suas afirmações de ausência
de chamadas reais/migração descrevem aquela entrega, não a continuidade acima.

Atualização: 11/11/2026. Responsável: Codex.
Objetivo: implementar a fase I5 conforme o plano aprovado, preservando parametrização
externa, componentes existentes e operação exclusivamente experimental.

## Resultado e autoridade

A implementação local foi autorizada expressamente pelo responsável nesta sessão.
Foram implementadas reservas com confirmação/reconciliação, registros Sheets por
outbox, solicitações, exceções, memória administrativa pelo Telegram e relatórios
sob demanda. A extração semântica reutiliza Responses e o orçamento/modelo I4;
permissões e efeitos continuam determinísticos no Python.

PRD v1.2.0, especificação v0.1.8, plano v0.1.1 e documentos de origem foram preservados.
Configuração particular, segredos, banco ativo, processo do bot e atalho Windows
não foram alterados. Não houve instalação de dependências, commit, push, chamada
OpenAI paga ou gravação Google. O Git foi consultado com exceção de propriedade
aplicada somente ao comando, sem alterar configuração global. A branch permaneceu `main`.

## Validação

Resultado final: **402 testes aprovados, incluindo 64 testes I5; zero falhas,
erros ou testes ignorados**. As quatro demonstrações I1/I2/I4/I5 e as cinco
inicializações de exemplos passaram. `git diff --check` passou. Os hashes dos
documentos normativos foram preservados; os hashes de código/testes conferem com
as evidências da execução final.

O verificador canônico é [verify_i5.py](../scripts/verify_i5.py). O resultado completo,
IDs dos testes, versões, hashes de fontes, preservação normativa e saídas das
demonstrações ficam em [i5-tests.json](evidencias/i5-tests.json) e
[i5-unittest.txt](evidencias/i5-unittest.txt).

A cobertura I5 inclui intenção commitada antes do POST; confirmação, taxa informativa
e perfil; indisponibilidade e alternativas consultadas; concorrência local;
replay; timeout após efeito; reconciliação sem segunda escrita; recuperação após
reinício; divergência/remoção de evento; fonte documental atual/desatualizada;
mudança de destino após proposta; outbox com falha, timeout e dado externo;
texto literal RAW; encaminhamento/resposta versionada e aviso único ao destinatário;
relatório restrito; orçamento e resposta de modelo inválida; confirmação de
orientações, público, correção, cancelamento, expiração na fila e ausência de broadcast.

A demonstração finita produz uma criação de evento e uma escrita Sheets nos
transportes fictícios, apesar do replay da confirmação. Inicializações dos exemplos
e regressão I1–I4 são verificadas em bancos temporários, sem credenciais reais.
Os ensaios locais não são evidência de APIs reais ou aceite humano.

## Pendências reais

- Confirmar exclusividade e autorização específica da Agenda/Sheets experimentais,
  região A:J dedicada, janela, unidade simulada e regras verificadas ou cenários
  explicitamente fictícios. O exemplo I5 mantém autorizações de escrita desabilitadas.
- Cadastrar os parâmetros I5 no YAML particular sem substituir os dados existentes,
  reautorizar OAuth de escrita no navegador e optar explicitamente pelo runtime I5.
- Validar qualidade da extração/composição no modelo configurado e operações reais
  nos destinos autorizados, com evidências e custo efetivamente medido.
- Obter aceite formal da I5 e autorização G5 antes da I6/ensaios integrados.

O bot e o painel existentes continuam na I4. Esta entrega conclui a implementação
local; não declara ativação real, aceite do piloto I5, aprovação T01–T18/MO01–MO10
em serviço real ou autorização da I6.

Procedimentos, limites e recuperação: [implementação I5](implementacao-i5.md).
Comportamento do agente: [Alfredo I5](agentes/alfredo-i5.md).
