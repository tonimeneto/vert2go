# Controle do Alfredo no Windows

Atualizado em 11/11/2026.

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
Windows, tarefa agendada ou inicialização automática. Não altera reservas,
Google ou permissões. A I5 foi implementada localmente, mas este painel continua
iniciando a I4. A ativação I5 é separada e permanece pendente;
ver [implementação I5](implementacao-i5.md).

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

Treze testes específicos cobrem prontidão, parada durante operação, reativação,
execução duplicada/externa, falha de leitura da trava, erros sem dados privados
e integração com o caminho canônico. A regressão integral está em
[i4-tests.json](evidencias/i4-tests.json); a verificação Windows em
[windows-control-live.json](evidencias/windows-control-live.json).
