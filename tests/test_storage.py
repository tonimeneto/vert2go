from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
from datetime import timedelta
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from unittest.mock import patch
from uuid import uuid4
from app.core.contracts import EngineError, stamp
from app.core.orchestrator import Orchestrator
from app.main import instance_lock, main
from app.storage.sqlite import Store
from tests.support import EngineCase, ROOT


class StorageTests(EngineCase):
    def test_eleven_tables_version_integrity_and_foreign_keys(self):
        tables=self.store.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        self.assertEqual(len(tables),11)
        self.assertEqual(self.store.execute('PRAGMA user_version').fetchone()[0],2)
        self.assertEqual(self.store.execute('PRAGMA foreign_keys').fetchone()[0],1)
        self.assertEqual(self.store.execute('PRAGMA integrity_check').fetchone()[0],'ok')
        self.assertEqual(self.store.execute('PRAGMA foreign_key_check').fetchall(),[])
        self.store.verify()

    def test_unrecognized_preexisting_database_is_not_modified(self):
        path=self.folder/'other.sqlite3'
        con=sqlite3.connect(path)
        con.execute('CREATE TABLE important(value)')
        con.execute("INSERT INTO important VALUES ('fictional-preserved')")
        con.commit()
        con.close()
        original=path.read_bytes()
        with self.assertRaisesRegex(EngineError,'unrecognized_database'):
            Store(path)
        self.assertEqual(original,path.read_bytes())

    def test_existing_empty_file_is_not_adopted(self):
        path=self.folder/'empty.sqlite3'
        path.touch()
        with self.assertRaises(EngineError):
            Store(path)
        self.assertEqual(path.stat().st_size,0)

    def test_schema_tampering_detected_without_migration(self):
        self.store.execute('CREATE TABLE unexpected(value)')
        self.store.close()
        before=self.database.read_bytes()
        with self.assertRaisesRegex(EngineError,'schema_mismatch'):
            Store(self.database)
        self.assertEqual(before,self.database.read_bytes())

    def test_foreign_key_rejects_orphan_revision(self):
        created=self.create()
        with self.assertRaises(sqlite3.IntegrityError):
            with self.store.transaction():
                self.store.execute('UPDATE operational_guidance SET current_version=99')
        self.assertEqual(self.store.execute('SELECT current_version FROM operational_guidance').fetchone()[0],1)

    def test_atomic_rollback_after_revision_write(self):
        proposal=self.propose()
        real=self.store.execute
        def fail(sql, parameters=()):
            result=real(sql,parameters)
            if 'INSERT INTO operational_guidance_revisions' in sql:
                raise sqlite3.OperationalError('FAKE_SECRET_DB_ERROR')
            return result
        with patch.object(self.store,'execute',side_effect=fail):
            with self.assertLogs('alfredo',level='WARNING') as logs:
                result=self.confirm(proposal)
        self.assertEqual(result.code,'storage_error')
        self.assertNotIn('FAKE_SECRET_DB_ERROR',' '.join(logs.output))
        self.assertEqual(self.count('operational_guidance'),0)
        self.assertEqual(self.count('operational_guidance_revisions'),0)
        self.assertEqual(self.store.execute('SELECT state FROM requests_state').fetchone()[0],'awaiting_confirmation')
        self.assertEqual(self.confirm(proposal).code,'confirmed')

    def test_lost_response_after_commit_recovers_cached_result(self):
        proposal=self.propose()
        msg=self.msg()
        payload=dict(explicit=True,operation_id=proposal.data['operation_id'],proposal_hash=proposal.data['proposal_hash'])
        original=self.store.transaction
        calls=0
        @contextmanager
        def lost_response():
            nonlocal calls
            calls+=1
            current=calls
            with original():
                yield
            if current==1:
                raise OSError('simulated response loss')
        with patch.object(self.store,'transaction',side_effect=lost_response):
            self.assertEqual(self.engine.handle(msg,'confirm',payload).code,'storage_error')
        self.reopen()
        self.assertEqual(self.engine.handle(msg,'confirm',payload).code,'confirmed')
        self.assertEqual(self.count('operational_guidance_revisions'),1)

    def _crash_child(self, proposal, crash_inside):
        message=self.msg()
        payload=dict(explicit=True,operation_id=proposal.data['operation_id'],proposal_hash=proposal.data['proposal_hash'])
        self.store.close()
        script="""
import json,sys,os
from datetime import datetime
from app.config.schema import load_config
from app.storage.sqlite import Store
from app.core.contracts import Scope,Message
from app.core.orchestrator import Orchestrator
data=json.loads(sys.argv[1])
clock=lambda:datetime.fromisoformat(data['now'])
store=Store(data['db'])
engine=Orchestrator(load_config(data['config']),store,clock)
message=Message(Scope(*data['scope']),data['message_id'],clock(),data['correlation_id'])
if data['inside']:
    original=store.execute
    def interrupted(sql, parameters=()):
        result=original(sql,parameters)
        if 'INSERT INTO operational_guidance_revisions' in sql:
            os._exit(91)
        return result
    store.execute=interrupted
engine.handle(message,'confirm',data['payload'])
os._exit(92)
"""
        data=dict(now=self.clock().isoformat(),db=str(self.database),config=str(self.config_path),
                  scope=list(message.scope.key()),message_id=message.message_id,correlation_id=message.correlation_id,
                  payload=payload,inside=crash_inside)
        child=subprocess.run([sys.executable,'-c',script,json.dumps(data)],cwd=ROOT,capture_output=True,timeout=20)
        self.assertEqual(child.returncode,91 if crash_inside else 92,child.stderr)
        self.reopen()
        self.assertEqual(self.engine.handle(message,'confirm',payload).code,'confirmed')
        self.assertEqual(self.count('operational_guidance_revisions'),1)
        self.assertEqual(self.store.execute('PRAGMA integrity_check').fetchone()[0],'ok')

    def test_actual_process_interruption_before_commit_rolls_back(self):
        self._crash_child(self.propose(),True)

    def test_actual_process_interruption_after_commit_no_second_effect(self):
        self._crash_child(self.propose(),False)

    def test_uncertain_committing_state_is_not_replayed(self):
        proposal=self.propose()
        self.store.execute("UPDATE requests_state SET state='committing'")
        self.assertEqual(self.reopen()['recovered'],1)
        self.assertEqual(self.store.execute('SELECT state FROM requests_state').fetchone()[0],'needs_reconciliation')
        self.assertEqual(self.confirm(proposal).code,'operation_not_confirmable')
        self.assertEqual(self.count('operational_guidance'),0)

    def test_committed_revision_reconciles_operation(self):
        self.create()
        self.store.execute("UPDATE requests_state SET state='committing',closed_at=NULL,result=NULL")
        self.assertEqual(self.reopen()['recovered'],1)
        self.assertEqual(self.store.execute('SELECT state FROM requests_state').fetchone()[0],'confirmed')
        self.assertEqual(self.count('operational_guidance_revisions'),1)

    def test_two_concurrent_corrections_only_one_expected_version_commits(self):
        created=self.create()
        proposals=[self.propose('correct',guidance_id=created.data['guidance_id'],expected_version=1,
                                content='Fict?cio '+str(i)) for i in range(2)]
        def confirm(proposal):
            store=Store(self.database)
            try:
                engine=Orchestrator(self.config,store,self.clock)
                return engine.handle(self.msg(),'confirm',dict(explicit=True,
                    operation_id=proposal.data['operation_id'],proposal_hash=proposal.data['proposal_hash']))
            finally:
                store.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(confirm,proposals))
        self.assertEqual(sorted(r.code for r in results),['confirmed','stale_version'])
        self.assertEqual(self.count('operational_guidance_revisions'),2)

    def test_os_lock_blocks_second_process_then_releases(self):
        command=[sys.executable,'-m','app.main','--config',str(self.config_path),'--database',str(self.database)]
        with instance_lock(self.database):
            child=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,timeout=20)
            self.assertEqual(child.returncode,1)
            self.assertIn('instance_already_running',child.stderr)
        child=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,timeout=20)
        self.assertEqual(child.returncode,0,child.stderr)

    def test_os_lock_released_after_process_crash(self):
        script="from app.main import instance_lock\nimport os,sys\nwith instance_lock(sys.argv[1]):\n    os._exit(93)\n"
        child=subprocess.run([sys.executable,'-c',script,str(self.database)],cwd=ROOT,capture_output=True,timeout=20)
        self.assertEqual(child.returncode,93)
        with instance_lock(self.database):
            pass

    def test_local_startup_configuration_error_is_sanitized(self):
        bad=self.folder/'bad.yaml'
        bad.write_text('FAKE_SECRET: [',encoding='utf-8')
        with self.assertLogs(level='ERROR') as logs:
            code=main(['--config',str(bad),'--database',str(self.folder/'unused.db')])
        self.assertEqual(code,1)
        self.assertNotIn('FAKE_SECRET',' '.join(logs.output))
        self.assertFalse((self.folder/'unused.db').exists())
