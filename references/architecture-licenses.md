# 架构借鉴与许可证边界（novel-video-pipeline）

本 skill 站在热门开源方案的「肩膀」上做编排方法论，但**代码自研、资产自包含**，不 fork 任何外部代码库。下面记录借鉴来源与许可证红线，便于后续合规审计与扩展。

## 借鉴来源与许可证

| 项目 | 许可证 | 借鉴点 | 使用方式 | 红线 |
|------|--------|--------|----------|------|
| **ViMax** | MIT | S1→S4 阶段切分、产物契约（story→storyboard→video）、多 Agent 协作思路 | 方法论参照（流程设计） | 可 fork / 改；但本 skill 自研实现，不拷其 Node 代码 |
| **seedance-prompt-skill** | MIT | SKILL 格式的提示词模板组织、seedance 平台 prompt 语法 | S3 底座参照 | 可 fork / 改；模板为本库原创 |
| **ai-shortfilm-prompts** | MIT | 短视频分镜提示词结构（镜头/运镜/情绪标签） | S3 标签体系参照 | 可 fork / 改 |
| **ArcReel** | **AGPL** | 端到端「漫画→视频」编排架构 | **仅学架构，不抄代码** | AGPL 传染性：任何合入本 MIT 风格 skill 的代码都必须开源；故只借鉴架构图，不引入其源码 |
| **Seedance Prompting Guide** | 文档（非代码） | 15+ 原生运镜术语 + `camera_fixed=false` 语法 + 动词强度/时序词方法论 | S3 运镜库 `camera-movements.json` 底座；平台语法注解 | 公开文档，无许可证传染性，方法可自由采用 |
| **aishotstudio 42 Camera Movements** | 文档 | 42 个运镜清单（truck/pedestal/orbit 180·360/reveal/through/fisheye/FPV/bullet time 等） | 补全运镜库条目广度 | 公开文档，方法可自由采用 |
| **zsky.ai Camera Guide** | 文档 | 「每镜单一主运动」铁律 + 五层结构示例 | `rule_single_primary` 规则来源 | 公开文档，方法可自由采用 |
| **jnmetacode/ai-shortfilm-prompts** | MIT | 真实镜头名 + 5 段式结构 + 模型专属建议 | 运镜条目 `name_en` 真实镜头名 + prompt 模板风格 | MIT，可 fork / 改（已在表中） |
| **18183《AI短剧角色锁定》** | 文档 | 锚定图法（正面近景/侧面/全身）+ 固定 prompt 模板一字不改 | `character-design.md` 一致性方法论来源 | 公开文档，方法可自由采用 |
| **xie.infoq.cn《AI漫剧角色一致性》** | 文档 | 角色三视图准备 → IP-Adapter → ControlNet 流程 | `character-design.md` 三视图资产设计 | 公开文档，方法可自由采用 |
| **hellokit《AI漫剧爆发在即》** | 文档 | 角色三视图（正/侧/背）确立 + 分镜批量生成工业化流程 | 资产库「先建角色/场景资产再写分镜」顺序 | 公开文档，方法可自由采用 |
| **shot-reverse-shot（MasterClass / howtofilmschool）** | 文档 | master→OTS→reverse→eyeline match→180 度轴线 | `scene-multiview.md` 正反打多视图方法论来源 | 公开文档，方法可自由采用 |

> 结论：ViMax / seedance-prompt-skill / ai-shortfilm-prompts 均为 **MIT**，可放心 fork / 改写；**ArcReel 为 AGPL，仅学架构**；其余 **Seedance Guide / aishotstudio / zsky / 18183 / xie.infoq / hellokit / shot-reverse-shot 均为公开文档或方法论述**，无代码传染性，本 skill 取其**方法层骨架**（运镜术语、单一主运动规则、角色三视图/锚定图、正反打轴线）做原创整理，不复制任何受版权保护的文本/图像/代码。本 skill 保持「原生编排 + 自包含资产」。

## 为什么不用 Fork ViMax 真实代码

- ViMax 为 Node 运行时（agents / agent_runtime / prompts / 392+ commits），调度模型与 WorkBuddy 的 Skill 执行模型不同，直接合入需大量适配。
- 其体积大、依赖重，违背「轻量可多机复制」目标。
- 本 skill 取其**编排思想的精华**（四站顺序 + 产物契约），用纯标准库 Python 重写三个实用脚本，体积 < 30KB。

## 资产许可证归因

- S1 全部为**结构/写法层范式**（公版故事结构、改编方法论），不含任何版权文本；范例取自公版戏剧（罗密欧与朱丽叶）与用户自有改编（西游记）。
- S2 视觉资产仅来自 **Public Domain / CC0** 源：Old Book Illustrations（全站 PD）、Openverse CC0、Met Museum Open Access（isPublicDomain）。
- S4 音频仅 **CC0**（Openverse/Freesound），Pixabay 为可选「免费可商用不可转售」扩充通道。
- 若将来引入 **CC BY 4.0** 数据（如某些 Freesound 条目），必须在 `storyboard.json` / `audio_manifest.json` 的 `attribution` 字段保留原作者与许可链接——这是 CC BY 的法定义务，不可省略。

## 扩展源（需凭据，当前未启用）

| 源 | 凭据 | 状态 | 申请地址 |
|----|------|------|----------|
| BHL（Biodiversity Heritage Library）API2 | 免费 API key | 占位 `fetch_bhl()`，无 key 跳过 | https://www.biodiversitylibrary.org/getapikey |
| NYPL（New York Public Library）数字藏品 | 免费 token（且站有 Imperva 反爬） | 占位 `fetch_nypl()`，无 token 跳过 | https://api.repo.nypl.org |

> OBI 已验证**无需 key** 即可稳定拉取，是当前主攻源；BHL/NYPL 留通道待凭据补齐。

## 已验证的踩坑（爬取类脚本复用）

1. **SSL 断流**：本环境 Python `urllib` 偶发 `SSL: UNEXPECTED_EOF_WHILE_READING` → OBI 传输改用系统 `curl -k --retry 5 --retry-all-errors` 子进程引擎。
2. **翻页末页陷阱**：OBI 超出实际页数返回**重复末页**而非空页 → 末页判据用「相邻页无新增 slug 即停」。
3. **high-res 非数字 id**：greenaway/brooke 的 high-res 目录 id 含字母连字符（如 `n-d-1886`）→ 正则由 `[0-9]+` 改为 `[0-9A-Za-z._-]+`，尺寸优先级 (1600,1200) 优先更大图。
4. **JPEG 尺寸免 Pillow**：用标准库 `struct` 解析 SOF0/1/2/3 marker 取宽高，避免重依赖。
