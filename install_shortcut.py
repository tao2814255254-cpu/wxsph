"""Recreate a desktop shortcut after moving/restoring this source directory."""
from pathlib import Path
import shlex
import subprocess

root = Path(__file__).resolve().parent
command = "/usr/bin/python3 " + shlex.quote(str(root / "launch.py"))
escaped = command.replace("\\", "\\\\").replace('"', '\\"')
source = 'try\n do shell script "' + escaped + '"\non error messageText\n display dialog messageText buttons {"好"} default button 1 with title "视频号备用下载"\nend try\n'
destination = Path.home() / "Desktop" / "视频号备用下载.app"
if destination.exists():
    raise SystemExit("桌面入口已存在，未覆盖。确认旧入口不再需要后再移走它。")
subprocess.run(["/usr/bin/osacompile", "-o", str(destination), "-"], input=source, text=True, check=True)
print("桌面备用下载入口已创建。")
