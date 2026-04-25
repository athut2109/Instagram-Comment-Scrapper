"""CLI for simple API key management (create/list/revoke)

Usage:
  python scripts/key_cli.py create --scopes admin --description "desc"
  python scripts/key_cli.py list
  python scripts/key_cli.py revoke --key-id <key_id>
"""
import argparse
from api import auth

parser = argparse.ArgumentParser()
subparsers = parser.add_subparsers(dest='cmd')

create = subparsers.add_parser('create')
create.add_argument('--scopes', default='read,write')
create.add_argument('--description', default=None)

list_p = subparsers.add_parser('list')

revoke = subparsers.add_parser('revoke')
revoke.add_argument('--key-id', required=True)

args = parser.parse_args()

if args.cmd == 'create':
    rec = auth.create_key(scopes=args.scopes, description=args.description)
    print('KEY_ID:', rec['key_id'])
    print('TOKEN  :', rec['token'])
    print('SCOPES :', rec['scopes'])

elif args.cmd == 'list':
    keys = auth.list_keys()
    for k in keys:
        print(k)

elif args.cmd == 'revoke':
    ok = auth.revoke_key(args.key_id)
    if ok:
        print('Revoked')
    else:
        print('Key not found')
else:
    parser.print_help()