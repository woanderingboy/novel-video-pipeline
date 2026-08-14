#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
memory_server/db.py — 自我生长记忆库的**共享数据库层**（单一事实源）
=========================================================================
被以下三类代码复用，保证「本地直连 SQLite 模式」与「HTTP 服务模式」schema 完全一致：
  - server.py      （HTTP 服务模式，远程 ingest / query / snapshot）
  - growth.py      （聚合 → snapshot/learnings.json + 回灌 priors）
  - scripts/collect.py / load_learnings.py  （本地免部署模式，直接读写同一 SQLite）

纯标准库（sqlite3 / json / datetime / threading），零依赖。

数据模型（SQLite，四张表）：
  productions  每次产线运行的客观指标（beats / shots / 解析率 / 时长 / 平台 …）
  feedback     人类评分（1-5，分维度：visual/story/pacing/ip_safety/overall）
  failures     失败日志（stage / error_type / fingerprint 归一化指纹）
  priors       风格先验 / 知识（key 唯一，带 weight 置信度，source 标记来源）
"""
import json
import os
import sqlite3
import threading
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
# 可用环境变量 NVP_DB_PATH 覆盖默认 SQLite 路径（便于测试 / 多项目隔离）
DEFAULT_DB = os.environ.get("NVP_DB_PATH") or os.path.join(HERE, "data", "nvp_memory.db")
SNAPSHOT_PATH = os.path.join(HERE, "snapshot", "learnings.json")


def snapshot_path():
    """learnings.json 的固定路径（growth.py 写出，load_learnings.py 读取）。"""
    return SNAPSHOT_PATH


def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_conn(db_path=DEFAULT_DB):
    """打开（必要时建库 + 建表）SQLite 连接。"""
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
# 聚合查询（HTTP /query 用）
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
