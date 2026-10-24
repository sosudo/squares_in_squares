"""Read-only Gradient project, notebook and machine availability inspection.

Uses the REST routes and X-API-Key authentication documented by the official
Paperspace/gradient-cli SDK. Credentials stay in process memory; no response
tokens, credential fields, environment values or signed URLs are printed.
This tool deliberately does not allocate, start, publish or bill resources.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import stat
import urllib.error
import urllib.parse
import urllib.request


BASE = 'https://api.paperspace.io'


class ExplicitAccessDenied(RuntimeError):
    """The service reports a nonretryable access denial before authentication."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        # Never forward an API credential to an unexpected redirect destination.
        return None


def credential():
    value = os.getenv('PAPERSPACE_API_KEY')
    if value:
        return value
    path = Path(os.getenv('PAPERSPACE_TOKEN_FILE', '/tmp/squares-paperspace-auth/token'))
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise ValueError('Paperspace credential file must have mode0600')
    return path.read_text().strip()


def read_json(path, token, params=None):
    url = BASE + '/' + path.lstrip('/')
    if params:
        url += '?' + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={
        'X-API-Key': token, 'Accept': 'application/json',
        'ps_client_name': 'gradient-cli-sdk',
    })
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        # Read only known classification fields; never print arbitrary error
        # payloads, which may echo input credentials.
        try:
            payload = json.loads(exc.read())
        except (ValueError, UnicodeError):
            payload = {}
        if (payload.get('cloudflare_error') is True and payload.get('error_code') == 1010
                and payload.get('retryable') is False):
            raise ExplicitAccessDenied(
                'Paperspace Cloudflare Error1010: browser_signature_banned; '
                'owner action required, credential authentication not reached. '
                'Do not retry until service access changes.') from None
        raise RuntimeError(f'Paperspace read-only route {path} returned HTTP{exc.code}') from None
    except urllib.error.URLError as exc:
        reason = str(exc.reason)
        if 'Tunnel connection failed:' in reason:
            raise RuntimeError(f'Paperspace egress proxy rejected {BASE}') from None
        raise RuntimeError(f'Paperspace connection failed ({type(exc.reason).__name__})') from None


def machine_catalog(payload):
    rows = []
    groups = payload.values() if isinstance(payload, dict) else [payload]
    for group in groups:
        if not isinstance(group, list):
            continue
        for entry in group:
            vm = entry.get('vmType', entry)
            row = {k: vm.get(k) for k in (
                'id', 'label', 'name', 'kind', 'cpus', 'ram', 'gpuCount',
                'gpuModel', 'isPreemptible', 'deploymentType',
            ) if k in vm}
            row['available'] = entry.get('isAvailable')
            for key in ('numAvailableNodes', 'numActiveNodes', 'clusterId', 'isPreemptible'):
                if key in entry:
                    row[key] = entry[key]
            row['clusters'] = [{k: c.get(k) for k in ('id', 'name') if k in c}
                               for c in entry.get('clusters', [])]
            # Preserve only explicitly named pricing/free-tier fields for review.
            for owner, prefix in ((entry, ''), (vm, 'vm_')):
                for k, v in owner.items():
                    if any(word in k.lower() for word in ('price', 'cost', 'free', 'rate')):
                        row[prefix + k] = v
            row['entry_field_names'] = sorted(entry)
            row['vm_field_names'] = sorted(vm)
            rows.append(row)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', default='pipamsa5ztw')
    parser.add_argument('--out', type=Path, default=Path('artifacts/paperspace-status.json'))
    args = parser.parse_args()
    token = credential()
    result = {'project_id': args.project, 'read_only': True}
    failures = []
    for name, path, params in (
        ('projects', 'projects/', {'filter': json.dumps({'where': {'handle': args.project}})}),
        ('machine_catalog', 'vmTypes/getVmTypesByClusters', {'includePublicClusters': 'true'}),
        ('notebooks', 'notebooks/getNotebooks', {'filter': json.dumps({'filter': {
            'limit': 100, 'where': {'dtDeleted': None}, 'order': 'jobId desc'}})}),
    ):
        try:
            data = read_json(path, token, params)
            if name == 'projects':
                result[name] = [{k: p.get(k) for k in ('id', 'handle', 'name', 'isPublic') if k in p}
                                for p in data.get('data', [])]
            elif name == 'notebooks':
                result[name] = [{k: p.get(k) for k in (
                    'handle', 'name', 'projectId', 'projectHandle', 'state', 'isPublic',
                    'machineType', 'vmTypeLabel', 'shutdownTimeout',
                ) if k in p} for p in data.get('notebookList', [])]
                result['notebook_totals'] = {k: data.get(k) for k in (
                    'total', 'runningTotal', 'freeTierRunningTotal', 'displayTotal') if k in data}
            else:
                result[name] = machine_catalog(data)
            print(json.dumps({'route': name, 'status': 'ok', 'entries': len(result[name])}), flush=True)
        except RuntimeError as exc:
            message = str(exc)
            result[name] = {'error': message}; failures.append(name)
            print(json.dumps({'route': name, 'status': 'blocked', 'reason': message}), flush=True)
            if isinstance(exc, ExplicitAccessDenied):
                result['external_access_denied'] = True
                result['credential_authentication_tested'] = False
                break
    result['failed_reads'] = failures
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    if not failures:
        print(json.dumps({'projects': result['projects'], 'notebook_totals': result.get('notebook_totals'),
                          'available_free_labeled_machines': [p for p in result['machine_catalog']
                            if p.get('available') and 'free' in str(p).lower()]}))
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
