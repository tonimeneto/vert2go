"""Finite I5 demonstration: fictitious transports, no secrets, no network."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
from uuid import uuid4
from unittest.mock import patch
from app.config.schema import load_config
from app.core.contracts import Message, Scope
from app.core.orchestrator import Orchestrator
from app.services.operations import Operations
from app.storage.sqlite import Store


class Calendar:
    def __init__(self):
        self.events,self.creates = {},0
    def read_events(self, *args):
        return {'events':deepcopy(list(self.events.values())),'complete':True}
    def create_event(self, calendar_id, event):
        self.creates += 1
        self.events[event['id']] = {**deepcopy(event),'status':'confirmed'}
    def get_event(self, calendar_id, event_id):
        return deepcopy(self.events.get(event_id))


class Sheets:
    def __init__(self):
        self.rows,self.writes = [],0
    def read_range(self,*args): return deepcopy(self.rows)
    def write_row(self,spreadsheet_id,target,values):
        self.writes += 1
        self.rows = [deepcopy(values)]


def main():
    root = Path(__file__).resolve().parents[1]
    config = load_config(root/'config.operations.example.yaml')
    now = datetime(2026,11,5,15,tzinfo=timezone.utc)
    with tempfile.TemporaryDirectory(prefix='vert2go-i5-demo-') as folder, \
         patch('socket.socket.connect',side_effect=AssertionError('Demo is offline')):
        store = Store(Path(folder)/'demo.sqlite3',operations=True)
        try:
            calendar,sheets = Calendar(),Sheets()
            service = Operations(config,store,calendar,sheets,clock=lambda:now,lock_root=Path(folder)/'locks')
            engine = Orchestrator(config,store,lambda:now,operations=service)
            scope = Scope(config.environment_id,'telegram',1001,1001)
            def message(): return Message(scope,str(uuid4()),now,str(uuid4()))
            proposal = engine.handle(message(),'propose_reservation',{'resource':'salao',
                'start':'2026-11-06T14:00:00-03:00','end':'2026-11-06T16:00:00-03:00'})
            confirmation = message()
            fields = {'operation_id':proposal.data['operation_id'],'proposal_hash':proposal.data['proposal_hash'],'explicit':True}
            result = engine.handle(confirmation,'confirm_operation',fields)
            replay = engine.handle(confirmation,'confirm_operation',fields)
            synced = service.sync()
            report = {'phase':'I5','scope':'offline_simulation','proposal':proposal.code,'confirmation':result.code,
                      'replay':replay.code,'calendar_creates':calendar.creates,'sheets_writes':sheets.writes,
                      'synced':synced.data['synced'],'real_api_attempted':False}
            print(json.dumps(report,ensure_ascii=False))
            return 0 if result.code == 'reservation_confirmed' and calendar.creates == sheets.writes == 1 else 1
        finally:
            store.close()


if __name__ == '__main__':
    raise SystemExit(main())
