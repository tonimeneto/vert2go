"""Real I4 usage, durable reservations and conservative storage estimates."""
from datetime import timedelta
from decimal import Decimal, ROUND_CEILING
import json
from app.ai.client import LocalBudget, money
from app.core.contracts import EngineError, canonical, digest, instant, stamp, utcnow


class RuntimeBudget(LocalBudget):
    def assess(self, estimated_next_brl='0', at=None):
        result = super().assess(estimated_next_brl, at)
        uncertain = self.store.execute("SELECT 1 FROM knowledge_calls WHERE environment_id=? AND state IN ('running','uncertain') LIMIT 1",
                                       (self.config.environment_id,)).fetchone()
        if uncertain:
            result.update(allowed=False, reason='openai_usage_uncertain')
        return result

    def estimate(self, kind):
        k, cfg = self.config.knowledge, self.config.openai
        if kind == 'answer':
            usd = (Decimal(k.limits['max_input_tokens'])*cfg['input_usd_per_million']/1000000 +
                   Decimal(k.limits['max_output_tokens'])*cfg['output_usd_per_million']/1000000 +
                   k.prices['search_usd_per_call'])
        else:
            # Conservative 31-day forecast for the configured storage cap, no free quota presumed.
            usd = Decimal(k.limits['max_storage_bytes'])/1000000000*k.prices['storage_usd_per_gb_day']*31
        return usd*cfg['usd_brl']

    def _record(self, usage_id, at, inputs=0, outputs=0, searches=0, storage_usd=Decimal(0)):
        k, cfg = self.config.knowledge, self.config.openai
        usd = (Decimal(inputs)*cfg['input_usd_per_million']/1000000 +
               Decimal(outputs)*cfg['output_usd_per_million']/1000000 +
               Decimal(searches)*k.prices['search_usd_per_call']+storage_usd)
        brl = (usd*cfg['usd_brl']).quantize(Decimal('.000001'), rounding=ROUND_CEILING)
        assumption = {key: str(value) for key,value in cfg.items()} | {
            'simulation': False, 'knowledge_prices': {key:str(value) for key,value in k.prices.items()},
            'storage_free_quota_assumed': False}
        payload = digest({'inputs':inputs,'outputs':outputs,'searches':searches,
                          'storage':str(storage_usd),'assumption':assumption})
        old = self.store.execute('SELECT payload_hash FROM usage_ledger WHERE environment_id=? AND usage_id=?',
                                 (self.config.environment_id,usage_id)).fetchone()
        if old:
            if old['payload_hash'] != payload:
                raise EngineError('usage_identity_conflict')
            return
        self.store.execute('''INSERT INTO usage_ledger VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (self.config.environment_id,usage_id,self.period(at),stamp(at),k.model,inputs,outputs,searches,
             str(storage_usd),str(usd),str(brl),1,canonical(assumption),payload))

    def storage(self, store_id, usage_bytes):
        if type(usage_bytes) is not int or usage_bytes < 0:
            raise EngineError('openai_storage_measurement_missing')
        now, env = instant(self.clock()), self.config.environment_id
        with self.store.transaction():
            row = self.store.execute('SELECT * FROM knowledge_storage WHERE environment_id=? AND vector_store_id=?',
                                     (env,store_id)).fetchone()
            if row:
                previous = instant(row['accounted_at'])
                if now < previous:
                    raise EngineError('knowledge_clock_invalid')
                # Split elapsed time by local billing month, including time with the app stopped.
                from zoneinfo import ZoneInfo
                from datetime import datetime
                cursor = previous
                while cursor < now:
                    local = cursor.astimezone(ZoneInfo(self.config.timezone))
                    year, month = (local.year+1,1) if local.month == 12 else (local.year,local.month+1)
                    boundary = datetime(year,month,1,tzinfo=local.tzinfo).astimezone(cursor.tzinfo)
                    end = min(now,boundary)
                    days = Decimal(str((end-cursor).total_seconds()))/86400
                    usd = Decimal(max(usage_bytes,row['usage_bytes']))/1000000000*days*self.config.knowledge.prices['storage_usd_per_gb_day']
                    self._record('storage_'+digest([store_id,stamp(cursor),stamp(end)]),cursor,storage_usd=usd)
                    cursor = end
            self.store.execute('''INSERT INTO knowledge_storage VALUES (?,?,?,?,?)
                ON CONFLICT(environment_id,vector_store_id) DO UPDATE SET
                usage_bytes=excluded.usage_bytes,accounted_at=excluded.accounted_at,checked_at=excluded.checked_at''',
                (env,store_id,usage_bytes,stamp(now),stamp(now)))
        if usage_bytes > self.config.knowledge.limits['max_storage_bytes']:
            raise EngineError('knowledge_storage_limit')

    def begin(self, call_id, kind, scope_hash, request_hash):
        now, env = instant(self.clock()), self.config.environment_id
        with self.store.transaction():
            old = self.store.execute('SELECT * FROM knowledge_calls WHERE environment_id=? AND call_id=?',
                                     (env,call_id)).fetchone()
            if old:
                if (old['request_hash'],old['scope_hash'],old['kind']) != (request_hash,scope_hash,kind):
                    raise EngineError('message_identity_conflict')
                if old['state'] != 'failed':
                    return dict(old)
            # Refuse fictitious prior usage as a basis for real billing decisions.
            rows = self.store.execute('SELECT assumption FROM usage_ledger WHERE environment_id=?', (env,)).fetchall()
            if any(json.loads(r['assumption']).get('simulation') is True for r in rows):
                raise EngineError('knowledge_simulated_usage_present')
            estimate = self.estimate(kind)
            assessment = self.assess(estimate, now)
            if not assessment['allowed']:
                raise EngineError(assessment['reason'])
            if old:
                self.store.execute('''UPDATE knowledge_calls SET state='running',result=NULL,remote_id=NULL,
                    reserved_brl=?,created_at=?,updated_at=?,expires_at=? WHERE environment_id=? AND call_id=?''',
                    (str(estimate),stamp(now),stamp(now),stamp(now+timedelta(days=self.config.retention['deduplication_days'])),env,call_id))
            else:
                self.store.execute('''INSERT INTO knowledge_calls VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
                    (env,call_id,request_hash,kind,'running',scope_hash,None,None,str(estimate),stamp(now),stamp(now),
                     stamp(now+timedelta(days=self.config.retention['deduplication_days']))))
        return None

    def complete(self, call_id, result, remote_id=None, *, inputs=0, outputs=0, searches=0):
        if any(type(v) is not int or v < 0 for v in (inputs,outputs,searches)):
            raise EngineError('openai_usage_missing')
        with self.store.transaction():
            row = self.store.execute('SELECT * FROM knowledge_calls WHERE environment_id=? AND call_id=?',
                                     (self.config.environment_id,call_id)).fetchone()
            if not row or row['state'] not in ('running','uncertain'):
                raise EngineError('knowledge_call_state_invalid')
            self._record(call_id, instant(row['created_at']), inputs, outputs, searches)
            self.store.execute('''UPDATE knowledge_calls SET state='completed',result=?,remote_id=?,updated_at=?
                WHERE environment_id=? AND call_id=?''',
                (canonical(result),remote_id,stamp(self.clock()),self.config.environment_id,call_id))

    def uncertain(self, call_id):
        with self.store.transaction():
            self.store.execute("UPDATE knowledge_calls SET state='uncertain',updated_at=? WHERE environment_id=? AND call_id=? AND state='running'",
                               (stamp(self.clock()),self.config.environment_id,call_id))

    def recover(self):
        with self.store.transaction():
            self.store.execute("UPDATE knowledge_calls SET state='uncertain',updated_at=? WHERE environment_id=? AND state='running'",
                               (stamp(self.clock()),self.config.environment_id))

    def verified_not_created(self, call_id):
        """Owner verified absence externally; next manual sync may retry. No original answer replay."""
        from app.core.contracts import Scope, Message
        env, now = self.config.environment_id, instant(self.clock())
        with self.store.transaction():
            row = self.store.execute('SELECT kind,state FROM knowledge_calls WHERE environment_id=? AND call_id=?',
                                     (env,call_id)).fetchone()
            if not row or row['kind'] == 'answer' or row['state'] != 'uncertain':
                raise EngineError('knowledge_call_state_invalid')
            self.store.execute("UPDATE knowledge_calls SET state='failed',updated_at=? WHERE environment_id=? AND call_id=?",
                               (stamp(now),env,call_id))
            msg = Message(Scope(env,'local',0,0),call_id,now,call_id)
            self.store.audit(msg,'operator','knowledge.reconcile','owner_verified_not_created',now,
                             entity_id=call_id,previous='uncertain',next_state='failed')
