# Implementação e operação I4 — conhecimento documental

A I5 local posterior está documentada em [implementação I5](implementacao-i5.md).
O bot e o painel permanecem operando na I4; escrita Google não foi ativada.
O verificador vigente é `scripts/verify_i5.py`, com evidências I4 preservadas.

Data: 10/11/2026. Conhecimento técnico do Vert2Go.
Referências: PRD v1.2.0, especificação Alfredo v0.1.8, plano v0.1.1
e PLAN I4 atualizado aprovado na sessão de execução.

## Estado e autoridade

O responsável aceitou formalmente a I3 e autorizou G3 nesta sessão: transferência
exclusiva do Regulamento Interno e da Convenção identificados na I3, indexação e
consultas de teste, orçamento estimado de R$ 30/mês e alerta em R$ 24.
Registro: [autorizações I4](evidencias/i4-authorizations.json).
Essa autorização não inclui exclusões, escrita Google ou operações da I5/I6.

A implementação local fornece os componentes abaixo. Testes offline não
comprovam acesso OpenAI, qualidade das respostas reais ou recebimento Telegram.
O estado consolidado é [relatorio-i4.md](relatorio-i4.md); a decisão formal fica
em [i4-acceptance.json](evidencias/i4-acceptance.json).

## Responsabilidades e fechamento preventivo

- `app/ai/configuration.py`: declaração imutável, hash de cada cópia autorizada,
  projeto/modelo/limites/preços e consentimentos separados de Telegram.
- `app/config/schema.py`: carregador canônico aceita OpenAI estritamente validada
  junto de Telegram/OAuth. Uma chave presente não ativa o uso da API.
- `app/integrations/google_auth.py`: renovação preserva a chave OpenAI; foi retirada
  a proibição antiga dessa coexistência. Não existe carregador permissivo paralelo.
- `app/ai/openai_http.py`: REST sobre `requests` já instalado. Endpoints fixos,
  TLS, sem redirecionamentos, DELETE, URL arbitrária ou retentativa automática.
  Não foi instalada dependência nova.
- `app/ai/runtime_budget.py`: uso real e reservas persistidas, custo de tokens,
  ferramenta e armazenamento, bloqueio de resultado incerto e recuperação.
  `LocalBudget.record_simulated` permanece exclusivamente para fixtures antigas.
- `app/services/knowledge.py`: sincronização, versão ativa, evidências e resposta.
  Orientações administrativas continuam separadas e fora da Vector Store.
- `003_knowledge.sql`: migração opcional 2→3. Aberturas anteriores continuam
  reconhecidas; inicialização sem I4 mantém o esquema 2 quando ele já existe.
  Antes de migrar um banco existente, há backup SQLite consistente e privado,
  protegido antes da gravação dos dados e sob a trava de instância.
- `app/core/orchestrator.py`, `app/channels/telegram.py` e `app/main.py`:
  ação documental com autorização Python e ativação explícita. Comandos anteriores,
  deduplicação, offset e entrega incerta permanecem no caminho canônico.
- Verificadores I1/I2/I3 encaminham para `verify_i4.py`, preservando os relatórios
  históricos. A inspeção Telegram reconhece os esquemas 2 e 3.

As especificações do comportamento do produto ficam em
[agentes/alfredo-i4.md](agentes/alfredo-i4.md). O AGENTS.md não foi alterado.

## Cadastro e configuração

`setup_openai_i4.py --enroll` pede o ID não secreto do projeto e a chave em terminal
com entrada oculta. Não aceita chave por argumento, variável de ambiente ou chat.
Entrada oculta indisponível causa erro, sem fallback para eco. Uma chave já
cadastrada não é sobrescrita. A escrita usa ACL privada, trava e substituição
atômica com verificação de alteração concorrente.

O cadastro resolve os dois documentos por referência de recurso e hash registrados
na leitura real I3, comparados às cópias autorizadas locais. Não escolhe arquivos por
nome, pasta ou busca indiscriminada. Mudanças de hash exigem nova autorização.

`config.knowledge.example.yaml` é inteiramente fictício e vem desabilitado.
Não deve substituir `config.yaml`. O cadastro real acrescenta a seção `knowledge`
e `knowledge.read`, preserva usuários/Google/Telegram e atualiza as premissas OpenAI.

O modelo inicial configurado pelo cadastro é `gpt-4.1-mini-2025-04-14`, cujo suporte
a Responses, File Search e saída estruturada foi conferido na documentação oficial.
O cliente usa o modelo da configuração; não há modelo fixo no transporte.

Em 11/11/2026, após novas recusas reais por citações montadas/IDs inventados,
o piloto existente foi ajustado para `gpt-4.1-2025-04-14`, mantendo projeto,
documentos, Vector Store e orçamento. Os preços de tokens foram atualizados para
US$ 2/8 por milhão de entrada/saída; entrada em cache continua contabilizada de
forma conservadora pelo preço integral. Isso aumenta o custo unitário em relação
ao mini. O alerta R$ 24 e o orçamento R$ 30 não foram ampliados. As amostras de
qualidade e suas limitações estão no relatório; não são garantia de acerto geral.
O padrão histórico do cadastro permanece mini; o estado deste piloto é o modelo
explicitamente registrado na configuração vigente.

Correção de 10/11/2026: o validador específico de modelo aceita letras, números,
ponto, hífen e sublinhado, até 200 caracteres e com início alfanumérico. Ele
preserva o identificador integral, incluindo `gpt-4.1-mini-2025-04-14`.
Os validadores de Project ID e Vector Store continuam separados e não aceitam ponto.
Espaços, URLs, barras e caracteres de controle permanecem rejeitados.

O erro anterior `knowledge_configuration_invalid` era provocado pela reutilização
do validador de IDs no modelo padrão. A falha ocorria antes da gravação da
configuração e da solicitação da chave. A cobertura agora inclui `configure()`
com Project ID fictício válido, o modelo padrão e persistência atômica em arquivo
temporário, além da rejeição de entradas inválidas sem gravação parcial.

Preços de referência consultados em 10/11/2026: entrada US$ 0,40/milhão de tokens,
saída US$ 1,60/milhão, File Search US$ 0,0025/chamada e armazenamento
US$ 0,10/GB/dia. Câmbio é premissa configurável, não cotação de mercado.
As premissas precisam ser revistas se o modelo ou as condições do serviço mudarem.

## Fluxo de sincronização

`knowledge_i4.py` exige uma operação e o banco escolhido explicitamente por
`--database`. `sync`, `query` e `reconcile` exigem `--allow-live-openai` e G3
persistido. O modo `status` não lê segredos, cria/migra banco ou usa rede.

Antes do primeiro upload, todas as fontes são lidas pela integração I3 e comparadas
com seus hashes aprovados. O primeiro fluxo suporta os Markdown/textos UTF-8 do
piloto; PDF, outros formatos e OCR não são ativados por conveniência.

Uma Vector Store exclusiva recebe referência do piloto e do projeto. Upload e
associação possuem intenções duráveis distintas. São verificadas conclusão e
atributos da indexação, e a fonte é relida antes de publicar `synced`. A sincronização
concluída persiste o ID não secreto da Vector Store na configuração privada.

Conteúdo original fica em memória durante o processamento; SQLite guarda
metadados, estados e respostas necessárias à retomada, sem índice de pesquisa.
As consultas filtram a geração documental autorizada e validam os IDs retornados.
Uma versão antiga, desconhecida ou fora do manifesto invalida a resposta.

Fonte alterada fica bloqueada até nova autorização e sincronização manual.
Remover um arquivo da Vector Store possui consistência eventual; a exclusão não
substitui os controles de versão. Nenhuma exclusão foi implementada ou autorizada.

## Consulta e evidências

`query` é uma consulta local operada pelo responsável, com `--question` e um
`--actor-id` já cadastrado ou `--role resident/manager`. Não envia Telegram.
Seleção por papel nesse script não permite ao texto de uma mensagem mudar de perfil.

A chamada Responses usa apenas File Search, uma chamada de ferramenta no máximo,
resultados limitados e formato estruturado. Não envia histórico completo, IDs Telegram,
unidade, células, eventos, segredos ou o conjunto de orientações administrativas.
O esquema de saída limita `file_id` aos IDs do manifesto autorizado já verificado
e limita cada citação gerada aos 1.000 caracteres já aceitos pelo validador.
Isso restringe referências; não seleciona uma resposta por assunto ou palavra-chave.
A busca e a interpretação permanecem semânticas, realizadas pela IA/File Search.
O Python verifica autorização, integridade e evidências, sem índice local ou
mapeamento de perguntas para respostas fixas.
`store=false` evita persistência da resposta para recuperação pela API; isso não
significa ausência de retenção pelo provedor nem elimina os arquivos indexados.

O documento integral é transferido na sincronização da versão autorizada, não
a cada pergunta. Cada consulta envia pergunta/instruções e usa os trechos
recuperados por File Search. A aplicação relê integralmente as duas fontes no
Drive antes/depois da geração e antes de entregar uma resposta com evidência
no Telegram, para conferir versão/hash; essa leitura não faz novo upload OpenAI.

O prompt reformula a pergunta coloquial por recurso/regra e reúne as consultas
em uma única chamada File Search. Não há uma segunda busca automática.

Cada afirmação precisa apresentar arquivo permitido e trecho contínuo presente nos
resultados recuperados. A comparação aceita igualdade literal ou normalização
limitada de espaços/quebras de linha e pares de marcadores de negrito Markdown.
Os espaços são normalizados antes do tratamento de negrito, inclusive quando
os marcadores envolvem texto quebrado em mais de uma linha do arquivo-fonte.
Não altera palavras, números, acentos, pontuação ou operadores matemáticos.
O recibo registra `quote_match` como `exact` ou `layout_normalized`. Citações vazias,
apenas formatação, montagens de trechos separados e números alterados são recusados.
Seção só é exibida se encontrada no trecho; páginas não são
inventadas. Esse controle valida referências e trechos, não constitui uma prova
determinística da correção semântica da interpretação do modelo. A validação real
de perguntas e paráfrases permanece parte obrigatória do aceite.

Sem evidência, divergência, resposta incompleta ou referência inválida, o usuário
recebe uma limitação segura. O consumo já ocorrido é registrado mesmo quando a
resposta é recusada. Mudanças da fonte durante a geração suprimem a resposta.

O prompt prioriza a regra específica suficiente e citações curtas contínuas,
sem omitir frases intermediárias. A validação não corrige citações montadas,
não procura correspondência aproximada e não troca o arquivo escolhido pelo modelo.
Recusas guardam `validation_error` com motivo interno fixo, como `quote_not_found`
ou `section_not_found`, no resultado persistido e no log. Nenhum texto da pergunta,
citação ou resposta bruta é acrescentado ao diagnóstico operacional. O canal
continua mostrando apenas o aviso seguro; os casos fixos do verificador real
registram separadamente o diagnóstico controlado de citações.

## Telegram e memória administrativa

O atalho Windows oferece ativação e parada do mesmo fluxo, com estados visíveis
e sem depender do VS Code. Procedimento em [controle-windows.md](controle-windows.md).
Minimizar mantém o agente ligado; fechar o painel solicita parada cooperativa.

A ativação exige simultaneamente `--telegram`, `--allow-live-telegram`, `--knowledge`,
`--allow-live-openai` e autorização documental Telegram na configuração.
Sem esses requisitos o modo anterior permanece disponível e não chama OpenAI.
A ajuda do modo I4 informa consulta documental e limites de operações.

O motor verifica `knowledge.read` e a identidade antes de consultar fontes.
Perguntas livres passam pelo novo fluxo; os comandos anteriores são preservados.
O resultado é limitado a 4.096 unidades UTF-16. Reentrega usa a resposta persistida
sem nova geração; permissões e atualidade das fontes continuam verificadas no motor.
Entrega Telegram incerta continua sem reenvio automático.
Antes de enviar uma resposta documental pendente, o canal revalida permissão,
habilitação e fonte. Mudança da fonte ou retomada sem I4 substituem o conteúdo
por aviso neutro, sem nova chamada ao modelo.

A composição administrativa preparada para a I5 usa `OperationalMemory.find`,
com filtros por assunto, público e vigência. Conflito ou verificação documental
ausente bloqueiam a composição. O fluxo I4 real não envia essas orientações ao modelo
nem ativa cadastro/correção/cancelamento via Telegram.

## Custos, interrupção e reconciliação

Cada operação externa tem intenção e estimativa persistidas antes da chamada.
Não se mantém uma transação SQLite aberta durante a rede. Chamada em execução
no reinício passa a incerta. Uma incerteza bloqueia novas despesas inclusive
após mudança de mês, até reconciliação explícita pelo responsável.

O armazenamento é estimado conservadoramente sem presumir franquia gratuita,
incluindo o intervalo em que o programa esteve parado. O cálculo usa divisor
decimal de bytes, conservador em relação ao GB binário da cobrança oficial.
Períodos entre meses são separados no fuso America/Sao_Paulo. A associação
assíncrona reserva a capacidade máxima configurada; o uso reportado é conferido.
Suspender consultas ou desligar o notebook não encerra custos de armazenamento.

Reconciliação exige `--call-id` e `--confirm-reconciliation`. Para resposta incerta,
os tokens e buscas precisam ser informados a partir de medição do provedor; não
estimá-los silenciosamente como zero. A resposta original não é gerada outra vez.
Para recurso aceito, `--remote-id` é conferido por API contra a referência do piloto,
nome técnico do upload ou associação esperada. Sem comprovação, o bloqueio permanece.
Se o responsável verificar externamente que um recurso não foi criado, pode registrar
`--verified-not-created` junto da confirmação. A decisão fica auditada e permite
nova tentativa somente no próximo `sync` manual. Isso não libera replay de resposta
incerta; para respostas, a medição de consumo continua obrigatória.

Não reduzir esquema 3 para 2. Para desativar I4, omitir sua ativação no processo
manual e desabilitar a seção de conhecimento, preservando metadados e trilhas.
Restauração de backup exige processo parado e avaliação do estado externo;
restaurar SQLite sozinho não desfaz upload, custo ou resposta já enviada.

Retenção fornece elegibilidade para respostas concluídas após 30 dias e preserva
chamadas incertas. Não existe limpeza ou exclusão automática.

## Validação local

O bloco abaixo usa apenas fixtures e bancos temporários; não lê credenciais reais.

```powershell
Set-Location -LiteralPath 'D:\MeusArquivos\Fs\Projetos\Vert2Go'
.\.venv\Scripts\python.exe scripts/verify_i4.py
if ($LASTEXITCODE -ne 0) { throw 'Verificação I4 reprovada. Consulte docs/evidencias/i4-unittest.txt.' }
.\.venv\Scripts\python.exe -m examples.i4_demo
if ($LASTEXITCODE -ne 0) { throw 'Demonstração I4 reprovada.' }
```

O verificador registra resultados individuais, hashes de fontes, demonstrações,
inicializações locais e integridade das fontes normativas protegidas. Ensaios reais
e aceite humano são registrados separadamente.

## Validação real de 10/11/2026

Cadastro e chave foram confirmados localmente. A migração do banco operacional
`data/i2.sqlite3` de 2 para 3 teve backup privado anterior; o estado de negócio
foi preservado. Os dois documentos autorizados foram lidos no Drive, comparados
por hash, enviados e confirmados como indexados. O ID não secreto da Vector Store
foi persistido pelo caminho canônico, preservando as demais configurações.

`scripts/validate_knowledge_i4.py` executa casos fixos e finitos pelo mesmo serviço,
com banco explícito, trava, G3 e autorização de rede. Não envia Telegram nem escreve
no Google. Registra consumo, resultado e diagnóstico limitado de busca/citação;
não grava respostas brutas do provedor nem mensagens arbitrárias dos participantes.
Os ensaios anteriores reprovados foram preservados junto aos retestes aprovados.
Os casos `bicycle_parking` e `apartment_62_spaces` reproduzem as duas perguntas
informadas pelo responsável após a retomada de 11/11/2026.

O teste exploratório `visitor_conflict` não comprovou contradição: as regras
tratavam de contextos distintos. Sua citação montada foi recusada. O caso válido
`visitor_scope` compara esses contextos e passou com trechos verificáveis; não
foi fabricada divergência documental para obter um resultado esperado.

O processo Telegram manual foi iniciado com I4. A resposta documental do morador
teve envio aceito pela API e recebimento com fonte confirmado pelo responsável.
Em 11/11/2026, o responsável também confirmou resposta correta no chat do síndico.
O recibo desse perfil registra envio aceito, fonte autorizada no Regulamento
Interno e correspondência com a resposta documental persistida. O teste nas duas
contas está concluído; permanece pendente o aceite formal da I4. Consultar
[relatório](relatorio-i4.md) e
[evidência Telegram](evidencias/i4-telegram-live.json) para o estado final.
Não há serviço Windows, inicialização automática ou garantia de execução contínua.

## Fontes técnicas consultadas

- [Modelo e recursos](https://developers.openai.com/api/docs/models/gpt-4.1-mini)
- [Modelo vigente do piloto](https://developers.openai.com/api/docs/models/gpt-4.1)
- [Restrições de saída estruturada](https://developers.openai.com/api/docs/guides/structured-outputs)
- [File Search](https://developers.openai.com/api/docs/guides/tools-file-search)
- [Vector Stores e sincronização](https://developers.openai.com/api/docs/guides/retrieval#vector-stores)
- [Preços](https://developers.openai.com/api/docs/pricing)
