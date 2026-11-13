"""Finite, supervised I5 Telegram session using the canonical app.main runtime."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from threading import Event,Thread,Timer
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.core.contracts import EngineError
from app.integrations.private_files import private_acl,no_links
from app.main import main as bot_main,instance_lock


def state_path(root): return root/'data/i5-telegram-test-runtime.json'
def stop_path(root): return root/'data/i5-telegram-test-stop.request'


def run(root=ROOT, *, seconds=1800, runner=bot_main):
    root=Path(root); root.joinpath('data').mkdir(exist_ok=True)
    target=no_links(state_path(root)); request=no_links(stop_path(root))
    stop=Event(); run_id=str(uuid4()); started=datetime.now(timezone.utc).isoformat()
    def observe(state,code=None):
        if not target.exists():
            fd=os.open(target,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600); os.close(fd)
        private_acl(root/'config.yaml',target)
        target.write_text(json.dumps({'phase':'I5','mode':'finite_real_telegram_test','state':state,
            'code':code,'run_id':run_id,'pid':os.getpid(),'started_at':started,
            'updated_at':datetime.now(timezone.utc).isoformat(),'timeout_seconds':seconds})+'\n',encoding='utf-8')
        print(json.dumps({'telegram_i5':state,'code':code}),flush=True)
    def watch():
        while not stop.wait(.5):
            if request.exists(): stop.set()
    with instance_lock(root/'data/i5-test-supervisor'):
        if request.exists(): request.unlink()
        observer=Thread(target=watch,daemon=True); observer.start()
        timer=Timer(seconds,stop.set); timer.daemon=True; timer.start()
        try:
            code=runner(['--config',str(root/'config.yaml'),'--database',str(root/'data/i2.sqlite3'),
                '--secrets',str(root/'secrets.yaml'),'--telegram','--allow-live-telegram','--knowledge',
                '--allow-live-openai','--operations','--allow-live-google-writes'],
                stop_event=stop,lifecycle_observer=observe)
            observe('closed' if code==0 else 'failed','test_runtime_exit_'+str(code) if code else None)
            return code
        finally:
            stop.set(); timer.cancel(); observer.join(2)
            if request.exists(): request.unlink()


def request_stop(root=ROOT):
    target=state_path(root)
    if not target.exists() or json.loads(target.read_text(encoding='utf-8'))['state'] in ('closed','failed'):
        print(json.dumps({'telegram_i5':'not_running'})); return 0
    request=no_links(stop_path(root))
    request.write_text('stop\n',encoding='utf-8')
    print(json.dumps({'telegram_i5':'stop_requested'})); return 0


def main(argv=None):
    p=argparse.ArgumentParser(description='Sessão finita de testes reais Telegram I5, sem novo serviço')
    mode=p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--start',action='store_true'); mode.add_argument('--stop',action='store_true')
    p.add_argument('--seconds',type=int,default=1800)
    args=p.parse_args(argv)
    if not 60<=args.seconds<=3600: p.error('seconds deve ficar entre 60 e 3600')
    try: return request_stop() if args.stop else run(seconds=args.seconds)
    except EngineError as e:
        print(json.dumps({'telegram_i5':'blocked','reason':e.code}),flush=True); return 1


if __name__=='__main__': raise SystemExit(main())
