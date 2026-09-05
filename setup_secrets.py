"""
One-time setup script: creates the Databricks secret scope and stores the
Massive API key. Run this locally (with the Databricks CLI configured) or
from a notebook - never commit the resulting secret value anywhere.

Usage:
    python setup_secrets.py
"""
from databricks.sdk import WorkspaceClient
from databricks.sdk.service import workspace
import getpass

w = WorkspaceClient()

if not any(scope.name == 'alpaca' for scope in w.secrets.list_scopes()):
    w.secrets.create_scope(scope='alpaca')
    print('Scope `alpaca` successfully created.')
else:
    print("Scope `alpaca` already exists.")    

w.secrets.put_secret(
    scope='alpaca',
    key='alpaca-api',
    string_value=getpass.getpass("Paste your Alpaca API key: ")
)

w.secrets.put_secret(
    scope='alpaca',
    key='alpaca-secret',
    string_value=getpass.getpass("Paste your Alpaca Secret: ")
)

w.secrets.put_acl(
    scope="alpaca",
    principal="users",
    permission=workspace.AclPermission.READ,
)
    

if not any(scope.name == 'massive' for scope in w.secrets.list_scopes()):
    w.secrets.create_scope(scope='massive')
    print('Scope `massive` successfully created.')
else:
    print("Scope `massive` already exists.")    

w.secrets.put_secret(
    scope='massive',
    key='api-key',
    string_value=getpass.getpass("Paste your Massive API key: ")
)

w.secrets.put_acl(
    scope='massive',
    principal='users',
    permission=workspace.AclPermission.READ,
)


if not any(scope.name == 'database' for scope in w.secrets.list_scopes()):
    w.secrets.create_scope(scope='database')
    print('Scope `database` successfully created.')
else:
    print("Scope `database` already exists.")    

w.secrets.put_secret(
    scope='database',
    key='lakebase-url',
    string_value=getpass.getpass("Paste your Lakebase URL: ")
)

w.secrets.put_acl(
    scope='database',
    principal='users',
    permission=workspace.AclPermission.READ,
)