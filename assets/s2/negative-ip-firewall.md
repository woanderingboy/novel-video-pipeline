---
type: reference
created: 2026-08-12
updated: 2026-08-13
tags: [负向提示词, IP防火墙, 版权屏蔽, 借鉴不照搬, S2]
related: [负向词库.json, 剧本格式规范]
license: 原创整理（屏蔽词清单不可版权，可自由用于商业产品）
---

# 负向提示词库 · IP 防火墙（原创整理）

## 一、目的

在 S3 分镜提示词生成后，自动追加 `negative_prompt` 字段，降低生成模型产出**已知版权形象**的概率。

> ⚠️ 本库为**辅助层**，不能 100% 保证屏蔽。必须与产品已有的 **NLP 语义拆解 + 特征向量相似度比对** 双保险配合使用（见「灵感童学工坊」IP 防火墙设计）。

## 二、版权方 / 角色清单（按来源分类，持续补充）

- **动画 / 幼教**：Peppa Pig（小猪佩奇）、Paw Patrol（汪汪队）、Cocomelon、Bluey、Numberblocks、Alphablocks、Blippi
- **Disney 系**：Disney Princess（迪士尼公主）、Mickey Mouse、Frozen（冰雪奇缘）、Toy Story、Moana（海洋奇缘）、Encanto
- **Marvel / DC**：Spider-Man、Batman、Superman、Marvel、DC
- **Sanrio**：Hello Kitty、My Melody、Cinnamoroll、Kuromi
- **其他**：My Little Pony（小马宝莉）、Powerpuff Girls（ powerpuff）、SpongeBob（海绵宝宝）、Pokémon、Harry Potter、Minions、Shrek

> 以上仅为「名称屏蔽」词；生成时作为 negative 词传入。产品侧仍走语义拆解（如「穿红裙子的小粉猪」→ 命中 Peppa）+ 向量比对双保险。

## 三、描述性负向词（风格层）

- 避免「官方海报风格」「某商业画师签名风」
- 避免直接复刻某 IP 的标志性配色 / 服饰组合
- 通用去噪：`low quality, deformed, extra limbs, watermark, text, copyright logo, signature`

## 四、与 S3 集成方式

S3 分镜 Skill 输出每条 shot 时，自动附加：

```
negative_prompt = 通用负向 + 命中分类的版权名列表
```

结构化定义见 `负向词库.json`，S3 Skill 直接 `json.load` 后 flatten `blocked_properties` 即可。

## 五、许可声明

本库为原创整理的「屏蔽词清单」，不含任何受版权保护的图像 / 文本 / 角色表达，可自由用于商业产品。

## 六、借鉴与抄袭边界（防火墙「别太绝对」）

> 用户要求：IP 防火墙别太绝对，**可以借鉴，但不要完全抄袭**。本库只屏蔽「真实第三方已注册版权形象」，不禁止对热门作品的**方法层借鉴**。

**🔓 可自由借鉴（不可版权，是创作养料）——鼓励：**

- 热门漫剧 / 网文 IP 的**题材类型、情绪结构、爽点范式、镜头语言、节奏**等叙事方法。
- 其「前 3 秒强钩子 + 中段压迫 + 反转爽点 + 集尾悬念」的节奏模板。
- 通用美术流派（国漫厚涂、水彩、写实、浮世绘……），这些本就开放。

**🔒 仍须守住（侵权边界，门禁硬校验）：**

- `negative-ip.json` 列出的**真实第三方已注册形象**（Disney / Marvel / Sanrio / Peppa Pig 等）——无论借鉴与否都不得复现，门禁强制校验令牌覆盖。
- **不得完全抄袭**具体作品的表达：逐角色照搬（同名同设定）、逐场复制名场面构图、直接复刻招牌画风 / 标志性配色组合、搬运原文台词。

**实操原则**：点名某爆款时，先抽「方法骨架」而非「表达」→ 填入原创角色 / 世界观 / 台词 → 送模型；本库负向词守住真实第三方版权形象，方法层借鉴自由发挥。
