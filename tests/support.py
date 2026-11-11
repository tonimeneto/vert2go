from datetime import datetime, timezone, timedelta
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4
import yaml
from app.config.schema import load_config
from app.core.contracts import Message, Scope
from app.core.orchestrator import Orchestrator
from app.storage.sqlite import Store

ROOT = Path(__file__).resolve().parents[1]


class Clock:
    def __init__(self):
        self.now = datetime(2026,11,5,15,0,tzinfo=timezone.utc)
    def __call__(self):
        return self.now
    def advance(self, **kwargs):
        self.now += timedelta(**kwargs)


class EngineCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='alfredo-i1-test-')
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.config_path = self.folder/'config.yaml'
        self.raw = yaml.safe_load((ROOT/'config.example.yaml').read_text(encoding='utf-8'))
        self.raw['users'][1]['chat_ids'] = [2002,2003]
        self.save_config()
        self.clock = Clock()
        self.database = self.folder/'test.sqlite3'
        self.store = Store(self.database)
        self.addCleanup(lambda: self.store.close())
        self.engine = Orchestrator(self.config,self.store,self.clock)
        self.manager = Scope(self.config.environment_id,'local',2002,2002)
        self.resident = Scope(self.config.environment_id,'local',1001,1001)
        for target in ('socket.socket.connect','socket.socket.connect_ex','socket.create_connection','urllib.request.urlopen'):
            blocker = patch(target,side_effect=AssertionError('Network is forbidden in I1 tests'))
            blocker.start()
            self.addCleanup(blocker.stop)

    def save_config(self):
        self.config_path.write_text(yaml.safe_dump(self.raw),encoding='utf-8')
        self.config = load_config(self.config_path)

    def msg(self, scope=None, **kwargs):
        return Message(scope or self.manager,str(uuid4()),self.clock(),str(uuid4()),**kwargs)

    def fields(self, **overrides):
        values = dict(topic='fachada',content='Dado fict?cio: manter janelas fechadas.',
                      audience='residents',effective_from=(self.clock()-timedelta(hours=1)).isoformat(),
                      effective_until=(self.clock()+timedelta(hours=4)).isoformat(),timezone='America/Sao_Paulo')
        values.update(overrides)
        return values

    def propose(self, kind='create', scope=None, **overrides):
        payload = dict(operation_id=str(uuid4()),idempotency_key=str(uuid4()))
        if kind != 'cancel':
            payload.update(self.fields())
        payload.update(overrides)
        result = self.engine.handle(self.msg(scope),'propose_'+kind,payload)
        return result

    def confirm(self, proposal, scope=None):
        return self.engine.handle(self.msg(scope),'confirm',dict(explicit=True,
            operation_id=proposal.data['operation_id'],proposal_hash=proposal.data['proposal_hash']))

    def create(self, **overrides):
        proposal = self.propose(**overrides)
        self.assertEqual(proposal.code,'proposal',proposal)
        result = self.confirm(proposal)
        self.assertEqual(result.code,'confirmed',result)
        return result

    def find(self, scope=None, **kwargs):
        return self.engine.handle(self.msg(scope or self.resident),'find_guidance',{'topic':'fachada',**kwargs})

    def count(self, table):
        return self.store.execute('SELECT count(*) FROM '+table).fetchone()[0]

    def reopen(self):
        self.store.close()
        self.store = Store(self.database)
        self.engine = Orchestrator(self.config,self.store,self.clock)
        return self.engine.startup()
