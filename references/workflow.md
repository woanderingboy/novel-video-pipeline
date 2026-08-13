# 四站式工作流详细契约（novel-video-pipeline）

每个工作站产出一份约定 JSON，下一站消费。本文给出字段契约、资产引用与常见操作。门禁校验见 `scripts/validate_pipeline.py`。

---

## S1 · 改编剧本（script.json）

**目标**：把长篇/原文压缩成「价值骨架 + 节拍表」，不丢失叙事张力与情绪曲线。

**载入资产**：
- `assets/s1/story-structure.md` — 三幕结构、节拍类型定义
- `assets/s1/adaptation-method.md` — 压缩方法论（保留价值骨架、删冗、情绪曲线设计）
- `assets/s1/beat-sheet.md` — 可填节拍表
- `assets/s1/format-spec.md` — 剧本格式规范
- `assets/s1/example-romeo-juliet.md` / `example-journey-to-west.md` — 改编范例

**产出契约 `script.json`**：
```json
{
  "title": "片名",
  "logline": "一句话价值主张（如：被家族抛弃的庶子，凭一卷残破秘籍逆天改命）",
  "characters": [
    {"name": "角色名", "role": "主角/配角", "trait": "性格/动机", "visual": "外观提示（送 S2/S3）"}
  ],
  "scenes": [
    {"scene_id": 1, "setting": "场景", "mood": "情绪"}
  ],
  "beats": [
    {"t": "00:00", "scene": 1, "action": "动作/事件", "value": "本拍传递的情绪价值或剧情推力（如：受辱→逆袭伏笔）"}
  ]
}
```
**节拍建议**：Hook（强钩子/悬念）→ 冲突/问题 → 进阶/尝试 → 反转/爽点 → 收尾（留续集悬念），≥3 拍。漫剧以「情绪钩子 + 爽点 + 反转 + 悬念」为核心（横屏 16:9 多集连载，对标爆款节奏但原创），`value` 字段填本拍传递的情绪价值或剧情推力（如：主角受辱→逆袭铺垫、误会加深→追妻伏笔），必须显式填写。

---

## S2 · 资产库（character_manifest.json + scene_manifest.json + visual_manifest.json）

**目标**：通读全局剧本，先建立「角色三视图资产」与「场景正反打多视图资产」，再配套拉取公共领域 / CC0 视觉参考。这是分镜的素材底座——**先建资产，后写分镜**。

**载入资产**：
- `assets/s2/character-design.md` — 角色三视图方法论（visual_lock + 三视图 + 锚定图包 + fixed_prompt + 一致性规则）
- `assets/s2/scene-multiview.md` — 场景正反打方法论（axis_of_action + establishing/OTS A→B/reverse/insert + 180 度轴线）
- `assets/s2/negative-ip.json` — 恒定负向词（Peppa Pig / Disney / Marvel / Sanrio / Numberblocks / 小马宝莉…）
- `assets/s2/negative-ip-firewall.md` — 语义拆解 + negative prompt 屏蔽方法论

**产出契约 `character_manifest.json`**：
```json
{
  "characters": [
    {"id": "char_zhao", "name": "沈昭", "role": "主角",
     "visual_lock": "二十出头将门孤女，隐忍冷冽；凤眼、左眉骨旧疤；乌发高束；绯色交领战袍、墨色披风；清瘦挺拔",
     "fixed_prompt": "Shen Zhao, sharp-faced young woman, phoenix eyes with old scar above left brow, high-bound black hair, crimson cross-collar battle robe, ink-black cape, slender upright",
     "three_view": {"front": {"ref_image": "char_zhao_front.png"}, "side": {"ref_image": "char_zhao_side.png"}, "back": {"ref_image": "char_zhao_back.png"}},
     "ref_pack": {"frontal_closeup": "char_zhao_face.png", "profile": "char_zhao_profile.png", "full_body": "char_zhao_full.png"},
     "consistency_rules": ["每镜固定拼接 fixed_prompt", "中途不换锚定图", "左眉骨旧疤逐镜保留"]}
  ]
}
```

**产出契约 `scene_manifest.json`**：
```json
{
  "scenes": [
    {"id": "scene_hall", "name": "顾府喜堂", "type": "interior",
     "geography": "顾府正厅：红绸灯笼、八仙桌、喜字屏风、窗外夜雨",
     "axis_of_action": "A(沈昭，画面左) ↔ B(顾砚之，画面右)",
     "views": {
       "establishing": {"desc": "master shot 双人全景", "suggested_camera": "wide static"},
       "ots_a": {"desc": "过沈昭肩拍顾砚之", "subject": "顾砚之", "foreground": "沈昭", "suggested_camera": "OTS eye-level"},
       "ots_b": {"desc": "过顾砚之肩拍沈昭（反打）", "subject": "沈昭", "foreground": "顾砚之", "suggested_camera": "OTS reverse"},
       "reverse": {"desc": "clean single 沈昭反应", "subject": "沈昭", "suggested_camera": "MCU static"},
       "insert": {"desc": "退婚书/虎符细节", "subject": "prop", "suggested_camera": "ECU rack focus"}},
     "eyeline_match": "沈昭看右、顾砚之看左，保持 180 度轴线"}
  ]
}
```

**拉取视觉参考（二选一）**：
```bash
# A. 用脚本实时拉取（推荐，零 IP 风险）
python scripts/fetch_visual_assets.py --out ./visual_assets --sources obi,openverse,met
# B. 指向你自己的 CC0 素材目录（如 ./visual_assets，脚本 A 拉取的产物）
#    任何 Public Domain / CC0 图库均可，只要 license 标注 PD/CC0 即可通过门禁
```

**产出契约 `visual_manifest.json`**（可选，配套参考图）：
```json
{
  "count": 12,
  "items": [
    {"file": "obi_rackham__xxx.jpg", "license": "Public Domain", "source": "Old Book Illustrations",
     "width": 1600, "height": 1200, "sha256": "...", "src_url": "https://..."}
  ]
}
```
**闸门**：license ∈ {Public Domain, CC0}；长边≥1000 且短边≥600；SHA256 去重。角色/场景资产一律原创（详见 IP 防火墙 §六）。

---

## S3 · 分镜提示词（storyboard.json，基于资产库）

**目标**：每 beat → 至少一镜头，从 S2 资产库取锁定描述 + 运镜库取 1 个主运镜 + 平台预设拼 prompt，必带 `negative_prompt`。

**载入资产**：
- `assets/s3/template-library.json` — 镜头类型/景别/情绪模板
- `assets/s3/camera-movements.json` — 运镜库（40+ 运镜 + subject_aware_map 节拍→运镜 + platform_notes 平台语法）
- `assets/s3/platform-presets.json` — 各平台 prompt 语法、宽高比、时长上限
- `assets/s3/tag-stats.json` — 标签频率统计（辅助选词、对齐爆款句式）
- `assets/s3/negative-quality.md` — 质量负向词（blur / distorted / extra limbs…）
- `assets/s2/character_manifest.json` / `scene_manifest.json` — 资产库（分镜引用的源头）
- `assets/s2/negative-ip.json` — IP 防火墙（与质量负向拼接进 `negative_prompt`）

**产出契约 `storyboard.json`**：
```json
{
  "shots": [
    {
      "shot_id": "S01",
      "beat_ref": "Hook",
      "character_ref": [{"char_id": "char_zhao", "view": "front"}],
      "scene_ref": {"scene_id": "scene_hall", "view": "ots_a"},
      "camera_movement": "OTS eye-level",
      "shot_size": "MCU",
      "prompt": "Over-the-shoulder over Shen Zhao's shoulder framing Gu Yanzhi, Shen Zhao in crimson cross-collar battle robe ink-black cape, warm lantern key, ARRI Alexa 35 Cooke anamorphic 16:9, tense standoff",
      "prompt_readable": "Core 羞辱开场; Character 沈昭绯袍; Atmos 暖灯 ARRI 16:9; Camera OTS; Storyboard 顾掷退婚书",
      "negative_prompt": "peppa pig, disney, marvel, sanrio, numberblocks, my little pony, blur, deformed, extra limbs, lowres",
      "platform": "bilibili",
      "aspect_ratio": "16:9",
      "duration_s": 15,
      "attribution": ""
    }
  ]
}
```
**硬规则**：
- 每条 shot **必须**有 `negative_prompt`（IP 防火墙 + 质量负向）。
- 每条 shot **应**带 `character_ref` 与 `scene_ref`（引用 S2 资产库，门禁会 warn 缺失）；prompt 开头用资产 `fixed_prompt` 锁角色，不逐镜重写描述。
- 每条 shot **取 1 个主运镜**（`camera-movements.json` 的 `camera_movement` 字段；组合运动多数模型会混乱，见 `rule_single_primary`）。
- 镜头数 ≥ S1 beats 数（每个节拍至少一镜，校验会 warn）。
- 若 prompt/参考用到 **CC BY 4.0** 数据，`attribution` 必填（作者 + 许可链接）。

---

## S4 · 音频（audio_manifest.json）

**目标**：为镜头匹配 CC0 BGM / 音效。

**载入资产**：
- `assets/s4/audio-manifest.json` — 已拉取 CC0 音频清单（类别：ambient / cinematic / tense（悬疑）/ romantic（感情线）/ playful / lullaby / whoosh / cartoon bounce / 等，覆盖漫剧各情绪段）

**拉取（可选扩充）**：
```bash
python scripts/fetch_audio.py --out ./audio_assets
```

**产出契约 `audio_manifest.json`**：
```json
{
  "count": 6,
  "items": [
    {"file": "ov_12345.mp3", "license": "CC0", "source": "Openverse/Freesound",
     "duration_ms": 12000, "use_for": "S01 转场"}
  ]
}
```
**闸门**：license == CC0；时长 0.3–180s（真实短音效如翻页/心跳/提示音可 <1s，仅过滤 0/损坏数据）；文件≥100KB。`use_for` 标注挂载镜头便于合成对齐。

---

## 门禁校验（validate_pipeline.py）

```bash
python scripts/validate_pipeline.py --project <DIR> --platform bilibili [--strict]
```
校验项：
- S1：必有 title/logline/beats；beats ≥ 3。
- S2 资产库：
  - `character_manifest.json`（存在时）：每个角色须有 `id / name / visual_lock / fixed_prompt` 与 `three_view`（front/side/back 三键齐全）。
  - `scene_manifest.json`（存在时）：每个场景须有 `id / name / geography / axis_of_action` 与 `views`（至少含 establishing + ots_a/ots_b 其一 + reverse）。
  - `visual_manifest.json`（存在时）：每张图 license ∈ {PD, CC0}；画质达标；sha256 无重复。
  - 三者至少存在其一，否则 S2 缺失。
- S3：每条 shot 必有 negative_prompt；**合并所有 shot 的 negative_prompt 必须覆盖 `assets/s2/negative-ip.json` 全部被屏蔽 IP 令牌**（缺失在 strict 下为 error、普通模式为 warn——守住真实第三方版权形象刚需）；`character_ref` / `scene_ref` 引用须指向资产库存在的 id（缺失或错引 warn）；时长须落在 `--platform` 对应合法集（横屏漫剧默认 bilibili {15,30,60,120}，竖屏抖音向用 douyin {5,10,15,30,60}），比例须匹配平台预设（bilibili=16:9）；CC BY 数据带 attribution；镜头数 ≥ beats 数。
- S4：每条音频 license == CC0；时长 0.3–180s（保留极短音效，仅过滤 0/损坏）。
- 跨站：S3 shots 数 ≥ S1 beats 数。

退出码非 0 表示门禁失败（strict 下含 warn）。通过后才进入视频合成（S4 合成不在本 skill 范围，交给视频生成平台/工具）。
