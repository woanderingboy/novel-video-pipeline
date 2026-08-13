---
type: reference
created: 2026-08-13
updated: 2026-08-13
tags: [S5, 合成, 成片, 剪辑, FFmpeg, 即梦, Runway, Kling, 闭环]
related: [workflow, scene-multiview, character-design]
license: 原创整理（方法论 + 自包含脚本，无外部代码依赖）
---

# S5 合成 SOP · 把分镜 + 音频闭合成成片

> 目的：S1–S4 产出的是「资产 + 分镜词 + 音频清单」，还不是视频。S5 负责把它们**闭合成可发布的成片**。本 SOP 给出可落地的生产顺序、工具矩阵、一致性清单，并附 `scripts/build_ffmpeg_concat.py` 自动生成拼接脚本。
> 定位：本 skill 是「编排方法论 + 自包含资产」，S5 不内嵌视频模型，而是**把资产正确喂给生产工具**（即梦 / Runway / Kling / 剪映 / FFmpeg）。

## 一、S5 生产顺序（五步闭环）

```
S3 storyboard.json（分镜词 + ref_images 锚定）
        │
        ├─① 逐镜生图/图生视频：ref_images + fixed_prompt + camera_movement → 每镜一段 clip
        │
S4 audio_manifest.json（CC0 BGM/音效）
        │
        ├─② 音频对齐：按 beat 情绪选 BGM，按 shot 时长裁音效
        │
        ├─③ 剪辑拼接：按 shot 顺序 + duration_s 把 clips 拼成时间线
        │
        ├─④ 平台导出：aspect_ratio（16:9 横屏漫剧）+ 平台编码（bilibili 1080p）
        │
        └─⑤ 一致性终检：跨镜角色/场景/色调/轴线核对（见 §四清单）
```

## 二、逐镜生图 / 图生视频（关键：用 ref_images 锁脸）

每条 `shot` 已带 `ref_images[]`（资产引用令牌 `char:<id>:<key>` 或真实图路径）+ `fixed_prompt` + `camera_movement` + `lens`（来自 `camera-movements.json`）。喂给生成器时：

| 工具 | 锚定方式 | 要点 |
|------|----------|------|
| **即梦（Jimeng）** | `@引用` 最多 9 张参考图 | 每角色配 2–3 张（`frontal_closeup`/`profile`/`full_body`），跨镜相似度 ~90%+；`ref_images` 令牌解析为真实图后批量 @引用 |
| **Runway Gen-4** | 单张参考图即锁脸/服装/身形 | 用 `char:<id>:frontal_closeup` 作锁脸底图，跨场景稳定；极端表情易微崩，避免大幅变妆 |
| **Kling（可灵）** | 首尾帧 + 参考图权重 0.8–1.0 | 用 `ref_images` 做图生视频转场，首尾帧控制稳 |
| **Seedance** | `camera_fixed=false` + 自然语句 | 把 `camera_movement` + `lens` 写成一句英文运镜描述（见 `camera-movements.json` 的 `prompt_en`） |

**5 段式提示词落地**：把 `camera-movements.json` 每条 movement 的 `stages`（setup/motion_start/peak/settle/exit）按顺序拼成一句自然语言，并把 `lens` 焦段写进相机参数，可显著提升运镜稳定（对标 ai-shortfilm-prompts）。

> 资产优先的红利：因 S2 已锁死 `fixed_prompt` + 三视图 + 锚定图，S5 只需「逐镜排布 + 引用」，漂移概率远低于逐镜现想描述。

## 三、剪辑拼接（build_ffmpeg_concat.py 自动生成）

`scripts/build_ffmpeg_concat.py` 读 `storyboard.json`，为每段 clip 生成 FFmpeg concat demuxer 列表（含 `duration` 指令，严格对齐 `duration_s`），并输出可直接执行的拼接命令；若同目录有 `audio_manifest.json` 则一并给出音视频合成命令。

```bash
# 1) 先准备好每镜 clip：<project>/clips/<shot_id>.mp4（由 §二 各生成器产出）
# 2) 生成拼接列表 + 命令
python scripts/build_ffmpeg_concat.py --project <DIR> --clips-dir <DIR>/clips --out <DIR>/concat.txt

# 3) 按输出的 ffmpeg 命令合成（示例）
ffmpeg -f concat -safe 0 -i concat.txt -i audio.m4a -c:v libx264 -c:a aac -r 30 -pix_fmt yuv420p -movflags +faststart output_16x9.mp4
```

横屏漫剧默认 `16:9` / `1920x1080` / `30fps`，对应 `platform-presets.json` 的 bilibili。竖屏抖音则切 `9:16` / `1080x1920`。

## 四、一致性终检清单（发布前必过）

- [ ] **角色一致**：跨镜脸/发型/服饰/标记（泪痣、旧疤）无漂移（ref_images + fixed_prompt 双保险）。
- [ ] **场景一致**：场景美术/光线/陈设连续；`scene_ref.view` 机位与 `axis_of_action` 一致，无跨轴跳切。
- [ ] **轴线连续**：180° 视线轴未破；多角色 `char_positions` 的 `side_of_axis` 未被违反（camera_side 角色不抢 action_line 反向）。
- [ ] **权力轴自洽**：`power_dynamic` 标记的镜头用了 `low_angle`/`high_angle` + `slow_motion`，且与 `power_notes` 描述一致。
- [ ] **时长合规**：每镜 `duration_s` ∈ 平台合法集；总时长落在平台区间（bilibili 15/30/60/120）。
- [ ] **IP 防火墙**：`negative_prompt` 仍覆盖全部令牌；成片无真实第三方版权形象；儿童向额外排 mature。
- [ ] **音频合规**：仅 CC0；BGM 情绪与 beat 匹配，音效不抢对白。
- [ ] **比例正确**：横屏 16:9 无黑边变形；导出编码平台友好。

## 五、工具矩阵（按需求选）

| 环节 | 推荐 | 备注 |
|------|------|------|
| 生图/锁脸 | 即梦 @引用 / Runway Gen-4 | 锚定图优先 |
| 图生视频 | Kling / Seedance / Runway | 运镜语法见 camera-movements.json |
| 剪辑拼接 | 剪映 / FFmpeg（本脚本生成命令） | 批量可控、可复现 |
| 音频 | 本 skill `audio_manifest.json`（CC0） | 仅 PD/CC0 |

> 诚实边界：S5 不替代专业剪辑审美，只把 S1–S4 资产「正确、可复现」地闭合成片；成片节奏/蒙太奇仍需人工精修。
