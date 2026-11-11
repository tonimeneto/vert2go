"""Finite demonstration using only fictional data and a disposable local SQLite."""
from datetime import timedelta
import json
from pathlib import Path
import tempfile
from uuid import uuid4
from app.config.schema import load_config
from app.core.contracts import Message, Scope, utcnow
from app.core.orchestrator import Orchestrator
from app.main import instance_lock
from app.storage.sqlite import Store


def main():
    root=Path(__file__).resolve().parents[1]
    config=load_config(root/'config.example.yaml')
    now=utcnow()
    def message(role):
        user=next(u for u in config.users if u.role==role)
        return Message(Scope(config.environment_id,user.channel,user.channel_user_id,user.chat_ids[0]),
                       str(uuid4()),now,str(uuid4()))
    fields=dict(topic='fachada',content='SIMULA??O: manter as janelas fechadas durante o servi?o fict?cio.',
                audience='residents',effective_from=now.isoformat(),
                effective_until=(now+timedelta(hours=4)).isoformat(),timezone=config.timezone)
    with tempfile.TemporaryDirectory(prefix='alfredo-i1-demo-') as folder:
        path=Path(folder)/'demo.sqlite3'
        with instance_lock(path):
            store=Store(path)
            try:
                engine=Orchestrator(config,store,lambda:now)
                engine.startup()
                proposal=engine.handle(message('manager'),'propose_create',
                    dict(operation_id=str(uuid4()),idempotency_key=str(uuid4()),**fields))
                before=engine.handle(message('resident'),'find_guidance',{'topic':'fachada'})
                confirmed=engine.handle(message('manager'),'confirm',
                    dict(explicit=True,operation_id=proposal.data['operation_id'],proposal_hash=proposal.data['proposal_hash']))
                after=engine.handle(message('resident'),'find_guidance',{'topic':'fachada'})
                output=dict(simulation=True,proposal=proposal.as_dict(),before_confirmation=before.as_dict(),
                            confirmation=confirmed.as_dict(),resident_query=after.as_dict())
                print(json.dumps(output,ensure_ascii=True,indent=2))
                return 0 if confirmed.code=='confirmed' and len(after.data['guidance'])==1 and not before.data['guidance'] else 1
            finally:
                store.close()


if __name__=='__main__':
    raise SystemExit(main())
