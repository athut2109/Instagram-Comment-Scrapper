import json
import urllib.request

url = 'http://127.0.0.1:8000/scans'
data = json.dumps({"post_url": "https://www.instagram.com/p/DEF456/", "mode": "keyword"}).encode('utf-8')
req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
with urllib.request.urlopen(req) as resp:
    print(resp.read().decode())
