#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
memory_server/server.py — novel-video-pipeline 自我生长记忆服务器（零依赖）
=================================================================================
一个纯标准库实现的轻量 HTTP 服务，让 skill 在每次产线运行后把「运行产物 / 人类评分 /
失败日志 / 风格先验」回灌进 SQLite，经 growth.py 聚合成 learnings.json 后再回灌 skill，
形成「采集 → 聚合 → 回灌」的数据闭环，使 skill 随使用自我生长。

设计约束（与 skill 其余脚本一致）：
  - 纯标准库，无需 pip install（sqlite3 / http.server / json / threading 等）。
  - 单文件可独立运行：python memory_server/server.py [--host 0.0.0.0] [--port 8080] [--db data/nvp_memory.db] [--no-auth]
  - 公网部署时由 Caddy 反向代理做 TLS（见 memory_server/README.md），本服务只跑 HTTP。

数据库层见同目录 db.py（server.py / growth.py / scripts/collect.py 共用，保证 schema 一致）。

HTTP 端点：
  GET  /health    健康检查（无需鉴权）
  POST /ingest    批量写入事件；body: {"events":[{type, ...}]}
  GET  /query?type=...&group=...  聚合查询（失败模式 / 评分均值 / 先验）
  GET  /snapshot  返回最新 snapshot/learnings.json（若已生成）
  GET  /export    导出全量数据为 JSON（便于离线镜像 / 备份）

鉴权：Authorization: Bearer <NVP_API_TOKEN>（环境变量或 --token）；--no-auth 跳过（仅本地测试）。
限速：每 IP 默认 120 次/分钟，超出返回 429。

注意：若你只想在**单机**使用自我生长（不部署公网），其实不需要起这个服务——
scripts/collect.py / load_learnings.py 在未设置 NVP_MEMORY_URL 时会自动改为直连本地 SQLite。
本服务仅在「多机汇总 / 多人协作 / 远程回灌」时才需要。见 README「0. 单机免部署」。
"""
import argparse
import json
import os
import sys
import time
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from db import (
    get_conn, insert_event, query_aggregates, export_all,
    snapshot_path, DEFAULT_DB, HERE,
)

# ---------------------------------------------------------------------------
# 限速
# ---------------------------------------------------------------------------

class RateLimiter:
    def __init__(self, max_per_min=120):
        self.max = max_per_min
        self.hits = {}  # ip -> list[ts]
        self.lock = threading.Lock()

    def allow(self, ip):
        now = time.time()
        with self.lock:
            lst = self.hits.get(ip, [])
            lst = [t for t in lst if now - t < 60]
            if len(lst) >= self.max:
                self.hits[ip] = lst
                return False
            lst.append(now)
            self.hits[ip] = lst
            return True


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "NVP-MemoryServer/1.0"

    # 由 Server 实例注入：db_path, token, no_auth, limiter
    def _auth_ok(self):
        srv = self.server
        if srv.no_auth:
            return True
        if not srv.token:
            # 未配置 token 且非 no_auth：拒绝，避免误开公网裸服务
            return False
        auth = self.headers.get("Authorization", "")
        return auth == f"Bearer {srv.token}"

    def _client_ip(self):
        fwd = self.headers.get("X-Forwarded-For", "")
        if fwd:
            return fwd.split(",")[0].strip()
        return self.client_address[0]

    def _send_json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
        except ValueError:
            length = 0
        if length <= 0:
            return b""
        return self.rfile.read(length)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path == "/health":
            self._send_json(200, {"status": "ok", "ts": _now_iso()})
            return

        # 以下端点需要鉴权 + 限速
        ip = self._client_ip()
        if not self.server.limiter.allow(ip):
            self._send_json(429, {"error": "rate limited"})
            return
        if not self._auth_ok():
            self._send_json(401, {"error": "unauthorized"})
            return

        conn = get_conn(self.server.db_path)
        try:
            if path == "/query":
                qtype = (qs.get("type") or ["failures"])[0]
                self._send_json(200, {"type": qtype, "data": query_aggregates(conn, qtype)})
            elif path == "/snapshot":
                snap_path = snapshot_path()
                if os.path.exists(snap_path):
                    with open(snap_path, encoding="utf-8") as f:
                        self._send_json(200, json.load(f))
                else:
                    self._send_json(404, {"error": "snapshot not generated; run growth.py"})
            elif path == "/export":
                self._send_json(200, export_all(conn))
            else:
                self._send_json(404, {"error": "not found"})
        finally:
            conn.close()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/health":
            self._send_json(200, {"status": "ok", "ts": _now_iso()})
            return

        ip = self._client_ip()
        if not self.server.limiter.allow(ip):
            self._send_json(429, {"error": "rate limited"})
            return
        if not self._auth_ok():
            self._send_json(401, {"error": "unauthorized"})
            return

        if path != "/ingest":
            self._send_json(404, {"error": "not found"})
            return

        body = self._read_body()
        try:
            payload = json.loads(body.decode("utf-8"))
        except Exception as e:  # noqa
            self._send_json(400, {"error": f"invalid json: {e}"})
            return

        events = payload.get("events")
        if not isinstance(events, list):
            self._send_json(400, {"error": "body must be {\"events\": [...]}"})
            return

        conn = get_conn(self.server.db_path)
        ok, fail = 0, 0
        failures = []
        try:
            conn.execute("BEGIN")
            for ev in events:
                good, reason = insert_event(conn, ev)
                if good:
                    ok += 1
                else:
                    fail += 1
                    failures.append(reason)
            conn.commit()
        except Exception as e:  # noqa
            conn.rollback()
            self._send_json(500, {"error": f"db error: {e}"})
            conn.close()
            return
        finally:
            if conn:
                conn.close()

        self._send_json(200, {"accepted": ok, "rejected": fail, "reasons": failures})

    # 静默默认日志，避免刷屏（需要时可在部署时打开）
    def log_message(self, fmt, *args):  # noqa
        pass


class Server(ThreadingHTTPServer):
    def __init__(self, bind, db_path, token, no_auth, limiter):
        super().__init__(bind, Handler)
        self.db_path = db_path
        self.token = token
        self.no_auth = no_auth
        self.limiter = limiter


# _now_iso 来自 db 模块（与 insert_event 同命名空间），Handler 用到，做个别名
from db import _now_iso  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="NVP self-growth memory server (zero-dep)")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--db", default=DEFAULT_DB, help="SQLite 路径")
    ap.add_argument("--token", default=None, help="Bearer token（覆盖环境变量 NVP_API_TOKEN）")
    ap.add_argument("--no-auth", action="store_true", help="关闭鉴权（仅本地测试）")
    ap.add_argument("--rate", type=int, default=120, help="每 IP 每分钟最大请求数")
    a = ap.parse_args()

    token = a.token or os.environ.get("NVP_API_TOKEN") or ""
    if not token and not a.no_auth:
        print("[warn] 未设置 NVP_API_TOKEN 且未启用 --no-auth：公网部署将拒绝所有请求（安全默认）。", file=sys.stderr)

    limiter = RateLimiter(max_per_min=a.rate)
    srv = Server((a.host, a.port), a.db, token, a.no_auth, limiter)
    print(f"[ok] NVP 记忆服务已启动 → http://{a.host}:{a.port}  (db={a.db}, auth={'off' if a.no_auth else 'bearer'})")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n[stop] 服务已停止")
        srv.shutdown()


if __name__ == "__main__":
    main()
