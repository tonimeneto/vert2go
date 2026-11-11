# Relat?rio de entrega ? Fase I1

> Relatório histórico preservado. A entrega vigente e suas pendências estão em
> [relatorio-i2.md](relatorio-i2.md), de 08/11/2026. Evidências I1 não foram regravadas.

Data: 05/11/2026. Projeto: Vert2Go. Agente do produto: Alfredo.
Respons?vel pela execu??o: Codex. Raiz autorizada:
D:/MeusArquivos/Fs/Projetos/Vert2Go.

## A. Resultado da fase

**I1 CONCLU?DA no escopo local autorizado.**

A inicializa??o local passou, o esquema SQLite est? ?ntegro, a demonstra??o
estruturada passou e a su?te final aprovou **102 de 102 testes**, sem falhas,
erros, testes ignorados ou bloqueios locais. MO01?MO10 foram exercitados no n?cleo
determin?stico. A conclus?o n?o representa integra??o, implanta??o nem aceite
dos cen?rios externos T01?T18.

As evid?ncias est?o em [i1-tests.json](evidencias/i1-tests.json),
[i1-unittest.txt](evidencias/i1-unittest.txt),
[i1-demo.json](evidencias/i1-demo.json),
[i1-local-checks.json](evidencias/i1-local-checks.json) e
[i1-preservation.json](evidencias/i1-preservation.json).

## B. Arquivos

Todos os caminhos abaixo s?o relativos ao workspace.

Criados ? configura??o e prote??o:

- .gitignore
- requirements.txt
- config.example.yaml
- secrets.example.yaml

Criados ? motor:

- app/__init__.py
- app/main.py
- app/config/__init__.py
- app/config/schema.py
- app/core/__init__.py
- app/core/contracts.py
- app/core/policy.py
- app/core/orchestrator.py
- app/ai/__init__.py
- app/ai/client.py
- app/services/__init__.py
- app/services/operational_memory.py
- app/storage/__init__.py
- app/storage/sqlite.py
- app/storage/migrations/001_initial.sql

Criados ? testes e demonstra??o:

- tests/__init__.py
- tests/support.py
- tests/test_configuration.py
- tests/test_security.py
- tests/test_storage.py
- tests/test_memory.py
- tests/test_budget_retention.py
- examples/__init__.py
- examples/i1_demo.py
- scripts/verify_i1.py

Criados ? documenta??o e evid?ncias:

- docs/implementacao-i1.md
- docs/relatorio-i1.md
- docs/evidencias/i1-tests.json
- docs/evidencias/i1-unittest.txt
- docs/evidencias/i1-demo.json
- docs/evidencias/i1-local-checks.json
- docs/evidencias/i1-preservation.json

Modificado: README.md, para refletir o estado implementado e fornecer um ?nico
bloco completo de prepara??o, testes, inicializa??o, demonstra??o e verifica??o.

Gerados localmente e ignorados: .venv/, caches __pycache__/, banco novo
data/i1-development.sqlite3 e arquivo de trava associado. SQLite pode criar
arquivos WAL/SHM durante uso. Bancos das su?tes e da demonstra??o s?o fict?cios,
tempor?rios e isolados; a limpeza dos tempor?rios n?o envolve dados preexistentes.
N?o foram criados config.yaml, secrets.yaml nem .env reais.

Preservados integralmente, com SHA-256 id?ntico ao invent?rio inicial:

- AGENTS.md
- docs/Vert2Go-PRD-v1.2.0.md
- docs/Alfredo-Especificacao-v018.md
- docs/Vert2Go-Plano-Implementacao-Codex-v0.1.1.md
- docs/4S_Regulamento_interno.md
- docs/4S_convencao_condominio.md

A conven??o permanece uma minuta modernizada, sem promo??o a documento registrado.
Nenhuma regra desses documentos foi convertida em l?gica condominial na I1.
Nenhum arquivo de outro projeto ou padr?o compartilhado foi alterado.

## C. Arquitetura

A inicializa??o manual e finita em app/main.py mant?m uma trava do sistema
operacional por banco, valida YAML/esquema e recupera estados antes de encerrar.

O esquema de configura??o ? estrito, com cadastro fechado e permiss?es imut?veis.
Policy separa identifica??o de autoriza??o para preservar inclusive o perfil
real de usu?rios conhecidos em auditorias de a??es negadas.

Orchestrator coordena entradas estruturadas, limites, deduplica??o, transa??es,
contexto m?nimo e auditoria. OperationalMemory implementa o ciclo administrativo
de orienta??o. Store concentra persist?ncia e reten??o. LocalBudget calcula
estimativas e bloqueio l?gico, sem cliente OpenAI.

Simplifica??es: biblioteca padr?o, duas depend?ncias, nove tabelas, um banco por
inst?ncia, correspond?ncia exata de assunto e nenhum servi?o/adapter vazio.
Sem ORM, Redis, fila externa, ?ndice documental local, framework multiagente,
SaaS, painel, servidor ou processo persistente.

Decis?es t?cnicas e contratos completos:
[implementacao-i1.md](implementacao-i1.md).

## D. SQLite

Migra??o criada: app/storage/migrations/001_initial.sql.
Aplicada somente no banco novo data/i1-development.sqlite3 e em bancos novos
tempor?rios de testes/demonstra??o. A reabertura n?o reaplica nem transforma o
esquema; valida application_id, user_version e compara??o de esquema.

Tabelas: conversation_state, processed_messages, requests_state, operation_log,
sync_outbox, document_sync_metadata, usage_ledger, operational_guidance e
operational_guidance_revisions.

Verifica??es finais: **9 tabelas, 7 ?ndices expl?citos**, al?m de chaves/?ndices
autom?ticos; user_version 1; integrity_check retornou ok e foreign_key_check
retornou zero problemas. Chaves estrangeiras ativas nas conex?es do motor,
BEGIN IMMEDIATE, WAL, synchronous FULL e unicidades por opera??o/vers?o.
O banco de desenvolvimento de inicializa??o continua sem dados de usu?rios.

Arquivos preexistentes desconhecidos s?o rejeitados, inclusive banco vazio.
H? teste que comprova preserva??o byte a byte de um banco estranho com dados.
N?o houve migra??o destrutiva, exclus?o de dados preexistentes ou adapta??o
silenciosa de esquema divergente.

## E. Mem?ria Operacional Administrativa

Implementadas: proposta e confirma??o de cria??o, corre??o e cancelamento,
consulta autorizada por assunto, hist?rico, expira??o l?gica e auditoria.

draft fica em conversation_state. Somente confirma??o expl?cita cria a orienta??o
autoritativa. active com in?cio futuro ainda n?o aparece como vigente.
expired/cancelled n?o aparecem nas consultas. Revis?es anteriores s?o preservadas.

A confirma??o exige ator/chat correto, operation_id, hash da proposta, prazo e
vers?o esperada quando aplic?vel. H? revalida??o de permiss?o na confirma??o e
imediatamente antes da escrita. O ?sim? estruturado sem opera??o s? vale para
uma proposta pendente inequ?voca no escopo. O exemplo adota 300 segundos de prazo.

Vig?ncia usa America/Sao_Paulo e limites inclusivo/exclusivo. Datas relativas
partem do instante original, com hor?rios expl?citos. T?rmino indefinido ou
amb?guo n?o ? ativado. Orienta??o expirada/cancelada n?o ? reativada por corre??o.

Corre??o cria outra vers?o at?mica; concorr?ncia sobre a mesma vers?o rejeita a
segunda confirma??o obsoleta. Cancelamento confirmado cria revis?o rastre?vel e
retira a orienta??o de consultas imediatamente.

Consultas retornam somente vers?o atual confirmada, do ambiente, assunto, p?blico
e intervalo corretos, com atribui??o ? administra??o. Conte?do ? dado n?o
confi?vel. Conflito documental informado gera resultado seguro sem arbitrar
preval?ncia. Nenhum conflito real foi pesquisado/validado nesta fase.

Sem NLP, Telegram, OpenAI, busca documental, broadcast ou notifica??es.
O exemplo de manuten??o ? estritamente fict?cio e exercitado com entrada estruturada.

## F. Testes e evid?ncias

Comandos executados: cria??o do ambiente por python -m venv .venv; instala??o
pelo Python da .venv com pip install --disable-pip-version-check -r requirements.txt;
testes por -m unittest tests.test_configuration tests.test_memory -v,
-m unittest discover -v e scripts/verify_i1.py; inicializa??o por -m app.main
com config.example.yaml e data/i1-development.sqlite3; compileall -q sobre app,
tests, examples e scripts. Os comandos completos copi?veis est?o no README.

Resultado final: **102 executados, 102 aprovados, 0 falhas, 0 erros, 0 ignorados,
0 bloqueados locais**. A execu??o final registrada pelo runner unittest durou
12,546 segundos nesta m?quina; varia??es de dura??o s?o esperadas.
A demonstra??o retornou c?digo de sa?da 0. Inicializa??o retornou
local_ready schema=001 simulation=true e local_closed. Compila??o terminou sem erro.

Cobertura exercitada:

- YAML v?lido/inv?lido, tipos, campos ausentes, duplicados, aliases, tags inseguras,
  segredos opcionais e disponibilidade do fuso.
- Resident/manager, desconhecidos, tentativa de eleva??o por texto/payload,
  revoga??o de permiss?es, grupos, usu?rio/chat/ambiente e conte?do restrito.
- Esquema, reabertura, FK, rollback e bancos desconhecidos preservados.
- MO01?MO10 e complementos: prazo, hash alterado, ?sim? amb?guo, in?cio futuro,
  vers?o obsoleta, reten??o longa, cancelamento, hist?rico e replay de consultas.
- Duas corre??es concorrentes com conex?es distintas; s? uma grava a vers?o esperada.
- Encerramento real de subprocessos com os._exit antes e depois do commit;
  integridade na retomada e aus?ncia de segundo efeito.
- Perda de resposta ap?s commit, estados incertos sem replay, trava contra outro
  processo e libera??o autom?tica da trava ap?s falha.
- Or?amento, medi??o ausente, pre?os/c?mbio fict?cios e virada de m?s no fuso local.
- Elegibilidade de reten??o, incidentes, aus?ncia de dele??o e sanitiza??o de logs.

Falhas intermedi?rias encontradas e corrigidas: escopo ausente causava AttributeError;
a??o com tipo inv?lido falhava na auditoria; verifica??o de esquema ap?s a abertura
comparava sqlite.Row com tupla. Os testes que revelaram esses problemas passaram
depois das corre??es. A auditoria de a??o negada tamb?m foi ajustada para guardar
o perfil de usu?rio conhecido, sem atribu?-lo a unknown.

Os testes do n?cleo bloqueiam socket.connect/connect_ex, create_connection e
urlopen. Os subprocessos executam apenas c?digo local inspecionado. A inspe??o
AST de app n?o encontrou importa??es de SDKs ou m?dulos de rede.
N?o houve pacote Telegram/Google/OpenAI instalado nem chamadas dessas APIs.

T01?T18 com depend?ncias externas: **n?o executados**, por pertencerem ?s fases
posteriores sem autoriza??o. N?o s?o contados como testes locais aprovados,
ignorados ou bloqueados. A aceita??o de I1 n?o afirma aprova??o desses ensaios.

## G. Depend?ncias

Ambiente efetivo: Python **3.13.7**, SQLite **3.50.4** da biblioteca padr?o,
pip 25.2 no ambiente virtual, PyYAML **6.0.3** e tzdata **2025.2**.

PyYAML ? necess?rio para YAML seguro e tipado. tzdata fornece a base IANA ausente
no Python Windows inspecionado, permitindo ZoneInfo America/Sao_Paulo sem
substituir o fuso por offset fixo. Ambas est?o fixadas em requirements.txt.

O primeiro pip foi bloqueado pelo sandbox de rede. A repeti??o com eleva??o
restrita ? instala??o autorizada concluiu a instala??o na .venv; n?o houve
rejei??o do mecanismo de aprova??o nem instala??o global. O ?nico acesso externo
da execu??o foi a obten??o das depend?ncias no ?ndice Python, expressamente
autorizada pelo prompt. Nenhuma API operacional do produto foi acessada.

## H. Seguran?a e limites observados

.gitignore protege configura??es particulares, segredos, OAuth, bancos e auxiliares,
backups, logs, ambientes e caches. Exemplos n?o cont?m segredos reais.
A inicializa??o n?o abre arquivo real de segredos. SQLite e YAML locais n?o s?o
criptografados; permiss?es do Windows continuam sob administra??o do propriet?rio.

Identidade e autoriza??o s?o determin?sticas, com nega??o por padr?o. Estado,
mensagens e opera??es s?o isolados por ambiente/canal/usu?rio/chat.
Idempot?ncia, hash da proposta e vers?o esperada impedem efeitos duplicados ou
alterados por replay. Erros n?o exibem par?metros SQL ou conte?do administrativo.

O c?digo n?o executa conte?do de orienta??o, n?o modifica configura??o pelo texto,
n?o acessa segredos e n?o dispara ferramentas arbitr?rias. A IA n?o decide permiss?es.
Na I1, a identidade local ? uma fixture confi?vel, sem alega??o de autentica??o real
Telegram. C?digo Python arbitr?rio com acesso ao processo/banco fica fora dessa fronteira.

Nenhum acesso Google, Calendar, Sheets, OAuth, Telegram, OpenAI, Supabase ou
upload documental. Nenhum deploy/publica??o/Lovable. Nenhum acesso a sistemas
oficiais do condom?nio ou altera??o em Emp2Go/DevTOLAS/Fs/Comum.

A inspe??o Git confirmou aus?ncia de reposit?rio local. N?o existe branch a relatar.
N?o foram executados init, clone, fetch, pull, push, commit, merge, rebase, reset,
checkout ou sincroniza??o GitHub.

## I. Documenta??o e decis?es persistidas

README.md cont?m o estado real, requisitos, instala??o, testes, inicializa??o,
exemplo, c?digos de log e limites. docs/implementacao-i1.md cont?m arquitetura,
contratos, esquema, transi??es, idempot?ncia, reten??o, or?amento e recupera??o.
Este relat?rio e as cinco evid?ncias fornecem o invent?rio e os resultados.

Foram mantidas as pol?ticas de 30 dias para contexto/deduplica??o e 90 dias para
auditoria/fechados, com preserva??o de opera??es abertas, vig?ncia longa e incidentes.
S? h? consultas de elegibilidade: nenhuma limpeza autom?tica ou exclus?o foi feita.

N?o houve substitui??o de responsabilidade existente, integra??o anterior ou
transfer?ncia de opera??o entre projetos. A nova implementa??o ocupa apenas o
escopo I1 antes inexistente. N?o foi necess?rio criar estado tempor?rio paralelo
ou alterar AGENTS.md.

## J. Pr?xima fase e pend?ncias

**I2 n?o iniciada.** Exige aprova??o expl?cita G1 e autoriza??o de uso do bot de
teste. O propriet?rio precisar? cadastrar token localmente e fornecer IDs dos dois
participantes de teste pelo mecanismo autorizado, sem expor segredos na conversa.

Trabalho futuro autorizado separadamente: adaptar configura??o/segredos ao Telegram,
implementar somente texto e chats privados, preservar timestamps/identidade,
deduplicar updates, manter inst?ncia ?nica durante polling e testar primeiro com
fixtures. Envio/recebimento real requer autoriza??o espec?fica.

Google/OAuth, modelos OpenAI, pre?os vigentes, transfer?ncia de documentos,
Vector Store, File Search e escritas em Calendar/Sheets dependem dos seus port?es.
O or?amento local n?o garante teto de fatura. Relev?ncia sem?ntica e detec??o real
de conflitos documentais n?o existem na I1. Reten??o destrutiva e corre??o de estados
incertos exigem procedimento e autoriza??o pr?prios.

N?o h? pend?ncia obrigat?ria local da I1 nem servi?o em execu??o. Sincroniza??o
GitHub e publica??o permanecem responsabilidade exclusiva do propriet?rio.
