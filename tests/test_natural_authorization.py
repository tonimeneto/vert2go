"""User journeys with fake Telegram only: no developer-supplied IDs or magic words."""
from dataclasses import replace
from datetime import datetime
import json
from unittest.mock import MagicMock
from app.channels.telegram import TelegramChannel,TelegramError
from app.config.schema import _parse_config
from app.core.contracts import EngineError,instant
from examples.i2_demo import FakeTelegram,update
from tests.test_operations import OperationsCase,configuration
from tests.test_operations_conversation import intent


class TelegramConversationCase(OperationsCase):
    def setUp(self):
        super().setUp()
        self.raw=configuration(telegram=True);self.config=_parse_config(self.raw);self.bind()
        from app.core.contracts import Scope
        self.resident=Scope(self.config.environment_id,'telegram',1001,1001)
        self.manager=Scope(self.config.environment_id,'telegram',2002,2002)
        self.api=FakeTelegram();self.interpreter=MagicMock();self.build()

    def build(self):
        self.channel=TelegramChannel(self.config,self.store,self.engine,self.api,clock=self.clock,
                                     operation_interpreter=self.interpreter)

    def message(self,number,text,actor=1001,parent=None):
        entry=update(number,text,self.clock,actor)
        if parent is not None:
            entry['message']['reply_to_message']={'message_id':parent,
                'from':{'id':9009,'is_bot':True},'chat':{'id':actor,'type':'private'}}
        return entry

    def send(self,number,text,actor=1001,parent=None,extracted=None):
        if extracted is not None:self.interpreter.interpret.return_value=extracted
        entry=self.message(number,text,actor,parent)
        code=self.channel.process(entry);self.channel._queue_operation_notices();self.channel.deliver()
        return code

    def reserve(self,number=1,start='2026-11-06T14:00:00-03:00',end='2026-11-06T16:00:00-03:00'):
        a,b=datetime.fromisoformat(start),datetime.fromisoformat(end)
        text='Quero reservar o salão de '+a.strftime('%d/%m/%Y às %H:%M')+' até '+b.strftime('%d/%m/%Y às %H:%M')
        return self.send(number,text,extracted=intent('reservation',resource='salao',start=start,end=end))

    def last_for(self,actor):
        return next(index for index in range(len(self.api.sent),0,-1) if self.api.sent[index-1]['chat_id']==actor)


class NaturalAuthorizationTests(TelegramConversationCase):
    def test_two_roles_finish_request_and_response_without_commands_or_developer_references(self):
        self.send(1,'Preciso pedir uma exceção à administração',extracted=intent('request',category='excecao',content='Pedido fictício',urgent=False))
        self.assertIn('Posso registrar e encaminhar',self.api.sent[-1]['text'])
        self.assertTrue(self.api.sent[-1]['reply_markup']['force_reply'])
        self.assertEqual(self.send(2,'Sim, pode encaminhar',parent=1),'pilot_confirmed')
        notice=self.last_for(2002)
        self.assertIn('Pedido fictício',self.api.sent[notice-1]['text'])
        calls=self.interpreter.interpret.call_count
        self.assertEqual(self.send(3,'Recebi. Vou avaliar esse pedido.',2002,notice),'pilot_proposal')
        self.assertEqual(self.interpreter.interpret.call_count,calls)
        self.assertIn('Posso enviar essa resposta ao morador?',self.api.sent[-1]['text'])
        self.assertEqual(self.store.execute('SELECT status FROM pilot_requests').fetchone()[0],'forwarded')
        response=self.last_for(2002)
        self.assertEqual(self.send(4,'Pode enviar',2002,response),'pilot_confirmed')
        row=self.store.execute('SELECT status,response,version FROM pilot_requests').fetchone()
        self.assertEqual(tuple(row),('resolved','Recebi. Vou avaliar esse pedido.',2))
        replies=[m for m in self.api.sent if m['chat_id']==1001 and m['text'].startswith('A administração respondeu')]
        self.assertEqual(len(replies),1)
        for message in self.api.sent:
            self.assertNotRegex(message['text'],r'[a-f0-9]{8}-[a-f0-9]{4}-')
            self.assertNotIn('/confirmar',message['text']);self.assertNotIn('versão',message['text'])
        self.channel.process(self.message(4,'Pode enviar',2002,response))
        self.channel._queue_operation_notices();self.channel.deliver()
        self.assertEqual(len([m for m in self.api.sent if m['text'].startswith('A administração respondeu')]),1)

    def test_sim_authorizes_only_a_delivered_reservation_question(self):
        self.reserve();self.assertEqual(self.calendar.creates,0)
        self.assertEqual(self.send(2,'Sim!',parent=1),'reservation_confirmed')
        self.assertEqual(self.calendar.creates,1)
        self.assertNotIn('Referência',self.api.sent[-1]['text'])
        self.send(3,'sim')
        self.assertEqual(self.calendar.creates,1)

    def test_manager_is_asked_to_sync_and_no_sheet_write_occurs_before_separate_approval(self):
        self.send(1,'Pedido',extracted=intent('request',category='excecao',content='Fictício'))
        self.send(2,'Sim',parent=1)
        self.send(3,'Recebido. Apenas ensaio.',2002,self.last_for(2002))
        self.send(4,'Pode enviar',2002,self.last_for(2002))
        self.assertIn('Posso sincronizar',self.api.sent[self.last_for(2002)-1]['text'])
        self.assertEqual(self.sheets.rows,[])
        question=self.last_for(2002)
        self.assertEqual(self.send(5,'Sim, pode',2002,question),'pilot_sync')
        self.assertEqual(self.store.execute("SELECT count(*) FROM pilot_outbox WHERE state='synced'").fetchone()[0],2)
        attempts=self.store.execute('SELECT sum(attempts) FROM pilot_outbox').fetchone()[0]
        self.send(6,'Sim',2002,question)
        self.assertEqual(self.store.execute('SELECT sum(attempts) FROM pilot_outbox').fetchone()[0],attempts)

    def test_natural_sync_request_requires_permission_and_then_explicit_approval(self):
        self.assertEqual(self.send(1,'Atualize a planilha'),'unauthorized')
        p=self.handle('propose_request',{'category':'excecao','content':'Fictício','urgent':False});self.confirm(p)
        self.assertEqual(self.send(2,'Atualize a planilha',2002),'pilot_sync_proposal')
        self.assertEqual(self.sheets.rows,[])
        self.assertEqual(self.send(3,'Não',2002,self.last_for(2002)),'pilot_declined')
        self.assertEqual(self.sheets.rows,[])

    def test_sync_consent_cannot_be_reused_after_destination_change(self):
        p=self.handle('propose_request',{'category':'excecao','content':'Fictício','urgent':False});self.confirm(p)
        self.send(1,'Atualize a planilha',2002)
        original=self.ops.destinations
        self.ops.destinations=lambda:{**original(),'sheet_range':'changed'}
        self.assertEqual(self.send(2,'Sim',2002,self.last_for(2002)),'operation_resource_changed')
        self.assertEqual(self.sheets.rows,[])

    def test_multiple_requests_are_bound_to_the_notice_replied_to(self):
        self.send(1,'Pedido A',extracted=intent('request',category='excecao',content='Pedido A'))
        self.send(2,'Sim',parent=1);first=self.last_for(2002)
        self.send(3,'Pedido B',extracted=intent('request',category='excecao',content='Pedido B'))
        self.send(4,'Sim',parent=self.last_for(1001))
        self.assertEqual(self.send(5,'Resposta ao pedido',2002),'request_choice_required')
        self.assertEqual(self.send(6,'Recebido A',2002,first),'pilot_proposal')
        self.send(7,'Pode enviar',2002,self.last_for(2002))
        rows={r['content']:r['status'] for r in self.store.execute('SELECT content,status FROM pilot_requests')}
        self.assertEqual(rows,{'Pedido A':'resolved','Pedido B':'forwarded'})

    def test_ok_to_authorization_question_is_not_an_automatic_write(self):
        self.reserve();calls=self.interpreter.interpret.call_count
        self.assertEqual(self.send(2,'Ok',parent=1),'pilot_proposal')
        self.assertEqual(self.calendar.creates,0)
        self.assertEqual(self.interpreter.interpret.call_count,calls)
        self.assertIn('Posso confirmar',self.api.sent[-1]['text'])

    def test_no_declines_the_unexecuted_proposal_and_preserves_history(self):
        self.reserve();self.assertEqual(self.send(2,'Não',parent=1),'pilot_declined')
        self.assertEqual(self.calendar.creates,0)
        self.assertEqual(self.store.execute('SELECT state FROM pilot_operations').fetchone()[0],'cancelled')

    def test_permission_to_cancel_does_not_create_a_reservation(self):
        self.reserve()
        self.assertEqual(self.send(2,'Tá bom, pode cancelar então',parent=1),'pilot_declined')
        self.assertEqual(self.calendar.creates,0)

    def test_natural_polite_permission_is_not_a_magic_word(self):
        self.reserve()
        self.assertEqual(self.send(2,'Tá bom, pode reservar então.',parent=1),'reservation_confirmed')
        self.assertEqual(self.calendar.creates,1)

    def test_conditional_permission_is_not_an_unconditional_authorization(self):
        self.reserve()
        self.send(2,'Pode reservar se alguém concordar',parent=1,extracted=intent('clarify',clarification_field='unspecified'))
        self.assertEqual(self.calendar.creates,0)

    def test_negative_question_is_not_permission(self):
        self.reserve()
        self.send(2,'Não! Pode reservar?',parent=1,extracted=intent('clarify',clarification_field='unspecified'))
        self.assertEqual(self.calendar.creates,0)

    def test_permission_for_a_different_action_or_target_does_not_execute(self):
        self.reserve()
        self.assertEqual(self.send(2,'Pode enviar a resposta',parent=1),'pilot_proposal')
        self.assertEqual(self.calendar.creates,0)
        self.assertEqual(self.send(3,'Pode registrar essa reserva',parent=self.last_for(1001)),'reservation_confirmed')
        self.assertEqual(self.calendar.creates,1)

    def test_sim_to_response_body_question_is_content_not_execution_permission(self):
        self.send(1,'Pedido',extracted=intent('request',category='excecao',content='Fictício'))
        self.send(2,'Sim',parent=1);notice=self.last_for(2002)
        self.assertEqual(self.send(3,'Sim',2002,notice),'pilot_proposal')
        self.assertEqual(self.store.execute('SELECT status FROM pilot_requests').fetchone()[0],'forwarded')
        data=json.loads(self.store.execute("SELECT proposal FROM pilot_operations WHERE kind='response'").fetchone()[0])
        self.assertEqual(data['response'],'Sim')
        self.assertIn('Posso enviar',self.api.sent[-1]['text'])

    def test_response_body_that_mentions_reservation_remains_literal_content(self):
        self.send(1,'Pedido',extracted=intent('request',category='excecao',content='Fictício'))
        self.send(2,'Sim',parent=1)
        body='Quero reservar o salão dia 16/11/2026. Qual data disponível?'
        self.assertEqual(self.send(3,body,2002,self.last_for(2002)),'pilot_proposal')
        data=json.loads(self.store.execute("SELECT proposal FROM pilot_operations WHERE kind='response'").fetchone()[0])
        self.assertEqual(data['response'],body)
        self.assertEqual(self.calendar.reads,0);self.assertEqual(self.calendar.creates,0)

    def test_multiple_proposals_need_a_reply_to_the_selected_question(self):
        self.reserve()
        self.reserve(2,'2026-11-07T14:00:00-03:00','2026-11-07T16:00:00-03:00')
        self.assertEqual(self.send(3,'Sim'),'ambiguous_confirmation')
        self.assertEqual(self.calendar.creates,0)
        self.assertEqual(self.send(4,'Sim',parent=1),'reservation_confirmed')
        self.assertEqual(self.calendar.creates,1)
        self.assertEqual(self.store.execute("SELECT count(*) FROM pilot_operations WHERE state='awaiting_confirmation'").fetchone()[0],1)

    def test_different_actor_cannot_authorize_someone_elses_question(self):
        self.reserve()
        self.assertEqual(self.send(2,'Sim',2002,1),'pilot_authorization_missing')
        self.assertEqual(self.calendar.creates,0)

    def test_expired_question_cannot_authorize_a_write(self):
        self.reserve();self.clock.advance(seconds=self.config.limits['confirmation_seconds']+1)
        self.send(2,'Sim',parent=1)
        self.assertEqual(self.calendar.creates,0)

    def test_unsent_question_cannot_authorize_a_write(self):
        real=self.api.call
        def failed(method,parameters):
            if method=='sendMessage':raise TelegramError('telegram_transport_error')
            return real(method,parameters)
        self.api.call=failed;self.reserve();self.api.call=real
        self.send(2,'Sim',parent=1)
        self.assertEqual(self.calendar.creates,0)

    def test_reply_binding_survives_restart(self):
        self.reserve();self.reopen();self.build()
        self.assertEqual(self.send(2,'Sim, pode reservar',parent=1),'reservation_confirmed')
        self.assertEqual(self.calendar.creates,1)

    def test_fee_acceptance_remains_separate_and_explicit(self):
        self.raw['operations']['resources'][0]['fee_brl']='10.00'
        self.config=_parse_config(self.raw);self.bind();self.build()
        self.reserve()
        self.assertEqual(self.send(2,'Sim',parent=1),'fee_acceptance_required')
        self.assertEqual(self.calendar.creates,0)
        self.assertEqual(self.send(3,'Sim, aceito a taxa',parent=len(self.api.sent)),'reservation_confirmed')
        self.assertEqual(self.calendar.creates,1)

    def test_correction_replaces_only_unexecuted_proposal_and_asks_again(self):
        self.reserve()
        self.send(2,'Mude o horário para as 16h até as 17h',parent=1,
            extracted=intent('reservation',resource='salao',start='2026-11-06T16:00:00-03:00',end='2026-11-06T17:00:00-03:00'))
        self.assertEqual(self.calendar.creates,0)
        self.assertEqual(self.store.execute("SELECT count(*) FROM pilot_operations WHERE state='cancelled'").fetchone()[0],1)
        self.assertEqual(self.send(3,'Sim',parent=len(self.api.sent)),'reservation_confirmed')
        self.assertEqual(self.calendar.creates,1)
        self.assertEqual(instant(next(iter(self.calendar.events.values()))['start']['dateTime']),instant('2026-11-06T16:00:00-03:00'))

    def test_message_replay_with_a_different_reply_target_is_rejected(self):
        self.reserve();entry=self.message(2,'Sim',parent=1);self.channel.process(entry)
        changed=self.message(2,'Sim',parent=99)
        with self.assertRaisesRegex(EngineError,'message_identity_conflict'):self.channel.process(changed)
        self.assertEqual(self.calendar.creates,1)

    def test_role_change_invalidates_natural_authorization(self):
        self.send(1,'Aviso',2002,extracted=intent('guidance_create',topic='fachada',content='Fictício',audience='residents',
            effective_from='2026-11-05T11:00:00-03:00',effective_until='2026-11-05T18:00:00-03:00'))
        users=tuple(replace(u,role='resident') if u.channel_user_id==2002 else u for u in self.config.users)
        self.engine.policy.config=replace(self.config,users=users)
        self.send(2,'Sim',2002,1)
        self.assertEqual(self.store.execute('SELECT count(*) FROM operational_guidance').fetchone()[0],0)

    def test_guidance_correction_uses_current_internal_version_and_topic(self):
        self.send(1,'Aviso',2002,extracted=intent('guidance_create',topic='fachada',content='Fictício',audience='residents',
            effective_from='2026-11-05T11:00:00-03:00',effective_until='2026-11-05T18:00:00-03:00'))
        self.send(2,'Sim, pode registrar',2002,1)
        self.send(3,'Corrija o aviso da fachada',2002,extracted=intent('guidance_correct',topic='fachada',content='Novo texto fictício'))
        self.assertIn('Posso registrar essa alteração?',self.api.sent[-1]['text'])
        self.send(4,'Pode registrar',2002,len(self.api.sent))
        self.assertEqual(self.store.execute('SELECT current_version FROM operational_guidance').fetchone()[0],2)
