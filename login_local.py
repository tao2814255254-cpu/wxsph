"""User-operated official Chrome login, private validation, atomic replacement."""
import os
import secrets
import subprocess
import threading


class LoginManager:
    def __init__(self, root, api):
        self.root, self.api = root, api
        self.lock = threading.Lock()
        saved = (root / "private/yuanbao-cookie").exists()
        self.state = {"status": "idle", "message": "本机已有登录信息，下载时验证有效性。" if saved else "尚未登录，请点击重新登录元宝。"}

    def status(self):
        with self.lock:
            return dict(self.state)

    def set_state(self, status, message):
        with self.lock:
            self.state = {"status": status, "message": message}

    def start(self):
        with self.lock:
            if self.state["status"] in {"opening", "waiting", "validating"}:
                return dict(self.state)
            self.state = {"status": "opening", "message": "正在打开腾讯官方登录窗口…"}
        threading.Thread(target=self.worker, daemon=True).start()
        return self.status()

    def worker(self):
        private = self.root / "private"
        candidate = private / ("login-candidate-" + secrets.token_hex(12))
        process = None
        try:
            binary = self.root / "runtime/node"
            if not binary.exists():
                binary = self.root.__class__("/usr/local/bin/node")
            process = subprocess.Popen([str(binary), str(self.root / "login_chrome.mjs"), str(candidate)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.set_state("waiting", "请在独立Chrome窗口扫码登录腾讯元宝；完成后将自动验证保存。")
            process.wait(timeout=600)
            if not candidate.exists():
                self.set_state("cancelled", "已取消登录，原登录信息未改变。")
                return
            self.set_state("validating", "正在向腾讯验证新登录态…")
            cookie = candidate.read_text().strip()
            parsed = self.api.parse_share_url("https://weixin.qq.com/sph/AtK7D9wgqM", cookie)
            export_id, token = self.api.split_playable_url(parsed)
            feed = self.api.get_feed_info(export_id, token)
            result = self.api.normalize_response("", parsed, feed)
            if not result["data"].get("url"):
                raise ValueError("No playable video returned")
            candidate.chmod(0o600)
            os.replace(candidate, private / "yuanbao-cookie")
            self.set_state("success", "登录已更新并验证成功，可以继续下载。")
        except subprocess.TimeoutExpired:
            if process:
                process.terminate()
            self.set_state("error", "登录超时，原登录信息未改变，请重试。")
        except Exception:
            self.set_state("error", "新登录未通过验证，原登录信息未改变。请确认官方窗口已登录，或稍后重试。")
        finally:
            if candidate.exists():
                candidate.unlink()
