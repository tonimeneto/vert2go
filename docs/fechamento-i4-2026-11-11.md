# Fechamento técnico I4 para aceite do responsável

Data: 11/11/2026. Escopo: consolidação dos retestes e revisão final da I4,
sem alterações de código, novas chamadas pagas ou avanço à I5.

## Resultado

**I4 aceita formalmente pelo responsável em 11/11/2026 para o piloto, com as
limitações abaixo.** O responsável respondeu “sim” à pergunta de aceite formal
nesse escopo. Registro: [i4-acceptance.json](evidencias/i4-acceptance.json).

A configuração vigente usa `gpt-4o-2024-08-06`. Os quatro últimos retestes da
bicicleta foram conferidos nos recibos: dois de morador e dois de síndico,
todos `knowledge_answer`, entrega `sent`, chamada concluída, resposta igual ao
resultado persistido e referências com hashes autorizados. O responsável
confirmou os quatro recebimentos; a diferença de redação não mudou a conclusão.
As referências técnicas estão em
[i4-final-review-20261111.json](evidencias/i4-final-review-20261111.json).

## Revisão das condições e evidências

- Entrada: I3 aceita e G3 já autorizado para os dois documentos, indexação,
  custos estimados e testes nas duas contas. Os registros de autorização foram mantidos.
- Indexação: sincronização real dos dois documentos já comprovada; versões/hash
  e manifesto continuam sendo as fronteiras de uso. Não há índice local.
- Semântica: consultas naturais, paráfrase e lacuna tiveram ensaios reais
  históricos. Os quatro retestes recentes confirmam o caso que havia falhado
  em ambos os perfis no modelo atual; não substituem todos os demais cenários.
- Segurança de evidência: a revisão do fluxo mantém arquivo permitido, trecho
  contínuo, seção verificável, geração atual e revalidação antes da entrega.
  Não foi introduzida pesquisa determinística por assunto ou resposta programada.
- Regressão: 338 testes aprovados na última execução; os hashes atuais de
  código/scripts/testes conferem com essa execução. Não foi necessário repetir
  a suíte, pois não houve alteração do código nesta revisão.
- Persistência: banco esquema 3, integridade e chaves estrangeiras válidas;
  nenhuma operação OpenAI em execução/incerta no snapshot. O custo medido
  acumulado convertido era R$ 2,580846, ante orçamento estimado R$ 30 e alerta R$ 24.
- Operação Windows: controle de ligar/desligar já validado separadamente,
  preservando o motor e a parada cooperativa. ATIVO não significa aprovação
  semântica das respostas.

## Limites e histórico preservado

Houve falhas reais, inclusive `quote_not_found`, antes dos quatro sucessos.
Não foram apagadas nem reclassificadas como sucesso. Quatro tentativas
consecutivas não estimam uma taxa de erro geral nem provam eliminação definitiva
da intermitência. A conferência literal da citação também não prova, sozinha,
que toda interpretação do modelo é semanticamente correta.

Não foi identificado um novo ensaio semântico controlado de ausência de regra
especificamente no GPT-4o. Há o ensaio real histórico e testes offline do código
vigente para lacuna/falha segura. Essa distinção deve acompanhar o aceite;
não apresentar todos os cenários históricos como reexecutados no modelo atual.
Este fechamento é uma revisão delimitada de critérios e evidências, não um
pentest ou auditoria exaustiva de todo o produto.

O orçamento é uma estimativa local; não é um teto garantido da fatura. Parar o
bot não remove os arquivos externos nem encerra armazenamento. Reservas,
escrita Google e memória administrativa real permanecem fora da I4.

## Reconciliação documental

Este fechamento substitui as declarações de confirmação da bicicleta ainda
pendente nos resumos anteriores. Os registros de falhas, o handoff de auditoria
e os relatórios de ajustes continuam históricos, com seus respectivos cortes.
O aceite e o resumo de validação foram atualizados para o modelo e retestes
atuais, sem modificar os artefatos individuais antigos.

## Próxima decisão

O aceite formal da I4 foi registrado com as limitações expostas. Ensaios adicionais
de lacuna e outras paráfrases poderão ampliar a evidência do piloto; não são
apresentados como executados por esse aceite.
O aceite não concede G4 automaticamente. I5 exige autorização própria para
gravações na Agenda/planilha e confirmação de recursos exclusivos do piloto.
