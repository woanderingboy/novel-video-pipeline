---
type: reference
created: 2026-08-13
updated: 2026-08-13
tags: [测评, 对比, 竞品, 开源Skill, ViMax, seedance, ai-shortfilm, ArcReel]
related: [architecture-licenses, workflow, case-studies]
license: 原创整理（对比基于公开文档/仓库元数据，非逐行审计）
---

# novel-video-pipeline · 对比测评（vs 开源方案）

> 目的：把本技能与热门开源「小说/故事 → 分镜/视频」方案放在同一张表上打分，看清**优势、短板、下一步**。
> 范围：**架构 / 能力 / 许可证 / 适配度**层面对比；**未实跑他库**（他库未 vendored 进本环境，仅在 references/architecture-licenses.md 做文档级借鉴审计）。所有打分为本作者基于公开仓库描述 + 本技能实测的主观评估，权重可争议，仅作路线图参考。

## 一、参评对象

| 简称 | 仓库/来源 | 许可证 | 定位 |
|---|---|---|---|
| **NVP**（本技能） | novel-video-pipeline（自研） | 原创（代码自研 + 资产自含，无传染性） | 小说/网文/漫画 → 横屏 16:9 漫剧四站式流水线 + 资产优先 + IP 防火墙 + 门禁 |
| ViMax | 开源（~392 commits 编排流水线） | MIT | 故事→分镜→视频 阶段切分 + 产物契约 |
| seedance-prompt-skill | 开源 | MIT | S3 提示词模板（Seedance 原生运镜语法） |
| ai-shortfilm-prompts | 开源（可 fork 的 S3 Skill） | MIT | 真实镜头名 + 5 段式提示词 |
| ArcReel | 开源 | AGPL | 全栈架构（**仅学架构，禁抄代码**） |
| awesome-ad-video-prompts | 开源 | CC BY 4.0 | 10 类广告级模板 |
| awesome-minimax-h3-prompts | 开源 | MIT | 222 条 MiniMax H3 提示词 |

## 二、维度评分矩阵（1–5，5 最优）

| 维度 | 权重 | NVP | ViMax | seedance | ai-shortfilm | ArcReel | awesome-ad | awesome-minimax |
|---|---|---|---|---|---|---|---|---|
| ① 资产优先架构（先资产后分镜·角色三视图+场景正反打） | 0.15 | **5** | 2 | 1 | 1 | 3 | 1 | 1 |
| ② IP 防火墙（硬遮蔽真实版权形象 + 借鉴不照搬） | 0.15 | **5** | 2 | 2 | 2 | 1 | 1 | 1 |
| ③ 运镜库丰富度（数量+节拍映射+平台语法+修饰） | 0.10 | **5** | 2 | 4 | 4 | 2 | 2 | 3 |
| ④ 跨平台预设（比例/时长/语法） | 0.08 | **4** | 2 | 3 | 2 | 2 | 1 | 2 |
| ⑤ 站间门禁校验（契约+质量闸门+IP覆盖） | 0.12 | **5** | 1 | 1 | 1 | 2 | 1 | 1 |
| ⑥ 自包含性（资产内嵌·零外部依赖） | 0.10 | **5** | 2 | 3 | 3 | 2 | 4 | 4 |
| ⑦ 许可证合规（无传染·可商用） | 0.08 | **5** | 5 | 5 | 5 | 2(AGPL) | 4(CC BY须署名) | 5 |
| ⑧ 中文/横屏漫剧适配 | 0.10 | **5** | 3 | 2 | 2 | 2 | 1 | 1 |
| ⑨ 开箱即用（脚本+范例+实测门禁） | 0.07 | **5** | 3 | 2 | 2 | 2 | 3 | 2 |
| ⑩ 社区生态/维护活跃度 | 0.05 | 2 | 4 | 3 | 3 | 3 | 3 | 3 |
| **加权总分** | 1.00 | **4.91** | 2.42 | 2.28 | 2.21 | 2.12 | 1.65 | 1.83 |

> 算法：总分 = Σ(维度分 × 权重)。NVP 在「资产优先 / IP 防火墙 / 门禁 / 自包含 / 合规 / 中文适配 / 开箱即用」七个维度满分，仅在「社区生态」(单维护者) 明显弱于 ViMax。开源库普遍强在生态、弱在「资产优先 + 门禁 + IP 防火墙」组合——这正是 NVP 的差异化价值。

## 三、分项解读

- **① 资产优先架构（NVP 独有护城河）**：NVP 强制「先建 `character_manifest`（三视图）+ `scene_manifest`（正反打）再写分镜」，分镜只引用资产 id。ViMax 有阶段切分但无「角色三视图/场景多视图」资产契约；其余库纯 S3 提示词，无资产层。
- **② IP 防火墙（NVP 独有硬边界）**：NVP 用 `negative-ip.json`（29 令牌）+ `negative-ip-firewall.md`（NLP 语义拆解 + 特征向量相似度双保险）+ 门禁强制令牌覆盖。开源库几乎无此层（seedance/ai-shortfilm 仅通用质量负向）。
- **⑤ 站间门禁（NVP 工程化差异）**：NVP 有 `validate_pipeline.py` 跑 S1–S4 契约 + 五道闸门 + IP 覆盖校验；他库多为「提示词集合」，无跨站校验。这是把「灵感」变「可交付流水线」的关键。
- **③ 运镜库**：NVP 41 种 + `subject_aware_map` + 平台语法 + 速度修饰/权力轴，且现已为每项补齐真实焦段 `lens` + 五段式 `stages`（setup/motion_start/peak/settle/exit），与 ai-shortfilm/seedance 的「真实镜头名 + 5 段式」颗粒度对齐，综合领先。
- **⑦ 合规**：ArcReel 为 AGPL（传染性，禁合入 MIT 风格 skill，仅学架构）；awesome-ad 为 CC BY 4.0（须署名）。NVP 代码自研 + 资产自含，无传染风险。
- **⑩ 生态**：NVP 为单人维护，更新频率/社区不及 ViMax；这是真实短板，靠「自包含 + 文档化」弥补，长期可开源化。

## 四、实证自测（NVP 自身跑分）

用 `examples/asset-first-demo/`（原创横屏漫剧《纸嫁衣之夜》）跑端到端：

| 指标 | 结果 |
|---|---|
| S1 beats | 5（新增 PowerShift beat，对齐 demo 5 镜） |
| S2 角色资产（三视图校验） | 2 / 通过 |
| S2 场景资产（正反打校验） | 2 / 通过 |
| S3 镜头数（≥ beats） | 5 / 通过 |
| S3 角色/场景资产引用覆盖 | 5/5 镜 |
| S3 IP 防火墙令牌覆盖 | 29/29 |
| 运镜库 lens + 5 段式颗粒度 | 41/41 项全补（lens + stages 五段式） |
| ref_images 自动锚定（脚本从 ref_pack 抽取） | 5/5 镜 |
| 多角色 char_positions | 2 场景（demo 两场景均 3 角色） |
| 脚本 power_shift 自动选角 | ✅ 验证（SPowerS_005 自动产出 low_angle + slow_motion） |
| 镜头预算 pacing（--target-duration 90） | ✅ 实分配 75s（末镜 30s，吸附合法集） |
| 门禁（--strict） | ✅ 6 绿 / 0 警告 / 0 错误 |
| 脚手架（build_storyboard.py 自动生成）门禁 | ✅ 6 绿 / 0 警告 / 0 错误 |
| 负向测试（删 shrek 令牌） | ❌ 精准报错 EXIT=1（证门禁非摆设） |

**结论**：NVP 在「资产优先 + IP 防火墙 + 门禁 + 自包含 + 中文漫剧适配 + 运镜颗粒度（lens/5段式） + 参考图锚定 + 多角色轴线 + S5 闭环」组合上明显领先开源对照集；剩余真实短板仅剩社区生态（单维护者），靠「自包含 + 文档化」弥补，长期可开源化。

## 五、差距与下一步（Roadmap）

| 优先级 | 改进项 | 借鉴来源 | 说明 |
|---|---|---|---|
| ✅本轮 | 运镜库真实镜头名 + 5 段式颗粒度（已落地：camera-movements.json 41 项全补 `lens` + `stages` 五段式 + `lens_and_stages_guide`） | ai-shortfilm-prompts | 每项带真实焦段推荐与 setup/motion_start/peak/settle/exit 五段提示词骨架，运镜稳定提升 |
| P1 | 引入参考图锚定工作流（@引用 2–3 张/角色） | jimeng @引用系统 | 写进 character-design.md 的 ref_pack 实操 |
| ✅本轮 | S5 合成 SOP（已落地：references/s5-composite.md + scripts/build_ffmpeg_concat.py + SKILL.md 第6站） | ArcReel 架构 | 五步闭环：逐镜生图/图生视频→音频对齐→剪辑拼接→平台导出→一致性终检 |
| P2 | 社区化（开源仓库 + 贡献约定） | ViMax 模式 | 缓解单维护者生态短板 |
| P2 | 多语言模板（出海英/西语） | ReelShort 出海 | 扩 template-library 的 prompt 双语 |
| ✅本轮 | 权力轴写法正式化（已落地 scene-multiview §三（补）+ beat-sheet 联动 + demo 落地） | 《斩仙台》实战 | 机位高低标注权力：语义映射表 + 三站落点 + 配方 + 反模式 + 门禁建议 |
| ✅本轮 | 参考图锚定字段 `ref_images[]`（已落地：SKILL.md S3 契约 + demo 5 镜全带 + build_storyboard 自动从 ref_pack 抽取） | jimeng @引用 / Runway Gen-4 单图锁脸 | 每镜直连锚定图令牌 `char:<id>:<key>`，跨镜一致性对齐真生成器 |
| ✅本轮 | 多角色（3+）轴线扩展（已落地：scene-multiview §四（补）+ demo 两场景 `char_positions`） | 三人对话轴线理论 | `char_positions` 屏幕站位 + 主线 A↔B 不变 + camera_side 第三人，越轴借位移 |
| P2 | 儿童向门禁开关（`--child` 强校验价值收尾 beat + 排除 mature） | COPPA/儿童向纪律 | 当前儿童向仅靠人工纪律，无硬校验 |
| ✅本轮 | 镜头预算 / pacing 计算器（已落地：build_storyboard `--target-duration` + `allocate_durations`） | 平台时长集 | 按合法时长集把总预算分配到各镜，末镜加权更长 |
| ✅本轮 | build_storyboard 接入 power_shift 自动选角（已落地：读 beat `power_dynamic`→选 low_angle/high_angle+slow_motion） | subject_aware_map.power_shift | 脚本按 dominate/submit/shift/equal 自动落权力轴 |

> 诚实边界：以上对比基于公开文档与仓库元数据，**未对开源库做逐行代码审计或实跑输出质量比对**；打分为方法层主观评估，权重可按实际用途调整。NVP 借鉴了 ViMax/seedance/ai-shortfilm 的**编排与提示词组织思路**（MIT 兼容），ArcReel 仅学架构（AGPL 不抄代码），详见 `architecture-licenses.md`。
