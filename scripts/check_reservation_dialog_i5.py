"""Replay the reported conversation with actual config and read-only Google.

The Telegram transport, database, event creation and readback are simulated.
No operational database is opened and no external write transport is constructed.
"""
import argparse
from copy import deepcopy
from contextlib import closing
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.channels.telegram import TelegramChannel
from app.config.schema import load_config
from app.core.contracts import EngineError,utcnow,instant
from app.core.orchestrator import Orchestrator
from app.integrations.calendar import Calendar
from app.integrations.google_auth import GoogleAuth
from app.integrations.google_http import GoogleHTTP
from app.services.operations import Operations
from app.storage.sqlite import Store
from examples.i2_demo import FakeTelegram,update


class ReadOnlyCalendarWithSimulatedWrites:
    def __init__(self,config,actual):
        self.config,self.actual=config,actual
        self.reads,self.simulated_creates=0,0
        self.local={}

    def read_events(self,calendar_id,start,end):
        self.reads+=1
        result=self.actual.read_events(calendar_id,start,end)
        return {**result,'events':result['events']+deepcopy(list(self.local.values()))}

    def create_event(self,calendar_id,event):
        assert calendar_id==self.config.operations.calendar_id
        self.simulated_creates+=1
        self.local.setdefault(event['id'],{**deepcopy(event),'status':'confirmed'})

    def get_event(self,calendar_id,event_id):
        assert calendar_id==self.config.operations.calendar_id
        return deepcopy(self.local.get(event_id))


class NoSheetsWrites:
    def read_range(self,*args):raise AssertionError('No Sheets operation expected')
    def write_row(self,*args):raise AssertionError('No Sheets operation expected')


class NoModel:
    def interpret(self,*args,**kwargs):raise AssertionError('Grounded replay must not need a model')


def replay(config,calendar,folder,day):
    actor=next(u.channel_user_id for u in config.users if u.role=='resident' and u.enabled)
    api=FakeTelegram()
    with closing(Store(Path(folder)/'isolated.sqlite3',operations=True)) as store:
        ops=Operations(config,store,calendar,NoSheetsWrites(),lock_root=Path(folder)/'locks')
        engine=Orchestrator(config,store,operations=ops)
        channel=TelegramChannel(config,store,engine,api,operation_interpreter=NoModel())
        engine.startup()
        number=datetime.fromisoformat(day).day
        complete=datetime.fromisoformat(day).strftime('%d/%m/%Y')
        messages=[
            (f'Olá quero reservar o salão de festas para dia {number} das 14 às 20','clarification_required'),
            (complete,'clarification_required'),
            ('Quais os horários disponíveis nesse dia','pilot_availability'),
            ('Pode ser das 8:00 às 12','pilot_availability'),
            (f'Puta que pariu como é que eu faço para poder reservar um horário no dia {number}','pilot_availability'),
            (f'Reserva no dia {number} das 8:00 ao meio-dia','pilot_availability'),
            ('Então das 14 às 18','pilot_proposal'),
            ('Sim, pode reservar','reservation_confirmed'),
        ]
        steps=[]
        for index,(text,expected) in enumerate(messages,1):
            entry=update(index,text,utcnow,actor)
            if index==len(messages):
                parent=next(i for i in range(len(api.sent),0,-1) if api.sent[i-1]['chat_id']==actor)
                entry['message']['reply_to_message']={'message_id':parent,
                    'from':{'id':config.telegram['bot_id'],'is_bot':True},'chat':{'id':actor,'type':'private'}}
            before=calendar.simulated_creates
            code=channel.process(entry);channel.deliver()
            assert code==expected,(index,code,expected)
            if index<len(messages):assert calendar.simulated_creates==before==0
            reply=next(m['text'] for m in reversed(api.sent) if m['chat_id']==actor)
            if index in (4,6):assert 'conflito' in reply and 'revalidação' not in reply
            steps.append({'step':index,'code':code,'expected':expected,'passed':True,'reply':reply})
        assert calendar.simulated_creates==1
        channel.process(entry);channel.deliver()
        assert calendar.simulated_creates==1
        row=store.execute("SELECT proposal,state FROM pilot_operations WHERE kind='reservation'").fetchone()
        assert row['state']=='confirmed'
        proposal=json.loads(row['proposal'])
        assert instant(proposal['start'])<instant(proposal['end'])
        return {'steps':steps,'duplicate_confirmation_created_again':False,
                'simulated_event_creates':calendar.simulated_creates,'calendar_reads':calendar.reads}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--allow-live-calendar',action='store_true')
    parser.add_argument('--date',required=True)
    args=parser.parse_args(argv)
    if not args.allow_live_calendar:parser.error('Explicit read-only Calendar access required')
    config=load_config(ROOT/'config.yaml')
    report={'phase':'I5','scope':'actual_config_real_calendar_reads_isolated_database_fake_telegram_simulated_event_write',
        'updated_at':utcnow().isoformat(),'result':'failed','google_mutations_attempted':False,
        'operational_database_opened':False,'live_telegram_messages_sent':0,'model_calls':0,
        'human_acceptance':False,'full_acceptance':False,'date':args.date,'source_sha256':{
            str(p.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [Path(__file__),ROOT/'app/services/operations.py',ROOT/'app/channels/reservation_conversation.py',ROOT/'app/channels/reservation_time.py']}}
    report['configuration_sha256']=hashlib.sha256((ROOT/'config.yaml').read_bytes()).hexdigest()
    report['parameters']={'window_start':config.google.window_start,'window_end':config.google.window_end,
        'alternative_offsets_days':config.operations.alternative_offsets_days,
        'resources':[{k:r[k] for k in ('id','status','verified_at','valid_until','opens','closes','max_duration_minutes')}
                     for r in config.operations.resources.values()]}
    auth=GoogleAuth(config.google,ROOT/'secrets.yaml',allow_live=True)
    http=GoogleHTTP(config.google,auth.bearer,allow_live=True,refresh=lambda:auth.bearer(force_refresh=True))
    try:
        identity=http.read('identity','').json()
        assert identity.get('user',{}).get('emailAddress','').casefold()==config.google.expected_account
        calendar=ReadOnlyCalendarWithSimulatedWrites(config,Calendar(config.google,http))
        with tempfile.TemporaryDirectory(prefix='vert2go-readonly-dialog-') as folder:
            report.update(replay(config,calendar,folder,args.date))
        report['result']='passed'
    except EngineError as error:report['reason']=error.code
    except Exception as error:report['reason']=type(error).__name__
    finally:http.close()
    report['updated_at']=utcnow().isoformat()
    target=ROOT/'docs/evidencias'/('i5-reservation-conflict-replay-'+utcnow().strftime('%Y%m%dT%H%M%S%fZ')+'.json')
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('steps','source_sha256')},ensure_ascii=True))
    return 0 if report['result']=='passed' else 1


if __name__=='__main__':raise SystemExit(main())
