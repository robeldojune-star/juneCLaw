import sys
sys.path.insert(0, '.')
from core.kiwoom_client import KiwoomAPIClient
from dotenv import load_dotenv
import os, json
load_dotenv()
client = KiwoomAPIClient.from_env()
body = {'qry_tp':'1','dmst_stex_tp':'KRX'}
acct = client.post('kt00004','/api/dostk/acnt',body)
print('acct type:', type(acct))
print('acct keys:', acct.keys() if hasattr(acct, 'keys') else 'no keys')
if hasattr(acct, 'data'):
    print('data type:', type(acct.data))
    if hasattr(acct.data, 'keys'):
        print('data keys:', list(acct.data.keys()))
        for k,v in acct.data.items():
            print(f'{k}: {v}')
    else:
        print('data:', acct.data)
else:
    print('acct:', acct)