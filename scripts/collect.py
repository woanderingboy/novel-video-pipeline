#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/collect.py — 把一次产线运行的产物回灌进记忆服务器（自我生长采集端）
=================================================================================
在 pipeline 跑完后调用，自动从项目目录读取客观指标，组装 events 并 POST 到记忆服务。
也支持手工追加人类评分（--feedback）与失败日志（--failures），以及离线镜像（--mirror）。

自动采集的客观指标（production 事件）：
  - beats    : 来自 script.json 的 beat 数
  - shots    : 来自 storyboard.json 的 shot 数
  - resolved_refs / unresolved_refs : 来自 storyboard.resolved.json 的 _ref_resolution
  - duration_sec : 来自 platform-presets.json 的单镜头时长 × shots
  - platform / project : 来自 --platform / --project 的目录名推断

用法：
  # 自动采集并回灌（默认连本地服务）
  python scripts/collect.py --project <DIR> --platform bilibili

  # 追加人类评分
  python scripts/collect.py --project <DIR> --feedback 5 overall "节奏很爽"

  # 追加失败日志（从文件，JSON 数组或 {"stage","error_type","message"}）
  python scripts/collect.py --project <DIR> --failures fails.json

  # 只生成镜像不发送（便于离线机稍后 --sync）
  python scripts/collect.py --project <DIR> --mirror ./mirror.json --dry-run

  # 把镜像文件同步到服务器
  python scripts/collect.py --sync ./mirror.json

配置：环境变量 NVP_MEMORY_URL（默认 http://127.0.0.1:8080）、NVP_API_TOKEN。
"""
import argparse
import json
import os
import sys
import urllib.request
import urllib.error

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULT_URL = os.environ.get("NVP_MEMORY_URL", "http://127.0.0.1:8080")
DEFAULT_TOKEN = os.environ.get("NVP_API_TOKEN", "")


def _load(p):
    if not os.path.exists(p):
        return None
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception as e:  # noqa
        print(f"[warn] 解析失败 {p}: {e}", file=sys.stderr)
        return None


def make_run_id():
    from datetime import datetime
    import random
    return "run_" + datetime.now().strftime("%Y%m%d%H%M%S") + "_" + f"{random.randint(0, 9999):04d}"


def build_production_event(project_dir, platform, run_id):
    p = os.path.abspath(project_dir)
    script = _load(os.path.join(p, "script.json")) or {}
    story = _load(os.path.join(p, "storyboard.json")) or {}
    resolved = _load(os.path.join(p, "storyboard.resolved.json")) or {}

    beats = len(script.get("beats", []) or [])
    shots = len(story.get("shots", []) or [])

    rr = (resolved.get("_ref_resolution") or {}).get("resolved", 0)
    ur = (resolved.get("_ref_resolution") or {}).get("unresolved", 0)

    # 单镜头时长（platform-presets）
    duration_per_shot = 0.0
    preset_path = os.path.join(SKILL_ROOT, "assets", "platform-presets.json")
    presets = _load(preset_path) or {}
    plat = presets.get(platform) or presets.get("bilibili") or {}
    dur = plat.get("duration")
    if isinstance(dur, (int, float)):
        duration_per_shot = float(dur)
    duration_sec = round(duration_per_shot * shots, 2) if shots else 0.0

    project_name = os.path.basename(p.rstrip("/\\")) or "unknown"

    return {
        "type": "production",
        "run_id": run_id,
        "project": project_name,
        "platform": platform,
        "beats": beats,
        "shots": shots,
        "resolved_refs": rr,
        "unresolved_refs": ur,
        "duration_sec": duration_sec,
        "model_notes": {
            "has_script": bool(script), "has_storyboard": bool(story),
            "has_resolved": bool(resolved),
        },
    }


def parse_failures_file(path, run_id):
    data = _load(path)
    if data is None:
        return []
    if isinstance(data, dict):
        data = [data]
    out = []
    for d in data:
        out.append({
            "type": "failure",
            "run_id": run_id,
            "stage": d.get("stage"),
            "error_type": d.get("error_type"),
            "message": d.get("message"),
            "fingerprint": d.get("fingerprint"),
        })
    return out


def post_events(url, token, events, timeout=15):
    body = json.dumps({"events": events}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url.rstrip("/") + "/ingest",
        data=body,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {token}" if token else "",
        },
        method="POST",
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", help="含 script.json / storyboard.json 的项目目录")
    ap.add_argument("--platform", default="bilibili", help="平台预设名（bilibili/douyin/...）")
    ap.add_argument("--url", default=DEFAULT_URL, help="记忆服务地址")
    ap.add_argument("--token", default=DEFAULT_TOKEN, help="Bearer token")
    ap.add_argument("--run-id", default=None, help="运行 ID（缺则自动生成）")
    ap.add_argument("--feedback", nargs=3, metavar=("RATING", "ASPECT", "COMMENT"),
                    help="追加人类评分：--feedback 5 overall '节奏很爽'")
    ap.add_argument("--failures", help="失败日志文件（JSON 数组 / 单对象）")
    ap.add_argument("--mirror", help="把 events 写入该镜像文件（不发送）")
    ap.add_argument("--sync", help="把镜像文件同步发送到服务器")
    ap.add_argument("--dry-run", action="store_true", help="只打印 events，不发送/不写镜像")
    a = ap.parse_args()

    if a.sync:
        events = _load(a.sync)
        if not events:
            print(f"[error] 镜像文件无效：{a.sync}", file=sys.stderr)
            return 2
        if not isinstance(events, list):
            events = events.get("events", [])
        code, resp = post_events(a.url, a.token, events)
        print(f"[sync] {a.sync} → HTTP {code} {resp}")
        return 0 if code == 200 else 1

    if not a.project:
        print("[error] 需提供 --project（或 --sync 镜像文件）", file=sys.stderr)
        return 2

    run_id = a.run_id or make_run_id()
    events = [build_production_event(a.project, a.platform, run_id)]

    if a.feedback:
        try:
            rating = int(a.feedback[0])
        except ValueError:
            print("[error] rating 必须是 1-5 整数", file=sys.stderr)
            return 2
        events.append({
            "type": "feedback", "run_id": run_id,
            "rating": rating, "aspect": a.feedback[1], "comment": a.feedback[2],
        })

    if a.failures:
        events.extend(parse_failures_file(a.failures, run_id))

    if a.dry_run:
        print(json.dumps({"events": events}, ensure_ascii=False, indent=2))
        return 0

    if a.mirror:
        with open(a.mirror, "w", encoding="utf-8") as f:
            json.dump({"events": events}, f, ensure_ascii=False, indent=2)
        print(f"[mirror] 已写镜像 → {a.mirror}（events={len(events)}）")
        return 0

    code, resp = post_events(a.url, a.token, events)
    print(f"[collect] HTTP {code} → {resp}")
    return 0 if code == 200 else 1


if __name__ == "__main__":
    sys.exit(main())
