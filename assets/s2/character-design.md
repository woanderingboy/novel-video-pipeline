---
title: 角色资产设计（三视图 + 锚定图包）
created: 2026-08-13
updated: 2026-08-13
tags: [角色一致性, 三视图, 锚定图, 资产库, S2]
---

# 角色资产设计 · 根据剧本全局建立「角色三视图 + 锚定图包」

> 来源方法论：综合 18183《AI短剧角色锁定》、xie.infoq.cn《AI漫剧角色一致性》、hellokit《AI漫剧爆发在即》研究报告、ailistprime / renderfire 角色一致性实测。核心结论：**角色漂移（character drift）是 AI 漫剧头号生产问题**，解法不是更好的 prompt，而是「视觉参考锚定 + 固定文字描述模板」双保险。

## 一、为什么先做角色资产（再写分镜）

传统做法每个镜头现想角色描述 → 下一镜改一个形容词（「棕发」变「栗发」）AI 就换脸。工业化做法是：

1. **S2 阶段通读 S1 全部 beats**，一次性锁定每个主要角色的「视觉身份」。
2. 产出 `character_manifest.json`（角色资产库）+ 三视图 / 锚定图（送图像模型先生成资产图）。
3. **S3 分镜直接引用 `character_ref`**，prompt 开头固定拼接 `fixed_prompt`，不再逐镜重新描述。

→ 生产顺序：**先生成资产（角色三视图 + 场景多视图），再生成分镜词**。分镜只是「把资产按镜头语言排布」。

## 二、每个角色必须锁定的视觉身份（visual_lock）

`visual_lock` 是一段**一字不改**的固定描述，覆盖：

| 维度 | 字段 | 示例 |
|------|------|------|
| 年龄/气质 | `age_temperament` | 「二十出头将门孤女，隐忍冷冽」 |
| 五官细节 | `face_detail` | 「凤眼、左眉骨一道旧疤、薄唇」 |
| 发型 | `hair` | 「乌发高束、鬓边一缕垂落」 |
| 服饰 | `costume` | 「绯色交领战袍、玄铁护腕、墨色披风」 |
| 身形 | `physique` | 「清瘦挺拔、身形利落」 |
| 独特标记 | `marks` | 「左眉骨旧疤、右手虎口茧」 |

**铁律**：`fixed_prompt` = 上述维度拼成的**单句模板**，逐镜复制到 prompt 开头，只改后面的动作/场景。`marks` 里的独特标记（疤/痣/胎记/配饰）必须逐镜保留，这是防换脸的最后防线。

## 三、角色三视图（front / side / back）

为严肃连载项目，每个主要角色建三视图资产（送 SD / MJ / 即梦生成后入库）：

- **front（正面全身）**：交代 costume / 身形 / 五官正面，锚定主体识别。
- **side（侧面轮廓）**：交代发型体积、鼻梁/下颌轮廓、披风/武器垂坠，防侧脸崩。
- **back（背面）**：交代发髻/束带/披风背面/武器背负方式，防背身换人。

三视图 + 锚定图包（见下）共同构成角色的「3D 理解」，**比单张参考图降低约 30% 面部漂移**（ailistprime 实测）。

## 四、锚定图包（ref_pack）—— 送图像模型生成资产图

| 视图 | 用途 | 质量要求 |
|------|------|----------|
| `frontal_closeup` 正面近景 | 锁五官（脸型/眼距/鼻/颌） | 1024+，平光，无遮挡，纯色背景 |
| `profile` 侧面 | 锁轮廓（发型/鼻梁/下颌） | 同上，正侧 90° |
| `full_body` 全身 | 锁身材比例 + 服装 | 全身入镜，姿态自然 |

**锚定图铁律**：
- 光线均匀、面部清晰、无遮挡；**不用远景/逆光劣质图**做锚定（决定一致性上限）。
- **中途绝不更换锚定图**——哪怕换同角色另一张，AI 也会产生新偏差。
- 即梦 @引用最多 9 张，主角配 2–3 张（正面近景/侧面/全身）即跨镜稳定（18183 实测相似度 ~90%+）。

## 五、一致性规则（consistency_rules）

1. 每镜 prompt 开头固定拼接 `fixed_prompt`（一字不改）。
2. 中途不换锚定图 / 参考图。
3. `marks` 独特标记逐镜保留。
4. 可选：连续多镜固定 seed / 采样参数，减少随机波动（进阶）。
5. 专业级：角色专属 LoRA（15–30 张多角度人像，相似度 90–95%）或 IP-Adapter-FaceID（1–3 张参考，75–85%）——本 skill 提供 prompt 层锚定，LoRA/IP-Adapter 交给生产工具。

## 六、产出契约 character_manifest.json

```json
{
  "characters": [
    {
      "id": "char_zhao",
      "name": "沈昭",
      "role": "主角",
      "visual_lock": "二十出头将门孤女，隐忍冷冽；凤眼、左眉骨旧疤、薄唇；乌发高束鬓边垂缕；绯色交领战袍、玄铁护腕、墨色披风；清瘦挺拔",
      "fixed_prompt": "Shen Zhao, a sharp-faced young woman in her early twenties, phoenix eyes with an old scar above her left brow, thin lips, high-bound black hair with one loose strand, crimson cross-collar battle robe, black iron bracers, ink-black cape, slender and upright",
      "three_view": {
        "front": {"ref_image": "char_zhao_front.png", "desc": "正面全身：绯袍交领右衽，护腕，披风垂坠"},
        "side":  {"ref_image": "char_zhao_side.png",  "desc": "侧面：发髻体积、鼻梁下颌线、披风垂坠"},
        "back":  {"ref_image": "char_zhao_back.png",  "desc": "背面：发髻束带、披风背面、无武器背负"}
      },
      "ref_pack": {
        "frontal_closeup": "char_zhao_face.png",
        "profile": "char_zhao_profile.png",
        "full_body": "char_zhao_full.png"
      },
      "consistency_rules": [
        "每镜 prompt 开头固定拼接 fixed_prompt",
        "中途不换锚定图",
        "左眉骨旧疤、玄铁护腕逐镜保留"
      ]
    }
  ]
}
```

门禁（`validate_pipeline.py`）会校验：每个 `characters[]` 必须有 `id / name / visual_lock / fixed_prompt` 与 `three_view`（front/side/back 三键齐全）。

## 借鉴延伸：《万物生》五类锚定矩阵与双层 STYLE LOCK（方法论借鉴，不照搬）

爆款 AI 漫剧《万物生》（抖音 300万赞，148 节点）沉淀出两条可复用的工业化原则，与本技能的「资产优先」完全同构：

**1. 五类锚定矩阵（cross-segment 不变形）**
把一致性风险拆成五类锚点，跨段落 / 跨镜恒定：
- 角色锚 → `character_manifest.json`（`visual_lock` / `fixed_prompt` / `three_view`）
- 场景锚 → `scene_manifest.json`（`geography` / `axis_of_action` / `views`）
- 色卡锚 → `visual_manifest.json` 的 `palette`（如「大漠残兵色板 10 色」主色贯穿全片）
- 音色锚 → `audio_manifest.json`（角色声线 / BGM 基调）
- 故事板锚 → S3 `storyboard.json` 的 `character_ref` / `scene_ref` 引用

→ 五锚齐全，S3 分镜只需「排布」而非「重建」，漂移概率骤降。

**2. 双层 STYLE LOCK（统一但不单调）**
- 底层（永不动）：角色固定描述 `fixed_prompt` + 胶片质感基调 —— 锁死身份。
- 上层（每段换）：类型调性（麦克斯追逐 / 猫鼠喜剧 / 钢铁侠变身）—— 用 S3 每镜的 `style_variation` 字段承载，不破坏底层锚定。

> 这正是本技能「先资产（底层锁死）后分镜（上层变调）」的设计哲学，案例佐证而非新发明。详见 `references/case-studies.md`。

## 七、IP 防火墙衔接

角色资产**一律原创**。若用户点名某爆款角色，只提取「方法层骨架」（如「强宿命感黑衣男主」），转成原创 `visual_lock`，**不得同名同设定照搬**（详见 `negative-ip-firewall.md` §六）。恒定负向词令牌仍由 S3 门禁强制校验。
