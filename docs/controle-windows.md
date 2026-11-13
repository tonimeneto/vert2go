# Controle do Alfredo no Windows

Atualizado em 13/11/2026.

O atalho **Alfredo - Ligar e desligar**, na área de trabalho, abre o controle
local do agente. Não depende do VS Code. A alternativa na pasta do projeto é
[Alfredo.cmd](../Alfredo.cmd).

## Uso

1. Abra o atalho com dois cliques.
2. Clique em **Ligar Alfredo**. Aguarde **ATIVO**, em verde.
3. Para parar, clique em **Desligar Alfredo**. Aguarde **INATIVO**, em vermelho.

Também há Ctrl+L para ligar e Ctrl+D para desligar, com a janela selecionada.
Minimizar mantém o bot ligado. Fechar a janela solicita desligamento e aguarda
a operação em andamento terminar antes de encerrar. O computador precisa
permanecer ligado e conectado.

## Estados

- **INATIVO**, vermelho: nenhuma execução do bot foi encontrada e o controle pode iniciar.
- **LIGANDO**, âmbar: inicialização em andamento; ainda não confirmou acesso Telegram.
- **ATIVO**, verde: o fluxo canônico confirmou identidade e webhook do Telegram.
- **DESLIGANDO**, âmbar: parada solicitada; uma consulta/polling em andamento pode levar algum tempo.
- **SEM CONEXÃO**, âmbar: houve falha Telegram; o fluxo existente tenta reconectar.
  Isso também se aplica à inicialização: uma falha temporária de transporte não
  encerra mais o bot antes da primeira conexão. Desligar/fechar interrompe a espera.
- **FALHA**, vermelho: inicialização/execução falhou; aparece somente um código de erro seguro.
- **OUTRA EXECUÇÃO**, âmbar: a trava do bot está ocupada por execução fora deste painel.
- **ESTADO INDISPONÍVEL**, âmbar: a trava não pôde ser verificada; iniciar fica bloqueado.

ATIVO indica funcionamento do consumidor Telegram. Não comprova qualidade das
respostas OpenAI nem substitui o aceite da I4. O estado não é inferido apenas
pela existência de um PID ou de um arquivo antigo.

## Configuração e limites

Cada nova ativação lê `config.yaml`, inclusive o modelo e os preços configurados.
Após alterar o modelo, desligue e ligue pelo painel. A janela não mostra chaves,
mensagens dos participantes, documentos ou respostas brutas do provedor.

A ativação usa o mesmo `app.main`, banco `data/i2.sqlite3`, configuração, segredos,
consentimentos G3 e limites já existentes. Não instala dependências, serviço
Windows, tarefa agendada ou inicialização automática. Quando a configuração já
contém operações I5 com autorização de escrita vigente, o mesmo botão inclui o
modo de operações e sua autorização no runtime canônico. Configuração sem operações
ou apenas em rascunho mantém o modo anterior. O painel não concede permissões,
não altera destinos nem executa reserva/cancelamento por si; essas ações seguem
os vínculos e as confirmações do diálogo. Ver [implementação I5](implementacao-i5.md).

Em 13/11 foi corrigida a partida que ainda iniciava somente o modo anterior,
apesar da configuração I5 já autorizada. Após uma atualização de código, feche a
janela antiga e abra o atalho novamente para carregar a versão atual. Uma janela
que já está aberta mantém o código carregado quando foi iniciada.

Uma segunda abertura do atalho restaura o painel existente. O controle nunca
mata processos por PID: uma execução manual fora dele deve ser encerrada no
seu terminal antes de usar os botões. A trava canônica continua prevenindo
instâncias simultâneas. A parada é cooperativa e não interrompe uma chamada
externa no meio; banco, recibos e consumo seguem as regras de recuperação vigentes.

## Implementação e validação

- `app/desktop/control.py`: thread supervisionada, sinal de parada e estados.
- `app/desktop/panel.py`: janela Tkinter, cores, botões e atalhos de teclado.
- `scripts/alfredo_control.py`: entrada Windows por `pythonw.exe`.
- `scripts/install_alfredo_shortcut.ps1`: instala/confere somente o atalho nomeado.
- `app.main` e `TelegramChannel`: notificações de ciclo de vida e sinal de parada opcionais.

O CLI anterior continua disponível. Não há um segundo motor de processamento,
índice local ou busca determinística criada pelo controle.

Testes específicos cobrem prontidão, parada durante operação, reativação,
execução duplicada/externa, falha de leitura da trava, erros sem dados privados
e integração com o caminho canônico. A regressão integral está em
[i5-tests.json](evidencias/i5-tests.json); o histórico da verificação Windows está em
[windows-control-live.json](evidencias/windows-control-live.json).

A regressão de 13/11 passou com 531 testes. Os seis cenários adicionados cobrem
modo I5 previamente autorizado, ausência de autorização em rascunho, código seguro
de configuração, recuperação na inicialização, parada durante essa recuperação
e erro de autenticação que deve continuar falhando sem repetição indiscriminada.

Atualização posterior: 538 testes aprovados após a correção de transporte. O
cliente reaproveita uma conexão HTTPS saudável entre polling e respostas, em vez
de criar uma conexão por chamada. Certificado, SNI e host fixo continuam validados.
Falha antes de transmitir qualquer byte HTTP mantém a resposta pendente para
nova tentativa; falha após início do envio continua incerta e não é repetida.

O estado seguro do controlador é gravado em `data/alfredo-control-status.json`,
com modo, estado, código fixo, PID e contadores de reconexão/prontidão, sem textos
de conversa ou credenciais. Esse registro deve ser conferido junto à trava do
processo e à data; um arquivo antigo sozinho não prova que o bot esteja ativo.
O launcher aceita `--start` para uma solicitação manual de abrir e ligar; o atalho
habitual mantém o comportamento de abrir o painel para uso dos botões. Isso não
cria serviço ou inicialização automática do Windows.
