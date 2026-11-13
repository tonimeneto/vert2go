# Alfredo — operações experimentais I5

Estado: implementação local aprovada nos ensaios automatizados; OAuth e cenários
Google reais validados em 12/11/2026. Os fluxos Telegram I5 e o aceite formal ainda
estão em validação. Sessões reais de teste são temporárias; o painel Windows
conserva seu modo I4. Para o estado vigente, consultar o [relatório I5](../relatorio-i5.md).

Esta etapa acrescenta à [I4](alfredo-i4.md) extração semântica de propostas de
reserva, solicitações e orientações, sem conceder ferramentas ou permissões à LLM.
Identidade, autorização, regras, confirmação e escrita são validadas pelo Python.
O modelo não confirma operações. Datas ambíguas e vigência insuficiente exigem
esclarecimento. Uma resposta administrativa não modifica regras nem aprova reserva.

A Agenda experimental é a única prova de disponibilidade/existência da reserva.
Sheets registra atividades por outbox independente. Orientações da administração
continuam no SQLite com versões, confirmação e vigência; não passam pelo índice
documental e não geram broadcast. Em conflito ou falta de base, pedir esclarecimento.
Respostas pertinentes podem usar somente orientações filtradas e compatíveis com
a evidência documental, atribuídas separadamente à administração.

O perfil `resident` reserva para a unidade fictícia cadastrada e acompanha suas
solicitações. `manager` responde encaminhamentos com confirmação/versionamento,
consulta relatórios sob demanda e reconcilia operações. Nenhum texto muda o perfil.

## Conversa e autorização

Na reserva, guardar data e horários já fornecidos e perguntar apenas o que falta.
Data sem horário não define um evento de dia inteiro. Se o intervalo violar as
condições externas, explicar o motivo concreto e conservar os dados válidos.
Perguntas sobre disponibilidade consultam a Agenda real em somente leitura e
mostram faixas livres e limites aplicáveis; não criam uma reserva. A proposta
completa e a autorização de gravação continuam sendo etapas distintas.

“Dia 16” usa uma data já conhecida ou a única possibilidade no período cadastrado;
caso ambíguo exige mês/ano. “Ao meio-dia” é reconhecido como 12h. Um conflito deve
ser explicado ao morador e seguir para alternativas consultadas, sem transferir
falhas de configuração ou validade de uma sugestão para o pedido original.

Preservar o objetivo da pergunta ao esclarecer datas: se o usuário perguntou por
disponibilidade e corrigiu o ano, consultar os horários nessa data. A correção não
transforma uma consulta em pedido de criação de reserva.

Alfredo conduz o atendimento no Telegram. Apresenta os dados e pergunta se pode
executar a ação correspondente; a pessoa responde em linguagem natural. Comandos
são atalhos de compatibilidade, não passos obrigatórios. IDs, hashes e versões
permanecem internos. Autorização não é decidida pela LLM: o Python confere pessoa,
conversa, perfil, proposta entregue, integridade, prazo e tipo de ação autorizado.

O aviso à administração inclui o pedido do morador e pede o texto da resposta.
Maria responde à mensagem; Alfredo mostra o texto e pede permissão antes de enviar.
Uma resposta como “sim” a uma pergunta de conteúdo é conteúdo, não autorização.
Depois de registrar a resposta, o bot pode pedir uma autorização separada para a
outbox da planilha. Dizer “não” encerra somente a proposta ainda não executada.
Vários pedidos exigem responder à mensagem do pedido escolhido, sem digitar IDs.

Contexto das chamadas, custos, recuperação, parâmetros e limitações constam na
[implementação I5](../implementacao-i5.md). O modelo e os limites continuam externos.
Não há cobrança, integração oficial, serviço novo ou operação de produção.
