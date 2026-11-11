from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from app.ai.configuration import validate_api_key
from app.ai.openai_http import OpenAIHTTP
from app.ai.runtime_budget import RuntimeBudget
from app.channels.telegram import TelegramChannel
from app.config.schema import _parse_config, load_enrollment_secrets, load_telegram_token, read_yaml
from app.core.contracts import EngineError, Scope, canonical, digest
from app.core.orchestrator import Orchestrator
from app.integrations.drive import DocumentRead
from app.integrations.google_auth import validate_secret_document
from app.services.knowledge import Knowledge
from app.storage.sqlite import Store
from examples.i2_demo import FakeTelegram, update
from scripts.setup_openai_i4 import configure, enroll_key
from tests.support import EngineCase, ROOT

CONTENT = b'# Piscina\nA piscina funciona das 8h as 22h.\n'
HASH = hashlib.sha256(CONTENT).hexdigest()


def knowledge_raw():
    return {'enabled':True,'project_id':'proj_fictional','model':'model-fictional','vector_store_id':None,
            'authorization':{'accepted_i3':True,'authorized_at':'2026-11-05T12:00:00Z','telegram':True},
            'documents':[{'id':'doc-fictional','title':'Regulamento fictício','sha256':HASH}],
            'limits':{'timeout_seconds':2,'max_question_chars':1000,'max_output_tokens':512,'max_results':2,
                      'max_response_bytes':65536,'max_poll_attempts':2,'poll_seconds':1,
                      'max_storage_bytes':1000000,'max_input_tokens':16384},
            'prices':{'search_usd_per_call':'0.0025','storage_usd_per_gb_day':'0.10',
                      'reference_date':'2026-11-05','reference_url':'https://developers.openai.com/api/docs/pricing'}}


class KnowledgeModelConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='vert2go-i4-model-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.raw = read_yaml(ROOT/'config.google.example.yaml')
        second = deepcopy(self.raw['google']['drive_documents'][0])
        second['id'] = 'doc-fictional-2'
        self.raw['google']['drive_documents'].append(second)
        self.documents = [{'id':doc['id'],'title':'Documento fictício','sha256':HASH}
                          for doc in self.raw['google']['drive_documents']]
        self.consent = {'authorized_at':'2026-11-10T12:00:00Z','telegram_document_tests':'authorized'}
        self.path = self.root/'config.yaml'
        self.path.write_text(__import__('yaml').safe_dump(self.raw),encoding='utf-8')
        self.secrets = self.root/'secrets.yaml'
        self.secrets.write_bytes(b'FICTIONAL_SECRET_NOT_TO_BE_READ_BY_CONFIGURE')
        for target in ('socket.socket.connect','socket.socket.connect_ex','socket.create_connection',
                       'scripts.setup_openai_i4.load_enrollment_secrets'):
            guard = patch(target,side_effect=AssertionError('No network or secret reads in configuration tests'))
            guard.start()
            self.addCleanup(guard.stop)

    def candidate(self):
        raw = deepcopy(self.raw)
        raw['knowledge'] = knowledge_raw()
        return raw

    def test_default_enrollment_model_is_validated_and_atomically_saved(self):
        with patch('scripts.setup_openai_i4.pilot_documents',return_value=(self.documents,self.consent)), \
             patch('app.integrations.private_files.private_acl'), \
             patch('builtins.input',return_value='proj_FICTIONAL_VALID123') as prompt:
            configure(self.root)
        saved = read_yaml(self.path)
        self.assertEqual(_parse_config(saved).knowledge.model,'gpt-4.1-mini-2025-04-14')
        self.assertEqual(saved['knowledge']['project_id'],'proj_FICTIONAL_VALID123')
        self.assertEqual(saved['knowledge']['documents'],self.documents)
        self.assertEqual(saved['google'],self.raw['google'])
        self.assertEqual(saved['users'],self.raw['users'])
        self.assertEqual(saved['channels'],self.raw['channels'])
        self.assertEqual(self.secrets.read_bytes(),b'FICTIONAL_SECRET_NOT_TO_BE_READ_BY_CONFIGURE')
        prompt.assert_called_once()

    def test_model_names_accept_dots_without_rewriting_the_identifier(self):
        for model in ('gpt-4.1-mini-2025-04-14','model.1-test','model-fictional','m'+'a'*199):
            with self.subTest(model=model):
                raw = self.candidate(); raw['knowledge']['model'] = model
                self.assertEqual(_parse_config(raw).knowledge.model,model)

    def test_invalid_model_names_remain_rejected(self):
        for model in (None,True,123,'','model name','model/name','https://example.invalid/model',
                      'model\n','model\x00','m'+'a'*200,'.model','model?query=1'):
            with self.subTest(model=model):
                raw = self.candidate(); raw['knowledge']['model'] = model
                with self.assertRaisesRegex(EngineError,'knowledge_configuration_invalid'):
                    _parse_config(raw)

    def test_project_and_vector_store_identifier_rules_are_unchanged(self):
        for field,value in (('project_id','proj_invalid.with.dot'),('project_id','wrong_prefix'),
                            ('vector_store_id','vs_invalid.with.dot'),('vector_store_id','wrong_prefix')):
            with self.subTest(field=field,value=value):
                raw = self.candidate(); raw['knowledge'][field] = value
                with self.assertRaisesRegex(EngineError,'knowledge_configuration_invalid'):
                    _parse_config(raw)

    def test_invalid_model_fails_before_lock_or_partial_configuration_write(self):
        before = self.path.read_bytes()
        with patch('scripts.setup_openai_i4.pilot_documents',return_value=(self.documents,self.consent)), \
             patch('scripts.setup_openai_i4.private_lock') as lock:
            with self.assertRaisesRegex(EngineError,'knowledge_configuration_invalid'):
                configure(self.root,project_id='proj_FICTIONAL_VALID123',model='invalid/model')
        lock.assert_not_called()
        self.assertEqual(self.path.read_bytes(),before)
        self.assertEqual(self.secrets.read_bytes(),b'FICTIONAL_SECRET_NOT_TO_BE_READ_BY_CONFIGURE')
        self.assertFalse(list(self.root.glob('*.lock')))
        self.assertFalse(list(self.root.glob('.*.tmp')))


class FakeDrive:
    def __init__(self):
        self.value = DocumentRead(CONTENT,'text/markdown','1','2026-11-05T12:00:00Z',HASH,'simulation')
        self.calls = 0
    def read_document(self, doc):
        self.calls += 1
        if doc != 'doc-fictional':
            raise AssertionError('Wrong document')
        return self.value


class FakeOpenAI:
    def __init__(self, pilot):
        self.pilot, self.files, self.attributes, self.calls = pilot, {}, {}, []
        self.answer_calls = 0
        self.custom = None
        self.index_status = 'completed'
        self.index_usage = 4096
    def create_store(self, reference):
        self.calls.append('store')
        return {'id':'vs_fictional','metadata':{'pilot_ref':reference}}
    def store(self, sid):
        self.calls.append('storage')
        return {'id':sid,'metadata':{'pilot_ref':self.pilot},'usage_bytes':self.index_usage}
    def upload(self, cid, content, mime):
        self.calls.append('upload')
        fid = 'file-fictional'+str(len(self.files)+1)
        self.files[fid] = {'id':fid,'filename':'alfredo-'+cid+'.md'}
        return {'id':fid}
    def file(self, fid):
        return self.files[fid]
    def attach(self, sid, fid, attrs):
        self.calls.append('attach')
        self.attributes[fid] = attrs
        return {'id':fid}
    def tag_file(self, sid, fid, attrs):
        self.calls.append('tag')
        self.attributes[fid] = attrs
        return {'id':fid}
    def indexed_file(self, sid, fid):
        return {'id':fid,'vector_store_id':sid,'attributes':self.attributes[fid],'status':self.index_status}
    def answer(self, question, sid, generation, file_ids):
        self.answer_calls += 1
        self.answer_files = tuple(file_ids)
        if self.custom is not None:
            if isinstance(self.custom, BaseException):
                raise self.custom
            return deepcopy(self.custom)
        fid = next(iter(self.files))
        return self.response(fid)
    def response(self, fid):
        return {'id':'resp_fictional','model':'model-fictional','status':'completed',
                'usage':{'input_tokens':120,'output_tokens':80},
                'output':[{'type':'file_search_call','status':'completed',
                           'results':[{'file_id':fid,'text':CONTENT.decode(),'attributes':self.attributes[fid]}]},
                          {'type':'message','role':'assistant','content':[{'type':'output_text','text':canonical({
                              'status':'answered','claims':[{'text':'Às 23h a piscina está fora do horário documentado.',
                                  'file_id':fid,'quote':'A piscina funciona das 8h as 22h.','section':'Piscina'}]})}]}]}


class KnowledgeTests(EngineCase):
    def setUp(self):
        super().setUp()
        google = json.loads(json.dumps(__import__('yaml').safe_load((ROOT/'config.google.example.yaml').read_text(encoding='utf-8'))))['google']
        self.raw['google'] = google
        self.raw['knowledge'] = knowledge_raw()
        for perms in self.raw['permissions'].values():
            perms.append('knowledge.read')
        self.save_config()
        self.store.close()
        self.store = Store(self.database,knowledge=True)
        self.drive = FakeDrive()
        self.provider = FakeOpenAI(digest([self.config.environment_id,self.config.knowledge.project_id]))
        self.service = Knowledge(self.config,self.store,self.drive,self.provider,clock=self.clock,sleep=lambda _:None)
        self.engine = Orchestrator(self.config,self.store,self.clock,knowledge=self.service)

    def sync(self):
        return self.service.sync()

    def question(self, scope=None, text='Posso dar um mergulho às onze da noite?'):
        return self.msg(scope or self.resident,text=text)

    def response(self):
        return self.provider.response(next(iter(self.provider.files)))

    def set_claim(self, value):
        response = self.response()
        response['output'][1]['content'][0]['text'] = canonical(value)
        self.provider.custom = response

    def test_opt_in_migration_preserves_existing_context_and_legacy_open(self):
        self.assertEqual(self.store.execute('PRAGMA user_version').fetchone()[0],3)
        self.store.verify()
        self.engine.handle(self.msg(),'set_context',{'context':{'unit_reference':'fake-101'}})
        self.store.close()
        self.store = Store(self.database)
        self.assertEqual(self.store.execute('SELECT count(*) FROM conversation_state').fetchone()[0],1)
        self.store.verify()

    def test_sync_then_paraphrase_has_verified_excerpt_and_source(self):
        self.assertEqual(self.sync()['status'],'synced')
        result = self.service.answer(self.question())
        self.assertEqual(result.code,'knowledge_answer')
        self.assertIn('Regulamento fictício',result.data['reply'])
        self.assertIn('8h as 22h',result.data['reply'])
        self.assertEqual(len(result.data['references']),1)
        self.assertEqual(self.count('knowledge_versions'),1)
        self.assertEqual(self.count('requests_state'),0)

    def test_repeat_sync_has_no_second_upload_or_attach(self):
        self.sync(); self.sync()
        self.assertEqual(self.provider.calls.count('upload'),1)
        self.assertEqual(self.provider.calls.count('attach'),1)

    def test_missing_evidence_is_safe_and_still_records_usage(self):
        self.sync()
        self.set_claim({'status':'insufficient','claims':[]})
        result = self.service.answer(self.question())
        self.assertEqual(result.code,'knowledge_insufficient')
        row = self.store.execute("SELECT * FROM usage_ledger WHERE input_tokens=120").fetchone()
        self.assertEqual(row['model'],'model-fictional')
        self.assertIs(json.loads(row['assumption'])['simulation'],False)

    def test_document_conflict_does_not_arbitrate(self):
        self.sync(); self.set_claim({'status':'conflict','claims':[]})
        self.assertEqual(self.service.answer(self.question()).code,'knowledge_conflict')

    def test_unregistered_file_even_with_plausible_text_is_rejected(self):
        self.sync(); response = self.response()
        response['output'][0]['results'][0]['file_id'] = 'file-unauthorized'
        self.provider.custom = response
        self.assertEqual(self.service.answer(self.question()).code,'knowledge_evidence_invalid')

    def test_invented_quote_and_section_are_rejected(self):
        self.sync()
        fid = next(iter(self.provider.files))
        for quote,section in (('Regra inventada sem evidencia.',None),('A piscina funciona das 8h as 22h.','Página 999')):
            self.set_claim({'status':'answered','claims':[{'text':'Texto','file_id':fid,'quote':quote,'section':section}]})
            self.assertEqual(self.service.answer(self.question()).code,'knowledge_evidence_invalid')

    def test_citation_accepts_only_layout_changes_and_records_the_matching_mode(self):
        self.sync(); response = self.response()
        response['output'][0]['results'][0]['text'] = '# Piscina\nA piscina funciona das **8h as 22h**.\n'
        self.provider.custom = response
        result = self.service.answer(self.question())
        self.assertEqual(result.code,'knowledge_answer')
        self.assertEqual(result.data['references'][0]['quote_match'],'layout_normalized')

    def test_citation_normalization_never_changes_words_numbers_or_math(self):
        from app.services.knowledge import citation_text
        self.assertEqual(citation_text('mandato **bienal (2 anos)**,\n permitida a reeleição.'),
                         'mandato bienal (2 anos), permitida a reeleição.')
        self.assertEqual(citation_text('2**3**4'),'2**3**4')
        self.sync(); response = self.response()
        response['output'][0]['results'][0]['text'] = '# Piscina\nA piscina funciona das **8h as 21h**.\n'
        self.provider.custom = response
        self.assertEqual(self.service.answer(self.question()).code,'knowledge_evidence_invalid')

    def test_wrapped_bold_garage_rule_supports_the_bicycle_question(self):
        self.sync(); response = self.response()
        source = (ROOT/'docs/4S_Regulamento_interno.md').read_text(encoding='utf-8')
        paragraph = 'Só é permitido utilizar a vaga'+source.split('Só é permitido utilizar a vaga',1)[1].split('\n\n',1)[0]
        quote = ' '.join(paragraph.replace('**','').split())
        response['output'][0]['results'][0]['text'] = '# Garagem\n'+paragraph
        fid = next(iter(self.provider.files))
        response['output'][1]['content'][0]['text'] = canonical({'status':'answered','claims':[{
            'text':'Não. A vaga é destinada a um veículo automotor, carro ou moto.',
            'file_id':fid,'quote':quote,'section':'Garagem'}]})
        self.provider.custom = response
        result = self.service.answer(self.question(text='Posso estacionar bicicleta na minha vaga de garagem?'))
        self.assertEqual(result.code,'knowledge_answer')
        self.assertEqual(result.data['references'][0]['quote_match'],'layout_normalized')
        self.assertIn('carro ou moto',result.data['reply'])

    def test_wrapped_bold_apartment_list_preserves_three_spaces_for_62(self):
        self.sync(); response = self.response()
        source = (ROOT/'docs/4S_convencao_condominio.md').read_text(encoding='utf-8')
        paragraph = 'II. possuem direito correspondente'+source.split('II. possuem direito correspondente',1)[1].split('\n\nIII.',1)[0]
        quote = ' '.join(paragraph.replace('**','').split())
        response['output'][0]['results'][0]['text'] = paragraph
        fid = next(iter(self.provider.files))
        def candidate(value):
            response['output'][1]['content'][0]['text'] = canonical({'status':'answered','claims':[{
                'text':'O apartamento 62 tem direito a três vagas indeterminadas.',
                'file_id':fid,'quote':value,'section':None}]})
            self.provider.custom = response
            return self.service.answer(self.question(text='Quantas vagas tem o apartamento 62?'))
        self.assertEqual(candidate(quote.replace('3 vagas','2 vagas')).code,'knowledge_evidence_invalid')
        self.assertEqual(candidate(quote.replace('61, 62, 71','61, 63, 71')).code,'knowledge_evidence_invalid')
        result = candidate(quote)
        self.assertEqual(result.code,'knowledge_answer')
        self.assertEqual(result.data['references'][0]['quote_match'],'layout_normalized')

    def test_wrapped_bold_does_not_allow_omitted_words_or_joined_chunks(self):
        self.sync(); response = self.response()
        chunk = 'Permitido **um veículo\nautomotor, carro ou moto** por vaga.'
        fid = next(iter(self.provider.files))
        response['output'][0]['results'] = [
            {'file_id':fid,'text':chunk},
            {'file_id':fid,'text':'Outra regra independente.'}]
        for quote in ('Permitido um veículo por vaga.',
                      'carro ou moto por vaga. Outra regra independente.'):
            response['output'][1]['content'][0]['text'] = canonical({'status':'answered','claims':[{
                'text':'Afirmação sem apoio contínuo.','file_id':fid,'quote':quote,'section':None}]})
            self.provider.custom = response
            self.assertEqual(self.service.answer(self.question()).code,'knowledge_evidence_invalid')

    def test_stitched_live_garage_citation_is_rejected_with_safe_reason(self):
        self.sync(); response = self.response()
        source = (ROOT/'docs/4S_Regulamento_interno.md').read_text(encoding='utf-8')
        block = source.split('## Garagem\n',1)[1].split('\n## ',1)[0]
        response['output'][0]['results'][0]['text'] = '# Garagem\n'+block
        fid = next(iter(self.provider.files))
        paragraph = 'Só é permitido utilizar a vaga'+block.split('Só é permitido utilizar a vaga',1)[1].split('\n\n',1)[0]
        quote = ' '.join(paragraph.replace('**','').split())+' Não use sua vaga como depósito.'
        response['output'][1]['content'][0]['text'] = canonical({'status':'answered','claims':[{
            'text':'Não. A vaga é destinada a carro ou moto.','file_id':fid,'quote':quote,'section':'Garagem'}]})
        self.provider.custom = response
        message = self.question(text='Posso estacionar bicicleta na minha vaga de garagem')
        with self.assertLogs('alfredo.knowledge',level='INFO') as logs:
            result = self.service.answer(message)
        self.assertEqual(result.code,'knowledge_evidence_invalid')
        self.assertEqual(result.data['validation_error'],'quote_not_found')
        self.assertEqual(set(result.data),{'reply','validation_error'})
        self.assertIn('reason=quote_not_found',' '.join(logs.output))
        self.assertNotIn(quote,' '.join(logs.output))
        self.assertNotIn(message.text,' '.join(logs.output))
        saved = self.store.execute('SELECT result FROM knowledge_calls WHERE call_id=?',
                                   (digest([message.scope.key(),message.message_id]),)).fetchone()[0]
        self.assertEqual(json.loads(saved)['data'],result.data)

    def test_bad_section_is_distinguished_from_bad_quote(self):
        self.sync(); fid = next(iter(self.provider.files))
        self.set_claim({'status':'answered','claims':[{'text':'Resposta','file_id':fid,
            'quote':'A piscina funciona das 8h as 22h.','section':'Seção não recuperada'}]})
        result = self.service.answer(self.question())
        self.assertEqual(result.code,'knowledge_evidence_invalid')
        self.assertEqual(result.data['validation_error'],'section_not_found')

    def test_blank_or_formatting_only_citation_cannot_bypass_evidence_validation(self):
        self.sync(); fid = next(iter(self.provider.files))
        for quote in (' '*12,'************','...........'):
            self.set_claim({'status':'answered','claims':[{'text':'Afirmação sem apoio','file_id':fid,'quote':quote,'section':None}]})
            self.assertEqual(self.service.answer(self.question()).code,'knowledge_evidence_invalid')

    def test_old_generation_attributes_are_rejected(self):
        self.sync(); response = self.response()
        response['output'][0]['results'][0]['attributes']['generation'] = 'old'
        self.provider.custom = response
        self.assertEqual(self.service.answer(self.question()).code,'knowledge_evidence_invalid')

    def test_source_changed_blocks_before_openai_even_for_cached_reply(self):
        self.sync(); msg = self.question(); self.service.answer(msg)
        self.drive.value = replace(self.drive.value,sha256='a'*64)
        with self.assertRaisesRegex(EngineError,'knowledge_source_changed'):
            self.service.answer(msg)
        self.assertEqual(self.provider.answer_calls,1)
        self.assertEqual(self.store.execute('SELECT status FROM document_sync_metadata').fetchone()[0],'outdated')

    def test_no_upload_when_authorized_hash_does_not_match(self):
        self.drive.value = replace(self.drive.value,sha256='a'*64)
        with self.assertRaisesRegex(EngineError,'knowledge_source_changed'):
            self.sync()
        self.assertEqual(self.provider.calls,[])

    def test_invalid_encoding_and_binary_format_require_explicit_future_handling(self):
        for value in (replace(self.drive.value,content=b'\xff'),replace(self.drive.value,mime_type='application/pdf')):
            self.drive.value = value
            with self.assertRaisesRegex(EngineError,'knowledge_document_not_readable'):
                self.sync()
        self.assertEqual(self.provider.calls,[])

    def test_index_not_completed_is_never_published_synced(self):
        self.provider.index_status = 'in_progress'
        with self.assertRaisesRegex(EngineError,'knowledge_index_not_ready'):
            self.sync()
        self.assertEqual(self.count('document_sync_metadata'),0)
        self.assertEqual(self.store.execute('SELECT status FROM knowledge_versions').fetchone()[0],'pending')

    def test_uncertain_answer_is_not_resubmitted_after_restart(self):
        self.sync(); message = self.question()
        self.provider.custom = EngineError('openai_result_uncertain')
        with self.assertRaises(EngineError):
            self.service.answer(message)
        restarted = Knowledge(self.config,self.store,self.drive,self.provider,clock=self.clock)
        restarted.startup()
        with self.assertRaisesRegex(EngineError,'openai_usage_uncertain'):
            restarted.answer(message)
        with self.assertRaisesRegex(EngineError,'openai_usage_uncertain'):
            restarted.answer(self.question())
        self.assertEqual(self.provider.answer_calls,1)

    def test_completed_answer_survives_missing_channel_receipt_without_second_charge(self):
        self.sync(); message = self.question()
        first = self.service.answer(message)
        second = self.service.answer(message)
        self.assertEqual(first,second)
        self.assertEqual(self.provider.answer_calls,1)

    def test_reused_message_id_with_changed_question_is_not_cached(self):
        self.sync(); message = self.question(); self.service.answer(message)
        with self.assertRaisesRegex(EngineError,'message_identity_conflict'):
            self.service.answer(replace(message,text='Outra pergunta'))

    def test_missing_usage_blocks_new_spending(self):
        self.sync(); response = self.response(); del response['usage']
        self.provider.custom = response
        with self.assertRaisesRegex(EngineError,'openai_usage_missing'):
            self.service.answer(self.question())
        self.assertFalse(self.service.budget.assess()['allowed'])

    def test_explicit_usage_reconciliation_records_cost_without_reissuing_question(self):
        self.sync(); message = self.question()
        self.provider.custom = EngineError('openai_result_uncertain')
        with self.assertRaises(EngineError):
            self.service.answer(message)
        cid = digest([message.scope.key(),message.message_id])
        self.service.reconcile(cid,inputs=100,outputs=50,searches=1)
        self.assertTrue(self.service.budget.assess()['allowed'])
        self.assertEqual(self.service.answer(message).code,'knowledge_reconciled_without_answer')
        self.assertEqual(self.provider.answer_calls,1)

    def test_measurement_is_required_for_reconciliation(self):
        self.sync(); message = self.question(); self.provider.custom = EngineError('openai_result_uncertain')
        with self.assertRaises(EngineError): self.service.answer(message)
        with self.assertRaisesRegex(EngineError,'openai_usage_missing'):
            self.service.reconcile(digest([message.scope.key(),message.message_id]))

    def test_budget_blocks_before_paid_request(self):
        self.sync()
        with self.store.transaction():
            self.service.budget._record('spent',self.clock(),storage_usd=__import__('decimal').Decimal('6'))
        with self.assertRaisesRegex(EngineError,'budget_blocked'):
            self.service.answer(self.question())
        self.assertEqual(self.provider.answer_calls,0)

    def test_storage_accrues_while_stopped_and_splits_months(self):
        self.clock.now = self.clock().replace(day=30,hour=12)
        self.service.budget.storage('vs_fictional',1000000)
        self.clock.advance(days=3)
        self.service.budget.storage('vs_fictional',1000000)
        periods = {r[0] for r in self.store.execute('SELECT period FROM usage_ledger')}
        self.assertEqual(periods,{'2026-11','2026-12'})
        self.assertFalse(any(json.loads(r[0])['storage_free_quota_assumed'] for r in self.store.execute('SELECT assumption FROM usage_ledger')))

    def test_oversized_storage_and_unverified_pilot_fail_closed(self):
        self.provider.index_usage = 2000000
        with self.assertRaisesRegex(EngineError,'knowledge_storage_limit'):
            self.sync()

    def test_unknown_identity_cannot_trigger_drive_or_openai(self):
        with self.assertRaisesRegex(EngineError,'unauthorized'):
            self.service.answer(self.question(Scope(self.config.environment_id,'local',9999,9999)))
        self.assertEqual(self.drive.calls,0)
        self.assertEqual(self.provider.calls,[])

    def test_revoked_permission_blocks_cached_reply(self):
        self.sync(); msg = self.question(); self.service.answer(msg)
        self.raw['permissions']['resident'].remove('knowledge.read'); self.save_config()
        denied = Knowledge(self.config,self.store,self.drive,self.provider,clock=self.clock)
        with self.assertRaisesRegex(EngineError,'unauthorized'):
            denied.answer(msg)

    def test_overlong_query_has_no_external_calls(self):
        result = self.service.answer(self.question(text='x'*1001))
        self.assertEqual(result.code,'knowledge_input_limit')
        self.assertEqual(self.drive.calls,0)

    def test_schema_tampering_is_rejected_on_reopen(self):
        self.store.execute('CREATE TABLE unexpected_i4(value)'); self.store.close()
        before = self.database.read_bytes()
        with self.assertRaisesRegex(EngineError,'schema_mismatch'):
            Store(self.database,knowledge=True)
        self.assertEqual(before,self.database.read_bytes())

    def test_core_knowledge_action_is_audited_and_keeps_admin_writes_empty(self):
        self.sync()
        result = self.engine.handle(self.question(),'query_documents',{})
        self.assertEqual(result.code,'knowledge_answer')
        self.assertEqual(self.count('operational_guidance'),0)
        self.assertEqual(self.count('requests_state'),0)
        self.assertEqual(self.store.execute("SELECT count(*) FROM operation_log WHERE operation='query_documents'").fetchone()[0],1)

    def test_telegram_dedup_uses_existing_delivery_and_no_second_model_call(self):
        self.raw['channels'] = {'telegram':{'bot_id':9009,'poll_seconds':25,'request_seconds':35,'batch_size':100,'retry_seconds':5}}
        for user in self.raw['users']:
            user['channel'] = 'telegram'; user['chat_ids'] = [user['channel_user_id']]
        self.save_config()
        self.service = Knowledge(self.config,self.store,self.drive,self.provider,clock=self.clock,sleep=lambda _:None)
        self.sync()
        engine = Orchestrator(self.config,self.store,self.clock,knowledge=self.service)
        sink = FakeTelegram()
        channel = TelegramChannel(self.config,self.store,engine,sink,clock=self.clock)
        incoming = update(10,'Posso dar um mergulho às onze?',self.clock,1001)
        channel.process(incoming); channel.deliver(); channel.process(incoming); channel.deliver()
        self.assertEqual(self.provider.answer_calls,1)
        self.assertEqual(len(sink.sent),1)
        self.assertEqual(channel.offset(),11)

    def test_g3_and_telegram_consent_are_independent(self):
        self.raw['knowledge']['authorization']['telegram'] = False
        self.save_config()
        self.assertRaisesRegex(EngineError,'knowledge_telegram_authorization_required',
                               self.config.knowledge.require_consent,telegram=True)
        self.config.knowledge.require_consent()

    def test_invalid_limits_and_unknown_configuration_are_rejected(self):
        for mutate in (lambda r:r['knowledge']['limits'].update(max_input_tokens=1024),
                       lambda r:r['knowledge'].update(extra=True),
                       lambda r:r['knowledge']['documents'][0].update(sha256='bad')):
            raw = deepcopy(self.raw); mutate(raw)
            with self.assertRaises(EngineError): _parse_config(raw)

    def test_valid_openai_key_coexists_with_telegram_and_google_validator(self):
        path = self.folder/'secrets.yaml'
        raw = {'telegram_bot_token':'9009:'+'X'*30,'openai_api_key':'sk-'+'A'*32,'google_oauth':None}
        path.write_text(__import__('yaml').safe_dump(raw),encoding='utf-8')
        self.assertEqual(load_telegram_token(path,9009),raw['telegram_bot_token'])
        validate_secret_document(raw)
        self.assertEqual(load_enrollment_secrets(path)['openai_api_key'],raw['openai_api_key'])

    def test_hidden_enrollment_preserves_other_secret_fields_and_does_not_overwrite(self):
        path = self.folder/'secrets.yaml'
        raw = {'telegram_bot_token':'9009:'+'X'*30,'openai_api_key':None,'google_oauth':None}
        path.write_text(__import__('yaml').safe_dump(raw),encoding='utf-8')
        with patch('scripts.setup_openai_i4.private_acl'),patch('app.integrations.private_files.private_acl'):
            self.assertEqual(enroll_key(self.folder,prompt=lambda _:'sk-'+'A'*32),'registered')
            self.assertEqual(enroll_key(self.folder,prompt=lambda _:self.fail('Should not prompt again')),'already_registered')
        saved = load_enrollment_secrets(path)
        self.assertEqual(saved['telegram_bot_token'],raw['telegram_bot_token'])
        self.assertIsNone(saved['google_oauth'])

    def test_secret_format_errors_do_not_echo_key(self):
        for key in ('FAKE_SECRET','sk- bad','sk-'+'X'*32+'\n',True):
            with self.assertRaises(EngineError) as error: validate_api_key(key)
            self.assertNotIn('FAKE_SECRET',str(error.exception))

    def test_http_adapter_fixed_host_no_retries_and_model_store_limits(self):
        response = MagicMock(status_code=200)
        response.iter_content.return_value = [b'{"ok":true}']
        session = MagicMock(); session.request.return_value = response
        client = OpenAIHTTP(self.config.knowledge,'sk-'+'X'*32,allow_live=True,session=session)
        client.answer('Pergunta fictícia','vs_fictional','generation',('file-fictional',))
        args,kwargs = session.request.call_args
        self.assertEqual(args,('POST','https://api.openai.com/v1/responses'))
        self.assertFalse(kwargs['allow_redirects'])
        self.assertFalse(kwargs['json']['store'])
        self.assertEqual(kwargs['json']['max_tool_calls'],1)
        self.assertEqual(kwargs['json']['tools'][0]['filters']['value'],'generation')
        self.assertEqual(kwargs['headers']['OpenAI-Project'],'proj_fictional')
        self.assertNotIn('url',kwargs['json'])
        self.assertNotIn('previous_response_id',kwargs['json'])

    def test_answer_schema_binds_only_current_manifest_without_cross_request_leak(self):
        response = MagicMock(status_code=200); response.iter_content.return_value = [b'{"ok":true}']
        session = MagicMock(); session.request.return_value = response
        client = OpenAIHTTP(self.config.knowledge,'sk-'+'X'*32,allow_live=True,session=session)
        client.answer('Pergunta','vs_fictional','generation',('file-currentA','file-currentB'))
        first = session.request.call_args.kwargs['json']['text']['format']['schema']
        fields = first['properties']['claims']['items']['properties']
        self.assertEqual(fields['file_id']['enum'],['file-currentA','file-currentB'])
        self.assertEqual(fields['quote']['maxLength'],1000)
        client.answer('Pergunta','vs_fictional','generation',('file-other',))
        second = session.request.call_args.kwargs['json']['text']['format']['schema']
        self.assertEqual(second['properties']['claims']['items']['properties']['file_id']['enum'],['file-other'])
        self.assertEqual(fields['file_id']['enum'],['file-currentA','file-currentB'])
        with self.assertRaisesRegex(EngineError,'knowledge_response_scope_invalid'):
            client.answer('Pergunta','vs_fictional','generation',())
        self.assertEqual(session.request.call_count,2)

    def test_model_receives_only_file_ids_of_the_verified_manifest(self):
        self.sync(); self.service.answer(self.question())
        self.assertEqual(set(self.provider.answer_files),set(self.provider.files))

    def test_invented_claim_file_is_still_rejected_after_schema_constraint(self):
        self.sync()
        self.set_claim({'status':'answered','claims':[{'text':'Texto','file_id':'file-invented',
            'quote':'A piscina funciona das 8h as 22h.','section':None}]})
        result = self.service.answer(self.question())
        self.assertEqual(result.code,'knowledge_evidence_invalid')
        self.assertEqual(result.data['validation_error'],'claim_fields_invalid')

    def test_http_errors_are_redacted_and_not_automatically_retried(self):
        session = MagicMock(); session.request.side_effect = RuntimeError('FAKE_SECRET')
        client = OpenAIHTTP(self.config.knowledge,'sk-'+'X'*32,allow_live=True,session=session)
        with self.assertRaisesRegex(EngineError,'openai_result_uncertain') as error:
            client.create_store('pilot')
        self.assertEqual(session.request.call_count,1)
        self.assertNotIn('FAKE_SECRET',str(error.exception))

    def test_live_gate_precedes_transport(self):
        with self.assertRaisesRegex(EngineError,'live_openai_authorization_required'):
            OpenAIHTTP(self.config.knowledge,'sk-'+'X'*32)

    def test_no_document_bytes_persisted_in_sqlite_metadata(self):
        self.sync()
        rows = [tuple(row) for row in self.store.execute('SELECT * FROM knowledge_versions')]
        self.assertNotIn(CONTENT.decode(),canonical(rows))
        self.assertNotIn(CONTENT.decode(),canonical([tuple(r) for r in self.store.execute('SELECT * FROM document_sync_metadata')]))

    def test_operational_context_keeps_origin_audience_and_expiry_separate(self):
        self.create(topic='fachada',content='Informação pública fictícia')
        self.create(topic='fachada',content='Informação restrita fictícia',audience='managers')
        message = self.question()
        self.assertEqual(self.service.operational_context(message,'fachada')['status'],'blocked')
        context = self.service.operational_context(message,'fachada',document_status='compatible')
        self.assertEqual(context['source'],'administration')
        self.assertEqual(len(context['guidance']),1)
        self.assertNotIn('restrita',canonical(context))
        self.clock.advance(days=1)
        self.assertEqual(self.service.operational_context(message,'fachada',document_status='compatible')['guidance'],[])
        self.assertEqual(self.provider.answer_calls,0)

    def test_operational_conflict_does_not_supply_unchecked_guidance(self):
        self.create(topic='fachada')
        result = self.service.operational_context(self.question(),'fachada',document_status='conflicting')
        self.assertEqual(result['guidance'],[])
        self.assertEqual(self.provider.calls,[])

    def test_retention_marks_completed_answers_and_preserves_resource_records(self):
        self.sync(); self.service.answer(self.question())
        self.clock.advance(days=31)
        self.assertEqual(len(self.store.retention_candidates(self.config,self.clock())['knowledge_calls']),1)
        self.assertEqual(self.count('knowledge_calls'),4)

    def test_http_denies_delete_arbitrary_url_and_redirect(self):
        session = MagicMock()
        client = OpenAIHTTP(self.config.knowledge,'sk-'+'X'*32,allow_live=True,session=session)
        for method,path in (('DELETE','/files/file-fictional'),('POST','https://example.invalid'),('POST','/responses/../../files')):
            with self.assertRaisesRegex(EngineError,'openai_operation_denied'):
                client._request(method,path)
        self.assertEqual(session.request.call_count,0)
        session.request.return_value = MagicMock(status_code=302)
        with self.assertRaisesRegex(EngineError,'openai_redirect_denied'):
            client.create_store('pilot')
        self.assertEqual(session.request.call_count,1)

    def test_source_change_during_response_records_usage_and_suppresses_answer(self):
        self.sync()
        original = self.provider.answer
        def change(*args):
            value = original(*args)
            self.drive.value = replace(self.drive.value,sha256='b'*64)
            return value
        with patch.object(self.provider,'answer',side_effect=change):
            result = self.service.answer(self.question())
        self.assertEqual(result.code,'knowledge_source_revalidation_failed')
        self.assertEqual(self.store.execute('SELECT count(*) FROM usage_ledger WHERE input_tokens=120').fetchone()[0],1)

    def test_incomplete_response_is_not_an_answer(self):
        self.sync(); response = self.response(); response['status'] = 'incomplete'; self.provider.custom = response
        self.assertEqual(self.service.answer(self.question()).code,'knowledge_incomplete_response')

    def test_extra_tool_attempt_fails_closed_without_a_second_provider_request(self):
        self.sync(); response = self.response()
        response['output'].insert(1,{'type':'file_search_call','status':'incomplete','results':[]})
        self.provider.custom = response
        self.assertEqual(self.service.answer(self.question()).code,'knowledge_incomplete_response')
        self.assertEqual(self.provider.answer_calls,1)

    def test_crash_after_running_intent_blocks_next_call(self):
        cid = 'a'*64
        self.assertIsNone(self.service.budget.begin(cid,'answer','scope','request'))
        self.service.startup()
        row = self.store.execute('SELECT state,reserved_brl FROM knowledge_calls WHERE call_id=?',(cid,)).fetchone()
        self.assertEqual(row['state'],'uncertain')
        self.assertGreater(__import__('decimal').Decimal(row['reserved_brl']),0)
        with self.assertRaisesRegex(EngineError,'openai_usage_uncertain'):
            self.service.budget.begin('b'*64,'answer','scope','request')

    def test_upload_timeout_reconciles_resource_without_repeating_upload(self):
        original = self.provider.upload
        def accepted_then_timeout(*args):
            original(*args)
            raise EngineError('openai_result_uncertain')
        with patch.object(self.provider,'upload',side_effect=accepted_then_timeout):
            with self.assertRaises(EngineError): self.sync()
        cid = self.store.execute("SELECT call_id FROM knowledge_calls WHERE kind='upload'").fetchone()[0]
        fid = next(iter(self.provider.files))
        self.service.reconcile(cid,remote=fid)
        self.sync()
        self.assertEqual(self.provider.calls.count('upload'),1)
        self.assertEqual(self.store.execute('SELECT status FROM document_sync_metadata').fetchone()[0],'synced')

    def test_reconciliation_rejects_unrelated_resource(self):
        self.service.budget.begin('a'*64,'upload',self.service.pilot,'request')
        self.service.budget.uncertain('a'*64)
        self.provider.files['file-unrelated'] = {'id':'file-unrelated','filename':'different.md'}
        with self.assertRaisesRegex(EngineError,'knowledge_reconciliation_mismatch'):
            self.service.reconcile('a'*64,remote='file-unrelated')
        self.assertFalse(self.service.budget.assess()['allowed'])

    def test_disabled_i4_live_flag_cannot_read_secrets_or_create_database(self):
        from app.main import main
        self.raw['channels'] = {'telegram':{'bot_id':9009,'poll_seconds':25,'request_seconds':35,'batch_size':100,'retry_seconds':5}}
        for user in self.raw['users']:
            user['channel'] = 'telegram'; user['chat_ids'] = [user['channel_user_id']]
        self.raw['knowledge']['enabled'] = False; self.save_config()
        path = self.folder/'not-created.sqlite3'
        with patch('app.ai.configuration.load_api_key',side_effect=AssertionError('Secret read')):
            self.assertEqual(main(['--config',str(self.config_path),'--database',str(path),'--telegram',
                                   '--allow-live-telegram','--knowledge','--allow-live-openai']),1)
        self.assertFalse(path.exists())

    def test_private_backup_precedes_migration_and_preserves_context(self):
        from app.storage.backup import before_knowledge_migration
        path = self.folder/'legacy.sqlite3'
        legacy = Store(path)
        legacy.execute("INSERT INTO conversation_state VALUES ('env','local',1,1,'context','{}','2026-01-01','2027-01-01')")
        legacy.close()
        with patch('app.storage.backup.private_acl'):
            target = before_knowledge_migration(path,self.config_path)
        copy = sqlite3.connect(target)
        self.assertEqual(copy.execute('PRAGMA user_version').fetchone()[0],2)
        self.assertEqual(copy.execute('SELECT count(*) FROM conversation_state').fetchone()[0],1)
        copy.close()
        upgraded = Store(path,knowledge=True)
        self.assertEqual(upgraded.execute('SELECT count(*) FROM conversation_state').fetchone()[0],1)
        upgraded.close()

    def test_failed_i4_migration_rolls_back_to_verified_schema_two(self):
        path = self.folder/'legacy.sqlite3'; legacy = Store(path); legacy.close()
        migration = MagicMock(); migration.read_text.return_value = 'CREATE TABLE temporary_i4(value); INVALID SQL;'
        with patch('app.storage.sqlite.KNOWLEDGE_MIGRATION',migration):
            with self.assertRaises(sqlite3.Error): Store(path,knowledge=True)
        preserved = Store(path)
        self.assertEqual(preserved.execute('PRAGMA user_version').fetchone()[0],2)
        preserved.verify(); preserved.close()

    def test_owner_verified_absent_resource_can_be_retried_by_next_manual_sync(self):
        with patch.object(self.provider,'create_store',side_effect=EngineError('openai_access_denied')):
            with self.assertRaises(EngineError): self.sync()
        cid = self.store.execute("SELECT call_id FROM knowledge_calls WHERE kind='store'").fetchone()[0]
        self.service.reconcile(cid,verified_not_created=True)
        self.assertEqual(self.sync()['status'],'synced')
        self.assertEqual(self.store.execute("SELECT count(*) FROM operation_log WHERE operation='knowledge.reconcile'").fetchone()[0],1)

    def test_owner_cannot_release_uncertain_answer_as_absent_resource(self):
        self.sync(); message = self.question(); self.provider.custom = EngineError('openai_result_uncertain')
        with self.assertRaises(EngineError): self.service.answer(message)
        with self.assertRaisesRegex(EngineError,'knowledge_call_state_invalid'):
            self.service.reconcile(digest([message.scope.key(),message.message_id]),verified_not_created=True)

    def test_google_refresh_preserves_registered_openai_and_telegram(self):
        from tests.test_google import secrets as google_secrets, declaration
        from app.integrations.google_config import parse_google
        from app.integrations.google_auth import GoogleAuth
        from datetime import datetime
        import yaml
        path = self.folder/'coexist-secrets.yaml'
        original = google_secrets(); original['openai_api_key'] = 'sk-'+'A'*32
        path.write_text(yaml.safe_dump(original),encoding='utf-8')
        def refreshed(credentials,request):
            credentials.token = 'FAKE_UPDATED'; credentials.expiry = datetime(2099,2,1)
        with patch('app.integrations.private_files.private_acl'), \
             patch('app.integrations.google_auth.private_acl'), \
             patch('google.oauth2.credentials.Credentials.refresh',new=refreshed):
            self.assertEqual(GoogleAuth(parse_google(declaration()),path,allow_live=True).bearer(force_refresh=True),'FAKE_UPDATED')
        persisted = load_enrollment_secrets(path)
        self.assertEqual(persisted['openai_api_key'],original['openai_api_key'])
        self.assertEqual(persisted['telegram_bot_token'],original['telegram_bot_token'])

    def test_pending_telegram_answer_is_neutralized_if_source_changes_before_send(self):
        from app.channels.telegram import NEUTRAL
        self.raw['channels'] = {'telegram':{'bot_id':9009,'poll_seconds':25,'request_seconds':35,'batch_size':100,'retry_seconds':5}}
        for user in self.raw['users']:
            user['channel'] = 'telegram'; user['chat_ids'] = [user['channel_user_id']]
        self.save_config()
        service = Knowledge(self.config,self.store,self.drive,self.provider,clock=self.clock,sleep=lambda _:None)
        service.sync()
        sink = FakeTelegram()
        engine = Orchestrator(self.config,self.store,self.clock,knowledge=service)
        channel = TelegramChannel(self.config,self.store,engine,sink,clock=self.clock)
        channel.process(update(10,'Pergunta documental fictícia?',self.clock,1001))
        self.drive.value = replace(self.drive.value,sha256='c'*64)
        channel.deliver()
        self.assertEqual(sink.sent[0]['text'],NEUTRAL)
        self.assertEqual(self.provider.answer_calls,1)
        self.assertEqual(self.store.execute('SELECT code FROM telegram_updates').fetchone()[0],'knowledge_delivery_invalidated')

    def test_pending_answer_is_not_exposed_after_restart_without_i4(self):
        from app.channels.telegram import NEUTRAL
        self.raw['channels'] = {'telegram':{'bot_id':9009,'poll_seconds':25,'request_seconds':35,'batch_size':100,'retry_seconds':5}}
        for user in self.raw['users']:
            user['channel'] = 'telegram'; user['chat_ids'] = [user['channel_user_id']]
        self.save_config()
        service = Knowledge(self.config,self.store,self.drive,self.provider,clock=self.clock,sleep=lambda _:None)
        service.sync()
        sink = FakeTelegram()
        active = TelegramChannel(self.config,self.store,Orchestrator(self.config,self.store,self.clock,knowledge=service),sink,clock=self.clock)
        active.process(update(10,'Pergunta documental fictícia?',self.clock,1001))
        legacy = TelegramChannel(self.config,self.store,Orchestrator(self.config,self.store,self.clock),sink,clock=self.clock)
        legacy.deliver()
        self.assertEqual(sink.sent[0]['text'],NEUTRAL)
        self.assertEqual(self.provider.answer_calls,1)
