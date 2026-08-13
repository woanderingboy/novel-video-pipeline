#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_storyboard.py — S1+S2 → S3 分镜脚手架生成器（资产优先）

读入 S1 剧本（script.json）+ S2 资产库（character_manifest.json / scene_manifest.json），
按「每 beat → 至少一镜头」自动拼出 storyboard.json 草稿：
  - 每条 shot 自动填 character_ref / scene_ref（引用 S2 资产 id）
  - 按 camera-movements.json 的 subject_aware_map 选 1 个主运镜
  - 按 beat 类型选景别（shot_size）
  - 拼接 negative_prompt（IP 防火墙令牌全覆盖 + 质量负向）
  - 套 platform-presets.json 的 aspect_ratio / duration

输出为「脚手架草稿」，供人工精修（相机角度、情绪、台词、节奏）后送视频模型。
纯标准库，无需 pip install。

用法：
  python scripts/build_storyboard.py --project <DIR> [--platform bilibili] [--out storyboard.json]
  （DIR 下需有 script.json；character_manifest.json / scene_manifest.json 可选，缺则只生成骨架）
"""
import argparse
import json
import os
import re
import sys

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:  # noqa
        print(f"[warn] 解析失败 {path}: {e}", file=sys.stderr)
        return None


# beat 类型 → camera-movements subject_aware_map 键 的别名表
BEAT_ALIAS = {
    "hook": "Hook", "setup": "Setup", "stakes": "Stakes",
    "turn": "Twist", "twist": "Twist", "confront": "confrontation",
    "confrontation": "confrontation", "payoff": "Payoff", "resolve": "Payoff",
    "cliff": "Cliff", "reveal": "revelation", "revelation": "revelation",
    "action": "action", "dialogue": "dialogue", "power": "power_shift",
    "powershift": "power_shift", "power_shift": "power_shift",
    "dominate": "power_shift", "submit": "power_shift", "shift": "power_shift",
    "establishing": "establishing", "reaction": "reaction",
}
SHOT_SIZE_BY_TYPE = {
    "confrontation": "MCU", "dialogue": "MCU", "establishing": "EWS",
    "revelation": "CU", "Hook": "MS", "Twist": "MCU", "Payoff": "MS",
    "Cliff": "MCU", "action": "WS", "reaction": "CU", "power_shift": "WS",
    "Stakes": "MS", "Setup": "MS",
}


def load_ip_tokens():
    """与 validate_pipeline.py 的 get_ip_tokens 对齐：只取 blocked_properties。"""
    d = _load(os.path.join(SKILL_ROOT, "assets", "s2", "negative-ip.json"))
    toks = []
    if d and "blocked_properties" in d:
        for vals in d["blocked_properties"].values():
            for v in vals:
                t = str(v).strip()
                if t:
                    toks.append(t)
    return toks


def load_quality_tokens():
    """从 negative-quality.md 提取第一段代码块里的质量负向词。"""
    p = os.path.join(SKILL_ROOT, "assets", "s3", "negative-quality.md")
    if not os.path.exists(p):
        return []
    txt = open(p, encoding="utf-8").read()
    m = re.search(r"```(.*?)```", txt, re.S)
    if not m:
        return []
    out = []
    for part in re.split(r"[,\n]", m.group(1)):
        t = part.strip().lower()
        if t and t not in ("",):
            out.append(t)
    return out


def resolve_beat_type(t):
    if not t:
        return "reaction"
    key = str(t).strip().lower()
    return BEAT_ALIAS.get(key, "reaction")


def pick_camera(move_map, beat_type, movements_ids):
    cands = move_map.get(beat_type, move_map.get("reaction", ["static"]))
    for c in cands:
        if c in movements_ids:
            return c
    return "static"


def pick_view(scene, beat_idx, beat_type):
    views = (scene or {}).get("views", {}) or {}
    if not views:
        return None
    if beat_type == "establishing" and "establishing" in views:
        return "establishing"
    if beat_idx == 0 and "establishing" in views:
        return "establishing"
    for v in ("ots_a", "ots_b", "reverse", "insert", "establishing"):
        if v in views:
            return v
    return next(iter(views))


def detect_chars(beat, char_ids, char_names):
    """beat 可带 characters 列表；否则按 action 文本命中的角色名/ id 推断；都无命中则全带上。"""
    explicit = beat.get("characters")
    if explicit:
        return [c for c in explicit if c in char_ids]
    action = str(beat.get("action", "")).lower()
    hits = []
    for cid in char_ids:
        name = (char_names.get(cid) or "").lower()
        if cid.lower() in action or (name and name in action):
            hits.append(cid)
    if hits:
        return hits
    return list(char_ids)  # 兜底：全带上（gate 仅 warn，不 error）


def collect_ref_images(chars, ref_chars):
    """从角色 ref_pack（优先）/ three_view 抽取锚定图令牌，直连 S5 锁脸（对齐即梦 @引用 / Runway 单图锁脸）。
    令牌格式 char:<char_id>:<ref_pack键或three_view键>，由 S5 合成脚本解析为真实图路径。"""
    out = []
    for cid in ref_chars:
        c = next((c for c in chars if c.get("id") == cid), None)
        if not c:
            continue
        rp = c.get("ref_pack") or {}
        keys = [k for k in ("frontal_closeup", "profile", "full_body") if k in rp]
        if not keys:  # ref_pack 非标准三键时取全部
            keys = list(rp.keys())
        if keys:
            for k in keys:
                out.append(f"char:{cid}:{k}")
        else:  # 退路：用三视图
            tv = c.get("three_view") or {}
            for k in ("front", "side", "back"):
                if k in tv:
                    out.append(f"char:{cid}:{k}")
    return out


def allocate_durations(shots, legal, target=None):
    """镜头预算 / pacing 计算器：把目标总时长分配到各镜。
    - target=None：末镜取最长合法时长作收束，其余用传入默认。
    - 否则：末镜加权 1.5（收束更长），其余 1.0；每镜时长吸附到平台合法集（<=预算，优先最大合法值）。"""
    n = len(shots)
    if n == 0:
        return
    if target is None:
        last = legal[-1] if legal else shots[-1].get("duration_s", 30)
        shots[-1]["duration_s"] = last
        return
    weights = [1.0] * n
    weights[-1] = 1.5
    total_w = sum(weights)
    raw = [target * w / total_w for w in weights]
    for s, r in zip(shots, raw):
        cands = [d for d in legal if d <= r + 1e-9]
        s["duration_s"] = max(cands) if cands else min(legal)


def main():
    ap = argparse.ArgumentParser(description="S1+S2 → S3 分镜脚手架生成器")
    ap.add_argument("--project", required=True, help="含 script.json（及可选 manifest）的项目目录")
    ap.add_argument("--platform", default="bilibili")
    ap.add_argument("--out", default=None, help="输出 storyboard.json 路径（默认 <project>/storyboard.json）")
    ap.add_argument("--target-duration", type=int, default=None,
                    help="镜头总时长预算（秒）；按平台合法时长集自动分配到各镜（末镜更长）。默认末镜取最长合法值。")
    args = ap.parse_args()

    proj = args.project
    script = _load(os.path.join(proj, "script.json"))
    if not script:
        print(f"[error] 找不到 {proj}/script.json", file=sys.stderr)
        return 2
    char_lib = _load(os.path.join(proj, "character_manifest.json")) or {}
    scene_lib = _load(os.path.join(proj, "scene_manifest.json")) or {}

    chars = char_lib.get("characters", []) or []
    char_ids = [c.get("id") for c in chars if c.get("id")]
    char_names = {c.get("id"): c.get("name", "") for c in chars}
    scenes = scene_lib.get("scenes", []) or []
    scene_ids = [s.get("id") for s in scenes if s.get("id")]
    scene_by_id = {s.get("id"): s for s in scenes}

    # 资产库（movements / subject_aware_map / presets）
    cam = _load(os.path.join(SKILL_ROOT, "assets", "s3", "camera-movements.json")) or {}
    move_map = cam.get("subject_aware_map", {}) or {}
    movements_ids = {m.get("id") for m in cam.get("movements", [])}
    presets = _load(os.path.join(SKILL_ROOT, "assets", "s3", "platform-presets.json")) or {}
    plat = (presets.get("platforms", {}) or {}).get(args.platform, {})
    aspect = plat.get("aspect_ratio", "16:9")
    durations = plat.get("durations", [15, 30, 60, 120])
    default_dur = 30 if 30 in durations else (durations[1] if len(durations) > 1 else durations[0])

    ip_tokens = load_ip_tokens()
    quality_tokens = load_quality_tokens()
    neg_ip = ", ".join(ip_tokens)
    neg_q = ", ".join(quality_tokens)
    neg_all = (neg_ip + ", " + neg_q).strip(", ")

    beats = script.get("beats", []) or []
    shots = []
    for i, b in enumerate(beats):
        bt = resolve_beat_type(b.get("t"))
        # 权力动态（power_dynamic）→ 自动选角（权力轴落地）
        power = b.get("power_dynamic")
        speed = "normal"
        if power in ("dominate", "submit", "shift", "equal"):
            bt = "power_shift"
            if power == "dominate":
                cam_id, shot_size = "low_angle", "CU"
            elif power == "submit":
                cam_id, shot_size = "high_angle", "MS"
            elif power == "shift":
                cam_id, shot_size, speed = "low_angle", "CU", "slow_motion"
            else:  # equal：平权谈判，用常规正反打
                cam_id = pick_camera(move_map, "power_shift", movements_ids)
                shot_size = "MS"
        else:
            cam_id = pick_camera(move_map, bt, movements_ids)
            shot_size = SHOT_SIZE_BY_TYPE.get(bt, "MS")
        # 场景解析
        raw_scene = b.get("scene")
        scene_id = None
        if isinstance(raw_scene, str) and raw_scene in scene_ids:
            scene_id = raw_scene
        elif isinstance(raw_scene, int) and 0 <= raw_scene - 1 < len(scenes):
            scene_id = scenes[raw_scene - 1].get("id")
        elif isinstance(raw_scene, str):
            scene_id = raw_scene  # 容错：gate 会 warn 未知 id
        view = pick_view(scene_by_id.get(scene_id), i, bt) if scene_id in scene_by_id else None
        scene_ref = {"scene_id": scene_id}
        if view:
            scene_ref["view"] = view
        # 角色解析
        ref_chars = detect_chars(b, char_ids, char_names)
        character_ref = [{"char_id": cid} for cid in ref_chars]
        ref_images = collect_ref_images(chars, ref_chars)
        # 拼 prompt（草稿）
        cparts = []
        for cid in ref_chars:
            fp = next((c.get("fixed_prompt", "") for c in chars if c.get("id") == cid), "")
            if fp:
                cparts.append(fp)
        scene_name = scene_by_id.get(scene_id, {}).get("name", scene_id or "")
        cam_en = next((m.get("prompt_en", "") for m in cam.get("movements", []) if m.get("id") == cam_id), "")
        prompt = ""
        if cparts:
            prompt += "; ".join(cparts[:2]) + ". "
        if scene_name:
            prompt += f"At {scene_name}. "
        if cam_en:
            prompt += cam_en.format(SUBJECT=ref_chars[0] if ref_chars else "the subject",
                                    STYLE="cinematic 16:9") + ". "
        prompt += f"{shot_size} shot, consistent character, [STYLE]."
        raw_t = str(b.get("t") or f"beat{i+1}")
        prefix = re.sub(r"[^A-Za-z0-9]", "", raw_t)[:6] or f"b{i+1}"
        readable = f"[{bt}] {b.get('action','')}｜场景:{scene_name or '—'}｜角色:{'/'.join(ref_chars) or '—'}｜运镜:{cam_id}｜{shot_size}" + (f"｜权力:{power}" if power else "")
        shot = {
            "shot_id": f"S{prefix}_{i+1:03d}",
            "beat_ref": b.get("t", f"beat{i+1}"),
            "character_ref": character_ref,
            "scene_ref": scene_ref,
            "ref_images": ref_images,
            "camera_movement": cam_id,
            "shot_size": shot_size,
            "speed": speed,
            "prompt": prompt.strip(),
            "prompt_readable": readable,
            "negative_prompt": neg_all,
            "platform": args.platform,
            "aspect_ratio": aspect,
            "duration_s": default_dur,
            "attribution": "",
        }
        if power:
            shot["power_dynamic"] = power
        shots.append(shot)

    # 镜头预算 / pacing：分配时长
    allocate_durations(shots, durations, args.target_duration)

    out = {
        "platform": args.platform,
        "aspect_ratio": aspect,
        "generated_by": "build_storyboard.py (scaffold)",
        "note": "脚手架草稿：请人工精修相机角度/情绪/台词/节奏后再送视频模型。",
        "shots": shots,
    }
    out_path = args.out or os.path.join(proj, "storyboard.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    # 摘要
    ref_char_hits = sum(1 for s in shots if s["character_ref"])
    ref_scene_hits = sum(1 for s in shots if s["scene_ref"].get("scene_id"))
    ref_img_hits = sum(1 for s in shots if s.get("ref_images"))
    total_dur = sum(s.get("duration_s", 0) for s in shots)
    print(f"[ok] 生成 {len(shots)} 镜（beats {len(beats)}）→ {out_path}")
    print(f"     角色资产引用 {ref_char_hits}/{len(shots)} 镜；场景资产引用 {ref_scene_hits}/{len(shots)} 镜；参考图锚定 {ref_img_hits}/{len(shots)} 镜")
    print(f"     IP 防火墙令牌 {len(ip_tokens)} 个已全覆盖（negative_prompt 合并 {len(quality_tokens)} 质量负向）")
    print(f"     平台 {args.platform}｜比例 {aspect}｜"
          + (f"总时长预算 {args.target_duration}s → 实分配 {total_dur}s（末镜 {shots[-1]['duration_s']}s）"
             if args.target_duration else f"默认时长 {default_dur}s，末镜 {shots[-1]['duration_s']}s"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
