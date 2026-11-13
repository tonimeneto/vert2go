"""Explicit I4 sync/query/reconciliation; one process lock and redacted evidence."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.ai.runtime import knowledge_runtime
from app.config.schema import load_config, read_yaml, read_configuration_bytes, _parse_config
from app.core.contracts import EngineError, Message, Scope, digest, stamp, utcnow
from app.main import instance_lock
from app.storage.sqlite import Store


def main(argv=None):
    parser = argparse.ArgumentParser(description='Conhecimento I4: sincronizacao manual e consulta autorizada')
    parser.add_argument('operation',choices=('status','sync','query','reconcile'))
    parser.add_argument('--database',required=True,help='Banco explicitamente escolhido pelo responsavel')
    parser.add_argument('--config',default=str(ROOT/'config.yaml'))
    parser.add_argument('--secrets',default=str(ROOT/'secrets.yaml'))
    parser.add_argument('--allow-live-openai',action='store_true')
    parser.add_argument('--actor-id',type=int)
    parser.add_argument('--role',choices=('resident','manager'),help='Selecionar ID já cadastrado para consulta local')
    parser.add_argument('--question')
    parser.add_argument('--call-id')
    parser.add_argument('--remote-id')
    parser.add_argument('--input-tokens',type=int)
    parser.add_argument('--output-tokens',type=int)
    parser.add_argument('--searches',type=int)
    parser.add_argument('--confirm-reconciliation',action='store_true')
    parser.add_argument('--verified-not-created',action='store_true',
                        help='Responsavel verificou externamente que o recurso nao foi criado; permite novo sync manual')
    args = parser.parse_args(argv)
    report = {'phase':'I4','operation':args.operation,'updated_at':utcnow().isoformat(),
              'status':'blocked','external_api_attempted':False,'google_mutations_attempted':False}
    service = None
    try:
        config = load_config(args.config)
        config_before = read_configuration_bytes(args.config)
        if config.knowledge is None:
            raise EngineError('knowledge_not_configured')
        config.knowledge.require_consent()
        if args.operation == 'status':
            # No secret I/O, database creation/migration or network in status mode.
            path = Path(args.database)
            if not path.is_file():
                raise EngineError('knowledge_database_missing')
            import sqlite3
            con = sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)
            try:
                from app.storage.sqlite import APPLICATION_ID
                if con.execute('PRAGMA application_id').fetchone()[0] != APPLICATION_ID or con.execute('PRAGMA user_version').fetchone()[0] not in (3,4,5):
                    raise EngineError('knowledge_migration_required')
                rows = con.execute('SELECT kind,state,count(*) FROM knowledge_calls WHERE environment_id=? GROUP BY kind,state',
                                   (config.environment_id,)).fetchall()
                report.update(status='passed',calls=[{'kind':r[0],'state':r[1],'count':r[2]} for r in rows])
            finally:
                con.close()
        else:
            if not args.allow_live_openai:
                raise EngineError('live_openai_authorization_required')
            from app.ai.configuration import load_api_key
            load_api_key(args.secrets)
            with instance_lock(args.database):
                from app.storage.backup import before_knowledge_migration
                report['private_backup_created'] = before_knowledge_migration(args.database,args.config) is not None
                store = Store(args.database,knowledge=True)
                try:
                    with knowledge_runtime(config,store,args.secrets,allow_live=True) as service:
                        if args.operation == 'sync':
                            sync_result = service.sync()
                            report.update(sync_result,status='passed')
                            if config.knowledge.vector_store_id is None:
                                from app.integrations.private_files import atomic_yaml, private_lock
                                raw = read_yaml(args.config)
                                raw['knowledge']['vector_store_id'] = sync_result['vector_store_id']
                                with private_lock(args.config):
                                    atomic_yaml(args.config,config_before,raw,_parse_config)
                        elif args.operation == 'query':
                            if not args.question or (args.actor_id is None and args.role is None) or (args.actor_id is not None and args.role is not None):
                                raise EngineError('knowledge_query_identity_required')
                            user = next((u for u in config.users if u.enabled and
                                         (u.channel_user_id == args.actor_id if args.role is None else u.role == args.role)),None)
                            if user is None:
                                raise EngineError('unauthorized')
                            # Local operator queries do not send Telegram messages. Authorization remains by configured ID.
                            scope = Scope(config.environment_id,user.channel,user.channel_user_id,user.chat_ids[0])
                            message = Message(scope,'operator_'+digest([stamp(utcnow()),args.question])[:32],utcnow(),'i4_operator',args.question)
                            # Telegram-source context still requires its separate sharing permission.
                            result = service.answer(message,operator=True)
                            report.update(status=result.status,result_code=result.code,references=result.data.get('references',[]))
                            print(result.data.get('reply','Consulta sem resposta.'))
                        else:
                            if not args.confirm_reconciliation or not args.call_id:
                                raise EngineError('knowledge_reconciliation_confirmation_required')
                            service.reconcile(args.call_id,remote=args.remote_id,inputs=args.input_tokens,
                                              outputs=args.output_tokens,searches=args.searches,
                                              verified_not_created=args.verified_not_created)
                            report.update(status='passed')
                        report['budget'] = service.budget.assess()
                finally:
                    store.close()
    except EngineError as error:
        report.update(status='blocked',reason=error.code)
    except Exception:
        report.update(status='blocked',reason='knowledge_operation_failed')
    finally:
        if service is not None:
            report['openai_request_count'] = service.provider.request_count
            report['google_data_request_count'] = service.drive.request_count
            report['external_api_attempted'] = bool(service.provider.request_count or service.drive.request_count)
    folder = ROOT/'docs/evidencias'
    filename = 'i4-'+args.operation+'-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json'
    (folder/filename).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))
    return 0 if report['status'] in ('passed','success') else 1


if __name__ == '__main__':
    raise SystemExit(main())
