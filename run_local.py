"""Loopback-only backup resolver; credentials stay in private local files."""
import os
from pathlib import Path
import secrets

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
os.umask(0o077)
PRIVATE = ROOT / "private"
PRIVATE.mkdir(mode=0o700, exist_ok=True)
KEY = PRIVATE / "api-key"
if not KEY.exists():
    KEY.write_text(secrets.token_urlsafe(32))
KEY.chmod(0o600)
os.environ.update({
    "WXSPH_HOST": "127.0.0.1",
    "WXSPH_PORT": "8787",
    "WXSPH_API_KEYS": KEY.read_text().strip(),
    "WXSPH_CACHE_TTL": "0",
    "WXSPH_CACHE_FILE": "",
    "WXSPH_DEBUG": "false",
})

import wxsph_api as api

# Reload credentials for each request without exposing them in output or logs.
resolve = api.resolve_share_url
def resolve_with_private_cookie(url):
    path = PRIVATE / "yuanbao-cookie"
    api.COOKIES = [path.read_text().strip()] if path.exists() else []
    return resolve(url)
api.resolve_share_url = resolve_with_private_cookie
from web_local import install
install(api, ROOT, resolve_with_private_cookie)
api.main()
