#!/usr/bin/env python3
"""Fresh workdir/ledger on this host. NOT independent clean-machine reproduction."""
import datetime
import hashlib
import json
import os
import pathlib
import platform
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
tag = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
OUT = ROOT/'evidence'/('local-review-'+tag)
WORK = ROOT/'.runtime'/('reproduction-'+tag)
OUT.mkdir(parents=True)
WORK.mkdir(parents=True)
report = {'classification':'same-machine fresh-workdir fresh-ledger rerun; NOT independent reproduction',
          'startedUtc':tag, 'os':platform.platform(), 'commands':[], 'status':'incomplete',
          'retainedHostDependencies':'Existing SDK 3.4.11, Java, Python, Assistant and user-level caches',
          'sourceSha256':{}, 'evidenceSha256':{}}
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def save(): (OUT/'run.json').write_text(json.dumps(report,indent=2)+'\n')
def command(args, filename):
    with (OUT/filename).open('w') as log:
        result=subprocess.run(args,cwd=WORK,stdout=log,stderr=subprocess.STDOUT)
    report['commands'].append({'argv':args,'exitCode':result.returncode,'output':filename})
    save()
    if result.returncode: raise RuntimeError('Command failed: '+filename)

ledger=None
try:
    for port in range(17601,17607):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',port))
    for folder in ('daml','scripts'):
        shutil.copytree(ROOT/folder,WORK/folder,ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copy2(ROOT/'daml.yaml',WORK/'daml.yaml')
    (WORK/'evidence').mkdir()
    for p in [WORK/'daml.yaml', *sorted((WORK/'daml').glob('*.daml')), *sorted((WORK/'scripts').glob('*.*'))]:
        report['sourceSha256'][str(p.relative_to(WORK))]=digest(p)
    save()
    command(['daml','version'],'versions.txt')
    command(['java','-version'],'java-version.txt')
    command([sys.executable,'--version'],'python-version.txt')
    command(['daml','build'],'build.txt')
    command(['daml','test'],'daml-test.txt')
    report['darSha256']=digest(WORK/'.daml/dist/canton-settlement-reliability-lab-0.1.0.dar')
    with (WORK/'startup.txt').open('w') as startup:
        ledger=subprocess.Popen(['bash','scripts/start-ledger.sh'],cwd=WORK,
                                stdout=startup,stderr=subprocess.STDOUT,start_new_session=True)
        deadline=time.monotonic()+180
        while 'Canton sandbox is ready.' not in (WORK/'startup.txt').read_text():
            if ledger.poll() is not None: raise RuntimeError('Ledger exited before readiness')
            if time.monotonic()>deadline: raise RuntimeError('Ledger readiness timed out')
            time.sleep(1)
        with urllib.request.urlopen('http://127.0.0.1:17606/docs/openapi',timeout=10) as response:
            schema=response.read()
        if b'version: 3.4.11' not in schema[:200]: raise RuntimeError('Unexpected API version')
        report['openapiSha256']=hashlib.sha256(schema).hexdigest()
        command([sys.executable,'scripts/live.py'],'live-run.txt')
        shutil.copy2(OUT/'daml-test.txt',WORK/'evidence/daml-test.txt')
        command([sys.executable,'scripts/check-evidence.py'],'check-evidence.txt')
        shutil.copy2(WORK/'evidence/live-api.json',OUT/'live-api.json')
    report['status']='passed'
except Exception as exc:
    report['status']='failed'
    report['failure']=str(exc)
finally:
    if ledger is not None:
        try:
            os.killpg(ledger.pid,signal.SIGINT)
            ledger.wait(timeout=20)
        except ProcessLookupError:
            pass
        except subprocess.TimeoutExpired:
            os.killpg(ledger.pid,signal.SIGTERM)
            ledger.wait(timeout=20)
        report['ledgerStopped']=ledger.poll() is not None
    # Export only a minimal startup summary; leave raw runtime logs private.
    if (WORK/'startup.txt').exists():
        lines=(WORK/'startup.txt').read_text().splitlines()
        (OUT/'startup.txt').write_text('\n'.join(x for x in lines if any(t in x for t in (
            'Daml Assistant has been deprecated','Daml Assistant will be removed','Starting Canton sandbox.',
            'Listening at port','Canton sandbox is ready.')))+'\n')
    # Redact host-specific workdir and executable paths in transcripts.
    for p in OUT.glob('*.txt'):
        p.write_text(p.read_text().replace(str(WORK),'$FRESH_WORKDIR').replace(str(pathlib.Path.home()),'$USER_HOME'))
    for p in OUT.glob('*'):
        if p.name!='run.json' and p.is_file(): report['evidenceSha256'][p.name]=digest(p)
    report['finishedUtc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
    save()
print(str(OUT.relative_to(ROOT))+': '+report['status'])
if report['status']!='passed': sys.exit(1)
