import json
import urllib.request
import sys

if len(sys.argv) < 2:
    print('Usage: python scripts/post_run_scan.py <scan_id> [--mock]')
    sys.exit(1)

scan_id = sys.argv[1]
mock = '--mock' in sys.argv
url = f'http://127.0.0.1:8000/scans/{scan_id}/run'
if mock:
    url += '?mock=true'

req = urllib.request.Request(url, data=b'', method='POST')
with urllib.request.urlopen(req) as resp:
    print(resp.read().decode())
