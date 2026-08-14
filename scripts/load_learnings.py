#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/load_learnings.py — 从记忆服务器拉取 learnings.json 并缓存到本地（自我生长回灌端）
=================================================================================
把 growth.py 聚合出的「失败模式建议 / 评分 / 风格信号」拉回本地，供 build_storyboard 等
脚本在生成时参考（例如高频失败模式 → 提前规避）。同时打印一份人读摘要。

用法：
  # 拉取并缓存（默认连本地服务），打印摘要
  python scripts/load_learnings.py

  # 拉取后把副本写入项目目录，供 build_storyboard 读取
  python scripts/load_learnings.py --project <DIR>

  # 只读本地缓存（离线，不发网络请求）
  python scripts/load_learnings.py --no-fetch

配置：环境变量 NVP_MEMORY_URL（默认 http://127.0.0.1:8080）、NVP_API_TOKEN。
"""
import argparse
import json
import os
import sys
import urllib.request
import urllib.error

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_PATH = os.path.join(SKILL_ROOT, ".cache", "learnings.json")

DEFAULT_URL = os.environ.get("NVP_MEMORY_URL", "http://127.0.0.1:8080")
DEFAULT_TOKEN = os.environ.get("NVP_API_TOKEN", "")


def fetch_snapshot(url, token, timeout=15):
    req = urllib.request.Request(
        url.rstrip("/") + "/snapshot",
        headers={"Authorization": f"Bearer {token}" if token else ""},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read().decode("utf-8"))
        except Exception:  # noqa
            msg = {"error": str(e)}
        return e.code, msg
    except Exception as e:  # noqa
        return 0, {"error": f"network: {e}"}


def load_cache():
    if os.path.exists(CACHE_PATH):
        try:
            return json.load(open(CACHE_PATH, encoding="utf-8"))
        except Exception:  # noqa
            return None
    return None


def save_cache(data):
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def print_summary(data):
    s = data.get("stats", {})
    print("=" * 60)
    print(f"  记忆快照 @ {data.get('generated_at')}  (v{data.get('version')})")
    print("=" * 60)
    print(f"  累计运行：{s.get('runs')} 次")
    if s.get("avg_shots") is not None:
        print(f"  均值：beats={s.get('avg_beats')}  shots={s.get('avg_shots')}  "
              f"解析率={s.get('avg_resolved_refs')}/{s.get('avg_resolved_refs') and (s.get('avg_resolved_refs') + (s.get('avg_unresolved_refs') or 0))}")
    ratings = s.get("ratings", {})
    if ratings:
        print("  评分（维度: 均值/样本）：")
        for asp, v in ratings.items():
            print(f"    - {asp}: {v.get('avg')} / n={v.get('n')}")
    fps = data.get("failure_patterns", [])
    print(f"  Top 失败模式（{len(fps)}）：")
    for fp in fps[:8]:
        print(f"    [{fp['count']}×] {fp['fingerprint'][:50]}")
        print(f"        → {fp['suggestion']}")
    ss = data.get("style_signals", {})
    if ss.get("top_platforms"):
        print(f"  高频平台：{ss['top_platforms']}")
    print("=" * 60)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=DEFAULT_URL)
    ap.add_argument("--token", default=DEFAULT_TOKEN)
    ap.add_argument("--project", help="把 learnings 副本写入该目录（learnings.json）")
    ap.add_argument("--no-fetch", action="store_true", help="只读本地缓存，不发请求")
    ap.add_argument("--out", default=None, help="自定义 learnings 输出路径（默认 .cache/learnings.json 或 <project>/learnings.json）")
    a = ap.parse_args()

    data = None
    if not a.no_fetch:
        code, resp = fetch_snapshot(a.url, a.token)
        if code == 200:
            data = resp
            save_cache(data)
            print(f"[ok] 已从 {a.url}/snapshot 拉取并缓存")
        else:
            print(f"[warn] 拉取失败 HTTP {code}：{resp}（尝试本地缓存）", file=sys.stderr)
            data = load_cache()
    else:
        data = load_cache()
        print("[ok] 使用本地缓存")

    if not data:
        print("[error] 无可用 learnings 数据（先跑 growth.py 或在服务器在线时拉取）", file=sys.stderr)
        return 1

    print_summary(data)

    out_path = a.out
    if out_path is None and a.project:
        out_path = os.path.join(os.path.abspath(a.project), "learnings.json")
    if out_path:
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[ok] 已写 learnings → {out_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
