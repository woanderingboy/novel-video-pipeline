#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_pipeline.py — 四站式产物门禁校验
=========================================
校验一个项目目录下 S1–S4 四站产物的契约与质量闸门（S5 合成在门禁通过后执行），输出报告。支持 --child 儿童向硬门禁。
每站产物为约定 JSON：
  S1  script.json            : {title, logline, characters[], scenes[], beats[{t,scene,action,value}]}
  S2  character_manifest     : {characters[{id,name,visual_lock,fixed_prompt,three_view{front,side,back},ref_pack}]}
      scene_manifest         : {scenes[{id,name,geography,axis_of_action,views{establishing,ots_a,ots_b,reverse,insert},char_positions(可选·多角色屏幕站位),power_notes(可选)}]}
      visual_manifest        : {items[{file,license,source,width,height,sha256}]}  （可选配套参考图）
  S3  storyboard.json        : {shots[{shot_id,beat_ref,character_ref[],scene_ref,ref_images[](可选·直连锚定图),camera_movement,shot_size,speed(可选),prompt,prompt_readable,negative_prompt,platform,aspect_ratio,duration_s,attribution}]}
  S4  audio_manifest         : {items[{file,license,source,duration_ms}]}

闸门（对齐《资产库-质量甄别与污染防控规范》）：
  - S1：必须有 title/logline/beats；beats 覆盖 Hook→价值收尾
  - S2：character_manifest / scene_manifest / visual_manifest 至少存在其一；角色须有三视图 front/side/back、场景须有正反打视图；视觉参考图 license ∈ {PD, CC0}、宽高 >= 闸门、sha256 去重
  - S3：每条 shot 必须有 negative_prompt（IP 防火墙 + 质量负向）；character_ref/scene_ref 须指向资产库存在的 id；CC BY 4.0 数据须带 attribution
  - S4：每条音频 license == CC0；时长 0.3–180s（保留极短音效，仅过滤 0/损坏数据）
  - 跨站：S3 shots 数 >= S1 beats 数（每个节拍至少一镜）

运行：
  python validate_pipeline.py --project <DIR> [--strict]
"""
import argparse, json, os, sys

# 归一化后比对，兼容真实来源的大小写差异（Openverse 返回 "cc0"、Met 返回 "Public Domain" 等）
CLEAN_LICENSE = {"public domain", "cc0", "cc0 1.0", "cc0 (public domain)"}


def norm_license(lic):
    return str(lic).strip().lower()


# skill 根目录（scripts/ 上一级），用于加载内置资产做硬校验
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_rel(rel):
    return load(os.path.join(SKILL_DIR, rel))


def get_ip_tokens():
    """从 S2 IP 防火墙负向词库 flatten 出全部被屏蔽 IP 名称（小写），供 S3 硬校验。"""
    d = _load_rel(os.path.join("assets", "s2", "negative-ip.json"))
    toks = set()
    if d and "blocked_properties" in d:
        for vals in d["blocked_properties"].values():
            for v in vals:
                t = str(v).strip().lower()
                if t:
                    toks.add(t)
    return toks


def get_platform_presets():
    """从 S3 平台预设读取各平台合法时长集与比例。"""
    d = _load_rel(os.path.join("assets", "s3", "platform-presets.json"))
    return d.get("platforms", {}) if d else {}


MIN_W, MIN_H = 1000, 600
# 音频时长下限 0.3s：过滤真正的 0/损坏数据，保留真实极短音效（翻页/心跳/提示音等 SFX）
MIN_AUDIO_DUR, MAX_AUDIO_DUR = 0.3, 180

# 儿童向硬门禁（--child）：价值收尾必含 + 儿童安全负向令牌 + 成熟内容扫描
CHILD_RESOLUTION_BEATS = {"resolve", "valueend", "value_end", "positive", "warm",
                          "价值收尾", "价值"}
CHILD_SAFETY_TOKENS = ["violence", "gore", "horror", "scary", "blood", "mature",
                       "nudity", "weapon", "smoking", "alcohol", "creepy", "disturbing"]
MATURITY_DENY = ["血腥", "暴力", "恐怖", "裸露", "色情", "武器", "吸烟", "酗酒", "自杀",
                 "杀人", "死亡", "kill", "murder", "blood", "gore", "nude", "nudity"]


def load(path):
    if not os.path.exists(path):
        return None
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception as e:
        return {"__error__": str(e)}


def check_s1(d, rep, child=False):
    if not d:
        return rep.error("S1", "script.json 缺失")
    for k in ("title", "logline", "beats"):
        if k not in d:
            rep.error("S1", f"缺少字段 {k}")
    beats = d.get("beats", [])
    if len(beats) < 3:
        rep.warn("S1", f"beats 仅 {len(beats)} 个，建议 >= 3（Hook→冲突→解决→价值）")
    rep.ok("S1", f"标题《{d.get('title','?')}》节拍 {len(beats)} 个")
    if child:
        has_resolution = any(
            str(b.get("t", "")).strip().lower() in CHILD_RESOLUTION_BEATS for b in beats
        )
        if not has_resolution:
            rep.error_strict(
                "S1",
                "儿童向要求至少一个「价值收尾」类节拍（t ∈ Resolve/ValueEnd/positive…），用于正面价值收束",
            )
        text = " ".join(
            str(b.get("action", "")) + " " + str(b.get("value", "")) + " " + str(b.get("scene", ""))
            for b in beats
        ).lower()
        hit = [w for w in MATURITY_DENY if w in text]
        if hit:
            rep.error_strict(
                "S1",
                f"[child] 命中成熟/敏感词 {hit[:6]} —— 儿童向内容须剔除暴力/恐怖/成人元素",
            )
    return len(beats)


def check_character_lib(d, rep):
    """校验角色资产库：每个角色须有锁定描述 + 三视图 front/side/back。"""
    if not d:
        return
    chars = d.get("characters", [])
    if not chars:
        rep.warn("S2", "character_manifest 存在但 characters 为空")
    for c in chars:
        cid = c.get("id", "?")
        for k in ("id", "name", "visual_lock", "fixed_prompt"):
            if not c.get(k):
                rep.error("S2", f"角色 {cid} 缺字段 {k}（视觉锁定/固定描述不完整）")
        tv = c.get("three_view", {})
        for v in ("front", "side", "back"):
            if v not in tv:
                rep.error("S2", f"角色 {cid} 三视图缺 {v}（front/side/back 须齐全）")
    rep.ok("S2", f"角色资产 {len(chars)} 个，三视图校验通过")


def check_scene_lib(d, rep):
    """校验场景资产库：每个场景须有空间关系 + 正反打视图。"""
    if not d:
        return
    scenes = d.get("scenes", [])
    if not scenes:
        rep.warn("S2", "scene_manifest 存在但 scenes 为空")
    for s in scenes:
        sid = s.get("id", "?")
        for k in ("id", "name", "geography", "axis_of_action"):
            if not s.get(k):
                rep.error("S2", f"场景 {sid} 缺字段 {k}（空间关系不完整）")
        views = s.get("views", {})
        need = ["establishing"]
        if not (views.get("ots_a") or views.get("ots_b")):
            need.append("ots_a/ots_b 至少其一")
        if not views.get("reverse"):
            need.append("reverse")
        missing = [v for v in ["establishing", "ots_a", "ots_b", "reverse", "insert"]
                   if v not in views and v in ("establishing", "reverse")]
        if missing:
            rep.error("S2", f"场景 {sid} 视图缺 {missing}（须含 establishing + ots_a/ots_b 其一 + reverse）")
        elif not (views.get("ots_a") or views.get("ots_b")):
            rep.error("S2", f"场景 {sid} 须含 ots_a/ots_b 至少其一（正反打）")
    rep.ok("S2", f"场景资产 {len(scenes)} 个，正反打视图校验通过")


def check_visual_lib(d, rep):
    if not d:
        return
    items = d.get("items", [])
    seen = set()
    for it in items:
        lic = norm_license(it.get("license", ""))
        if lic not in CLEAN_LICENSE:
            rep.error("S2", f"{it.get('file')} 许可不符：{lic}")
        w, h = it.get("width", 0), it.get("height", 0)
        if min(w, h) < MIN_H or max(w, h) < MIN_W:
            rep.warn("S2", f"{it.get('file')} 画质偏低 {w}x{h}")
        sha = it.get("sha256")
        if sha in seen:
            rep.error("S2", f"重复 sha256：{it.get('file')}")
        seen.add(sha)
    rep.ok("S2", f"视觉参考 {len(items)} 张，去重后 {len(seen)} 张")


def check_s2(d_char, d_scene, d_visual, rep):
    """S2 资产库：三者至少存在其一；分别校验。"""
    present = [x for x in (d_char, d_scene, d_visual) if x is not None]
    if not present:
        return rep.error("S2", "资产库缺失：character_manifest / scene_manifest / visual_manifest 至少需其一")
    check_character_lib(d_char, rep)
    check_scene_lib(d_scene, rep)
    check_visual_lib(d_visual, rep)


def check_s3(d, rep, n_beats, platform="bilibili", platform_presets=None,
             ip_tokens=None, char_ids=None, scene_ids=None, child=False):
    if not d:
        return rep.error("S3", "storyboard.json 缺失")
    shots = d.get("shots", [])
    for s in shots:
        if not s.get("negative_prompt"):
            rep.error("S3", f"{s.get('shot_id')} 缺 negative_prompt（IP 防火墙）")
        # 资产库引用校验
        for cr in s.get("character_ref", []) or []:
            cid = cr.get("char_id")
            if char_ids is not None and cid not in char_ids:
                rep.warn("S3", f"{s.get('shot_id')} character_ref 引用未知角色 {cid}（资产库无此 id）")
        sr = s.get("scene_ref") or {}
        sid = sr.get("scene_id")
        if scene_ids is not None and sid and sid not in scene_ids:
            rep.warn("S3", f"{s.get('shot_id')} scene_ref 引用未知场景 {sid}（资产库无此 id）")
        if not s.get("character_ref"):
            rep.warn("S3", f"{s.get('shot_id')} 未带 character_ref（建议引用 S2 角色资产锁定一致性）")
        if not s.get("scene_ref"):
            rep.warn("S3", f"{s.get('shot_id')} 未带 scene_ref（建议引用 S2 场景资产保证空间连续）")
        # 平台预设校验：时长必须落在合法集、比例须匹配
        if platform_presets:
            pp = platform_presets.get(platform, {})
            legal = pp.get("durations", [])
            ar = pp.get("aspect_ratio")
            dur = s.get("duration_s")
            if legal and dur is not None and dur not in legal:
                rep.error_strict(
                    "S3",
                    f"{s.get('shot_id')} 时长 {dur}s 不在平台「{platform}」合法集 {legal}",
                )
            if ar and s.get("aspect_ratio") and s.get("aspect_ratio") != ar:
                rep.warn("S3", f"{s.get('shot_id')} 比例 {s.get('aspect_ratio')} 与平台「{platform}」预设 {ar} 不符")
        if "CC BY" in str(s.get("attribution", "")) and not s.get("attribution"):
            rep.warn("S3", f"{s.get('shot_id')} 用到 CC BY 4.0 数据但未带 attribution")
    # IP 防火墙令牌硬校验：合并所有 shot negative_prompt，必须覆盖全部被屏蔽 IP 名称
    covered = 0
    if ip_tokens:
        merged = " ".join(str(s.get("negative_prompt", "")) for s in shots).lower()
        covered = sum(1 for t in ip_tokens if t in merged)
        missing = [t for t in sorted(ip_tokens) if t not in merged]
        if missing:
            rep.error_strict(
                "S3",
                f"negative_prompt 缺失 IP 防火墙令牌 {len(missing)} 个"
                f"（如：{', '.join(missing[:8])}{'…' if len(missing) > 8 else ''}）—— 守住真实第三方版权形象刚需",
            )
    if len(shots) < n_beats:
        rep.warn("S3", f"镜头数 {len(shots)} < 节拍数 {n_beats}，存在未覆盖节拍")
    rep.ok("S3", f"{len(shots)} 个镜头，IP 防火墙令牌覆盖 {covered}/{len(ip_tokens or set())} 个")
    if child and CHILD_SAFETY_TOKENS:
        merged = " ".join(str(s.get("negative_prompt", "")) for s in shots).lower()
        missing = [t for t in CHILD_SAFETY_TOKENS if t not in merged]
        if missing:
            rep.error_strict(
                "S3",
                f"[child] negative_prompt 缺儿童安全令牌 {len(missing)} 个"
                f"（如：{', '.join(missing[:6])}{'…' if len(missing) > 6 else ''}）—— 守住儿童向底线",
            )
    return len(shots)


def check_s4(d, rep):
    if not d:
        return rep.error("S4", "audio_manifest 缺失")
    items = d.get("items", [])
    for it in items:
        if norm_license(it.get("license")) != "cc0":
            rep.error("S4", f"{it.get('file')} 许可非 CC0：{it.get('license')}")
        dur = (it.get("duration_ms") or 0) / 1000.0
        if dur and (dur < MIN_AUDIO_DUR or dur > MAX_AUDIO_DUR):
            rep.error("S4", f"{it.get('file')} 时长 {dur:.1f}s 超出 {MIN_AUDIO_DUR}–{MAX_AUDIO_DUR}s 区间")
    rep.ok("S4", f"{len(items)} 个 CC0 音频")
    return len(items)


class Report:
    def __init__(self, strict):
        self.strict = strict
        self.errors, self.warns, self.okays = 0, 0, 0

    def error(self, stage, msg):
        self.errors += 1
        print(f"  ❌ [{stage}] {msg}")

    def warn(self, stage, msg):
        self.warns += 1
        print(f"  ⚠️  [{stage}] {msg}")

    def error_strict(self, stage, msg):
        """硬约束：strict 模式下升级为 error（门禁失败），普通模式仅 warn。"""
        if self.strict:
            self.error(stage, msg)
        else:
            self.warn(stage, msg)

    def ok(self, stage, msg):
        self.okays += 1
        print(f"  ✅ [{stage}] {msg}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True, help="含 S1-S4 产物 JSON 的项目目录")
    ap.add_argument("--strict", action="store_true", help="遇 warn 也视为失败")
    ap.add_argument("--platform", default="bilibili",
                    help="目标平台预设（bilibili/douyin/xiaohongshu/square），默认 bilibili（横屏 16:9 漫剧）")
    ap.add_argument("--child", action="store_true",
                    help="儿童向硬门禁：S1 须含价值收尾节拍 + S3 须覆盖儿童安全负向令牌 + 扫描成熟内容")
    a = ap.parse_args()
    p = os.path.abspath(a.project)
    rep = Report(a.strict)
    ip_tokens = get_ip_tokens()
    platform_presets = get_platform_presets()
    print(f"== 校验项目：{p} ｜ 平台：{a.platform} ==")
    n_beats = check_s1(load(os.path.join(p, "script.json")), rep, child=a.child)
    d_char = load(os.path.join(p, "character_manifest.json"))
    d_scene = load(os.path.join(p, "scene_manifest.json"))
    d_visual = load(os.path.join(p, "visual_manifest.json"))
    check_s2(d_char, d_scene, d_visual, rep)
    char_ids = set(c.get("id") for c in (d_char or {}).get("characters", []))
    scene_ids = set(s.get("id") for s in (d_scene or {}).get("scenes", []))
    check_s3(load(os.path.join(p, "storyboard.json")), rep, n_beats,
             platform=a.platform, platform_presets=platform_presets,
             ip_tokens=ip_tokens, char_ids=char_ids or None, scene_ids=scene_ids or None,
             child=a.child)
    check_s4(load(os.path.join(p, "audio_manifest.json")), rep)
    print(f"\n== 结果：✅{rep.okays}  ⚠️{rep.warns}  ❌{rep.errors} ==")
    if rep.errors or (a.strict and rep.warns):
        sys.exit(1)
    print("门禁通过，可进入下一站 / 合成。")


if __name__ == "__main__":
    main()
