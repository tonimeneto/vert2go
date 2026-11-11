# Relatório I3 — validação Google concluída, pronta para aceite

Data: 09/11/2026. Responsável: Codex. Objetivo ativo: concluir a integração Google
somente leitura do Alfredo, conforme o PLAN aprovado e a solicitação EXECUTE.

## Resultado vigente

**Implementação e critérios técnicos I3 concluídos. Pronta para aceite do responsável.**
Não há falha ou critério técnico pendente. O proprietário identificou os recursos,
confirmou o projeto, consentiu OAuth e autorizou separadamente a janela da Agenda
e, após a descoberta das abas, o intervalo exato de células. A execução final
comprovou leitura real dos três serviços e renovação de token, com HTTP 200 nas
11 chamadas de dados, todas GET. Nenhum recurso foi escolhido por nome, inferido
ou pesquisado indiscriminadamente. O aceite formal humano não é presumido.

A I2 continua definitivamente aprovada, sem reabertura de critérios. A entrega
I3 não autoriza I4, I5 ou I6. Documentos normativos e suas versões foram preservados.

## Entrega e validação

- OAuth Desktop com PKCE/state, callback temporário em loopback, conta conferida,
  consentimento manual, renovação e recarga do cadastro persistido.
- Seção de configuração estrita, recursos explícitos, Drive prioritário,
  Calendar/Sheets opcionais para cadastro progressivo e exigidos para aceite total.
- Leitura de bytes/versionamento no Drive; eventos delimitados por calendário
  e período; metadados mínimos e células de intervalos exatos no Sheets.
- Transporte GET com endpoints fixos, TLS, rejeição de redirecionamentos e de
  escritas, timeouts, limites de resposta/paginação/células e retentativas limitadas.
- Persistência atômica com DACL privada aplicada antes dos bytes temporários,
  bloqueio de segundo escritor e verificação de alteração concorrente.
- Correção do carregador compartilhado para coexistência de Google e Telegram.
  Nenhuma chamada Google foi adicionada à inicialização ou ao polling Telegram.
- Scripts operacionais e verificador vigente; os pontos de entrada antigos
  encaminham para I3 sem sobrescrever as evidências históricas I1/I2.

`scripts/verify_i3.py`: **255 testes passaram**, sendo 205 anteriores e 50 da
I3, sem falhas, erros ou testes ignorados. Também passaram as demonstrações I1/I2
e a inicialização finita dos três exemplos YAML em bancos temporários. O esquema
operacional permanece 2. A rede é bloqueada na execução dos testes locais.

`pip check`: nenhuma dependência incompatível. Bibliotecas foram instaladas
apenas no `.venv` do Vert2Go e as versões resolvidas foram fixadas em
`requirements.txt`. Windows/Python 3.13.7, google-auth 2.62.1,
google-auth-oauthlib 1.5.0 e requests 2.34.2.

O teste nativo de Windows confirmou DACL privada antes/depois da substituição
atômica e recarga por processo Python novo, com tokens **fictícios**. Não confundir
com renovação Google ou reinício real autorizado de uma integração já cadastrada.

A checagem inicial `google_not_configured` é histórica da primeira entrega local.
Na continuação, o cliente Desktop de `vert2go-alfredo` foi identificado em Downloads
e copiado para um arquivo protegido/ignorado dentro do projeto. O original não foi
alterado. O proprietário concluiu o consentimento no navegador. A conta experimental
foi conferida por API antes de salvar tokens em `secrets.yaml`, sem exposição.
Um processo separado de checagem carregou o cadastro, renovou efetivamente o token
e repetiu as leituras com a configuração final. O plugin Google não substituiu
essa comprovação de OAuth Desktop do Alfredo.

Resultados reais: Regulamento Interno com 12.360 bytes e Convenção com 32.481
bytes, ambos `text/markdown`, obtidos integralmente; os hashes coincidem com as
cópias autorizadas em docs. Não houve transferência à OpenAI. A Agenda retornou
zero eventos de 10/11/2026 00:00 a 17/11/2026 00:00, em America/Sao_Paulo.
Sheets apresentou a aba Página1 (grade A1:Z1000), sem intervalos nomeados. Primeiro
foram lidos somente metadados; após autorização separada, somente A1:J20 foi
consultado, retornando vazio. Isso não afirma que toda a planilha esteja vazia.

## Matriz de aceite da I3

1. Configuração/regressão: **passed**, local; coexistência Google/Telegram,
   esquema estrito, perfis e os 205 testes anteriores preservados.
2. Conta e consentimento reais: **passed**, conta experimental conferida e
   cliente Desktop do projeto informado, com escopos exatos de leitura.
3. Drive real por documento: **passed**, conteúdo integral, hashes e versão
   consistente antes/depois. Negação e formatos também passaram em testes locais.
4. Calendar real no ID/período autorizado: **passed**, consulta vazia válida.
   Paginação completa, repetida e incompleta passaram em simulação.
5. Sheets real no intervalo autorizado: **passed**, A1:J20 vazio, consultado
   somente depois da autorização específica; demais intervalos seguem bloqueados.
6. Renovação real e persistência: **passed** em Google. Cadastro OAuth foi lido
   por processo de checagem separado; a recarga após renovação usa outro gerenciador
   no mesmo processo, conforme a evidência. Reinício com credenciais fictícias
   também passou em teste local Windows.
7. Falhas OAuth/acesso: **passed**, local; `invalid_grant`, falha transitória,
   consentimento parcial, conta incorreta, 401/403/404, sem revogação de token real.
8. IDs/operações/intervalos fora da lista: **passed**, rejeitados antes da rede.
9. Interrupção/concorrrência/ACL: **passed**, temporários fictícios; arquivo
   anterior íntegro em falha antes da substituição e preservação do token Telegram.
10. Ausência de escrita Google: **passed** nas restrições locais e na trilha real:
    todas as chamadas de dados foram GET e não existe método de mutação habilitado.
11. Rastreabilidade/minimização: **passed**, local; referências controladas,
    contagens/hashes, logs sem conteúdo/segredos e nenhuma chamada OpenAI.

Estado formal: [i3-acceptance.json](evidencias/i3-acceptance.json). Os casos reais
não foram preenchidos com resultados simulados. Uma leitura vazia válida não
será apresentada como evento ou célula preenchida, nem provocará criação de dados.

## Preservação e limites

Na primeira entrega local, a comparação em memória confirmou os YAML particulares
idênticos; esse é o escopo histórico de `i3-preservation.json`. Na continuação,
`config.yaml` recebeu somente recursos/limites aprovados e `secrets.yaml` recebeu
OAuth e renovações autorizadas. Os campos Telegram foram preservados pelo fluxo
canônico, e a checagem offline vigente confirmou configuração/token/bot válidos,
sem chamada Telegram. ACLs de configuração, segredos e JSON local passaram na
conferência final. AGENTS, fontes normativas e evidências I2 foram preservados.
Hashes de arquivos privados não são publicados. Evidência inicial:
[i3-preservation.json](evidencias/i3-preservation.json).

Nenhum banco operacional foi aberto ou migrado pelo trabalho I3. Os testes
utilizaram arquivos/bancos temporários próprios. Não houve alteração de offsets,
cadastros, reservas, eventos, planilhas ou documentos Google existentes.
Não houve instalação global, serviço Windows, publicação ou operação Git remota.
Não existe repositório Git local; branch e histórico de versionamento de segredos
não são verificáveis. O projeto não foi inicializado nem clonado autonomamente.

Mudanças existentes: configuração/validador Python, roteamento dos verificadores,
requirements, README e exemplos, além dos YAML particulares autorizados na
continuação. Novos arquivos: adaptadores, scripts, testes, exemplo fictício,
documentação/evidências I3 e cópia privada do cliente Desktop ignorada pelo Git.

## Pendências e próxima ação

Única pendência: o responsável revisar as evidências e registrar o aceite formal
da I3. Não há nova configuração, recurso Google ou teste técnico pendente.
A evidência real final é indicada por `real_google.source` em
[i3-acceptance.json](evidencias/i3-acceptance.json); o diagnóstico inicial e a
primeira descoberta sem células permanecem históricos. Não há autorização para I4.

Riscos remanescentes: escopo Drive de leitura amplo sobre os acessos da conta,
validade de sete dias do refresh token em External/Testing e necessidade de nova
autorização para mudar IDs, intervalos, janela da Agenda ou operações.
Os arquivos de segredos continuam sendo texto local, sem criptografia.

Regras de recuperação, suspensão de Google, limites e fontes técnicas constam
da documentação operacional. Nenhuma exclusão ou revogação é automática.
