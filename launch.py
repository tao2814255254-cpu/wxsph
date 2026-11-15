"""Start the isolated service once, then open its web page."""
import fcntl
import json
from pathlib import Path
import subprocess
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent
(ROOT / "private").mkdir(mode=0o700, exist_ok=True)
URL = "http://127.0.0.1:8787"
def ready():
    try:
        with urlopen(URL + "/health", timeout=1) as response:
            return json.load(response).get("app") == "wxsph-backup-web"
    except Exception:
        return False

with (ROOT / "private/launcher.lock").open("w") as lock:
    fcntl.flock(lock, fcntl.LOCK_EX)
    if not ready():
        with (ROOT / "service.log").open("ab") as log:
            process = subprocess.Popen(["/usr/bin/python3", str(ROOT / "run_local.py")], cwd=ROOT, stdout=log, stderr=log, start_new_session=True)
        for _ in range(50):
            if ready():
                break
            if process.poll() is not None:
                raise RuntimeError("备用服务启动失败，端口可能被占用。")
            time.sleep(.1)
        else:
            raise RuntimeError("备用服务启动超时。")
subprocess.run(["/usr/bin/open", URL], check=True)
