"""Redacted read-only data proof. No polling, operational database or document cache."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.config.schema import load_config, load_enrollment_secrets
from app.core.contracts import EngineError, canonical
from app.integrations.google_auth import GoogleAuth
from app.integrations.google_config import validate_binding
from app.integrations.google_http import GoogleHTTP
from app.integrations.private_files import private_acl
from app.integrations.drive import Drive
from app.integrations.calendar import Calendar
from app.integrations.sheets import Sheets


def reference(value):
    return hashlib.sha256(value.encode()).hexdigest()[:24]


def check(root=ROOT, *, allow_live=False, verify_refresh=False):
    report = {'phase': 'I3', 'scope': 'google_read_only', 'updated_at': datetime.now(timezone.utc).isoformat(),
              'local_configuration': 'blocked', 'local_credentials': 'not_run', 'account_verified': 'not_run',
              'refresh_and_reload': 'not_run', 'documents': [], 'calendar': {'result': 'not_run'},
              'sheets': {'result': 'not_run'}, 'calls': [], 'external_api_attempted': False,
              'google_mutations_attempted': False, 'database_opened': False, 'openai_used': False,
              'acceptance': 'blocked', 'I4_I5_I6': 'not_authorized'}
    http = None
    try:
        config = load_config(root/'config.yaml').google
        if config is None:
            raise EngineError('google_not_configured')
        report['local_configuration'] = 'passed'
        private_acl(root/'secrets.yaml')
        oauth = load_enrollment_secrets(root/'secrets.yaml')['google_oauth']
        validate_binding(oauth, config)
        report['local_credentials'] = 'passed'
        if not allow_live:
            report['reason'] = 'live_google_not_requested'
            return report
        report['external_api_attempted'] = True
        auth = GoogleAuth(config, root/'secrets.yaml', allow_live=True)
        if verify_refresh:
            auth.bearer(force_refresh=True)
            # Fresh manager rereads the persisted YAML; no in-memory token reuse.
            auth = GoogleAuth(config, root/'secrets.yaml', allow_live=True)
        http = GoogleHTTP(config, auth.bearer, allow_live=True, refresh=lambda: auth.bearer(force_refresh=True))
        identity = http.read('identity', '').json()
        if identity.get('user', {}).get('emailAddress', '').casefold() != config.expected_account:
            raise EngineError('google_account_mismatch')
        report['account_verified'] = 'passed'
        if verify_refresh:
            report['refresh_and_reload'] = 'passed'
            report['reload_modality'] = 'new_manager_same_process'
        for doc in config.documents:
            entry = {'resource_ref': reference(doc.id), 'result': 'failed'}
            try:
                value = Drive(config, http).read_document(doc.id)
                entry.update(result='passed', byte_count=len(value.content), sha256=value.sha256,
                             source_version_ref=reference(value.source_version), classification=value.classification,
                             mime_type=value.mime_type)
            except EngineError as error:
                entry['reason'] = error.code
            report['documents'].append(entry)
        if config.calendar_id:
            try:
                value = Calendar(config, http).read_events(config.calendar_id, config.window_start, config.window_end)
                report['calendar'] = {'result': 'passed', 'resource_ref': reference(config.calendar_id),
                                      'event_count': len(value['events']), 'empty': not value['events'],
                                      'data_sha256': hashlib.sha256(canonical(value).encode()).hexdigest(), 'complete': True}
            except EngineError as error:
                report['calendar'] = {'result': 'failed', 'reason': error.code}
        if config.spreadsheet_id:
            try:
                adapter = Sheets(config, http)
                adapter.read_metadata(config.spreadsheet_id)
                if config.discover_structure:
                    structure = adapter.read_structure(config.spreadsheet_id)
                    report['sheets_structure'] = {'result': 'passed', **structure,
                                                   'cells_read': False, 'dimensions_are_used_range': False}
                ranges = []
                for target in config.ranges:
                    rows = adapter.read_range(config.spreadsheet_id, target)
                    ranges.append({'range_ref': reference(target), 'row_count': len(rows),
                                   'cell_count': sum(map(len, rows)), 'empty': not rows,
                                   'data_sha256': hashlib.sha256(canonical(rows).encode()).hexdigest()})
                report['sheets'] = {'result': 'passed' if config.ranges else 'metadata_only',
                                   'resource_ref': reference(config.spreadsheet_id), 'ranges': ranges}
            except EngineError as error:
                report['sheets'] = {'result': 'failed', 'reason': error.code}
        passed = (all(d['result'] == 'passed' for d in report['documents']) and
                  report['calendar']['result'] == report['sheets']['result'] == 'passed' and
                  report['refresh_and_reload'] == 'passed')
        report['acceptance'] = 'passed_google_reads' if passed else 'pending'
        report['reason'] = 'offline_tests_and_owner_review_also_required' if passed else 'google_acceptance_incomplete'
    except EngineError as error:
        report['reason'] = error.code
    except Exception:
        report['reason'] = 'google_local_check_error'
    finally:
        if http is not None:
            report['calls'] = http.calls
            http.close()
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description='Diagnostico Google I3: somente leituras permitidas')
    parser.add_argument('--allow-live-google', action='store_true')
    parser.add_argument('--verify-refresh', action='store_true')
    args = parser.parse_args(argv)
    if args.verify_refresh and not args.allow_live_google:
        parser.error('--verify-refresh exige --allow-live-google')
    report = check(allow_live=args.allow_live_google, verify_refresh=args.verify_refresh)
    folder = ROOT/'docs'/'evidencias'
    folder.mkdir(exist_ok=True)
    path = folder/'i3-google-check.json'
    # A read-only/offline probe cannot overwrite real evidence from a previous run.
    if path.exists():
        previous = json.loads(path.read_text(encoding='utf-8'))
        if previous.get('external_api_attempted'):
            path = folder/('i3-google-check-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json')
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report['acceptance'] == 'passed_google_reads' else 1


if __name__ == '__main__':
    raise SystemExit(main())
