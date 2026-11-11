"""One local entry point for structured inputs; no channel or network code."""
from datetime import timedelta
import json
import logging
import re
import sqlite3
from app.core.contracts import EngineError, Message, Scope, Result, canonical, digest, instant, stamp, utcnow
from app.core.policy import Policy
from app.services.operational_memory import OperationalMemory, exact

LOG = logging.getLogger('alfredo')
PERMISSIONS = {
    'propose_create':'guidance.create', 'propose_correct':'guidance.correct',
    'propose_cancel':'guidance.cancel', 'confirm':'context.read',
    'find_guidance':'guidance.read', 'guidance_history':'guidance.history',
    'get_context':'context.read','set_context':'context.write',
    'query_documents':'knowledge.read',
}
READ_ACTIONS = {'find_guidance','guidance_history','get_context'}


class Orchestrator:
    def __init__(self, config, store, clock=utcnow, *, knowledge=None):
        self.config, self.store, self.clock = config, store, clock
        self.policy = Policy(config)
        self.memory = OperationalMemory(store,self.policy,config)
        self.knowledge = knowledge

    def startup(self):
        now = instant(self.clock())
        recovered = self.store.recover(self.config.environment_id,now)
        with self.store.transaction():
            expired = self.memory.expire(self.config.environment_id,now)
        return {'recovered':recovered,'expired':expired}

    def _validate(self, message, action, payload, now):
        if not isinstance(message,Message) or type(action) is not str or action not in PERMISSIONS or type(payload) is not dict:
            raise EngineError('invalid_input')
        for value in (message.message_id,message.correlation_id):
            if type(value) is not str or not re.fullmatch(r'[a-zA-Z0-9_-]{1,128}',value):
                raise EngineError('invalid_input')
        if message.update_id is not None and (type(message.update_id) is not str
                or not re.fullmatch(r'[a-zA-Z0-9_-]{1,128}',message.update_id)):
            raise EngineError('invalid_input')
        if type(message.text) is not str or len(message.text)>self.config.limits['max_message_chars']:
            raise EngineError('input_limit')
        try:
            serialized = canonical(payload)
        except (TypeError, ValueError, RecursionError):
            raise EngineError('invalid_input') from None
        if len(serialized) > self.config.limits['max_message_chars']*2:
            raise EngineError('input_limit')
        received = instant(message.received_at)
        if received > now + timedelta(seconds=30):
            raise EngineError('future_message')
        return self.policy.authorize(message.scope,PERMISSIONS[action])

    def handle(self, message, action, payload):
        now, role = instant(self.clock()), 'unknown'
        try:
            if isinstance(message,Message):
                role = self.policy.identify(message.scope)
            role = self._validate(message,action,payload,now)
            if action == 'query_documents':
                exact(payload,())
                if self.knowledge is None:
                    return Result('blocked','knowledge_not_enabled',
                                  {'reply':'A consulta documental não está habilitada nesta execução.'})
                result = self.knowledge.answer(message)
                with self.store.transaction():
                    self.store.audit(message,role,action,result.code,now)
                return result
            request_hash = digest({'scope':message.scope.key(),'message_id':message.message_id,
                'update_id':message.update_id,'received_at':stamp(message.received_at),
                'text':message.text,'action':action,'payload':payload})
            with self.store.transaction():
                existing = self.store.execute("""SELECT * FROM processed_messages WHERE environment_id=?
                    AND channel=? AND ((channel_user_id=? AND chat_id=? AND message_id=?)
                    OR (update_id IS NOT NULL AND update_id=?))""",
                    (*message.scope.key(),message.message_id,message.update_id)).fetchone()
                if existing:
                    if existing['request_hash'] != request_hash:
                        raise EngineError('message_identity_conflict')
                    if action not in READ_ACTIONS:
                        # Confirmation privileges are revalidated even for a cached message.
                        if action == 'confirm' and existing['operation_id']:
                            r = self.memory._request(message.scope,existing['operation_id'])
                            self.policy.authorize(message.scope,'guidance.'+r['kind'])
                        cached = json.loads(existing['result'])
                        return Result(**cached)
                else:
                    count = self.store.execute("""SELECT count(*) FROM processed_messages WHERE
                        environment_id=? AND channel=? AND channel_user_id=? AND chat_id=? AND created_at>?""",
                        (*message.scope.key(),stamp(now-timedelta(minutes=1)))).fetchone()[0]
                    if count >= self.config.limits['messages_per_minute']:
                        raise EngineError('rate_limit')
                if action.startswith('propose_'):
                    result = self.memory.propose(message,action[8:],payload,now)
                elif action == 'confirm':
                    result = self.memory.confirm(message,payload,now)
                elif action == 'find_guidance':
                    result = self.memory.find(message,payload,now)
                elif action == 'guidance_history':
                    result = self.memory.history(message,payload,now)
                elif action == 'set_context':
                    exact(payload,('context',))
                    # Narrow context contract prevents hidden commands and copied guidance.
                    context = payload['context']
                    exact(context,(),('unit_reference','request_reference'))
                    if any(type(v) is not str or len(v)>64 for v in context.values()):
                        raise EngineError('invalid_input')
                    self.store.execute("""INSERT INTO conversation_state
                        (environment_id,channel,channel_user_id,chat_id,state_key,payload,updated_at,expires_at)
                        VALUES (?,?,?,?,'context',?,?,?) ON CONFLICT
                        (environment_id,channel,channel_user_id,chat_id,state_key)
                        DO UPDATE SET payload=excluded.payload,updated_at=excluded.updated_at,expires_at=excluded.expires_at""",
                        (*message.scope.key(),canonical(context),stamp(now),
                         stamp(now+timedelta(days=self.config.retention['conversation_days']))))
                    result = Result('success','context_saved')
                else:
                    exact(payload,())
                    row = self.store.execute("""SELECT payload FROM conversation_state WHERE environment_id=?
                        AND channel=? AND channel_user_id=? AND chat_id=? AND state_key='context' AND expires_at>?""",
                        (*message.scope.key(),stamp(now))).fetchone()
                    result = Result('success','context',{'context':json.loads(row['payload']) if row else {}})
                if not existing:
                    self.store.execute("""INSERT INTO processed_messages
                        (environment_id,channel,channel_user_id,chat_id,message_id,update_id,request_hash,operation_id,result,created_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?)""",
                        (*message.scope.key(),message.message_id,message.update_id,request_hash,
                         result.data.get('operation_id'),canonical(result.as_dict()),stamp(now)))
                self.store.audit(message,role,action,'success',now)
                return result
        except EngineError as error:
            self._failure(message,role,action,error.code,now)
            return Result('rejected',error.code)
        except (sqlite3.Error, OSError):
            self._failure(message,role,action,'storage_error',now)
            return Result('error','storage_error')

    def _failure(self, message, role, action, code, now):
        # Fixed errors only. No exception repr, SQL parameters, text, or secret values.
        LOG.warning('operation_rejected code=%s',code)
        if isinstance(message,Message):
            # Audit remains in the configured environment, with bounded identity types.
            scope = message.scope
            uid = scope.channel_user_id if isinstance(scope,Scope) and type(scope.channel_user_id) is int else 0
            chat = scope.chat_id if isinstance(scope,Scope) and type(scope.chat_id) is int else 0
            channel = scope.channel if isinstance(scope, Scope) and scope.channel in ('local','telegram') else 'local'
            message = Message(Scope(self.config.environment_id,channel,uid,chat),
                              'rejected',now,message.correlation_id)
            try:
                with self.store.transaction():
                    self.store.audit(message,role,action if type(action) is str and action in PERMISSIONS else 'invalid',
                                     'rejected',now,safe_error=code)
            except (sqlite3.Error,EngineError):
                LOG.error('audit_unavailable')
