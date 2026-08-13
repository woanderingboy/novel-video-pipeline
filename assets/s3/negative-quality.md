---
type: reference
created: 2026-08-12
updated: 2026-08-12
tags: [负向提示词, 去噪, 质量, S3, 平台预设]
related: [负向提示词库-IP防火墙, seedance-2-prompts-模板库]
license: 原创整理（可自由用于商业产品）
---

# S3 负向提示词补充（质量层）+ 平台预设

> 与 `S2-视觉风格/负向词库.json`（IP 防火墙·角色屏蔽）分工：
> - **S2 负向词库** = 版权角色屏蔽（Peppa / Disney 等）→ 防侵权
> - **本文件** = 生成质量 + 风格一致负向（去畸变、防抄袭特定画师）→ 提质
> S3 分镜 Skill 输出每条 shot 时，把两者 `negative_prompt` 合并追加。

## 一、通用去噪负向词（必加）

```
low quality, low resolution, blurry, deformed, deformed hands, extra fingers,
extra limbs, bad anatomy, mangled, watermark, text, signature, logo, copyright,
jpeg artifacts, oversaturated, cropped, out of frame, duplicate, mutated
```

## 二、风格一致负向（防"混搭翻车"）

- 单镜头内不要混多种画风：`mixed styles, inconsistent art style`
- 防直接复刻某商业画师签名风：`specific artist signature style, copyrighted art style`
- 防 3D 渲染伪影（若走 2D 插画）：`poor 3d render, plastic texture`

## 三、与 S2 合并示例（S3 Skill 自动拼装）

```json
{
  "shot_id": "s03",
  "prompt": "extreme close-up, a child's hand planting a seed in soil, soft morning light, watercolor style",
  "negative_prompt": "low quality, deformed, extra fingers, watermark, text, Peppa Pig, Disney Princess, specific artist signature style"
}
```

## 四、平台比例 / 时长预设

见 `platform_presets.json`（S3 Skill 按目标平台读取 `aspect_ratio` 与 `duration` 自动套用模板库占位符）。
