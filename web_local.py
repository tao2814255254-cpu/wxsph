"""Same-origin local UI; no credentials are sent to the browser."""
import json
import re
import secrets
import subprocess
import threading
import time
from urllib.parse import urlparse
from urllib.request import Request, urlopen


def install(api, root, resolve):
    token = secrets.token_urlsafe(32)
    downloads = root / "downloads"
    downloads.mkdir(exist_ok=True)
    lock = threading.Lock()
    original = api.Handler

    class Handler(original):
        def end_headers(self):
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            super(original, self).end_headers()

        def valid_host(self):
            return self.headers.get("Host") in {"127.0.0.1:8787", "localhost:8787"}

        def do_GET(self):
            if not self.valid_host():
                self.send_error(403)
                return
            if self.path == "/":
                body = (root / "index.html").read_text().replace("__TOKEN__", token).encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif self.path == "/health":
                self.send_json(200, {"ok": True, "app": "wxsph-backup-web", "version": 1})
            else:
                super().do_GET()

        def do_POST(self):
            if self.path not in {"/web/download", "/web/open-folder"}:
                return super().do_POST()
            if (not self.valid_host() or self.headers.get("Origin") not in
                    {"http://127.0.0.1:8787", "http://localhost:8787"} or
                    not secrets.compare_digest(self.headers.get("X-Local-Token", ""), token)):
                self.send_json(403, {"error": "请求未授权，请刷新本机页面。"})
                return
            if self.path == "/web/open-folder":
                subprocess.run(["/usr/bin/open", str(downloads)], check=True)
                self.send_json(200, {"ok": True})
                return
            if not lock.acquire(blocking=False):
                self.send_json(409, {"error": "已有下载任务，请等待完成。"})
                return
            part = None
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 8192:
                    raise ValueError("链接内容过长或为空。")
                body = json.loads(self.rfile.read(length))
                share = api.extract_url(body.get("url", ""))
                data = resolve(share)["data"]
                url = data.get("url", "")
                host = urlparse(url).hostname or ""
                if urlparse(url).scheme != "https" or not (host.endswith(".qq.com") or host.endswith(".qpic.cn")):
                    raise ValueError("解析结果不是受支持的腾讯媒体地址。")
                title = re.sub(r'[\x00-\x1f/\\:*?"<>|]', "_", data.get("title") or "视频号")[:80].strip(". ") or "视频号"
                output = downloads / (title + "-" + time.strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(2) + ".mp4")
                part = output.with_suffix(".part")
                with urlopen(Request(url, headers={"User-Agent": api.UA}), timeout=45) as response, part.open("wb") as dest:
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        dest.write(chunk)
                with part.open("rb") as source:
                    header = source.read(12)
                if header[4:8] != b"ftyp":
                    raise ValueError("此视频需要额外解密，备用服务暂不支持，未保存为成功视频。")
                part.rename(output)
                self.send_json(200, {"ok": True, "path": str(output), "bytes": output.stat().st_size})
            except api.ApiError as exc:
                message = "解析失败，元宝登录态可能已失效，或该链接暂不支持。"
                self.send_json(exc.status, {"error": message})
            except Exception:
                self.send_json(400, {"error": "下载失败，请检查分享链接和网络；加密视频可能暂不支持。"})
            finally:
                if part and part.exists():
                    part.unlink()
                lock.release()

    api.Handler = Handler
