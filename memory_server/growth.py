#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
memory_server/growth.py — 把 SQLite 中的原始事件聚合成 learnings.json，并回灌 priors
=================================================================================
运行方式：
  python memory_server/growth.py [--db data/nvp_memory.db] [--out snapshot/learnings.json]

也可被 scripts/collect.py 在「本地免部署模式」下直接调用：
  from growth import run_growth
  run_growth(db_path, out_path)

职责：
  1. 读取 productions / feedback / failures / priors 四张表（连接走 db.get_conn，schema 与 server 一致）。
  2. 计算：总运行数、各维度评分均值、Top 失败模式（聚类 + 建议）、产出风格信号。
  3. 写出 snapshot/learnings.json（skill 侧 load_learnings.py 读取此文件）。
  4. 把聚合得到的稳定知识 upsert 进 priors 表（source=aggregated），供后续查询/加权。

失败模式 → 建议映射（error_type 命中即给针对性建议，否则按 stage 给通用建议）。
learnings.json 结构见本文件 FORMAT 常量注释。
"""
import argparse
import json
import os
from datetime import datetime, timezone

from db import get_conn, snapshot_path, DEFAULT_DB

DEFAULT_OUT = snapshot_path()

# error_type / 指纹关键字 → 给 skill 的具体优化建议
SUGGESTIONS = {
    "unresolved_ref": "build_storyboard 生成时优先保证每个角色至少 1 张三视图锚定图（three_view），降低 S5 锁脸退化率。",
    "ip_firewall_hit": "该运行命中 IP 防火墙令牌；检查 negative_prompt 是否覆盖新出现的版权形象，必要时扩充 S2 负向词库。",
    "power_shift_missing": "权力轴 beat 缺少对应 WS 镜头；建议 build_storyboard 在 power_shift 类型 beat 强制补 1 个 WS + 低角度。",
    "ref_resolution_fail": "storyboard.resolved.json 存在未解析 ref_images；在送 S5 前补齐 character_manifest.ref_pack / scene_manifest.view_images。",
    "validate_gate": "门禁校验未通过；检查 game_config / script.json 的结构字段是否齐全。",
    "schema": "JSON Schema 校验失败；核对字段命名与 SKILL.md 资产契约是否一致。",
}

STAGE_GENERIC = {
    "S1": "复盘剧本结构（beat 数 / 冲突前置 / 黄金 3 秒），确保 hook 在前 3 秒。",
    "S2": "复盘资产库（角色三视图 / 场景多视图 / 负向词）覆盖率。",
    "S3": "复盘分镜脚手架（景别 / 运镜 / ref_images 锚定）质量。",
    "S4": "复盘音频（BGM / 音效 / 配音）匹配度。",
    "S5": "复盘合成（锁脸 / 时长 / 节奏）稳定性。",
    "validate": "复盘门禁字段完整性。",
}


def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _suggest(fp, error_type, stage):
    if error_type and error_type in SUGGESTIONS:
        return SUGGESTIONS[error_type]
    for k, v in SUGGESTIONS.items():
        if k in (fp or ""):
            return v
    if stage and stage in STAGE_GENERIC:
        return STAGE_GENERIC[stage]
    return "复查该阶段日志，定位根因后补强对应校验或资产。"


def aggregate(conn):
    # 运行总数与产出均值
    prod = conn.execute(
        """SELECT COUNT(*) AS n, AVG(beats) AS ab, AVG(shots) AS as_,
                  AVG(resolved_refs) AS ar, AVG(unresolved_refs) AS au,
                  AVG(duration_sec) AS ad
           FROM productions"""
    ).fetchone()
    runs = prod["n"] or 0

    # 评分均值（按维度）
    fb_rows = conn.execute(
        "SELECT aspect, AVG(rating) AS avg, COUNT(*) AS n FROM feedback GROUP BY aspect"
    ).fetchall()
    ratings = {r["aspect"]: {"avg": round(r["avg"], 2), "n": r["n"]} for r in fb_rows}

    # Top 失败模式（聚类 + 建议）
    fail_rows = conn.execute(
        """SELECT fingerprint, COUNT(*) AS c,
                  GROUP_CONCAT(DISTINCT stage) AS stages,
                  GROUP_CONCAT(DISTINCT error_type) AS etypes
           FROM failures GROUP BY fingerprint ORDER BY c DESC LIMIT 30"""
    ).fetchall()
    failure_patterns = []
    for r in fail_rows:
        stages = (r["stages"] or "").split(",")
        etypes = (r["etypes"] or "").split(",")
        primary_stage = stages[0] if stages else None
        primary_et = etypes[0] if etypes else None
        failure_patterns.append({
            "fingerprint": r["fingerprint"],
            "count": r["c"],
            "stages": stages,
            "error_types": etypes,
            "suggestion": _suggest(r["fingerprint"], primary_et, primary_stage),
        })

    # 风格信号（近 50 次运行）
    style_rows = conn.execute(
        "SELECT platform, project FROM productions ORDER BY id DESC LIMIT 50"
    ).fetchall()
    platforms = {}
    projects = {}
    for r in style_rows:
        platforms[r["platform"] or "?"] = platforms.get(r["platform"] or "?", 0) + 1
        projects[r["project"] or "?"] = projects.get(r["project"] or "?", 0) + 1
    style_signals = {
        "top_platforms": sorted(platforms.items(), key=lambda x: -x[1])[:5],
        "top_projects": sorted(projects.items(), key=lambda x: -x[1])[:10],
        "sample_size": len(style_rows),
    }

    return {
        "runs": runs,
        "avg_beats": round(prod["ab"], 2) if prod["ab"] is not None else None,
        "avg_shots": round(prod["as_"], 2) if prod["as_"] is not None else None,
        "avg_resolved_refs": round(prod["ar"], 2) if prod["ar"] is not None else None,
        "avg_unresolved_refs": round(prod["au"], 2) if prod["au"] is not None else None,
        "avg_duration_sec": round(prod["ad"], 2) if prod["ad"] is not None else None,
        "ratings": ratings,
        "failure_patterns": failure_patterns,
        "style_signals": style_signals,
    }


def upsert_priors(conn, agg):
    """把稳定的聚合知识写回 priors（source=aggregated）。"""
    now = _now_iso()
    priors = []

    if agg["runs"]:
        priors.append(("meta.total_runs", agg["runs"], 1.0, "aggregated"))
    ov = agg["ratings"].get("overall")
    if ov:
        priors.append(("quality.avg_rating_overall", ov["avg"], min(1.0, ov["n"] / 10.0), "aggregated"))
    if agg["avg_unresolved_refs"] is not None:
        priors.append((
            "production.avg_unresolved_refs", agg["avg_unresolved_refs"],
            1.0 if agg["runs"] >= 5 else 0.3, "aggregated"))
    # 把高频失败模式也作为先验写入，供 skill 提前规避
    for fp in agg["failure_patterns"][:10]:
        if fp["count"] >= 2:
            priors.append((
                f"failure_pattern::{fp['fingerprint']}",
                {"suggestion": fp["suggestion"], "count": fp["count"]},
                min(1.0, fp["count"] / 10.0), "aggregated"))

    for key, value, weight, source in priors:
        conn.execute(
            """INSERT INTO priors (key, value, weight, source, updated_at)
               VALUES (?,?,?,?,?)
               ON CONFLICT(key) DO UPDATE SET
                 value=excluded.value, weight=excluded.weight,
                 source=excluded.source, updated_at=excluded.updated_at""",
            (key, json.dumps(value, ensure_ascii=False), weight, source, now),
        )
    conn.commit()
    return len(priors)


def run_growth(db_path=DEFAULT_DB, out_path=DEFAULT_OUT):
    """聚合指定 db → 写出 learnings.json（被 CLI 与 collect 本地模式共用）。"""
    conn = get_conn(db_path)
    try:
        agg = aggregate(conn)
        n_priors = upsert_priors(conn, agg)
    finally:
        conn.close()

    learnings = {
        "generated_at": _now_iso(),
        "version": 1,
        "stats": {
            "runs": agg["runs"],
            "avg_beats": agg["avg_beats"],
            "avg_shots": agg["avg_shots"],
            "avg_resolved_refs": agg["avg_resolved_refs"],
            "avg_unresolved_refs": agg["avg_unresolved_refs"],
            "avg_duration_sec": agg["avg_duration_sec"],
            "ratings": agg["ratings"],
        },
        "failure_patterns": agg["failure_patterns"],
        "style_signals": agg["style_signals"],
    }

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(learnings, f, ensure_ascii=False, indent=2)

    print(f"[ok] 聚合完成：{agg['runs']} 次运行，{len(agg['failure_patterns'])} 个失败模式，"
          f"回灌 {n_priors} 条 priors → {out_path}")
    return learnings


def main():
    ap = argparse.ArgumentParser(description="聚合记忆库 → learnings.json + priors")
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--out", default=DEFAULT_OUT)
    a = ap.parse_args()
    run_growth(a.db, a.out)


if __name__ == "__main__":
    main()
