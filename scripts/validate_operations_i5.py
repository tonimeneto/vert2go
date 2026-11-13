"""Resumable live I5 proof. Existing pilot resources only; no deletion or Git.

Inputs are explicitly synthetic engine messages. Google calls are real; injected
timeouts/crashes are labeled separately. This is not a Telegram delivery proof.
"""
import argparse
from dataclasses import replace
from datetime import datetime, timezone, timedelta
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.config.schema import load_config
from app.core.contracts import EngineError, Message, Scope, canonical, stamp, instant, digest, utcnow
from app.core.orchestrator import Orchestrator
from app.integrations.operations import FreshGoogle
from app.integrations.private_files import private_acl, no_links
from app.main import instance_lock
from app.services.operations import Operations
from app.storage.backup import before_operations_migration
from app.storage.sqlite import Store


class SimulatedInterruption(BaseException):
    pass


class FaultCalendar:
    def __init__(self, actual, *, crash=False):
        self.actual,self.crash,self.creates = actual,crash,0
    def read_events(self,*args): return self.actual.read_events(*args)
    def get_event(self,*args): return self.actual.get_event(*args)
    def create_event(self,*args):
        self.creates += 1
        self.actual.create_event(*args)
        if self.crash: raise SimulatedInterruption()
        raise EngineError('injected_timeout_after_real_calendar_write')


class FaultSheets:
    def __init__(self, actual, *, after_write=False):
        self.actual,self.after_write,self.writes = actual,after_write,0
    def read_range(self,*args):
        if not self.after_write: raise EngineError('injected_sheets_unavailable')
        return self.actual.read_range(*args)
    def write_row(self,*args):
        self.writes += 1
        self.actual.write_row(*args)
        raise EngineError('injected_timeout_after_real_sheets_write')


class Proof:
    def __init__(self, root=ROOT, *, semantic_preflight=False):
        self.root=root; self.config=load_config(root/'config.yaml')
        if semantic_preflight and self.config.operations is None:
            staged=load_config(root/'data/i5-candidate-config.yaml')
            # Extraction needs resource names, not Google write credentials. Preserve read-only Google binding.
            self.config=replace(self.config,operations=staged.operations)
        self.config.operations.require_live() if self.config.operations else self.fail('operations_not_configured')
        self.state_path=root/'data/i5-live-state.json'
        self.report_path=root/'docs/evidencias/i5-live-validation.json'
        self.state=json.loads(self.state_path.read_text(encoding='utf-8')) if self.state_path.exists() else {
            'run_id':str(uuid4()),'messages':{},'proposals':{},'steps':{}}
        self.report=json.loads(self.report_path.read_text(encoding='utf-8')) if self.report_path.exists() else {
            'phase':'I5','input_origin':'synthetic_engine_messages','google_transport':'real_authorized_pilot',
            'telegram_live_test':'not_run','full_acceptance':False,'deletions_attempted':False,'git_operations':False,'tests':{}}
        self.actual=FreshGoogle(self.config,root/'secrets.yaml',allow_live=True)
        self.store=None

    @staticmethod
    def fail(code): raise EngineError(code)

    def save(self):
        self.report['updated_at']=stamp(utcnow())
        self.report['pending']=['Telegram I5 nas duas contas e confirmação humana',
                                'aceite formal I5 e demais critérios obrigatórios ainda sem evidência real']
        self.report_path.write_text(json.dumps(self.report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        no_links(self.state_path)
        if not self.state_path.exists():
            fd=os.open(self.state_path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600); os.close(fd)
        private_acl(self.root/'config.yaml',self.state_path)
        self.state_path.write_text(json.dumps(self.state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

    def record(self, name, ok, **evidence):
        previous=self.report['tests'].get(name)
        if previous and previous['result']=='passed' and ok:
            previous['revalidated_at']=stamp(utcnow())
        else:
            self.report['tests'][name]={'result':'passed' if ok else 'failed',**evidence}
        self.save(); print(json.dumps({'test':name,'result':'passed' if ok else 'failed'}),flush=True)
        if not ok: self.fail('i5_live_assertion_failed')

    def message(self, name, *, role='resident', text=None):
        u=next(u for u in self.config.users if u.role==role and u.enabled)
        if name not in self.state['messages']:
            self.state['messages'][name]={'id':'i5live_'+uuid4().hex,'received_at':stamp(utcnow()),
                                         'text':text or 'Ensaio I5 fictício — '+name,'role':role}
            self.save()
        v=self.state['messages'][name]
        if v['role']!=role: self.fail('i5_test_identity_conflict')
        return Message(Scope(self.config.environment_id,u.channel,u.channel_user_id,u.chat_ids[0]),
                       v['id'],instant(v['received_at']),'i5live_'+self.state['run_id'],v['text'])

    def bind(self, calendar=None, sheets=None):
        self.operations=Operations(self.config,self.store,calendar or self.actual,sheets or self.actual)
        self.engine=Orchestrator(self.config,self.store,operations=self.operations)

    def proposal(self, name, offset):
        if name in self.state['proposals']: return self.state['proposals'][name]
        local=utcnow().astimezone(__import__('zoneinfo').ZoneInfo(self.config.timezone))
        day=(local+timedelta(days=offset)).date().isoformat()
        payload={'resource':'salao','start':day+'T14:00:00-03:00','end':day+'T15:00:00-03:00'}
        result=self.engine.handle(self.message(name),'propose_reservation',payload)
        if result.code!='pilot_proposal': self.fail('i5_live_proposal_'+result.code)
        self.state['proposals'][name]=result.data; self.save()
        return result.data

    def confirm(self, name, proposal):
        return self.engine.handle(self.message(name),'confirm_operation',{'operation_id':proposal['operation_id'],
            'proposal_hash':proposal['proposal_hash'],'explicit':True})

    def open(self):
        if 'baseline_rows' not in self.state:
            con=sqlite3.connect((self.root/'data/i2.sqlite3').resolve().as_uri()+'?mode=ro',uri=True)
            try:
                tables=[r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
                self.state['baseline_rows']={name:[digest(list(row)) for row in con.execute('SELECT * FROM "'+name+'"')]
                                             for name in tables}
            finally: con.close()
            self.save()
        backup=before_operations_migration(self.root/'data/i2.sqlite3',self.root/'config.yaml')
        self.store=Store(self.root/'data/i2.sqlite3',operations=True); self.bind()
        if backup: self.report['private_database_backup_created']=True
        self.report['database_schema']=self.store.execute('PRAGMA user_version').fetchone()[0]
        self.save()

    def preservation(self):
        counts={}; all_preserved=True
        for name,old in self.state['baseline_rows'].items():
            current={digest(list(row)) for row in self.store.execute('SELECT * FROM "'+name+'"')}
            preserved=all(value in current for value in old)
            counts[name]={'original_rows':len(old),'preserved':preserved}
            all_preserved=all_preserved and preserved
        self.record('existing_rows_preserved',all_preserved,tables=counts)

    def create(self):
        if self.state['steps'].get('create'): return
        self.report['google_transport']='real_authorized_pilot'
        self.report['google_write_tests']='in_progress'
        a=self.proposal('reservation_a',1); b=self.proposal('reservation_b_same_slot',1)
        result=self.confirm('confirm_a',a)
        if result.code=='reservation_confirmed' or result.status=='uncertain':
            self.report['google_mutations_attempted']=True
        self.record('calendar_create_and_readback',result.code=='reservation_confirmed',operation_id=a['operation_id'],
                    external_reference=result.data.get('external_reference'))
        replay=self.confirm('confirm_a',a)
        self.record('confirmation_replay',replay.code=='reservation_confirmed',same_message=True)
        conflict=self.confirm('confirm_b_same_slot',b)
        self.record('two_proposals_single_slot',conflict.status=='conflict',second_event_not_created=True)
        later=self.engine.handle(self.message('query_a'),'reservation_status',{'operation_id':a['operation_id']})
        self.record('reservation_current_calendar_evidence',later.code=='reservation_confirmed')
        broken=FaultSheets(self.actual); self.bind(sheets=broken)
        sync=self.operations.sync()
        self.bind()
        still=self.engine.handle(self.message('query_a_after_sheets_failure'),'reservation_status',{'operation_id':a['operation_id']})
        self.record('sheets_failure_does_not_invalidate_reservation',sync.status=='pending' and still.code=='reservation_confirmed',
                    fault_injection='Sheets unavailable before real mutation')
        timeout=self.proposal('reservation_timeout',2)
        fault=FaultCalendar(self.actual); self.bind(calendar=fault)
        uncertain=self.confirm('confirm_timeout',timeout)
        self.record('calendar_timeout_after_real_write',uncertain.status=='uncertain',operation_id=timeout['operation_id'],
                    fault_injection='timeout after successful real POST',create_attempts=fault.creates)
        self.bind()
        crash=self.proposal('reservation_restart',3)
        fault=FaultCalendar(self.actual,crash=True); self.bind(calendar=fault)
        try: self.confirm('confirm_restart',crash)
        except SimulatedInterruption: pass
        row=self.store.execute('SELECT state FROM pilot_operations WHERE environment_id=? AND operation_id=?',
                               (self.config.environment_id,crash['operation_id'])).fetchone()
        self.record('interrupted_after_real_write_before_result',row[0]=='committing',operation_id=crash['operation_id'],
                    fault_injection='local interruption after successful real POST',process_id=os.getpid())
        self.state['steps']['create']=True; self.save()

    def recover(self):
        if not self.state['steps'].get('create'): self.fail('i5_create_phase_required')
        self.bind(); recovered=self.operations.startup()
        for key in ('reservation_timeout','reservation_restart'):
            p=self.state['proposals'][key]
            result=self.engine.handle(self.message('reconcile_'+key,role='manager'),'reconcile_operation',{'operation_id':p['operation_id']})
            self.record('reconcile_'+key,result.code=='reservation_confirmed',operation_id=p['operation_id'],
                        external_reference=result.data.get('external_reference'),process_id=os.getpid(),new_post_not_attempted=True)
        self.report['restart_recovered_operations']=recovered
        if not self.state['steps'].get('sheets_timeout'):
            fault=FaultSheets(self.actual,after_write=True); self.bind(sheets=fault)
            result=self.operations.sync()
            self.record('sheets_timeout_after_real_put',result.status=='pending' and fault.writes>0,
                        fault_injection='timeout after actual RAW PUT',real_put_attempts=fault.writes)
            self.state['steps']['sheets_timeout']=True; self.save()
        self.bind(); first=self.operations.sync(); second=self.operations.sync()
        pending=self.store.execute("SELECT count(*) FROM pilot_outbox WHERE environment_id=? AND state!='synced'",
                                   (self.config.environment_id,)).fetchone()[0]
        self.record('sheets_reconciliation_and_idempotent_reprocess',first.status==second.status=='success' and pending==0,
                    rows_reconciled=first.data['synced'],second_sync_rows=second.data['synced'])
        events=self.actual.read_events(self.config.google.calendar_id,self.config.google.window_start,self.config.google.window_end)
        expected={digest([self.config.environment_id,self.state['proposals'][k]['operation_id']])
                  for k in ('reservation_a','reservation_timeout','reservation_restart')}
        actual={v['id'] for v in events['events']}
        self.record('calendar_three_unique_test_events',expected==actual,expected_test_events=3,
                    actual_event_count=len(actual),matched_event_ids=sorted(expected&actual))
        self.record('resident_report_denied',self.engine.handle(self.message('resident_report'),'operations_report',{}).code=='unauthorized')
        self.record('manager_report',self.engine.handle(self.message('manager_report',role='manager'),'operations_report',{}).code=='pilot_report')
        self.state['steps']['recover']=True; self.save()
        self.report['google_write_tests']='passed_selected_scenarios'
        self.save()

    def semantic(self):
        from app.ai.runtime import knowledge_runtime
        from app.ai.operation_intent import OperationInterpreter
        if self.state['steps'].get('semantic'): return
        text='Quero reservar o salao amanhã, das 14h às 15h. É somente o teste experimental I5.'
        message=self.message('semantic_reservation',text=text)
        with knowledge_runtime(self.config,self.store,self.root/'secrets.yaml',allow_live=True) as knowledge:
            before=knowledge.budget.assess()
            parsed=OperationInterpreter(knowledge).interpret(message)
            after=knowledge.budget.assess()
        expected=(message.received_at.astimezone(__import__('zoneinfo').ZoneInfo(self.config.timezone))+timedelta(days=1)).date()
        valid=parsed['action']=='reservation' and parsed['resource']=='salao' and instant(parsed['start']).astimezone(
            __import__('zoneinfo').ZoneInfo(self.config.timezone)).date()==expected
        valid=valid and instant(parsed['start']).astimezone(__import__('zoneinfo').ZoneInfo(self.config.timezone)).strftime('%H:%M')=='14:00'
        valid=valid and instant(parsed['end']).astimezone(__import__('zoneinfo').ZoneInfo(self.config.timezone)).strftime('%H:%M')=='15:00'
        self.record('real_model_semantic_extraction',valid,model=self.config.knowledge.model,
                    no_calendar_write_from_model=True,budget_before_brl=before['estimated_brl'],budget_after_brl=after['estimated_brl'])
        self.state['steps']['semantic']=True; self.save()


def main(argv=None):
    p=argparse.ArgumentParser(description='Ensaios reais I5 sem exclusão ou Git')
    p.add_argument('--phase',choices=('create','recover','semantic'),required=True)
    args=p.parse_args(argv)
    proof=None
    try:
        proof=Proof(semantic_preflight=args.phase=='semantic')
        with instance_lock(ROOT/'data/i2.sqlite3'):
            proof.open(); getattr(proof,args.phase)(); proof.preservation()
        return 0
    except EngineError as error:
        if proof:
            proof.report['last_blocker']=error.code; proof.save()
        print(json.dumps({'result':'blocked','reason':error.code}),flush=True); return 1
    except Exception:
        if proof:
            proof.report['last_blocker']='i5_live_local_error'; proof.save()
        print(json.dumps({'result':'blocked','reason':'i5_live_local_error'}),flush=True); return 1
    finally:
        if proof and proof.store: proof.store.close()


if __name__=='__main__': raise SystemExit(main())
