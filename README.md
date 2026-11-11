# Vert2Go

**Controle Windows:** o atalho **Alfredo - Ligar e desligar**, na área de trabalho,
abre uma janela com botões e estados visíveis. Pode minimizar; fechar a janela
desliga o agente com segurança. Não depende do VS Code.
[Como usar](docs/controle-windows.md).

I4, 11/11/2026: **OpenAI, indexação e consultas documentais reais validadas,
inclusive nos ensaios das duas contas Telegram; ajuste de qualidade aplicado,
confirmação da bicicleta no Telegram e aceite formal pendentes**. O responsável aceitou formalmente
a I3 e autorizou G3 para Regulamento Interno/Convenção e consultas de teste,
com orçamento estimado de R$ 30/mês e alerta em R$ 24. Também autorizou ativação
documental e testes nas duas contas Telegram. Projeto/chave foram cadastrados
localmente. Os dois documentos foram indexados e o bot manual está com I4 ativa.
As respostas documentais dos perfis de morador e síndico foram aceitas pela API
Telegram, com fontes autorizadas e recebimento confirmado pelo responsável.
338 testes locais passaram, incluindo o controle Windows; evidências reais e confirmação humana ficam separadas.
Em 11/11, o processo manual estava parado e foi reativado. Duas mensagens pendentes
receberam aviso seguro por citação inválida. O responsável informou as perguntas
e autorizou a correção: o negrito quebrado em linhas passou a ser reconhecido.
Os retestes reais de bicicleta na garagem e vagas do apartamento 62 passaram,
e o bot foi reiniciado com a correção. A ativação é manual pelo painel Windows
ou CLI, sem início automático.

Uma nova recusa da bicicleta mostrou que o mini ainda montava citações e inventava
IDs de arquivo. O piloto vigente usa `gpt-4.1-2025-04-14`, com preços atualizados
e orçamento/alerta preservados. O formato restringe referências ao manifesto e
o validador mantém a conferência estrita. Bicicleta nas duas variantes e piscina
passaram no serviço real; a confirmação da bicicleta no Telegram após esse ajuste
está pendente. A busca/interpretação continuam semânticas, sem índice local ou
respostas fixas por palavras-chave. Evidência: [ajuste de qualidade](docs/evidencias/i4-model-quality-fix.json).

I4 acrescenta sincronização manual Drive → Vector Store, consulta natural por
Responses + File Search, verificação de trechos/fontes, controle de versões,
orçamento real estimado e recuperação de chamadas incertas. A ativação é explícita;
o modo anterior não passa a usar OpenAI pela presença de uma chave. Não há escrita
Google, reserva ou alteração administrativa real. Procedimento:
[implementação I4](docs/implementacao-i4.md), [relatório](docs/relatorio-i4.md),
[autorizações](docs/evidencias/i4-authorizations.json) e
[aceite](docs/evidencias/i4-acceptance.json).
O verificador vigente é `scripts/verify_i4.py`; I1/I2/I3 encaminham para ele e
preservam suas evidências históricas. O banco só recebe a migração opcional I4
quando esse uso é explicitamente habilitado; antes disso é feito backup privado
de um banco existente. Os registros operacionais anteriores são preservados.

O texto abaixo conserva a entrega e o histórico I1–I3. Para estado atual, prevalecem
o relatório I4 e os registros de aceite/autorizações correspondentes.

## Histórico da entrega I3

I3, 09/11/2026: integração Google **validada localmente e nas APIs reais; pronta para aceite**.
OAuth Desktop, tokens protegidos e leitura de documentos Drive, Calendar e Sheets
estão disponíveis pelos scripts locais. A conta e os recursos autorizados já
foram cadastrados por solicitação do proprietário; a janela da Agenda é
10–17/11/2026 e o Sheets permite somente `'Página1'!A1:J20`, autorizado depois da
descoberta de metadados. OAuth, renovação, Drive, Calendar e Sheets passaram nas
APIs reais; a Agenda na janela e o intervalo da planilha retornaram vazios.
255 testes locais passaram. O responsável registrou aceite formal em 10/11/2026,
conforme a decisão de aceite I3 atualizada; o relatório de 09/11 permanece histórico.
Os campos Telegram, bancos e aceite definitivo da I2 foram preservados.
Procedimento e limites: [implementacao-i3.md](docs/implementacao-i3.md).
Validação histórica da entrega: `scripts/verify_i3.py`, agora encaminhado à I4,
preservando as evidências históricas. Resultados originais em
[i3-tests.json](docs/evidencias/i3-tests.json) e [relatório I3](docs/relatorio-i3.md).
Na entrega I3, I4–I6 e qualquer escrita Google estavam fora de seu escopo.

Alfredo é o motor de IA vertical para operações condominiais. A I1 fornece o
núcleo determinístico, autorização, memória administrativa, auditoria e orçamento
estimado. A implementação local I2 acrescenta Telegram por long polling, somente
texto e chats privados, dois participantes cadastrados, deduplicação, offset
persistido e tratamento de respostas incertas.

Atualização: 09/11/2026. Regressão local aprovada (205 testes). Aceite definitivo:
**I2 APROVADA**, conforme [decisão de aceite](docs/evidencias/i2-acceptance.json).
A solicitação de configuração e validação real autoriza o bot experimental e
envio/recebimento de teste nesta fase. Token/bot e dois participantes já cadastrados.
Ajuda e contexto foram processados e respondidos pela API real; o usuário confirmou
recebimento nas duas contas. A demora de conexão por IPv6 indisponível foi corrigida
com tentativa concorrente de IPv4, preservando TLS e o host oficial. Os critérios
da I2 foram comprovados nas modalidades reais e locais discriminadas no relatório.
Após a correção de conexão, ajuda/contexto do morador tiveram envios aceitos em
1.012/1.064 ms e recebimento rápido confirmado. O reteste posterior da síndica
registrou ajuda/contexto com envios aceitos em 1.057/1.004 ms; o usuário confirmou
o recebimento nessa conta. O isolamento real com referências fictícias distintas
foi confirmado pelo usuário e pelos recibos persistidos. Autorização, negação de
desconhecidos/grupos, elevação por texto e idempotência passaram nos ensaios locais
com código/configuração vigentes e cópias do banco real. O replay do update original
em memória e a conferência após reinício têm evidências separadas no relatório.
O replay original já passou, sem segundo efeito ou envio. A tentativa real de
elevação do morador retornou apenas o limite da fase, sem criar operação administrativa.
O usuário confirmou esse aviso e o isolamento dos contextos após o último reinício.
A checagem interna vinculou a mensagem ao recibo e à auditoria como resident,
com permissão de criação negada e nenhuma orientação administrativa gravada.
Não há critério I2 pendente ou reprovado. Desconhecidos/grupos foram testados com
entradas sintéticas e nenhum envio externo, conforme autorização; replay do update
original ocorreu em cópias SQLite em memória, sem alegar reentrega pela rede.
Na entrega I2, I3–I6 ainda dependiam de seus portões e não estavam autorizadas.

## Verificação local

Ambiente validado: Windows, Python 3.13.7, SQLite 3.50.4, PyYAML 6.0.3 e tzdata
2025.2. O adaptador usa a biblioteca padrão. Nenhuma dependência foi acrescentada
ou instalada na I2. O ambiente .venv existente contém requirements.txt; em outra
máquina, preparar esse ambiente e instalar as dependências antes de executar.

Execute na raiz com o ambiente preparado. Testes e demonstrações usam dados
fictícios e bancos temporários. A inicialização finita abaixo cria ou migra
somente o banco local de desenvolvimento indicado.

```powershell
Set-Location -LiteralPath 'D:\MeusArquivos\Fs\Projetos\Vert2Go'
.\.venv\Scripts\python.exe scripts/verify_i2.py
if ($LASTEXITCODE -ne 0) { throw 'Verificação I2 reprovada. Consulte docs/evidencias/i2-tests.json.' }
.\.venv\Scripts\python.exe -m examples.i2_demo
if ($LASTEXITCODE -ne 0) { throw 'Demonstração I2 reprovada.' }
.\.venv\Scripts\python.exe -m app.main --config config.telegram.example.yaml --database data/i2-development.sqlite3
if ($LASTEXITCODE -ne 0) { throw 'Inicialização local reprovada.' }
```

Sem --telegram, app.main valida configuração, mantém trava, verifica/migra SQLite,
recupera operações, expira orientações e encerra. Não lê segredos nem chama
Telegram. config.example.yaml continua como exemplo local I1;
config.telegram.example.yaml contém IDs fictícios. Preserve configurações
particulares existentes.

## Telegram e segurança

O procedimento consolidado está em [implementacao-i2.md](docs/implementacao-i2.md).
scripts/setup_telegram_i2.py cadastra o token com entrada oculta e os IDs numéricos
confirmados localmente. O cadastro agora permite concluir primeiro token/bot
(--token-only com descoberta autorizada), validando o username AlfredoVert2GoBot
via getMe e salvando o progresso antes da descoberta dos participantes. A descoberta
inclui mensagens privadas pendentes como /start, sem exigir marcadores de perfil.
O operador atribui os dois perfis explicitamente a IDs encontrados; não há autocadastro.
A descoberta opcional usa a API oficial, sem confirmar ou
descartar a fila remota. scripts/check_telegram_i2.py valida os arquivos e, somente
com --allow-live-telegram, consulta getMe/getWebhookInfo; não envia mensagens nem
abre bancos. O polling exige --telegram e --allow-live-telegram e continua manual.
Esses indicadores declaram a autorização do operador; não substituem consentimento
humano. Nunca enviar o token ao chat. Google foi cadastrado na I3;
OpenAI tem cadastro separado na I4, sem ativação implícita.

live_acceptance=blocked no verificador indica testes que ele não executa; esse
campo não desativa o bot nem impede polling. O aceite por mensagens é registrado
separadamente em [i2-live-validation.json](docs/evidencias/i2-live-validation.json).

config.yaml e secrets.yaml particulares foram criados sem sobrescrever arquivos
preexistentes. O acesso está restrito ao usuário Windows autorizado, à identidade
isolada do Codex e ao SYSTEM. Em 08/11 a ACL foi aplicada apenas à identidade
isolada/SYSTEM, bloqueando o usuário; o leitor convertia esse PermissionError em
invalid_yaml. A correção de 09/11 preservou o conteúdo integral dos dois arquivos.
Erros de acesso agora retornam configuration_read_denied e o nome fixo do arquivo;
erros de sintaxe retornam invalid_yaml e coordenadas, sem exibir conteúdo.

Campos nulos são permitidos exclusivamente no cadastro e impedem a ativação
operacional. A checagem offline agora distingue YAML válido de cadastro incompleto:
config_yaml, secrets_yaml e enrollment_structure ficam passed; enquanto faltarem
token/bot_id, reason é telegram_enrollment_incomplete e nenhuma API é chamada.
Depois de cadastrar token/bot, a checagem autorizada já pode consultar sua identidade
e webhook, mesmo enquanto os IDs dos participantes ainda estiverem ausentes.
Na primeira inspeção da ausência de respostas não havia processo Python, banco
I2 ou trava I2. O consumidor foi iniciado de forma supervisionada e criou
data/i2.sqlite3 para o bot cadastrado. O banco I1 e as configurações foram preservados.
Não foi possível reconstruir por que a invocação anterior não deixou processo ativo.

O erro invalid_telegram_secrets informado após o prompt vinha da validação local
do texto recebido, antes da API. A entrada descartada não foi registrada; sua
forma exata não pode ser reconstruída. Agora há códigos específicos para entrada
vazia, caracteres de controle, espaços internos e formato inválido, separados de
erros de arquivo/esquema e de rejeição do provedor. Apenas espaços externos de uma
nova entrada podem ser removidos; tokens já armazenados não são normalizados nem
sobrescritos. Há até três tentativas ocultas. A evidência de cada execução informa
etapa/resultado sem token ou trechos de mensagens.
No terminal do VSCode é esperado que nada apareça ao colar o token, nem asteriscos;
isso não informa se a colagem foi recebida. O roteiro operacional agrupa os comandos
em um único bloco PowerShell, analisado antes de abrir o cadastro interativo.

Comandos reais: /ajuda, /contexto e /unidade REFERENCIA. Texto livre informa os
limites da fase. Interpretação natural e conhecimento documental dependem de
fases posteriores. A memória administrativa via Telegram é ensaiada exclusivamente
com transporte falso; sua ativação no transporte real está bloqueada nesta fase.

A identidade vem dos IDs cadastrados. Grupos e desconhecidos recebem somente
rejeição neutra, limitada por taxa. Áudio, arquivos, encaminhamentos e edições não
executam operações. O núcleo mantém as permissões; não há autocadastro ou
alteração de perfil por texto.

Logs contêm eventos e códigos fixos, sem token, URL autenticada, texto ou erro
bruto do provedor. Incluem processo/trava, bot pronto, início de polling, quantidade
recebida, perfil autorizado, categoria de comando, resposta aceita pela API,
falhas/recuperação e duração de chamadas. Sem process_started, a execução ainda
não chegou ao Python; telegram_ready e telegram_poll_started confirmam o consumidor.
getUpdates pode aguardar até poll_seconds quando não há mensagens, sem ser falha.
scripts/inspect_telegram_i2.py examina SQLite em somente leitura, sem rede ou reparo,
registrando recibos, estados de entrega e coerência do offset de forma agregada.
scripts/accept_telegram_i2.py executa dez cenários em cópias SQLite temporárias
consistentes, com transporte capturado e rede bloqueada. Não lê segredos nem escreve
no banco ativo. Comandos de unidade fora do formato permitido agora são rejeitados
com invalid_input; antes podiam retornar uma consulta de contexto sem salvar unidade.
SQLite contém dados privados e não é criptografado.
.gitignore cobre configuração particular, segredos, bancos/WAL/SHM, logs e ambiente
virtual; isso não substitui as permissões do Windows. Não foi encontrado
repositório Git local. Nenhuma operação Git/GitHub ou publicação Lovable ocorreu.

## Documentação e pendências

- [Implementação e operação I2](docs/implementacao-i2.md): configuração, contratos,
  retomada, falhas, retenção e procedimento manual.
- [Relatório I2](docs/relatorio-i2.md) e [evidências](docs/evidencias/i2-tests.json):
  resultados locais e pendências externas.
- [Checagem de preparação real](docs/evidencias/i2-telegram-check.json): configuração,
  credenciais e bot; o aceite geral continua separado de testes por mensagens.
- [Validação real](docs/evidencias/i2-live-validation.json) e
  [snapshot operacional](docs/evidencias/i2-runtime-snapshot.json): respostas reais,
  confirmação humana, retomada e pendências. O snapshot não infere confirmação humana.
- [Aceite de segurança](docs/evidencias/i2-security-tests.json) e
  [decisão I2](docs/evidencias/i2-acceptance.json): cenários, origem das entradas,
  limites entre integração local/Telegram real e pendências objetivas.
- [Checagem interna final](docs/evidencias/i2-final-internal-check.json): perfil,
  autorização, auditoria correlacionada e ausência de orientações administrativas.
- [Correção do bloqueio YAML](docs/evidencias/i2-yaml-fix.json): causa de acesso,
  preservação de conteúdo e verificação no contexto Windows do usuário.
- [Correção do fluxo do token](docs/evidencias/i2-token-flow-fix.json): diagnóstico
  limitado ao que foi observado, cadastro por etapas, descoberta e regressão.
- [Implementação I1](docs/implementacao-i1.md) e
  [relatório I1](docs/relatorio-i1.md): histórico da fundação local.
- PRD v1.2.0, especificação v0.1.8 e plano v0.1.1 em docs/ permanecem preservados.
  A solicitação de 08/11/2026 autoriza implementar I2; estados históricos de
  planejamento não revogam essa autorização local.

Telegram real de ajuda/contexto já foi exercitado nas duas contas. OAuth e leituras
Google foram validados e aceitos na I3. OpenAI/indexação e consultas documentais
reais foram validadas nos ensaios da I4, inclusive nas duas contas Telegram.
As novas consultas recusadas tiveram ajustes e retestes do serviço aprovados;
a confirmação da bicicleta no Telegram com o ajuste atual e o aceite formal I4 permanecem
pendente conforme o relatório vigente. Reservas, escrita Sheets e
aceite integrado T01–T18 dependem das fases e portões posteriores.
Não há broadcast, serviço Windows, webhook,
publicação, cobrança condominial ou integração oficial. O orçamento OpenAI usa
consumo real medido e preços/câmbio estimados. Retenção fornece elegibilidade,
sem exclusão ou agendamento automático.
