"""Security acceptance on private disposable SQLite copies; never connects to Telegram.

The operational database is opened mode=ro and copied with SQLite's backup API.
Runtime authorization/configuration is reused unchanged; secrets are never read.
This runner is local evidence and cannot grant real-message acceptance by itself.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.config.schema import load_config
from app.core.contracts import EngineError
from tests.test_telegram_acceptance import TelegramAcceptanceTests


def logical_fingerprint(connection):
    value = hashlib.sha256()
    for line in connection.iterdump():
        value.update(line.encode('utf-8'))
        value.update(b'\n')
    return value.digest()


def project_path(value):
    path = (ROOT/value).resolve()
    if not path.is_relative_to(ROOT):
        raise EngineError('acceptance_path_outside_project')
    return path


def observe_live_context(config, connection):
    """Read persisted scopes/replies; publish predicates, never references or identities."""
    roles, references = {}, {}
    identity = config.environment_id, config.telegram['bot_id']
    for user in config.users:
        if not user.enabled:
            continue
        context = connection.execute("""SELECT payload,updated_at FROM conversation_state
            WHERE environment_id=? AND channel='telegram' AND channel_user_id=? AND chat_id=?
            AND state_key='context' AND expires_at>?""",
            (identity[0], user.channel_user_id, user.channel_user_id,
             datetime.now(timezone.utc).isoformat())).fetchone()
        reference = json.loads(context[0]).get('unit_reference') if context else None
        reads = connection.execute("""SELECT reply FROM telegram_updates WHERE environment_id=?
            AND bot_id=? AND channel_user_id=? AND chat_id=? AND code='context' AND state='sent'
            AND created_at>=? ORDER BY created_at DESC LIMIT 1""",
            (*identity, user.channel_user_id, user.channel_user_id, context[1] if context else '9999')).fetchone()
        saved = connection.execute("""SELECT count(*) FROM telegram_updates WHERE environment_id=?
            AND bot_id=? AND channel_user_id=? AND chat_id=? AND code='context_saved' AND state='sent'
            AND updated_at>=?""",
            (*identity, user.channel_user_id, user.channel_user_id, context[1] if context else '9999')).fetchone()[0]
        own = json.loads(reads[0]).get('data', {}).get('context') if reads else None
        roles[user.role] = {'has_nonempty_unit_reference': type(reference) is str and bool(reference),
                            'unit_save_response_api_accepted': bool(saved),
                            'subsequent_context_response_api_accepted': bool(reads),
                            'subsequent_response_contains_exactly_own_reference': bool(reference) and own == {'unit_reference': reference}}
        references[user.role] = reference
    distinct = bool(references.get('resident')) and bool(references.get('manager')) and references['resident'] != references['manager']
    return {'read_only': True, 'distinct_references': bool(distinct), 'roles': roles,
            'api_and_persistence_observation': 'passed' if distinct and all(
                all(r.values()) for r in roles.values()) else 'not_proven',
            'human_confirmation_inferred': False}


def run(config_path, source_path):
    config_bytes = config_path.read_bytes()
    config = load_config(config_path)
    if not config.telegram:
        raise EngineError('telegram_not_configured')
    report = {'phase': 'I2', 'scope': 'local_security_acceptance_on_operational_snapshot',
        'updated_at': datetime.now(timezone.utc).isoformat(),
        'operational_database_open_mode': 'ro', 'operational_database_write_attempted': False,
        'source_snapshot_method': 'sqlite_backup_api', 'secrets_read': False,
        'external_api_attempted': False, 'messages_sent_to_telegram': False,
        'transport': 'in_memory_capture_with_network_guards',
        'administrative_simulation_enabled': False,
        'local_acceptance': 'blocked', 'live_acceptance': 'not_decided_by_this_runner',
        'I3': 'not_authorized', 'git_operations': False, 'lovable_publication': False}
    with tempfile.TemporaryDirectory(prefix='vert2go-i2-acceptance-snapshot-') as folder:
        frozen = Path(folder)/'snapshot.sqlite3'
        source = sqlite3.connect(source_path.as_uri()+'?mode=ro', uri=True)
        destination = sqlite3.connect(frozen)
        try:
            source.execute('BEGIN')
            initial = logical_fingerprint(source)
            source.backup(destination)
            report['source_schema_version'] = source.execute('PRAGMA user_version').fetchone()[0]
            report['source_integrity_ok'] = source.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
            report['source_foreign_keys_valid'] = not source.execute('PRAGMA foreign_key_check').fetchall()
            report['source_receipts_at_snapshot'] = source.execute('SELECT count(*) FROM telegram_updates').fetchone()[0]
            report['live_context_observation_at_snapshot'] = observe_live_context(config, source)
        finally:
            destination.close()
            source.close()
        case_type = type('OperationalSnapshotAcceptance', (TelegramAcceptanceTests,),
                         {'runtime_config': config, 'source_database': frozen})
        outcomes = []
        logger = logging.getLogger('alfredo')
        previous_disabled = logger.disabled
        logger.disabled = True
        try:
            for name in unittest.defaultTestLoader.getTestCaseNames(case_type):
                case = case_type(name)
                result = unittest.TestResult()
                case.run(result)
                status = ('error' if result.errors else 'failed' if result.failures
                          else 'skipped' if result.skipped else 'passed')
                # No traceback, exception repr, assertion values, raw messages or identities in evidence.
                outcomes.append({'scenario': name.removeprefix('test_'), 'result': status,
                                 'checks': getattr(case, 'evidence', {})})
        finally:
            logger.disabled = previous_disabled
        after = sqlite3.connect(source_path.as_uri()+'?mode=ro', uri=True)
        try:
            report['source_logical_contents_unchanged_during_runner'] = logical_fingerprint(after) == initial
        finally:
            after.close()
    report['configuration_bytes_unchanged'] = config_path.read_bytes() == config_bytes
    report['scenarios'] = outcomes
    report['tests_run'] = len(outcomes)
    report['passed'] = sum(c['result'] == 'passed' for c in outcomes)
    report['failed'] = sum(c['result'] == 'failed' for c in outcomes)
    report['errors'] = sum(c['result'] == 'error' for c in outcomes)
    report['temporary_copies_removed'] = True
    report['local_acceptance'] = 'passed' if (
        outcomes and all(c['result'] == 'passed' for c in outcomes)
        and report['configuration_bytes_unchanged'] and report['source_integrity_ok']
        and report['source_foreign_keys_valid']) else 'failed'
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description='Aceite local I2 em copias temporarias, sem rede nem segredos')
    parser.add_argument('--config', default='config.yaml')
    parser.add_argument('--database', default='data/i2.sqlite3')
    args = parser.parse_args(argv)
    try:
        report = run(project_path(args.config), project_path(args.database))
    except (EngineError, OSError, sqlite3.Error, ValueError, TypeError):
        report = {'phase': 'I2', 'scope': 'local_security_acceptance_on_operational_snapshot',
                  'local_acceptance': 'blocked', 'reason': 'acceptance_setup_error',
                  'external_api_attempted': False, 'secrets_read': False}
    (ROOT/'docs/evidencias/i2-security-tests.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k: report[k] for k in ('local_acceptance', 'tests_run', 'passed', 'failed', 'errors') if k in report}))
    return 0 if report['local_acceptance'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
