# Implementação I5 — operações experimentais

## Correções autorizadas em 13/11/2026 — comportamento vigente

Transporte atualizado após os relatos de oscilação: conexão HTTPS persistente por
instância do cliente Telegram, encerrada no desligamento ou erro. A abertura TCP/TLS
é separada do envio HTTP; somente uma falha comprovada nessa abertura permite manter
`sendMessage` como pendente para nova tentativa. Após início do pedido, o resultado
continua incerto e não pode ser repetido automaticamente. Não foram relaxados TLS,
host fixo, autenticação ou vínculo entre proposta entregue e confirmação.
538 testes locais passaram. Duas provas reais somente leitura registraram 12
chamadas seguidas e um período de 71 segundos com pausa de 30 segundos na mesma
conexão. São evidências de transporte, não de cancelamento Google real ou aceite I5.
Depois do fechamento confirmado pelo proprietário, o painel foi reaberto e ligado
no modo autorizado. O processo filho e a trava do consumidor foram conferidos;
90,06 segundos contínuos em ATIVO, com zero falhas, foram registrados na
[observação operacional](evidencias/i5-telegram-keepalive-panel-verified-20261113.json).
Não houve confirmação de cancelamento pelo agente de desenvolvimento. A proposta
anterior expirou; seu encerramento não cancela a reserva original.

O mesmo painel Windows passa a iniciar `--operations --allow-live-google-writes`
quando `config.yaml` já contém operações autorizadas. Isso corrige o caminho de
partida que ainda iniciava exclusivamente I4, sem novas permissões ou outro motor.
Sem operações/autorização, conserva o modo anterior. A inicialização Telegram
agora reexecuta somente o handshake após falha de transporte/rate limit/resultado
incerto de leitura; não repete envio de mensagem ou escrita Google. A espera é
interrompida por desligamento. Erros de identidade/autenticação continuam fatais.
São 531 testes aprovados após essa correção; estado real no relatório vigente.

O EXECUTE desta data autoriza cancelamento de reservas próprias e herança funcional
`manager` → `resident`. Substitui a restrição anterior de reserva exclusiva do
morador e a ausência de cancelamento, inclusive a matriz original da seção 6.1 da
especificação. PLAN, PRD e especificação originais foram preservados; esta extensão
é documentada aqui e na [definição atual do Alfredo](agentes/alfredo-i5.md).

`ReservationCancellations` reutiliza titularidade por ID, unidade, destinos,
exclusividade local, recibos idempotentes, auditoria e a outbox Sheets. A migration
aditiva `005_reservation_cancellations.sql` acrescenta o diário `pilot_cancellations`,
com referência à reserva original e índice que impede dois cancelamentos efetivos.
Não substitui a tabela original nem altera seus identificadores ou propostas.

O diálogo consulta somente as reservas do participante na Agenda. Um intervalo que
cruza reservas não escolhe alvo nem significa cancelamento parcial: pede a seleção
da reserva inteira. Depois apresenta seus dados e exige outra autorização explícita.
Uma recusa encerra somente a proposta; autorização, prazo, hash, unidade e destino
são revalidados. A LLM identifica a finalidade `reservation_cancel`; não pode
escolher um ID fictício, conceder privilégios ou confirmar a operação. A consulta
`my_reservations` permite listar os próprios registros sem digitar referências.

A alteração Google é estritamente um PATCH de `status=cancelled`, com `If-Match`
da versão conferida. Não há chamada DELETE, exclusão local ou limpeza de histórico.
Há consentimento externo específico `operations.authorization.calendar_cancel`,
desabilitado por padrão. Antes do PATCH, o estado `committing` já está persistido.
O sucesso só é informado após GET confirmar o cancelamento. Resultado incerto não
repete gravação: a retomada consulta a Agenda; se o evento continuar confirmado,
uma solicitação explícita de nova tentativa prepara outra proposta e exige nova
autorização. Alteração concorrente detectada por ETag exige nova conferência.

O [PATCH do Calendar](https://developers.google.com/workspace/calendar/api/v3/reference/events/patch)
preserva campos omitidos; a [modificação condicional](https://developers.google.com/workspace/calendar/api/guides/version-resources)
retorna 412 se a versão mudou. No Google, o [estado cancelado](https://developers.google.com/workspace/calendar/api/v3/reference/events)
tem semântica de evento removido e pode desaparecer posteriormente. Por isso a
preservação durável de proposta, IDs e auditoria permanece no SQLite, sujeita à
retenção existente, sem depender da permanência do evento cancelado no Google.

Não foi encontrada política documental específica de cancelamento. Nenhum prazo,
multa, penalidade ou nova restrição condominial foi inventado. Aplicam-se identidade,
titularidade/unidade, destino autorizado e confirmação explícita. Restrições de
criação continuam no fluxo de criação; não são reutilizadas como prazo de desistência.

Depois da conferência Google, SQLite registra o cancelamento da reserva e o diário
da operação na mesma transação, com auditoria dos dois registros. A planilha recebe
atividade `reservation_cancellation/cancelled` pela mesma outbox; a linha histórica
da criação não é sobrescrita. Falha no Sheets não desfaz o cancelamento. Relatórios
distinguem reserva cancelada na Agenda de proposta encerrada sem execução.

As permissões efetivas de `manager` são a união de suas permissões administrativas
com as configuradas para `resident`. A identidade continua por ID numérico e a
seleção de reservas continua limitada ao próprio participante e à unidade vinculada;
não existe permissão implícita de cancelar reservas de outras unidades. O cadastro
externo aceita unidade para manager, sem outra conta. A ausência do vínculo pede
conferência cadastral, em vez de simular uma unidade. O campo opcional `legacy_units`
permite compatibilidade explícita por ID em correções cadastrais, sempre junto à
titularidade original. A configuração local usa Maria 52 e Toninho 62; a unidade
fictícia anterior de Toninho foi mantida somente como vínculo histórico da mesma
conta, sem reescrever reservas existentes.

SQLite operacional `data/i2.sqlite3`: versão 4 → 5, backup prévio e comparação de
todos os registros anteriores aprovada. Leitores I4/inspeção reconhecem o esquema
5; o painel continua no modo I4 e não foi acionado. Não há Supabase neste fluxo.
Validação: 525 testes aprovados e reprodução completa com configuração vigente,
Google/Telegram fictícios, rede bloqueada e banco temporário. Cancelamentos reais,
novo recebimento humano e aceite integral continuam pendentes. I6 não autorizada.
As seções abaixo que descrevem entregas anteriores preservam a cronologia.

Continuidade: reserva humana de 16/11/2026, das 16h às 19h, confirmada com linguagem
natural e conferida na Agenda. Agora são cinco eventos; a nova outbox segue pendente.
A consulta de disponibilidade mantém seu objetivo após correção de data inválida;
essa correção passou em reprodução isolada com a Agenda real. Estado completo,
regressão vigente e pendências no [relatório I5](relatorio-i5.md).

Estado vigente após o segundo incidente de conversa: falso bloqueio de fonte em
alternativa fora de validade corrigido; 496 testes aprovados. A reprodução completa
com a configuração vigente e dez leituras da Agenda real passou, com gravação
simulada somente em memória, sem nova reserva externa. Contexto operacional mantido.
Detalhes, evidências e limites no [relatório I5](relatorio-i5.md); os registros abaixo
preservam a cronologia. Reteste humano e aceite integral continuam pendentes.

Continuidade em 12/11/2026: configuração promovida com os recursos existentes;
OAuth de escrita, leitura Google, extração no modelo real e cenários selecionados
de escrita/reconciliação aprovados. SQLite migrado aditivamente com backup e
conferência das linhas anteriores. Ensaios reais Telegram e retestes após correções
executados; conferência final com quatro eventos, oito linhas e zero pendências.
Após a rejeição da conversa anterior, foi implementada a autorização conduzida
pelo próprio Alfredo; 462 testes locais aprovados, incluindo 21 do novo diálogo.
O teste humano de reserva subsequente falhou na coleta parcial. A correção
progressiva passou em 490 testes locais e na reprodução isolada com leitura da
Agenda real, sem escrita. Reteste humano, usabilidade e aceite formal continuam
pendentes. Estado atual em
[relatório I5](relatorio-i5.md); as afirmações abaixo sobre a execução de 11/11
permanecem históricas.

Atualização: 11/11/2026. Responsável pela implementação: Codex, mediante solicitação
expressa do responsável nesta sessão. Base: fase I5 do plano v0.1.1, PRD v1.2.0 e
especificação v0.1.8. Os documentos normativos foram preservados integralmente.

## Estado e fronteiras

Código local implementado, testes com mocks e demonstração finita disponíveis.
Não houve ativação da I5 no bot, leitura de segredos, migração do banco operacional,
OAuth novo, gravação Google ou chamada OpenAI paga nesta entrega. A instrução de
implementar substitui a espera anterior pela autorização de execução local; não
substitui as autorizações específicas de recurso exigidas pelo plano.
O aceite I4 continua vigente para o bot já configurado. Aceite I5 real e G5/I6 pendentes.

## Componentes e fechamento dos caminhos anteriores

- `app/services/operations.py`: máquina de estados, regras, confirmação, Agenda,
  reconciliação, solicitações, notificações e outbox.
- `app/config/operations.py` e seção opcional `operations` no único YAML: unidades
  simuladas, recursos, condições e proveniência, destinos, categorias e limites.
- `app/integrations/calendar.py` e `sheets.py`: contratos existentes ampliados;
  `app/integrations/operations.py` reutiliza HTTP/OAuth e aplica a fronteira de escrita.
- `app/channels/operations.py`: conversa com resumo antes da confirmação;
  `app/ai/operation_intent.py` reutiliza Responses, modelo e orçamento I4.
- A memória administrativa continua exclusivamente em `OperationalMemory`, com
  confirmação, versões e auditoria existentes; nenhum armazenamento paralelo foi criado.
- `004_operations.sql`: migração original da I5; `005_reservation_cancellations.sql`
  acrescenta o diário de cancelamentos na versão 5. As tabelas I1–I4 são preservadas.
  Sem habilitação explícita, bancos antigos não recebem a migração I5.
- O verificador canônico passa a ser `verify_i5.py`. Entradas I1–I4 encaminham para
  ele, preservando os resultados históricos. Leitores I4 e inspeção Telegram aceitam
  os esquemas 4 e 5. O painel Windows continua iniciando a I4, sem habilitação implícita I5.

## Reservas e reconciliação

A conversa mantém recurso, data e horários no contexto existente, coleta somente
o que falta e não transforma data sem horário em evento de dia inteiro. A extração
determinística confere os valores na mensagem original, inclusive respostas curtas;
o modelo não pode preencher horários ausentes. Datas relativas usam a recepção
original. Alternativas ambíguas exigem esclarecimento. Conteúdo de resposta a um
morador continua literal, mesmo quando menciona reserva ou disponibilidade.

`reservation_conversation.py` e `reservation_time.py` conduzem essa coleta no
caminho Telegram existente. O motor fornece `reservation_availability` somente
leitura, autorizado como `reservation.read`: subtrai ocupações opacas da Agenda,
respeita dia inteiro, janela, vigência, antecedência e horários configurados.
Leitura incompleta não pode provar disponibilidade. Faixas livres não constituem
proposta nem autorização; duração máxima é informada separadamente. Os motivos
de intervalo inválido vêm da mesma validação utilizada pela execução. A proposta
só é criada com dados completos; gravação continua exigindo autorização posterior.

Dias sem mês/ano são resolvidos apenas pela data já conhecida ou por uma única
possibilidade no período externo autorizado; ambiguidade exige data completa.
“Ao meio-dia” é término explícito quando acompanha outro início. Alternativas
com término após a validade ou fora das condições cadastradas são descartadas
antes da revalidação de fonte: a inaptidão de uma sugestão não invalida o pedido
original. Falhas reais de fonte nos intervalos elegíveis continuam bloqueando.

O objetivo de consultar disponibilidade é mantido no mesmo contexto de coleta,
inclusive depois de corrigir uma data inválida. Informar uma nova data para essa
consulta continua sendo leitura, sem exigir permissão de criação ou gerar proposta.
Escolher horários muda para a coleta de reserva, sujeita às permissões existentes.

A unidade vem do cadastro externo por ID autorizado; o comando de contexto não
altera a unidade elegível para reservar. `resident` e `manager` podem propor,
confirmar, consultar e cancelar suas próprias reservas quando as permissões e o
vínculo de unidade estiverem configurados. `manager` mantém também relatórios,
respostas e reconciliação administrativos, sem cancelamento irrestrito de terceiros.

O motor valida intervalo com fuso, janela Google autorizada, horário, duração,
antecedência, vigência e taxa informativa. Nenhuma condição tem valor condominial
padrão. Uma regra `verified` precisa de fonte autorizada, revisão/hash atuais no Drive
e metadados I4 sincronizados. Regras `unverified`, `conflicting` ou vencidas bloqueiam.
Regras `simulated` são cenários explicitamente fictícios e aparecem assim no resumo.

A Agenda é consultada antes da proposta e novamente sob exclusividade local na
confirmação. Se ocupada, alternativas nos deslocamentos externos configurados são
consultadas na Agenda e continuam sujeitas à nova conferência final. Eventos de dia
inteiro são respeitados; intervalos são de início inclusivo e fim exclusivo. Por
conservadorismo, eventos opacos da Agenda experimental bloqueiam todos os recursos
declarados nessa mesma Agenda. Não se infere disponibilidade de SQLite ou Sheets.

O resumo inclui os dados, origem/condições e taxa, terminando na pergunta de
autorização do Alfredo. ID/hash continuam exigidos internamente, junto do mesmo
remetente, proposta vigente e aceite explícito da taxa quando positiva. Pelo Telegram
a proposta precisa ter envio aceito. Uma resposta curta sem associação vale apenas
para uma proposta inequívoca; a resposta nativa do Telegram permite escolher a
pergunta exata quando houver mais de uma. A frase deve autorizar o tipo de ação
perguntado. A LLM não possui intenção de confirmar nem ferramentas de escrita;
toda execução passa pelas permissões Python.
Os horários do resumo são apresentados em Brasília, mantendo UTC apenas nos
registros internos. Metadados no contexto existente vinculam a pergunta efetivamente
enviada ao participante, à proposta/hash e à mensagem. O texto visível não precisa
conter o comando de confirmação; os atalhos anteriores coexistem por compatibilidade.

Perguntas e avisos utilizam o [ForceReply do Telegram](https://core.telegram.org/bots/api#forcereply),
sem método de API novo. Só uma resposta a mensagem do próprio bot na mesma conversa
pode fornecer a associação nativa. O aviso da administração contém o pedido e pede
o texto da resposta, que é tratado como dado literal; o bot solicita outra autorização
antes de enviá-lo. Referências e versões atuais são consultadas pelo motor, sem
ser inventadas pelo modelo ou exigidas do participante.

A sincronização mantém sua outbox independente. Após a resposta administrativa,
Alfredo pode perguntar se deve conferir as atividades na planilha; também entende
o pedido natural de atualizar a planilha. Essa autorização tem prazo, destino e
consumo único persistidos no contexto existente, com permissão revalidada antes da
chamada ao motor. Recusa não sincroniza. Comandos explícitos anteriores permanecem
como atalhos opcionais. Não houve migração de banco, nova dependência ou serviço.

`committing` é persistido e commitado antes do POST. O ID do evento deriva de
ambiente/operação; propriedades privadas vinculam operação, recurso, proprietário
pseudônimo e hash da proposta. Há releitura do evento e nova busca de conflitos.
Somente evidência compatível permite `confirmed`. A consulta posterior repete a
conferência na Agenda. Um evento removido/alterado não continua confirmado por cache.

Timeout, evento ausente/incompatível ou leitura inconclusiva deixam
`needs_reconciliation`. Após reinício, `committing` vira pendência de reconciliação;
não há novo POST automático. Uma pendência sobreposta bloqueia novas confirmações.
Reconciliação busca o mesmo ID e valida todos os vínculos. Ausência não autoriza
recriação automática: o operador deve investigar. Conflito após escrita não provoca
exclusão ou cancelamento automático: gera uma exceção idempotente na categoria
externa indicada para a síndica e um aviso de verificação manual. Após correção
externa, a reconciliação pode comprovar o evento sem novo POST. A proposta e a
outbox vinculam os destinos originais; alterar IDs/intervalo de escrita no YAML
não redireciona operações já propostas ou pendentes. Edições externas simultâneas continuam fora
da garantia da trava local. O runtime mantém também uma trava por Agenda, além da
trava do banco, para impedir duas instâncias I5 usando bancos diferentes.

## Sheets, solicitações e avisos

Sheets é um diário operacional independente, com região finita dedicada A:J.
Cada atividade confirmada gera uma outbox na mesma transação do estado local.
As dez colunas são: ID estável do registro, criação, unidade fictícia, categoria,
estado da atividade, responsável, atualização, referência externa, sincronização
e conteúdo mínimo. Os registros de resposta têm referência à operação de resposta;
o SQLite mantém o vínculo com a solicitação original para auditoria.

O reprocessamento é manual sob demanda. Antes de gravar, lê a região autorizada,
localiza o ID ou reserva uma linha vazia ainda não atribuída. Persiste a linha antes
do PUT, usa `RAW` e confere por releitura. Timeout após PUT é reconciliado por leitura;
não usa `append`. Dados externos, IDs duplicados ou linha movida/substituída bloqueiam
sobrescrita. Região cheia exige intervenção. Sheets não oferece transação com uma
edição externa concorrente; por isso a região precisa ser exclusiva do piloto.
Falha Sheets mantém a reserva verificada na Agenda e deixa sincronização pendente.
Conflitos após escrita permanecem incidentes não encerrados para retenção.

Solicitações confirmadas usam categorias/responsáveis externos. Só categorias
atribuídas a `manager` são encaminhadas; as demais ficam pendentes sem encaminhamento
automático. A urgência é persistida e destacada no aviso de encaminhamento.
A resposta do gestor exige confirmação e versão esperada. Ela resolve a solicitação
simulada, sem aprovar reserva ou alterar regra. O aviso ao solicitante original é
criado atomicamente, uma vez por versão, e usa a fila Telegram existente. Avisos de
envio incerto não são reenviados automaticamente. Não há broadcast de orientações.
Relatórios são agregados, somente para `manager`, sempre sob demanda e identificados
como histórico operacional experimental; não substituem a conferência de reservas.

## Linguagem natural e memória administrativa

A extração semântica recebe texto atual, instante original, fuso e nomes dos
recursos/categorias. Um esclarecimento pode incluir somente os campos estruturados
do pedido pendente no mesmo ambiente, canal, usuário e conversa, dentro do prazo
externo de confirmação. Mudança de perfil invalida esse contexto; um novo pedido
independente o substitui. Nenhum histórico integral é reenviado. Datas relativas
usam a data de recebimento original. Campos
extraídos incluem a finalidade solicitada (`requested_action`), separada da
sinalização de esclarecimento. A conversa valida localmente os campos necessários:
uma pergunta redundante do modelo não bloqueia uma proposta completa, enquanto
dados ausentes ou ambíguos continuam exigindo esclarecimento. Cache de extração
inclui a identidade do contrato e das instruções para não reaproveitar resultado
obsoleto após uma correção. A autorização e a confirmação não são decididas pela LLM.
Em uma resposta administrativa, o texto extraído inequivocamente em `content` é
normalizado para `response`; valores divergentes exigem esclarecimento. Uma resposta
literal `Ok` ao campo de resposta pendente é preenchida sem nova chamada à LLM,
mas continua gerando apenas proposta, com confirmação separada obrigatória.
Intervalos brasileiros completos, com duas datas/anos, horários, ligação `até` e
indicação de Brasília, são normalizados diretamente do texto pelo parser compartilhado
de reservas e orientações. Esse caminho não infere datas ou anos e rejeita valores
literais inválidos; intervalos alternativos ou incompletos não são preenchidos por ele.
Campos indispensáveis ambíguos bloqueiam a ação e pedem esclarecimento; a interpretação
não inventa IDs, perfil, taxa, regra ou prazo. Nenhuma configuração do modelo foi
alterada. Chamadas estruturadas usam o modelo externo da I4, sem armazenamento
remoto da resposta e sem ferramentas; o mesmo orçamento registra tokens, reserva
custo e bloqueia chamadas incertas/repetidas. Não há nova dependência.

Cadastro, correção e cancelamento de orientação reutilizam a memória existente.
Em consulta documental pertinente, a memória é filtrada por assunto, perfil,
público e vigência antes de qualquer composição. Só quando há orientação pertinente
uma comparação semântica adicional confronta o contexto mínimo com a resposta
documental verificada. Compatibilidade insuficiente/conflito produz ressalva e
orientação para esclarecimento da administração, sem aplicar prevalência inventada.
Orientações compatíveis são atribuídas à administração. Fontes, versão e vigência
são revalidadas antes da entrega. Orientações não são indexadas, copiadas ao Sheets
ou publicadas espontaneamente. A consulta direta por assunto conserva ressalva
explícita de que a orientação não altera regulamento.

## Ativação e operação manual

Antes de qualquer uso real: confirmar IDs da Agenda/Sheets e exclusividade do piloto,
região A:J dedicada, janela temporal, cadastro de unidade e condições comprovadas
ou cenários fictícios expressos. Registrar autorizações na seção `operations` do
`config.yaml` particular, preservando todos os demais campos. O exemplo é fictício,
tem escritas desabilitadas e não deve substituir o cadastro particular.

O OAuth existente é somente leitura. A reautorização será manual, no navegador,
usando o cadastro Google já existente com a opção adicional explícita de escrita.
Com I5 autorizada, os escopos passam a Drive leitura, Calendar events (owned quando
aplicável) e Sheets escrita; IDs/operações seguem limitados pelo Python. O escopo
Sheets não é limitado pelo Google a uma planilha: a allowlist local é obrigatória.

`app.main` só ativa I5 com as opções conjuntas `--operations`,
`--allow-live-google-writes`, `--telegram`, `--allow-live-telegram`, `--knowledge`
e `--allow-live-openai`, além do cadastro autorizado. Antes de migrar banco existente,
é produzido backup SQLite privado com verificação. Ausência de consentimento ou
cadastro impede ativação. Não foi executada essa ativação nesta entrega.

Comandos de operação disponíveis no modo I5: ajuda; consulta de solicitações;
relatório; consulta de reserva pelo ID; reconciliação pelo ID; sincronização da
outbox. Os nomes exatos são apresentados pela ajuda do bot. Desligamento permanece
manual e controlado. Não há serviço novo, início automático ou publicação.

Para validação exclusivamente local, os comandos abaixo usam somente exemplos
fictícios, mocks, bancos temporários e evidências locais:

```powershell
Set-Location -LiteralPath 'D:\MeusArquivos\Fs\Projetos\Vert2Go'
.\.venv\Scripts\python.exe -B scripts/verify_i5.py
if ($LASTEXITCODE -ne 0) { throw 'Verificação local I5 reprovada. Consulte docs/evidencias/i5-tests.json.' }
.\.venv\Scripts\python.exe -B -m examples.i5_demo
if ($LASTEXITCODE -ne 0) { throw 'Demonstração local I5 reprovada.' }
```

## Recuperação e limites

Não trocar de banco para contornar pendências. Parar o consumidor antes de restaurar
backup ou mudar parâmetros; manter banco/WAL/SHM e backup privados. A recuperação
usa o mesmo banco e IDs. Reverter ativação significa iniciar a I4 sem as opções I5,
preservando a versão 5 e os registros pendentes. Não fazer downgrade destrutivo nem
restaurar snapshot anterior a uma possível escrita remota sem reconciliar a Agenda.

A retenção continua somente como relatório de elegibilidade, sem DELETE ou
agendamento. Pendências I5 preservam conservadoramente contexto, recibos e auditoria.
Não há pagamento, reservas oficiais ou alteração documental. Cancelamentos seguem
exclusivamente o fluxo de titularidade, confirmação e conferência descrito acima.
Ensaios reais integrados, confirmação humana e aceite final pertencem aos portões
seguintes e permanecem pendentes.

## Referências técnicas verificadas

Contratos usados: [IDs e criação de eventos Calendar](https://developers.google.com/workspace/calendar/api/v3/reference/events/insert),
[valores RAW no Sheets](https://developers.google.com/workspace/sheets/api/samples/writing) e
[Structured Outputs da OpenAI](https://developers.openai.com/api/docs/guides/structured-outputs).
A consulta à documentação não constitui validação real da conta ou dos serviços.
