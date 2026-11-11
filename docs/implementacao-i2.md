# Implementação e operação I2 — canal Telegram

Atualização: 09/11/2026, Codex. Conhecimento técnico vigente do Vert2Go.
Implementação local e configuração/validação real autorizadas pelas respectivas
solicitações de execução I2. Complementa I1 e substitui a declaração anterior de
que I2 não foi iniciada. A autorização de teste do bot foi concedida na solicitação
de 08/11; o cadastro e os testes reais de ajuda/contexto nas duas contas foram
concluídos; os critérios de segurança e aceite I2 também foram encerrados conforme
as evidências reais e locais discriminadas abaixo. O bloqueio de acesso aos
YAML foi corrigido em 09/11.
Token e participantes já foram cadastrados pelo usuário. Ajuda/contexto tiveram
respostas reais aceitas pela API e recebimento confirmado nas duas contas. O aceite
definitivo é **I2 APROVADA**, registrado em [i2-acceptance.json](evidencias/i2-acceptance.json).
O isolamento após reinício e a negação de elevação do morador foram confirmados
pelo usuário e pelos registros internos. Isso não aprova o piloto nem I3.

## Escopo e referências

Aplicados PRD v1.2.0, especificação Alfredo v0.1.8, plano v0.1.1 e normas DevTOLAS
de governança, método, documentação, estado vigente, uso de LLM e conteúdo para
copiar. O catálogo Fs/Comum não indica padrão adicional para o motor sem interface.
Referências externas e documentos normativos locais foram preservados.

Validação, autorização, polling e comandos de ensaio são determinísticos. Não há
LLM ou envio de contexto/documentos. Interpretação natural fica para I4.

API consultada em 08/11 e 09/11/2026: [getMe](https://core.telegram.org/bots/api#getme),
[getUpdates](https://core.telegram.org/bots/api#getupdates),
[sendMessage](https://core.telegram.org/bots/api#sendmessage) e
[ResponseParameters](https://core.telegram.org/bots/api#responseparameters).
O offset seguinte confirma updates anteriores; polling e webhook são exclusivos.
A retenção remota é de até 24 horas; não há recuperação ilimitada ou operação 24/7.

## Componentes e fechamento da mudança

Orchestrator.handle continua como entrada canônica das operações. Políticas e
memória não foram duplicadas. A entrada estruturada local I1 coexiste para ensaios
sem rede. Cada configuração aceita apenas um canal de identidade.

- app/channels/telegram.py: HTTPS, normalização, comandos, polling, recibos e entrega.
- app/channels/telegram_connection.py: conexão TCP com tentativas intercaladas das
  famílias IPv6/IPv4, mantendo HTTPS, certificado e SNI do host oficial.
- app/config/schema.py: configuração Telegram opcional imutável; carregador de token
  exclusivo para a inicialização real explicitamente habilitada.
- app/core/policy.py: canal autorizado vindo da configuração; perfil vindo do cadastro.
- app/main.py: inicialização finita por padrão; polling sob trava por toda a execução.
- 002_telegram.sql: dois estados adicionais; esquema vigente 2 com onze tabelas.
- scripts/verify_i2.py: verificação vigente; verify_i1.py encaminha para ela,
  preservando evidências históricas I1.
- scripts/setup_telegram_i2.py: preparação sem sobrescrita e cadastro local com
  token oculto; descoberta opcional de IDs sem confirmar updates.
- scripts/check_telegram_i2.py: checagem de configuração/token e diagnóstico
  opcional do bot, com evidência sem token, IDs, textos ou URLs autenticadas.
- scripts/inspect_telegram_i2.py: snapshot SQLite em somente leitura, sem rede,
  migração ou reparo; recibos, estados de entrega e coerência do offset agregados.
- scripts/accept_telegram_i2.py: dez cenários de segurança sobre cópias consistentes
  e privadas do banco real, sem rede/segredos nem escrita na origem.
- app/channels/telegram_replay_probe.py: sonda opcional de um update original de
  contexto, recebida após entrega normal; replay em SQLite em memória, envio capturado.

## Configuração e ativação manual

Usar config.telegram.example.yaml como referência para config.yaml particular,
preservando arquivos existentes. Exatamente dois usuários habilitados, resident e
manager, IDs distintos e chat privado igual ao ID de cada participante. O bot tem
outro ID; channels.telegram.bot_id deve corresponder ao prefixo do token. Alterar
bot/ambiente exige revisar o banco destinado ao ensaio.

Parâmetros não secretos no YAML: polling 1–50 segundos, timeout HTTP maior que
polling e até 60 segundos, lote 1–100, intervalo de retentativa 1–60 segundos.
Limites gerais de tamanho e mensagens/minuto continuam obrigatórios. O canal
limita entrada a 4096 caracteres; respostas são texto simples, limitadas também
em unidades UTF-16, sem parse_mode e sem prévia de links.

Na preparação de 08/11, config.yaml e secrets.yaml foram criados porque não existiam.
Naquela preparação, bot, IDs e token estavam nulos; o usuário depois concluiu o
cadastro real. Não são usados os IDs fictícios do exemplo. O ambiente
é i2-experimental e simulation_mode permanece true, mesmo no transporte real.
Isso mantém os limites funcionais da I2. A ACL aplicada naquela preparação permitia
apenas a identidade isolada do agente e SYSTEM, excluindo o usuário do terminal.
Em 09/11 foi incluído explicitamente o usuário Windows autorizado, preservando as
regras anteriores e a herança desabilitada. O conteúdo dos dois arquivos ficou
idêntico byte a byte. Não foram adicionados grupos amplos, como Users/Everyone.
A escrita do cadastro preserva as ACLs. Não há criptografia em repouso; se
recriar/mover os arquivos, rever permissões antes de cadastrar credenciais.
O banco I1 foi preservado. A validação real posterior criou e usou o banco I2
dedicado, sem migração ou reparo de banco operacional preexistente.

Não configurar permissões usando apenas a identidade corrente de um agente isolado:
ela pode ser diferente do usuário Windows que executará o cadastro. Validar a
leitura no contexto desse usuário antes de considerar a preparação concluída.

O esquema de cadastro aceita null somente em channels.telegram.bot_id, nos IDs
dos dois usuários e no chat privado correspondente, além do token ainda ausente.
Demais tipos, limites, permissões e controles são os mesmos do esquema operacional.
load_enrollment_config retorna dados para cadastro, sem fornecer um Config
operacional incompleto. load_config e load_telegram_token continuam recusando
identidades/token ausentes. Não se preenchem identidades com números fictícios.

O leitor agora distingue configuration_read_denied, configuration_file_missing,
configuration_read_error, invalid_yaml_encoding, invalid_yaml_size e invalid_yaml.
Os diagnósticos incluem apenas o nome fixo do arquivo e, em erro de sintaxe,
linha/coluna. Nunca incluem valores, trechos YAML ou mensagem bruta da exceção.
Se a falha for de acesso ao arquivo, não existe campo YAML a corrigir: o parser
não chegou a ler o documento.

Criar um bot exclusivo de teste pelo [BotFather oficial](https://t.me/BotFather),
seguindo a [criação oficial de bots](https://core.telegram.org/bots/features#creating-a-new-bot).
Guardar o token localmente. Preparar duas contas humanas distintas: morador
simulado e síndica simulada; duas sessões da mesma conta têm o mesmo ID e não
atendem ao requisito. Não é necessário contratar OpenAI ou configurar Google.

O bot indicado pelo usuário é @AlfredoVert2GoBot; as duas contas já iniciaram
conversa. O cadastro verifica esse username e o ID via getMe, não só o prefixo do
token. --expected-bot recebe exclusivamente username público sem @; o padrão CLI
é AlfredoVert2GoBot. Nunca colocar token nesse argumento.

O roteiro abaixo conclui primeiro token/bot e depois os participantes. O token é
solicitado somente no prompt oculto, até três tentativas. Usar somente a sequência
completa fornecida pelo BotFather, sem aspas, rótulo, URL ou prefixo adicional.
No terminal integrado do VSCode nenhum caractere ou asterisco aparece: esse é o
comportamento de segurança esperado e não confirma nem descarta uma colagem.
Após colar somente o token, pressionar Enter uma vez e observar o próximo resultado.
Espaços ASCII externos de uma nova entrada podem ser removidos; espaços internos,
caracteres de controle e formatos inválidos continuam recusados. Se a colagem não
for recebida, tentar Shift+Insert ou clique direito no terminal. Não é necessário
regenerar o token por uma rejeição local de formato; autenticação remota é outra etapa.

Diagnóstico do erro relatado: com secrets.yaml nulo e esquema aprovado, o único
invalid_telegram_secrets imediatamente após o prompt no código anterior era a
checagem local de formato do texto recebido. Não era leitura YAML nem resposta
de getMe. A entrada histórica foi descartada sem registro, portanto não se pode
afirmar se chegou vazia, truncada, com rótulo ou com caracteres de controle.
Os diagnósticos novos eliminam essa ambiguidade sem registrar seu conteúdo:

- telegram_token_input_empty, telegram_token_input_control_characters,
  telegram_token_input_whitespace e telegram_token_input_format_invalid: prompt.
- telegram_token_stored_*: valor existente no arquivo, preservado sem normalização.
- telegram_secrets_schema_invalid e telegram_non_i2_secrets_present: esquema local.
- Erro de transporte/provedor na etapa getMe: formato local aprovado, mas identidade
  remota ainda não confirmada. Não é classificado como erro de entrada.

Após getMe aprovar ID e username esperados, token e bot_id são salvos antes de
getWebhookInfo/getUpdates ou de solicitar IDs. Uma falha posterior ou Ctrl+C não
perde o token já cadastrado. Token preexistente nunca é substituído automaticamente;
uma identidade diferente é recusada. --token-only encerra após salvar o token e
verificar webhook, sem consultar participantes ou enviar mensagens. Se houver
webhook ativo, a execução interrompe sem removê-lo, preservando o token verificado.

A descoberta aceita remetentes humanos de mensagens privadas textuais pendentes,
inclusive /start, e exibe apenas IDs no terminal local. Confirme pessoalmente qual
conta pertence a cada ID antes de atribuir resident/manager. Marcadores privados
/cadastro_morador e /cadastro_sindica são dicas opcionais, não requisito nem concessão
de perfil. Se não souber distinguir os IDs, envie esses marcadores de cada conta
e repita somente a segunda etapa. IDs digitados nessa etapa precisam constar nos
candidatos encontrados; duplicação ou identidade desconhecida não é gravada.
Não usar bots terceiros para obter IDs.

Na descoberta, getUpdates é chamado sem offset e sem allowed_updates; não confirma
updates nem modifica o filtro remoto. Lê no máximo os primeiros 100 pendentes,
sem descartar fila. Iniciar conversa anteriormente não garante que a mensagem ainda
esteja pendente: getUpdates não consulta o histórico inteiro, e a fila remota dura
até 24 horas. Se uma conta não aparecer, enviar uma nova mensagem privada e repetir
a etapa dos participantes com outros pollers parados; não apagar fila ou banco.
Se houver mais de 100 updates pendentes, investigar antes de confirmar qualquer
offset. Não executar descoberta com outro polling ativo. A API confirma
updates quando recebe offset maior, conforme [contrato oficial](https://core.telegram.org/bots/api#getupdates).

O cadastro completa somente campos nulos preparados; preserva valores existentes,
recusa converter configuração I1 e recusa trocar o bot. Arquivos já válidos ficam
inalterados. A preparação pula arquivos existentes sem tentar abri-los para
escrita exclusiva; isso evita PermissionError de criação no Windows. A estrutura
de cadastro é validada antes de solicitar token ou acessar a rede.
Se falhar/cancelar, não iniciar polling; conferir a checagem antes da
retomada. Caso já conheça os IDs, o cadastro sem as opções de descoberta funciona
sem rede e solicita os mesmos números no terminal. Nunca enviar credenciais ao
chat, argumentos, variáveis de ambiente, histórico do shell, logs ou documentação.

Um único bloco operacional, sem valores secretos a completar. O token é digitado
apenas no prompt oculto do Python; não colar este bloco na conversa do Telegram.
Manter o agrupamento PowerShell abaixo ao copiar tudo: ele faz o shell analisar
todos os comandos antes de iniciar o processo interativo, em vez de enviar linhas
soltas enquanto o processo filho está aguardando entrada.
O programa permanecerá no polling manual até Ctrl+C. Só há envio de respostas a
mensagens recebidas; não há mensagem de teste automática nem broadcast.

```powershell
& {
Set-Location -LiteralPath 'D:\MeusArquivos\Fs\Projetos\Vert2Go'
.\.venv\Scripts\python.exe scripts/setup_telegram_i2.py --discover --allow-live-telegram --expected-bot AlfredoVert2GoBot --token-only
if ($LASTEXITCODE -ne 0) { throw 'Etapa do token interrompida. Consulte o codigo e a etapa, sem enviar o token ao chat.' }
.\.venv\Scripts\python.exe scripts/setup_telegram_i2.py --discover --allow-live-telegram --expected-bot AlfredoVert2GoBot
if ($LASTEXITCODE -ne 0) { throw 'Cadastro I2 interrompido. Nao iniciar o bot.' }
.\.venv\Scripts\python.exe scripts/check_telegram_i2.py --allow-live-telegram --expected-bot AlfredoVert2GoBot
if ($LASTEXITCODE -ne 0) { throw 'Diagnostico I2 reprovado. Consultar o codigo seguro na evidencia.' }
# Durante o polling, em cada conta privada: /ajuda, /unidade i2-morador ou /unidade i2-sindica, e /contexto.
# Use somente referencias ficticias distintas para cada conta. Confira o isolamento antes e depois do reinicio.
.\.venv\Scripts\python.exe -m app.main --config config.yaml --secrets secrets.yaml --database data/i2.sqlite3 --telegram --allow-live-telegram --i2-replay-evidence
if ($LASTEXITCODE -notin @(0, 130)) { throw 'Polling I2 terminou com falha. Nao apagar banco ou lock.' }
.\.venv\Scripts\python.exe scripts/inspect_telegram_i2.py
if ($LASTEXITCODE -ne 0) { throw 'Inspecao local I2 reprovada. Consultar o snapshot seguro.' }
.\.venv\Scripts\python.exe scripts/accept_telegram_i2.py
if ($LASTEXITCODE -ne 0) { throw 'Aceite local de seguranca I2 reprovado. Consultar i2-security-tests.json.' }
.\.venv\Scripts\python.exe scripts/verify_i2.py
if ($LASTEXITCODE -ne 0) { throw 'Regressao I2 reprovada. Consultar docs/evidencias/i2-tests.json.' }
}
```

Não iniciar o mesmo bot com bancos diferentes. data/i2.sqlite3 deve permanecer
associado ao mesmo bot/ambiente. Se já existir em outra retomada, parar e fazer
backup privado consistente antes de usá-lo. Uma checagem com saída zero significa
apenas preparação/diagnóstico aprovado; o campo live_acceptance continua blocked
até a validação supervisionada por mensagens. Uma saída zero de --token-only
significa apenas que a etapa do token terminou; não exige que os participantes
estejam cadastrados. Se restarem apenas os dois IDs, a checagem autorizada valida
getMe/getWebhookInfo mas ainda retorna cadastro incompleto e saída 1.
Sem indicadores de autorização,
app.main não lê segredos nem inicia transporte real. O verificador offline lê e
valida os arquivos locais em memória, sem transmitir seus valores. Esse transporte ainda não
era executado na primeira entrega; a validação real posterior está registrada
em i2-live-validation.json. Com arquivos já cadastrados, não é necessário repetir
o assistente de cadastro para iniciar app.main.

Na partida: validar configuração/token, adquirir trava, verificar/migrar banco,
recuperar núcleo e entregas interrompidas, verificar getMe e getWebhookInfo,
então polling. Divergência do bot, webhook ativo, 401/403/409 ou estado inválido
interrompem com código seguro. Não remove webhook nem descarta fila remota.

Parar com Ctrl+C no terminal original. Banco e trava fecham em finally. Sem
processo, internet ou notebook ativo não há atendimento. Não apagar lock/banco
para tentar recuperar funcionamento. Trava é por banco; não iniciar o mesmo bot
com bancos diferentes. Conflito remoto 409 interrompe o processo.
Aguardar telegram_closed/local_interrupted e a saída efetiva do processo antes de
reiniciar. Uma chamada HTTPS em andamento pode retardar o encerramento; a trava
continua válida nesse intervalo. A tentativa de abrir outra instância nesse estado
foi recusada de verdade com instance_already_running, sem segundo consumidor.

## Entrada e comandos

normalize preserva update_id, message_id, remetente, chat e data UTC originais.
Nomes não participam da identidade. Aceita texto em message/chat privado; recusa
bots, edições, callbacks, encaminhamentos e sender_chat/business. Não baixa mídia.
Grupos e desconhecidos não executam operações e recebem apenas rejeição fixa
neutra, sujeita à taxa. Updates malformados ou sem mensagem não geram envio.

O canal real oferece ajuda, leitura do próprio contexto e referência de unidade
fictícia. Texto livre informa o limite da fase; não registra solicitação externa.
Contexto permanece isolado por ambiente/canal/usuário/chat, com retenção de 30 dias.
O formato de unidade aceita uma referência ASCII de 1 a 64 letras, números,
hífens ou sublinhados. Formatos inválidos são rejeitados com invalid_input e resposta
neutra, sem leitura ou alteração de contexto. Corrigido no aceite: o fallback anterior
fazia get_context para certas entradas inválidas iniciadas por /unidade.

/simular recebe envelope JSON estrito action/payload somente em transporte falso
injetado e explicitamente habilitado pelo ensaio. Reutiliza propostas, confirmação
por hash, revisões, vigência e autorização I1. IDs de operação/idempotência são
derivados da identidade da mensagem. O transporte real recusa ativação
administrativa e não existe opção CLI de habilitação. Não há broadcast.

## Persistência e retomada

telegram_poll_state guarda offset por ambiente/bot. telegram_updates guarda
recibo por update e mensagem/chat/bot, hash da entrada, código, resposta mínima,
estado de entrega e horários. Não guarda token nem JSON bruto; o banco é privado.

O núcleo commita antes do recibo. Falha nessa fronteira mantém o offset anterior;
reentrega usa deduplicação do núcleo e IDs estáveis. Recibo e offset são gravados
juntos. Repetições não geram novo efeito/resposta; identidade com conteúdo alterado
bloqueia processamento. Lote inválido/fora de ordem não é confirmado. Falha de
armazenamento não confirma sucesso nem permite avançar offset.

Entrega: pending → sending → sent. sending é persistido antes da chamada. Queda
nesse ponto ou timeout após possível envio produz uncertain. Não há reenvio
automático de uncertain: sendMessage não oferece chave de idempotência utilizada
pelo adaptador. Pode haver resposta sem entrega comprovada. Investigar no chat de
teste e banco protegido antes de autorizar reparo; não afirmar entrega confirmada.

429 mantém pending com retry_after persistido e suspende novos envios do bot,
inclusive após reinício. Falha definitiva marca failed. Polling transitório aguarda
intervalo configurado interrompível. Entrega revalida cadastro; respostas
particulares de usuário revogado são descartadas. Taxa inclui ajuda, texto livre
e simulação; rejeição por taxa é registrada sem responder novamente.

Pendências de envio com mais de 30 dias são descartadas logicamente. Elegibilidade
de retenção inclui recibos terminais após 30 dias; preserva pending/sending/
uncertain, operações abertas e incidentes relacionados. Offset permanece como
estado mínimo. Não há exclusão ou limpeza automática.

## Migração, rollback e diagnóstico

Antes de usar banco operacional existente, parar e produzir backup privado
consistente por API SQLite ou cópia offline do conjunto consistente. A entrega
não altera bancos existentes de data/. O verificador usa temporários.

A abertura reconhece application_id Vert2Go e versões 1/2; verifica esquema
completo, integridade e FKs antes de migrar v1. Migração transacional preserva
tabelas/dados I1. Banco desconhecido/adulterado é recusado. Não há downgrade:
rollback exige parar, preservar banco atual e restaurar backup v1 em outro caminho
com código compatível e verificação de integridade. Não apagar tabelas.

Eventos seguros: process_started (PID/modo), instance_lock_acquired,
telegram_starting, telegram_delivery_recovered (quantidade),
telegram_identity_verified, telegram_webhook_clear, telegram_ready,
telegram_poll_started, telegram_poll_received (quantidade),
telegram_update_received, telegram_sender_authorized (perfil),
telegram_input_rejected (código), telegram_command_started (categoria fixa),
telegram_update_processed, telegram_update_deduplicated, telegram_reply_sending,
telegram_reply_sent (aceite API), telegram_reply_deferred/discarded/unavailable,
telegram_poll_unavailable/recovered, telegram_http_finished (método fixo/duração),
telegram_closed e startup_rejected. Não habilitar debug HTTP ou imprimir exceções brutas: a URL
contém token. TLS e host fixo api.telegram.org, sem redirects, proxy automático ou
retentativas ocultas. SQLite não é criptografado; proteger por permissões Windows.

Diagnóstico real da demora: o DNS retornou IPv6 primeiro; a conexão IPv6 não
completou no teste de 3 segundos, enquanto IPv4 conectou em 235 ms. O discador
sequencial original deixou getMe levar 21.726 ms; com o discador corrigido getMe
levou 960 ms e getWebhookInfo 967 ms. A correção inicia a próxima família após
250 ms e fecha sockets perdedores, com prazo total para conexão. A abordagem de
tentativas TCP concorrentes é inspirada na [RFC 8305](https://www.rfc-editor.org/rfc/rfc8305.html);
não há alteração global de rede ou desativação de IPv6. HTTPSConnection continua
validando o certificado e o hostname api.telegram.org e realizando TLS/SNI.
getUpdates aguardando aproximadamente poll_seconds sem mensagens é comportamento
normal de long polling; esse tempo não representa demora para responder a uma
mensagem já recebida. Os tempos seguros agora permitem distinguir as situações.
No reteste real com a correção, o morador enviou ajuda/contexto e os sendMessage
foram aceitos em 1.012/1.064 ms, com recebimento rápido confirmado pelo usuário.
O reteste posterior da síndica recebeu/processou ajuda/contexto, com sendMessage
aceito em 1.057/1.004 ms. O usuário confirmou o recebimento na conta da síndica.
Essa confirmação encerra a pendência de recebimento desse perfil após a correção;
não mede a percepção humana de latência nem aprova os demais cenários da I2.

Antes do primeiro início supervisionado não havia processo Python, banco I2 ou
trava I2. Isso comprova ausência de consumidor naquele momento, mas não explica
historicamente por que o comando informado não deixou um processo ativo. Depois,
o consumidor iniciou, recebeu a fila das duas contas e respondeu. A rede IPv6
indisponível explicou a demora adicional e o escoamento tardio dessas respostas.
Cada sendMessage continuou destinado ao chat do recibo, com verificação do chat
retornado pela API. Respostas atrasadas nos dois celulares correspondiam a entradas
pendentes dos dois perfis; não houve broadcast.

## Validação e continuidade

README e [i2-tests.json](evidencias/i2-tests.json) registram execução reproduzível:
regressão I1, canal falso, transporte mockado, migração, trava, interrupção,
armazenamento, timeout, flood control, isolamento e demonstração. A regressão atual
tem 205 testes aprovados: os 190 anteriores, dez de aceite de segurança e cinco da
sonda de replay. Inclui 37 de cadastro/diagnóstico, sete de logs/inspeção e oito de
conexão TCP. Nessa suíte não são usados tokens reais,
contas ou APIs operacionais. Não houve Git/GitHub ou Lovable. O verificador
offline não declara o estado da integração real; aponta para sua evidência própria.

[i2-telegram-check.json](evidencias/i2-telegram-check.json) registra configuração,
token, getMe/getWebhookInfo aprovados e nenhum campo ausente. live_acceptance=blocked
significa que esse script não executa cenários por mensagens; não é uma trava do
consumidor. A confirmação real fica em
[i2-live-validation.json](evidencias/i2-live-validation.json). O
[snapshot](evidencias/i2-runtime-snapshot.json) é uma leitura agregada de recibos e
entregas, não confirma recebimento humano por inferência.
[i2-yaml-fix.json](evidencias/i2-yaml-fix.json) registra reprodução do PermissionError
original e validação após a correção. O cadastro real no terminal do usuário chegou
ao prompt oculto; foi cancelado sem fornecer token, antes de qualquer chamada externa.
Isso comprova o desbloqueio local e não comprova Telegram operacional.

[i2-token-flow-fix.json](evidencias/i2-token-flow-fix.json) registra a correção
posterior de entrada/persistência/descoberta: na ocasião o token ainda estava
ausente e as chamadas reais estavam pendentes. Esse registro é histórico e foi
complementado pelo aceite parcial real. A cada nova execução do cadastro, o
arquivo docs/evidencias/i2-enrollment.json é gerado com etapa, motivo fixo, progresso
e contagem de candidatos; não contém token, ID de participante, texto ou payload
do provedor. Ele distingue falha na entrada, arquivo/esquema, getMe, webhook,
descoberta e confirmação dos perfis. Os testes usam evidências de cadastro apenas
em diretórios temporários.

Critérios I2 e origem da evidência, reconciliados com o EXECUTE de aceite:

1. getMe/getWebhookInfo: identidade do bot corresponde ao cadastro e webhook vazio.
2. Identificação dos dois perfis: ajuda e contexto respondem somente no chat de
   origem; API aceitar sendMessage não comprova leitura/recebimento pelo humano.
3. Isolamento: cada conta salva referência fictícia própria e lê apenas a sua;
   repetir a leitura após parar/reiniciar manualmente com o mesmo banco/ambiente.
4. Troca de perfil por mensagem não altera cadastro ou capacidades; simulação
   administrativa continua bloqueada no transporte real, inclusive para manager.
5. Desconhecido, grupo e chat de outra conta: entradas externas sintéticas, código
   real, configuração vigente e cópias do SQLite; zero chamadas de orquestração,
   zero mudança de estado de negócio, resposta neutra capturada sem envio externo.
   O EXECUTE atual autoriza essa simulação e veda uso de terceiros/destinos não
   autorizados. Isso substitui a exigência operacional anterior de terceira conta
   e grupo reais, sem mudar as regras de autorização do produto.
6. Reentrega: o ensaio local reconstrói uma mensagem de contexto persistida e aceita
   a reconstrução somente se o hash completo normalizado for idêntico ao recibo.
   O teste direto do update original é separado: --i2-replay-evidence ativa uma
   sonda para a próxima consulta de contexto autorizada e já enviada normalmente.
   O objeto recebido de getUpdates permanece somente em memória; a API SQLite backup copia
   o SQLite para memória, o canal canônico processa a duplicata antes/depois de
   reabrir o estado copiado e deliver usa um capturador sem rede. Nenhum replay
   é executado no banco ativo nem envia outra mensagem real. A evidência fixa
   i2-real-replay.json registra ausência de efeito/envio duplicado e offset estável,
   sem update bruto, IDs ou conteúdo. A sonda roda uma única vez por inicialização
   e não decide o aceite sozinha. Não comprova uma nova reentrega pela rede do provedor.
7. Registrar resultados sem token/IDs/textos privados; preservar material privado
   necessário no banco protegido. Rodar regressão após qualquer correção.

Identidade/webhook, comandos básicos, isolamento com referências distintas após
reinício e recusa de elevação do morador foram exercitados de verdade e confirmados
pelo usuário. A auditoria correlacionada manteve resident, registrando somente
get_context e telegram.receive; a política negou guidance.create e as tabelas
administrativas permaneceram vazias. O replay usou um update original real em
cópias em memória, sem segundo efeito/envio. Não há pendência de aceite I2.
A decisão e os limites constam de i2-acceptance.json. Desconhecido/grupo e falhas
injetadas são provas locais autorizadas, sem alegar uso desses destinos reais.
Timeout, 429 e falhas críticas são cobertos offline; não provocar carga,
trocar credenciais ou descartar fila para fabricar falhas reais. Depois do aceite,
I3 exigirá G2 separado. A solicitação atual veda avançar a I3 e não concede OAuth,
OpenAI, transferência documental, escrita Google ou aprovação T01–T18/MO01–MO10.
