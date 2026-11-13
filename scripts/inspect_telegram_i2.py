"""Read-only, redacted operational snapshot. Never polls, sends, migrates or repairs."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.config.schema import load_config
from app.core.contracts import EngineError, stamp
from app.storage.sqlite import APPLICATION_ID


def inspect(config, database):
    report = {'phase': 'I2', 'scope': 'telegram_runtime_snapshot',
              'updated_at': datetime.now(timezone.utc).isoformat(),
              'database_exists': database.exists(), 'read_only': True,
              'external_api_attempted': False, 'human_delivery_confirmed': False,
              'live_acceptance': 'blocked', 'result': 'blocked'}
    if not database.exists():
        report['reason'] = 'telegram_database_not_created'
        return report
    con = sqlite3.connect(database.resolve().as_uri()+'?mode=ro', uri=True)
    try:
        if (con.execute('PRAGMA application_id').fetchone()[0] != APPLICATION_ID
                or con.execute('PRAGMA user_version').fetchone()[0] not in (2,3,4,5)):
            raise EngineError('unrecognized_database')
        identity = config.environment_id, config.telegram['bot_id']
        integrity = con.execute('PRAGMA integrity_check').fetchone()[0]
        report['integrity_check'] = 'ok' if integrity == 'ok' else 'failed'
        report['foreign_keys_valid'] = not con.execute('PRAGMA foreign_key_check').fetchall()
        row = con.execute('SELECT next_offset FROM telegram_poll_state WHERE environment_id=? AND bot_id=?', identity).fetchone()
        maximum = con.execute('SELECT max(update_id) FROM telegram_updates WHERE environment_id=? AND bot_id=? AND update_id>=0', identity).fetchone()[0]
        report['offset_persisted'] = row is not None
        report['offset_covers_receipts'] = maximum is None or (row is not None and row[0] > maximum)
        roles = {u.channel_user_id: u.role for u in config.users if u.enabled}
        report['delivery_states'] = {s: 0 for s in ('pending','sending','sent','uncertain','failed','discarded')}
        report['api_accepted_commands'] = {r: {'help_including_start':0, 'context':0} for r in ('resident','manager')}
        report['receipt_count'] = 0
        for actor, code, state, count in con.execute('''SELECT channel_user_id,code,state,count(*) FROM telegram_updates
                WHERE environment_id=? AND bot_id=? GROUP BY channel_user_id,code,state''', identity):
            report['receipt_count'] += count
            if state in report['delivery_states']:
                report['delivery_states'][state] += count
            role = roles.get(actor)
            if state == 'sent' and role in report['api_accepted_commands']:
                if code in ('help','context'):
                    report['api_accepted_commands'][role]['help_including_start' if code=='help' else 'context'] += count
        deferred = con.execute("SELECT max(next_attempt_at) FROM telegram_updates WHERE environment_id=? AND bot_id=? AND state='pending'", identity).fetchone()[0]
        report['delivery_backoff_active'] = bool(deferred and deferred > stamp(datetime.now(timezone.utc)))
        report['result'] = 'passed' if report['integrity_check']=='ok' and report['foreign_keys_valid'] and report['offset_covers_receipts'] else 'failed'
        report['reason'] = 'snapshot_only_human_and_scenario_acceptance_pending'
        return report
    finally:
        con.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description='Inspecao local I2 sem rede, migracao ou alteracao de dados')
    parser.add_argument('--config', default='config.yaml')
    parser.add_argument('--database', default='data/i2.sqlite3')
    args = parser.parse_args(argv)
    try:
        config = load_config(ROOT/args.config)
        if not config.telegram:
            raise EngineError('telegram_not_configured')
        report = inspect(config, ROOT/args.database)
    except EngineError as error:
        report = {'result':'blocked','reason':error.code,'read_only':True,'external_api_attempted':False}
    except (OSError,sqlite3.Error,ValueError,TypeError):
        report = {'result':'blocked','reason':'local_inspection_error','read_only':True,'external_api_attempted':False}
    (ROOT/'docs'/'evidencias'/'i2-runtime-snapshot.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))
    return 0 if report['result']=='passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
