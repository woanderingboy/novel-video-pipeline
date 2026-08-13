---
title: 场景资产设计（正反打多视图）
created: 2026-08-13
updated: 2026-08-13
tags: [场景资产, 正反打, 过肩, 180度轴线, 资产库, S2]
---

# 场景资产设计 · 根据剧本全局建立「场景正反打多视图」

> 来源方法论：综合 shot-reverse-shot 影视语法（MasterClass / howtofilmschool / filmdistrictdubai）——**master shot → OTS → reverse → eyeline match → 180 度轴线**。这是对话/对峙戏的骨架，也是 AI 漫剧最该先建「场景资产」的原因：分镜直接引用场景视图，保证空间连续与屏幕方向一致。

## 一、为什么先建场景资产

每个对话/对峙场景若不预先定义空间关系，分镜容易：① 角色忽左忽右（跨轴）；② 视线对不上（eyeline 错位）；③ 缺交代镜头（观众不知谁在哪）。

**S2 阶段通读 S1 全部 scenes/beats**，为每个主要场景建立 `scene_manifest.json`：定义 `axis_of_action`（动作轴线）、`geography`（空间陈设）、`views`（各机位视图）。S3 分镜引用 `scene_ref.view` 即可自动套用正确机位与轴线。

## 二、每个场景必须定义的视图（views）

| 视图 key | 中文 | 作用 | 典型机位 |
|----------|------|------|----------|
| `establishing` | 主镜头/交代镜 | 双人同框全景，交代空间与谁在场（兼做 establishing） | wide static / slow crane |
| `ots_a` | 过 A 肩拍 B | 从 A 肩后框住 B，对话/对峙主句型 | OTS eye-level |
| `ots_b` | 过 B 肩拍 A（反打） | `ots_a` 的反向，保持 180 度轴线 | OTS reverse eye-level |
| `reverse` | 干净单人中景 | clean single / 反角，强调反应 | MCU static |
| `insert` | 细节插入 | 道具/文件/手部特写，转场或线索 | ECU rack focus |
| `fifty_fifty` | 50-50 对峙 | 双方面侧脸对切（各占半幅），正面硬碰硬、压迫感最强 | profile two-shot |
| `french_over` | 过背（French-over） | 从两人背后拍私密对话，半遮表情、压低光线，适合密谋 | over-the-back dim |

## 三、180 度轴线规则（axis_of_action）

- 在 A、B 之间 imaginary 一条线（axis of action）。**相机始终留在轴线一侧**（≤180°），角色屏幕方向才一致：A 在画面左看右、B 在画面右看左。
- 跨轴会让角色「互换左右」，破坏空间逻辑 → 门禁会在 `scene_ref` 引用不一致时 warn。
- **eyeline match**：A 看向画面右、B 看向画面左，所有正反打保持同侧视线。

## 三（补）· 权力的视觉轴（权力轴）——用机位高低标注强弱

> 借鉴来源：shot-reverse-shot 权力语义理论 + 《斩仙台 AI 真人版》"仰拍拉特写，再切慢动作"实战。权力轴与动作轴（180° 视线轴）**正交**：改权力不改变空间连续性，但高低角本身仍须共轴（≤180°），不得借权力轴越轴。

正反打不只是「谁在说话」，还能用**机位高低**直接标注人物权力关系。这是一层**语义轴**，叠加在 `ots_a/ots_b/reverse/fifty_fifty` 之上，不新增视图 key——S3 写分镜时通过 `camera_movement` 选 `low_angle` / `high_angle` 实现。

### 3-补.1 语义映射表（机位 → 权力）

| 机位 / 运动 | 权力语义 | 适用情境 | 对应 camera id |
|------|------|------|------|
| 低角度（仰拍） | 强势 / 威压 / 英雄感 | 战力对峙、反派亮剑、主角觉醒 | `low_angle` |
| 高角度（俯拍） | 弱势 / 被压制 / 被揭穿 | 主角受困、落败、孤立 | `high_angle` |
| 升格（摇臂升 / 垂直升 / 上摇） | 赋予力量 / 宏大 | 英雄登场、觉醒瞬间 | `crane_up` / `pedestal_up` / `tilt_up` |
| 眼平 OTS / 双人镜 | 平权对话 | 势均力敌的谈判、对峙 | `ots` / `two_shot` |
| 慢动作（修饰） | 拉长权力时刻 | 关键对峙 / 揭示瞬间 | `slow_motion`（speed 修饰） |

### 3-补.2 三站落点（怎么写）

- **S1 节拍表（beat-sheet）**：给权力变化的节拍标 `power_dynamic`（取值 `dominate` 强势 / `submit` 弱势 / `equal` 平权 / `shift` 反转）。`camera-movements.json` 的 `subject_aware_map` 已内置 `power_shift` 推荐运镜（`low_angle / high_angle / crane_up / tilt_up / slow_motion`）。
- **S2 场景资产（scene_manifest）**：场景级加 `power_notes` 描述整体权力关系；在 `views` 上为关键正反打标注 `default_power`（如 `ots_a` 默认仰拍强势方、`ots_b` 默认俯拍弱势方）。`axis_of_action` 不变，权力轴叠加其上。
- **S3 分镜（storyboard）**：`camera_movement` 选 `low_angle` / `high_angle`，配 `speed: "slow_motion"` 拉长情绪；`shot_size` 用 `CU/MCU` 拉特写。完整写法：`{camera_movement:"low_angle", shot_size:"CU", speed:"slow_motion"}`。

### 3-补.3 权力配方（可直接套）

| 情境 | 配方 | 说明 |
|------|------|------|
| 觉醒 / 亮剑 | `low_angle` + `CU` + `slow_motion` | 仰拍特写拉长觉醒瞬间 |
| 压制 / 威压 | `low_angle`（强势方,`MCU`）↔ `high_angle`（弱势方,`MS`） | 正反打落差强化权力差 |
| 权力反转 | 前 `high_angle`（弱势）→ 切 `low_angle`（反转主导）+ `whip_pan` | 转场即反转，落差动 |
| 平权谈判 | 眼平 `ots` ↔ `ots_reverse`，不用高低角 | 势均力敌、不偏袒 |

### 3-补.4 实战范例（storyboard 片段 · 雨巷权力反转）

```json
{
  "shot_id": "S1_005",
  "beat_ref": "PowerShift",
  "character_ref": [{"char_id": "shen_zhao"}],
  "scene_ref": {"scene_id": "scene_rain_alley", "view": "ots_b"},
  "camera_movement": "low_angle",
  "shot_size": "CU",
  "speed": "slow_motion",
  "prompt": "low-angle close-up of shen_zhao at the north end of a rainy alley, slow motion, rain frozen mid-air, she projects dominance and calm, the ghost-marriage conspiracy broken, 16:9",
  "negative_prompt": "（同全部 IP 防火墙令牌 + 质量负向，门禁强制覆盖）",
  "platform": "bilibili", "aspect_ratio": "16:9", "duration_s": 8, "attribution": ""
}
```

### 3-补.5 反模式 / 校验建议

- **不要为「说话」而高低角**：权力轴只用于权力关系变化（觉醒 / 压制 / 反转）的时刻，滥用会削弱语义、观众麻木。平权对话用眼平 OTS 即可。
- **高低角仍须共轴**：`ots_a` 仰拍强势方、`ots_b` 俯拍弱势方时，两者仍须留在 180° 轴线同侧，否则跨轴破坏空间逻辑。
- **景别仍须匹配**：配对正反打即便一方仰一方俯，景别也要 `MCU↔MCU`，否则跳切感。
- **门禁建议（可选）**：场景若声明 `power_notes`，相关 `shot` 宜出现 `low_angle` / `high_angle` 之一；可在 `validate_pipeline.py` 加 warn 级校验（当前未强制）。

## 四（补）· 多角色（3+）轴线——三人及以上对话戏的空间方法

> 当前 `axis_of_action` 默认建模 **A↔B 双人视线轴**。但漫剧里三人/四人对话戏极常见（如茶馆命案：沈昭 + 顾言 + 凶手同场）。核心原则：**主冲突线的 180° 轴线始终不变，第三角色靠「站位归属」而非「新轴线」解决**。

### 4-补.1 站位归属（char_positions）

在 `scene_manifest.json` 的每个 `scenes[]` 加可选 `char_positions`，把每个在场角色映射到屏幕与轴线关系：

```json
"char_positions": {
  "shen_zhao": {"screen": "left",  "side_of_axis": "action_line", "note": "主角，始终在画面左看右，属主冲突线 A 端"},
  "gu_yan":    {"screen": "center","side_of_axis": "camera_side", "note": "助手，置相机侧（线同侧）作前景/反应，不参与 A↔B 视线交换"},
  "killer":    {"screen": "right", "side_of_axis": "action_line", "note": "反派，画面右看左，属主冲突线 B 端"}
}
```

- `screen`：`left` / `right` / `center` —— 角色在画面中的基本方位（左屏看右、右屏看左、中屏朝向镜头或侧对）。
- `side_of_axis`：`action_line`（站在 A↔B 主冲突线上，参与视线交换）或 `camera_side`（站在 180° 线同侧的「观众侧」，作为前景/反应，不破坏轴线）。

### 4-补.2 三种三人戏处理法

| 情境 | 做法 | 说明 |
|------|------|------|
| 三人同框建关系 | `establishing` / `group_shot` 全景先建立三人空间 | 先让观众知道谁在哪，再切正反打 |
| 主冲突（A↔B）驱动，C 旁观 | C 置 `camera_side` 作 OTS 前景或 `reverse` 单人中景 | C 不进入 A↔B 视线交换，轴线安全 |
| C 介入打破平衡 | 借 C 的「位移入场」（如从西墙缺口切入）合法越轴 | 越轴必须靠可见位移过渡，不可硬切（demo 雨巷即此） |

### 4-补.3 与权力轴正交

`char_positions`（空间轴）与权力轴（机位高低，见 §三（补））彼此独立、可叠加：例如 `gu_yan` 站 `camera_side`、同时用 `high_angle` 显弱势；`shen_zhao` 站 `action_line` 左端、用 `low_angle` 显主导。两者都不改变 180° 视线轴的连续性。

### 4-补.4 门禁建议（可选）

若场景声明 `char_positions` 且角色数 ≥ 3，分镜不宜让 `camera_side` 角色突然出现在本属于 `action_line` 角色的屏幕反向（越轴）；`validate_pipeline.py` 可加 warn 级提示（当前未强制，靠人工纪律）。

## 四、正反打配对铁律

- `ots_a` 与 `ots_b` **成对出现**，机位绕轴线 180° 反转，不跨轴。
- 匹配景别：若 `ots_a` 是 MCU，其反打 `ots_b` 也用 MCU（否则跳切感）。
- `establishing` 先建立关系，再切 `ots` / `reverse` 驱动情绪交换（two-shot 建立连接，正反打强调对比/反应）。

## 五、产出契约 scene_manifest.json

```json
{
  "scenes": [
    {
      "id": "scene_hall",
      "name": "顾府喜堂",
      "type": "interior",
      "geography": "顾府正厅：红绸灯笼、八仙桌、喜字屏风、窗外夜雨",
      "axis_of_action": "A(沈昭，画面左) ↔ B(顾砚之/宾客，画面右)",
      "views": {
        "establishing": {"desc": "master shot：两人对坐全景，交代喜堂空间", "suggested_camera": "wide static / slow crane"},
        "ots_a":        {"desc": "过沈昭肩拍顾砚之", "subject": "顾砚之", "foreground": "沈昭", "suggested_camera": "OTS eye-level", "default_power": "submit"},
        "ots_b":        {"desc": "过顾砚之肩拍沈昭（反打）", "subject": "沈昭", "foreground": "顾砚之", "suggested_camera": "OTS reverse eye-level", "default_power": "dominate"},
        "reverse":      {"desc": "clean single 沈昭反应", "subject": "沈昭", "suggested_camera": "MCU static"},
        "insert":       {"desc": "退婚书 / 虎符细节", "subject": "prop", "suggested_camera": "ECU rack focus"}
      },
      "power_notes": "嫡女沈昭压顾砚之：正反打用 ots_a(俯拍顾砚之=submit) ↔ ots_b(仰拍沈昭=dominate) 强化权力落差；觉醒瞬间可加 slow_motion。",
      "eyeline_match": "沈昭看向画面右、顾砚之看向画面左，保持 180 度轴线"
    }
  ]
}
```

门禁（`validate_pipeline.py`）会校验：每个 `scenes[]` 必须有 `id / name / geography / axis_of_action` 与 `views`（至少含 `establishing` + `ots_a`/`ots_b` 其一 + `reverse`）。

## 六、IP 防火墙衔接

场景资产（陈设/美术）原创；**招牌画风 / 标志性配色组合不可复刻**热门 IP 场景（详见 `negative-ip-firewall.md` §六）。恒定负向词令牌仍由 S3 门禁强制校验。
