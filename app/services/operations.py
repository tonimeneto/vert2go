"""I5 state machine. Durable intent precedes Google; uncertain writes are never replayed.

No LLM receives permission to execute tools. The injected Calendar/Sheets contracts
are also used by offline tests. There is no SQLite availability calendar.
"""
from datetime import datetime, timedelta
from contextlib import contextmanager, ExitStack
from decimal import Decimal
import json
from pathlib import Path
import re
import sqlite3
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo
from app.core.contracts import EngineError, Result, canonical, digest, instant, stamp, utcnow
from app.core.policy import Policy
from app.services.operational_memory import exact, identifier

PERMISSIONS = {
    'propose_reservation':'reservation.create', 'confirm_operation':'context.read',
    'reservation_status':'reservation.read', 'propose_request':'request.create',
    'request_status':'request.read', 'propose_response':'request.respond',
    'operations_report':'report.read', 'reconcile_operation':'operations.reconcile',
    'sync_operations':'operations.reconcile', 'contextual_guidance':'guidance.read',
    'reservation_availability':'reservation.read',
    'my_reservations':'reservation.read',
    'propose_reservation_cancellation':'reservation.cancel',
    'confirm_reservation_cancellation':'reservation.cancel',
    'reconcile_reservation_cancellation':'reservation.cancel',
}
READS = {'reservation_status','request_status','operations_report','contextual_guidance','reservation_availability','my_reservations','reconcile_reservation_cancellation','confirm_reservation_cancellation','propose_reservation_cancellation'}


class Operations:
    def __init__(self, config, store, calendar, sheets, *, drive=None, clock=utcnow, lock_root=None):
        if config.operations is None:
            raise EngineError('operations_not_configured')
        if store.execute('PRAGMA user_version').fetchone()[0] != 5:
            raise EngineError('operations_migration_required')
        self.config, self.store, self.calendar, self.sheets = config,store,calendar,sheets
        self.c, self.policy, self.clock, self.drive = config.operations,Policy(config),clock,drive
        # Same canonical resource lock for different database names and processes.
        self.lock_root = Path(lock_root) if lock_root else Path(__file__).resolve().parents[2]/'data/locks'
        from app.services.reservation_cancellations import ReservationCancellations
        self.cancellations=ReservationCancellations(self)

    @contextmanager
    def lock(self):
        from app.main import instance_lock
        with ExitStack() as locks:
            for kind,resource in (('calendar',self.c.calendar_id),('sheets',self.c.spreadsheet_id)):
                locks.enter_context(instance_lock(self.lock_root/('google-'+digest([kind,resource]))))
            yield

    def destinations(self):
        return {'calendar_id':self.c.calendar_id,'spreadsheet_id':self.c.spreadsheet_id,'sheet_range':self.c.sheet_range}

    def _check_destinations(self, proposal):
        if proposal.get('destinations') != self.destinations():
            raise EngineError('operation_resource_changed')

    def startup(self):
        now = stamp(self.clock())
        with self.store.transaction():
            count = self.store.execute("UPDATE pilot_operations SET state='needs_reconciliation',updated_at=? WHERE environment_id=? AND state='committing'",
                                       (now,self.config.environment_id)).rowcount
            self.store.execute("UPDATE pilot_operations SET state='cancelled',closed_at=?,updated_at=? WHERE environment_id=? AND state='awaiting_confirmation' AND expires_at<=?",
                               (now,now,self.config.environment_id,now))
        conflicts = self.store.execute("SELECT * FROM pilot_operations WHERE environment_id=? AND kind='reservation' AND state='conflicted' AND external_reference IS NOT NULL",
                                       (self.config.environment_id,)).fetchall()
        for row in conflicts:
            self._conflict_request(row)
        return count+self.cancellations.startup()

    def _row(self, message, operation_id, *, manager=False):
        identifier(operation_id)
        row = self.store.execute('SELECT * FROM pilot_operations WHERE environment_id=? AND operation_id=?',
                                 (self.config.environment_id,operation_id)).fetchone()
        if row is None or (not manager and (row['channel'],row['channel_user_id'],row['chat_id']) != message.scope.key()[1:]):
            raise EngineError('operation_not_found')
        return row

    def _transition(self, message, row, state, result=None, external=None):
        now = instant(self.clock())
        with self.store.transaction():
            self.store.execute('''UPDATE pilot_operations SET state=?,result=?,external_reference=COALESCE(?,external_reference),
                updated_at=?,closed_at=? WHERE environment_id=? AND operation_id=?''',
                (state,canonical(result) if result else None,external,stamp(now),
                 stamp(now) if state in ('confirmed','conflicted','failed','cancelled')
                     and not (state == 'conflicted' and (external or row['external_reference'])) else None,
                 self.config.environment_id,row['operation_id']))
            self.store.audit(message,self.policy.identify(message.scope),'pilot.'+row['kind'],state,now,
                             row['operation_id'],previous=row['state'],next_state=state)
            if state == 'confirmed':
                proposal = json.loads(row['proposal'])
                self._enqueue(row['operation_id'],proposal,row['kind'],external,now)

    def _enqueue(self, operation_id, proposal, category, external, now):
        oid = digest([operation_id,'sheets'])
        status = ('forwarded' if proposal.get('assigned_to') == 'manager' else 'pending') if category == 'request' else (
            'resolved' if category == 'response' else 'forwarded' if category == 'reservation_conflict' else 'cancelled' if category=='reservation_cancellation' else 'confirmed')
        payload = [oid,stamp(now),proposal.get('unit_reference',''),category,status,
                   proposal.get('assigned_to',''),stamp(now),external or operation_id,'synced',
                   proposal.get('content',proposal.get('response',''))]
        self.store.execute('''INSERT OR IGNORE INTO pilot_outbox
            (environment_id,outbox_id,operation_id,target_id,target_range,payload,state,created_at,updated_at)
            VALUES (?,?,?,?,?,?,'pending',?,?)''',
            (self.config.environment_id,oid,operation_id,self.c.spreadsheet_id,self.c.sheet_range,
             canonical(payload),stamp(now),stamp(now)))

    def _unit(self, scope):
        unit = self.c.units.get(str(scope.channel_user_id))
        if unit is None:
            raise EngineError('simulated_unit_not_enrolled')
        return unit

    def rules(self, resource, start, end):
        rule = self.c.resources.get(resource) if type(resource) is str else None
        now = instant(self.clock())
        if rule is None or rule['status'] not in ('verified','simulated'):
            raise EngineError('document_rule_requires_review')
        if not instant(rule['verified_at']) <= now < instant(rule['valid_until']) or instant(end) > instant(rule['valid_until']):
            raise EngineError('document_rule_outdated')
        if rule['status'] == 'verified':
            if self.drive is None:
                raise EngineError('document_freshness_required')
            document = self.drive.read_document(rule['source_document_id'])
            if document.source_version != rule['source_revision'] or document.sha256 != rule['source_hash']:
                raise EngineError('document_rule_outdated')
            metadata = self.store.execute('SELECT * FROM document_sync_metadata WHERE environment_id=? AND source_id=?',
                                           (self.config.environment_id,rule['source_document_id'])).fetchone()
            if (metadata is None or metadata['status'] != 'synced' or metadata['source_revision'] != rule['source_revision']
                    or metadata['source_hash'] != rule['source_hash']):
                raise EngineError('document_rule_outdated')
        zone = ZoneInfo(self.config.timezone)
        a,b = instant(start).astimezone(zone),instant(end).astimezone(zone)
        if self.interval_issues(resource,a,b):
            raise EngineError('reservation_conditions_not_met')
        return rule

    def interval_issues(self, resource, start, end):
        """One source for validation and conversational explanations; parameters stay external."""
        rule=self.c.resources.get(resource)
        if rule is None:
            raise EngineError('document_rule_requires_review')
        zone=ZoneInfo(self.config.timezone);now=instant(self.clock())
        a,b=instant(start).astimezone(zone),instant(end).astimezone(zone)
        checks=(('past',a<=now),('order',b<=a),('same_day',a.date()!=b.date()),
            ('hours',a.strftime('%H:%M')<rule['opens'] or b.time()>datetime.strptime(rule['closes'],'%H:%M').time()),
            ('duration',b-a>timedelta(minutes=rule['max_duration_minutes'])),
            ('notice',a-now<timedelta(hours=rule['min_notice_hours'])),
            ('advance',a-now>timedelta(days=rule['max_advance_days'])),
            ('window',not instant(self.config.google.window_start)<=a<b<=instant(self.config.google.window_end)))
        return [name for name,failed in checks if failed]

    def _event_bounds(self, event):
        try:
            def bound(value):
                if 'dateTime' in value:return instant(value['dateTime'])
                return datetime.fromisoformat(value['date']).replace(tzinfo=ZoneInfo(self.config.timezone))
            a,b=bound(event['start']),bound(event['end'])
            if b<=a:raise ValueError
            return a,b
        except (KeyError,TypeError,ValueError,EngineError):
            raise EngineError('calendar_event_invalid') from None

    def availability(self, resource, day=None):
        rule=self.c.resources.get(resource)
        if not rule or rule['status'] not in ('verified','simulated'):
            raise EngineError('document_rule_requires_review')
        zone=ZoneInfo(self.config.timezone);now=instant(self.clock()).astimezone(zone)
        window_start=instant(self.config.google.window_start).astimezone(zone)
        window_end=instant(self.config.google.window_end).astimezone(zone)
        if now>=window_end:raise EngineError('reservation_window_closed')
        if not instant(rule['verified_at'])<=now<instant(rule['valid_until']):
            raise EngineError('document_rule_outdated')
        earliest=max(now+timedelta(hours=rule['min_notice_hours']),window_start)
        latest=min(window_end,instant(rule['valid_until']).astimezone(zone))
        if day is not None:
            try:days=[datetime.fromisoformat(day).date()]
            except (TypeError,ValueError):raise EngineError('invalid_datetime') from None
        else:
            # Bounded by the existing display/read limit; never scan an unbounded calendar.
            days=[earliest.date()+timedelta(days=n) for n in range(self.c.report_limit)]
        found=[]
        for date in days:
            opening=datetime.combine(date,datetime.strptime(rule['opens'],'%H:%M').time(),zone)
            closing=datetime.combine(date,datetime.strptime(rule['closes'],'%H:%M').time(),zone)
            a=max(opening,earliest);b=min(closing,latest)
            if a<=now or a.second or a.microsecond:a=a.replace(second=0,microsecond=0)+timedelta(minutes=1)
            if a>=b or a-now>timedelta(days=rule['max_advance_days']):continue
            try:self.rules(resource,a,min(a+timedelta(minutes=1),b))
            except EngineError as error:
                if error.code=='reservation_conditions_not_met':continue
                raise
            busy=[]
            for event in self._events(stamp(a),stamp(b)):
                if event.get('status')=='cancelled' or event.get('transparency')=='transparent':continue
                x,y=self._event_bounds(event)
                if x<b and a<y:busy.append((max(a,x),min(b,y)))
            cursor=a;free=[]
            for x,y in sorted(busy):
                if cursor<x:free.append({'start':stamp(cursor),'end':stamp(x)})
                cursor=max(cursor,y)
            if cursor<b:free.append({'start':stamp(cursor),'end':stamp(b)})
            if free:found.append({'date':date.isoformat(),'free':free})
            if len(found)>=min(3,self.c.report_limit):break
        return Result('success','pilot_availability',{'resource':resource,'days':found,
            'max_duration_minutes':rule['max_duration_minutes'],'opens':rule['opens'],'closes':rule['closes'],
            'rule_status':rule['status'],'queried_date':day,'window_start':self.config.google.window_start,
            'window_end':self.config.google.window_end})

    def _events(self, start, end):
        value = self.calendar.read_events(self.c.calendar_id,start,end)
        if value.get('complete') is not True or type(value.get('events')) is not list:
            raise EngineError('calendar_read_incomplete')
        return value['events']

    def _conflicts(self, proposal, *, exclude=None):
        a,b = instant(proposal['start']),instant(proposal['end'])
        conflicts = []
        for event in self._events(proposal['start'],proposal['end']):
            if event.get('id') == exclude or event.get('status') == 'cancelled' or event.get('transparency') == 'transparent':
                continue
            ea,eb=self._event_bounds(event)
            if ea < b and a < eb:
                conflicts.append(event['id'])
        return conflicts

    def _proposal(self, message, kind, fields, input_hash):
        now = instant(self.clock())
        oid = str(uuid5(NAMESPACE_URL,canonical([message.scope.key(),message.message_id,kind])))
        old = self.store.execute('SELECT * FROM pilot_operations WHERE environment_id=? AND operation_id=?',
                                 (self.config.environment_id,oid)).fetchone()
        if old:
            if old['input_hash'] != input_hash:
                raise EngineError('message_identity_conflict')
            return Result('awaiting_confirmation','pilot_proposal',
                          {**json.loads(old['proposal']),'operation_id':oid,'proposal_hash':old['proposal_hash']})
        expires = instant(message.received_at)+timedelta(seconds=self.config.limits['confirmation_seconds'])
        if expires <= now:
            raise EngineError('confirmation_expired')
        proposal = {**fields,'kind':kind,'scope':list(message.scope.key()),'expires_at':stamp(expires),
                    'destinations':self.destinations()}
        phash = digest(proposal)
        with self.store.transaction():
            self.store.execute('''INSERT INTO pilot_operations
                (environment_id,operation_id,channel,channel_user_id,chat_id,kind,input_hash,proposal,proposal_hash,
                 state,created_at,updated_at,expires_at) VALUES (?,?,?,?,?,?,?,?,?,'awaiting_confirmation',?,?,?)''',
                (self.config.environment_id,oid,*message.scope.key()[1:],kind,input_hash,canonical(proposal),phash,
                 stamp(now),stamp(now),stamp(expires)))
            self.store.audit(message,self.policy.identify(message.scope),'pilot.'+kind,'proposal',now,oid,
                             next_state='awaiting_confirmation')
        return Result('awaiting_confirmation','pilot_proposal',{**proposal,'operation_id':oid,'proposal_hash':phash})

    def handle(self, message, action, payload):
        self.policy.authorize(message.scope,PERMISSIONS[action])
        hashed = digest([message.scope.key(),message.message_id,message.update_id,stamp(message.received_at),message.text,action,payload])
        old = self.store.execute('''SELECT * FROM pilot_receipts WHERE environment_id=? AND channel=?
            AND ((channel_user_id=? AND chat_id=? AND message_id=?) OR (update_id IS NOT NULL AND update_id=?))''',
            (*message.scope.key(),message.message_id,message.update_id)).fetchone()
        if old and old['request_hash'] != hashed:
            raise EngineError('message_identity_conflict')
        if old and action not in READS:
            if action == 'confirm_operation':
                row = self._row(message,payload.get('operation_id'))
                self.policy.authorize(message.scope,{'reservation':'reservation.create','request':'request.create','response':'request.respond'}[row['kind']])
            return Result(**json.loads(old['result']))
        if not old:
            count = self.store.execute('''SELECT count(*) FROM pilot_receipts WHERE environment_id=? AND channel=?
                AND channel_user_id=? AND chat_id=? AND created_at>?''',
                (*message.scope.key(),stamp(instant(self.clock())-timedelta(minutes=1)))).fetchone()[0]
            if count >= self.config.limits['messages_per_minute']:
                raise EngineError('rate_limit')
        result = self._dispatch(message,action,payload,hashed)
        if not old:
            with self.store.transaction():
                self.store.execute('INSERT INTO pilot_receipts VALUES (?,?,?,?,?,?,?,?,?,?)',
                    (*message.scope.key(),message.message_id,message.update_id,hashed,result.data.get('operation_id'),
                     canonical(result.as_dict()),stamp(self.clock())))
        return result

    def _dispatch(self, message, action, p, hashed):
        if action in ('my_reservations','propose_reservation_cancellation','confirm_reservation_cancellation','reconcile_reservation_cancellation'):
            return self.cancellations.dispatch(message,action,p,hashed)
        if action=='reservation_availability':
            exact(p,('resource',),('date',))
            return self.availability(p['resource'],p.get('date'))
        if action in ('propose_reservation','propose_request','propose_response'):
            kind = {'propose_reservation':'reservation','propose_request':'request','propose_response':'response'}[action]
            oid = str(uuid5(NAMESPACE_URL,canonical([message.scope.key(),message.message_id,kind])))
            previous = self.store.execute('SELECT * FROM pilot_operations WHERE environment_id=? AND operation_id=?',
                                          (self.config.environment_id,oid)).fetchone()
            if previous:
                if previous['input_hash'] != hashed:
                    raise EngineError('message_identity_conflict')
                if previous['state'] == 'awaiting_confirmation' and instant(previous['expires_at']) > instant(self.clock()):
                    return Result('awaiting_confirmation','pilot_proposal',{**json.loads(previous['proposal']),
                        'operation_id':oid,'proposal_hash':previous['proposal_hash']})
                if previous['kind'] == 'reservation' and previous['state'] in ('confirmed','committing','needs_reconciliation'):
                    with self.lock():
                        return self._verify_event(message,previous)
                return Result('success' if previous['state'] == 'confirmed' else 'pending','pilot_confirmed'
                    if previous['state'] == 'confirmed' else 'pilot_state',{'operation_id':oid,'state':previous['state']})
        if action == 'propose_reservation':
            exact(p,('resource','start','end'))
            rule = self.rules(p['resource'],p['start'],p['end'])
            data = {**p,'start':stamp(p['start']),'end':stamp(p['end']), 'unit_reference':self._unit(message.scope),
                    'rule':dict(rule),'experimental':True}
            with self.lock():
                if self._conflicts(data):
                    alternatives = []
                    for days in self.c.alternative_offsets_days:
                        candidate = {**data,'start':stamp(instant(data['start'])+timedelta(days=days)),
                                     'end':stamp(instant(data['end'])+timedelta(days=days))}
                        # A suggestion outside this rule's date range says nothing
                        # about the freshness of the valid, originally requested rule.
                        if (instant(candidate['end'])>instant(rule['valid_until'])
                                or self.interval_issues(candidate['resource'],candidate['start'],candidate['end'])):
                            continue
                        try:
                            self.rules(candidate['resource'],candidate['start'],candidate['end'])
                        except EngineError as error:
                            if error.code == 'reservation_conditions_not_met':
                                continue
                            raise
                        if not self._conflicts(candidate):
                            alternatives.append({k:candidate[k] for k in ('resource','start','end')})
                    return Result('conflict','reservation_unavailable',{'alternatives':alternatives})
            return self._proposal(message,'reservation',data,hashed)
        if action == 'propose_request':
            exact(p,('category','content','urgent'))
            if (type(p['category']) is not str or p['category'] not in self.c.request_categories
                    or type(p['urgent']) is not bool or type(p['content']) is not str or not p['content'].strip()):
                raise EngineError('invalid_input')
            return self._proposal(message,'request',{**p,'unit_reference':self._unit(message.scope),
                                  'assigned_to':self.c.request_categories[p['category']]},hashed)
        if action == 'propose_response':
            exact(p,('request_id','expected_version','response'))
            identifier(p['request_id'])
            row = self.store.execute('SELECT * FROM pilot_requests WHERE environment_id=? AND request_id=?',
                                     (self.config.environment_id,p['request_id'])).fetchone()
            if row is None or row['assigned_to'] != 'manager' or row['status'] != 'forwarded':
                raise EngineError('request_not_respondable')
            if type(p['expected_version']) is not int or row['version'] != p['expected_version']:
                raise EngineError('stale_version')
            if type(p['response']) is not str or not p['response'].strip():
                raise EngineError('invalid_input')
            return self._proposal(message,'response',p,hashed)
        if action == 'confirm_operation':
            return self.confirm(message,p)
        if action == 'reservation_status':
            exact(p,('operation_id',))
            row = self._row(message,p['operation_id'])
            if row['kind'] != 'reservation':
                raise EngineError('operation_not_found')
            if row['state'] in ('committing','needs_reconciliation','confirmed') or (row['state'] == 'conflicted' and row['external_reference']):
                with self.lock():
                    return self._verify_event(message,row)
            return Result('pending','reservation_state',{'state':row['state'],'operation_id':row['operation_id']})
        if action == 'reconcile_operation':
            exact(p,('operation_id',))
            row = self._row(message,p['operation_id'],manager=True)
            if row['kind'] != 'reservation' or row['state'] not in ('committing','needs_reconciliation','confirmed','conflicted'):
                raise EngineError('operation_not_reconcilable')
            with self.lock():
                return self._verify_event(message,row)
        if action == 'sync_operations':
            exact(p,())
            return self.sync()
        if action == 'request_status':
            exact(p,(),('request_id',))
            params = [self.config.environment_id]
            query = 'SELECT request_id,unit_reference,category,content,status,assigned_to,urgent,version,response,created_at,updated_at FROM pilot_requests WHERE environment_id=?'
            if self.policy.identify(message.scope) != 'manager':
                query += ' AND channel=? AND channel_user_id=? AND chat_id=?'
                params.extend(message.scope.key()[1:])
            if 'request_id' in p:
                identifier(p['request_id']); query += ' AND request_id=?'; params.append(p['request_id'])
            rows = [dict(r) for r in self.store.execute(query+' ORDER BY updated_at DESC LIMIT ?',(*params,self.c.report_limit))]
            return Result('success','pilot_requests',{'requests':rows})
        if action == 'operations_report':
            exact(p,())
            env = self.config.environment_id
            def groups(table):
                expression=('status' if table=='pilot_requests' else 'state')
                if table=='pilot_operations':
                    expression="CASE WHEN state='cancelled' AND json_extract(result,'$.cancellation_id') IS NOT NULL THEN 'reservation_cancelled' ELSE state END"
                return [dict(r) for r in self.store.execute('SELECT '+('kind,' if table=='pilot_operations' else '')+expression+' AS status,count(*) AS count FROM '+table+' WHERE environment_id=? GROUP BY '+('kind,' if table=='pilot_operations' else '')+expression,(env,))]
            return Result('success','pilot_report',{'experimental':True,'operations':groups('pilot_operations'),
                'requests':groups('pilot_requests'),'sheets':groups('pilot_outbox'),
                'cancellations':groups('pilot_cancellations'),
                'reservation_evidence':'operation_history_only; consult Calendar for current existence'})
        if action == 'contextual_guidance':
            return self.contextual_guidance(message,p)
        raise EngineError('invalid_action')

    def confirm(self, message, p):
        exact(p,('operation_id','proposal_hash','explicit'),('accept_fee',))
        if p['explicit'] is not True:
            raise EngineError('explicit_confirmation_required')
        row = self._row(message,p['operation_id'])
        self.policy.authorize(message.scope,{'reservation':'reservation.create','request':'request.create','response':'request.respond'}[row['kind']])
        proposal = json.loads(row['proposal'])
        self._check_destinations(proposal)
        if p['proposal_hash'] != row['proposal_hash'] or digest(proposal) != row['proposal_hash']:
            raise EngineError('proposal_changed')
        if row['state'] == 'confirmed':
            if row['kind'] == 'reservation':
                with self.lock():
                    return self._verify_event(message,row)
            return Result('success','pilot_confirmed',{'operation_id':row['operation_id']})
        if row['state'] != 'awaiting_confirmation':
            return Result('pending','pilot_reconciliation_required',{'operation_id':row['operation_id'],'state':row['state']})
        if instant(self.clock()) >= instant(row['expires_at']):
            raise EngineError('confirmation_expired')
        with self.lock():
            row = self._row(message,p['operation_id'])
            if row['state'] != 'awaiting_confirmation':
                raise EngineError('operation_not_confirmable')
            if row['kind'] == 'reservation':
                rule = self.rules(proposal['resource'],proposal['start'],proposal['end'])
                if dict(rule) != proposal['rule'] or self._unit(message.scope) != proposal['unit_reference']:
                    raise EngineError('proposal_changed')
                if Decimal(rule['fee_brl']) > 0 and p.get('accept_fee') is not True:
                    raise EngineError('fee_acceptance_required')
                # An uncertain overlapping operation blocks new effects even if Calendar reads empty.
                pending = self.store.execute("SELECT * FROM pilot_operations WHERE environment_id=? AND kind='reservation' AND state IN ('committing','needs_reconciliation')",
                                             (self.config.environment_id,)).fetchall()
                if any(instant(json.loads(r['proposal'])['start']) < instant(proposal['end'])
                       and instant(proposal['start']) < instant(json.loads(r['proposal'])['end']) for r in pending):
                    raise EngineError('overlapping_operation_uncertain')
                if self._conflicts(proposal):
                    self._transition(message,row,'conflicted')
                    return Result('conflict','reservation_unavailable')
                self._transition(message,row,'committing')  # Committed before the first POST.
                event = self.event(row)
                try:
                    self.calendar.create_event(self.c.calendar_id,event)
                    return self._verify_event(message,self._row(message,row['operation_id']))
                except EngineError:
                    self._transition(message,row,'needs_reconciliation')
                    return Result('uncertain','pilot_reconciliation_required',{'operation_id':row['operation_id']})
            return self._confirm_local(message,row,proposal)

    def event(self, row):
        p = json.loads(row['proposal'])
        return {'id':digest([self.config.environment_id,row['operation_id']]),
                'summary':'Reserva experimental Alfredo', 'description':'Simulação sem validade oficial.',
                'start':{'dateTime':p['start'],'timeZone':self.config.timezone},
                'end':{'dateTime':p['end'],'timeZone':self.config.timezone},
                'extendedProperties':{'private':{'operation_id':row['operation_id'],
                    'environment_id':self.config.environment_id,'resource_id':p['resource'],
                    'owner_ref':digest(p['scope']),'proposal_hash':row['proposal_hash']}}}

    def _verify_event(self, message, row):
        self._check_destinations(json.loads(row['proposal']))
        expected = self.event(row)
        try:
            actual = self.calendar.get_event(self.c.calendar_id,expected['id'])
            if (actual is None or actual.get('id') != expected['id'] or actual.get('status') != 'confirmed'
                    or actual.get('transparency','opaque') != 'opaque'
                    or actual.get('extendedProperties') != expected['extendedProperties']
                    or instant(actual.get('start',{}).get('dateTime')) != instant(expected['start']['dateTime'])
                    or instant(actual.get('end',{}).get('dateTime')) != instant(expected['end']['dateTime'])):
                raise EngineError('reservation_evidence_invalid')
            proposal = json.loads(row['proposal'])
            if self._conflicts(proposal,exclude=expected['id']):
                self._transition(message,row,'conflicted',external=expected['id'])
                self._conflict_request(self._row(message,row['operation_id'],manager=self.policy.identify(message.scope) == 'manager'))
                return Result('conflict','reservation_conflict_requires_review',{'operation_id':row['operation_id']})
        except EngineError:
            self._transition(message,row,'needs_reconciliation')
            return Result('uncertain','pilot_reconciliation_required',{'operation_id':row['operation_id']})
        result = {'operation_id':row['operation_id'],'external_reference':expected['id'],'experimental':True,
                  'sheets_status':'pending_or_synced_independently'}
        self._transition(message,row,'confirmed',result,expected['id'])
        return Result('success','reservation_confirmed',result)

    def _conflict_request(self, row):
        """A post-write conflict is an incident, never an automatic event cancellation."""
        env,now = self.config.environment_id,stamp(self.clock())
        rid = str(uuid5(NAMESPACE_URL,canonical([env,row['operation_id'],'reservation_conflict'])))
        p = json.loads(row['proposal'])
        self._check_destinations(p)
        content = 'Conflito em reserva experimental; verificação manual necessária. Operação: '+row['operation_id']
        with self.store.transaction():
            created = self.store.execute('''INSERT OR IGNORE INTO pilot_requests VALUES
                (?,?,?,?,?,?,?,?, 'forwarded','manager',0,1,NULL,?,?,NULL)''',
                (env,rid,row['channel'],row['channel_user_id'],row['chat_id'],p['unit_reference'],
                 self.c.reservation_exception_category,content,now,now))
            if created.rowcount:
                manager = next(u for u in self.config.users if u.role == 'manager' and u.enabled)
                self._notice(manager.channel,manager.channel_user_id,manager.chat_ids[0],rid,0,
                             'Conflito de reserva experimental: '+rid+'. Verificação manual necessária; nenhum evento foi cancelado.')
                self._enqueue(rid,{'unit_reference':p['unit_reference'],'content':content,'assigned_to':'manager'},
                              'reservation_conflict',row['external_reference'],instant(now))

    def _confirm_local(self, message, row, p):
        now,env = stamp(self.clock()),self.config.environment_id
        with self.store.transaction():
            if row['kind'] == 'request':
                if self._unit(message.scope) != p['unit_reference'] or self.c.request_categories.get(p['category']) != p['assigned_to']:
                    raise EngineError('proposal_changed')
                status = 'forwarded' if p['assigned_to'] == 'manager' else 'pending'
                self.store.execute('''INSERT INTO pilot_requests VALUES (?,?,?,?,?,?,?,?,?,?,?,1,NULL,?,?,NULL)''',
                    (env,row['operation_id'],*message.scope.key()[1:],p['unit_reference'],p['category'],p['content'],status,
                     p['assigned_to'],int(p['urgent']),now,now))
                if status == 'forwarded':
                    manager = next(u for u in self.config.users if u.role == 'manager' and u.enabled)
                    self._notice(manager.channel,manager.channel_user_id,manager.chat_ids[0],row['operation_id'],0,
                        ('URGENTE — ' if p['urgent'] else '')+'Novo pedido da unidade '+p['unit_reference']+':\n'+p['content']+
                        '\n\nQual mensagem você quer que eu responda ao morador? Pode responder a esta mensagem normalmente. '
                        'Antes de enviar, vou pedir sua autorização. Atendimento experimental.')
            else:
                updated = self.store.execute("UPDATE pilot_requests SET response=?,status='resolved',version=version+1,updated_at=?,closed_at=? WHERE environment_id=? AND request_id=? AND version=? AND status='forwarded' AND assigned_to='manager'",
                    (p['response'],now,now,env,p['request_id'],p['expected_version']))
                if updated.rowcount != 1:
                    raise EngineError('stale_version')
                request = self.store.execute('SELECT * FROM pilot_requests WHERE environment_id=? AND request_id=?',
                                            (env,p['request_id'])).fetchone()
                self._notice(request['channel'],request['channel_user_id'],request['chat_id'],p['request_id'],request['version'],
                             'A administração respondeu ao seu pedido:\n'+p['response']+
                             '\n\nAtendimento experimental. Essa resposta não cria reserva nem altera as regras.')
            result = {'operation_id':row['operation_id'],'experimental':True}
            self.store.execute("UPDATE pilot_operations SET state='confirmed',result=?,updated_at=?,closed_at=? WHERE environment_id=? AND operation_id=?",
                               (canonical(result),now,now,env,row['operation_id']))
            self._enqueue(row['operation_id'],p,row['kind'],None,instant(now))
            self.store.audit(message,self.policy.identify(message.scope),'pilot.'+row['kind'],'confirmed',now,
                             row['operation_id'],previous=row['state'],next_state='confirmed')
        return Result('success','pilot_confirmed',result)

    def _notice(self, channel, uid, chat, request_id, version, reply):
        nid = digest([request_id,version])
        self.store.execute("INSERT OR IGNORE INTO pilot_notifications VALUES (?,?,?,?,?,?,?,?, 'pending',?)",
            (self.config.environment_id,nid,channel,uid,chat,request_id,version,reply,stamp(self.clock())))

    def sync(self):
        synced,failed = 0,0
        with self.lock():
            rows = self.store.execute("SELECT * FROM pilot_outbox WHERE environment_id=? AND state!='synced' ORDER BY created_at,outbox_id LIMIT ?",
                                       (self.config.environment_id,self.c.report_limit)).fetchall()
            for row in rows:
                try:
                    self._sync_row(row)
                    synced += 1
                except EngineError:
                    with self.store.transaction():
                        self.store.execute("UPDATE pilot_outbox SET state='needs_reconciliation',safe_error='sheets_sync_unverified',updated_at=? WHERE environment_id=? AND outbox_id=?",
                                           (stamp(self.clock()),self.config.environment_id,row['outbox_id']))
                    failed += 1
        return Result('success' if not failed else 'pending','pilot_sync',{'synced':synced,'pending':failed})

    def _sync_row(self, row):
        if (row['target_id'],row['target_range']) != (self.c.spreadsheet_id,self.c.sheet_range):
            raise EngineError('operation_resource_changed')
        values = self.sheets.read_range(self.c.spreadsheet_id,self.c.sheet_range)
        match = re.fullmatch(r'(.+)!A([0-9]+):J([0-9]+)',self.c.sheet_range)
        top,bottom = int(match[2]),int(match[3])
        if len(values) > bottom-top+1:
            raise EngineError('sheets_journal_invalid')
        expected = json.loads(row['payload'])
        def padded(values):
            # Sheets omits empty trailing cells in ValueRange responses.
            if len(values)>len(expected):
                raise EngineError('sheets_journal_invalid')
            return values+['']*(len(expected)-len(values))
        number = row['row_number']
        matches = [top+i for i,v in enumerate(values) if v and v[0] == row['outbox_id']]
        if len(matches) > 1 or (matches and number is not None and matches != [number]):
            raise EngineError('sheets_journal_changed')
        if number is None:
            used = {r[0] for r in self.store.execute('SELECT row_number FROM pilot_outbox WHERE environment_id=? AND row_number IS NOT NULL',
                                                    (self.config.environment_id,))}
            number = matches[0] if matches else next((n for n in range(top,bottom+1) if n not in used
                        and (n-top >= len(values) or not any(v != '' for v in values[n-top]))),None)
            if number is None:
                raise EngineError('sheets_journal_full')
        current = padded(values[number-top]) if number-top < len(values) else []
        if current and any(v != '' for v in current) and current != expected:
            raise EngineError('sheets_journal_changed')
        with self.store.transaction():
            self.store.execute("UPDATE pilot_outbox SET row_number=?,state='needs_reconciliation',attempts=attempts+1,updated_at=? WHERE environment_id=? AND outbox_id=?",
                               (number,stamp(self.clock()),self.config.environment_id,row['outbox_id']))
        target = match[1]+'!A'+str(number)+':J'+str(number)
        if current != expected:
            self.sheets.write_row(self.c.spreadsheet_id,target,expected)
        readback = self.sheets.read_range(self.c.spreadsheet_id,self.c.sheet_range)
        if number-top >= len(readback) or padded(readback[number-top]) != expected:
            raise EngineError('sheets_write_uncertain')
        with self.store.transaction():
            self.store.execute("UPDATE pilot_outbox SET state='synced',safe_error=NULL,updated_at=? WHERE environment_id=? AND outbox_id=?",
                               (stamp(self.clock()),self.config.environment_id,row['outbox_id']))

    def contextual_guidance(self, message, p):
        exact(p,('topic',))
        from app.services.operational_memory import OperationalMemory
        result = OperationalMemory(self.store,self.policy,self.config).find(message,p,instant(self.clock()))
        # Never present unchecked operational guidance as a replacement for formal rules.
        return Result('success','pilot_guidance',{'source':'administration','guidance':result.data['guidance'],
            'notice':'Orientação operacional da administração; não altera regulamento. Em conflito ou dúvida, solicitar esclarecimento.'})
