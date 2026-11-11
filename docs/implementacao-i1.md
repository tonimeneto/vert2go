# Implementa??o I1 ? motor local Alfredo

> Registro histórico da entrega de 05/11/2026. Desde 08/11/2026, configuração,
> inicialização e esquema vigentes são descritos em [implementacao-i2.md](implementacao-i2.md).
> A I2 local foi implementada; o teste real do bot continua pendente de autorização
> específica. As declarações abaixo sobre ausência de I2/esquema 1 referem-se à I1.

Atualiza??o: 05/11/2026. Escopo vigente: somente I1, executada por autoriza??o
expressa do propriet?rio. Conhecimento t?cnico permanente do Vert2Go.
A implementa??o n?o altera as fontes normativas nem representa implanta??o oficial.

## Refer?ncias e decis?es

Prevalecem PRD v1.2.0, especifica??o t?cnica v0.1.8 (arquivo
Alfredo-Especificacao-v018.md) e plano Codex v0.1.1, nessa ordem. A solicita??o
consolidada de execu??o resolve os pontos P0: nove tabelas, rascunhos em
conversation_state, inst?ncia ?nica Windows e aus?ncia de integra??es na I1.
N?o foi encontrado relat?rio P0 separado no workspace inicial.

Foram consultados AGENTS.md, README.md, as tr?s fontes normativas, o cat?logo
Fs/Comum/README.md e as normas DevTOLAS de uso de LLM, documenta??o, estado vigente
e conte?do para copiar e colar. Os padr?es de interface do cat?logo n?o se aplicam
ao motor sem interface. Nenhuma fonte externa de refer?ncia foi modificada.

Decis?es de implementa??o:

- Python 3.13.7, biblioteca padr?o, PyYAML 6.0.3 e tzdata 2025.2; sem ORM.
- Entrada estruturada local, sem interpreta??o probabil?stica ou cliente de rede.
- Identificadores de opera??o, orienta??o e idempot?ncia s?o UUIDs can?nicos.
- Hor?rios de persist?ncia s?o ISO 8601 UTC de precis?o fixa; apresenta??o deve usar
  America/Sao_Paulo. Intervalos t?m in?cio inclusivo e fim exclusivo.
- Propostas s?o imut?veis. Altera??o exige outra opera??o e outra confirma??o.
- Corre??o e cancelamento geram revis?es; n?o apagam nem alteram vers?es anteriores.
- Revis?o preserva status no instante do commit. O status atual fica na identidade
  da orienta??o; o hist?rico tamb?m informa current_status e current_version.
- N?o h? arquivo redundante de estado tempor?rio: c?digo, testes, este documento
  e o relat?rio de entrega permitem retomar o trabalho.

## Componentes e fronteira de confian?a

app/main.py valida configura??o, adquire trava de arquivo mantida pelo sistema
operacional, abre SQLite, recupera estados, aplica expira??o l?gica e fecha tudo.
? execu??o finita, sem servidor ou processo em segundo plano.

app/config/schema.py aceita apenas o esquema I1. Rejeita campos desconhecidos,
duplicados, aliases, tags inseguras, arquivos excessivos, tipos incorretos,
ambientes sem simula??o, canais n?o locais e escalada de permiss?es. Limita YAML
a 64 KiB. Configura??o e permiss?es ficam imut?veis ap?s carregamento.
validate_secrets ? um validador opcional de campos nulos para I1; n?o imprime
conte?do e n?o ? chamado automaticamente sobre um arquivo real de segredos.

app/core/contracts.py define Scope, Message, Result, c?digos de erro, estados,
serializa??o can?nica e fun??es de tempo. relative_day_interval exige hor?rios
expl?citos e calcula a data a partir de received_at original, sem presumir dura??o.

app/core/policy.py identifica por ambiente, canal local, ID num?rico e chat privado
permitido. O perfil vem exclusivamente da configura??o. Permiss?es s?o negadas por
padr?o, inclusive para opera??es n?o cadastradas. Uma configura??o pode reduzir
capacidades, mas n?o conceder capacidades de manager a resident.

app/core/orchestrator.py ? o ponto de entrada operacional. Valida, autoriza,
deduplica, abre a transa??o, despacha a opera??o e registra resultado/auditoria.
Imp?e limites de entrada e de mensagens distintas processadas por minuto.

app/services/operational_memory.py implementa propostas, confirma??o, consulta,
hist?rico e expira??o. S? deve ser chamado pelo orquestrador em transa??o.

app/storage/sqlite.py administra conex?es, transa??es, esquema, auditoria,
recupera??o e consultas de elegibilidade para reten??o.

app/ai/client.py cont?m apenas LocalBudget, um livro local estimado para medi??es
fict?cias. N?o importa SDK nem implementa chamadas OpenAI.

Scope ? uma identidade fornecida por um adaptador confi?vel, simulada nesta fase.
Um texto ou payload n?o pode defini-la nem definir role. A futura autenticidade
do remetente Telegram dever? ser estabelecida pelo adaptador I2, separadamente.
C?digo Python local e acesso direto ao SQLite s?o fronteiras administrativas
confi?veis; este n?cleo n?o isola c?digo arbitr?rio executado pelo dono do processo.

## Contratos de entrada

Orchestrator.handle recebe Message, nome de a??o e dicion?rio de payload.
Message cont?m Scope, message_id, received_at com fuso, correlation_id, text e
update_id opcional. Scope cont?m environment_id, channel, channel_user_id,
chat_id e chat_type. A I1 aceita channel local e chat_type private.

A??es existentes:

- propose_create: operation_id, idempotency_key, topic, content, audience,
  effective_from, effective_until e timezone.
- propose_correct: mesmos campos de cria??o, mais guidance_id e expected_version.
- propose_cancel: operation_id, idempotency_key, guidance_id e expected_version.
- confirm: explicit igual ao booleano true; operation_id e proposal_hash para
  confirma??o identificada. Sem operation_id, exige exatamente uma proposta
  pendente, n?o vencida e vinculada ao ator/chat.
- find_guidance: topic estruturado. N?o aceita usu?rio-alvo nem p?blico arbitr?rio.
- guidance_history: guidance_id; somente manager.
- set_context: context com unit_reference e/ou request_reference fict?cios.
- get_context: dicion?rio vazio; retorna somente o contexto do pr?prio escopo.

topic ? uma chave exata de 1?64 caracteres, com letras min?sculas ASCII, n?meros,
h?fen e sublinhado. audience admite residents ou managers. effective_from e
effective_until s?o timestamps expl?citos com fuso; timezone deve ser
America/Sao_Paulo. T?rmino ausente, amb?guo ou anterior/igual ao in?cio exige
esclarecimento. N?o existe vig?ncia tempor?ria indefinida neste piloto.

Propostas devolvem resumo com conte?do, p?blico, intervalo, fuso, opera??o,
orienta??o, vers?o esperada, ator/chat (scope), instante original, prazo e hash.
O programa que as apresenta deve exibir esse resumo antes da confirma??o.
explicit representa a confirma??o do usu?rio j? capturada pelo chamador confi?vel;
o n?cleo I1 n?o interpreta o texto ?sim?.

Result cont?m status, code e data. Rejei??es usam c?digos fixos, por exemplo
unauthorized, clarification_required, proposal_changed, stale_version e
confirmation_expired. Nenhuma exce??o bruta ou SQL com par?metros ? exibido.
Uma confirma??o repetida devolve o resultado hist?rico daquela opera??o; para
saber vig?ncia atual ? obrigat?rio executar find_guidance.

## SQLite e migra??o

001_initial.sql ? a ?nica migra??o. PRAGMA application_id identifica o aplicativo
e PRAGMA user_version identifica a vers?o 1. Na abertura, o esquema completo de
tabelas e ?ndices ? comparado com a migra??o executada em mem?ria. O arquivo SQL
tamb?m ? identificado por SHA-256 nas evid?ncias.

Um arquivo preexistente desconhecido, inclusive arquivo vazio, ? rejeitado sem
migra??o. Somente bancos novos recebem o esquema inicial. Reabrir um banco I1
valida a identidade, o esquema, integrity_check e foreign_key_check. N?o h?
adapta??o silenciosa de esquemas divergentes.

As nove tabelas s?o:

- conversation_state: chave ambiente/canal/usu?rio/chat/state_key; contexto m?nimo
  e propostas separadas por opera??o, com prazo e metadados.
- processed_messages: chaves de mensagem e update, hash da entrada, refer?ncia ?
  opera??o e resultado dur?vel para deduplica??o.
- requests_state: opera??o, propriet?rio, idempot?ncia, vers?o esperada, hash da
  proposta, estado, resultado, prazo e eventual reten??o por incidente.
- operation_log: auditoria sem conte?do de mensagens; ator pseud?nimo, perfil,
  opera??o, entidade, vers?o, transi??o, resultado, correla??o e confirma??o.
- sync_outbox: contratos m?nimos de estado/refer?ncia para sincroniza??o futura.
  A I1 n?o enfileira nem entrega mensagens, n?o conecta servi?os.
- document_sync_metadata: identificadores, revis?o/hash e classifica??o; nenhum
  texto integral, ?ndice local ou pesquisa documental.
- usage_ledger: per?odo, consumo fict?cio, custo decimal, premissas e idempot?ncia.
- operational_guidance: identidade, vers?o atual, estado e retirada de vig?ncia.
- operational_guidance_revisions: conte?do, autoria, p?blico, per?odo, confirma??o,
  hash, opera??o e vers?o substitu?da.

S?o usados ?ndices de estado, reten??o de mensagens, assunto/p?blico/vig?ncia,
entidade de auditoria, per?odo de consumo e estado da outbox, al?m dos ?ndices
autom?ticos das chaves e unicidades. Chaves estrangeiras permanecem ativas.
As refer?ncias c?clicas entre identidade e revis?o s?o diferidas at? o commit.
As vers?es e opera??es s?o ?nicas por ambiente.

Transa??es usam BEGIN IMMEDIATE, foreign_keys ON, journal_mode WAL,
synchronous FULL e busy_timeout de 5 segundos. Todas as altera??es administrativas,
a revis?o, a vers?o atual, a auditoria de sucesso e a mensagem deduplicada
participam da mesma transa??o. Erro antes do commit provoca rollback integral.
A proposta/solicita??o j? foi persistida em uma transa??o anterior.

requests_state n?o armazena disponibilidade de sal?o. Nenhuma tabela funciona
como agenda paralela. Tr?s tabelas de integra??o futura existem por exig?ncia do
esquema aprovado; n?o h? adaptadores vazios de servi?os externos.

## Estados, confirma??o e idempot?ncia

A proposta nasce como draft em conversation_state; n?o existe orienta??o
autoritativa at? o commit confirmado. A solicita??o registra received e
awaiting_confirmation. Na confirma??o, committing e confirmed s?o auditados na
mesma transa??o do efeito local.

Uma orienta??o confirmada fica active, mesmo se o in?cio estiver no futuro.
A consulta exige effective_from menor/igual ao instante e effective_until maior.
Ao terminar o intervalo, a exclus?o de consultas ? imediata mesmo sem job de
expira??o. startup tamb?m materializa expired e audita essa transi??o.
Cancelamento confirmado gera nova revis?o cancelled e retira o conte?do
imediatamente. Corre??o de orienta??o expirada/cancelada ? rejeitada; uma nova
orienta??o exige outra cria??o confirmada.

O prazo de confirma??o do exemplo ? 300 segundos, configur?vel at? 3600.
? par?metro conservador de opera??o do piloto, n?o regra condominial. O prazo
come?a em received_at original, n?o no rein?cio. Igualdade com o vencimento j?
rejeita a confirma??o.

O hash can?nico cobre campos, opera??o, ator/chat, vers?o, instante original e
prazo. A confirma??o identificada exige o hash apresentado. O n?cleo recalcula
o hash do rascunho e confere contra requests_state, revalida o perfil e repete a
autoriza??o imediatamente antes de gravar.

A corre??o/cancelamento exige expected_version. BEGIN IMMEDIATE serializa commits;
a atualiza??o compara novamente a vers?o atual. Duas propostas sobre vers?o 1
n?o podem sobrescrever silenciosamente uma ? outra: a segunda confirma??o recebe
stale_version depois que a primeira criar a vers?o 2.

Mensagem ou update repetido com entrada alterada recebe message_identity_conflict.
Mesmo operation_id ou chave de idempot?ncia com proposta diferente ? rejeitado.
Texto igual com IDs de opera??o distintos n?o ? fundido silenciosamente.
Replays de consultas reexecutam filtros atuais em vez de devolver conte?do ativo
em cache que j? tenha sido cancelado ou expirado.

## Consulta, p?blico, conflito e conte?do n?o confi?vel

Somente vers?es atuais, confirmadas, ativas, vigentes, do ambiente e assunto
corretos s?o consultadas. Resident recebe apenas audience residents. Manager pode
consultar conte?do restrito e hist?rico. O resultado contextual identifica a fonte
como ?orienta??o comunicada pela administra??o?, sem atribu?-la ao regulamento.

Conte?do administrativo n?o ? interpretado como Python, permiss?o, configura??o,
prompt de sistema ou chamada de ferramenta. N?o existe execu??o de texto nem
pipeline de instru??es de modelo na I1. Nenhum broadcast, notifica??o autom?tica,
mural ou envio espont?neo ? implementado.

O campo opcional document_conflict admite not_checked ou reported. Uma cria??o
com conflito informado ? rejeitada para esclarecimento; uma consulta com conflito
informado retorna status conflict e conjunto vazio, sem arbitrar preval?ncia.
document_check ? sempre not_checked_in_i1. Esse contrato recebe sinais estruturados
do chamador: n?o detecta contradi??es sem?nticas e n?o prova compatibilidade com
documentos reais. N?o h? busca documental nem leitura das regras 4S pelo c?digo.

## Auditoria e reten??o

A auditoria inclui hor?rio UTC, identidade pseudonimizada, perfil, a??o,
entidade/vers?o quando aplic?veis, estados, resultado, correlation_id derivado,
refer?ncia de confirma??o e erro seguro. Negativas tamb?m s?o auditadas ap?s
rollback; falha de grava??o gera audit_unavailable no log. N?o s?o guardados
corpos integrais de mensagens na auditoria. Propostas e orienta??es cont?m apenas
o conte?do administrativo necess?rio.

retention_candidates ? somente leitura, sem DELETE ou limpeza autom?tica:

- Contexto: 30 dias; preservar enquanto houver opera??o aberta ou incidente.
- Deduplica??o: 30 dias; preservar opera??es abertas e incidentes relacionados.
- Auditoria: 90 dias; preservar v?nculos necess?rios a opera??es abertas,
  orienta??es ativas e incidentes n?o resolvidos.
- Solicita??es: abertas indefinidamente; fechadas por pelo menos 90 dias, com
  depend?ncias de revis?es e outbox preservadas.
- Orienta??es: enquanto vigentes, inclusive al?m de 30 dias; eleg?veis apenas
  ap?s t?rmino/cancelamento e mais de 90 dias, sem opera??o aberta ou incidente.

incident_open exige justificativa incident_reason. N?o h? coleta autom?tica de
incidentes. As consultas preservam registros relacionados marcados no SQLite.
A lista de orienta??es representa o grupo identidade/revis?es, n?o uma instru??o
para remover uma linha isolada. Chaves estrangeiras e refer?ncias exigir?o ordem
de limpeza planejada; opera??es ainda referenciadas por revis?es n?o s?o candidatas.

Limpeza futura exigir? autoriza??o espec?fica, revis?o da lista de elegibilidade,
backup privado consistente, valida??o de incidentes e depend?ncias, execu??o
transacional e compara??o de integridade/contagens antes e depois. A I1 n?o
implementa nem agenda esse procedimento destrutivo.

## Or?amento estimado local

LocalBudget registra apenas uso fict?cio, de forma idempotente por usage_id.
O m?s ? calculado em America/Sao_Paulo. Custos usam Decimal, pre?os USD de
refer?ncia para tokens, valores fict?cios expl?citos de busca/armazenamento e
c?mbio configurado. Premissas e data s?o persistidas com cada registro.
N?o se consultam pre?os, cota??es ou APIs.

O exemplo usa R$ 30 por m?s, alerta l?gico em R$ 24 e bloqueio de novas chamadas
hipot?ticas em R$ 30. assess tamb?m pode verificar custo projetado da pr?xima
chamada. Medi??o ausente ? registrada como desconhecida e bloqueia conservadoramente
o per?odo; a I1 n?o implementa reconcilia??o de faturas nem envio do alerta.
A virada de m?s abre outro per?odo. Consumo j? incorrido pode exceder o or?amento
e ? registrado, sem descarte. A trava local n?o garante teto absoluto da fatura.

## Inicializa??o, parada, backup e recupera??o

Os comandos completos est?o no README. app.main executa valida??o/recupera??o e
encerra; examples.i1_demo executa um fluxo fict?cio finito. N?o h? polling para
parar nem servi?o instalado. Ctrl+C encerra a inicializa??o com fechamento e
libera??o da trava; n?o delete arquivos de banco ou lock como tentativa de reparo.

A trava ? por caminho absoluto do banco. Sua propriedade ? mantida pelo sistema
operacional e liberada mesmo se o processo morrer. O arquivo .lock pode permanecer;
sua exist?ncia n?o significa inst?ncia ativa. Todo futuro hospedeiro duradouro do
orquestrador deve manter instance_lock por toda a vida do processo.

Na retomada, committing com revis?o confirmada correspondente tem o resultado
reconstitu?do; sem prova do efeito vira needs_reconciliation, sem replay.
Propostas vencidas s?o marcadas cancelled. Propostas ainda v?lidas permanecem
pendentes; nenhuma ? confirmada pelo rein?cio. Falhas durante uma transa??o local
s?o desfeitas pelo SQLite. Ap?s commit, a mensagem/resultado dur?veis evitam repetir
o efeito se a resposta tiver sido perdida.

needs_reconciliation bloqueia nova confirma??o. Na I1 n?o h? rotina autom?tica
para concluir estados incertos sem evid?ncia. Deve-se investigar o banco e a
opera??o em ambiente protegido antes de autorizar eventual corre??o.
received n?o ? um estado dur?vel esperado de uma proposta completa: received e
awaiting_confirmation s?o gravados na mesma transa??o.

Para backup, pare o processo e copie o conjunto consistente do banco, ou use a
API sqlite3.Connection.backup em procedimento local autorizado. N?o copie apenas
o arquivo principal com conex?o ativa e WAL pendente. Preserve o original e
valide a restaura??o em outro caminho privado com integrity_check,
foreign_key_check, esquema e contagens. A I1 n?o altera ACLs, criptografa arquivos
nem cria pol?tica autom?tica de backups.

N?o h? pr?-requisito de internet para executar o motor com depend?ncias instaladas.
Queda de servi?os externos n?o produz falsa confirma??o, pois eles n?o s?o usados.
Nenhuma cobertura de indisponibilidade de APIs reais foi exercitada nesta fase.

## Valida??o e continuidade para I2

A su?te unittest usa rel?gio controlado, diret?rios/bancos tempor?rios e dados
fict?cios. Bloqueia sockets e urlopen nos testes do n?cleo e exercita subprocessos
locais para falhas abruptas e travas. Valida MO01?MO10, permiss?es, isolamento,
confirma??es, concorr?ncia, rollback, rein?cio, or?amento, reten??o e logs.
Resultados, nomes dos testes, comandos e vers?es est?o em docs/evidencias/.
scripts/verify_i1.py reproduz a su?te, a demonstra??o e a confer?ncia SHA-256
dos arquivos iniciais; n?o acessa APIs nem sincroniza Git.

I2 exige autoriza??o expressa G1 e autoriza??o espec?fica para usar um bot de
teste e depois enviar/receber mensagens reais. O propriet?rio dever? cadastrar
localmente o token e os IDs reais dos dois participantes, sem envi?-los ao chat.
Ser? necess?rio adaptar o esquema de configura??o para o canal Telegram, construir
o adaptador de texto/chats privados, preservar identidades e timestamps originais,
deduplicar updates e manter a trava durante long polling. O validador de segredos
dever? evoluir apenas nessa fase autorizada.

Google/OAuth, OpenAI, c?pia/indexa??o de documentos e escritas em recursos
experimentais permanecem sujeitos aos seus pr?prios port?es. T01?T18 externos
n?o foram executados. Nenhuma etapa I2?I6 foi iniciada.
