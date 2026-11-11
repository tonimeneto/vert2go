# Relatório de entrega I2

Atualização: 09/11/2026. Responsável: Codex. Projeto e única raiz de escrita:
D:/MeusArquivos/Fs/Projetos/Vert2Go.

## Resultado e vigência

Implementação local I2 concluída, com testes e documentação. A solicitação de
configuração e validação real de 08/11/2026 concedeu autorização para testar o
bot experimental e enviar/receber mensagens dentro da I2, substituindo a pendência
de autorização da primeira entrega. O usuário concluiu o cadastro de token/bot e
dos dois participantes. Ajuda e contexto foram recebidos, autorizados e respondidos
pela API real, com recebimento confirmado pelo usuário nas duas contas. A demora
da conexão IPv6 foi identificada e corrigida, mantendo o host/TLS e os dados.
Decisão vigente do aceite definitivo: **I2 APROVADA**, detalhada na seção de aceite
de segurança e em [i2-acceptance.json](evidencias/i2-acceptance.json).
O isolamento real com referências distintas foi confirmado pelo usuário; os
limites das modalidades de prova são explicitados na decisão, sem critério I2 pendente.
As seções de correção de YAML/token registram o histórico anterior ao cadastro real.

Canal de texto privado via long polling oficial implementado: cadastro fechado,
ID numérico, política Python, limites de taxa/tamanho, contexto isolado,
deduplicação de update/mensagem, offset durável, retomada e entrega conservadora.
Ensaio administrativo falso reutiliza proposta/confirmação/revisões I1; não há
ativação administrativa no transporte real ou broadcast.

## Alterações

- Criados adaptador em app/channels/, migração 002_telegram.sql, exemplo Telegram
  fictício, demonstração i2_demo.py, testes test_telegram.py e verificador verify_i2.py.
- Ampliados configuração, política, auditoria de falhas, armazenamento/retencão,
  inicialização manual e teste de esquema vigente para onze tabelas/versão 2.
- verify_i1.py encaminha ao verificador vigente sem regravar evidências I1.
- README reescrito em UTF-8, operação I2 documentada e documentos operacionais I1
  marcados explicitamente como históricos. PRD, especificação, plano, AGENTS.md
  e documentos de condomínio preservados, com hashes verificados.
- Na primeira entrega não foram abertos configurações/segredos/bancos particulares.
  Na configuração atual, foram criados config.yaml e secrets.yaml particulares,
  ausentes no inventário inicial, com token e IDs nulos. Não foram inventadas
  credenciais. A descrição anterior de ACL como acesso do "usuário atual" era
  insuficiente: tratava-se da identidade isolada do agente, excluindo o usuário
  Windows do terminal. Em 09/11 esse usuário foi incluído, mantendo agente/SYSTEM.
  Conteúdo dos arquivos e data/i1-development.sqlite3 preservados.
- Acrescentados setup_telegram_i2.py, check_telegram_i2.py e 13 testes do cadastro
  e diagnóstico. Entrada do token oculta e recusada se o terminal não puder ocultar;
  descoberta pela API oficial sem offset/ack, confirmação explícita dos IDs por
  perfil, recusa de conversão I1/troca de bot e evidências sem segredos/IDs.
- Corrigida a declaração fixa do verificador offline, que ainda exigia autorização
  real independentemente da sessão: agora aponta para a evidência própria do
  Telegram. README e operação I2 refletem a autorização atual e as pendências reais.
- Nenhuma dependência acrescentada/instalada ou serviço instalado. A primeira
  entrega não abriu bancos operacionais; a validação posterior usou o banco I2
  e consultas/cópias somente leitura. A correção de formato no aceite é descrita abaixo.

## Correção do bloqueio local — 09/11/2026

**Causa raiz concreta:** config.yaml e secrets.yaml já eram YAML UTF-8 válido.
As ACLs criadas em 08/11 permitiam apenas a identidade isolada do Codex e SYSTEM;
o usuário Windows do terminal não conseguia ler nenhum dos dois arquivos.
Reprodução no contexto do usuário: PermissionError/errno 13 em ambos; read_yaml
capturava OSError genericamente e devolvia invalid_yaml. Portanto não havia campo
YAML inválido: a falha acontecia no acesso ao arquivo, antes da análise sintática.

O cadastro também tentava abrir arquivos existentes com modo exclusivo de criação,
desnecessário para preservá-los e sujeito a PermissionError no Windows. Esse erro
caía no local_setup_error genérico. A preparação agora verifica a existência antes
da abertura exclusiva e informa erros de arquivo com código e nome seguros.

**Correções:** inclusão do SID do usuário Windows autorizado nas ACLs dos dois
arquivos, sem remover regras ou acrescentar grupos amplos; leitor distingue
permissões, arquivo ausente, leitura, codificação, tamanho e sintaxe; diagnóstico
não mostra conteúdo/erro bruto. Criados validadores de cadastro que aceitam null
somente nas identidades/token ainda não informados. O carregador operacional
continua estrito. O cadastro valida os demais campos antes do prompt/rede e o
verificador distingue cadastro incompleto de YAML inválido.

Arquivos de código corrigidos: app/config/schema.py, scripts/setup_telegram_i2.py,
scripts/check_telegram_i2.py e tests/test_telegram_setup.py. Modelos YAML já eram
válidos e foram preservados. config.yaml e secrets.yaml tiveram somente ACLs
corrigidas: conteúdo byte a byte preservado, sem cadastrar ou substituir valores.
README, operação I2, relatório e evidências foram atualizados. Núcleo, adaptador,
migrações, dados operacionais e fases posteriores permaneceram preservados.

## Validações e evidências

[i2-tests.json](evidencias/i2-tests.json) registra os resultados por nome de teste,
versões, hashes de código, fontes protegidas e verificações locais.
[i2-unittest.txt](evidencias/i2-unittest.txt) registra a execução completa.
Comando reproduzível no README: scripts/verify_i2.py com o Python da .venv.

- **205 testes aprovados**, zero falhas, erros ou testes ignorados: 102 da fundação
  I1, 43 do canal/inspeção, oito da conexão TCP, 37 de cadastro/diagnóstico,
  dez de aceite de segurança e cinco da sonda de replay.
  A correção anterior acrescentou 15 testes (sete de logs/inspeção e oito de conexão).
  A primeira entrega tinha 138 testes; cadastro ampliou para 151, acesso para 160,
  token/descoberta para 175, diagnóstico/latência para 190 e aceite atual para 205.
- Cadastro/diagnóstico: preservação de arquivos válidos byte a byte, campos nulos
  na preparação, dois IDs distintos, rejeição de troca de bot/conversão I1,
  interrupção segura sem terminal adequado, descoberta sem confirmar fila e
  recusa de webhook ativo sem excluir webhook ou expor sua URL. Esses testes usam
  credenciais fictícias somente em temporários e transporte mockado, sem rede.
- [Permissões dos arquivos particulares](evidencias/i2-private-files-acl.json):
  herança desabilitada e três regras, apenas usuário Windows autorizado, identidade
  isolada do agente e SYSTEM. A revisão de 09/11 substitui a evidência de duas
  regras de 08/11 que não contemplava o usuário do terminal. Sem nome, SID ou token.
- [Correção YAML](evidencias/i2-yaml-fix.json): reprodução no contexto do usuário,
  conteúdo dos dois arquivos preservado, leitura posterior aprovada e cadastro
  em terminal real chegando ao prompt oculto, cancelado sem token/rede. Nove testes
  novos cobrem erro de acesso distinto de sintaxe, arquivo ausente, preservação
  de arquivo protegido existente, rascunho válido com runtime bloqueado, parâmetros
  inseguros recusados antes do prompt, chegada ao prompt, token preexistente
  preservado byte a byte e diagnóstico sem conteúdo privado.
- [Correção do fluxo do token](evidencias/i2-token-flow-fix.json): 15 regressões
  adicionais para entrada oculta, diagnóstico de esquema/arquivo/provedor,
  persistência antes da descoberta, retomada sem solicitar token novamente,
  descoberta de /start, bot esperado, IDs candidatos, webhook ativo e evidência
  sem segredo. Todos os transportes desses testes são falsos, nunca integração real.
- Migração de banco I1 conhecido preserva contexto; SQL inválido desfaz a migração;
  esquema adulterado é recusado antes de migração.
- Configuração inválida, grupo, desconhecido, troca de identidade, mídia, replay,
  isolamento, revogação, confirmação expirada e limites exercitados sem rede.
- Falha entre commit do núcleo e recibo não repete efeito; reinício em sending
  gera uncertain; timeout não provoca reenvio; 429 suspende envios pelo prazo
  persistido; interrupção manual fecha banco e libera trava.
- Inicialização finita com os dois exemplos: saída zero, esquema 2,
  integrity_check=ok e nenhuma violação de chave estrangeira em bancos temporários.
- [Demonstração I2](evidencias/i2-demo.json): cinco recibos, offset 6, uma revisão
  administrativa após confirmação duplicada, cinco respostas exclusivamente ao
  transporte falso, integridade ok e nenhuma rede.
- [Regressão da demonstração I1](evidencias/i2-regression-demo.json): execução local
  preservada; evidência nova separada do registro histórico.

Cobertura local relacionada a T01/T02/T09/T12/T18 exercita identidade, negação,
duplicação e reinício com fixtures. A memória e suas permissões continuam cobertas
pela suíte I1 e pelos novos ensaios de criação/correção/cancelamento no adaptador.
Isso não equivale a passar T01–T18 ou MO01–MO10 em integração real. Cenários de
Google/OpenAI/reservas/relatórios permanecem not_run nas fases correspondentes.

## Correção posterior — token oculto e descoberta dos participantes

O usuário informou invalid_telegram_secrets imediatamente após o prompt oculto.
Nesta inspeção, config.yaml e secrets.yaml passaram na leitura YAML e esquema de
cadastro; o token permaneceu null e bot/IDs ausentes. Assim, a falha indicada pelo
fluxo anterior fica localizada na checagem de formato da entrada em memória,
antes de getMe. Não é evidência de token rejeitado pelo Telegram, falha de leitura
do arquivo ou erro estrutural no YAML. A entrada histórica não foi armazenada;
não é possível afirmar qual caractere/forma causou a rejeição, nem atribuir culpa
à colagem. Nenhum valor do token foi solicitado ao chat ou reconstruído por hipótese.

O usuário esclareceu depois que colou no terminal integrado do VSCode e pressionou
Enter porque nada aparecia. Ausência de eco é o comportamento normal de getpass,
não evidência de entrada vazia. O log enviado ainda mostra o prompt/erro antigos.
Foi acrescentada orientação explícita de que não aparecem caracteres/asteriscos;
o bloco operacional agora usa agrupamento PowerShell para análise completa antes
da abertura do processo interativo. Não se afirma que linhas enfileiradas foram
a causa histórica: o conteúdo recebido pelo prompt permanece desconhecido.

**Defeitos de implementação confirmados:** código genérico compartilhado entre
erros de entrada e de arquivo; contrato do token duplicado no script/validador;
token válido só era salvo depois de todos os IDs; descoberta exigia marcadores
particulares e ignorava /start; não havia verificação do username solicitado.

**Correções:** contrato único em validate_telegram_token, com erros fixos por
origem/etapa e até três tentativas ocultas. Somente espaços externos da entrada
nova são normalizados; caracteres internos, rótulo/URL/aspas, faixa de ID e
regras de credencial continuam estritos. Tokens existentes não são normalizados
nem substituídos. A evidência não contém tamanho, prefixo, sufixo ou valor do token.

Com --discover e autorização, getMe verifica ID e username AlfredoVert2GoBot antes
de qualquer persistência de token novo. O assistente salva token/bot, preservando
ACLs e demais configurações, antes de consultar webhook/participantes. --token-only
permite encerrar essa etapa separadamente. Falhas posteriores preservam o progresso
validado. Não remove webhook, descarta fila, confirma updates ou envia mensagens.

A descoberta considera remetentes humanos de mensagens privadas textuais pendentes,
inclusive /start das contas que já falaram com @AlfredoVert2GoBot. Mantém a chamada
getUpdates sem offset/allowed_updates, limite 100. Exibe IDs apenas no terminal
local; confirmação manual dos perfis é obrigatória e IDs não descobertos/duplicados
são recusados. Marcadores são somente dicas opcionais. Conversas passadas fora da
fila pendente não podem ser recuperadas como histórico; enviar texto novo se
necessário, sem apagar estado remoto ou banco.

O verificador pode consultar getMe/getWebhookInfo após token/bot cadastrados mesmo
com participantes pendentes, mantendo saída 1 e cadastro incompleto enquanto os
dois IDs faltarem. O assistente registra docs/evidencias/i2-enrollment.json a cada
execução com etapa e resultado seguros; o arquivo será gerado na próxima execução
real. Sua segurança foi testada em diretórios temporários.

Código e testes alterados: app/config/schema.py, scripts/setup_telegram_i2.py,
scripts/check_telegram_i2.py e tests/test_telegram_setup.py. README, operação I2,
relatório e evidências atualizados. Nenhum token/configuração particular foi
modificado nesta correção; modelos, ACLs, núcleo, canal, dados e dependências
preservados. Nenhuma chamada real ao bot pôde ser executada, pois o token ainda
está ausente. Esse limite permanece explícito, mesmo havendo autorização para as
consultas necessárias.

## Diagnóstico real — ausência de consumidor e demora de conexão

Na inspeção inicial, nenhum processo Python estava ativo no contexto Windows do
usuário, e data/i2.sqlite3 e sua trava não existiam. Configuração/token e os dois
cadastros estavam válidos. Logo, não havia consumidor persistente nesse momento;
não foi possível reconstruir historicamente por que a invocação relatada não o
deixou ativo. O valor live_acceptance=blocked do verificador não impede a execução.

getMe confirmou o bot esperado, getWebhookInfo confirmou webhook vazio e cinco
updates pendentes. A primeira execução supervisionada criou apenas o banco I2
dedicado, adquiriu trava e processou mensagens das duas contas. Foram gravados
nove recibos e nove respostas aceitas pela API antes do reteste de latência,
incluindo ajuda/contexto de ambos os perfis. Não havia envio incerto ou falho.
O usuário confirmou recebimento nas duas contas e depois relatou a demora.

**Causa concreta da demora:** DNS com IPv6 antes de IPv4; a conexão IPv6 ficou em
timeout no teste de 3.005 ms, enquanto IPv4 conectou em 235 ms. O discador original
do HTTP fazia tentativas sequenciais, podendo aguardar até request_seconds por
endereço. Uma consulta getMe com esse discador levou 21.726 ms. A fila de respostas
era escoada lentamente, dando a impressão de respostas associadas ao celular errado.
Os chats de origem continuaram correspondentes aos retornados pela API; não houve
broadcast ou alteração de perfil.

**Correção:** app/channels/telegram_connection.py inicia a outra família após
250 ms, respeita um prazo total de conexão e fecha os sockets perdedores. A família
IPv6 continua suportada e preferida quando funciona. A substituição limita-se ao
discador TCP de cada HTTPSConnection do Telegram; hostname, TLS, SNI, verificação
de certificado, ausência de proxy automático e ausência de retry HTTP oculto foram
preservados. Não foi alterada configuração global de rede.

Fechamento preventivo: a implementação anterior era o discador sequencial padrão
de HTTPSConnection, consumido por TelegramAPI e, por ela, pelo cadastro, checagem
e canal. Foi substituído somente o ponto de conexão TCP desses consumidores; não
há opção concorrente de discador legado na execução normal. O transporte HTTP/TLS
canônico, suas validações, os testes e a configuração foram mantidos/reconciliados.

Com o transporte corrigido, getMe levou 960 ms e getWebhookInfo 967 ms; as duas
consultas confirmaram a identidade/webhook esperados. A inicialização real também
registrou 903/894 ms. Long polling vazio de aproximadamente 25 segundos continua
normal, pois corresponde à espera configurada, não à demora de uma resposta pronta.

Foram ampliados logs de app/main.py e app/channels/telegram.py para identificar
início/PID, trava, bot pronto, polling, autorização por perfil, categoria fixa de
comando, envio aceito, deferimento/falha, recuperação e tempo por método. Sem token,
URL autenticada, nome/ID de participante, texto recebido ou resposta privada nos logs.
scripts/inspect_telegram_i2.py fornece inspeção SQLite em somente leitura, sem
rede, migração, limpeza ou alteração de estado. Os recibos privados permanecem
no banco; a evidência é agregada por perfil/categoria e estado de entrega.

Retomadas usam o mesmo banco e offset, preservando os nove recibos existentes,
sem reenvio observado no polling vazio. Uma segunda inicialização enquanto a
anterior ainda encerrava foi recusada com instance_already_running, comprovando
exclusividade real. Aguardar o encerramento efetivo antes de reiniciar evita esse
conflito; não apagar a trava. Não houve reset de fila, offset ou histórico, reparo
de entrega incerta ou modificação de banco I1/configuração/permissões.

[i2-live-validation.json](evidencias/i2-live-validation.json) contém o estado real
dos testes, medições, confirmação humana e pendências;
[i2-runtime-snapshot.json](evidencias/i2-runtime-snapshot.json) contém integridade,
recibos, entregas e coerência do offset. A categoria help inclui /start e não
permite, isoladamente, provar qual alias foi usado; o teste humano informou os
comandos /ajuda e /contexto, e os logs registraram as categorias correspondentes.

Uma única instância supervisionada com a correção permanece ativa para receber
o reteste humano de latência. O PID e horário no relatório JSON são observações,
não substituem verificação de processo/trava em uma retomada. Não iniciar outro
consumidor antes de conferir a instância. O reteste de novas mensagens da síndica
com a conexão corrigida foi concluído posteriormente, conforme evidência abaixo.

**Reteste efetivo após a correção:** duas mensagens do perfil resident foram
recebidas e processadas como help/context; sendMessage foi aceito em 1.012 e
1.064 ms. O usuário confirmou que a conta do morador respondeu rapidamente.
O reteste da síndica ficou inicialmente bloqueado pela indisponibilidade do celular.
Posteriormente, o consumidor corrigido recebeu novas mensagens manager nas categorias
help/context e registrou sendMessage aceito em 1.057/1.004 ms. O usuário informou:
"O Alfredo respondeu agora no telegram da sindica". Há, portanto, processamento e
aceite API de ambos os comandos após a correção, além de confirmação humana de
recebimento nessa conta. A mensagem humana não mede latência nem confirma
individualmente o conteúdo de cada resposta; esses limites permanecem explícitos.
O snapshot posterior registra 14 recibos, todos sent, sem falhas ou entregas incertas,
integridade ok e offset coerente. Esse número é histórico da rodada de comunicação;
a contagem vigente consta do snapshot e da decisão de aceite abaixo.

## Aceite de segurança, autorização, isolamento e idempotência — 09/11/2026

O EXECUTE atual autoriza ensaios locais e permite entradas externas sintéticas,
vedando contas reais de terceiros e mensagens a destinos não autorizados. Assim,
negação a desconhecidos/grupos é comprovada na fronteira do canal com entradas
sintéticas, configuração vigente e SQLite real copiado; não se alega teste externo
com esses destinos. Essa modalidade substitui a antiga pendência de terceira conta
ou grupo real. Os controles do produto e as permissões cadastradas não mudaram.

**Aprovado localmente:** dez cenários em [i2-security-tests.json](evidencias/i2-security-tests.json),
com TelegramChannel, Policy, Orchestrator e Store canônicos, simulação administrativa
desativada e rede bloqueada. Cada cenário recebe uma cópia independente via API
SQLite backup; a origem é aberta mode=ro. Cobrem isolamento nos dois sentidos e
após reinício, message_id igual em chats diferentes, desconhecido/grupo/chat
divergente sem chamada ao orquestrador, nome/perfil alegado sem elevação, update e
mensagem repetidos sem segundo efeito/envio, identidade reutilizada com conteúdo
alterado sem avanço de offset, resultado incerto sem reenvio, e falha entre commit
do núcleo e gravação do recibo. O observador de isolamento recusa referências iguais
ou resposta anterior à última alteração; não infere confirmação humana.

**Isolamento real:** o usuário informou registro e consulta de referências fictícias
distintas nas duas contas e confirmou que cada uma recuperou somente a própria.
O observador somente leitura confirmou referências distintas e respostas API
aceitas contendo exatamente o contexto do remetente. Nomes, IDs e referências não
foram transcritos nas evidências agregadas. Persistência após o novo reinício e
replay do objeto original têm provas separadas, sem repetir a rodada de ajuda.

**Correção encontrada:** em _route, entrada de unidade que falhava na expressão
regular caía no get_context genérico; a renderização posterior aceitava o prefixo
da unidade e devolvia context, ocultando que nenhuma unidade fora salva. Agora esse
formato retorna invalid_input/resposta neutra antes de chamar o núcleo. Sete formatos
inválidos, incluindo múltiplas referências, quebras/tabulação e excesso de tamanho,
têm regressão. Não houve migração nem reparo retroativo das mensagens anteriores.
O roteador canônico foi modificado; não existe segundo caminho de interpretação.

**Replay e limites:** o runner local já reconstruiu uma mensagem de contexto real
com correspondência exata ao hash normalizado persistido, sem segundo efeito/envio
na cópia. Isso não é captura do objeto original. Para essa prova adicional foi
implementada a sonda optativa --i2-replay-evidence: observa somente um contexto
autorizado já entregue, usa o update original em memória e repete processamento/
entrega em cópias SQLite em memória, com capturador sem rede. O núcleo/canal mantêm
o caminho canônico; a sonda observa após deliver, sem escrever no banco operacional.
Os cinco testes da sonda cobrem momento da observação, preservação da origem,
conteúdo privado omitido, execução única, erro sanitizado e bloqueio de ativação
sem modo Telegram autorizado. A sonda não implica reentrega remota pelo Telegram.

**Dados e operação:** esquema permanece versão 2; nenhuma tabela foi alterada.
O runner preservou o conteúdo lógico da origem e os bytes da configuração, removendo
apenas suas cópias temporárias. Foi preservado um backup consistente em
data/backups/i2-before-acceptance-20261109T212841Z.sqlite3, com integridade/FKs
aprovadas e as mesmas regras de acesso do banco original. Mensagens reais de ensaio
acrescentam recibos/auditoria/offsets e alteram somente os contextos fictícios de
suas próprias contas. Não houve limpeza, reset de offset, mudança de perfil ou
edição manual de registros operacionais. Reinícios aguardaram a saída efetiva da
instância anterior; não há consumidor concorrente.

Resultado vigente, critérios comprovados, pendências humanas e fontes de cada
resultado ficam em [i2-acceptance.json](evidencias/i2-acceptance.json).

**Resultado desta execução:** 205/205 testes de regressão e 10/10 cenários nas
cópias do banco vigente aprovados. A sonda recebeu uma consulta original do
morador após o reinício e aprovou dois replays em memória, com hash correspondente,
offset estável, zero segundo efeito e zero chamada adicional de envio;
[i2-real-replay.json](evidencias/i2-real-replay.json). As duas contas já têm novas
respostas API de contexto posteriores ao reinício; o observador confirmou em ambas
exatamente a referência própria. O snapshot registra 24 recibos sent, integridade
ok, FKs válidas e offset coerente, sem pending/sending/failed/uncertain/discarded.

**Elevação real negada:** a mensagem específica solicitada foi enviada pelo
resident e vinculada ao recibo pela correspondência do hash normalizado completo.
O resultado foi phase_not_available, com resposta aceita pela API em 997 ms,
perfil resident preservado e zero requests_state/operational_guidance_revisions.
Não foi usada uma mensagem do manager como prova de negação ao resident.

**Recomendação definitiva: I2 APROVADA.** Substitui a decisão provisória I2 PENDENTE,
que aguardava somente confirmações humanas. O usuário confirmou que ambas as contas
mantiveram exclusivamente suas referências após reinício e que o morador recebeu
apenas o aviso de limite/ajuda ao tentar elevar seu perfil.

Antes do fechamento foi executada uma nova consulta somente leitura, sem repetir
comunicação ou regressão: [i2-final-internal-check.json](evidencias/i2-final-internal-check.json).
A identidade e o texto da tentativa corresponderam ao hash normalizado do recibo.
O perfil cadastrado permaneceu resident; Policy negou guidance.create. A auditoria
vinculada à mesma mensagem e ator contém somente get_context/success e
telegram.receive/processed, ambos como resident, sem operation_id ou entity_id.
Isso representa leitura inofensiva e recebimento no canal, não criação administrativa.
requests_state, operational_guidance e operational_guidance_revisions têm zero
registros. Não se inventou um evento de negação de permissão na auditoria real:
o canal respondeu phase_not_available e a negação determinística foi conferida
diretamente na política. Os bytes do código coincidem com os 205 testes já aprovados.

Nenhum critério I2 está reprovado, pendente ou dependente de nova intervenção humana.
Limites explícitos: desconhecidos/grupos/chat divergente foram entradas sintéticas
com código/configuração vigentes e SQLite copiado, sem contas de terceiros ou envio
externo; replay usou o update original em cópias em memória e não comprova reentrega
pela rede do provedor; falhas de comunicação foram injetadas localmente. Essas
modalidades foram autorizadas no EXECUTE e não são apresentadas como testes externos.
Nenhuma mudança de código/configuração ocorreu no fechamento, portanto a regressão
não foi repetida. A aprovação encerra somente I2; G2/I3 continuam não autorizados.

## Governança, limitações e pendências

Não foram encontrados metadados .git na raiz nem nos ancestrais até D:/; branch
e alterações versionadas não são verificáveis. Não houve comando Git, acesso
GitHub, commit, publicação Lovable ou modificação fora da raiz autorizada.

Referências DevTOLAS e Fs/Comum foram somente leitura. O token real cadastrado foi
lido em memória para as consultas e respostas autorizadas do Telegram; não foi
exibido, registrado em evidência ou solicitado ao chat. Não houve OAuth, Google,
OpenAI, indexação, dependência instalada ou alteração global de rede/serviços.

**Checagem vigente:** scripts/check_telegram_i2.py foi executado em 09/11 com
--allow-live-telegram e bot esperado, no contexto Windows do usuário. A evidência
[i2-telegram-check.json](evidencias/i2-telegram-check.json) registra config_yaml,
secrets_yaml, enrollment_structure, local_configuration, local_token e
getMe_and_getWebhookInfo=passed; missing_fields=[]. live_acceptance continua blocked
nesse verificador porque ele não executa testes por mensagens. Isso não é trava
do polling. O aceite definitivo I2 e as confirmações humanas têm evidência separada.

**Participação humana:** o usuário confirmou recebimento nas duas contas e depois
esclareceu que são contas diferentes, uma selecionada em cada celular. A percepção
de respostas tardias nas duas contas motivou a medição/correção de latência, sem
inferir broadcast. O reteste após a correção e seus limites são registrados em
i2-live-validation.json. Não é necessário repetir o cadastro ou enviar token ao chat.

**Pendências I2:** nenhuma. A decisão consolidada é i2-acceptance.json.
Isolamento real já tem confirmação humana; desconhecidos,
grupos e chat divergente foram negados nos ensaios locais autorizados, sem terceiros.
Retomada de offset não equivale a replay; enviar texto repetido cria outra mensagem.
Os testes T01–T18 de integrações futuras não são bloqueios artificiais de I2 e
continuam fora desta etapa. Nenhum resultado local preenche uma prova real pendente.

Respostas uncertain exigem investigação antes de reparo; o canal não promete
entrega exatamente uma vez. SQLite é privado e não criptografado. Não há
atendimento 24/7. Interpretação natural, documentos, reservas e operações externas
pertencem às próximas fases e seus portões. I3 está fora desta solicitação; após
aceite I2, G2 continua exigindo autorização separada, não concedida aqui.

Houve integração real somente com Telegram nesta etapa. A comprovação se limita
aos cenários efetivamente realizados, sem aprovar piloto, I3 ou T01–T18 completos.

Não há estado temporário artificialmente ativo: código, evidências, documentação
operacional e este relatório registram a situação e a próxima ação.
