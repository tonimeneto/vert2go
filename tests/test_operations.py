"""I5 offline failure injection. All identities, conditions and transports are fictitious."""
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
import json
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4
import yaml
from app.config.schema import _parse_config
from app.core.contracts import EngineError, Message, Scope, digest
from app.core.orchestrator import Orchestrator
from app.integrations.operations import OperationsHTTP
from app.services.operations import Operations
from app.storage.sqlite import Store
from tests.support import ROOT, Clock
from tests.test_google import declaration, response


def parameters():
    return {'authorization':{'calendar_id':declaration()['calendar']['id'],
            'spreadsheet_id':declaration()['sheets']['id'],'sheet_range':"'Operacao'!A2:J30",
            'exclusive_pilot_resources':False,'calendar_insert':False,'sheets_update':False},
        'units':{'1001':'SIM-101'},'resources':[{
            'id':'salao','rule_id':'fictional-rule','status':'simulated','source_document_id':'fixture-only',
            'source_title':'Cenário fictício; não é regra condominial','section':'fixture',
            'source_revision':'1','source_hash':'fixture-only','verified_at':'2026-11-01T00:00:00-03:00',
            'valid_until':'2026-12-01T00:00:00-03:00','opens':'08:00','closes':'22:00',
            'max_duration_minutes':240,'min_notice_hours':0,'max_advance_days':20,'fee_brl':'0.00'}],
        'request_categories':{'excecao':'manager','informacao':'unassigned'},'report_limit':20,
        'alternative_offsets_days':[1,2,3],'reservation_exception_category':'excecao'}


def configuration(*, telegram=False, authorized=False):
    raw = yaml.safe_load((ROOT/('config.telegram.example.yaml' if telegram else 'config.example.yaml')).read_text(encoding='utf-8'))
    raw['google'] = declaration()
    raw['google']['sheets']['ranges'] = ["'Operacao'!A2:J30"]
    raw['google']['limits']['max_cells'] = 1000
    raw['operations'] = parameters()
    if authorized:
        raw['operations']['authorization'].update(exclusive_pilot_resources=True,calendar_insert=True,sheets_update=True)
    raw['permissions']['resident'] += ['reservation.create','reservation.read','reservation.cancel','request.create','request.read']
    raw['permissions']['manager'] += ['request.read','request.respond','report.read','operations.reconcile']
    return raw


class FakeCalendar:
    def __init__(self):
        self.events,self.creates,self.reads = {},0,0
        self.fail_read,self.timeout,self.after_create,self.on_create = False,False,None,None
    def read_events(self, calendar_id, start, end):
        self.reads += 1
        if self.fail_read:
            raise EngineError('google_reauthorization_required')
        return {'events':deepcopy(list(self.events.values())),'complete':True}
    def create_event(self, calendar_id, event):
        self.creates += 1
        if self.on_create:
            self.on_create()
        self.events.setdefault(event['id'],{**deepcopy(event),'status':'confirmed'})
        if self.after_create:
            self.after_create(self,event)
        if self.timeout:
            raise EngineError('google_operation_uncertain')
    def get_event(self, calendar_id, event_id):
        if self.fail_read:
            raise EngineError('google_reauthorization_required')
        return deepcopy(self.events.get(event_id))


class FakeSheets:
    def __init__(self):
        self.rows,self.writes,self.fail,self.timeout = [],0,False,False
    def read_range(self, spreadsheet_id, target):
        if self.fail:
            raise EngineError('google_access_denied')
        return deepcopy(self.rows)
    def write_row(self, spreadsheet_id, target, values):
        import re
        number = int(re.search('!A([0-9]+)',target)[1])-2
        while len(self.rows) <= number:
            self.rows.append([])
        self.rows[number] = deepcopy(values)
        self.writes += 1
        if self.timeout:
            raise EngineError('google_operation_uncertain')


class OperationsCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='vert2go-i5-')
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.path = self.folder/'test.sqlite3'
        self.raw = configuration()
        self.config = _parse_config(self.raw)
        self.clock,self.calendar,self.sheets = Clock(),FakeCalendar(),FakeSheets()
        self.store = Store(self.path,operations=True)
        self.addCleanup(lambda:self.store.close())
        self.bind()
        self.resident = Scope(self.config.environment_id,'local',1001,1001)
        self.manager = Scope(self.config.environment_id,'local',2002,2002)
        for name in ('socket.socket.connect','socket.socket.connect_ex','socket.create_connection'):
            blocker = patch(name,side_effect=AssertionError('I5 offline: network forbidden'))
            blocker.start(); self.addCleanup(blocker.stop)
    def bind(self):
        self.ops = Operations(self.config,self.store,self.calendar,self.sheets,clock=self.clock,lock_root=self.folder/'locks')
        self.engine = Orchestrator(self.config,self.store,self.clock,operations=self.ops)
    def msg(self, scope=None, text='', mid=None):
        return Message(scope or self.resident,mid or str(uuid4()),self.clock(),str(uuid4()),text)
    def handle(self, action, payload, *, scope=None, message=None):
        return self.engine.handle(message or self.msg(scope),action,payload)
    def proposal(self, **fields):
        p = {'resource':'salao','start':'2026-11-06T14:00:00-03:00','end':'2026-11-06T16:00:00-03:00',**fields}
        result = self.handle('propose_reservation',p)
        self.assertEqual(result.code,'pilot_proposal',result)
        return result
    def confirm(self, proposal, *, scope=None, message=None, **extra):
        return self.handle('confirm_operation',{'operation_id':proposal.data['operation_id'],
            'proposal_hash':proposal.data['proposal_hash'],'explicit':True,**extra},scope=scope,message=message)
    def state(self, oid):
        return self.store.execute('SELECT state FROM pilot_operations WHERE operation_id=?',(oid,)).fetchone()[0]
    def reopen(self):
        self.store.close(); self.store = Store(self.path,operations=True); self.bind()
        return self.engine.startup()


class ReservationTests(OperationsCase):
    def test_T06_intent_committed_before_external_write_and_readback(self):
        proposal = self.proposal()
        self.assertEqual(self.calendar.creates,0)
        def inspect():
            con = sqlite3.connect(self.path)
            try:
                self.assertEqual(con.execute('SELECT state FROM pilot_operations').fetchone()[0],'committing')
            finally:
                con.close()
        self.calendar.on_create = inspect
        result = self.confirm(proposal)
        self.assertEqual(result.code,'reservation_confirmed',result)
        self.assertEqual(self.calendar.creates,1)
        self.assertGreaterEqual(self.calendar.reads,3)
        self.assertEqual(self.state(proposal.data['operation_id']),'confirmed')

    def test_T08_two_pending_proposals_only_one_confirmation(self):
        first,second = self.proposal(),self.proposal()
        self.assertEqual(self.confirm(first).code,'reservation_confirmed')
        self.assertEqual(self.confirm(second).status,'conflict')
        self.assertEqual(self.calendar.creates,1)

    def test_T09_duplicate_confirmation_and_new_message_do_not_duplicate(self):
        proposal,message = self.proposal(),self.msg()
        self.assertEqual(self.confirm(proposal,message=message).code,'reservation_confirmed')
        self.assertEqual(self.confirm(proposal,message=message).code,'reservation_confirmed')
        self.assertEqual(self.confirm(proposal).code,'reservation_confirmed')
        self.assertEqual(self.calendar.creates,1)
        self.assertEqual(self.store.execute('SELECT count(*) FROM pilot_outbox').fetchone()[0],1)

    def test_T10_timeout_reconciles_existing_event_without_second_post(self):
        proposal = self.proposal(); self.calendar.timeout = True
        result = self.confirm(proposal)
        self.assertEqual(result.status,'uncertain')
        self.assertEqual(self.state(proposal.data['operation_id']),'needs_reconciliation')
        result = self.handle('reconcile_operation',{'operation_id':proposal.data['operation_id']},scope=self.manager)
        self.assertEqual(result.code,'reservation_confirmed',result)
        self.assertEqual(self.calendar.creates,1)

    def test_timeout_without_event_never_reposts_and_blocks_overlap(self):
        first,second = self.proposal(),self.proposal()
        self.calendar.after_create = lambda c,e:c.events.clear()
        self.calendar.timeout = True
        self.assertEqual(self.confirm(first).status,'uncertain')
        self.assertEqual(self.confirm(second).code,'overlapping_operation_uncertain')
        self.assertEqual(self.handle('reconcile_operation',{'operation_id':first.data['operation_id']},scope=self.manager).status,'uncertain')
        self.assertEqual(self.calendar.creates,1)

    def test_T12_restart_committing_reconciles_without_replay(self):
        proposal = self.proposal()
        row = self.ops._row(self.msg(),proposal.data['operation_id'])
        event = self.ops.event(row)
        self.calendar.events[event['id']] = {**event,'status':'confirmed'}
        with self.store.transaction():
            self.store.execute("UPDATE pilot_operations SET state='committing'")
        self.reopen()
        self.assertEqual(self.state(proposal.data['operation_id']),'needs_reconciliation')
        self.assertEqual(self.handle('reservation_status',{'operation_id':proposal.data['operation_id']}).code,'reservation_confirmed')
        self.assertEqual(self.calendar.creates,0)

    def test_T17_local_confirmation_is_not_proof_of_current_existence(self):
        proposal = self.proposal(); self.confirm(proposal); self.calendar.events.clear()
        result = self.handle('reservation_status',{'operation_id':proposal.data['operation_id']})
        self.assertEqual(result.status,'uncertain')
        self.assertEqual(self.state(proposal.data['operation_id']),'needs_reconciliation')

    def test_conflict_after_creation_never_confirms_or_deletes(self):
        proposal = self.proposal()
        self.calendar.after_create = lambda c,e:c.events.update(other={**deepcopy(e),'id':'other'})
        self.assertEqual(self.confirm(proposal).status,'conflict')
        self.assertEqual(len(self.calendar.events),2)
        self.assertEqual(self.state(proposal.data['operation_id']),'conflicted')

    def test_missing_or_tampered_confirmation_and_wrong_actor_blocked(self):
        proposal = self.proposal()
        self.assertEqual(self.confirm(proposal,scope=self.manager).code,'operation_not_found')
        self.assertEqual(self.confirm(proposal,explicit=False).code,'explicit_confirmation_required')
        self.assertEqual(self.confirm(proposal,proposal_hash='bad').code,'proposal_changed')
        self.assertEqual(self.calendar.creates,0)

    def test_expired_confirmation_does_not_create(self):
        proposal = self.proposal(); self.clock.advance(minutes=6)
        self.assertEqual(self.confirm(proposal).code,'confirmation_expired')
        self.assertEqual(self.calendar.creates,0)

    def test_fee_requires_explicit_acceptance_without_payment(self):
        self.raw['operations']['resources'][0]['fee_brl'] = '125.00'
        self.config = _parse_config(self.raw); self.bind()
        proposal = self.proposal()
        self.assertEqual(self.confirm(proposal).code,'fee_acceptance_required')
        self.assertEqual(self.calendar.creates,0)
        self.assertEqual(self.confirm(proposal,accept_fee=True).code,'reservation_confirmed')

    def test_rules_changed_after_proposal_block_confirmation(self):
        proposal = self.proposal()
        self.raw['operations']['resources'][0]['fee_brl'] = '125.00'
        self.config = _parse_config(self.raw); self.bind()
        self.assertEqual(self.confirm(proposal,accept_fee=True).code,'proposal_changed')

    def test_unverified_conflicting_outdated_rules_and_invalid_intervals(self):
        for status in ('unverified','conflicting'):
            self.raw['operations']['resources'][0]['status'] = status
            self.config = _parse_config(self.raw); self.bind()
            self.assertEqual(self.handle('propose_reservation',{'resource':'salao','start':'2026-11-06T14:00:00-03:00','end':'2026-11-06T16:00:00-03:00'}).code,'document_rule_requires_review')
        self.raw['operations']['resources'][0]['status'] = 'simulated'
        self.config = _parse_config(self.raw); self.bind()
        for start,end in [('2026-11-06T07:00:00-03:00','2026-11-06T09:00:00-03:00'),
                          ('2026-11-06T14:00:00','2026-11-06T16:00:00-03:00'),
                          ('2026-11-06T21:00:00-03:00','2026-11-07T01:00:00-03:00')]:
            self.assertEqual(self.handle('propose_reservation',{'resource':'salao','start':start,'end':end}).status,'rejected')
        self.clock.advance(days=30)
        self.assertEqual(self.handle('propose_reservation',{'resource':'salao','start':'2026-11-06T14:00:00-03:00','end':'2026-11-06T16:00:00-03:00'}).code,'document_rule_outdated')

    def test_google_failure_does_not_mean_available(self):
        self.calendar.fail_read = True
        self.assertEqual(self.handle('propose_reservation',{'resource':'salao','start':'2026-11-06T14:00:00-03:00','end':'2026-11-06T16:00:00-03:00'}).code,'google_reauthorization_required')
        self.assertEqual(self.calendar.creates,0)

    def test_all_day_and_adjacent_events_half_open_interval(self):
        self.calendar.events['adjacent'] = {'id':'adjacent','status':'confirmed','start':{'dateTime':'2026-11-06T12:00:00-03:00'},'end':{'dateTime':'2026-11-06T14:00:00-03:00'}}
        proposal = self.proposal()
        self.calendar.events['day'] = {'id':'day','status':'confirmed','start':{'date':'2026-11-06'},'end':{'date':'2026-11-07'}}
        self.assertEqual(self.confirm(proposal).status,'conflict')

    def test_foreign_or_mutated_event_is_not_accepted(self):
        proposal = self.proposal()
        self.calendar.after_create = lambda c,e:c.events[e['id']]['extendedProperties']['private'].update(owner_ref='other')
        self.assertEqual(self.confirm(proposal).status,'uncertain')

    def test_crash_after_effect_before_receipt_recovers_same_proposal(self):
        message = self.msg()
        payload = {'resource':'salao','start':'2026-11-06T14:00:00-03:00','end':'2026-11-06T16:00:00-03:00'}
        proposal = self.handle('propose_reservation',payload,message=message)
        self.confirm(proposal)
        with self.store.transaction():
            self.store.execute('DELETE FROM pilot_receipts WHERE message_id=?',(message.message_id,))
        self.assertEqual(self.handle('propose_reservation',payload,message=message).code,'reservation_confirmed')
        self.assertEqual(self.calendar.creates,1)

    def test_resource_lock_shared_across_database_names(self):
        other_store = Store(self.folder/'other.sqlite3',operations=True)
        self.addCleanup(other_store.close)
        other = Operations(self.config,other_store,self.calendar,self.sheets,clock=self.clock,lock_root=self.folder/'locks')
        with self.ops.lock():
            with self.assertRaisesRegex(EngineError,'instance_already_running'):
                with other.lock():
                    self.fail('Lock was not exclusive')

    def test_T07_alternatives_are_read_and_revalidated_not_invented(self):
        original = self.proposal(); self.confirm(original)
        self.calendar.events['day2'] = {'id':'day2','status':'confirmed',
            'start':{'date':'2026-11-07'},'end':{'date':'2026-11-08'}}
        result = self.handle('propose_reservation',{'resource':'salao','start':'2026-11-06T14:00:00-03:00',
                                                 'end':'2026-11-06T16:00:00-03:00'})
        self.assertEqual(result.status,'conflict')
        self.assertEqual(len(result.data['alternatives']),2)
        self.assertTrue(all('2026-11-07' not in p['start'] for p in result.data['alternatives']))
        self.assertGreaterEqual(self.calendar.reads,7)

    def test_verified_rule_requires_current_authorized_source_and_synced_revision(self):
        rule = self.raw['operations']['resources'][0]
        rule.update(status='verified',source_document_id='doc-fictional',source_hash='a'*64)
        self.config = _parse_config(self.raw); self.bind()
        self.ops.drive = MagicMock()
        self.ops.drive.read_document.return_value = SimpleNamespace(source_version='1',sha256='a'*64)
        p = {'resource':'salao','start':'2026-11-06T14:00:00-03:00','end':'2026-11-06T16:00:00-03:00'}
        self.assertEqual(self.handle('propose_reservation',p).code,'document_rule_outdated')
        with self.store.transaction():
            self.store.execute("INSERT INTO document_sync_metadata VALUES (?,?,?,?,?,?,?,?,?,?)",
                (self.config.environment_id,'doc-fictional','1','a'*64,'official','file-test','vs_test','synced',self.clock().isoformat(),None))
        proposal = self.handle('propose_reservation',p)
        self.assertEqual(proposal.code,'pilot_proposal')
        self.ops.drive.read_document.return_value = SimpleNamespace(source_version='2',sha256='b'*64)
        self.assertEqual(self.confirm(proposal).code,'document_rule_outdated')
        self.assertEqual(self.calendar.creates,0)

    def test_real_source_change_during_alternative_lookup_still_blocks(self):
        rule=self.raw['operations']['resources'][0]
        rule.update(status='verified',source_document_id='doc-fictional',source_hash='a'*64)
        self.config=_parse_config(self.raw);self.bind();self.ops.drive=MagicMock()
        self.ops.drive.read_document.side_effect=[SimpleNamespace(source_version='1',sha256='a'*64),
                                                SimpleNamespace(source_version='2',sha256='b'*64)]
        with self.store.transaction():
            self.store.execute('INSERT INTO document_sync_metadata VALUES (?,?,?,?,?,?,?,?,?,?)',
                (self.config.environment_id,'doc-fictional','1','a'*64,'official','file-test','vs_test','synced',self.clock().isoformat(),None))
        self.calendar.events['busy']={'id':'busy','start':{'date':'2026-11-06'},'end':{'date':'2026-11-07'}}
        result=self.handle('propose_reservation',{'resource':'salao','start':'2026-11-06T14:00:00-03:00','end':'2026-11-06T16:00:00-03:00'})
        self.assertEqual(result.code,'document_rule_outdated');self.assertEqual(self.calendar.creates,0)

    def test_post_write_conflict_remains_unresolved_for_retention(self):
        proposal = self.proposal()
        self.calendar.after_create = lambda c,e:c.events.update(other={**deepcopy(e),'id':'other'})
        self.confirm(proposal)
        self.clock.advance(days=200)
        report = self.store.retention_candidates(self.config,self.clock())
        self.assertEqual(report['pilot_operations'],[])
        self.assertEqual(report['operation_log'],[])
        self.assertIsNone(self.store.execute('SELECT closed_at FROM pilot_operations').fetchone()[0])

    def test_destination_change_requires_new_proposal_and_preserves_old_outbox_target(self):
        pending = self.proposal()
        other = self.proposal(start='2026-11-07T14:00:00-03:00',end='2026-11-07T16:00:00-03:00')
        self.confirm(other)
        old_target = self.config.operations.spreadsheet_id
        self.raw['google']['sheets']['id'] = 'other-sheet-fictional'
        self.raw['operations']['authorization']['spreadsheet_id'] = 'other-sheet-fictional'
        self.config = _parse_config(self.raw); self.bind()
        self.assertEqual(self.confirm(pending).code,'operation_resource_changed')
        self.assertEqual(self.ops.sync().status,'pending')
        self.assertEqual(self.sheets.writes,0)
        self.assertEqual(self.store.execute('SELECT target_id FROM pilot_outbox').fetchone()[0],old_target)

    def test_shared_calendar_lock_also_covers_different_sheet_bindings(self):
        raw = deepcopy(self.raw)
        raw['google']['sheets']['id'] = 'other-sheet-fictional'
        raw['operations']['authorization']['spreadsheet_id'] = 'other-sheet-fictional'
        config = _parse_config(raw)
        other = Operations(config,self.store,self.calendar,self.sheets,clock=self.clock,lock_root=self.folder/'locks')
        with self.ops.lock():
            with self.assertRaisesRegex(EngineError,'instance_already_running'):
                with other.lock(): self.fail('Shared resource lock bypassed')

    def test_conflict_incident_is_forwarded_once_and_reconciles_after_external_correction(self):
        proposal = self.proposal()
        self.calendar.after_create = lambda c,e:c.events.update(other={**deepcopy(e),'id':'other'})
        self.assertEqual(self.confirm(proposal).status,'conflict')
        self.reopen(); self.engine.startup()
        requests = self.store.execute('SELECT * FROM pilot_requests').fetchall()
        self.assertEqual(len(requests),1); self.assertEqual(requests[0]['status'],'forwarded')
        self.assertEqual(self.store.execute('SELECT count(*) FROM pilot_notifications').fetchone()[0],1)
        self.calendar.events.pop('other')  # External intervention is simulated, never done by the service.
        result = self.handle('reconcile_operation',{'operation_id':proposal.data['operation_id']},scope=self.manager)
        self.assertEqual(result.code,'reservation_confirmed')
        self.assertEqual(self.calendar.creates,1)


class SheetsOutboxTests(OperationsCase):
    def trimmed_google_response(self):
        original=self.sheets.read_range
        def read(*args):
            rows=original(*args)
            for row in rows:
                while row and row[-1]=='': row.pop()
            return rows
        self.sheets.read_range=read

    def test_google_omitted_empty_trailing_cells_are_valid_readback(self):
        self.confirm(self.proposal()); self.trimmed_google_response()
        self.assertEqual(self.ops.sync().status,'success')
        self.assertEqual(self.sheets.writes,1)

    def test_google_trimmed_row_reconciles_timeout_without_second_put(self):
        self.confirm(self.proposal()); self.trimmed_google_response()
        self.sheets.timeout=True
        self.assertEqual(self.ops.sync().status,'pending')
        self.sheets.timeout=False
        self.assertEqual(self.ops.sync().status,'success')
        self.assertEqual(self.sheets.writes,1)

    def test_T11_sheets_failure_preserves_verified_reservation(self):
        proposal = self.proposal(); self.confirm(proposal); self.sheets.fail = True
        result = self.handle('sync_operations',{},scope=self.manager)
        self.assertEqual(result.status,'pending')
        self.assertEqual(self.state(proposal.data['operation_id']),'confirmed')
        self.sheets.fail = False
        self.assertEqual(self.handle('sync_operations',{},scope=self.manager).data['synced'],1)
        self.assertEqual(self.handle('sync_operations',{},scope=self.manager).data['synced'],0)
        self.assertEqual(self.sheets.writes,1)

    def test_timeout_after_sheet_write_reads_before_retry_no_duplicate(self):
        self.confirm(self.proposal()); self.sheets.timeout = True
        self.assertEqual(self.ops.sync().status,'pending')
        self.reopen()
        self.sheets.timeout = False
        self.assertEqual(self.ops.sync().data['synced'],1)
        self.assertEqual(self.sheets.writes,1)
        self.assertEqual(len(self.sheets.rows),1)

    def test_reserved_row_moved_or_replaced_is_not_overwritten(self):
        self.confirm(self.proposal()); self.sheets.timeout = True; self.ops.sync()
        self.sheets.rows[0] = ['FOREIGN DATA']
        self.sheets.timeout = False
        self.assertEqual(self.ops.sync().status,'pending')
        self.assertEqual(self.sheets.rows[0],['FOREIGN DATA'])

    def test_existing_rows_preserved_and_formula_text_passes_as_literal(self):
        self.sheets.rows = [['FOREIGN DATA']]
        proposal = self.handle('propose_request',{'category':'informacao','content':'=IMPORTXML("fictional")','urgent':False})
        self.assertEqual(self.confirm(proposal).code,'pilot_confirmed')
        self.assertEqual(self.ops.sync().data['synced'],1)
        self.assertEqual(self.sheets.rows[0],['FOREIGN DATA'])
        self.assertEqual(self.sheets.rows[1][-1],'=IMPORTXML("fictional")')


class RequestTests(OperationsCase):
    def request(self, category='excecao'):
        proposal = self.handle('propose_request',{'category':category,'content':'Solicitação fictícia','urgent':True})
        self.assertEqual(proposal.code,'pilot_proposal',proposal)
        self.assertEqual(self.confirm(proposal).code,'pilot_confirmed')
        return proposal.data['operation_id']

    def test_T13_T14_report_permissions_and_traceable_history(self):
        self.assertEqual(self.handle('operations_report',{}).code,'unauthorized')
        self.request()
        result = self.handle('operations_report',{},scope=self.manager)
        self.assertEqual(result.code,'pilot_report')
        self.assertTrue(result.data['experimental'])

    def test_T15_T16_manager_response_and_notification_are_atomic_and_unique(self):
        rid = self.request()
        result = self.handle('request_status',{})
        self.assertEqual(result.data['requests'][0]['status'],'forwarded')
        manager_view = self.handle('request_status',{'request_id':rid},scope=self.manager)
        self.assertEqual(manager_view.data['requests'][0]['content'],'Solicitação fictícia')
        p = {'request_id':rid,'expected_version':1,'response':'Resposta simulada'}
        self.assertEqual(self.handle('propose_response',p).code,'unauthorized')
        proposal = self.handle('propose_response',p,scope=self.manager)
        self.assertEqual(self.confirm(proposal,scope=self.manager).code,'pilot_confirmed')
        self.confirm(proposal,scope=self.manager)
        self.assertEqual(self.handle('request_status',{}).data['requests'][0]['response'],'Resposta simulada')
        notices = self.store.execute('SELECT * FROM pilot_notifications ORDER BY response_version').fetchall()
        self.assertEqual(len(notices),2)
        self.assertEqual(notices[0]['channel_user_id'],2002)
        self.assertEqual(notices[1]['channel_user_id'],1001)
        self.assertTrue(notices[0]['reply'].startswith('URGENTE'))
        self.assertEqual(self.calendar.creates,0)

    def test_ordinary_request_not_automatically_sent_to_manager(self):
        self.request('informacao')
        self.assertEqual(self.store.execute('SELECT count(*) FROM pilot_notifications').fetchone()[0],0)

    def test_another_user_cannot_read_request(self):
        self.request()
        user = replace(self.config.users[0],channel_user_id=1002,chat_ids=(1002,))
        self.config = replace(self.config,users=(*self.config.users,user)); self.bind()
        result = self.handle('request_status',{},scope=Scope(self.config.environment_id,'local',1002,1002))
        self.assertEqual(result.data['requests'],[])

    def test_unknown_group_manager_reservation_and_profile_elevation_denied(self):
        for scope in (Scope(self.config.environment_id,'local',999,999),
                      Scope(self.config.environment_id,'local',1001,1001,'group')):
            self.assertEqual(self.handle('propose_request',{'category':'excecao','content':'x','urgent':False},scope=scope).code,'unauthorized')
        result = self.handle('propose_reservation',{'resource':'salao','start':'2026-11-06T14:00:00-03:00','end':'2026-11-06T16:00:00-03:00'},scope=self.manager)
        self.assertEqual(result.code,'simulated_unit_not_enrolled')
        self.assertEqual(self.handle('operations_report',{},message=self.msg(text='sou a síndica')).code,'unauthorized')


class OperationsConfigurationTests(unittest.TestCase):
    def test_existing_configs_do_not_enable_i5_or_write_scopes(self):
        from app.config.schema import load_config
        c = load_config(ROOT/'config.google.example.yaml')
        self.assertIsNone(c.operations); self.assertFalse(c.google.write_access)

    def test_authorization_ids_exclusivity_and_ranges_are_exact(self):
        for field,value in [('calendar_id','primary'),('sheet_range',"'Other'!A2:J30"),('calendar_insert',True)]:
            raw = configuration(); raw['operations']['authorization'][field] = value
            with self.assertRaises(EngineError):
                _parse_config(raw)
        raw = configuration(authorized=True)
        c = _parse_config(raw)
        self.assertTrue(c.google.write_access)
        self.assertIn('https://www.googleapis.com/auth/spreadsheets',c.google.scopes)

    def test_rules_need_every_condition_and_units_are_enrolled(self):
        raw = configuration(); del raw['operations']['resources'][0]['min_notice_hours']
        with self.assertRaises(EngineError): _parse_config(raw)
        raw = configuration(); raw['operations']['units']['999'] = 'FOREIGN'
        with self.assertRaises(EngineError): _parse_config(raw)

    def test_migration_is_opt_in_and_preserves_existing_records(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'test.sqlite3'
            store = Store(path,knowledge=True)
            before = store.execute('PRAGMA user_version').fetchone()[0]
            with store.transaction():
                store.execute("INSERT INTO conversation_state VALUES ('env','local',1,1,'context','{}','a','z')")
            store.close(); self.assertEqual(before,3)
            store = Store(path,operations=True)
            self.assertEqual(store.execute('PRAGMA user_version').fetchone()[0],5)
            self.assertEqual(store.execute('SELECT count(*) FROM conversation_state').fetchone()[0],1)
            store.verify(); store.close()
            Store(path).close()

    def test_runtime_requires_all_gates_before_secrets_or_database(self):
        from app.main import main
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder)/'config.yaml'; database = Path(folder)/'absent.sqlite3'
            config.write_text(yaml.safe_dump(configuration(telegram=True)),encoding='utf-8')
            with patch('app.main.load_telegram_token') as token:
                self.assertEqual(main(['--config',str(config),'--database',str(database),'--operations']),1)
                self.assertEqual(main(['--config',str(config),'--database',str(database),'--operations',
                    '--telegram','--allow-live-telegram','--knowledge','--allow-live-openai','--allow-live-google-writes']),1)
            token.assert_not_called(); self.assertFalse(database.exists())

    def test_oauth_write_scope_consent_is_explicit_before_secret_access(self):
        from scripts.setup_google_i3 import authorize
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            (path/'config.yaml').write_text(yaml.safe_dump(configuration(authorized=True)),encoding='utf-8')
            with self.assertRaisesRegex(EngineError,'live_google_writes_authorization_required'):
                authorize(path,allow_live=True)


class OperationsHTTPTests(unittest.TestCase):
    def setUp(self):
        self.config = _parse_config(configuration(authorized=True))
        self.session,self.bearer = MagicMock(),MagicMock(return_value='NEVER-LOG-TOKEN')
        self.http = OperationsHTTP(self.config,self.bearer,allow_live=True,session=self.session)
        self.addCleanup(self.http.close)

    def test_wrong_resource_row_and_method_denied_before_auth(self):
        for call in (lambda:self.http.event_request('DELETE',self.config.google.calendar_id,event_id='a'*64),
                     lambda:self.http.event_request('GET','foreign',event_id='a'*64),
                     lambda:self.http.row_request(self.config.google.spreadsheet_id,"'Other'!A2:J2",['']*10),
                     lambda:self.http.row_request(self.config.google.spreadsheet_id,"'Operacao'!A31:J31",['']*10)):
            with self.assertRaises(EngineError): call()
        self.bearer.assert_not_called(); self.session.request.assert_not_called()

    def test_RAW_prevents_formula_interpretation_and_only_one_attempt(self):
        self.session.request.return_value = response({'updatedRows':1})
        self.http.row_request(self.config.google.spreadsheet_id,"'Operacao'!A2:J2",['=1+1']*10)
        args,kw = self.session.request.call_args
        self.assertEqual(args[0],'PUT'); self.assertEqual(kw['params'],{'valueInputOption':'RAW'})
        self.assertEqual(kw['json']['values'],[['=1+1']*10])
        self.assertFalse(kw['allow_redirects'])

    def test_timeout_does_not_retry_write_or_expose_transport_error(self):
        import requests
        self.session.request.side_effect = requests.Timeout('SECRET BODY')
        with self.assertRaisesRegex(EngineError,'^google_operation_uncertain$'):
            self.http.row_request(self.config.google.spreadsheet_id,"'Operacao'!A2:J2",['']*10)
        self.assertEqual(self.session.request.call_count,1)

    def test_disabled_authorization_blocks_even_injected_transport(self):
        config = _parse_config(configuration())
        http = OperationsHTTP(config,self.bearer,allow_live=True,session=self.session)
        with self.assertRaisesRegex(EngineError,'experimental_writes_authorization_required'):
            http.row_request(config.google.spreadsheet_id,"'Operacao'!A2:J2",['']*10)
        self.bearer.assert_not_called()

    def test_deterministic_calendar_insert_and_collision_requires_readback(self):
        oid = str(uuid4()); env = self.config.environment_id
        event = {'id':digest([env,oid]),'summary':'Reserva experimental Alfredo','description':'Simulação sem validade oficial.',
            'start':{'dateTime':'2026-11-06T14:00:00-03:00','timeZone':'America/Sao_Paulo'},
            'end':{'dateTime':'2026-11-06T16:00:00-03:00','timeZone':'America/Sao_Paulo'},
            'extendedProperties':{'private':{'operation_id':oid,'environment_id':env,'resource_id':'salao',
                                           'owner_ref':'a'*64,'proposal_hash':'b'*64}}}
        self.session.request.return_value = response({},409)
        self.assertEqual(self.http.event_request('POST',self.config.google.calendar_id,event=event),{})
        args,kw = self.session.request.call_args
        self.assertEqual(args[0],'POST'); self.assertEqual(kw['params'],{'sendUpdates':'none'})
        self.assertEqual(kw['json']['id'],event['id'])
        self.session.reset_mock(); self.bearer.reset_mock()
        event['extendedProperties']['private']['environment_id'] = 'foreign'
        with self.assertRaises(EngineError):
            self.http.event_request('POST',self.config.google.calendar_id,event=event)
        self.bearer.assert_not_called(); self.session.request.assert_not_called()
