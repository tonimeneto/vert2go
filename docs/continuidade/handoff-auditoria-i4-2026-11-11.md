# Handoff para auditoria — Vert2Go / I4 / controle Windows

Data: 11/11/2026. Responsável pelo registro: Codex.
Natureza: continuidade temporária específica do projeto; apoio à auditoria, não norma nem aceite.
Corte operacional observado: **11/11/2026 às 12:32:28, America/Sao_Paulo**.

## 1. Objetivo da próxima sessão

Auditar o estado efetivo da I4, as alterações de geração/validação documental,
a configuração de modelos e o controle Windows recém-criado. Começar em
**somente leitura**, com achados rastreáveis e propostas mínimas. Não implementar
correções, alterar configuração, reiniciar/parar o bot, enviar mensagens, realizar
consultas pagas ou avançar à I5 durante essa auditoria.

Projeto autorizado: `D:\MeusArquivos\Fs\Projetos\Vert2Go`.
Repositório esperado nas instruções: `https://github.com/tonimeneto/vert2go.git`.
**Não foi encontrado `.git` local.** Não houve inicialização ou operação Git;
branch e diff Git não foram verificados. O usuário proibiu operações Git.
As comparações existentes usam hashes de conteúdo, não Git.

Antes de concluir qualquer coisa, ler `AGENTS.md` e reconciliar código, configuração,
evidências e estado observável. A tarefa de handoff não é a execução da auditoria.

## 2. Resumo do estado e pendência principal

- I3 aceita pelo responsável. G3 e testes documentais nas duas contas autorizados.
- Dois documentos autorizados foram transferidos e indexados na OpenAI.
- Consultas reais tiveram sucessos e falhas; ambos os tipos de registro foram preservados.
- Houve recebimento humano confirmado de respostas documentais nos dois perfis
  Telegram em ensaios anteriores. Isso não aprova automaticamente modelos/ajustes posteriores.
- **A I4 não tem aceite formal. A falha recorrente da bicicleta não está demonstrada como resolvida.**
- O controle Windows passou nos testes locais e na operação real de ligar/desligar.
  Isso comprova ciclo de vida do bot, não qualidade da interpretação documental.
- No corte, o painel mostrava **Alfredo - ATIVO**, e a trava do banco estava ocupada.
- **I5 não foi iniciada.** Não houve reserva, escrita Google, administração real,
  OCR, exclusões ou nova instalação de dependências nesta continuidade.

## 3. Autorizações e restrições vigentes

O responsável aceitou formalmente I3 e autorizou G3 para enviar exclusivamente
o Regulamento Interno e a Convenção identificados na I3, indexá-los e consultar
esses documentos. Orçamento estimado **R$ 30/mês**, alerta **R$ 24**. Autorizou
também ativação documental e testes nas duas contas Telegram já cadastradas.
Fonte: [i4-authorizations.json](../evidencias/i4-authorizations.json).

O responsável depois autorizou corrigir os defeitos observados, solicitou mudar
o modelo no arquivo com comentários visíveis e criar o controle Windows.
Isso não equivale a aceitar I4 ou autorizar I5. A próxima auditoria permanece
somente leitura; chamadas/alterações devem aguardar uma solicitação de execução.
As autorizações G3 já concedidas não devem ser solicitadas novamente para o mesmo escopo.

**Não abrir nem expor `secrets.yaml`, tokens, OAuth ou chaves para esta auditoria.**
Não copiar o banco operacional para uma área pública. Consultar apenas os campos
não secretos de configuração/metadados necessários. Não incluir IDs de participantes,
conteúdo de mensagens, credenciais ou respostas brutas em relatório ou prompt.
DevTOLAS e `Fs\Comum` são referências externas somente leitura.

O usuário exige **busca e interpretação semânticas pela IA**. Não criar índice
local, busca de negócio por palavras-chave, nem mapeamentos fixos pergunta → resposta.
Validação determinística de autorização, orçamento, versão e citações continua
sendo uma responsabilidade do Python. Leituras locais usadas no diagnóstico e
fixtures de teste não são um mecanismo de busca do bot.

## 4. Configuração efetivamente observada

Fonte vigente: `config.yaml` privado, não o exemplo YAML nem um relatório histórico.
Os seguintes valores não são secretos:

- `knowledge.model`: **gpt-4o-2024-08-06**.
- `openai.input_usd_per_million`: **2.50**.
- `openai.output_usd_per_million`: **10.00**.
- `openai.usd_brl`: **5.00**, premissa configurada, não cotação de mercado.
- Orçamento/alerta: **30.00 / 24.00 BRL**.

Por solicitação explícita, modelo/preços anteriores do GPT-4.1 foram comentados
no próprio arquivo, e os valores novos inseridos imediatamente abaixo. No corte,
os comentários de preços começavam na linha 48; o modelo anterior na linha 95
e o novo ativo na linha 98. Confirmar as linhas antes de citá-las em novo relatório.
Demais campos, documentos, projeto e Vector Store foram preservados; a escrita
foi comparada com o original, validada pelo carregador e manteve ACL privada.
O controle Windows não alterou a configuração.

`openai` contém preços de tokens/orçamento; `knowledge.prices` contém File Search
e armazenamento. São conjuntos distintos. O nome do modelo é enviado a partir
da configuração, sem nome fixo no transporte. Uma troca exige também preços
corretos e reinício: `app.main` carrega a configuração na inicialização.

O cadastro inicial em `scripts/setup_openai_i4.py` ainda tem mini como padrão.
Isso não sobrescreve uma seção já cadastrada nem determina o modelo do piloto atual.
O verificador exige igualdade literal entre `response.model` e o modelo configurado.
Aliases que retornem outro identificador podem ser recusados. Um possível campo
`knowledge.response_model` foi apenas sugerido em uma análise; **não foi implementado**.

## 5. Arquitetura e responsabilidades a revisar

- `app/ai/configuration.py`: consentimento, documentos/hash, configuração imutável
  e validação do nome do modelo. Aceita ponto, hífen e sublinhado nos nomes.
- `app/ai/openai_http.py`: Responses + File Search, endpoints fixos, TLS, sem retry
  automático ou redirecionamento; `store=false`, uma chamada de ferramenta,
  resultados limitados, filtro por geração e saída estruturada.
- O esquema de cada chamada restringe `file_id` ao manifesto verificado. O limite
  vigente de `quote` é 1.000 caracteres; a tentativa de 160 foi abandonada.
- `app/services/knowledge.py`: sincronização, manifesto atual, citações, renderização
  e verificação antes da entrega. `citation_text` normaliza espaços antes de remover
  marcadores pareados de negrito; palavras, números e operadores devem permanecer.
- Citação precisa existir em um resultado recuperado do mesmo arquivo permitido.
  Não há busca aproximada, reconstrução de citação omitindo palavras, substituição
  automática de arquivo ou recuperação por índice documental local.
- Recusas agora persistem um `validation_error` fixo, como `quote_not_found`,
  `section_not_found` ou `claim_fields_invalid`, sem texto bruto no diagnóstico.
- `app/ai/runtime.py`: relê as fontes Drive para conferir atualidade. A leitura
  integral no Drive não é novo upload nem envio integral ao modelo em cada pergunta.
- `app/ai/runtime_budget.py`: intenções duráveis, consumo, armazenamento, reserva
  de custo, recuperação de incerteza e reconciliação. Custos antigos preservam
  suas premissas registradas. O cálculo não presume franquia gratuita de armazenamento.
- `app/core/orchestrator.py` e `app/channels/telegram.py`: permissões Python,
  deduplicação, offset, recibos, resposta segura e revalidação da fonte na entrega.
- Banco operacional canônico: `data/i2.sqlite3`, **esquema 3**. Houve backup privado
  consistente anterior à migração 2→3 em `data/backups/`.

O controle não substitui o motor: ele usa o mesmo `app.main`, configuração, banco,
segredos e autorizações. Não é serviço Windows, tarefa agendada ou autostart.

## 6. Histórico mínimo necessário para não repetir conclusões incorretas

1. O cadastro falhava porque o validador compartilhado de IDs rejeitava o ponto
   de `gpt-4.1-mini-2025-04-14`. Foi criado validador de modelo separado, com
   regressão do fluxo real de cadastro em arquivos temporários.
2. Os dois documentos reais foram sincronizados e indexados após G3. A primeira
   tentativa de rede falhou antes de chamar OpenAI; a seguinte passou.
3. Ensaios reais provocaram ajustes de formulação semântica, uma busca por pergunta
   e citações contínuas. Casos de horário/paráfrase da piscina, lacuna, mandato da
   Convenção e contextos de visitantes tiveram sucessos documentados.
4. O caso exploratório `visitor_conflict` não demonstrou contradição inequívoca:
   tratava de contextos diferentes. Sua falha não foi reclassificada como sucesso.
5. As perguntas sobre bicicleta e apartamento 62 revelaram rejeição de negrito
   atravessando linhas. Os testes reproduziram o defeito; inverter a ordem da
   normalização corrigiu esse caso, com retestes reais aprovados.
6. **A bicicleta voltou a falhar no Telegram.** Reproduções reais mostraram
   citações montadas, omissões intermediárias e IDs inventados. O validador
   estrito bloqueava corretamente esses conteúdos; a correção de layout não
   resolvia a confiabilidade da geração.
7. Instruções mais específicas não estabilizaram o mini nas amostras. O esquema
   passou a restringir IDs ao manifesto. O limite experimental de 160 caracteres
   causou truncamentos e foi revertido para 1.000. Tentativas reprovadas permaneceram
   nas evidências, inclusive depois de testes isolados bem-sucedidos.
8. Foi avaliado e configurado GPT-4.1 completo com preços correspondentes.
   Duas variantes da bicicleta e piscina passaram em consultas locais reais.
   **Isso não se sustentou no reteste Telegram:** o responsável respondeu
   “Retornou indisponibilidade novamente”. O recibo de 11/11 às **14:37:23 UTC**
   registra `knowledge_evidence_invalid`, entrega `sent` e **`quote_not_found`**.
   Essa falha é confirmada, não uma confirmação humana ainda desconhecida.
9. Depois, o responsável pediu o bloco de outro modelo e autorizou editar
   `config.yaml`, comentando os valores anteriores. Foi configurado GPT-4o.
   Não foi realizado um reteste semântico identificado para aprovar essa configuração.
10. Por solicitação posterior, foi criado e validado o controle Windows.
    Nenhuma evolução para I5 ocorreu.

As respostas brutas dos updates Telegram recusados não foram preservadas.
Não atribuir retrospectivamente a cada update a mesma causa exata dos ensaios
reproduzidos. Os relatórios dos casos fixos têm diagnósticos controlados; não
contêm todas as respostas brutas dos participantes.

## 7. Evidências e limites das validações

Resultado offline vigente: **338 testes aprovados**, zero falhas/erros/ignorados.
Inclui 70 testes em `test_knowledge`, 11 em `test_desktop` e dois novos testes de
integração do controle em `test_telegram`. Esses grupos não devem ser somados
novamente ao total. Inicializações dos quatro exemplos e demos I1/I2/I4 passaram.
Não houve nova instalação de dependências. `pip_check: passed` consta do registro
de aceite; não foi reexecutado para produzir este handoff.

No corte, hashes atuais de código/scripts/testes conferiam com `i4-tests.json`.
O `.cmd` e o instalador `.ps1`, fora do conjunto Python/SQL do verificador, têm
hashes adicionais em `windows-control-live.json`. Testes offline usam fixtures,
rede bloqueada e bancos temporários: não comprovam semântica da API real.

O banco foi inspecionado em somente leitura: integridade e chaves estrangeiras
válidas; **zero chamadas OpenAI em `running`/`uncertain` no corte**. O total de
consumo medido convertido pelas premissas registradas era **R$ 1,127696**.
Isso é um snapshot local estimado, não reconciliação da fatura nem garantia de teto.
Desligar o bot não apaga a Vector Store nem encerra custos de armazenamento.

A última ocorrência Telegram no corte foi `telegram_update_unsupported`,
descartada em **15:20:29 UTC**. Não se conhece o texto/tipo original apenas por
esse código; isso não é prova de sucesso ou falha da bicicleta no GPT-4o.

Evidências prioritárias:

- [Autorizações](../evidencias/i4-authorizations.json) e [aceite](../evidencias/i4-acceptance.json).
- [Testes atuais](../evidencias/i4-tests.json), [saída detalhada](../evidencias/i4-unittest.txt)
  e [comparação por hashes](../evidencias/i4-change-review.json).
- [Sincronização real](../evidencias/i4-sync-20261110T174455399413Z.json).
- [Casos reais e histórico](../evidencias/i4-live-validation.json).
- [Correção do cadastro](../evidencias/i4-model-validation-fix.json).
- [Correção de layout](../evidencias/i4-multiline-citation-fix.json).
- [Ajustes de qualidade/modelo](../evidencias/i4-model-quality-fix.json).
- [Controle Windows](../evidencias/windows-control-live.json) e
  [primeiro probe preservado](../evidencias/windows-control-live-first-probe.json).
- [Snapshot deste handoff](../evidencias/handoff-auditoria-i4-20261111-snapshot.json).

## 8. Controle Windows entregue

Atalho na área de trabalho: **Alfredo - Ligar e desligar.lnk**. Aponta para
`.venv\Scripts\pythonw.exe -B scripts\alfredo_control.py`, com caminhos absolutos
e diretório de trabalho do projeto. Alternativa: `Alfredo.cmd` na raiz.

Arquivos principais: `app/desktop/control.py`, `app/desktop/panel.py`,
`scripts/alfredo_control.py`, `scripts/install_alfredo_shortcut.ps1` e
[manual](../controle-windows.md). `app.main` recebeu sinal de parada e observador
opcionais; `TelegramChannel` emite prontidão, indisponibilidade e recuperação.

ATIVO, em verde, depende de prontidão Telegram, não só da existência de uma thread.
INATIVO é vermelho. Há estados intermediários e estado distinto para instância
externa ou trava não verificável. O controle não mata processos desconhecidos.
Uma segunda abertura restaura o painel. Minimizar mantém o bot ligado; fechar
solicita parada cooperativa e aguarda o fim das operações. Ctrl+L/Ctrl+D usam os
mesmos comandos de ligar/desligar.

A validação Windows observou ATIVO, DESLIGANDO, janela encerrada, reabertura,
INATIVO e retomada. Verificou trava livre após desligar e ocupada após ligar.
Não houve force kill. O controle foi deixado aberto e ATIVO.

**Limite da evidência visual:** captura WGC falhou com `window capture timed out`;
clique por coordenadas falhou com `coordinate input geometry unavailable`.
Foram usados a árvore de acessibilidade, Alt+F4 e Ctrl+L/Ctrl+D. Não alegar
screenshots aprovados ou cliques reais de mouse nos dois botões. A árvore expôs
os botões sem nomes textuais. O layout foi conferido pelo Tk no contexto normal
Windows: conteúdo solicitado 396×402, mínimo 480×460. A verificação no sandbox
não carregava Tcl; o processo Windows normal funcionou, sem instalar Tcl novo.

O primeiro probe de outro controlador esperava inatividade, mas encontrou o
painel já ativo e foi bloqueado como execução externa. Esse registro foi
preservado; o relatório final distingue esse probe dos testes posteriores.

## 9. Divergências documentais a tratar explicitamente na auditoria

- `i4-acceptance.json` ainda informa `complete_and_real_OpenAI_validated`,
  `current_model: gpt-4.1-2025-04-14` e confirmação pós-ajuste pendente.
  O modelo no arquivo atual é GPT-4o; o reteste pós-ajuste do GPT-4.1 foi
  efetivamente reprovado pelo responsável e pelo recibo.
- `i4-model-quality-fix.json` e `i4-live-validation.json` preservam um snapshot
  anterior à confirmação de falha. Não interpretar `pending` como ausência de teste.
- `i4-telegram-live.json` registra sucessos históricos; não é prova de aceite
  semântico com a configuração atual.
- README/relatório/implementação têm histórico de ajustes e descrições em tempos
  diferentes. Declarações de “correção” não substituem a evidência de recorrência.

Essas divergências foram registradas aqui, **sem reescrever silenciosamente as
evidências para parecer que o problema foi resolvido**. Não aprovar I4 por contar
testes ou pelo controle Windows funcionar.

## 10. Próxima ação concreta e entrega esperada da auditoria

Primeiro reconciliar o modelo/preços atuais, os snapshots e a classificação
da falha recorrente. Depois revisar, em código, o contrato geração → evidências
→ entrega, cobertura real dos testes, orçamento/recuperação e ciclo de vida Windows.
Examinar especialmente a diferença entre citação estruturalmente válida,
interpretação semanticamente correta e sucesso isolado em um ensaio.

Entregar achados por severidade com arquivo/linha, evidência, impacto e ajuste
mínimo proposto; separar fatos comprovados de hipóteses. Informar critérios
`passed`, `failed`, `blocked` ou `not_run` quando aplicáveis e quais verificações
reais seriam necessárias em uma execução posterior. Não implementar, não criar
regras de resposta por assunto, não marcar I4 aceita e não iniciar I5.
