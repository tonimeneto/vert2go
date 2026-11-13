"""Owner-scoped cancellation journal; persist before PATCH, never replay uncertain writes."""
from datetime import timedelta
import json
from uuid import NAMESPACE_URL,uuid5
from zoneinfo import ZoneInfo
from app.core.contracts import EngineError,Result,canonical,digest,instant,stamp
from app.services.operational_memory import exact,identifier


class ReservationCancellations:
    def __init__(self,operations):
        self.ops=operations;self.store=operations.store

    def startup(self):
        now=stamp(self.ops.clock())
        with self.store.transaction():
            changed=self.store.execute("UPDATE pilot_cancellations SET state='needs_reconciliation',updated_at=? WHERE environment_id=? AND state='committing'",(now,self.ops.config.environment_id)).rowcount
            self.store.execute("UPDATE pilot_cancellations SET state='cancelled',closed_at=?,updated_at=? WHERE environment_id=? AND state='awaiting_confirmation' AND expires_at<=?",(now,now,self.ops.config.environment_id,now))
        return changed

    def target(self,message,reservation_id):
        row=self.ops._row(message,reservation_id)
        if row['kind']!='reservation' or not row['external_reference']:
            raise EngineError('reservation_not_found')
        p=json.loads(row['proposal']);unit=self.ops._unit(message.scope)
        legacy=(self.ops.c.legacy_units or {}).get(str(message.scope.channel_user_id),())
        if p['unit_reference'] not in (unit,*legacy):raise EngineError('reservation_unit_changed')
        if list(message.scope.key())!=p['scope']:raise EngineError('operation_not_found')
        self.ops._check_destinations(p)
        if not instant(self.ops.config.google.window_start)<=instant(p['start'])<instant(p['end'])<=instant(self.ops.config.google.window_end):
            raise EngineError('google_resource_denied')
        return row,p

    def row(self,message,operation_id):
        identifier(operation_id)
        row=self.store.execute('SELECT * FROM pilot_cancellations WHERE environment_id=? AND operation_id=?',
            (message.scope.environment_id,operation_id)).fetchone()
        if row is None or (row['channel'],row['channel_user_id'],row['chat_id'])!=message.scope.key()[1:]:
            raise EngineError('operation_not_found')
        self.target(message,row['reservation_id'])
        return row

    def event(self,message,row):
        actual=self.ops.calendar.get_event(self.ops.c.calendar_id,row['external_reference'])
        expected=self.ops.event(row)
        if not actual or actual.get('id')!=expected['id']:raise EngineError('reservation_evidence_invalid')
        if actual.get('status')=='cancelled':return actual
        if (actual.get('status')!='confirmed' or actual.get('extendedProperties')!=expected['extendedProperties']
                or instant(actual.get('start',{}).get('dateTime'))!=instant(expected['start']['dateTime'])
                or instant(actual.get('end',{}).get('dateTime'))!=instant(expected['end']['dateTime'])
                or actual.get('recurrence') or actual.get('recurringEventId')):
            raise EngineError('reservation_evidence_invalid')
        return actual

    def dispatch(self,message,action,p,hashed):
        if action=='my_reservations':
            exact(p,(),('resource',))
            unit=self.ops._unit(message.scope)
            rows=self.store.execute("SELECT * FROM pilot_operations WHERE environment_id=? AND channel=? AND channel_user_id=? AND chat_id=? AND kind='reservation' AND state IN ('confirmed','cancelled') AND external_reference IS NOT NULL ORDER BY created_at DESC LIMIT ?",
                (*message.scope.key(),self.ops.c.report_limit+1)).fetchall()
            if len(rows)>self.ops.c.report_limit:raise EngineError('reservation_search_limit')
            found=[]
            for row in rows:
                proposal=json.loads(row['proposal'])
                if p.get('resource') and proposal['resource']!=p['resource']:continue
                self.target(message,row['operation_id'])
                actual=self.event(message,row)
                found.append({'operation_id':row['operation_id'],'resource':proposal['resource'],
                    'unit_reference':unit,'original_unit_reference':proposal['unit_reference'],
                    'start':proposal['start'],'end':proposal['end'],'state':actual['status']})
            return Result('success','own_reservations',{'reservations':found})
        if action=='propose_reservation_cancellation':
            exact(p,('reservation_id',),('retry',))
            if 'retry' in p and type(p['retry']) is not bool:raise EngineError('invalid_input')
            return self.propose(message,p['reservation_id'],hashed,p.get('retry',False))
        if action=='confirm_reservation_cancellation':
            exact(p,('operation_id','proposal_hash','explicit'))
            if p['explicit'] is not True:raise EngineError('explicit_confirmation_required')
            return self.confirm(message,p)
        exact(p,('operation_id',))
        with self.ops.lock():return self.reconcile(message,self.row(message,p['operation_id']))

    def propose(self,message,reservation_id,hashed,retry=False):
        target,p=self.target(message,reservation_id)
        oid=str(uuid5(NAMESPACE_URL,canonical([message.scope.key(),message.message_id,'reservation_cancellation'])))
        old=self.store.execute('SELECT * FROM pilot_cancellations WHERE environment_id=? AND operation_id=?',(message.scope.environment_id,oid)).fetchone()
        if old:
            if old['input_hash']!=hashed:raise EngineError('message_identity_conflict')
            if old['state'] in ('confirmed','committing','needs_reconciliation'):
                with self.ops.lock():return self.reconcile(message,old)
            if old['state']!='awaiting_confirmation' or instant(old['expires_at'])<=self.ops.clock():raise EngineError('confirmation_expired')
            return self.summary(old)
        pending=self.store.execute("SELECT operation_id FROM pilot_cancellations WHERE environment_id=? AND reservation_id=? AND state IN ('committing','needs_reconciliation')",(message.scope.environment_id,reservation_id)).fetchone()
        if pending:
            with self.ops.lock():
                previous=self.row(message,pending[0]);checked=self.reconcile(message,previous)
                if checked.code=='reservation_cancelled' or not retry:return checked
                actual=self.event(message,target)
                if actual['status']!='confirmed':return checked
                # Only a new explicit retry request may prepare another proposal.
                # No PATCH is repeated here; another delivered approval is required.
                self.transition(message,previous,'failed',{'superseded_by_new_authorization':oid})
        actual=self.event(message,target)
        if actual['status']=='cancelled':return Result('success','reservation_already_cancelled',{'reservation_id':reservation_id})
        if target['state']!='confirmed':raise EngineError('reservation_not_cancellable')
        etag=actual.get('etag')
        if type(etag) is not str or not etag or len(etag)>1024 or '\r' in etag or '\n' in etag:
            raise EngineError('calendar_etag_required')
        now=instant(self.ops.clock());expires=instant(message.received_at)+timedelta(seconds=self.ops.config.limits['confirmation_seconds'])
        if expires<=now:raise EngineError('confirmation_expired')
        proposal={'kind':'reservation_cancellation','reservation_id':reservation_id,'resource':p['resource'],
            'unit_reference':self.ops._unit(message.scope),'original_unit_reference':p['unit_reference'],
            'start':p['start'],'end':p['end'],'event_id':target['external_reference'],'event_etag':etag,
            'reservation_hash':target['proposal_hash'],'scope':list(message.scope.key()),
            'destinations':self.ops.destinations(),'expires_at':stamp(expires)}
        with self.store.transaction():
            self.store.execute("INSERT INTO pilot_cancellations (environment_id,operation_id,channel,channel_user_id,chat_id,reservation_id,input_hash,proposal,proposal_hash,state,created_at,updated_at,expires_at) VALUES (?,?,?,?,?,?,?,?,?,'awaiting_confirmation',?,?,?)",
                (*message.scope.key()[:1],oid,*message.scope.key()[1:],reservation_id,hashed,canonical(proposal),digest(proposal),stamp(now),stamp(now),stamp(expires)))
            self.store.audit(message,self.ops.policy.identify(message.scope),'pilot.reservation_cancellation','proposal',now,oid,next_state='awaiting_confirmation')
        return self.summary(self.row(message,oid))

    def summary(self,row):
        return Result('awaiting_confirmation','pilot_proposal',{**json.loads(row['proposal']),'operation_id':row['operation_id'],'proposal_hash':row['proposal_hash']})

    def transition(self,message,row,state,result=None):
        now=stamp(self.ops.clock())
        with self.store.transaction():
            self.store.execute('UPDATE pilot_cancellations SET state=?,result=?,updated_at=?,closed_at=? WHERE environment_id=? AND operation_id=?',
                (state,canonical(result) if result else None,now,now if state in ('confirmed','failed','cancelled') else None,message.scope.environment_id,row['operation_id']))
            self.store.audit(message,self.ops.policy.identify(message.scope),'pilot.reservation_cancellation',state,now,row['operation_id'],previous=row['state'],next_state=state)

    def confirm(self,message,p):
        row=self.row(message,p['operation_id']);proposal=json.loads(row['proposal'])
        self.ops._check_destinations(proposal)
        if p['proposal_hash']!=row['proposal_hash'] or digest(proposal)!=row['proposal_hash']:raise EngineError('proposal_changed')
        if self.ops._unit(message.scope)!=proposal['unit_reference']:raise EngineError('proposal_changed')
        with self.ops.lock():
            row=self.row(message,p['operation_id'])
            if row['state'] in ('confirmed','committing','needs_reconciliation'):return self.reconcile(message,row)
            if row['state']!='awaiting_confirmation' or instant(row['expires_at'])<=self.ops.clock():raise EngineError('confirmation_expired')
            target,original=self.target(message,row['reservation_id'])
            actual=self.event(message,target)
            if actual['status']=='cancelled':
                self.transition(message,row,'cancelled')
                return Result('success','reservation_already_cancelled',{'reservation_id':target['operation_id']})
            if (target['state']!='confirmed' or target['proposal_hash']!=proposal['reservation_hash']
                    or actual.get('etag')!=proposal['event_etag']):raise EngineError('cancellation_target_changed')
            other=self.store.execute("SELECT operation_id FROM pilot_cancellations WHERE environment_id=? AND reservation_id=? AND operation_id!=? AND state IN ('committing','needs_reconciliation','confirmed')",(message.scope.environment_id,target['operation_id'],row['operation_id'])).fetchone()
            if other:raise EngineError('cancellation_in_progress')
            self.transition(message,row,'committing')
            try:
                self.ops.calendar.cancel_event(self.ops.c.calendar_id,target['external_reference'],actual['etag'])
                return self.reconcile(message,self.row(message,row['operation_id']))
            except EngineError as error:
                if error.code=='calendar_precondition_failed':
                    self.transition(message,row,'failed')
                    raise EngineError('cancellation_target_changed') from None
                self.transition(message,row,'needs_reconciliation')
                return Result('uncertain','cancellation_reconciliation_required',{'operation_id':row['operation_id']})

    def reconcile(self,message,row):
        proposal=json.loads(row['proposal']);self.ops._check_destinations(proposal)
        if self.ops._unit(message.scope)!=proposal['unit_reference']:raise EngineError('proposal_changed')
        if row['state'] not in ('committing','needs_reconciliation','confirmed'):raise EngineError('operation_not_confirmable')
        try:
            actual=self.ops.calendar.get_event(self.ops.c.calendar_id,proposal['event_id'])
            if not actual or actual.get('id')!=proposal['event_id'] or actual.get('status')!='cancelled':
                raise EngineError('cancellation_evidence_invalid')
        except EngineError:
            self.transition(message,row,'needs_reconciliation')
            return Result('uncertain','cancellation_reconciliation_required',{'operation_id':row['operation_id']})
        result={'operation_id':row['operation_id'],'reservation_id':row['reservation_id'],'start':proposal['start'],'end':proposal['end'],'sheets_status':'pending_or_synced_independently'}
        with self.store.transaction():
            target,_=self.target(message,row['reservation_id'])
            if target['state']!='cancelled':
                now=stamp(self.ops.clock())
                preserved=json.loads(target['result']) if target['result'] else {}
                self.store.execute("UPDATE pilot_operations SET state='cancelled',result=?,updated_at=?,closed_at=? WHERE environment_id=? AND operation_id=?",(canonical({**preserved,'cancellation_id':row['operation_id'],'external_state':'cancelled'}),now,now,message.scope.environment_id,target['operation_id']))
                self.store.audit(message,self.ops.policy.identify(message.scope),'pilot.reservation','cancelled',now,target['operation_id'],previous=target['state'],next_state='cancelled')
            if row['state']!='confirmed':
                now=stamp(self.ops.clock())
                self.store.execute("UPDATE pilot_cancellations SET state='confirmed',result=?,updated_at=?,closed_at=? WHERE environment_id=? AND operation_id=?",(canonical(result),now,now,message.scope.environment_id,row['operation_id']))
                self.store.audit(message,self.ops.policy.identify(message.scope),'pilot.reservation_cancellation','confirmed',now,row['operation_id'],entity_id=row['reservation_id'],previous=row['state'],next_state='confirmed')
            self.ops._enqueue(row['operation_id'],{**proposal,'content':'Cancelamento da reserva '+row['reservation_id']},'reservation_cancellation',proposal['event_id'],self.ops.clock())
        return Result('success','reservation_cancelled',result)
