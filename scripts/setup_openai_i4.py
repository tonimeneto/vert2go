"""Owner enrollment with hidden key input and private atomic persistence. No network."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import getpass
import hashlib
import json
from pathlib import Path
import sys
import warnings

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.ai.configuration import validate_api_key
from app.config.schema import _parse_config, load_enrollment_secrets, read_configuration_bytes, read_yaml
from app.core.contracts import EngineError
from app.integrations.private_files import private_acl, private_lock, atomic_yaml


def pilot_documents(root, raw):
    """Resolve the two G3-authorized documents by I3 resource reference and byte hash, never by name."""
    consent = json.loads((root/'docs/evidencias/i4-authorizations.json').read_text(encoding='utf-8'))
    if consent.get('accepted_i3') is not True or consent.get('g3') != 'authorized':
        raise EngineError('knowledge_g3_required')
    proof = json.loads((root/'docs/evidencias/i3-google-check-20261109T232128245703Z.json').read_text(encoding='utf-8'))
    by_ref = {d['resource_ref']:d for d in proof['documents'] if d['result'] == 'passed'}
    local = {}
    for path,title in (('docs/4S_Regulamento_interno.md','Regulamento Interno'),
                       ('docs/4S_convencao_condominio.md','Convenção do Condomínio')):
        value = hashlib.sha256((root/path).read_bytes()).hexdigest()
        if value not in consent['authorized_local_sha256']:
            raise EngineError('knowledge_document_not_authorized')
        local[value] = title
    documents = []
    for doc in raw['google']['drive_documents']:
        reference = hashlib.sha256(doc['id'].encode()).hexdigest()[:24]
        entry = by_ref.get(reference,{})
        if entry.get('sha256') in local:
            documents.append({'id':doc['id'],'title':local[entry['sha256']],'sha256':entry['sha256']})
    if len(documents) != 2:
        raise EngineError('knowledge_document_mapping_invalid')
    return documents,consent


def configure(root=ROOT, *, project_id=None, model='gpt-4.1-mini-2025-04-14'):
    path = root/'config.yaml'
    before, raw = read_configuration_bytes(path), deepcopy(read_yaml(path))
    _parse_config(raw)
    documents,consent = pilot_documents(root,raw)
    if raw.get('knowledge') is not None:
        raise EngineError('knowledge_already_configured')
    project_id = project_id or input('ID nao secreto do projeto OpenAI (proj_...): ').strip()
    raw['knowledge'] = {
        'enabled':True, 'project_id':project_id,'model':model,'vector_store_id':None,
        'authorization':{'accepted_i3':True,'authorized_at':consent['authorized_at'],
                         'telegram':consent.get('telegram_document_tests') == 'authorized'},
        'documents':documents,
        'limits':{'timeout_seconds':45,'max_question_chars':2000,'max_output_tokens':1200,
                  'max_results':6,'max_response_bytes':1048576,'max_poll_attempts':12,'poll_seconds':2,
                  'max_storage_bytes':104857600,'max_input_tokens':32768},
        'prices':{'search_usd_per_call':'0.0025','storage_usd_per_gb_day':'0.10',
                  'reference_date':'2026-11-10','reference_url':'https://developers.openai.com/api/docs/pricing'}}
    for permissions in raw['permissions'].values():
        if 'knowledge.read' not in permissions:
            permissions.append('knowledge.read')
    raw['openai'].update(input_usd_per_million='0.40',output_usd_per_million='1.60',
                         reference_date='2026-11-10',
                         reference_label='OpenAI official standard pricing; BRL FX is a configurable estimate')
    if str(raw['openai']['monthly_budget_brl']) not in ('30','30.0','30.00') or str(raw['openai']['alert_brl']) not in ('24','24.0','24.00'):
        raise EngineError('knowledge_budget_confirmation_required')
    _parse_config(raw)
    with private_lock(path):
        atomic_yaml(path,before,raw,_parse_config)


def enroll_key(root=ROOT, *, prompt=getpass.getpass):
    path = root/'secrets.yaml'
    private_acl(path)
    before, raw = read_configuration_bytes(path), deepcopy(load_enrollment_secrets(path))
    if raw['openai_api_key'] is not None:
        return 'already_registered'
    if not sys.stdin.isatty() and prompt is getpass.getpass:
        raise EngineError('openai_hidden_terminal_required')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error',getpass.GetPassWarning)
            value = prompt('Cole a chave OpenAI (entrada oculta; nada sera exibido): ')
    except (getpass.GetPassWarning, EOFError, KeyboardInterrupt):
        raise EngineError('openai_hidden_input_unavailable') from None
    # New prompt input may drop outer whitespace. Stored keys are never rewritten.
    value = value.strip() if type(value) is str else value
    validate_api_key(value)
    if value is None:
        raise EngineError('openai_key_missing')
    raw['openai_api_key'] = value
    def validate(new):
        from app.integrations.google_config import validate_oauth
        validate_api_key(new['openai_api_key'])
        validate_oauth(new['google_oauth'])
        if set(new) != set(raw) or new['telegram_bot_token'] != raw['telegram_bot_token']:
            raise EngineError('openai_enrollment_invalid')
    with private_lock(path):
        atomic_yaml(path,before,raw,validate)
    return 'registered'


def main(argv=None):
    parser = argparse.ArgumentParser(description='Cadastro privado OpenAI I4, sem rede')
    parser.add_argument('--enroll',action='store_true',help='Configurar projeto e cadastrar chave oculta')
    parser.add_argument('--key-only',action='store_true')
    parser.add_argument('--project-id')
    args = parser.parse_args(argv)
    try:
        if args.enroll == args.key_only:
            raise EngineError('openai_enrollment_mode_required')
        if args.enroll:
            if read_yaml(ROOT/'config.yaml').get('knowledge') is None:
                configure(project_id=args.project_id)
        result = enroll_key()
        # Separate enrollment evidence does not overwrite the owner's authorization record.
        proof = {'phase':'I4','scope':'local_private_enrollment','key':result,
                 'updated_at':datetime.now(timezone.utc).isoformat(),'external_api_attempted':False,
                 'project_registered':read_yaml(ROOT/'config.yaml').get('knowledge') is not None}
        target = ROOT/'docs/evidencias'/('i4-enrollment-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json')
        target.write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({'phase':'I4','key':result,'external_api_attempted':False}))
        return 0
    except EngineError as error:
        print(json.dumps({'phase':'I4','reason':error.code,'external_api_attempted':False}))
        return 1
    except Exception:
        print(json.dumps({'phase':'I4','reason':'openai_enrollment_failed','external_api_attempted':False}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
