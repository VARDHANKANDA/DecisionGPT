import urllib.request
import json

req = urllib.request.Request(
    'http://127.0.0.1:8000/api/v1/auth/login',
    data=json.dumps({'email': 'researcher@decisiongpt.local', 'password': 'ResearchPass@2026!'}).encode('utf-8'),
    headers={'Content-Type': 'application/json'}
)
with urllib.request.urlopen(req) as resp:
    token = json.loads(resp.read())['access_token']

r = urllib.request.Request(
    'http://127.0.0.1:8000/api/v1/research/validation',
    headers={'Authorization': f'Bearer {token}', 'X-Research-Token': 'change-me-research-console-token'}
)
with urllib.request.urlopen(r) as resp:
    val = json.loads(resp.read())
    print('Validation State:', val.get('state'))
    print('Counts:', val.get('counts'))
    print('Total checks:', len(val.get('checks', [])))
    for check in val.get('checks', []):
        st = check.get('status')
        if st != 'passed':
            print(f"[{st.upper()}] {check}")
