"""I5 preflight: existing Google destinations, read-only, redacted evidence."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.config.schema import load_config,load_enrollment_secrets
from app.core.contracts import EngineError,digest,stamp
from app.integrations.google_auth import GoogleAuth
from app.integrations.google_http import GoogleHTTP
from app.integrations.calendar import Calendar
from app.integrations.sheets import Sheets


def main():
    report={'phase':'I5','scope':'existing_google_resources_read_only','updated_at':stamp(datetime.now(timezone.utc)),
            'google_mutations_attempted':False,'openai_used':False,'git_operations':False,'result':'blocked'}
    http=None
    try:
        c=load_config(ROOT/'config.yaml'); g=c.google
        token=load_enrollment_secrets(ROOT/'secrets.yaml')['google_oauth']['token']
        report['write_scopes_registered']=g.write_access
        report['registered_scope_count']=len(token['scopes'])
        auth=GoogleAuth(g,ROOT/'secrets.yaml',allow_live=True)
        http=GoogleHTTP(g,auth.bearer,allow_live=True,refresh=lambda:auth.bearer(force_refresh=True))
        identity=http.read('identity','').json()
        if identity.get('user',{}).get('emailAddress','').casefold()!=g.expected_account:
            raise EngineError('google_account_mismatch')
        report['account_verified']=True
        events=Calendar(g,http).read_events(g.calendar_id,g.window_start,g.window_end)
        report['calendar']={'result':'passed','resource_ref':digest(g.calendar_id),
                            'event_count':len(events['events']),'complete':events['complete']}
        sheets=Sheets(g,http); sheets.read_metadata(g.spreadsheet_id)
        report['sheets']=[]
        for target in g.ranges:
            rows=sheets.read_range(g.spreadsheet_id,target)
            report['sheets'].append({'result':'passed','resource_ref':digest(g.spreadsheet_id),'range_ref':digest(target),
                'row_count':len(rows),'cell_count':sum(map(len,rows)),'empty':not any(any(v!='' for v in row) for row in rows)})
        report['result']='passed'
        if not g.write_access: report['remaining_gate']='Google OAuth write consent and candidate promotion'
    except EngineError as e: report['reason']=e.code
    except Exception: report['reason']='i5_preflight_local_error'
    finally:
        if http: report['calls']=http.calls; http.close()
    target=ROOT/'docs/evidencias/i5-live-preflight.json'
    if target.exists(): target=target.with_name('i5-live-preflight-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json')
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='calls'},ensure_ascii=True),flush=True)
    return 0 if report['result']=='passed' else 1


if __name__=='__main__': raise SystemExit(main())
