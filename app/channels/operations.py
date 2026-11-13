"""I5 conversational adapter; confirmations are explicit and never model generated."""
from uuid import NAMESPACE_URL, uuid5
import json
import re
from datetime import timedelta
from app.core.contracts import EngineError, Result, canonical, stamp, digest, instant
from app.channels.operation_dialog import OperationDialog, YES, NO, words, permission, authorization_phrase


class OperationsConversation:
    def __init__(self, engine, interpreter=None):
        self.engine,self.interpreter = engine,interpreter
        self.dialog=OperationDialog(engine)
        from app.channels.reservation_conversation import ReservationConversation
        self.reservations=ReservationConversation(self)

    def _clarification_context(self, message):
        row=self.engine.store.execute('''SELECT payload,expires_at FROM conversation_state WHERE environment_id=?
            AND channel=? AND channel_user_id=? AND chat_id=? AND state_key='i5-clarification' ''',message.scope.key()).fetchone()
        if row is None or instant(row['expires_at'])<=instant(self.engine.clock()):
            return None
        context=json.loads(row['payload'])
        return context if context['role']==self.engine.policy.identify(message.scope) else None

    def _ask(self, message, intent, field):
        # Transient conversational context is distinct from confirmed administrative memory.
        now=instant(self.engine.clock())
        context={'role':self.engine.policy.identify(message.scope),'intent':intent,'field':field}
        with self.engine.store.transaction():
            self.engine.store.execute('''INSERT INTO conversation_state VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(environment_id,channel,channel_user_id,chat_id,state_key)
                DO UPDATE SET payload=excluded.payload,updated_at=excluded.updated_at,expires_at=excluded.expires_at''',
                (*message.scope.key(),'i5-clarification',canonical(context),stamp(now),
                 stamp(now+timedelta(seconds=self.engine.config.limits['confirmation_seconds']))))
        self.dialog.output(message,{'kind':'clarification','intent':intent,'field':field})
        return 'clarification_required',self.clarification(field)

    def _clear_clarification(self, message):
        with self.engine.store.transaction():
            self.engine.store.execute('''DELETE FROM conversation_state WHERE environment_id=? AND channel=?
                AND channel_user_id=? AND chat_id=? AND state_key='i5-clarification' ''',message.scope.key())

    def _pending(self, message):
        store,now = self.engine.store,stamp(self.engine.clock())
        rows = store.execute("SELECT operation_id,proposal_hash,kind,'pilot' AS source FROM pilot_operations WHERE environment_id=? AND channel=? AND channel_user_id=? AND chat_id=? AND state='awaiting_confirmation' AND expires_at>?",
                              (*message.scope.key(),now)).fetchall()
        rows += store.execute("SELECT operation_id,proposal_hash,kind,'guidance' AS source FROM requests_state WHERE environment_id=? AND channel=? AND channel_user_id=? AND chat_id=? AND state='awaiting_confirmation' AND expires_at>?",
                               (*message.scope.key(),now)).fetchall()
        if message.scope.channel == 'telegram':
            delivered = store.execute("SELECT message_id,reply FROM telegram_updates WHERE environment_id=? AND channel_user_id=? AND chat_id=? AND code IN ('pilot_proposal','proposal') AND state='sent'",
                (message.scope.environment_id,message.scope.channel_user_id,message.scope.chat_id)).fetchall()
            rows = [r for r in rows if any(self.dialog.delivered_proposal(message.scope,d,r)
                    or '/confirmar '+r['operation_id'] in d['reply'] for d in delivered)]
        return rows

    def _proposal_intent(self, message, operation):
        from app.ai.operation_intent import FIELDS
        if operation['source']=='pilot':
            data=json.loads(self.engine.operations._row(message,operation['operation_id'])['proposal'])
            action=data['kind'] if 'kind' in data else operation['kind']
        else:
            data=self.engine.memory._draft(message.scope,operation['operation_id'])
            action='guidance_'+operation['kind']
        return {**{key:data.get(key) for key in FIELDS},'action':action,
                'requested_action':action,'expected_version':data.get('expected_version'),'urgent':data.get('urgent',False)}

    def _remember_proposal(self, message, result):
        if result.code in ('proposal','pilot_proposal'):
            self.dialog.output(message,{'kind':'proposal','operation_id':result.data['operation_id'],
                'proposal_hash':result.data['proposal_hash']},instant(result.data['expires_at']))

    def _prepare_sync(self, message, lead=''):
        self.engine.policy.authorize(message.scope,'operations.reconcile')
        count=self.engine.store.execute("SELECT count(*) FROM pilot_outbox WHERE environment_id=? AND state!='synced'",
                                        (message.scope.environment_id,)).fetchone()[0]
        if not count:
            return 'pilot_sync','A planilha experimental está sem atividades pendentes de sincronização.'
        token=str(uuid5(NAMESPACE_URL,canonical(['sync',message.scope.key(),message.message_id])))
        expires=self.engine.clock()+timedelta(seconds=self.engine.config.limits['confirmation_seconds'])
        data={'kind':'sync','token':token,'state':'waiting','count':count,
              'destinations':self.engine.operations.destinations(),'expires_at':stamp(expires)}
        self.dialog.put(message.scope,'sync:'+token,data,expires)
        self.dialog.output(message,data,expires)
        from app.channels.operation_messages import local_time
        return 'pilot_sync_proposal',(lead+'\n\n' if lead else '')+f'Há {count} atividade(s) para conferir na planilha experimental. Posso sincronizar esses registros agora?\nEsta autorização vale até '+local_time(expires,self.engine.config.timezone)+'.'

    def _completed(self, message, result):
        code,reply=self.render(result)
        if result.code=='reservation_confirmed':
            self.reservations.close(message.scope)
        if result.code=='pilot_confirmed' and self.engine.policy.identify(message.scope)=='manager':
            row=self.engine.store.execute('SELECT kind FROM pilot_operations WHERE environment_id=? AND operation_id=?',
                                          (message.scope.environment_id,result.data['operation_id'])).fetchone()
            if row and row['kind']=='response':
                # Independent Sheets outbox: ask, never synchronize on response approval itself.
                try:
                    self.engine.policy.authorize(message.scope,'operations.reconcile')
                except EngineError:
                    return code,reply
                return code,self._prepare_sync(message,reply)[1]
        return code,reply

    def _repeat_proposal(self, message, context):
        rows=[row for row in self._pending(message) if row['operation_id']==context['operation_id']]
        if len(rows)!=1:
            raise EngineError('confirmation_expired')
        row=rows[0]
        if row['source']=='pilot':
            data={**json.loads(self.engine.operations._row(message,row['operation_id'])['proposal']),
                  'operation_id':row['operation_id'],'proposal_hash':row['proposal_hash']}
            result=Result('awaiting_confirmation','pilot_proposal',data)
        else:
            result=Result('awaiting_confirmation','proposal',self.engine.memory._summary(self.engine.memory._draft(message.scope,row['operation_id'])))
        self._remember_proposal(message,result)
        return result.code,'Antes de executar, preciso da sua autorização:\n'+self.render(result)[1]

    def _request_reply(self, message, context):
        self.engine.policy.authorize(message.scope,'request.respond')
        row=self.engine.store.execute('''SELECT version,status,assigned_to FROM pilot_requests
            WHERE environment_id=? AND request_id=?''',(message.scope.environment_id,context['request_id'])).fetchone()
        if not row or row['status']!='forwarded' or row['assigned_to']!='manager' or row['version']!=context['expected_version']:
            raise EngineError('request_not_respondable')
        if message.reply_to_message_id is None:
            count=self.engine.store.execute("SELECT count(*) FROM pilot_requests WHERE environment_id=? AND assigned_to='manager' AND status='forwarded'",(message.scope.environment_id,)).fetchone()[0]
            if count!=1:
                raise EngineError('request_choice_required')
        from app.ai.operation_intent import FIELDS
        return {**{key:None for key in FIELDS},'action':'response','requested_action':'response',
                'request_id':context['request_id'],'expected_version':row['version'],
                'response':message.text.strip(),'urgent':False}

    def _resolve_references(self, message, intent):
        kind=intent['action'];store=self.engine.store
        if kind=='response':
            self.engine.policy.authorize(message.scope,'request.respond')
            if not intent.get('request_id'):
                rows=store.execute("SELECT request_id,version FROM pilot_requests WHERE environment_id=? AND assigned_to='manager' AND status='forwarded' ORDER BY created_at LIMIT 2",(message.scope.environment_id,)).fetchall()
                if len(rows)!=1:
                    raise EngineError('request_choice_required' if rows else 'request_not_respondable')
                intent={**intent,'request_id':rows[0]['request_id']}
            row=store.execute('SELECT version FROM pilot_requests WHERE environment_id=? AND request_id=?',
                              (message.scope.environment_id,intent['request_id'])).fetchone()
            if row and intent.get('expected_version') is None:
                intent={**intent,'expected_version':row['version']}
        if kind in ('guidance_correct','guidance_cancel'):
            self.engine.policy.authorize(message.scope,'guidance.'+('correct' if kind=='guidance_correct' else 'cancel'))
            params=[message.scope.environment_id]
            query='''SELECT v.* FROM operational_guidance g JOIN operational_guidance_revisions v
                ON v.environment_id=g.environment_id AND v.guidance_id=g.guidance_id AND v.version=g.current_version
                WHERE g.environment_id=? AND g.status='active' '''
            if intent.get('guidance_id'):
                query+=' AND g.guidance_id=?';params.append(intent['guidance_id'])
            elif intent.get('topic'):
                query+=' AND v.topic=?';params.append(intent['topic'])
            rows=store.execute(query+' LIMIT 2',params).fetchall()
            if len(rows)!=1:
                raise EngineError('guidance_choice_required')
            row=rows[0];intent={**intent,'guidance_id':row['guidance_id']}
            if intent.get('expected_version') is None:
                intent={**intent,'expected_version':row['version']}
            if kind=='guidance_correct':
                intent={**intent,**{key:row[key] for key in ('topic','content','audience','effective_from','effective_until') if intent.get(key) is None}}
        return intent

    def validate_delivery(self, scope, message_id, reply, guard):
        if self.engine.policy.identify(scope) != guard['role'] or digest(reply) != guard['reply_hash']:
            raise EngineError('pilot_delivery_invalidated')
        store = self.engine.store
        composed = store.execute('''SELECT payload,expires_at FROM conversation_state WHERE environment_id=?
            AND channel=? AND channel_user_id=? AND chat_id=? AND state_key=?''',
            (*scope.key(),'i5-delivery:'+message_id)).fetchone()
        if composed:
            from app.core.contracts import Message
            data = json.loads(composed['payload'])
            if instant(composed['expires_at']) <= instant(self.engine.clock()):
                raise EngineError('pilot_delivery_invalidated')
            if data['document_reply'] is not None:
                self.engine.knowledge.validate_delivery(scope,message_id,data['document_reply'],has_evidence=True)
            message = Message(scope,message_id,self.engine.clock(),'delivery')
            found = self.engine.operations.contextual_guidance(message,{'topic':data['topic']})
            current = [{k:r[k] for k in ('guidance_id','version','content','effective_from','effective_until')}
                       for r in found.data.get('guidance',[])]
            if current != data['guidance']:
                raise EngineError('pilot_delivery_invalidated')
        if guard['code'] == 'pilot_document_conflict':
            cid = digest([scope.key(),message_id])
            call = store.execute('SELECT result FROM knowledge_calls WHERE environment_id=? AND call_id=?',
                                 (scope.environment_id,cid)).fetchone()
            if call is None:
                raise EngineError('pilot_delivery_invalidated')
            original = json.loads(call['result'])['data']['reply']
            self.engine.knowledge.validate_delivery(scope,message_id,original,has_evidence=True)
        if guard['code'] == 'reservation_confirmed':
            from app.core.contracts import Message
            receipt = store.execute('''SELECT operation_id FROM pilot_receipts WHERE environment_id=? AND channel=?
                AND channel_user_id=? AND chat_id=? AND message_id=?''',(*scope.key(),message_id)).fetchone()
            if receipt is None or receipt['operation_id'] is None:
                raise EngineError('pilot_delivery_invalidated')
            manager = guard['role'] == 'manager'
            self.engine.policy.authorize(scope,'operations.reconcile' if manager else 'reservation.read')
            message = Message(scope,'delivery_'+message_id,self.engine.clock(),'delivery')
            operation = self.engine.operations._row(message,receipt['operation_id'],manager=manager)
            with self.engine.operations.lock():
                result = self.engine.operations._verify_event(message,operation)
            if result.code != 'reservation_confirmed':
                raise EngineError('pilot_delivery_invalidated')

    def route(self, message):
        text = message.text.strip()
        try:
            phrase=words(text)
            context=self.dialog.context(message) if message.scope.channel=='telegram' else None
            clarification=self._clarification_context(message)
            replaced_proposal=None
            editing_action=None
            fragment=self.reservations.route_fragment(message,context)
            if fragment is not None:
                return fragment
            if text in ('/ajuda','/start','/help') or (phrase in ('olá','ola','oi','bom dia','boa tarde','boa noite','ajuda','como você pode me ajudar')
                    and (not context or context['kind']=='closed')):
                return 'pilot_help',('Sou o Alfredo, assistente experimental. Conte o que você precisa: consultar uma informação, '
                    'reservar um espaço ou enviar um pedido à administração. Vou perguntar apenas o que faltar '
                    'e pedir sua autorização antes de registrar ou enviar. Você pode responder normalmente por aqui. '
                    'Neste piloto não há cobrança nem alteração de sistemas oficiais.')
            literal_reply=bool(context and (context['kind']=='request_reply' or
                context['kind']=='clarification' and context.get('field') in ('response','content')) and not text.startswith('/'))
            literal_reply=literal_reply or bool(clarification and clarification['field'] in ('response','content') and not text.startswith('/'))
            legacy=text.startswith('/confirmar') or phrase in ('confirmo','confirmar','sim confirmo','confirmo e aceito a taxa')
            if context and context['kind']=='sync' and authorization_phrase(phrase):
                consent=permission(phrase,'sync')
                if consent is None:
                    data=self.dialog.get(message.scope,'sync:'+context['token'])
                    if not data or data['state']!='waiting':raise EngineError('confirmation_expired')
                    self.dialog.output(message,data,instant(data['expires_at']))
                    return 'pilot_sync_proposal','A pergunta é sobre atualizar os registros da planilha experimental. Você autoriza essa sincronização?'
                self.dialog.consume_sync(message,context['token'],'used' if consent else 'declined')
                if not consent:
                    return 'pilot_declined','Tudo bem. Mantive os registros pendentes e não sincronizei a planilha.'
                return self.render(self.engine.handle(message,'sync_operations',{}))
            if context and phrase in ('ok','okay','entendi') and context['kind']=='proposal':
                return self._repeat_proposal(message,context)
            if context and phrase in ('ok','okay','entendi') and context['kind']=='sync':
                data=self.dialog.get(message.scope,'sync:'+context['token'])
                if not data or data['state']!='waiting':
                    raise EngineError('confirmation_expired')
                self.dialog.output(message,data,instant(data['expires_at']))
                return 'pilot_sync_proposal','Para continuar: você autoriza sincronizar as atividades pendentes na planilha experimental?'
            if not literal_reply and (legacy or authorization_phrase(phrase)):
                if not legacy and message.scope.channel=='telegram' and (not context or context['kind']!='proposal'):
                    return 'pilot_authorization_missing','Não tenho um pedido aguardando sua autorização nesta conversa. O que você deseja fazer?'
                if text.startswith('/confirmar'):
                    text=' '.join(text.split())
                if text.startswith('/confirmar') and not re.fullmatch(r'/confirmar [a-f0-9-]{36}(?: ACEITO TAXA)?',text):
                    raise EngineError('explicit_confirmation_required')
                parts = text.split()
                oid = parts[1] if text.startswith('/confirmar ') and len(parts) >= 2 else None
                if oid is None and context and context['kind']=='proposal' and message.reply_to_message_id is not None:
                    oid=context['operation_id']
                rows = [r for r in self._pending(message) if oid is None or r['operation_id'] == oid]
                if len(rows) != 1:
                    raise EngineError('ambiguous_confirmation')
                row = rows[0]
                consent=True if text.startswith('/confirmar ') else permission(phrase,row['kind'])
                if consent is None:
                    return self._repeat_proposal(message,{'operation_id':row['operation_id']})
                if not consent:
                    if row['kind']=='reservation':self.reservations.close(message.scope)
                    return self.dialog.decline(message,row)
                action = 'confirm_operation' if row['source'] == 'pilot' else 'confirm'
                payload = {'explicit':True,'operation_id':row['operation_id'],'proposal_hash':row['proposal_hash']}
                if action == 'confirm_operation':
                    payload['accept_fee'] = text.endswith(' ACEITO TAXA') or bool(re.search(r'\baceito a taxa\b',phrase))
                result = self.engine.handle(message,action,payload)
                if result.code=='fee_acceptance_required':
                    expiry=self.engine.store.execute('SELECT expires_at FROM pilot_operations WHERE environment_id=? AND operation_id=?',
                        (message.scope.environment_id,row['operation_id'])).fetchone()
                    self.dialog.output(message,{'kind':'proposal','operation_id':row['operation_id'],
                        'proposal_hash':row['proposal_hash']},instant(expiry['expires_at']))
                return self._completed(message,result)
            if phrase in ('obrigado','obrigada','valeu','entendi','ok','okay') and not clarification and (not context or context['kind']=='closed'):
                return 'pilot_acknowledged','Por nada. Quando precisar, pode me contar por aqui.'
            commands = {'/relatorio':('operations_report',{}),'/solicitacoes':('request_status',{}),
                        '/sincronizar':('sync_operations',{})}
            if phrase in ('atualize a planilha','atualizar a planilha','quero atualizar a planilha',
                          'sincronize a planilha','quero sincronizar a planilha','pode atualizar a planilha'):
                return self._prepare_sync(message)
            if text in commands:
                action,payload = commands[text]
            elif re.fullmatch(r'/(?:reserva|reconciliar) [a-f0-9-]{36}',text):
                action = 'reservation_status' if text.startswith('/reserva ') else 'reconcile_operation'
                payload = {'operation_id':text.split()[1]}
            elif text.startswith('/orientacoes '):
                action,payload = 'contextual_guidance',{'topic':text.split(maxsplit=1)[1]}
            elif text=='/contexto' or re.match(r'/unidade(?:\s|$)',text) or text.startswith('/simular '):
                return None
            elif text.startswith('/'):
                return 'pilot_unknown_command','Não reconheci esse atalho da I5. Pode me contar em palavras o que você precisa; eu conduzo os próximos passos.'
            else:
                if self.interpreter is None:
                    return 'pilot_clarification_required','A interpretação natural não está habilitada nesta execução.'
                pending=clarification
                if context and context['kind']=='request_reply':
                    intent=self._request_reply(message,context)
                elif context and context['kind']=='clarification' and context.get('field') in ('response','content'):
                    intent={**context['intent'],context['field']:text,'clarification_field':None}
                elif pending and pending['field'] in ('response','content') and (phrase in YES or phrase in NO or phrase in ('ok','okay')):
                    # The asked-for response is literal text, not an operation approval.
                    # Still render a proposal and require a separate confirmation.
                    intent={**pending['intent'],pending['field']:text,'clarification_field':None}
                else:
                    if not pending and context and context['kind']=='proposal':
                        candidates=[row for row in self._pending(message) if row['operation_id']==context['operation_id']]
                        if len(candidates)==1:
                            pending={'intent':self._proposal_intent(message,candidates[0]),'field':'changes'}
                            if re.match(r'^(?:mude|altere|troque|corrija|na verdade|prefiro|quero mudar)\b',text,re.I):
                                replaced_proposal=candidates[0]
                                editing_action=pending['intent']['action']
                    intent=(self.interpreter.interpret(message,pending=pending) if pending
                            else self.interpreter.interpret(message))
                if intent['action']=='clarify':
                    requested=intent.get('requested_action')
                    if not requested:
                        return 'clarification_required',self.clarification(intent.get('clarification_field'))
                    # Completeness is validated locally, independently of the model's
                    # clarification flag. This can only propose; confirmation is separate.
                    intent={**intent,'action':requested}
                if pending and intent['action']==pending['intent']['action']:
                    previous=pending['intent']
                    for key,value in previous.items():
                        if key not in ('action','requested_action','clarification_field',pending['field']) and intent.get(key) is None:
                            intent={**intent,key:value}
                    # A follow-up may not invent a different existing target/version.
                    for key in ('request_id','guidance_id'):
                        if previous.get(key) and intent.get(key)!=previous[key] and str(intent.get(key)) not in message.text:
                            intent={**intent,key:previous[key]}
                    if previous.get('expected_version') is not None and not re.search(r'\bvers[aã]o(?:\s+atual)?[\s:]+\d+',message.text,re.I):
                        intent={**intent,'expected_version':previous['expected_version']}
                if intent['action']=='response':
                    if intent.get('response') and intent.get('content') and intent['response']!=intent['content']:
                        return self._ask(message,{**intent,'response':None,'content':None},'response')
                    if not intent.get('response') and intent.get('content'):
                        intent={**intent,'response':intent['content'],'content':None}
                intent=self._resolve_references(message,intent)
                if intent['action']=='availability':
                    data=self.reservations.state(message,context)
                    resource=intent.get('resource') or data.get('resource')
                    if not resource:return self._ask(message,intent,'resource')
                    return self.reservations.availability(message,{**data,'resource':resource})
                if intent['action']=='reservation' and message.scope.channel=='telegram':
                    return self.reservations.process(message,intent,context)
                if intent['action'] in ('reservation','guidance_create','guidance_correct'):
                    from app.channels.explicit_interval import explicit_interval
                    interval=explicit_interval(message.text,self.engine.config.timezone)
                    if interval is not None:
                        names=(('start','end') if intent['action']=='reservation'
                               else ('effective_from','effective_until'))
                        # An exact literal date range is deterministic source data,
                        # not a value to omit or rewrite probabilistically.
                        intent={**intent,**dict(zip(names,interval))}
                required={
                    'reservation':('resource','start','end'),
                    'request':('category','content'),
                    'response':('request_id','expected_version','response'),
                    'guidance_create':('topic','content','audience','effective_from','effective_until'),
                    'guidance_correct':('guidance_id','expected_version','topic','content','audience','effective_from','effective_until'),
                    'guidance_cancel':('guidance_id','expected_version'),
                    'guidance_read':('topic',),
                }.get(intent['action'],())
                missing=next((key for key in required if intent.get(key) is None or intent[key]==''),None)
                if missing:
                    return self._ask(message,intent,missing)
                if intent['action'] == 'documents':
                    if pending:
                        self._clear_clarification(message)
                    return self.documents(message,intent.get('topic'))
                action,payload = self.extract(message,intent)
                if pending:
                    self._clear_clarification(message)
            result = self.engine.handle(message,action,payload)
            self._remember_proposal(message,result)
            if replaced_proposal and intent['action']==editing_action and result.code in ('proposal','pilot_proposal'):
                self.dialog.decline(message,replaced_proposal)
            if action == 'contextual_guidance' and result.code == 'pilot_guidance' and result.data['guidance']:
                limited = [{k:r[k] for k in ('guidance_id','version','content','effective_from','effective_until')}
                           for r in result.data['guidance']]
                rendered = self.render(result)[1]
                self._save_composition(message,payload['topic'],rendered,None,limited)
            return self.render(result)
        except EngineError as error:
            if error.code=='guidance_choice_required' and 'intent' in locals():
                return self._ask(message,intent,'topic')
            return error.code,self.safe_error(error.code)

    def extract(self, message, i):
        kind = i['action']
        select = lambda *names: {k:i.get(k) for k in names}
        if kind == 'reservation':
            return 'propose_reservation',select('resource','start','end')
        if kind == 'request':
            return 'propose_request',select('category','content','urgent')
        if kind == 'response':
            return 'propose_response',select('request_id','expected_version','response')
        if kind == 'report':
            return 'operations_report',{}
        if kind == 'request_status':
            return 'request_status',({'request_id':i['request_id']} if i.get('request_id') else {})
        if kind == 'reservation_status':
            return 'reservation_status',select('operation_id')
        if kind == 'guidance_read':
            return 'contextual_guidance',select('topic')
        if kind.startswith('guidance_'):
            action = {'guidance_create':'propose_create','guidance_correct':'propose_correct','guidance_cancel':'propose_cancel'}.get(kind)
            if not action:
                raise EngineError('clarification_required')
            fields = select('guidance_id','expected_version') if kind != 'guidance_create' else {}
            if kind != 'guidance_cancel':
                fields.update(select('topic','content','audience','effective_from','effective_until'))
                fields['timezone'] = self.engine.config.timezone
                if fields['effective_from'] and fields['effective_until'] and instant(fields['effective_until'])<=instant(fields['effective_from']):
                    raise EngineError('guidance_invalid_interval')
            stable = str(uuid5(NAMESPACE_URL,canonical([message.scope.key(),message.message_id])))
            return action,{**fields,'operation_id':stable,'idempotency_key':stable}
        raise EngineError('clarification_required')

    def documents(self, message, topic):
        result = self.engine.handle(message,'query_documents',{})
        reply = result.data.get('reply','Não foi possível verificar a regra documental.')
        if result.code != 'knowledge_answer' or type(topic) is not str or not re.fullmatch('[a-z0-9_-]{1,64}',topic):
            return result.code,reply
        guidance = self.engine.handle(message,'contextual_guidance',{'topic':topic})
        entries = guidance.data.get('guidance',[])
        if not entries:
            return result.code,reply
        limited = [{k:r[k] for k in ('guidance_id','version','content','effective_from','effective_until')} for r in entries]
        if self.interpreter.compatible(message,reply,limited) != 'compatible':
            return 'pilot_document_conflict',reply+'\n\nHá orientação administrativa cuja compatibilidade exige esclarecimento da administração. Nenhuma regra foi alterada.'
        reply += '\n\nOrientação operacional da administração (não altera o regulamento):\n'+'\n'.join(r['content'] for r in limited)
        # Persist only the exact, filtered composition for later delivery revalidation.
        self._save_composition(message,topic,reply,result.data['reply'],limited)
        return 'pilot_contextual_answer',reply

    def _save_composition(self, message, topic, reply, document_reply, limited):
        with self.engine.store.transaction():
            self.engine.store.execute('''INSERT INTO conversation_state VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(environment_id,channel,channel_user_id,chat_id,state_key)
                DO UPDATE SET payload=excluded.payload,updated_at=excluded.updated_at,expires_at=excluded.expires_at''',
                (*message.scope.key(),'i5-delivery:'+message.message_id,canonical({'reply':reply,'topic':topic,
                 'document_reply':document_reply,'guidance':limited}),stamp(self.engine.clock()),
                 min(r['effective_until'] for r in limited)))

    def render(self, result):
        if result.status in ('rejected','error','blocked'):
            return result.code,self.safe_error(result.code)
        d = result.data
        if result.code in ('pilot_proposal','proposal'):
            from app.channels.operation_messages import proposal
            request=None
            if d['kind']=='response':
                row=self.engine.store.execute('SELECT content FROM pilot_requests WHERE environment_id=? AND request_id=?',
                                              (self.engine.config.environment_id,d['request_id'])).fetchone()
                request=row['content'] if row else None
            return result.code,proposal(d,self.engine.config.timezone,request)
        if result.code == 'reservation_confirmed':
            return result.code,'Pronto, sua reserva foi confirmada e verificada na Agenda experimental. Não haverá cobrança neste ensaio.'
        if result.code == 'pilot_confirmed':
            row=self.engine.store.execute('SELECT kind,proposal FROM pilot_operations WHERE environment_id=? AND operation_id=?',
                                          (self.engine.config.environment_id,d['operation_id'])).fetchone()
            if row and row['kind']=='response':
                return result.code,'Registrei sua resposta. Vou entregá-la ao morador por aqui.'
            if row and row['kind']=='request':
                forwarded=json.loads(row['proposal']).get('assigned_to')=='manager'
                return result.code,('Registrei seu pedido e o encaminhamento à administração. Aviso você por aqui quando houver resposta.'
                                    if forwarded else 'Registrei seu pedido. Ele está pendente de atendimento no piloto.')
            return result.code,'Pronto, registrei o pedido neste atendimento experimental.'
        if result.code in ('confirmed','already_confirmed'):
            return result.code,('Pronto, retirei a orientação de vigência e preservei seu histórico.' if d.get('status')=='cancelled'
                                else 'Pronto, registrei a orientação da administração. Ela não altera o regulamento.')
        if result.code == 'pilot_reconciliation_required':
            return result.code,'Ainda não consegui comprovar a reserva na Agenda. Não a considere confirmada. Vou manter o pedido em verificação, sem repetir a criação.'
        if result.status == 'conflict':
            reply = 'Intervalo indisponível ou conflito encontrado na Agenda. A reserva não foi confirmada; solicite outro intervalo.'
            if d.get('alternatives'):
                reply += '\nAlternativas consultadas na Agenda (sujeitas a nova verificação na confirmação):\n'+'\n'.join(
                    r['start']+' até '+r['end'] for r in d['alternatives'])
            return result.code,reply
        if result.code == 'pilot_requests':
            labels={'forwarded':'encaminhado à administração','resolved':'respondido','pending':'pendente de atendimento','received':'recebido','closed':'encerrado','failed':'com falha'}
            return result.code,'Pedidos neste atendimento experimental:\n'+ ('\n\n'.join(
                str(index)+'. '+r['content']+'\nSituação: '+labels.get(r['status'],r['status'])+
                ('\nResposta: '+r['response'] if r['response'] else '') for index,r in enumerate(d['requests'],1)) or 'Nenhum pedido encontrado.')
        if result.code == 'pilot_report':
            from app.channels.operation_messages import report
            return result.code,report(d)
        if result.code == 'pilot_guidance':
            from app.channels.operation_messages import local_time
            return result.code,d['notice']+'\n'+('\n'.join(r['content']+'\nVale de '+local_time(r['effective_from'],self.engine.config.timezone)+' até '+local_time(r['effective_until'],self.engine.config.timezone)
                for r in d['guidance']) or 'Nenhuma orientação vigente para este assunto.')
        if result.code == 'pilot_sync':
            return result.code,'Sheets: '+str(d['synced'])+' registro(s) verificado(s); '+str(d['pending'])+' pendente(s).'
        return result.code,'Operação em estado '+d.get('state',result.status)+'.'

    @staticmethod
    def clarification(field):
        return {
            'topic':'Qual é o assunto da orientação administrativa?',
            'content':'Qual orientação ou solicitação você deseja registrar?',
            'audience':'A orientação é para os moradores ou apenas para a síndica?',
            'effective_from':'Em que data e horário a orientação começa a valer, no horário de Brasília?',
            'effective_until':'Até que data e horário a orientação vale, no horário de Brasília?',
            'resource':'Qual recurso você deseja reservar?',
            'start':'Em que data e horário a reserva deve começar?',
            'end':'Em que data e horário a reserva deve terminar?',
            'category':'Esse pedido precisa de uma decisão da administração ou é uma consulta de informação?',
            'guidance_id':'Qual orientação você quer alterar? Pode me dizer o assunto.',
            'request_id':'A qual pedido você quer responder? Pode responder diretamente à mensagem desse pedido.',
            'expected_version':'Os dados do pedido precisam ser conferidos novamente antes de continuar. Qual pedido você quer tratar?',
            'response':'Qual resposta você deseja registrar para a solicitação?'
        }.get(field,'Você deseja cadastrar uma orientação, solicitar uma reserva ou consultar uma informação?')

    @staticmethod
    def safe_error(code):
        return {
            'unauthorized':'Seu perfil não tem permissão para esta operação.',
            'explicit_confirmation_required':'Ainda não recebi uma autorização válida. Responda normalmente à pergunta sobre os dados do pedido; nada foi executado.',
            'clarification_required':'Informe assunto, conteúdo, público e as datas/horários de início e fim da orientação. Nenhuma orientação foi ativada.',
            'guidance_invalid_interval':'O fim da vigência precisa ser posterior ao início. Confira as datas e os anos; qual é a data e o horário corretos de término?',
            'ambiguous_confirmation':'Tenho mais de um pedido ou nenhum pedido válido aguardando autorização. Responda diretamente à mensagem do pedido que deseja autorizar. Ainda não executei.',
            'confirmation_expired':'O prazo dessa autorização terminou. Podemos preparar os dados novamente antes de executar.',
            'fee_acceptance_required':'Você aceita a taxa informativa apresentada e autoriza a reserva? Não haverá cobrança neste ensaio.',
            'document_rule_requires_review':'Não há regra verificada suficiente para reservar. Solicite esclarecimento à administração.',
            'document_rule_outdated':'A fonte da regra exige revalidação. A reserva está bloqueada.',
            'reservation_conditions_not_met':'O intervalo não atende às condições documentadas ou à janela autorizada do piloto.',
            'stale_version':'Esse pedido mudou enquanto conversávamos. Preciso mostrar os dados atuais antes de pedir uma nova autorização.',
            'request_not_respondable':'Esse pedido já foi atendido ou não está aguardando resposta da administração. Posso ajudar com outro pedido?',
            'request_choice_required':'Há mais de um pedido para atender. Responda diretamente à mensagem do pedido que deseja tratar, para eu não trocar as respostas.',
            'guidance_choice_required':'Qual orientação você deseja alterar? Diga o assunto para eu localizar a orientação correta.',
            'operation_resource_changed':'O destino experimental mudou. Preciso preparar uma nova autorização antes de continuar.',
            'guidance_expired':'A vigência dessa orientação terminou. Podemos preparar uma nova orientação com datas atuais.',
            'reservation_window_closed':'A janela autorizada deste ensaio terminou. A configuração precisa ser revalidada antes de consultar novas datas; não vou inventar uma disponibilidade.',
            'proposal_changed':'Os dados mudaram desde a pergunta de autorização. Precisamos conferir os dados atuais antes de continuar.',
            'operation_not_confirmable':'Essa autorização já foi encerrada. Não vou executar outra operação com ela.',
            'budget_blocked':'O orçamento estimado bloqueia novas interpretações. Nenhuma operação foi executada.',
        }.get(code,'Não consegui concluir esta etapa com segurança. Pode me contar o que deseja fazer ou ajustar para eu esclarecer o pedido antes de continuar?')
