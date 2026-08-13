# novel-video-pipeline

把一段故事（网文 / 漫画 / 原创剧本 / 童话绘本）稳定转化为**可喂给文生视频模型的「分镜提示词包 + 视觉参考图 + CC0 配音配乐」**，全程守住「不复制真实第三方版权形象」底线。默认面向**横屏 16:9 漫剧**产线，也可切儿童向 / 竖屏短视频。

## 特性

- **五站式流水线**：S1 改编剧本 → S2 资产库 → S3 分镜提示词 → S4 音频 → S5 合成。
- **资产优先**：先建角色三视图 + 场景正反打资产，再写分镜，保证跨镜一致与空间连续。
- **IP 防火墙**：恒定负向词（Peppa / Disney / Marvel / Sanrio …），门禁强制校验令牌全覆盖。
- **站间门禁** `validate_pipeline.py`：五道质量闸门 + `--strict` + `--child` 儿童向硬门禁。
- **零 IP 风险拉取**：PD / CC0 图（OBI / Openverse / Met）+ CC0 音频（Openverse），仅标准库 + curl。
- **借鉴方法层、禁止照搬表达**：爆款漫剧只取法「题材 / 情绪 / 爽点」骨架，角色情节一律原创。
- **配套脚手架**：`build_storyboard`（自动分镜）、`resolve_ref_images`（锚定图解析）、`build_ffmpeg_concat`（拼接）。

## 架构

```
S1 改编剧本 ─script.json─▶ S2 资产库 ─char+scene manifest─▶ S3 分镜词 ─storyboard.json─▶ S4 音频 ─▶ S5 合成 ─▶ 成片
        │                                                                          │
        └────────── 资产优先：先建库再写镜；IP 防火墙 + 门禁(--strict/--child) 贯穿全程 ┘
```

三机制贯穿全程：**资产优先**（S2 永远在 S3 前）、**IP 防火墙**（negative-ip 令牌强制覆盖）、**站间门禁**（许可 / 画质 / 去重 / 来源 / 敏感 + 儿童向）。

## 快速开始

```bash
# 0. 准备故事：写 S1 script.json（参考 examples/asset-first-demo/script.json）
# 1. 拉取 CC0 视觉参考（可选）
python scripts/fetch_visual_assets.py --out ./visual_assets --sources obi,openverse,met
# 2. 拉取 CC0 音频（可选）
python scripts/fetch_audio.py --out ./audio_assets
# 3. 自动生成分镜草稿（从 S1+S2 自动落地 character_ref/scene_ref/运镜/IP 负向）
python scripts/build_storyboard.py --project ./my_project --platform bilibili
# 4. 解析锚定图（S5 前，令牌 → 真实图路径）
python scripts/resolve_ref_images.py --project ./my_project
# 5. 门禁校验（儿童向追加 --child）
python scripts/validate_pipeline.py --project ./my_project --platform bilibili --strict
# 6. 合成（S5）：逐镜生图 → 音频对齐 → 拼接导出 1080p
python scripts/build_ffmpeg_concat.py --project ./my_project --clips-dir ./my_project/clips
```

## 安装为 WorkBuddy Skill

将本仓库克隆 / 解压到 WorkBuddy 的 skills 目录（`~/.workbuddy/skills/novel-video-pipeline/`），重启 WorkBuddy 即自动发现。

## 许可

MIT，详见 [LICENSE](./LICENSE)。资产库（图 / 音）仅引用 Public Domain / CC0 来源；所有范例均为公版或原创，不内嵌任何版权文本。

## 全流程搭档

配合 [novel-writing-pipeline](https://github.com/<your-org>/novel-writing-pipeline) 使用：先写小说（含 13 类风格预设 + 写作指纹去 AI 味），再把其人物卡 / 设定集 / 章纲喂入本项目的 S1 `script.json`，形成「写作 → 漫剧」端到端流水线。
