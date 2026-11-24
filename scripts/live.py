#!/usr/bin/env python3
"""Local synthetic experiment. Never logs JWTs or the HMAC signing key."""
import base64, hashlib, hmac, json, pathlib, re, time, urllib.request, urllib.error, uuid
ROOT = pathlib.Path(__file__).resolve().parents[1]
BASE = 'http://127.0.0.1:17606'
# Invalidate prior success before reading credentials or contacting the ledger.
report = {'startedUtc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'apiVersion':'3.4.11 / v2', 'checks':[]}
(ROOT/'evidence').mkdir(exist_ok=True)
(ROOT/'evidence/live-api.json').write_text(json.dumps(report,indent=2)+'\n')
if not __debug__:
    raise RuntimeError('Run without -O/PYTHONOPTIMIZE; assertions are required.')
secret = re.search(r'secret = "([^"]+)"', (ROOT/'.runtime/auth.conf').read_text())[1]
def token(party=None):
    payload = {'sub': party or 'participant_admin', 'scope': 'daml_ledger_api', 'exp': int(time.time())+60}
    enc = lambda x: base64.urlsafe_b64encode(x).rstrip(b'=')
    msg = enc(b'{"alg":"HS256","typ":"JWT"}')+b'.'+enc(json.dumps(payload).encode())
    return (msg+b'.'+enc(hmac.new(secret.encode(),msg,hashlib.sha256).digest())).decode()
def request(path, data=None, party=None, method=None, raw=False):
    headers = {'Authorization':'Bearer '+token(party), 'Content-Type':'application/octet-stream' if raw else 'application/json'}
    body = data if raw else (json.dumps(data).encode() if data is not None else None)
    req = urllib.request.Request(BASE+path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req,timeout=90) as r:
            body = r.read().decode(); return r.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        body=e.read().decode()
        try: body=json.loads(body)
        except ValueError: pass
        return e.code, body


def record(label, path, data=None, user=None, expected=200, raw=False, method=None):
    status, body = request(path,data,user,method,raw)
    entry = {'label':label,'method':method or ('POST' if data is not None else 'GET'),'path':path,
             'user':user or 'participant_admin','request':'DAR bytes omitted' if raw else data,
             'status':status,'response':body,'passed':status==expected}
    report['checks'].append(entry)
    (ROOT/'evidence/live-api.json').write_text(json.dumps(report,indent=2)+'\n')
    assert status==expected, (label,status,body)
    print(label+': HTTP '+str(status))
    return body

def tid(name): return '#canton-settlement-reliability-lab:Settlement:'+name

def main():
    suffix=uuid.uuid4().hex[:8]
    parties={}; users={}
    record('authenticated DAR upload','/v2/packages', (ROOT/'.daml/dist/canton-settlement-reliability-lab-0.1.0.dar').read_bytes(),raw=True)
    for role in ['issuer','buyer','seller','outsider']:
        parties[role]=record('allocate '+role,'/v2/parties',{'partyIdHint':role+'-'+suffix,'identityProviderId':'','synchronizerId':'','userId':''})['partyDetails']['party']
        users[role]=role+'-'+suffix
        record('restrict '+role,'/v2/users',{'user':{'id':users[role],'primaryParty':parties[role],'isDeactivated':False,'identityProviderId':''},
            'rights':[{'kind':{'CanActAs':{'value':{'party':parties[role]}}}}]})
        record('verify rights '+role,'/v2/users/'+users[role]+'/rights',user=users[role])
    report['parties']=parties; report['users']=users
    def submit(label,role,cmd,expected=200):
        return record(label,'/v2/commands/submit-and-wait-for-transaction',{'commands':{'commandId':uuid.uuid4().hex,'actAs':[parties[role]],'userId':users[role],'commands':[cmd]}},users[role],expected)
    def create(label,role,template,args):
        result=submit(label,role,{'CreateCommand':{'templateId':tid(template),'createArguments':args}})
        return result['transaction']['events'][0]['CreatedEvent']['contractId']
    def accept(label,role,p,c,expected=200):
        return submit(label,role,{'ExerciseCommand':{'templateId':tid('Proposal'),'contractId':p,'choice':'Accept','choiceArgument':{'cashId':c}}},expected)
    def filt(role):
        return {'filtersByParty':{parties[role]:{'cumulative':[{'identifierFilter':{'WildcardFilter':{'value':{'includeCreatedEventBlob':False}}}}]}}}
    def snapshot(label,role,query_role=None,expected=200):
        end=record(label+' offset','/v2/state/ledger-end',user=users[role])['offset']
        result=record(label,'/v2/state/active-contracts',{'filter':filt(query_role or role),'verbose':True,'activeAtOffset':end},users[role],expected)
        return result
    i,b,s=[parties[x] for x in ['issuer','buyer','seller']]
    c=create('issue cash','issuer','Cash',{'issuer':i,'owner':b,'currency':'USD-SYN','amount':'100.0'})
    f=create('issue fund','issuer','FundUnit',{'issuer':i,'owner':s,'fund':'FUND-SYN','units':'10.0','readers':[b]})
    terms={'issuer':i,'seller':s,'buyer':b,'fundId':f,'fund':'FUND-SYN','units':'10.0','currency':'USD-SYN','price':'100.0'}
    p=create('seller proposal','seller','Proposal',terms)
    before={role:snapshot('before '+role,role) for role in ['issuer','buyer','seller','outsider']}
    def contracts(rows):
        return {row['contractEntry']['JsActiveContract']['createdEvent']['contractId']:row['contractEntry']['JsActiveContract']['createdEvent']['createArgument'] for row in rows}
    def check(label, actual, expected):
        passed=actual==expected
        report.setdefault('assertions',[]).append({'label':label,'actual':actual,'expected':expected,'passed':passed})
        (ROOT/'evidence/live-api.json').write_text(json.dumps(report,indent=2)+'\n')
        assert passed, label
    for role,ids in [('issuer',[c,f]),('buyer',[c,f,p]),('seller',[f,p]),('outsider',[])]:
        check('before visibility '+role, sorted(contracts(before[role])), sorted(ids))
    # Seller can see the proposal, but lacks the controller's authority.
    denied=accept('missing buyer authority','seller',p,c,400)
    check('authority error code',denied['code'],'DAML_AUTHORIZATION_ERROR')
    for role in before:
        check('authority unchanged '+role,contracts(snapshot('authority after '+role,role)),contracts(before[role]))
    for label,changes,message in [('insufficient cash',{'price':'101.0'},'exact cash quantity required'),('late fund mismatch',{'fund':'WRONG-FUND'},'fund identifier mismatch')]:
        bad=create(label+' proposal','seller','Proposal',dict(terms,**changes))
        baseline={role:contracts(snapshot(label+' before '+role,role)) for role in before}
        rejected=accept(label,'buyer',bad,c,400)
        check(label+' reason',message in json.dumps(rejected),True)
        for role in before:
            check(label+' unchanged '+role,contracts(snapshot(label+' after '+role,role)),baseline[role])
        submit(label+' cleanup','seller',{'ExerciseCommand':{'templateId':tid('Proposal'),'contractId':bad,'choice':'Archive','choiceArgument':{}}})
    snapshot('outsider cannot query buyer','outsider','buyer',403)
    snapshot('buyer cannot query seller','buyer','seller',403)
    result=accept('successful settlement','buyer',p,c)
    after={role:contracts(snapshot('after '+role,role)) for role in before}
    check('after outsider empty',after['outsider'],{})
    check('after buyer count',len(after['buyer']),1)
    check('after seller count',len(after['seller']),1)
    check('after issuer union',after['issuer'],dict(after['buyer'],**after['seller']))
    check('buyer receives exact fund',list(after['buyer'].values()),[{'issuer':i,'owner':b,'fund':'FUND-SYN','units':'10.0000000000','readers':[]}])
    check('seller receives exact cash',list(after['seller'].values()),[{'issuer':i,'owner':s,'currency':'USD-SYN','amount':'100.0000000000'}])
    rejected=accept('consumed proposal new command id','buyer',p,c,404)
    check('reuse error code',rejected['code'],'CONTRACT_NOT_FOUND')
    for role in before:
        check('reuse unchanged '+role,contracts(snapshot('reuse after '+role,role)),after[role])
    offset=result['transaction']['offset']
    for role in ['buyer','seller','outsider']:
        for endpoint in ['flats','trees']:
            updates=record('settlement '+endpoint+' '+role,'/v2/updates/'+endpoint,{'beginExclusive':offset-1,'endInclusive':offset,'filter':filt(role),'verbose':True},users[role])
            if role=='outsider':
                check(endpoint+' outsider sees no settlement',updates,[])
                continue
            check(endpoint+' '+role+' single transaction',len(updates),1)
            tx=updates[0]['update']['Transaction' if endpoint=='flats' else 'TransactionTree']['value']
            check(endpoint+' '+role+' same update',tx['updateId'],result['transaction']['updateId'])
            events=[next(iter(e.values())) for e in tx['events']] if endpoint=='flats' else [next(iter(e.values()))['value'] for e in tx['eventsById'].values()]
            check(endpoint+' '+role+' consequences',sorted(e.get('choice','Create '+e['templateId'].split(':')[-1]) for e in events), sorted(['Accept','TransferCash','TransferFund','Create Cash','Create FundUnit']))
            check(endpoint+' '+role+' witnesses scoped',all(e['witnessParties']==[parties[role]] for e in events),True)
    report['completedUtc']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
    (ROOT/'evidence/live-api.json').write_text(json.dumps(report,indent=2)+'\n')
    print('All live assertions passed.')

if __name__ == '__main__': main()
