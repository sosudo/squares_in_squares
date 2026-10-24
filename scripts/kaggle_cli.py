"""Run the official CLI using runtime authentication or a protected token file.

Usage: .venv/bin/python scripts/kaggle_cli.py competitions list -s squares-in-squares
Set KAGGLE_API_TOKEN, or KAGGLE_TOKEN_FILE to a mode-0600 token file.
The onboarding session's temporary token file is supported outside the checkout.
"""
import os
from pathlib import Path
import stat
import sys


def main():
    runtime = dict(os.environ)
    token_path = Path(runtime.get('KAGGLE_TOKEN_FILE', '/tmp/squares-kaggle-auth/token'))
    if not runtime.get('KAGGLE_API_TOKEN') and token_path.exists():
        if stat.S_IMODE(token_path.stat().st_mode) & 0o077:
            raise SystemExit('Token file must be private (chmod 600).')
        runtime['KAGGLE_API_TOKEN'] = token_path.read_text().strip()
    runtime.setdefault('KAGGLE_CONFIG_DIR', '/tmp/squares-kaggle-auth')
    os.environ.update(runtime)
    # Kaggle serves the same authenticated v1 RPCs at this compatibility URL.
    # Confirmed with token introspection and quota calls; avoids requiring the
    # separate API hostname for metadata operations. Keep the SDK pinned.
    # Set KAGGLE_USE_WWW_API=0 to use the SDK's standard api.kaggle.com route.
    if runtime.get('KAGGLE_USE_WWW_API', '1') == '1':
        import kagglesdk.kaggle_env as kaggle_env
        kaggle_env._env_to_endpoint[kaggle_env.KaggleEnv.PROD] = 'https://www.kaggle.com/api'
    from kaggle.cli import main as cli_main
    import requests
    from urllib.parse import urlsplit
    try:
        cli_main()
    except requests.RequestException as exc:
        # Download errors can contain signed URLs. Report only destination and
        # status, never a traceback with URL query strings or credentials.
        req = getattr(exc, 'request', None)
        resp = getattr(exc, 'response', None)
        host = urlsplit(req.url).hostname if req is not None else 'unknown'
        status = resp.status_code if resp is not None else 'connection failed'
        raise SystemExit(f'Kaggle request failed: {type(exc).__name__}; host={host}; status={status}')


if __name__ == '__main__':
    main()
