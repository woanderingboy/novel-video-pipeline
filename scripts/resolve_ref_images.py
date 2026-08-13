#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
resolve_ref_images.py — 把 storyboard.json 的 ref_images 令牌解析为真实图路径
=================================================================================
S5 合成前，把每个 shot 的 `ref_images` 由「资产引用令牌」展开为真实图文件 / URL，
供即梦 @引用 / Runway Gen-4 / Kling 等图生视频模型直接锁脸、锁服装。

令牌约定（与 SKILL.md / build_storyboard.py 约定一致）：
  char:<char_id>:<key>    → character_manifest.characters[id].ref_pack[key]
                             或 .three_view[key]（三视图作锚定图）
  scene:<scene_id>:<view> → scene_manifest.scenes[id].view_images[view]
                             （若缺，则回退到 visual_manifest 中 tag 命中的图）
  直接路径 / http(s) URL   → 原样透传（绝对路径 / 网络地址 / 相对 assets_dir 的路径）

产物：<project>/storyboard.resolved.json
  - 每个 shot.ref_images 替换为「已解析的真实路径 / URL」列表
  - 无法解析的令牌保留原串并在报告中告警（不静默丢弃，避免锁脸失效）
  - 顶部新增 _ref_resolution 汇总（resolved / unresolved 计数）

运行：
  python scripts/resolve_ref_images.py --project <DIR> [--assets-dir <DIR>/assets]
"""
import argparse
import json
import os
import sys

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(p):
    if not os.path.exists(p):
        return None
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        return {"__error__": str(e)}


def _find_char(char_lib, cid):
    for c in (char_lib or {}).get("characters", []):
        if c.get("id") == cid:
            return c
    return None


def _find_scene(scene_lib, sid):
    for s in (scene_lib or {}).get("scenes", []):
        if s.get("id") == sid:
            return s
    return None


def _visual_by_tag(visual_lib, tag):
    out = []
    for it in (visual_lib or {}).get("items", []):
        tags = it.get("tags") or []
        if tag in tags or tag in str(it.get("file", "")):
            out.append(it.get("file"))
    return out


def resolve_token(tok, char_lib, scene_lib, visual_lib, assets_dir):
    """返回 (resolved_value, status)。status ∈ resolved/unresolved/passthrough。"""
    tok = (tok or "").strip()
    if not tok:
        return tok, "unresolved"

    # 直链 / URL / 绝对路径：透传
    if tok.startswith("http://") or tok.startswith("https://"):
        return tok, "passthrough"
    if os.path.isabs(tok):
        return tok, "passthrough"

    if tok.startswith("char:"):
        parts = tok.split(":", 2)
        if len(parts) < 3:
            return tok, "unresolved"
        _, cid, key = parts
        c = _find_char(char_lib, cid)
        if not c:
            return tok, "unresolved"
        rp = c.get("ref_pack") or {}
        tv = c.get("three_view") or {}
        if key in rp:
            return rp[key], "resolved"
        if key in tv:
            return tv[key], "resolved"
        # key 未命中角色资产：保留原串待补（status=unresolved）
        return tok, "unresolved"

    if tok.startswith("scene:"):
        parts = tok.split(":", 2)
        if len(parts) < 3:
            return tok, "unresolved"
        _, sid, view = parts
        s = _find_scene(scene_lib, sid)
        if s:
            vi = s.get("view_images") or {}
            if view in vi:
                return vi[view], "resolved"
        # 回退：visual_manifest 中按 tag 命中（scene_id:view）
        hits = _visual_by_tag(visual_lib, f"{sid}:{view}") or _visual_by_tag(visual_lib, sid)
        if hits:
            return hits[0], "resolved"
        return tok, "unresolved"

    # 相对 assets_dir 的路径
    cand = os.path.join(assets_dir, tok)
    if os.path.exists(cand):
        return cand, "resolved"
    return tok, "unresolved"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True, help="含 storyboard.json 的项目目录")
    ap.add_argument("--assets-dir", default=None,
                    help="相对图根目录（默认 <project>/assets）；用于解析相对路径令牌")
    a = ap.parse_args()
    p = os.path.abspath(a.project)
    assets_dir = a.assets_dir or os.path.join(p, "assets")

    story = load(os.path.join(p, "storyboard.json"))
    if not story or "__error__" in (story or {}):
        print(f"[error] 找不到或无法解析 {p}/storyboard.json", file=sys.stderr)
        return 2
    char_lib = load(os.path.join(p, "character_manifest.json"))
    scene_lib = load(os.path.join(p, "scene_manifest.json"))
    visual_lib = load(os.path.join(p, "visual_manifest.json"))

    resolved_total = 0
    unresolved_total = 0
    per_shot = []
    for s in story.get("shots", []):
        new_imgs = []
        for tok in s.get("ref_images", []) or []:
            val, status = resolve_token(tok, char_lib, scene_lib, visual_lib, assets_dir)
            if status == "unresolved":
                unresolved_total += 1
                print(f"  ⚠️  [{s.get('shot_id')}] 未解析令牌：{tok}")
            else:
                resolved_total += 1
            new_imgs.append(val)
        s["ref_images"] = new_imgs
        per_shot.append((s.get("shot_id"), len(new_imgs)))

    story["_ref_resolution"] = {
        "resolved": resolved_total,
        "unresolved": unresolved_total,
        "note": "unresolved 令牌已保留原串，请在 S5 合成前补齐对应锚定图（character_manifest.ref_pack / scene_manifest.view_images / visual_manifest）。",
    }

    out_path = os.path.join(p, "storyboard.resolved.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(story, f, ensure_ascii=False, indent=2)

    print(f"[ok] 解析 {resolved_total + unresolved_total} 个 ref_images → {out_path}")
    print(f"     已解析 {resolved_total} ｜ 未解析 {unresolved_total}（已保留原串待补）")
    if unresolved_total:
        print("     提示：未解析令牌不影响产出，但 S5 锁脸会退化为纯文本 fixed_prompt。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
