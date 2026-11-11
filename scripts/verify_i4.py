"""Current offline verification. Never reads real secrets or opens operational databases."""
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import io
import json
import logging
from pathlib import Path
import platform
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.verify_i1 import BASELINE, EvidenceResult


def main():
    folder = ROOT/'docs/evidencias'
    stream = io.StringIO()
    logger = logging.getLogger()
    handlers, level = logger.handlers[:], logger.level
    logger.handlers = [logging.StreamHandler(stream)]
    logger.setLevel(logging.INFO)
    try:
        suite = unittest.defaultTestLoader.discover(str(ROOT/'tests'),top_level_dir=str(ROOT))
        with patch('socket.socket.connect',side_effect=AssertionError('Offline I4: network forbidden')), \
             patch('socket.socket.connect_ex',side_effect=AssertionError('Offline I4: network forbidden')), \
             redirect_stderr(stream), redirect_stdout(stream):
            result = unittest.TextTestRunner(stream=stream,verbosity=2,resultclass=EvidenceResult).run(suite)
    finally:
        logger.handlers, logger.level = handlers, level
    (folder/'i4-unittest.txt').write_text(stream.getvalue(),encoding='utf-8')
    checks = []
    with tempfile.TemporaryDirectory(prefix='vert2go-i4-verify-') as temporary:
        for name in ('config.example.yaml','config.telegram.example.yaml','config.google.example.yaml','config.knowledge.example.yaml'):
            process = subprocess.run([sys.executable,'-B','-m','app.main','--config',name,'--database',str(Path(temporary)/(name+'.sqlite3'))],
                                     cwd=ROOT,capture_output=True,text=True,timeout=30)
            checks.append({'config':name,'exit_code':process.returncode})
    demos = {}
    for name in ('i1','i2','i4'):
        process = subprocess.run([sys.executable,'-B','-m','examples.'+name+'_demo'],cwd=ROOT,capture_output=True,text=True,timeout=30)
        demos[name] = process.returncode
    protected = {name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest().upper() == expected
                 for name,expected in BASELINE.items() if name != 'README.md'}
    good = result.wasSuccessful() and all(protected.values()) and all(c['exit_code'] == 0 for c in checks) and all(v == 0 for v in demos.values())
    report = {'phase':'I4','scope':'local_offline','updated_at':datetime.now(timezone.utc).isoformat(),
              'python':platform.python_version(),'sqlite':sqlite3.sqlite_version,
              'dependencies':{p:version(p) for p in ('PyYAML','tzdata','google-auth','google-auth-oauthlib','requests')},
              'tests_run':result.testsRun,'passed':len(result.passed),'failed':len(result.failures),'errors':len(result.errors),
              'skipped':len(result.skipped),'successful':good,'passed_test_ids':result.passed,
              'failure_test_ids':[t.id() for t,_ in result.failures],'error_test_ids':[t.id() for t,_ in result.errors],
              'i4_test_count':sum('.test_knowledge.' in t for t in result.passed),
              'protected_sources_unchanged':protected,'local_startup_checks':checks,'demo_exit_codes':demos,
              'real_secrets_read':False,'operational_database_opened':False,'external_api_attempted':False,
              'google_mutations_attempted':False,'openai_live':'not_run_by_offline_verifier',
              'source_sha256':{str(p.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest()
                               for directory in ('app','scripts','tests') for p in sorted((ROOT/directory).rglob('*'))
                               if p.suffix in ('.py','.sql')}}
    (folder/'i4-tests.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('tests_run','passed','failed','errors','skipped','successful')}))
    return 0 if good else 1


if __name__ == '__main__':
    raise SystemExit(main())
