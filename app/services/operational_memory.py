"""Administrative guidance lifecycle. Called inside the orchestrator's transaction.

Content is untrusted data, never Python, a prompt, a permission, or a tool command.
"""
from datetime import timedelta
import json
import re
from uuid import UUID, uuid4
from app.core.contracts import EngineError, canonical, digest, instant, stamp, Result, Message, Scope


def identifier(value):
    try:
        if type(value) is not str or str(UUID(value)) != value:
            raise ValueError
        return value
    except (ValueError, TypeError, AttributeError):
        raise EngineError('invalid_identifier') from None


def exact(payload, required, optional=()):
    if type(payload) is not dict or not set(required) <= set(payload) or not set(payload) <= set(required) | set(optional):
        raise EngineError('invalid_input')


class OperationalMemory:
    def __init__(self, store, policy, config):
        self.store, self.policy, self.config = store, policy, config

    def _request(self, scope, operation_id):
        row = self.store.execute("""SELECT * FROM requests_state WHERE environment_id=? AND
            operation_id=? AND channel=? AND channel_user_id=? AND chat_id=?""",
            (scope.environment_id,operation_id,scope.channel,scope.channel_user_id,scope.chat_id)).fetchone()
        if row is None:
            raise EngineError('operation_not_found')
        return row

    def _current(self, env, guidance_id):
        row = self.store.execute("""SELECT v.*,g.status AS current_status,g.retired_at
            FROM operational_guidance g JOIN operational_guidance_revisions v
            ON v.environment_id=g.environment_id AND v.guidance_id=g.guidance_id AND v.version=g.current_version
            WHERE g.environment_id=? AND g.guidance_id=?""", (env,guidance_id)).fetchone()
        if row is None:
            raise EngineError('guidance_not_found')
        return row

    def _fields(self, data):
        for name in ('topic','content','audience','effective_from','effective_until','timezone'):
            if name not in data or data[name] is None:
                raise EngineError('clarification_required')
        if (type(data['topic']) is not str or not re.fullmatch(r'[a-z0-9_-]{1,64}',data['topic'])
                or type(data['content']) is not str or not data['content'].strip()
                or len(data['content']) > self.config.limits['max_message_chars']):
            raise EngineError('invalid_input')
        if data['audience'] not in ('residents','managers') or data['timezone'] != self.config.timezone:
            raise EngineError('clarification_required')
        start, end = instant(data['effective_from']), instant(data['effective_until'])
        if end <= start:
            raise EngineError('clarification_required')
        return {**{k:data[k] for k in ('topic','content','audience','timezone')},
                'effective_from':stamp(start),'effective_until':stamp(end)}

    def propose(self, message, kind, payload, now):
        role = self.policy.authorize(message.scope,'guidance.' + kind)
        required = ('operation_id','idempotency_key')
        if kind == 'create':
            required += ('topic','content','audience','effective_from','effective_until','timezone')
        elif kind == 'correct':
            required += ('guidance_id','expected_version','topic','content','audience','effective_from','effective_until','timezone')
        elif kind == 'cancel':
            required += ('guidance_id','expected_version')
        else:
            raise EngineError('invalid_action')
        exact(payload,required,('document_conflict',))
        if payload.get('document_conflict','not_checked') not in ('not_checked','reported'):
            raise EngineError('invalid_input')
        if payload.get('document_conflict') == 'reported':
            raise EngineError('document_conflict_requires_review')
        operation_id = identifier(payload['operation_id'])
        idempotency_key = identifier(payload['idempotency_key'])
        # Check identity/ownership before revealing idempotent results.
        existing = self.store.execute("""SELECT * FROM requests_state WHERE environment_id=?
            AND (operation_id=? OR idempotency_key=?)""",
            (message.scope.environment_id,operation_id,idempotency_key)).fetchone()
        input_hash = digest({'kind':kind,'payload':payload,'scope':message.scope.key()})
        if existing:
            self._request(message.scope,existing['operation_id'])
            draft = self._draft(message.scope,existing['operation_id'])
            if (existing['operation_id'] != operation_id or existing['idempotency_key'] != idempotency_key
                    or draft is None or draft['input_hash'] != input_hash):
                raise EngineError('idempotency_conflict')
            if existing['state'] == 'confirmed':
                return Result('success','already_confirmed',json.loads(existing['result']))
            if existing['state'] != 'awaiting_confirmation' or existing['expires_at'] <= stamp(now):
                raise EngineError('confirmation_expired')
            return Result('awaiting_confirmation','proposal',self._summary(draft))
        if kind == 'create':
            fields = self._fields(payload)
            guidance_id, expected = str(uuid4()), None
        else:
            guidance_id = identifier(payload['guidance_id'])
            expected = payload['expected_version']
            if type(expected) is not int or expected < 1:
                raise EngineError('invalid_version')
            current = self._current(message.scope.environment_id,guidance_id)
            if current['version'] != expected:
                raise EngineError('stale_version')
            if current['current_status'] != 'active' or instant(current['effective_until']) <= now:
                raise EngineError('guidance_not_active')
            fields = self._fields(payload if kind == 'correct' else dict(current))
        if instant(fields['effective_until']) <= now:
            raise EngineError('guidance_expired')
        expires_at = stamp(instant(message.received_at) + timedelta(seconds=self.config.limits['confirmation_seconds']))
        if expires_at <= stamp(now):
            raise EngineError('confirmation_expired')
        draft = {**fields,'kind':kind,'operation_id':operation_id,'idempotency_key':idempotency_key,
                 'guidance_id':guidance_id,'expected_version':expected,'scope':list(message.scope.key()),
                 'original_message_at':stamp(message.received_at),'expires_at':expires_at,
                 'document_check':'not_checked_in_i1','input_hash':input_hash}
        proposal_hash = digest(draft)
        draft['proposal_hash'] = proposal_hash
        self.store.execute("""INSERT INTO requests_state
            (environment_id,operation_id,idempotency_key,channel,channel_user_id,chat_id,kind,guidance_id,
             expected_version,proposal_hash,state,created_at,updated_at,expires_at)
             VALUES (?,?,?,?,?,?,?,?,?,?,'received',?,?,?)""",
            (*message.scope.key()[:1],operation_id,idempotency_key,message.scope.channel,
             message.scope.channel_user_id,message.scope.chat_id,kind,guidance_id,expected,
             proposal_hash,stamp(now),stamp(now),expires_at))
        self.store.audit(message,role,'guidance.'+kind,'success',now,operation_id,guidance_id,
                         expected,previous=None,next_state='received')
        self.store.execute("""INSERT INTO conversation_state
            (environment_id,channel,channel_user_id,chat_id,state_key,payload,updated_at,expires_at)
            VALUES (?,?,?,?,?,?,?,?)""",
            (*message.scope.key(),'proposal:'+operation_id,canonical(draft),stamp(now),
             stamp(now+timedelta(days=self.config.retention['conversation_days']))))
        self.store.execute("""UPDATE requests_state SET state='awaiting_confirmation'
            WHERE environment_id=? AND operation_id=?""", (message.scope.environment_id,operation_id))
        self.store.audit(message,role,'guidance.'+kind,'success',now,operation_id,guidance_id,
                         expected,previous='received',next_state='awaiting_confirmation')
        return Result('awaiting_confirmation','proposal',self._summary(draft))

    def _draft(self, scope, operation_id):
        row = self.store.execute("""SELECT payload FROM conversation_state WHERE environment_id=?
            AND channel=? AND channel_user_id=? AND chat_id=? AND state_key=?""",
            (*scope.key(),'proposal:'+operation_id)).fetchone()
        return json.loads(row['payload']) if row else None

    def _summary(self, draft):
        return {k:draft[k] for k in ('operation_id','guidance_id','kind','expected_version','topic',
                'content','audience','effective_from','effective_until','timezone','expires_at',
                'proposal_hash','document_check','scope','original_message_at')}

    def confirm(self, message, payload, now):
        exact(payload,('explicit',),('operation_id','proposal_hash'))
        if payload['explicit'] is not True:
            raise EngineError('explicit_confirmation_required')
        self.policy.authorize(message.scope,'context.read')
        operation_id = payload.get('operation_id')
        if operation_id is None:
            if payload.get('proposal_hash') is not None:
                raise EngineError('invalid_input')
            pending = self.store.execute("""SELECT operation_id FROM requests_state WHERE environment_id=?
                AND channel=? AND channel_user_id=? AND chat_id=? AND state='awaiting_confirmation'
                AND expires_at>?""", (*message.scope.key(),stamp(now))).fetchall()
            if len(pending) != 1:
                raise EngineError('ambiguous_confirmation')
            operation_id = pending[0]['operation_id']
        else:
            identifier(operation_id)
            if type(payload.get('proposal_hash')) is not str:
                raise EngineError('confirmation_digest_required')
        request = self._request(message.scope,operation_id)
        role = self.policy.authorize(message.scope,'guidance.'+request['kind'])
        draft = self._draft(message.scope,operation_id)
        if not draft:
            raise EngineError('proposal_not_found')
        submitted_hash = payload.get('proposal_hash',draft['proposal_hash'])
        draft_without_hash = {k:v for k,v in draft.items() if k != 'proposal_hash'}
        if (submitted_hash != request['proposal_hash'] or digest(draft_without_hash) != request['proposal_hash']
                or draft['scope'] != list(message.scope.key())):
            raise EngineError('proposal_changed')
        if request['state'] == 'confirmed':
            return Result('success','already_confirmed',json.loads(request['result']))
        if request['state'] != 'awaiting_confirmation':
            raise EngineError('operation_not_confirmable')
        if stamp(now) >= request['expires_at']:
            raise EngineError('confirmation_expired')
        if instant(draft['effective_until']) <= now:
            raise EngineError('guidance_expired')
        current = None
        expected = request['expected_version']
        if request['kind'] != 'create':
            current = self._current(message.scope.environment_id,request['guidance_id'])
            if current['version'] != expected:
                raise EngineError('stale_version')
            if current['current_status'] != 'active' or instant(current['effective_until']) <= now:
                raise EngineError('guidance_not_active')
        # Revalidate immediately before writing. Authorization never comes from draft content.
        role = self.policy.authorize(message.scope,'guidance.'+request['kind'])
        self.store.execute("""UPDATE requests_state SET state='committing',updated_at=?
            WHERE environment_id=? AND operation_id=?""", (stamp(now),message.scope.environment_id,operation_id))
        self.store.audit(message,role,'confirm','success',now,operation_id,request['guidance_id'],
                         expected,previous='awaiting_confirmation',next_state='committing')
        version = 1 if expected is None else expected + 1
        status = 'cancelled' if request['kind'] == 'cancel' else 'active'
        env, gid = message.scope.environment_id, request['guidance_id']
        reference = digest({'scope':message.scope.key(),'message_id':message.message_id})
        self.store.execute("""INSERT INTO operational_guidance_revisions
            (environment_id,guidance_id,version,operation_id,author_channel_user_id,topic,content,audience,
             effective_from,effective_until,timezone,status,confirmation_at,confirmation_ref,proposal_hash,
             supersedes_version,created_at,updated_at)
             VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (env,gid,version,operation_id,message.scope.channel_user_id,draft['topic'],draft['content'],
             draft['audience'],draft['effective_from'],draft['effective_until'],draft['timezone'],status,
             stamp(now),reference,request['proposal_hash'],expected,stamp(now),stamp(now)))
        if current is None:
            self.store.execute("""INSERT INTO operational_guidance
                (environment_id,guidance_id,current_version,status,created_at,updated_at)
                VALUES (?,?,?,?,?,?)""", (env,gid,version,status,stamp(now),stamp(now)))
        else:
            count = self.store.execute("""UPDATE operational_guidance SET current_version=?,status=?,
                updated_at=?,retired_at=? WHERE environment_id=? AND guidance_id=? AND current_version=? AND status='active'""",
                (version,status,stamp(now),stamp(now) if status=='cancelled' else None,env,gid,expected)).rowcount
            if count != 1:
                raise EngineError('stale_version')
        data = dict(operation_id=operation_id,guidance_id=gid,version=version,status=status)
        self.store.execute("""UPDATE requests_state SET state='confirmed',result=?,updated_at=?,closed_at=?
            WHERE environment_id=? AND operation_id=?""", (canonical(data),stamp(now),stamp(now),env,operation_id))
        self.store.audit(message,role,'guidance.'+request['kind'],'success',now,operation_id,gid,version,
                         previous=current['current_status'] if current else 'draft',
                         next_state=status,confirmation_ref=reference)
        self.store.audit(message,role,'confirm','success',now,operation_id,gid,version,
                         previous='committing',next_state='confirmed',confirmation_ref=reference)
        return Result('success','confirmed',data)

    def find(self, message, payload, now):
        role = self.policy.authorize(message.scope,'guidance.read')
        exact(payload,('topic',),('document_conflict',))
        if type(payload['topic']) is not str or not re.fullmatch(r'[a-z0-9_-]{1,64}',payload['topic']):
            raise EngineError('invalid_input')
        conflict = payload.get('document_conflict','not_checked')
        if conflict not in ('not_checked','reported'):
            raise EngineError('invalid_input')
        if conflict == 'reported':
            return Result('conflict','document_conflict_requires_review',
                          {'guidance':[],'document_check':'not_checked_in_i1'})
        rows = self.store.execute("""SELECT v.guidance_id,v.version,v.topic,v.content,v.audience,
            v.effective_from,v.effective_until,v.timezone FROM operational_guidance g
            JOIN operational_guidance_revisions v ON v.environment_id=g.environment_id
            AND v.guidance_id=g.guidance_id AND v.version=g.current_version
            WHERE g.environment_id=? AND g.status='active' AND v.status='active' AND v.confirmation_at IS NOT NULL
            AND v.effective_from<=? AND v.effective_until>? AND v.topic=?
            AND (v.audience='residents' OR ?='manager') ORDER BY v.guidance_id LIMIT 20""",
            (message.scope.environment_id,stamp(now),stamp(now),payload['topic'],role)).fetchall()
        return Result('success','guidance',{'guidance':[dict(r) for r in rows],
                      'source':'orienta??o comunicada pela administra??o',
                      'document_check':'not_checked_in_i1','content_is_untrusted_data':True})

    def history(self, message, payload, now):
        self.policy.authorize(message.scope,'guidance.history')
        exact(payload,('guidance_id',))
        gid = identifier(payload['guidance_id'])
        current = self._current(message.scope.environment_id,gid)
        current_status = current['current_status']
        if current_status == 'active' and instant(current['effective_until']) <= now:
            current_status = 'expired'
        rows = self.store.execute("""SELECT * FROM operational_guidance_revisions
            WHERE environment_id=? AND guidance_id=? ORDER BY version""",
            (message.scope.environment_id,gid)).fetchall()
        return Result('success','history',{'revisions':[dict(r) for r in rows],
                      'current_status':current_status,'current_version':current['version']})

    def expire(self, environment_id, now):
        """Logical expiration only. Immutable revision retains the status at confirmation."""
        rows = self.store.execute("""SELECT g.guidance_id,g.current_version,v.effective_until FROM operational_guidance g
            JOIN operational_guidance_revisions v ON v.environment_id=g.environment_id
            AND v.guidance_id=g.guidance_id AND v.version=g.current_version
            WHERE g.environment_id=? AND g.status='active' AND v.effective_until<=?""",
            (environment_id,stamp(now))).fetchall()
        for row in rows:
            self.store.execute("""UPDATE operational_guidance SET status='expired',retired_at=?,updated_at=?
                WHERE environment_id=? AND guidance_id=?""",
                (row['effective_until'],stamp(now),environment_id,row['guidance_id']))
            msg = Message(Scope(environment_id,'local',0,0),'expiry',now,row['guidance_id'])
            self.store.audit(msg,'system','expiry','success',now,entity_id=row['guidance_id'],
                version=row['current_version'],previous='active',next_state='expired')
        return len(rows)
