"""I5 enrollment using existing resources/client. No Git, deletion or secret output."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.config.schema import _parse_config, load_config, load_enrollment_secrets, read_yaml, read_configuration_bytes
from app.core.contracts import EngineError, canonical, stamp
from app.integrations.private_files import private_acl, private_lock, atomic_yaml, no_links
from app.main import instance_lock

CAPABILITIES = {
    'resident':('reservation.create','reservation.read','request.create','request.read'),
    'manager':('request.read','request.respond','report.read','operations.reconcile'),
}


def private_snapshot(source, folder, *, reference=None):
    source,folder = no_links(source),no_links(folder)
    folder.mkdir(parents=True,exist_ok=True)
    private_acl(reference or source)
    target = folder/(source.stem+'-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+source.suffix)
    fd = os.open(target,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,'wb') as handle:
        private_acl(reference or source,target)
        handle.write(read_configuration_bytes(source)); handle.flush(); os.fsync(handle.fileno())
    return target


def scenario(now, end):
    return {'id':'salao','rule_id':'i5-live-fixture-20261112','status':'simulated',
        'source_document_id':'i5-live-test-fixture','source_title':'Cenário fictício I5; não é regra condominial',
        'section':'Ensaio experimental autorizado','source_revision':'2026-11-12',
        'verified_at':stamp(now),'valid_until':end,'opens':'08:00','closes':'22:00',
        'max_duration_minutes':240,'min_notice_hours':0,'max_advance_days':5,'fee_brl':'0.00'}


def candidate(raw, units, now):
    config = _parse_config(raw)
    if config.operations is not None:
        raise EngineError('operations_already_configured')
    g = config.google
    if g is None or not g.calendar_id or not g.spreadsheet_id or len(g.ranges) != 1:
        raise EngineError('i5_existing_resources_incomplete')
    out = deepcopy(raw)
    rule = scenario(now,g.window_end)
    rule['source_hash'] = hashlib.sha256(canonical(rule).encode()).hexdigest()
    out['operations'] = {'authorization':{'calendar_id':g.calendar_id,'spreadsheet_id':g.spreadsheet_id,
        'sheet_range':g.ranges[0],'exclusive_pilot_resources':True,'calendar_insert':True,'sheets_update':True},
        'units':units,'resources':[rule], 'request_categories':{'excecao':'manager','informacao':'unassigned'},
        'report_limit':20,'alternative_offsets_days':[1,2,3],'reservation_exception_category':'excecao'}
    for role, capabilities in CAPABILITIES.items():
        out['permissions'][role] += [v for v in capabilities if v not in out['permissions'][role]]
    _parse_config(out)
    for key in raw:
        if key != 'permissions' and out[key] != raw[key]:
            raise EngineError('i5_existing_configuration_changed')
    return out


def prepare(root=ROOT):
    config_path, database = root/'config.yaml',root/'data/i2.sqlite3'
    raw = read_yaml(config_path); config = _parse_config(raw)
    units = {}
    connection = sqlite3.connect(database.resolve().as_uri()+'?mode=ro',uri=True)
    try:
        for user in config.users:
            if user.role != 'resident' or not user.enabled:
                continue
            row = connection.execute("SELECT payload FROM conversation_state WHERE environment_id=? AND channel=? AND channel_user_id=? AND chat_id=? AND state_key='context'",
                (config.environment_id,user.channel,user.channel_user_id,user.chat_ids[0])).fetchone()
            value = json.loads(row[0]) if row else {}
            if not value.get('unit_reference'):
                raise EngineError('i5_existing_simulated_unit_missing')
            units[str(user.channel_user_id)] = value['unit_reference']
    finally:
        connection.close()
    draft = candidate(raw,units,datetime.now(timezone.utc))
    target = no_links(root/'data/i5-candidate-config.yaml')
    if target.exists():
        raise EngineError('i5_candidate_already_exists')
    import yaml
    fd = os.open(target,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,'wb') as handle:
        private_acl(config_path,target)
        handle.write(yaml.safe_dump(draft,allow_unicode=True,sort_keys=False).encode())
        handle.flush(); os.fsync(handle.fileno())
    report = {'phase':'I5','source':'explicit_owner_continuity_request_2026-11-12','updated_at':stamp(datetime.now(timezone.utc)),
        'candidate_prepared':True,'active_config_changed':False,'existing_destinations_reused':True,
        'simulation_conditions':draft['operations']['resources'],'calendar_write_authorized':True,
        'sheets_write_authorized':True,'deletions_authorized':False,'i6_started':False,
        'baseline_config_sha256':hashlib.sha256(read_configuration_bytes(config_path)).hexdigest()}
    (root/'docs/evidencias/i5-live-authorizations.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'candidate_prepared':True,'active_config_changed':False,'existing_simulated_unit_reused':True}))


def authorize(root=ROOT, *, consent_timeout_seconds=600):
    from app.integrations.google_auth import GoogleAuth
    config_path,secret_path = root/'config.yaml',root/'secrets.yaml'
    draft = read_yaml(root/'data/i5-candidate-config.yaml'); config = _parse_config(draft)
    config.operations.require_live()
    baseline = read_configuration_bytes(config_path)
    authorization_path = root/'docs/evidencias/i5-live-authorizations.json'
    report = json.loads(authorization_path.read_text(encoding='utf-8'))
    if hashlib.sha256(baseline).hexdigest() != report['baseline_config_sha256']:
        raise EngineError('configuration_changed_during_enrollment')
    client = root/'client_secret_i3_desktop.json'
    if not client.is_file():
        raise EngineError('google_existing_desktop_client_missing')
    with instance_lock(root/'data/i2.sqlite3'):
        private_snapshot(config_path,root/'data/backups/i5-enrollment')
        private_snapshot(secret_path,root/'data/backups/i5-enrollment')
        previous = load_enrollment_secrets(secret_path)
        print('OAUTH_BROWSER_CONSENT_REQUIRED',flush=True)
        GoogleAuth(config.google,secret_path,allow_live=True).enroll(client,consent_timeout_seconds=consent_timeout_seconds)
        current = load_enrollment_secrets(secret_path)
        if any(current[k] != previous[k] for k in ('telegram_bot_token','openai_api_key')):
            raise EngineError('i5_existing_secrets_changed')
        with private_lock(config_path):
            atomic_yaml(config_path,baseline,draft,_parse_config)
        report.update(oauth_write_consent='passed',active_config_changed=True,previous_configuration_backed_up=True,
                      existing_telegram_and_openai_secrets_preserved=True,updated_at=stamp(datetime.now(timezone.utc)),
                      actual_scopes=list(config.google.scopes))
        authorization_path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({'oauth_write_consent':'passed','configuration_promoted':True,'existing_secrets_preserved':True}),flush=True)


def main(argv=None):
    p = argparse.ArgumentParser(description='Preparação e consentimento I5 com recursos existentes')
    action = p.add_mutually_exclusive_group(required=True)
    action.add_argument('--prepare',action='store_true'); action.add_argument('--authorize',action='store_true')
    p.add_argument('--consent-seconds',type=int,default=600,help='Tempo para concluir o navegador, entre 30 e 1800 segundos')
    args = p.parse_args(argv)
    try:
        if not 30 <= args.consent_seconds <= 1800:
            raise EngineError('google_consent_timeout_invalid')
        prepare() if args.prepare else authorize(consent_timeout_seconds=args.consent_seconds)
        return 0
    except EngineError as error:
        report_path=ROOT/'docs/evidencias/i5-live-authorizations.json'
        if args.authorize and report_path.exists():
            report=json.loads(report_path.read_text(encoding='utf-8'))
            report.update(oauth_write_consent='blocked',last_reason=error.code,
                          diagnostic=getattr(error,'diagnostic',{}),updated_at=stamp(datetime.now(timezone.utc)))
            report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({'result':'blocked','reason':error.code,'diagnostic':getattr(error,'diagnostic',{})}),flush=True); return 1
    except Exception:
        print(json.dumps({'result':'blocked','reason':'i5_enrollment_local_error'}),flush=True); return 1


if __name__ == '__main__':
    raise SystemExit(main())
