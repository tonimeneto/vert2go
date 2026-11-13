"""Human-facing I5 messages. Internal identifiers never become a required user step."""
from zoneinfo import ZoneInfo
from app.core.contracts import instant


def local_time(value, timezone):
    when=instant(value).astimezone(ZoneInfo(timezone))
    return when.strftime('%d/%m/%Y às %H:%M')+' (horário de Brasília)'


def proposal(data, timezone, request_content=None):
    kind=data['kind']
    introductions={
        'reservation':'Entendi que você quer reservar este espaço:',
        'request':'Você quer encaminhar este pedido à administração:',
        'response':'Você quer responder ao morador com esta mensagem:',
        'create':'Você quer registrar esta orientação da administração:',
        'correct':'Você quer atualizar esta orientação da administração:',
        'cancel':'Você quer retirar esta orientação de vigência, preservando o histórico:',
    }
    questions={
        'reservation':'Posso confirmar essa reserva na Agenda experimental?',
        'request':'Posso registrar e encaminhar esse pedido?',
        'response':'Posso enviar essa resposta ao morador?',
        'create':'Posso registrar essa orientação?',
        'correct':'Posso registrar essa alteração?',
        'cancel':'Posso retirar essa orientação de vigência?',
    }
    lines=[introductions[kind]]
    if request_content:
        lines+=['Pedido do morador'+(' (trecho)' if len(request_content)>1000 else '')+': '+request_content[:1000]]
    labels=(('resource','Espaço'),('unit_reference','Unidade simulada'),('start','Início'),('end','Fim'),
            ('topic','Assunto'),('content','Conteúdo'),('response','Resposta'),('audience','Público'),
            ('effective_from','Vigência inicial'),('effective_until','Vigência final'))
    for key,label in labels:
        if key in data:
            value=data[key]
            if key in ('start','end','effective_from','effective_until'):
                value=local_time(value,timezone)
            elif key=='audience':
                value={'residents':'moradores','managers':'administração'}[value]
            elif key=='resource':
                value={'salao':'salão'}.get(value,value.replace('_',' '))
            lines.append(label+': '+str(value))
    if data.get('urgent'):
        lines.append('Pedido marcado como urgente.')
    if 'rule' in data:
        rule=data['rule']
        status={'simulated':'simulada','verified':'verificada'}.get(rule['status'],'pendente de verificação')
        lines+=['Condição do piloto ('+status+'): '+rule['source_title']+' — '+rule['section'],
                'Taxa informativa: R$ '+rule['fee_brl']+'. Não haverá cobrança neste ensaio.']
    lines+=['Ainda não executei. Este atendimento é experimental.',questions[kind]]
    if 'rule' in data and data['rule']['fee_brl'] not in ('0','0.00'):
        lines.append('Preciso também do seu aceite explícito da taxa informativa para continuar.')
    lines+=['Se quiser mudar algo, diga o que deseja ajustar.',
            'Esta autorização vale até '+local_time(data['expires_at'],timezone)+'.']
    return '\n'.join(lines)


def report(data):
    names={'reservation':'Reserva','request':'Pedido','response':'Resposta administrativa'}
    states={'confirmed':'registrada','conflicted':'em conflito','awaiting_confirmation':'aguardando autorização',
            'cancelled':'proposta encerrada sem execução','needs_reconciliation':'em verificação',
            'committing':'em processamento','failed':'com falha','resolved':'respondido',
            'forwarded':'encaminhado','pending':'pendente','received':'recebido','closed':'encerrado',
            'synced':'verificado na planilha'}
    lines=['Relatório do piloto experimental.','Histórico de operações (a existência atual das reservas é conferida na Agenda):']
    for row in data['operations']:
        lines.append(names.get(row['kind'],row['kind'])+' — '+states.get(row['status'],row['status'])+': '+str(row['count']))
    lines.append('Pedidos: '+(', '.join(states.get(r['status'],r['status'])+': '+str(r['count']) for r in data['requests']) or 'nenhum'))
    lines.append('Planilha: '+(', '.join(states.get(r['status'],r['status'])+': '+str(r['count']) for r in data['sheets']) or 'nenhum registro'))
    return '\n'.join(lines)
