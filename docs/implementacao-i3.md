# Implementação e operação I3 — integração Google somente leitura

Atualização: 09/11/2026. Responsável: Codex. Conhecimento técnico do Vert2Go.
Referências: PRD v1.2.0, Alfredo v0.1.8, plano v0.1.1 e autorização EXECUTE da I3.
Substitui a declaração operacional de que não existe implementação Google;
não substitui os documentos normativos nem o aceite histórico definitivo da I2.

## Estado e fronteira

A implementação local fornece OAuth Desktop, renovação, cadastro interativo,
persistência privada e adaptadores de leitura. O aceite completo depende de
leituras reais autorizadas e revisão das evidências. A existência de código ou
testes simulados não comprova acesso à conta Google.

Na continuação autorizada, o proprietário informou a conta experimental,
projeto `vert2go-alfredo`, dois documentos Markdown, Agenda e planilha. O cadastro
particular recebeu esses recursos; campos Telegram e bancos foram preservados.
O cliente Desktop correspondente foi localizado em Downloads e copiado para
arquivo protegido e ignorado no projeto, sem alterar o original. O consentimento
foi concluído pelo proprietário no navegador, com identidade e persistência
conferidas. A checagem real final passou nos três serviços e na renovação OAuth.
255 testes locais passaram. A I3 está pronta para aceite formal do responsável.
O diagnóstico inicial
`google_not_configured` é histórico da primeira entrega, antes desse cadastro.
Consulte [evidência local](evidencias/i3-tests.json),
[diagnóstico Google](evidencias/i3-google-check.json) e [relatório](relatorio-i3.md).

I3 não oferece respostas documentais em linguagem natural, indexação, OCR,
reservas ou registros operacionais Google. Não ativa novos comandos Telegram.
As consultas são operadas localmente pelo responsável; o perfil de morador não
recebe acesso a eventos ou células brutos. I4–I6 exigem seus próprios portões.

## Componentes e fechamento preventivo

- `app/config/schema.py`: seção Google opcional. Configurações I1/I2 continuam
  válidas; configuração Google presente passa por validação estrita e imutável.
- `app/integrations/google_config.py`: conta esperada, documentos classificados,
  calendário/período, planilha/intervalos, escopos e limites.
- `google_auth.py`: fluxo Desktop com PKCE/state pela biblioteca oficial,
  navegador local, callback temporário em 127.0.0.1, renovação e conta conferida.
- `private_files.py`: proteção de acesso, exclusão mútua, detecção de alteração
  concorrente, validação, flush/fsync e substituição atômica do YAML.
- `google_http.py`: lista de operações e endpoints GET; não aceita URL, método
  ou máscara de campos fornecidos pelo usuário. TLS permanece validado.
- `drive.py`, `calendar.py`, `sheets.py`: leitura limitada e tratamento de
  respostas incompletas; conteúdo documental permanece em memória.
- `scripts/setup_google_i3.py`: cadastro de parâmetros e consentimento do dono.
- `scripts/check_google_i3.py`: evidências redigidas de leituras, sem SQLite.
- `scripts/verify_i3.py`: verificador vigente, sem serviços externos nem segredos.

Os pontos de entrada `verify_i1.py` e `verify_i2.py` encaminham para I3. A antiga
rotina que sobrescrevia relatórios I2 foi retirada; os artefatos históricos
existentes permanecem preservados. Testes e demonstrações I1/I2 integram a nova
regressão, sem reabrir seu aceite definitivo.

O carregador canônico `load_enrollment_secrets`, também utilizado por
`load_telegram_token` e pelos scripts I2, passa a aceitar **somente** material
Google validado para I3. Substitui a proibição indiscriminada de `google_oauth`
preenchido. OpenAI continua proibida. Não há carregador paralelo permissivo.
O cadastro Telegram continua recusando alterar segredos já cadastrados e
verificando alterações concorrentes. Após a I3, mudanças de credenciais Google
pertencem exclusivamente ao fluxo Google com escrita atômica.

A autenticação real e a leitura não utilizam `app.main`: sua inicialização abre
SQLite e executa recuperação. O novo diagnóstico evita esses efeitos. O banco
permanece no esquema 2; não foi criada migração, agenda paralela, índice ou cache
documental. `document_sync_metadata` continua reservado à sincronização futura;
uma leitura I3 não é registrada como indexação concluída.

## Autorização e escopos

Cada documento deve possuir ID explícito, classificação e MIME de exportação
quando for Google Docs. Pasta não concede autorização transitiva a seus filhos.
O calendário exige ID concreto (`primary` é recusado), declaração de propriedade
dos dados e janela com fuso de até 31 dias. Sheets exige ID e intervalos exatos
com aba e limites, sem colunas/linhas inteiras ou intervalos nomeados.

Exceção explícita para descoberta autorizada: `sheets.discover_structure: true`
permite consultar nomes/dimensões das abas e definições de intervalos nomeados,
com `includeGridData=false` e máscara sem células. Nesse modo, `ranges: []`
é válido e impede toda chamada `sheets.values`. Dimensões indicam capacidade,
não comprovam intervalo preenchido; intervalos nomeados não liberam leitura
automática. A evidência registra `metadata_only`, que não aprova Sheets/I3.
O indicador ausente ou falso mantém o comportamento anterior sem descoberta.

Autorização vigente do proprietário: Agenda de 10/11/2026 00:00 a
17/11/2026 00:00 em America/Sao_Paulo, início inclusivo/fim exclusivo;
nenhuma escrita. A recusa inicial da janela foi substituída pela autorização
explícita posterior. Após conhecer os metadados, o proprietário autorizou
exclusivamente `'Página1'!A1:J20` (200 células). A grade da aba é A1:Z1000 e
não existem intervalos nomeados; sua capacidade não prova a área preenchida.
A leitura efetiva do intervalo autorizado retornou vazia. A Agenda retornou
zero eventos na janela, sem que qualquer evento ou célula fosse criado.
Registro: [i3-resource-authorizations.json](evidencias/i3-resource-authorizations.json).

O conjunto desta implementação é `drive.readonly`, mais
`calendar.events.owned.readonly` quando o proprietário confirma ser dono dos
dados da Agenda; caso contrário, `calendar.events.readonly`. Sem calendário
cadastrado, o consentimento pede apenas Drive. `drive.readonly` também autoriza
os métodos de leitura usados no Sheets; não se acrescenta escopo redundante.

`drive.readonly` permite ler outros arquivos acessíveis à conta e é classificado
como restrito pelo Google. A conta experimental deve ter seus acessos reduzidos
e o proprietário deve aceitar conscientemente essa abrangência. A lista local
de IDs limita o Alfredo, mas não reduz o alcance de um token roubado.
`drive.file` não foi adotado: também permite escrita e depende da concessão
específica dos arquivos ao aplicativo. Não há escopo de escrita nesta I3.

Escopos são calculados pela configuração, conferidos no consentimento e na
renovação, e comparados ao cadastro persistido. Escopos adicionais, insuficientes
ou destinados à escrita são recusados. Alterar recursos pode exigir novo
consentimento; aplicativos instalados não oferecem autorização incremental.

## Ações do proprietário no Google Cloud Console

1. Selecionar projeto exclusivo experimental, ou providenciar sua criação se
   ainda não existir, com autorização própria. Nada disso foi criado pelo Codex.
2. Habilitar Google Drive API, Google Calendar API e Google Sheets API.
3. Em Google Auth Platform, conferir Branding, Audience e Data Access. Para
   conta externa em Testing, adicionar somente a conta experimental como test user.
4. Selecionar/criar cliente do tipo **Desktop app**. Cliente Web ou conta de
   serviço não atende ao fluxo aprovado.
5. Baixar o JSON para dentro do Vert2Go, mantendo o nome `client_secret*.json`,
   já ignorado pelo Git. Não enviar o arquivo ou seus valores ao chat. Também é
   aceito arquivo dentro de `private/`, se essa pasta já existir.
6. Confirmar conta, documentos, calendário, planilha e intervalos de leitura;
   conferir as permissões existentes sem envolver recursos oficiais.

O cadastro restringe a ACL do JSON selecionado **antes de ler seu conteúdo** e
preserva o arquivo original. Não modifica arquivo fora do projeto. O segredo
Desktop não torna o aplicativo um cliente confidencial: PKCE continua obrigatório.

Quando o proprietário autoriza localizar o download, `stage_downloaded_client`
examina apenas arquivos com nomes usuais de cliente OAuth, em leitura limitada,
e seleciona um único cliente Desktop do Project ID informado. O conteúdo é
tratado somente em memória; uma cópia local recebe ACL privada antes de ser
gravada. O original em Downloads é somente leitura e não é removido nem tem sua
ACL alterada. Clientes distintos do mesmo projeto exigem desambiguação humana.

Em External/Testing, refresh tokens para estes escopos expiram em sete dias.
Reautorizar manualmente quando necessário; não publicar em produção só para
evitar essa limitação. Login, senha e segundo fator pertencem ao navegador Google.
O callback e a URL de autorização não são impressos no terminal ou nos logs.

## Procedimento consolidado do proprietário

Pré-condições: dependências de `requirements.txt` instaladas no `.venv`, I2
cadastrada, JSON Desktop salvo conforme acima e IDs/intervalos conhecidos.
Os IDs são solicitados como IDs, não URLs. Todos os passos param em caso de erro.
O primeiro cadastro pode deixar Calendar/Sheets vazios para priorizar Drive;
nesse caso o aceite integral permanece pendente. Para completar depois, repetir
o cadastro incluindo os recursos e refazer o consentimento.

```powershell
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath 'D:\MeusArquivos\Fs\Projetos\Vert2Go'
.\.venv\Scripts\python.exe -B scripts/verify_i3.py
if ($LASTEXITCODE -ne 0) { throw 'Validacao local I3 reprovada. Consulte docs/evidencias/i3-tests.json.' }
.\.venv\Scripts\python.exe -B scripts/setup_google_i3.py --configure
if ($LASTEXITCODE -ne 0) { throw 'Cadastro dos recursos interrompido. Nenhum OAuth deve ser iniciado.' }
.\.venv\Scripts\python.exe -B scripts/setup_google_i3.py --authorize --allow-live-google
if ($LASTEXITCODE -ne 0) { throw 'Consentimento OAuth nao concluido. Consulte o codigo seguro exibido.' }
.\.venv\Scripts\python.exe -B scripts/check_google_i3.py --allow-live-google --verify-refresh
if ($LASTEXITCODE -ne 0) { throw 'Aceite Google pendente. Consulte docs/evidencias/i3-google-check*.json.' }
```

A configuração exige digitar `AUTORIZO LEITURA` após a conferência local dos
escopos. A autorização pede o caminho do JSON em entrada oculta e abre o navegador.
O fluxo expira após 180 segundos sem retorno. Falha/cancelamento não apaga o
cadastro anterior. Não executar simultaneamente cadastros Telegram e Google.

`--allow-live-google` atesta a autorização do operador, não substitui consentimento
nem autoriza outros recursos. A invocação sem esse indicador faz diagnóstico
offline. `--verify-refresh` força renovação real e recarrega o YAML por outro
gerenciador antes das consultas; a evidência identifica essa recarga como mesma
execução Python, sem afirmar reinício de processo. Um teste local separado
comprova recarga em processo Python novo usando credenciais fictícias.

## Proteção, falhas e evidências

Tokens e material Desktop são gravados no campo `google_oauth` de `secrets.yaml`.
Parâmetros permanecem em `config.yaml`; não se usa `.env`, banco ou gerenciador
global. Os arquivos são texto legível. A proteção é de permissões locais, não
criptografia. A ACL deve estar protegida, sem Users/Everyone/Authenticated Users,
Administrators ou grupo coletivo do sandbox. O proprietário mantém acesso.

Um temporário vazio recebe a DACL protegida antes dos bytes secretos; a
substituição preserva as regras de acesso. O proprietário do novo objeto de
arquivo pode ser a identidade que efetuou a atualização. Permissões do usuário
autorizado são preservadas. Não copiar ACL ampla de `data/` ou da raiz.
Temporários privados são removidos pelo próprio fluxo após falha; o JSON Desktop
selecionado pelo proprietário não é excluído. Não há backup secreto automático.

Cada requisição passa por conferência de operação, recurso, janela/intervalo e
limites. Requisições de dados são GET para hosts fixos, sem redirecionamentos.
Troca/renovação OAuth usa POST exclusivamente no endpoint oficial de tokens;
isso não cria nem altera documentos, eventos ou células. Não há método de escrita
Google exposto nos adaptadores. Proxies de ambiente não recebem credenciais.

Limites padrão: 20 segundos por chamada, 120 segundos para uma sessão de leitura,
três tentativas por falha transitória, cinco páginas, 10 MiB **acumulados** nas
respostas da sessão e mil células declaradas. O limite Google de exportação é
10 MB e pode ser atingido antes do limite local. `Retry-After` é respeitado se
couber no prazo; caso contrário, a operação é interrompida. Paginação incompleta,
mudança de versão durante download, arquivo vazio ou tamanho divergente falham.

Uma resposta 401 pode provocar uma renovação, sem loop. Token revogado,
`invalid_grant` ou consentimento insuficiente bloqueiam a operação e requerem
reautorização. Falha transitória de autenticação não é confundida com revogação.
403 não significa recurso inexistente; 404 pode indicar ausência ou inacessibilidade.
Falha Google não é interpretada como agenda livre ou sucesso de operação.

Evidências contêm referências hash dos IDs/intervalos, bytes/hash/versão da leitura
documental, contagens e hashes dos resultados Calendar/Sheets, horário, correlação,
método, classe HTTP, tentativas e duração. Não contêm conta, IDs reais, células,
eventos, textos, URLs autenticadas ou mensagens brutas do provedor. Leituras vazias
são explícitas. Não criar evento/linha para preencher teste.

A evidência real anterior não é sobrescrita por diagnóstico posterior: novas
execuções recebem sufixo temporal. `passed_google_reads` comprova os recursos e
renovação daquela execução; aceite definitivo também exige regressão local e
revisão do responsável. Falhas simuladas são identificadas nos testes, não como
revogações ou falhas de recursos reais provocadas pelo Codex.

## Recuperação e encerramento

Em falha de configuração ou credencial, corrigir localmente a causa e repetir o
procedimento pertinente. Reautorizar com o mesmo cliente Desktop quando necessário;
não enviar valores ao chat. O consentimento não é iniciado automaticamente pelo bot.

Para suspender Google, configurar `google: null` localmente sob autorização do
proprietário. As credenciais podem permanecer protegidas sem uso e o Telegram
continua operando; não remover o campo de segredos nem apagar banco/offsets.
Revogação, exclusão de arquivos e cancelamentos externos exigem autorização
específica. A I3 não autoriza I4, I5, I6, OpenAI ou publicação.

## Fontes técnicas verificadas

- [OAuth Desktop e PKCE](https://developers.google.com/identity/protocols/oauth2/native-app)
- [Expiração de refresh tokens](https://developers.google.com/identity/protocols/oauth2)
- [Consentimento Google](https://developers.google.com/workspace/guides/configure-oauth-consent)
- [Escopos Drive](https://developers.google.com/workspace/drive/api/guides/api-specific-auth)
- [Escopos Calendar](https://developers.google.com/workspace/calendar/api/auth)
- [Sheets get](https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets/get)
- [Sheets values.get](https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets.values/get)
- [Download e exportação](https://developers.google.com/workspace/drive/api/guides/manage-downloads)

As normas DevTOLAS e o catálogo Fs/Comum foram consultados como referências
externas somente leitura. Não há padrão adicional de interface aplicável.
