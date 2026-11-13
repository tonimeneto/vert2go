"""Scoped questions and Telegram reply bindings. No model can authorize an effect."""
from datetime import timedelta
import json
from app.core.contracts import EngineError, canonical, instant, stamp


def words(text):
    return ' '.join(text.casefold().replace(',', ' ').strip(' .!\n\t').split())


YES = frozenset(('sim','sim pode','pode','pode sim','autorizo','sim autorizo',
    'claro','com certeza',
    'pode registrar','sim pode registrar','pode enviar','sim pode enviar',
    'pode reservar','sim pode reservar','pode cadastrar','sim pode cadastrar',
    'pode cancelar','sim pode cancelar','confirmo','confirmar','sim confirmo',
    'pode encaminhar','sim pode encaminhar','pode mandar','sim pode mandar',
    'sim por favor','pode seguir','sim pode seguir','pode fazer','pode prosseguir',
    'confirmo e aceito a taxa','sim aceito a taxa','sim pode registrar e aceito a taxa'))
NO = frozenset(('não','nao','não autorizo','nao autorizo','não quero','nao quero',
    'não envie','nao envie','não registre','nao registre','deixa pra lá',
    'deixe pra lá','desisto'))


def authorization_words(phrase):
    if '?' in phrase or any(word in phrase.split() for word in ('se','caso','talvez','não','nao')):
        return None
    for _ in range(4):
        before=phrase
        for prefix in ('tá bom ','ta bom ','está bem ','esta bem ','claro ','entendi ','por favor ','caralho ','porra '):
            phrase=phrase.removeprefix(prefix)
        for suffix in (' por favor',' agora',' então',' entao',' isso mesmo',' caralho',' porra'):
            phrase=phrase.removesuffix(suffix)
        if phrase==before:break
    return phrase


def permission(phrase, kind):
    """Match an explicit answer to the action asked, never to a different action."""
    if phrase in NO or (kind not in ('cancel','reservation_cancellation') and phrase in ('pode cancelar','sim pode cancelar')):
        return False
    phrase=authorization_words(phrase)
    if phrase is None:return None
    if kind not in ('cancel','reservation_cancellation') and phrase in ('pode cancelar','sim pode cancelar'):
        return False
    if phrase in ('sim','sim pode','pode','pode sim','autorizo','sim autorizo','confirmo','confirmar',
                  'sim confirmo','sim por favor','pode seguir','sim pode seguir','pode fazer','pode prosseguir','claro','com certeza'):
        return True
    if phrase in ('confirmo e aceito a taxa','sim aceito a taxa','sim pode registrar e aceito a taxa'):
        return True if kind=='reservation' else None
    verbs={
        'reservation':('reservar','registrar','confirmar'),
        'request':('registrar','encaminhar','enviar','mandar'),
        'response':('enviar','mandar','registrar'),
        'create':('registrar','cadastrar'), 'correct':('registrar','alterar','atualizar'),
        'cancel':('cancelar','retirar','encerrar'), 'sync':('sincronizar','atualizar'),
        'reservation_cancellation':('cancelar','desmarcar'),
    }
    objects={
        'reservation':('a reserva','essa reserva'), 'request':('o pedido','esse pedido'),
        'response':('a resposta','essa resposta','a mensagem','essa mensagem','para o morador','ao morador'),
        'create':('a orientação','essa orientação','o aviso','esse aviso'),
        'correct':('a alteração','essa alteração','a orientação','o aviso'),
        'cancel':('a orientação','essa orientação','o aviso','esse aviso'),
        'sync':('a planilha','os registros','as atividades'),
        'reservation_cancellation':('a reserva','essa reserva','a minha reserva','minha reserva'),
    }
    stem=phrase.removeprefix('sim ').removeprefix('pode ')
    if not phrase.startswith(('pode ','sim pode ')):
        return None
    stem=stem.removesuffix(' por favor')
    for verb in verbs.get(kind,()):
        if stem==verb or stem.startswith(verb+' ') and stem[len(verb)+1:] in (*objects.get(kind,()),'isso'):
            return True
    return None


def authorization_phrase(phrase):
    if phrase in NO:return True
    phrase=authorization_words(phrase)
    if phrase is None:return False
    return phrase in YES or (phrase.startswith(('pode ','sim pode ')) and
        any(word in phrase.split() for word in ('enviar','mandar','registrar','reservar','cadastrar',
            'cancelar','atualizar','sincronizar','retirar','alterar','confirmar','encaminhar')))


class OperationDialog:
    def __init__(self, engine):
        self.engine=engine

    def put(self, scope, key, data, expires):
        data={**data,'role':self.engine.policy.identify(scope)}
        with self.engine.store.transaction():
            self.engine.store.execute('''INSERT INTO conversation_state VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(environment_id,channel,channel_user_id,chat_id,state_key)
                DO UPDATE SET payload=excluded.payload,updated_at=excluded.updated_at,expires_at=excluded.expires_at''',
                (*scope.key(),'i5-dialog:'+key,canonical(data),stamp(self.engine.clock()),stamp(expires)))

    def get(self, scope, key):
        row=self.engine.store.execute('''SELECT payload,expires_at FROM conversation_state WHERE environment_id=?
            AND channel=? AND channel_user_id=? AND chat_id=? AND state_key=?''',
            (*scope.key(),'i5-dialog:'+key)).fetchone()
        if row is None or instant(row['expires_at'])<=instant(self.engine.clock()):
            return None
        data=json.loads(row['payload'])
        if data['role']!=self.engine.policy.identify(scope):
            return None
        return data

    def output(self, message, data, expires=None):
        expires=expires or (self.engine.clock()+timedelta(seconds=self.engine.config.limits['confirmation_seconds']))
        self.put(message.scope,'output:'+message.message_id,{**data,'expires_at':stamp(expires)},expires)

    def request_notice(self, scope, row):
        if row['code']!='pilot_request_notification' or self.engine.policy.identify(scope)!='manager':
            return None
        for notice in self.engine.store.execute('''SELECT request_id,notification_id,response_version FROM pilot_notifications
            WHERE environment_id=? AND channel=? AND channel_user_id=? AND chat_id=? AND state='queued' ''',scope.key()):
            if -(int(notice['notification_id'][:15],16)+1)==row['update_id'] and notice['response_version']==0:
                request=self.engine.store.execute('''SELECT request_id,version,status FROM pilot_requests
                    WHERE environment_id=? AND request_id=? AND assigned_to='manager' ''',
                    (scope.environment_id,notice['request_id'])).fetchone()
                if request and request['status']=='forwarded':
                    return {'kind':'request_reply','request_id':request['request_id'],'expected_version':request['version']}
        return None

    def outgoing(self, scope, row):
        return self.get(scope,'output:'+str(row['message_id'])) or self.request_notice(scope,row)

    def markup(self, scope, row):
        question=self.outgoing(scope,row)
        if question and question['kind'] in ('proposal','clarification','request_reply','sync','cancellation_choice'):
            # Native reply association; no slash command or copied technical ID.
            return {'force_reply':True,'input_field_placeholder':'Responda normalmente por aqui'}
        return None

    def sent(self, scope, row, telegram_message_id):
        question=self.outgoing(scope,row)
        expires=(instant(question['expires_at']) if question and question.get('expires_at') else
                 self.engine.clock()+timedelta(days=self.engine.config.retention['conversation_days']))
        binding={**(question or {'kind':'closed'}),'source_update_id':row['update_id']}
        self.put(scope,'reply:'+str(telegram_message_id),binding,expires)
        self.put(scope,'current',binding,expires)

    def context(self, message):
        key=('reply:'+str(message.reply_to_message_id) if message.reply_to_message_id is not None else 'current')
        data=self.get(message.scope,key)
        if not data:
            return None
        receipt=self.engine.store.execute('''SELECT state FROM telegram_updates
            WHERE environment_id=? AND update_id=? AND channel_user_id=? AND chat_id=?''',
            (message.scope.environment_id,data['source_update_id'],message.scope.channel_user_id,message.scope.chat_id)).fetchone()
        return data if receipt and receipt['state']=='sent' else None

    def delivered_proposal(self, scope, receipt, operation):
        data=self.get(scope,'output:'+str(receipt['message_id']))
        return bool(data and data['kind']=='proposal' and data['operation_id']==operation['operation_id']
                    and data['proposal_hash']==operation['proposal_hash'])

    def decline(self, message, operation):
        table=('pilot_cancellations' if operation['source']=='cancellation' else 'pilot_operations' if operation['source']=='pilot' else 'requests_state')
        permission=({'reservation':'reservation.create','request':'request.create','response':'request.respond'}[operation['kind']]
                    if table=='pilot_operations' else 'reservation.cancel' if table=='pilot_cancellations' else 'guidance.'+operation['kind'])
        role=self.engine.policy.authorize(message.scope,permission)
        now=stamp(self.engine.clock())
        with self.engine.store.transaction():
            count=self.engine.store.execute('UPDATE '+table+''' SET state='cancelled',closed_at=?,updated_at=?
                WHERE environment_id=? AND operation_id=? AND channel=? AND channel_user_id=? AND chat_id=?
                AND state='awaiting_confirmation' AND proposal_hash=? AND expires_at>?''',
                (now,now,message.scope.environment_id,operation['operation_id'],*message.scope.key()[1:],
                 operation['proposal_hash'],now)).rowcount
            if count!=1:
                raise EngineError('confirmation_expired')
            self.engine.store.audit(message,role,'dialog.decline','cancelled',self.engine.clock(),operation['operation_id'],
                                    previous='awaiting_confirmation',next_state='cancelled')
        return 'pilot_declined','Tudo bem. Não vou executar esse pedido. Se quiser, podemos ajustar os dados e começar outra proposta.'

    def consume_sync(self, message, token, state):
        data=self.get(message.scope,'sync:'+token)
        if not data or data.get('state')!='waiting':
            raise EngineError('confirmation_expired')
        role=self.engine.policy.authorize(message.scope,'operations.reconcile')
        if data['destinations']!=self.engine.operations.destinations():
            raise EngineError('operation_resource_changed')
        with self.engine.store.transaction():
            changed=self.engine.store.execute('''UPDATE conversation_state SET payload=?,updated_at=? WHERE
                environment_id=? AND channel=? AND channel_user_id=? AND chat_id=? AND state_key=? AND payload=?''',
                (canonical({**data,'state':state}),stamp(self.engine.clock()),*message.scope.key(),
                 'i5-dialog:sync:'+token,canonical(data))).rowcount
            if changed!=1:
                raise EngineError('confirmation_expired')
            self.engine.store.audit(message,role,'dialog.sync_authorization',state,self.engine.clock(),token)
        return data
