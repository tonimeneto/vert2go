from datetime import datetime, timezone
from uuid import uuid4
from app.ai.client import LocalBudget
from app.core.contracts import EngineError, stamp
from tests.support import EngineCase


class BudgetTests(EngineCase):
    def setUp(self):
        super().setUp()
        self.budget=LocalBudget(self.config,self.store,self.clock)

    def record_brl(self, value, **kwargs):
        return self.budget.record_simulated(str(uuid4()),0,0,search_usd=str(value/5),**kwargs)

    def test_accumulation_alert_block_and_estimate_before_call(self):
        self.assertTrue(self.budget.assess()['allowed'])
        self.record_brl(23)
        self.assertFalse(self.budget.assess()['alert'])
        self.record_brl(1)
        self.assertTrue(self.budget.assess()['alert'])
        self.assertFalse(self.budget.assess('7')['allowed'])
        self.record_brl(6)
        result=self.budget.assess()
        self.assertEqual(result['estimated_brl'],'30.000000')
        self.assertFalse(result['allowed'])

    def test_missing_measurement_blocks_conservatively(self):
        self.budget.record_simulated(str(uuid4()),None,2)
        self.assertEqual(self.budget.assess()['reason'],'measurement_missing')

    def test_month_rollover_uses_sao_paulo_midnight(self):
        self.clock.now=datetime(2026,12,1,2,59,tzinfo=timezone.utc)
        self.record_brl(30)
        self.assertEqual(self.budget.assess()['period'],'2026-11')
        self.assertFalse(self.budget.assess()['allowed'])
        self.clock.advance(minutes=1)
        self.assertEqual(self.budget.assess()['period'],'2026-12')
        self.assertTrue(self.budget.assess()['allowed'])

    def test_token_pricing_fx_and_reference_saved(self):
        result=self.budget.record_simulated(str(uuid4()),1000000,1000000)
        self.assertEqual(result['estimated_brl'],'15.000000')
        row=self.store.execute('SELECT * FROM usage_ledger').fetchone()
        self.assertEqual(row['cost_usd'],'3.00')
        self.assertIn('fictitious-test-prices',row['assumption'])
        self.assertEqual(row['model'],'local-fictional')

    def test_usage_idempotency_and_mismatched_reuse(self):
        uid=str(uuid4())
        self.budget.record_simulated(uid,1000000,0)
        self.budget.record_simulated(uid,1000000,0)
        self.assertEqual(self.count('usage_ledger'),1)
        with self.assertRaisesRegex(EngineError,'usage_identity_conflict'):
            self.budget.record_simulated(uid,2000000,0)

    def test_invalid_measurements_rejected(self):
        for value in (-1,True,'NaN'):
            with self.subTest(value=value):
                with self.assertRaises(EngineError):
                    self.budget.record_simulated(str(uuid4()),value,0)

    def test_already_incurred_over_budget_is_recorded(self):
        self.record_brl(31)
        self.assertFalse(self.budget.assess()['allowed'])

    def test_storage_and_search_costs_count(self):
        result=self.budget.record_simulated(str(uuid4()),0,0,searches=2,search_usd='1',storage_usd='2')
        self.assertEqual(result['estimated_brl'],'15.000000')

    def test_budget_persists_after_restart(self):
        self.record_brl(30)
        self.reopen()
        self.budget=LocalBudget(self.config,self.store,self.clock)
        self.assertFalse(self.budget.assess()['allowed'])


class RetentionTests(EngineCase):
    def candidates(self):
        return self.store.retention_candidates(self.config,self.clock())

    def test_live_guidance_beyond_thirty_days_preserved(self):
        from datetime import timedelta
        created=self.create(effective_until=(self.clock()+timedelta(days=60)).isoformat())
        self.clock.advance(days=31)
        report=self.candidates()
        self.assertNotIn(created.data['guidance_id'],report['operational_guidance'])
        self.assertEqual(len(self.find().data['guidance']),1)

    def test_context_and_dedup_age_eligible_without_deletion(self):
        self.engine.handle(self.msg(),'set_context',{'context':{'unit_reference':'fake-101'}})
        before=self.count('conversation_state')
        self.clock.advance(days=31)
        report=self.candidates()
        self.assertTrue(report['conversation_state'])
        self.assertTrue(report['processed_messages'])
        self.assertEqual(self.count('conversation_state'),before)

    def test_open_operation_and_incident_preserve_evidence(self):
        proposal=self.propose()
        self.clock.advance(days=120)
        report=self.candidates()
        self.assertEqual(report['conversation_state'],[])
        self.assertEqual(report['processed_messages'],[])
        self.assertEqual(report['requests_state'],[])
        self.store.execute("""UPDATE requests_state SET state='failed',closed_at=?,incident_open=1,
            incident_reason='fixture: unresolved local incident'""", (stamp(self.clock()),))
        self.clock.advance(days=120)
        report=self.candidates()
        self.assertEqual(report['conversation_state'],[])
        self.assertEqual(report['processed_messages'],[])

    def test_cancelled_guidance_ninety_days_and_incident_hold(self):
        created=self.create()
        self.confirm(self.propose('cancel',guidance_id=created.data['guidance_id'],expected_version=1))
        self.clock.advance(days=89)
        self.assertEqual(self.candidates()['operational_guidance'],[])
        self.clock.advance(days=2)
        self.assertIn(created.data['guidance_id'],self.candidates()['operational_guidance'])
        self.store.execute("""UPDATE operational_guidance SET incident_open=1,incident_reason='fixture: unresolved'""")
        self.assertEqual(self.candidates()['operational_guidance'],[])

    def test_expired_guidance_retention_anchored_to_end(self):
        from datetime import timedelta
        created=self.create(effective_until=(self.clock()+timedelta(hours=1)).isoformat())
        self.clock.advance(days=92)
        self.engine.startup()
        self.assertIn(created.data['guidance_id'],self.candidates()['operational_guidance'])

    def test_audit_ninety_days_and_incident_hold(self):
        self.find()
        self.clock.advance(days=91)
        self.assertTrue(self.candidates()['operation_log'])
        self.store.execute("""UPDATE operation_log SET incident_open=1,incident_reason='fixture: unresolved'""")
        self.assertEqual(self.candidates()['operation_log'],[])

    def test_closed_request_ninety_days(self):
        proposal=self.propose()
        self.store.execute("UPDATE requests_state SET state='failed',closed_at=?",(stamp(self.clock()),))
        self.clock.advance(days=89)
        self.assertEqual(self.candidates()['requests_state'],[])
        self.clock.advance(days=2)
        self.assertIn(proposal.data['operation_id'],self.candidates()['requests_state'])
