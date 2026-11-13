# Relatório I4 — aceite formal do piloto registrado com limitações

Nota posterior de implementação: a I5 foi implementada localmente por autorização
expressa em 11/11/2026, sem ativação real. Ver [relatório I5](relatorio-i5.md).
As menções abaixo a I5 não iniciada descrevem o fechamento histórico da I4.

Aceite posterior: em 11/11/2026, o responsável aceitou formalmente a I4 para o
piloto, com as limitações do fechamento. Prevalece o registro em
[i4-acceptance.json](evidencias/i4-acceptance.json). As pendências de aceite no
histórico abaixo foram encerradas; G4 não foi concedido e I5 não foi iniciada.

Atualização de fechamento: os quatro retestes posteriores no GPT-4o foram
confirmados nos recibos e pelo responsável. Para estado atual e limitações,
prevalece [fechamento-i4-2026-11-11.md](fechamento-i4-2026-11-11.md).
As etapas abaixo preservam o histórico anterior a esse fechamento.

Data: 10/11/2026. Atualizado em 11/11/2026. Responsável: Codex.
Escopo: executar o PLAN I4 aprovado, respeitando G3 e autorizações por operação.

## Resultado vigente

**Implementação e consultas OpenAI reais validadas. I4 ainda não aceita integralmente.**

O responsável aceitou formalmente a I3 e autorizou G3 para transferir exclusivamente
o Regulamento Interno e a Convenção identificados na I3, indexá-los e realizar
consultas de teste no orçamento estimado de R$ 30/mês, alerta em R$ 24. Também
autorizou a consulta documental no bot experimental e testes nas duas contas.
As decisões foram registradas, sem presumir autorização para I5/I6 ou exclusões.

Depois da entrega local e da correção do cadastro, o responsável confirmou a chave
registrada e solicitou continuidade real. Projeto/chave foram validados localmente;
somente os dois documentos autorizados foram transferidos e indexados. As consultas
reais passaram com referências verificáveis. O processo manual Telegram foi
iniciado com I4: a resposta documental do morador foi aceita pela API e o responsável
confirmou o recebimento com fonte. Em 11/11/2026, o responsável confirmou resposta
correta também no chat do síndico. O recibo desse perfil comprova envio aceito
e fonte autorizada no Regulamento Interno. A validação real nas duas contas
dos ensaios previstos está concluída. Duas consultas adicionais de 11/11 foram
recusadas pela validação de citações após retomada do bot, conforme ocorrência
abaixo. O responsável informou as perguntas e autorizou a correção, que passou
nos testes locais e nos dois retestes OpenAI reais. O bot foi reiniciado com a
correção. O aceite formal da I4 permanece pendente.

## Implementação

Foi preservada a arquitetura Drive → Vector Stores + File Search, sem índice local.
A sequência executada preparou configuração/segredos, persistência e orçamento
antes de integrar o fluxo documental ao canal existente.

Há validação estrita de G3, documentos/hash, projeto e limites; cadastro oculto
com escrita privada atômica; migração opcional 2→3 e backup privado anterior;
sincronização manual com acompanhamento de upload/associação/indexação;
consulta natural com resposta estruturada, trechos e fontes verificáveis;
controle de consumo real estimado e armazenamento; estados incertos duráveis,
reconciliação e deduplicação sem repetição automática de despesas.

O transporte usa `requests` já instalado, endpoints permitidos, TLS e nenhum
redirecionamento ou retry automático. O modelo inicial do cadastro é parametrizado
como `gpt-4.1-mini-2025-04-14`, com suporte e preços conferidos nas fontes oficiais.
Sua adequação foi conferida nos casos reais discriminados abaixo, sem trocar modelo.

O orçamento não presume franquia gratuita de armazenamento e contabiliza tempo
com o programa parado. O bloqueio local estimado não é garantia de teto de fatura.

A verificação Python exige trecho contínuo presente no resultado e arquivo permitido,
aceitando apenas normalização limitada de layout Markdown e espaços;
não prova deterministicamente que a interpretação semântica do modelo é correta.
Essa limitação está documentada e faz parte da revisão humana do aceite.

## Fechamento preventivo

As proibições antigas de coexistência OpenAI foram substituídas nos carregadores
canônicos Telegram e Google. A renovação OAuth foi testada preservando os outros
segredos. O fluxo anterior continua disponível sem ativação da I4.

A ação documental foi integrada ao orquestrador e ao canal existentes, preservando
autorização, comandos, limite de mensagens, offset, recibos e entrega incerta.
Uma resposta pendente perde seu conteúdo documental se a fonte mudar ou a I4
estiver desabilitada na retomada. Isso não faz nova geração OpenAI.

Os verificadores antigos encaminham à I4 e preservam seus artefatos históricos.
A inspeção Telegram reconhece esquema 3. A elegibilidade de retenção inclui
respostas documentais concluídas, preservando incertezas e sem exclusão automática.

Orientações administrativas permanecem separadas, com preparação/testes de
composição por assunto, público e vigência. Não houve ativação real de escrita
administrativa nem envio dessas orientações ao modelo.

## Validação

`scripts/verify_i4.py`: **325 testes aprovados**, sendo 255 da regressão anterior
e 70 específicos da I4; zero falhas, erros ou testes ignorados.
Rede bloqueada, credenciais fictícias e bancos temporários nos testes.

Também passaram as demonstrações I1/I2/I4, a inicialização finita dos quatro
exemplos YAML e `pip check`. Nenhuma dependência nova foi instalada.
Os hashes de código/scripts/testes conferem com a evidência final.
As fontes normativas protegidas permaneceram íntegras.

Foram cobertos: paráfrase com evidência capturada, lacuna, conflito, citação
inventada, arquivo não permitido, geração antiga, fonte alterada antes/durante a
resposta e antes do envio, indexação incompleta, timeout depois de possível
upload, reinício, falta de medição, bloqueio financeiro, armazenamento entre meses,
reconciliação, público/vigência, coexistência de segredos e rollback de migração.
Os cenários semânticos capturados não são apresentados como T03/T04 reais.

## Correção do cadastro — nome do modelo

Em 10/11/2026, o responsável relatou `knowledge_configuration_invalid` depois
de informar um Project ID válido. O cadastro definia `gpt-4.1-mini-2025-04-14`,
mas a validação compartilhada com IDs não permitia o ponto desse nome. A falha
ocorria em `_parse_config(raw)`, antes de gravar configuração ou solicitar a chave.

A correção introduziu `model_name` em `app/ai/configuration.py`, mantendo
inalterados o modelo padrão, o script de cadastro e as restrições dos IDs de projeto
e Vector Store. O validador específico admite ponto e preserva o nome completo,
sem aceitar espaços, URLs, barras, caracteres de controle ou tamanho excessivo.

Foram acrescentados cinco testes de regressão. O caminho `configure()` agora é
executado com dados fictícios, entrada de Project ID simulada e persistência
atômica em arquivo temporário, verificando preservação de Google, usuários, canal
e arquivo fictício de segredos. Entradas inválidas são rejeitadas antes da trava
ou de gravação parcial. Os novos testes reproduziram o defeito antes da correção
e passaram depois dela. A suíte anterior usava `model-fictional`, sem ponto,
e não cobria a configuração gerada pelo cadastro com o modelo padrão.

A evidência original de 308 testes foi preservada em
[i4-tests-before-model-validation-fix.json](evidencias/i4-tests-before-model-validation-fix.json).
A correção e seus resultados estão em
[i4-model-validation-fix.json](evidencias/i4-model-validation-fix.json).
Nenhuma operação Git, chamada externa, leitura de segredo real ou alteração de
configuração particular foi realizada naquela correção isolada. A continuidade
real autorizada ocorreu depois do cadastro, conforme a seção seguinte.

## Continuidade real autorizada

O banco operacional foi migrado de esquema 2 para 3 com backup privado consistente
anterior. O primeiro acesso à rede foi bloqueado antes de qualquer chamada OpenAI;
a execução autorizada com rede disponível sincronizou os dois documentos, com
14 requisições OpenAI para criação, upload, associação e acompanhamento. As fontes
foram conferidas por hash antes e depois da indexação, sem índice documental local.

Casos reais aprovados: horário da piscina; paráfrase sobre mergulhar às onze da
noite; ausência de regra sobre cor de pulseiras; mandato de dois anos/reeleição
na Convenção; comparação dos contextos de visitantes da piscina e convidados do
salão. Evidências individuais preservam consumo, busca, trechos e referências.
Resumo em [i4-live-validation.json](evidencias/i4-live-validation.json).

Os ensaios revelaram buscas coloquiais pouco precisas, tentativa extra de ferramenta
e rejeição de citações corretas com negrito/quebras de linha. O prompt agora
reformula por recurso/regra e pede uma única busca com citações curtas contínuas.
A comparação aceita somente diferenças de layout, registra o modo de correspondência
e continua rejeitando números alterados, conteúdo vazio e montagens de trechos.
Quatro novos testes cobrem esses limites; modelo, documentos e arquitetura foram
preservados. Tentativas reprovadas permanecem nas evidências, sem custos ocultos.

O consumo medido acumulado, convertido pelas premissas configuradas, foi de
**R$ 1,044485** no fechamento dos ensaios adicionais de 11/11/2026, abaixo do alerta de R$ 24
e do orçamento estimado de R$ 30/mês. Não havia operação OpenAI incerta ou em
execução. Armazenamento continua existindo e pode gerar custo com o bot parado;
esse valor não é uma reconciliação da fatura do provedor.

O caso exploratório de conflito de visitantes não demonstrou contradição inequívoca:
as cláusulas pertencem a contextos distintos. Uma citação montada foi corretamente
recusada; o reteste de comparação contextual passou. O tratamento de conflito
permanece coberto offline, sem alegar conflito real inexistente.

No Telegram, uma tentativa anterior do morador recebeu indisponibilidade por
citação inválida; `/ajuda` foi entregue e uma nova consulta recebeu horário da
piscina com fonte válida. O responsável confirmou essa resposta com fonte na conta
de morador. O recibo do perfil de síndico, de 10/11/2026 às 22:45 UTC, registra
`knowledge_answer`, entrega `sent`, chamada concluída, uma fonte autorizada no
Regulamento Interno e resposta idêntica ao resultado persistido. Em 11/11/2026,
o responsável confirmou que o teste nesse chat respondeu corretamente. A consulta
local com o papel de síndico permanece uma evidência distinta do teste Telegram.
Estado por perfil em [i4-telegram-live.json](evidencias/i4-telegram-live.json).
O bot foi executado em processo manual supervisionado, sem serviço ou execução automática.

Evidências: [testes](evidencias/i4-tests.json),
[saída detalhada](evidencias/i4-unittest.txt),
[decisão de aceite](evidencias/i4-acceptance.json) e
[autorizações](evidencias/i4-authorizations.json).

## Preservação e documentação

Na etapa offline não houve abertura/migração operacional. A continuidade real
autorizada migrou o banco e persistiu metadados/consumo/recibos, com preservação das
tabelas de negócio conferida contra o backup. A configuração recebeu o ID não
secreto da Vector Store pelo caminho canônico; cadastro e renovação preservaram
os demais campos privados. Não foram expostos segredos.
O aceite I2 e os relatórios/testes históricos I1–I3 foram preservados. Somente o
registro formal de aceite I3 foi atualizado para refletir a decisão explícita humana.

Não existe repositório Git local; branch/histórico/diff Git não são verificáveis.
Não houve inicialização Git, operação remota, publicação, serviço Windows ou
alteração fora do Vert2Go. Os padrões externos foram consultados somente em leitura.

README foi atualizado para o estado vigente, removendo declarações atuais de
ausência de Google. Procedimento em [implementacao-i4.md](implementacao-i4.md);
contrato do agente em [agentes/alfredo-i4.md](agentes/alfredo-i4.md).

## Retomada manual de 11/11/2026

Após relato de pergunta sem resposta, não havia processo Python ativo nem trava
de instância ocupada. O último recibo era de 10/11 às 22:46 UTC e a sessão anterior
não estava disponível. Isso comprova ausência do consumidor naquele momento,
sem permitir reconstruir a causa do encerramento anterior.

O mesmo processo manual I4 foi reativado, validou identidade/webhook e encontrou
duas mensagens pendentes do morador. Ambas terminaram em `knowledge_evidence_invalid`
e tiveram o aviso seguro de indisponibilidade aceito pela API Telegram. Não houve
operação OpenAI incerta, mudança de código ou avanço à I5. Os textos recebidos não
foram registrados; o responsável foi solicitado a informá-los para diagnóstico,
sem repetir automaticamente as despesas dessas mensagens.

A execução continua manual. Um atalho foi explicado como possibilidade de
facilitar a ativação, mas não foi criado e não existe inicialização automática.
Evidência: [retomada](evidencias/i4-runtime-restart-20261111.json).

## Correção de citações com negrito em várias linhas — 11/11/2026

As perguntas informadas foram sobre estacionar bicicleta na vaga de garagem e
quantidade de vagas do apartamento 62. Ambos os trechos autorizados contêm negrito
atravessando quebras de linha. O validador tentava remover o negrito antes de
normalizar espaços, com expressão que excluía novas linhas; assim, citações que
reproduziam o texto visível eram recusadas. Os dois novos testes de regressão
reproduziram essa falha antes da correção. As respostas brutas das tentativas
originais não foram preservadas; não se afirma que esse tenha sido o único motivo
possível para aquelas recusas.

A correção em `citation_text` apenas antecipa a normalização de espaços ao
tratamento dos marcadores já existente. Números, palavras e operadores continuam
preservados. Um terceiro teste verifica que omissões e montagem de trechos
distintos continuam rejeitadas. O transporte, modelo, fontes, geração documental,
permissões e limites não foram alterados, e não houve novo upload dos documentos.

Os 320 testes completos passaram. Os dois casos adicionais executaram pelo serviço
canônico com chamadas OpenAI reais e retornaram `knowledge_answer` com fontes
autorizadas e trechos verificáveis: regra de estacionamento para carro/moto e três
vagas indeterminadas para o apartamento 62. A primeira resposta apresentou a regra
aplicável, sem uma frase explícita de conclusão sobre bicicleta. A segunda informou
as três vagas. Não se apresenta esses retestes locais como novas entregas Telegram.

O bot manual foi reiniciado com a correção e confirmou identidade, webhook livre
e início do polling. Evidência: [correção](evidencias/i4-multiline-citation-fix.json).
A evidência anterior de 317 testes foi preservada em
[snapshot anterior](evidencias/i4-tests-before-multiline-citation-fix.json).

## Nova recusa da bicicleta e ajuste de qualidade — 11/11/2026

O responsável informou que bicicleta voltou a receber indisponibilidade e que
piscina respondeu. Os recibos confirmaram ambos os resultados. A reprodução real
mostrou citações que omitiam uma frase intermediária e IDs de arquivo inventados;
o bloqueio estrito era correto. A correção de negrito anterior continua válida,
mas não eliminava erros de geração do modelo. Os registros reprovados e os
aprovados foram preservados, sem apresentar um único sucesso como prova de
consistência. As respostas brutas dos updates originais não foram recuperadas.

O prompt passou a pedir apenas as regras necessárias, conclusão explícita e
citações curtas contínuas. O esquema de saída agora restringe `file_id` aos IDs
do manifesto aprovado. O ensaio com limite de citação de 160 caracteres produziu
palavras truncadas e foi abandonado; o limite vigente é o original de 1.000.
Não se adotou correção aproximada de citações nem troca automática do arquivo
atribuído pelo modelo. Citações montadas continuam bloqueadas. Novos motivos
fixos de recusa (`validation_error`) são persistidos/logados sem texto de usuário,
fonte ou resposta bruta. O aviso Telegram permanece seguro.

As novas instruções/limites não bastaram para estabilizar o mini nas amostras.
Após avaliação real sem troca permanente inicial, o piloto foi ajustado para
`gpt-4.1-2025-04-14`, com preços corretos de US$ 2/8 por milhão de tokens de
entrada/saída, preservando o teto de R$ 30/mês e alerta R$ 24. Projeto, fontes,
geração, Vector Store e outros campos privados permaneceram iguais, com escrita
atômica/ACL e sem abrir o arquivo de segredos para essa alteração.
Fontes: [modelo](https://developers.openai.com/api/docs/models/gpt-4.1),
[preços](https://developers.openai.com/api/docs/pricing),
[saída estruturada](https://developers.openai.com/api/docs/guides/structured-outputs).

A busca e a interpretação continuam semânticas, feitas pela IA/File Search.
Não houve índice local, busca por palavras-chave no bot ou regras como
pergunta/assunto → resposta programada. Leituras locais de trechos foram usadas
somente no diagnóstico e nas fixtures de regressão. O Python continua conferindo
permissões, atualidade e citações. I5 não foi iniciada.
Evidência consolidada: [ajuste de qualidade](evidencias/i4-model-quality-fix.json).

Na configuração final, duas variantes da bicicleta e a pergunta da piscina
passaram no serviço real com fontes/trechos conferidos. São três amostras,
não uma garantia geral de consistência. Os 325 testes locais passaram e o bot
manual foi retomado com identidade/webhook verificados e polling ativo.
Foi solicitada uma nova mensagem sobre bicicleta no Telegram para confirmar
o comportamento após este ajuste; essa confirmação ainda está pendente.

## Pendências e continuação

1. Confirmar a pergunta da bicicleta no Telegram após o ajuste de qualidade atual.
2. Responsável revisar as evidências reais e registrar o aceite formal da I4.

Essas operações já têm as autorizações I4 registradas; não se deve solicitá-las
novamente para o mesmo escopo. Cadastro, sincronização e consultas locais reais
estão concluídos. I5/I6, escrita Google, OCR e exclusões continuam fora desta entrega.
