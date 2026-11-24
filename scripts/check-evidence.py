#!/usr/bin/env python3
"""Offline evidence checks; local credentials are optional, never exported."""
import argparse
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
TESTS = {'positiveAmounts', 'repeatedSettlement', 'insufficientCash',
         'lateFailureRollback', 'matchingTerms', 'missingAuthority', 'successfulSettlement'}

def require(condition, message):
    if not condition:
        raise ValueError(message)

def validate(directory, auth_file):
    j = json.loads((directory/'live-api.json').read_text())
    require(j.get('completedUtc'), 'Incomplete live run')
    require(len(j.get('checks', [])) == 99, 'Expected 99 HTTP checks for this edition')
    require(len(j.get('assertions', [])) == 48, 'Expected 48 live assertions for this edition')
    for section in ('checks', 'assertions'):
        labels = [entry['label'] for entry in j[section]]
        require(len(set(labels)) == len(labels), 'Duplicate labels in '+section)
    require(set(j['parties']) == {'issuer', 'buyer', 'seller', 'outsider'},
            'Missing or unexpected party roles')
    require(len(set(j['parties'].values())) == 4, 'Party identities must be distinct')
    for c in j['checks']:
        expected = 403 if c['label'] in {'outsider cannot query buyer', 'buyer cannot query seller'} else (
            404 if c['label'] == 'consumed proposal new command id' else (
                400 if c['label'] in {'missing buyer authority', 'insufficient cash', 'late fund mismatch'} else 200))
        require(c['passed'] is True and c['status'] == expected, 'Failed HTTP check: '+c['label'])
    for a in j['assertions']:
        require(a['passed'] is True and a['actual'] == a['expected'], 'Failed assertion: '+a['label'])
    for role, party in j['parties'].items():
        rows = [c for c in j['checks'] if c['label'] == 'verify rights '+role]
        require(len(rows) == 1 and rows[0]['response'] == {
            'rights':[{'kind':{'CanActAs':{'value':{'party':party}}}}]}, 'Unexpected rights: '+role)
    tests = (directory/'daml-test.txt').read_text()
    names = re.findall(r'Tests.daml:(\w+): ok,', tests)
    require(len(names) == 7 and set(names) == TESTS and ': failed' not in tests,
            'Missing or failing Script tests')
    secret = None
    if auth_file.exists():
        match = re.search(r'secret = "([^"]+)"', auth_file.read_text())
        require(match is not None, 'Unrecognized local auth config')
        secret = match[1]
    for p in directory.glob('*'):
        if p.is_file():
            data = p.read_text()
            require(not secret or secret not in data, 'Local key found in '+p.name)
            require(not re.search(r'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+', data),
                    'JWT-like value found in '+p.name)
    return 'checked' if secret else 'SKIPPED (no local auth config; offline review)'

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--evidence-dir', type=pathlib.Path, default=ROOT/'evidence')
    parser.add_argument('--auth-file', type=pathlib.Path, default=ROOT/'.runtime/auth.conf')
    args = parser.parse_args()
    try:
        key_check = validate(args.evidence_dir, args.auth_file)
    except (ValueError, KeyError, OSError, TypeError) as exc:
        parser.exit(1, 'FAIL: '+str(exc)+'\n')
    print('PASS: 7 Script tests; 99 HTTP checks; 48 live assertions; exact party rights; JWT scan.')
    print('Local signing-key scan: '+key_check)
