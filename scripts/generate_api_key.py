"""Generate an API key and insert it into the PoC DB.

Usage (local):
  python scripts/generate_api_key.py --scopes "admin" --description "bootstrap admin key"

The script prints the plaintext token (store it safely) and a suggested setx / export command.
"""
import argparse
from api import auth

parser = argparse.ArgumentParser()
parser.add_argument('--scopes', default='read,write', help='Comma-separated scopes (e.g., admin,read)')
parser.add_argument('--description', default=None)
args = parser.parse_args()

rec = auth.create_key(scopes=args.scopes, description=args.description)
print('Created API key:')
print('key_id:', rec['key_id'])
print('token:', rec['token'])
print('\nStore this token safely — it will not be shown again.')
print('\nSuggested env (PowerShell):')
print(f"$env:POC_API_KEY = '{rec['token']}'")
print('\nSuggested env (Windows cmd):')
print(f"setx POC_API_KEY \"{rec['token']}\"")
print('\nSuggested env (bash):')
print(f"export POC_API_KEY='{rec['token']}'")