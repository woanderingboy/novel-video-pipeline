---
name: novel-video-pipeline
description: 小说 / 网文 / 漫画改编 AI 漫剧（横屏 16:9）的「四站式」生成流水线 Skill（S1 改编剧本 → S2 视觉资产 → S3 分镜提示词 → S4 音频）。当用户要把一段故事、小说、网文、漫画或剧本做成 AI 漫剧（横屏 16:9）/ 短视频（分镜提示词 + 视觉参考 + 配音配乐），或需要四站中任意一站的产出与质量把关时使用。内置 S1 故事结构库（含爆款漫剧情绪引擎）与改编压缩方法论、S2 公共领域负向词 IP 防火墙、S3 分镜模板库与平台预设、S4 CC0 音频清单，并提供零 IP 风险的图/音拉取脚本与站间门禁校验。支持借鉴热门爆款漫剧的题材 / 情绪 / 爽点结构（方法层，可自由使用），但坚守「不照搬表达、不复制真实第三方版权形象」底线；也支持儿童向漫剧（童话 / 绘本改编）作为可选子类型。
---

# 漫剧（小说 / 网文 / 漫画改编）· 四站式流水线（novel-video-pipeline）

## Overview

把一段文本故事（网文小说、漫画、原创剧本、童话绘本等）稳定地转化为可喂给文生视频模型的**分镜提示词包 + 视觉参考图 + CC0 配音配乐**，全程守住「不复制真实第三方版权形象」底线。默认面向**漫剧（横屏 16:9 / 多集连载）**产线，也可按需切换为儿童向漫剧、单集短视频等子类型。产线基调对标当下爆款漫剧的「强钩子 + 情绪拉扯 + 反转 + 爽点 + 集间悬念」节奏，但只取法其**方法层骨架**，角色 / 情节 / 画风一律原创。

流水线由四个顺序工作站组成，每站产出一份约定 JSON / 资源目录，下一站消费上一站产物。**核心生产顺序：先建资产库（S2），再写分镜词（S3）**——分镜只是把资产按镜头语言排布，确保角色一致性与场景空间连续。

```
S1 改编剧本  ──script.json──▶  S2 资产库  ──character_manifest + scene_manifest (+ visual_manifest)──▶  S3 分镜提示词  ──storyboard.json（引用资产+ref_images锚定）──▶  S4 音频  ──audio_manifest──▶  S5 合成  ──成片
```

- **S1 改编剧本**：把长篇/原文压缩成「教学或叙事价值骨架 + 节拍表」，输出 `script.json`（title / logline / characters / scenes / beats）。
- **S2 资产库（先建）**：通读全局剧本，建立**角色三视图资产**（`character_manifest.json`：visual_lock + front/side/back 三视图 + 锚定图包 + fixed_prompt）与**场景正反打多视图资产**（`scene_manifest.json`：axis_of_action + establishing/OTS A→B/reverse/insert），并配套拉取公共领域 / CC0 视觉参考图（`visual_manifest.json`）。套用 IP 防火墙负向词。这一步产出的就是「资产库」，供 S3 直接引用。
- **S3 分镜提示词（基于资产库）**：把每个 beat 展开成镜头（shot），**每条 shot 引用 `character_ref`（角色+视图）与 `scene_ref`（场景+视图）**，从资产库锁定描述 + 运镜库（`camera-movements.json`）+ 平台预设拼出 prompt，注入 `negative_prompt`，输出 `storyboard.json`。
- **S4 音频**：为镜头匹配 CC0 BGM / 音效，输出 `audio_manifest.json`。
- **S5 合成（闭环到成片）**：把 S3 `storyboard.json`（含 `ref_images` 锚定图）+ S4 `audio_manifest.json` 闭合成片——逐镜生图/图生视频（用 `ref_images` 锁脸）→ 音频对齐 → 剪辑拼接（按 `duration_s` 与 `aspect_ratio`）→ 平台导出 → 一致性终检。详见 `references/s5-composite.md` 与 `scripts/build_ffmpeg_concat.py`。

## When To Use（触发）

- 用户给出一段故事/小说/网文/漫画/剧本，要「做成漫剧 / 短视频 / 分镜 / 动画」。
- 用户要「改编剧本、写分镜提示词、生成视频脚本、配画风、配音乐」。
- 用户需要**任意单站**产出（如只想要分镜提示词，或只想要公共领域参考图）。
- 用户对素材有「版权干净 / 可商用 / 零 IP 风险」硬要求。

## 工作流（Workflow）

> 全流程参考热门开源方案的**编排思路**，但代码自研、资产自包含：
> - **ViMax**（MIT，~392 commits 的 S1→S4 编排流水线）→ 借鉴其「故事→分镜→视频」的阶段切分与产物契约。
> - **seedance-prompt-skill** / **ai-shortfilm-prompts**（MIT）→ 借鉴其 SKILL 格式的提示词模板组织方式，作为 S3 底座。
> - **ArcReel**（AGPL）→ **仅学架构，不抄代码**（AGPL 传染性，禁止合入本 MIT 风格 skill）。
> 详见 `references/architecture-licenses.md`。

### 第 0 步 · 接收需求
确认四点：① 源故事（网文 / 漫画 / 原创剧本 / 贴文或给路径）；② 目标平台（横屏漫剧默认 B站 / YouTube 向，见 `assets/s3/platform-presets.json` 的 bilibili；竖屏抖音 / 视频号向则用 douyin）；③ 画风（国漫 / 水彩 / 写实 / 浮世绘 / 童书插画…）；④ 子类型与受众（默认横屏 16:9 漫剧，对标爆款节奏但原创；若儿童向则额外强制 IP 防火墙 + 排除 mature 内容）。

### 第 1 站 · S1 改编剧本
1. 载入 `assets/s1/story-structure.md`（三幕 / 节拍结构模板）+ `assets/s1/adaptation-method.md`（压缩方法论：保留价值骨架、删冗、情绪曲线）。
2. 按需填 `assets/s1/beat-sheet.md`（可填节拍表）。
3. 参考 `assets/s1/example-romeo-juliet.md`、`example-journey-to-west.md` 两个改编范例。
4. 产出 `script.json`，字段见 `references/workflow.md` §S1 契约。

### 第 2 站 · S2 资产库（先建，后写分镜）
1. 通读 S1 全部 beats / characters / scenes，建立**角色资产**：载入 `assets/s2/character-design.md`，为每个主要角色产出 `character_manifest.json`（visual_lock + fixed_prompt + 三视图 front/side/back + 锚定图包 ref_pack + 一致性规则）。
2. 建立**场景资产**：载入 `assets/s2/scene-multiview.md`，为每个主要场景产出 `scene_manifest.json`（geography + axis_of_action + views{establishing, ots_a, ots_b, reverse, insert}）。
3. 配套拉取 / 生成公共领域 / CC0 视觉参考图 `visual_manifest.json`（多画风：国漫 / 水彩 / 写实 / 童书插画 / Met 公版美术…），套用 IP 防火墙。
4. 套用 IP 防火墙：`assets/s2/negative-ip.json` + `assets/s2/negative-ip-firewall.md`。
5. **许可闸门**：仅收 `Public Domain` / `CC0`。角色 / 场景资产一律原创，禁止同名同设定照搬爆款（详见 IP 防火墙 §六）。

### 第 3 站 · S3 分镜提示词（基于资产库写）
1. 载入 `assets/s3/template-library.json`（分镜模板库：镜头类型 / 景别 / 情绪）+ `assets/s3/camera-movements.json`（运镜库：40+ 运镜 + 节拍→运镜映射 + 平台语法）+ `assets/s3/platform-presets.json`（各平台 prompt 语法、宽高比、时长上限）+ `assets/s3/tag-stats.json`（标签频率统计）+ `assets/s3/negative-quality.md`（质量负向词）+ `assets/s2/negative-ip.json`（IP 防火墙）。
2. 每 beat → 至少一 shot；每条 shot **必带 `character_ref` 与 `scene_ref`**（引用 S2 资产库），并从资产 `fixed_prompt` 取锁定角色描述；从 `camera-movements.json` 取 1 个主运镜（subject_aware_map 按 beat 类型推荐）；必带 `negative_prompt`（IP 防火墙 + 质量负向拼接）。
3. 产出 `storyboard.json`：`shots[{shot_id, beat_ref, character_ref[], scene_ref, ref_images[]（可选·直连锚定图，见下方「参考图锚定」）, camera_movement, shot_size, speed（可选·速度修饰 slow_motion 等，见 camera-movements.json 的 speed_modifiers）, prompt, prompt_readable, negative_prompt, platform, aspect_ratio, duration_s, attribution}]`。权力变化镜头用 `camera_movement: low_angle/high_angle` + `speed: "slow_motion"`（写法见 `assets/s2/scene-multiview.md` §三（补）权力轴）。

   **参考图锚定（ref_images，跨镜一致性关键）**：`ref_images` 是每镜**直连锚定图的列表**，比纯文本 `fixed_prompt` 更稳（对齐即梦 @引用 / Runway Gen-4 单图锁脸）。每条为字符串，约定两种写法：① 资产引用令牌 `char:<char_id>:<ref_pack键或three_view键>` / `scene:<scene_id>:<view>`（由脚本自动从 `character_manifest.ref_pack` 抽取，生成器再解析为真实图路径）；② 直接图路径 / URL（如 `/assets/char_shen_zhao_face.png`）。建议每角色配 2–3 张（正面近景/侧面/全身），即梦上限 9 张、Runway 单张即锁。`build_storyboard.py` 默认自动把角色 `ref_pack` 抽成 `ref_images`；也可在 S5 合成时直接喂给图生视频模型做锁脸/锁服装参考。
4. **CC BY 4.0 数据须带 attribution**（本库资产均为 PD/CC0，默认免署名；若引入外部 CC BY 数据则必须填 attribution）。
5. **脚手架加速（可选）**：先建好 S1 `script.json` + S2 `character_manifest.json` / `scene_manifest.json`，运行 `python scripts/build_storyboard.py --project <DIR> --platform bilibili` 自动生成 `storyboard.json` 草稿（按 beat 自动填 `character_ref`/`scene_ref`、从 `subject_aware_map` 选 1 主运镜、按 beat 类型选景别、拼接 `negative_prompt` 全覆盖 IP 令牌），再人工精修相机角度 / 情绪 / 台词 / 节奏。该脚本是「资产优先」顺序的自动落地，产出可被 `validate_pipeline.py` 直接通过。

### 第 4 站 · S4 音频
1. 载入 `assets/s4/audio-manifest.json`（已拉取的 CC0 音频清单，含 BGM / 音效 / 情绪类别：ambient / cinematic / playful / tense / romantic / lullaby 等）。
2. 按镜头情绪匹配：悬疑低音→反转段、温柔钢琴→温情段、whoosh→转场、lullaby→安睡段、cartoon bounce→活泼段。
3. 产出 `audio_manifest.json`：`items[{file, license, source, duration_ms}]`，**仅 CC0**。

### 第 5 站 · S5 合成（闭环到成片）
1. 载入 `references/s5-composite.md`（S5 合成 SOP：五步闭环 + 工具矩阵 + 一致性终检清单）。
1.5 **解析锚定图**：运行 `python scripts/resolve_ref_images.py --project <DIR>`，把每条 shot 的 `ref_images` 令牌（`char:<id>:<key>` / `scene:<id>:<view>`）展开为真实图路径，产出 `storyboard.resolved.json`（未解析令牌保留原串并告警）。
2. **逐镜生图 / 图生视频**：以 `storyboard.resolved.json` 的 `ref_images`（已解析真实图）作为锁脸/锁服装参考，配合 `fixed_prompt` + `camera_movement` + `camera-movements.json` 的 `lens`/`stages` 喂给即梦 @引用 / Runway Gen-4 / Kling / Seedance 生成每段 clip。
3. **音频对齐**：按 beat 情绪从 `audio_manifest.json`（CC0）选 BGM，按 `duration_s` 裁音效。
4. **剪辑拼接**：运行 `python scripts/build_ffmpeg_concat.py --project <DIR> --clips-dir <DIR>/clips` 生成 concat 列表与命令，按 `aspect_ratio`（横屏 16:9）导出 1080p。
5. **一致性终检**：核对 §四清单（角色/场景/轴线/权力轴/时长/IP 防火墙/音频/比例）后再发布。

### 第 6 步 · 门禁校验（必做）
运行 `scripts/validate_pipeline.py --project <DIR> --platform bilibili [--strict]`，校验四站产物契约 + 五道质量闸门：S3 每条 shot 的 `negative_prompt` **必须覆盖 `assets/s2/negative-ip.json` 全部被屏蔽 IP 令牌**（守住真实第三方版权形象刚需，缺失在 strict 下即失败）；时长须落在 `platform-presets.json` 对应平台合法集、比例须匹配（横屏漫剧默认 16:9）；S4 音频时长 0.3–180s（保留真实极短音效）。`--strict` 下 warn 也判失败。通过后才可进入视频合成。儿童向产线追加 `--child`：强制 S1 含「价值收尾」类节拍、S3 覆盖儿童安全负向令牌（violence/gore/horror/blood/mature/nudity/weapon…）、扫描 beats 命中成熟内容（strict 下为失败）。

## 拉取脚本（零 IP 风险）

两个脚本仅标准库 + 系统 curl，无需 pip install：

```bash
# S2 视觉资产：OBI 公共领域多画风插画（含童书/国漫风）+ Openverse CC0 图 + Met 公版美术
python scripts/fetch_visual_assets.py --out <DIR> --sources obi,openverse,met

# S4 音频：Openverse CC0（免 key）；填 PIXABAY/FREESOUND key 可启用扩充通道
python scripts/fetch_audio.py --out <DIR>
```

- 质量闸门内置：许可（PD/CC0）、画质（长边≥1000 且短边≥600、文件≥50KB）、去重（SHA256 跨运行）、来源闸（仅机构源）、敏感闸（Openverse `mature=true` 一律排除，全平台硬要求）。
- OBI 传输用 `curl` 引擎（`--retry 5 --retry-all-errors -k`）绕过本环境 Python `urllib` 偶发 SSL 断流。

## 五道质量闸门（全站通用）

1. **许可闸门**：S2/S4 仅收 `Public Domain` / `CC0`；引入 CC BY 4.0 必须带 attribution。
2. **画质闸门**：图最长边≥1000 且短边≥600；音频时长 0.3–180s、文件≥100KB。
3. **去重闸门**：SHA256 跨运行持久化，重复图/音频自动跳过。
4. **来源闸门**：仅机构级 / 公共领域源（OBI、Openverse、Met、Freesound CC0…）；拒收不明来源。
5. **敏感闸门**：全内容排除 `mature`（儿童向额外强化）；S2/S3 强制注入 IP 防火墙负向词，屏蔽已知版权形象；对热门漫剧 / 网文 IP **可借鉴其题材 / 情绪 / 爽点结构（方法层），但禁止逐角色、逐场、名场面完全照搬（完全抄袭）**。

## IP 防火墙（借鉴不照搬）

- 恒定负向词见 `assets/s2/negative-ip.json`，覆盖 Peppa Pig、Disney、Marvel、Sanrio、Numberblocks、My Little Pony 等**已注册的真实第三方版权形象**——这些是硬边界，无论借鉴与否都不得复现（门禁会强制校验令牌覆盖）。
- **漫剧专项纪律（借鉴不照搬）**：热门漫剧 / 网文 IP 的「题材类型、情绪结构、爽点范式、镜头语言、节奏」属**方法层**，不可版权、可作创作养料，**鼓励借鉴**；但**禁止完全抄袭**——即不得逐角色照搬（同名同设定）、逐场复制名场面构图、直接复刻招牌画风 / 标志性配色组合、搬运原文台词。即使用户点名某爆款，也只提取其「可复用的方法骨架」而非「表达」，转成原创描述（「强宿命感的黑衣男主 + 红衣女主对峙」），再送图像 / 视频模型，并叠加 negative prompt 双保险守住真实第三方版权形象。
- 本 skill **不内嵌任何版权文本**，只统计结构 / 写法层范式；所有范例均为公版或用户自有素材。

## Resources

- `assets/s1/`：故事结构模板、改编压缩方法论、可填节拍表、剧本格式规范、两个改编范例。
- `assets/s2/`：负向词库 `negative-ip.json` + IP 防火墙说明 `negative-ip-firewall.md` + 角色资产方法论 `character-design.md` + 场景资产方法论 `scene-multiview.md`。
- `assets/s3/`：分镜模板库 `template-library.json`、运镜库 `camera-movements.json`、平台预设 `platform-presets.json`、标签统计 `tag-stats.json`、质量负向词 `negative-quality.md`。
- `assets/s4/`：已拉取 CC0 音频清单 `audio-manifest.json`。
- `scripts/`：`fetch_visual_assets.py`（S2 拉图）、`fetch_audio.py`（S4 拉音）、`build_storyboard.py`（S1+S2 → S3 分镜脚手架自动生成，支持 `ref_images` 锚定自动抽取 / `power_dynamic` 自动选角 / `--target-duration` 镜头预算）、`resolve_ref_images.py`（S5 把 `ref_images` 令牌解析为真实图路径，产出 `storyboard.resolved.json`）、`build_ffmpeg_concat.py`（S5 由 storyboard.json 生成 FFmpeg 拼接列表 + 命令）、`validate_pipeline.py`（站间门禁，支持 `--child` 儿童向硬门禁）。
- `references/`：`architecture-licenses.md`（开源方案借鉴与许可证边界）、`workflow.md`（四站详细契约与用法）、`case-studies.md`（爆款漫剧/短剧运镜·分镜语法借鉴，方法论文献，不照搬 IP）、`benchmark.md`（对比测评：NVP vs ViMax/seedance/ai-shortfilm/ArcReel 等评分矩阵 + 实证自测）、`s5-composite.md`（S5 合成 SOP：五步闭环 + 工具矩阵 + 一致性终检清单）。

## 注意事项

- 大体积图库/音频库不内嵌进 skill（保持可携带）；运行时用脚本拉取，或指向你自己的 CC0 素材目录（如 `./assets/characters`、`S4-音频库/samples/` 这类本地洁净批）。
- 本 skill 为编排方法论 + 自包含资产，不依赖 ViMax/ArcReel 等外部代码运行。
- 取得 BHL key / NYPL token 后，可自行在 `fetch_visual_assets.py` 追加 `fetch_bhl()` / `fetch_nypl()` 通道（OBI 已验证无需 key）。
