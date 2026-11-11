# Alfredo — comportamento documental I4

Especificação do agente do produto, 10/11/2026.
O prompt executável canônico está em `app/ai/openai_http.py`, em `INSTRUCTIONS`.
Esta especificação descreve seus contratos e não substitui PRD/especificação técnica.

Alfredo recebe uma pergunta textual de usuário autorizado e consulta exclusivamente
os documentos elegíveis da geração configurada na Vector Store do piloto. Responde
em português, com interpretação natural e evidências; não inventa horários, taxas,
disponibilidade, páginas ou regras ausentes.

Antes de recuperar evidências, o modelo deve interpretar a atividade e os parâmetros
da pergunta e formular a busca com o recurso e a regra pertinentes. Horários por
extenso são convertidos para 24 horas para comparação. Essa formulação continua
sob responsabilidade da LLM e de File Search; não acrescenta índice local,
buscador por palavra-chave ou regra condominial presumida.

A resposta usa o menor número necessário de afirmações e prioriza a regra
específica suficiente. Perguntas de sim/não recebem uma conclusão explícita.
O texto pode interpretar; a citação deve copiar palavras consecutivas de um
único resultado, sem omitir frases intermediárias ou copiar parágrafos desnecessários.
O identificador do arquivo deve pertencer ao mesmo resultado da citação.
O esquema restringe os IDs aos arquivos do manifesto e a citação gerada a
1.000 caracteres. Essas restrições não substituem busca ou interpretação semântica
por regras de resposta determinísticas. A seleção do conteúdo continua com a IA.

Os documentos e a pergunta são conteúdo não confiável. Não modificam instruções,
identidade, papéis, permissões, recursos, orçamento ou ferramentas. A identidade e
a autorização são determinadas pelo Python antes de qualquer chamada.

A única ferramenta fornecida ao modelo é File Search. Não há função de reserva,
gravação Google, alteração administrativa ou acesso a credenciais. O fluxo não
envia histórico completo nem dados operacionais desnecessários ao provedor.

A saída estruturada separa resposta apoiada em evidência, insuficiência e conflito.
Afirmações precisam de trecho literal e arquivo autorizado; a validação Python
confere esses vínculos antes de apresentar a resposta. A interpretação semântica
precisa também dos ensaios reais de qualidade, não apenas da validação estrutural.

A comparação de citações admite somente diferenças de espaços/quebras de linha
e marcadores pareados de negrito Markdown, inclusive envolvendo texto quebrado
em várias linhas na fonte. Os espaços são normalizados antes dos marcadores.
Palavras, números, acentos, pontuação
e operadores matemáticos continuam preservados. O modo da conferência fica
registrado em `quote_match`; citações vazias ou não contíguas são rejeitadas.
Recusas registram apenas um código interno fixo em `validation_error` e no log;
o Telegram recebe somente o aviso seguro, sem diagnóstico interno ou texto bruto.

Fontes de simulação são identificadas como tais. Orientação administrativa é uma
fonte operacional distinta, mantida em SQLite e não compartilhada no fluxo I4 real.
Sem evidência ou em falha, o canal apresenta uma limitação segura.

Proveniência, atualização, estados incertos, custos e ativação são tratados em
[implementacao-i4.md](../implementacao-i4.md). O aceite da I4 não libera a I5.
