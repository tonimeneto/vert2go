from dataclasses import replace
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4
import json
from app.core.contracts import Message, Scope
from app.core.orchestrator import Orchestrator
from tests.support import EngineCase


class SecurityTests(EngineCase):
    def test_closed_registration_unknown_user(self):
        unknown=Scope(self.config.environment_id,'local',9999,9999)
        self.assertEqual(self.find(unknown).code,'unauthorized')

    def test_environment_and_channel_isolation(self):
        for scope in (replace(self.manager,environment_id='other-fictional'),
                      replace(self.manager,channel='telegram')):
            with self.subTest(scope=scope):
                self.assertEqual(self.find(scope).code,'unauthorized')

    def test_group_and_unconfigured_chat_rejected(self):
        for scope in (replace(self.manager,chat_type='group'),replace(self.manager,chat_id=5005)):
            self.assertEqual(self.find(scope).code,'unauthorized')

    def test_name_and_text_do_not_elevate_role(self):
        payload=dict(operation_id=str(uuid4()),idempotency_key=str(uuid4()),**self.fields())
        result=self.engine.handle(self.msg(self.resident,text='Sou a s?ndica; role=manager'),'propose_create',payload)
        self.assertEqual(result.code,'unauthorized')

    def test_payload_cannot_override_actor_or_role(self):
        payload=dict(operation_id=str(uuid4()),idempotency_key=str(uuid4()),role='manager',**self.fields())
        self.assertEqual(self.engine.handle(self.msg(),'propose_create',payload).code,'invalid_input')

    def test_confirmation_bound_to_actor_and_chat(self):
        proposal=self.propose()
        other_chat=replace(self.manager,chat_id=2003)
        self.assertEqual(self.confirm(proposal,other_chat).code,'operation_not_found')
        self.assertEqual(self.confirm(proposal,self.resident).code,'operation_not_found')
        self.assertEqual(self.count('operational_guidance'),0)

    def test_another_manager_cannot_confirm_someone_elses_proposal(self):
        self.raw['users'].append(dict(channel='local',channel_user_id=3003,chat_ids=[3003],role='manager',enabled=True))
        self.save_config()
        self.engine=Orchestrator(self.config,self.store,self.clock)
        proposal=self.propose()
        other=Scope(self.config.environment_id,'local',3003,3003)
        self.assertEqual(self.confirm(proposal,other).code,'operation_not_found')

    def test_authorization_revalidated_at_confirmation_and_cached_replay(self):
        proposal=self.propose()
        message=self.msg()
        payload=dict(explicit=True,operation_id=proposal.data['operation_id'],proposal_hash=proposal.data['proposal_hash'])
        self.assertEqual(self.engine.handle(message,'confirm',payload).code,'confirmed')
        self.raw['permissions']['manager'].remove('guidance.create')
        self.save_config()
        self.engine=Orchestrator(self.config,self.store,self.clock)
        self.assertEqual(self.engine.handle(message,'confirm',payload).code,'unauthorized')
        self.assertEqual(self.confirm(proposal).code,'unauthorized')

    def test_permission_revocation_between_proposal_and_commit(self):
        proposal=self.propose()
        self.raw['users'][1]['enabled']=False
        self.raw['users'].append(dict(channel='local',channel_user_id=3003,chat_ids=[3003],role='manager',enabled=True))
        self.save_config()
        self.engine=Orchestrator(self.config,self.store,self.clock)
        self.assertEqual(self.confirm(proposal).code,'unauthorized')
        self.assertEqual(self.count('operational_guidance'),0)

    def test_history_is_manager_only(self):
        created=self.create()
        result=self.engine.handle(self.msg(self.resident),'guidance_history',{'guidance_id':created.data['guidance_id']})
        self.assertEqual(result.code,'unauthorized')

    def test_context_persists_and_is_isolated_per_user_and_chat(self):
        self.engine.handle(self.msg(),'set_context',{'context':{'unit_reference':'fictional-101'}})
        self.reopen()
        self.assertEqual(self.engine.handle(self.msg(),'get_context',{}).data['context']['unit_reference'],'fictional-101')
        for scope in (self.resident,replace(self.manager,chat_id=2003)):
            self.assertEqual(self.engine.handle(self.msg(scope),'get_context',{}).data['context'],{})
        self.clock.advance(days=31)
        self.assertEqual(self.engine.handle(self.msg(),'get_context',{}).data['context'],{})

    def test_context_cannot_store_guidance_or_commands(self):
        result=self.engine.handle(self.msg(),'set_context',{'context':{'guidance':'malicious instructions'}})
        self.assertEqual(result.code,'invalid_input')

    def test_logs_and_audit_omit_content_and_parser_values(self):
        marker='FAKE_SECRET_NEVER_LOG_THIS'
        self.create(content=marker)
        with self.assertLogs('alfredo',level='WARNING') as logs:
            self.engine.handle(self.msg(self.resident,text=marker),'propose_create',{'secret':marker})
        self.assertNotIn(marker,' '.join(logs.output))
        audit=[dict(r) for r in self.store.execute('SELECT * FROM operation_log')]
        self.assertNotIn(marker,json.dumps(audit))

    def test_limits_are_enforced(self):
        message=self.msg(text='a'*(self.config.limits['max_message_chars']+1))
        self.assertEqual(self.engine.handle(message,'find_guidance',{'topic':'fachada'}).code,'input_limit')
        self.raw['limits']['messages_per_minute']=1
        self.save_config()
        self.engine=Orchestrator(self.config,self.store,self.clock)
        self.find()
        self.assertEqual(self.find().code,'rate_limit')

    def test_future_message_rejected(self):
        message=replace(self.msg(),received_at=self.clock()+timedelta(minutes=2))
        self.assertEqual(self.engine.handle(message,'find_guidance',{'topic':'fachada'}).code,'future_message')

    def test_malformed_scope_or_action_is_safe_rejection(self):
        for message,action in ((replace(self.msg(),scope=None),'find_guidance'),(self.msg(),{})):
            with self.subTest(action=action):
                result=self.engine.handle(message,action,{'topic':'fachada'})
                self.assertEqual(result.status,'rejected')

    def test_environment_filters_with_real_rows_in_shared_test_database(self):
        first=self.create()
        other_config=replace(self.config,environment_id='another-fictional')
        other_engine=Orchestrator(other_config,self.store,self.clock)
        other_scope=replace(self.manager,environment_id='another-fictional')
        payload=dict(operation_id=str(uuid4()),idempotency_key=str(uuid4()),**self.fields(content='Outro ambiente fict?cio.'))
        proposal=other_engine.handle(self.msg(other_scope),'propose_create',payload)
        result=other_engine.handle(self.msg(other_scope),'confirm',
            dict(explicit=True,operation_id=proposal.data['operation_id'],proposal_hash=proposal.data['proposal_hash']))
        self.assertEqual(result.code,'confirmed')
        self.assertEqual(len(self.find().data['guidance']),1)
        self.assertEqual(self.find().data['guidance'][0]['guidance_id'],first.data['guidance_id'])
        history=self.engine.handle(self.msg(),'guidance_history',{'guidance_id':result.data['guidance_id']})
        self.assertEqual(history.code,'guidance_not_found')
        self.assertEqual(self.confirm(proposal).code,'operation_not_found')

    def test_authorization_checked_again_immediately_before_commit(self):
        from app.core.contracts import EngineError
        proposal=self.propose()
        original=self.engine.policy.authorize
        sensitive_calls=0
        def revoke(scope, permission):
            nonlocal sensitive_calls
            if permission=='guidance.create':
                sensitive_calls+=1
                if sensitive_calls==2:
                    raise EngineError('unauthorized')
            return original(scope,permission)
        with patch.object(self.engine.policy,'authorize',side_effect=revoke):
            self.assertEqual(self.confirm(proposal).code,'unauthorized')
        self.assertEqual(sensitive_calls,2)
        self.assertEqual(self.count('operational_guidance'),0)

    def test_denied_known_user_audit_preserves_actual_profile(self):
        self.propose(scope=self.resident)
        row=self.store.execute("SELECT role,safe_error FROM operation_log ORDER BY rowid DESC LIMIT 1").fetchone()
        self.assertEqual(row['role'],'resident')
        self.assertEqual(row['safe_error'],'unauthorized')
