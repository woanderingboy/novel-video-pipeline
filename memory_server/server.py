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

数据模型（SQLite，四张表）：
  productions  每次产线运行的客观指标（beats / shots / 解析率 / 时长 / 平台 …）
  feedback     人类评分（1-5，分维度：visual/story/pacing/ip_safety/overall）
  failures     失败日志（stage / error_type / fingerprint 归一化指纹）
  priors       风格先验 / 知识（key 唯一，带 weight 置信度，source 标记来源）

HTTP 端点：
  GET  /health    健康检查（无需鉴权）
  POST /ingest    批量写入事件；body: {"events":[{type, ...}]}
  GET  /query?type=...&group=...  聚合查询（失败模式 / 评分均值 / 先验）
  GET  /snapshot  返回最新 snapshot/learnings.json（若已生成）
  GET  /export    导出全量数据为 JSON（便于离线镜像 / 备份）

鉴权：Authorization: Bearer <NVP_API_TOKEN>（环境变量或 --token）；--no-auth 跳过（仅本地测试）。
限速：每 IP 默认 120 次/分钟，超出返回 429。
"""
import argparse
import json
import os
import sqlite3
import sys
import time
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB = os.path.join(HERE, "data", "nvp_memory.db")

# ---------------------------------------------------------------------------
# 数据库层
# ---------------------------------------------------------------------------

def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_conn(db_path):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _init_schema(conn)
    return conn


def _init_schema(conn):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS productions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            run_id TEXT,
            project TEXT,
            platform TEXT,
            beats INTEGER,
            shots INTEGER,
            resolved_refs INTEGER,
            unresolved_refs INTEGER,
            duration_sec REAL,
            model_notes TEXT,
            raw TEXT
        );

        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            run_id TEXT,
            rating INTEGER,
            aspect TEXT,
            comment TEXT
        );

        CREATE TABLE IF NOT EXISTS failures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            run_id TEXT,
            stage TEXT,
            error_type TEXT,
            message TEXT,
            fingerprint TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_fail_fp ON failures(fingerprint);

        CREATE TABLE IF NOT EXISTS priors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE NOT NULL,
            value TEXT,
            weight REAL DEFAULT 1.0,
            source TEXT,
            updated_at TEXT
        );
        """
    )
    conn.commit()


# ---------------------------------------------------------------------------
# 事件写入
# ---------------------------------------------------------------------------

def insert_event(conn, ev):
    """根据 ev['type'] 写入对应表。返回 (ok, reason)。"""
    t = (ev or {}).get("type")
    ts = ev.get("ts") or _now_iso()
    if t == "production":
        conn.execute(
            """INSERT INTO productions
               (ts, run_id, project, platform, beats, shots, resolved_refs,
                unresolved_refs, duration_sec, model_notes, raw)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                ts, ev.get("run_id"), ev.get("project"), ev.get("platform"),
                ev.get("beats"), ev.get("shots"), ev.get("resolved_refs"),
                ev.get("unresolved_refs"), ev.get("duration_sec"),
                json.dumps(ev.get("model_notes"), ensure_ascii=False)
                if ev.get("model_notes") is not None else None,
                json.dumps(ev, ensure_ascii=False),
            ),
        )
        return True, "production"
    if t == "feedback":
        conn.execute(
            """INSERT INTO feedback (ts, run_id, rating, aspect, comment)
               VALUES (?,?,?,?,?)""",
            (ts, ev.get("run_id"), ev.get("rating"), ev.get("aspect"), ev.get("comment")),
        )
        return True, "feedback"
    if t == "failure":
        conn.execute(
            """INSERT INTO failures (ts, run_id, stage, error_type, message, fingerprint)
               VALUES (?,?,?,?,?,?)""",
            (
                ts, ev.get("run_id"), ev.get("stage"), ev.get("error_type"),
                ev.get("message"), ev.get("fingerprint") or _fingerprint(ev),
            ),
        )
        return True, "failure"
    if t == "prior":
        conn.execute(
            """INSERT INTO priors (key, value, weight, source, updated_at)
               VALUES (?,?,?,?,?)
               ON CONFLICT(key) DO UPDATE SET
                 value=excluded.value, weight=excluded.weight,
                 source=excluded.source, updated_at=excluded.updated_at""",
            (
                ev.get("key"), json.dumps(ev.get("value"), ensure_ascii=False)
                if ev.get("value") is not None else None,
                ev.get("weight", 1.0), ev.get("source", "human"), _now_iso(),
            ),
        )
        return True, "prior"
    return False, f"unknown type: {t!r}"


def _fingerprint(ev):
    """失败事件的归一化指纹（用于聚类）。"""
    parts = [str(ev.get("stage") or "?"), str(ev.get("error_type") or "?")]
    msg = ev.get("message") or ""
    # 把数字 / id 归一，避免同一类错误因具体数值不同而分散
    norm = "".join(ch if not ch.isdigit() else "#" for ch in msg)
    norm = norm[:120]
    return "|".join(parts) + "::" + norm


# ---------------------------------------------------------------------------
# 聚合查询
# ---------------------------------------------------------------------------

def query_aggregates(conn, qtype, group=None):
    if qtype == "failures":
        rows = conn.execute(
            """SELECT fingerprint, COUNT(*) AS c,
                      GROUP_CONCAT(DISTINCT stage) AS stages,
                      GROUP_CONCAT(DISTINCT error_type) AS etypes
               FROM failures GROUP BY fingerprint ORDER BY c DESC LIMIT 50"""
        ).fetchall()
        return [
            {
                "fingerprint": r["fingerprint"],
                "count": r["c"],
                "stages": (r["stages"] or "").split(","),
                "error_types": (r["etypes"] or "").split(","),
            }
            for r in rows
        ]
    if qtype == "feedback":
        rows = conn.execute(
            """SELECT aspect, AVG(rating) AS avg, COUNT(*) AS n
               FROM feedback GROUP BY aspect ORDER BY n DESC"""
        ).fetchall()
        return [{"aspect": r["aspect"], "avg": round(r["avg"], 2), "n": r["n"]} for r in rows]
    if qtype == "productions":
        row = conn.execute(
            """SELECT COUNT(*) AS n, AVG(beats) AS ab, AVG(shots) AS as_,
                      AVG(resolved_refs) AS ar, AVG(unresolved_refs) AS au,
                      AVG(duration_sec) AS ad
               FROM productions"""
        ).fetchone()
        return {
            "runs": row["n"],
            "avg_beats": round(row["ab"], 2) if row["ab"] is not None else None,
            "avg_shots": round(row["as_"], 2) if row["as_"] is not None else None,
            "avg_resolved_refs": round(row["ar"], 2) if row["ar"] is not None else None,
            "avg_unresolved_refs": round(row["au"], 2) if row["au"] is not None else None,
            "avg_duration_sec": round(row["ad"], 2) if row["ad"] is not None else None,
        }
    if qtype == "priors":
        rows = conn.execute(
            "SELECT key, value, weight, source, updated_at FROM priors ORDER BY weight DESC, updated_at DESC"
        ).fetchall()
        return [
            {
                "key": r["key"], "value": _maybe_json(r["value"]),
                "weight": r["weight"], "source": r["source"], "updated_at": r["updated_at"],
            }
            for r in rows
        ]
    return []


def _maybe_json(s):
    if s is None:
        return None
    try:
        return json.loads(s)
    except Exception:  # noqa
        return s


def export_all(conn):
    out = {"exported_at": _now_iso()}
    for name in ("productions", "feedback", "failures", "priors"):
        rows = conn.execute(f"SELECT * FROM {name} ORDER BY id").fetchall()
        out[name] = [dict(r) for r in rows]
    return out


# ---------------------------------------------------------------------------
# HTTP 处理
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
                snap_path = os.path.join(HERE, "snapshot", "learnings.json")
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
