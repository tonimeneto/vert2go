"""I5 owner/manager journeys and injected failures. No operational data/network."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime,timezone
import json
import unittest
from unittest.mock import MagicMock
from unittest.mock import patch
import sqlite3
from app.config.schema import _parse_config
from app.core.contracts import EngineError,Scope
from app.integrations.operations import OperationsHTTP
from tests.test_google import response
from tests.test_operations import configuration,FakeCalendar
import tests.test_operations as operations_support
from tests.test_natural_authorization import TelegramConversationCase


class CancellableCalendar(FakeCalendar):
    def __init__(self):
        super().__init__();self.cancels=0;self.fail_before=False;self.fail_after=False;self.on_cancel=None
    def create_event(self,calendar_id,event):
        super().create_event(calendar_id,event)
        self.events[event['id']]['etag']='"created"'
    def cancel_event(self,calendar_id,event_id,etag):
        self.cancels+=1
        if self.on_cancel:self.on_cancel()
        if self.fail_before:raise EngineError('google_operation_uncertain')
        if self.events[event_id]['etag']!=etag:raise EngineError('calendar_precondition_failed')
        self.events[event_id].update(status='cancelled',etag='"cancelled"')
        if self.fail_after:raise EngineError('google_operation_uncertain')


class CancellationTests(TelegramConversationCase):
    def setUp(self):
        super().setUp()
        self.raw=configuration(telegram=True,authorized=True)
        self.raw['operations']['units']={'1001':'62','2002':'52'}
        self.raw['operations']['authorization']['calendar_cancel']=True
        self.raw['google']['calendar'].update(window_start='2026-11-10T00:00:00-03:00',window_end='2026-11-17T00:00:00-03:00')
        self.clock.now=datetime(2026,11,13,12,tzinfo=timezone.utc)
        self.config=_parse_config(self.raw);self.calendar=CancellableCalendar();self.bind();self.build()
        self.interpreter.interpret.side_effect=AssertionError('Explicit cancellation must not need model guesses')

    def booking(self,actor=1001,start='2026-11-16T16:00:00-03:00',end='2026-11-16T19:00:00-03:00'):
        scope=self.resident if actor==1001 else self.manager
        proposal=self.handle('propose_reservation',{'resource':'salao','start':start,'end':end},scope=scope)
        self.assertEqual(proposal.code,'pilot_proposal',proposal)
        result=self.confirm(proposal,scope=scope)
        self.assertEqual(result.code,'reservation_confirmed',result)
        return proposal

    def last_text(self,actor=1001):return self.api.sent[self.last_for(actor)-1]['text']

    def cancellation(self,proposal,scope=None):
        result=self.handle('propose_reservation_cancellation',{'reservation_id':proposal.data['operation_id']},scope=scope)
        self.assertEqual(result.code,'pilot_proposal',result)
        return result

    def execute_cancel(self,p,scope=None,message=None):
        return self.handle('confirm_reservation_cancellation',{'operation_id':p.data['operation_id'],'proposal_hash':p.data['proposal_hash'],'explicit':True},scope=scope,message=message)

    def test_own_reservation_natural_confirmation_and_history(self):
        booking=self.booking();before=self.store.execute('SELECT count(*) FROM operation_log').fetchone()[0]
        self.assertEqual(self.send(1,'Alfredo, quero cancelar minha reserva do salão.'),'pilot_proposal')
        self.assertIn('16:00',self.last_text());self.assertIn('19:00',self.last_text())
        self.assertEqual(self.calendar.cancels,0)
        self.assertEqual(self.send(2,'Pode cancelar',parent=self.last_for(1001)),'reservation_cancelled')
        self.assertEqual(self.calendar.cancels,1)
        self.assertEqual(self.state(booking.data['operation_id']),'cancelled')
        self.assertGreater(self.store.execute('SELECT count(*) FROM operation_log').fetchone()[0],before)
        payloads=[json.loads(r[0]) for r in self.store.execute('SELECT payload FROM pilot_outbox')]
        self.assertEqual({p[3] for p in payloads},{'reservation','reservation_cancellation'})
        self.assertEqual([p[4] for p in payloads if p[3]=='reservation_cancellation'],['cancelled'])

    def test_crossing_two_bookings_requires_choice_then_separate_permission(self):
        first=self.booking();second=self.booking(start='2026-11-16T19:00:00-03:00',end='2026-11-16T22:00:00-03:00')
        self.assertEqual(self.send(1,'Quero cancelar a reserva do dia 16/11/2026 das 18 as 20'),'cancellation_choice_required')
        self.assertIn('cruza',self.last_text());self.assertIn('16:00 às 19:00',self.last_text());self.assertIn('19:00 às 22:00',self.last_text())
        self.assertEqual(self.send(2,'Sim'),'cancellation_choice_required')
        self.assertEqual(self.calendar.cancels,0)
        self.assertEqual(self.send(3,'A segunda'),'pilot_proposal')
        self.assertIn('19:00',self.last_text());self.assertEqual(self.calendar.cancels,0)
        self.assertEqual(self.send(4,'Sim',parent=self.last_for(1001)),'reservation_cancelled')
        self.assertEqual(self.state(first.data['operation_id']),'confirmed');self.assertEqual(self.state(second.data['operation_id']),'cancelled')

    def test_other_unit_and_manager_cannot_cancel_someone_elses_booking(self):
        booking=self.booking()
        result=self.handle('propose_reservation_cancellation',{'reservation_id':booking.data['operation_id']},scope=self.manager)
        self.assertEqual(result.code,'operation_not_found');self.assertEqual(self.calendar.cancels,0)
        mine=self.booking(2002,start='2026-11-16T19:00:00-03:00',end='2026-11-16T22:00:00-03:00')
        self.assertEqual(self.handle('propose_reservation_cancellation',{'reservation_id':mine.data['operation_id']}).code,'operation_not_found')

    def test_decline_expiry_and_unconfirmed_cancel_have_no_effect(self):
        self.booking();self.send(1,'Quero cancelar minha reserva do salão')
        self.assertEqual(self.send(2,'Não',parent=self.last_for(1001)),'pilot_declined')
        self.assertEqual(self.calendar.cancels,0)
        self.send(3,'Quero cancelar minha reserva do salão');self.clock.advance(minutes=10)
        self.assertNotEqual(self.send(4,'Sim'),'reservation_cancelled');self.assertEqual(self.calendar.cancels,0)

    def test_repeated_confirmation_and_already_cancelled_never_patch_again(self):
        booking=self.booking();p=self.cancellation(booking);m=self.msg()
        self.assertEqual(self.execute_cancel(p,message=m).code,'reservation_cancelled')
        self.assertEqual(self.execute_cancel(p,message=m).code,'reservation_cancelled')
        self.assertEqual(self.handle('propose_reservation_cancellation',{'reservation_id':booking.data['operation_id']}).code,'reservation_already_cancelled')
        self.assertEqual(self.calendar.cancels,1)
        self.assertEqual(self.store.execute("SELECT count(*) FROM pilot_outbox WHERE json_extract(payload,'$[3]')='reservation_cancellation'").fetchone()[0],1)

    def test_timeout_after_patch_is_recovered_by_read_only_after_restart(self):
        booking=self.booking();p=self.cancellation(booking);self.calendar.fail_after=True
        self.assertEqual(self.execute_cancel(p).code,'cancellation_reconciliation_required')
        self.reopen();self.build()
        result=self.handle('reconcile_reservation_cancellation',{'operation_id':p.data['operation_id']})
        self.assertEqual(result.code,'reservation_cancelled');self.assertEqual(self.calendar.cancels,1)

    def test_timeout_before_patch_and_repeated_approval_do_not_retry_write(self):
        booking=self.booking();p=self.cancellation(booking);self.calendar.fail_before=True
        self.assertEqual(self.execute_cancel(p).code,'cancellation_reconciliation_required')
        self.assertEqual(self.execute_cancel(p).code,'cancellation_reconciliation_required')
        self.assertEqual(self.calendar.cancels,1);self.assertEqual(self.state(booking.data['operation_id']),'confirmed')

    def test_event_changed_after_proposal_requires_new_authorization(self):
        booking=self.booking();p=self.cancellation(booking)
        event=next(iter(self.calendar.events.values()));event['etag']='"edited"'
        self.assertEqual(self.execute_cancel(p).code,'cancellation_target_changed');self.assertEqual(self.calendar.cancels,0)

    def test_conditional_patch_prevents_race_and_is_not_retried(self):
        booking=self.booking();p=self.cancellation(booking)
        self.calendar.on_cancel=lambda:next(iter(self.calendar.events.values())).update(etag='"raced"')
        self.assertEqual(self.execute_cancel(p).code,'cancellation_target_changed')
        self.assertEqual(self.calendar.cancels,1);self.assertEqual(self.state(booking.data['operation_id']),'confirmed')

    def test_cancelled_booking_stops_blocking_calendar_and_sheet_failure_is_independent(self):
        booking=self.booking();p=self.cancellation(booking);self.execute_cancel(p)
        self.assertEqual(self.handle('propose_reservation',{'resource':'salao','start':'2026-11-16T16:00:00-03:00','end':'2026-11-16T19:00:00-03:00'}).code,'pilot_proposal')
        self.sheets.fail=True
        self.assertGreater(self.handle('sync_operations',{},scope=self.manager).data['pending'],0)
        self.assertEqual(self.state(booking.data['operation_id']),'cancelled')
        self.sheets.fail=False;self.assertEqual(self.handle('sync_operations',{},scope=self.manager).data['pending'],0)
        writes=self.sheets.writes;self.handle('sync_operations',{},scope=self.manager);self.assertEqual(self.sheets.writes,writes)

    def test_manager_inherits_all_resident_features_for_own_unit_only(self):
        self.assertTrue(self.config.permissions['resident']<=self.config.permissions['manager'])
        self.assertEqual(self.send(1,'Quero reservar o salão dia 16/11/2026 das 16h às 19h',2002),'pilot_proposal')
        self.assertIn('52',self.last_text(2002))
        self.assertEqual(self.send(2,'Sim',2002,self.last_for(2002)),'reservation_confirmed')
        self.assertEqual(self.send(3,'Quero cancelar minha reserva do salão',2002),'pilot_proposal')
        self.assertEqual(self.send(4,'Pode cancelar',2002,self.last_for(2002)),'reservation_cancelled')
        self.assertEqual(self.handle('operations_report',{}).code,'unauthorized')
        self.assertEqual(self.handle('propose_response',{'request_id':'x','expected_version':1,'response':'x'}).code,'unauthorized')

    def test_legacy_unit_mapping_preserves_original_without_cross_account_authority(self):
        booking=self.booking()
        self.raw['operations']['units']['1001']='63';self.raw['operations']['legacy_units']={'1001':['62']}
        self.config=_parse_config(self.raw);self.bind()
        p=self.cancellation(booking);self.assertEqual(p.data['unit_reference'],'63');self.assertEqual(p.data['original_unit_reference'],'62')
        self.assertEqual(self.execute_cancel(p).code,'reservation_cancelled')
        original=self.store.execute('SELECT proposal FROM pilot_operations WHERE operation_id=?',(booking.data['operation_id'],)).fetchone()[0]
        self.assertEqual(json.loads(original)['unit_reference'],'62')

    def test_pending_cancellation_keeps_audit_and_context_out_of_retention(self):
        booking=self.booking();p=self.cancellation(booking);self.calendar.fail_before=True;self.execute_cancel(p)
        self.clock.advance(days=200)
        eligible=self.store.retention_candidates(self.config,self.clock())
        self.assertEqual(eligible['pilot_cancellations'],[]);self.assertEqual(eligible['operation_log'],[])

    def test_startup_recovers_committing_without_network_or_repeated_patch(self):
        booking=self.booking();p=self.cancellation(booking)
        self.ops.cancellations.transition(self.msg(),self.ops.cancellations.row(self.msg(),p.data['operation_id']),'committing')
        self.assertEqual(self.ops.startup(),1)
        self.assertEqual(self.calendar.cancels,0)

    def test_second_proposal_for_same_booking_cannot_duplicate_the_effect(self):
        booking=self.booking();a=self.cancellation(booking);b=self.cancellation(booking)
        self.assertEqual(self.execute_cancel(a).code,'reservation_cancelled')
        self.assertEqual(self.execute_cancel(b).code,'reservation_already_cancelled')
        self.assertEqual(self.calendar.cancels,1)

    def test_changed_unit_without_explicit_legacy_binding_blocks_confirmation(self):
        booking=self.booking();p=self.cancellation(booking)
        self.raw['operations']['units']['1001']='63';self.config=_parse_config(self.raw);self.bind()
        self.assertEqual(self.execute_cancel(p).code,'reservation_unit_changed')
        self.assertEqual(self.calendar.cancels,0)

    def test_manager_inheritance_is_independent_of_name_or_numeric_identity(self):
        for u in self.raw['users']:
            if u['role']=='manager':u.update(channel_user_id=3003,chat_ids=[3003])
        del self.raw['operations']['units']['2002'];self.raw['operations']['units']['3003']='77'
        self.config=_parse_config(self.raw);self.manager=Scope(self.config.environment_id,'telegram',3003,3003);self.bind()
        booking=self.booking(2002);p=self.cancellation(booking,self.manager)
        self.assertEqual(p.data['unit_reference'],'77')
        self.assertEqual(self.execute_cancel(p,self.manager).code,'reservation_cancelled')

    def test_semantic_cancellation_uses_same_owner_scoped_executor(self):
        from tests.test_operations_conversation import intent
        self.booking();self.interpreter.interpret.side_effect=None
        self.assertEqual(self.send(1,'Não vou mais precisar do salão que marquei.',extracted=intent('reservation_cancel')),'pilot_proposal')
        self.assertEqual(self.calendar.cancels,0)
        self.assertIn('cancelar integralmente',self.last_text())

    def test_new_booking_and_help_are_not_hijacked_by_a_cancellation_choice(self):
        self.booking();self.booking(start='2026-11-16T19:00:00-03:00',end='2026-11-16T22:00:00-03:00')
        self.send(1,'Quero cancelar minha reserva do salão')
        self.assertEqual(self.send(2,'/ajuda'),'pilot_help')
        self.assertEqual(self.send(3,'Quero reservar o salão dia 16/11/2026 das 08h às 10h'),'pilot_proposal')
        self.assertEqual(self.calendar.cancels,0)

    def test_natural_repeat_after_uncertain_patch_reconciles_without_new_write(self):
        booking=self.booking();p=self.cancellation(booking);self.calendar.fail_after=True
        self.execute_cancel(p);self.reopen();self.build()
        self.assertEqual(self.send(1,'Quero cancelar minha reserva do salão'),'reservation_cancelled')
        self.assertEqual(self.calendar.cancels,1)

    def test_confirmation_must_be_explicit_and_proposal_hash_valid(self):
        booking=self.booking();p=self.cancellation(booking)
        data={'operation_id':p.data['operation_id'],'proposal_hash':p.data['proposal_hash'],'explicit':False}
        self.assertEqual(self.handle('confirm_reservation_cancellation',data).code,'explicit_confirmation_required')
        self.assertEqual(self.handle('confirm_reservation_cancellation',{**data,'explicit':True,'proposal_hash':'bad'}).code,'proposal_changed')
        self.assertEqual(self.calendar.cancels,0)

    def test_new_retry_request_requires_a_new_proposal_and_approval(self):
        self.booking();self.send(1,'Quero cancelar minha reserva do salão')
        self.calendar.fail_before=True
        self.assertEqual(self.send(2,'Pode cancelar',parent=self.last_for(1001)),'cancellation_reconciliation_required')
        self.calendar.fail_before=False
        self.assertEqual(self.send(3,'Tente novamente'),'pilot_proposal')
        self.assertEqual(self.calendar.cancels,1)
        self.assertEqual(self.send(4,'Sim',parent=self.last_for(1001)),'reservation_cancelled')
        self.assertEqual(self.calendar.cancels,2)
        self.assertEqual(self.store.execute("SELECT count(*) FROM pilot_cancellations WHERE state='confirmed'").fetchone()[0],1)

    def test_sqlite_failure_after_patch_rolls_back_and_recovers_without_patch_replay(self):
        booking=self.booking();p=self.cancellation(booking)
        original=self.store.audit
        def fail(*args,**kwargs):
            if len(args)>3 and args[2]=='pilot.reservation_cancellation' and args[3]=='confirmed':raise sqlite3.OperationalError('injected commit failure')
            return original(*args,**kwargs)
        with patch.object(self.store,'audit',side_effect=fail):
            self.assertEqual(self.execute_cancel(p).code,'storage_error')
        self.assertEqual(self.state(booking.data['operation_id']),'confirmed')
        self.reopen();self.build()
        self.assertEqual(self.handle('reconcile_reservation_cancellation',{'operation_id':p.data['operation_id']}).code,'reservation_cancelled')
        self.assertEqual(self.calendar.cancels,1)


class CancellationHTTPTests(unittest.TestCase):
    def setUp(self):operations_support.OperationsHTTPTests.setUp(self)
    def test_patch_is_status_only_and_conditional(self):
        raw=configuration(authorized=True);raw['operations']['authorization']['calendar_cancel']=True
        config=_parse_config(raw);http=OperationsHTTP(config,self.bearer,allow_live=True,session=self.session)
        self.addCleanup(http.close);self.session.request.return_value=response({'id':'a'*64,'status':'cancelled'})
        http.cancel_request(config.operations.calendar_id,'a'*64,'"version"')
        args,kwargs=self.session.request.call_args
        self.assertEqual(args[0],'PATCH');self.assertEqual(kwargs['json'],{'status':'cancelled'})
        self.assertEqual(kwargs['headers']['If-Match'],'"version"');self.assertFalse(kwargs['allow_redirects'])

    def test_patch_requires_separate_destination_consent(self):
        with self.assertRaisesRegex(EngineError,'calendar_cancellation_not_authorized'):
            self.http.cancel_request(self.config.operations.calendar_id,'a'*64,'"version"')
        self.session.request.assert_not_called()

    def test_patch_precondition_failure_is_never_retried(self):
        raw=configuration(authorized=True);raw['operations']['authorization']['calendar_cancel']=True
        config=_parse_config(raw);http=OperationsHTTP(config,self.bearer,allow_live=True,session=self.session);self.addCleanup(http.close)
        self.session.request.return_value=response({},412)
        with self.assertRaisesRegex(EngineError,'calendar_precondition_failed'):http.cancel_request(config.operations.calendar_id,'a'*64,'"version"')
        self.assertEqual(self.session.request.call_count,1)
