# 题库与结构化数据 · 需求文档

| 项 | 值 |
|---|---|
| 版本 | **v0.3（修订稿）** |
| 日期 | 2026-11-07 |
| 位置 | `mem/doc/question-bank.md` |
| 目标读者 | 在 `mem` 仓库实现题库索引的 agent；**索引的首要消费者也是 agent** |
| 关联 | `mem/AGENTS.md`（批改流程、统计口径、Git 约定）；`mem/readme.md` |

> 本索引只定义「题目身份与作答索引」这一件事，不改变现有 Markdown 复习流程。**Markdown 是唯一真源，索引是自动生成的导航层**：题干不进索引，索引里的每条记录都必须能回指原文；agent 查到结论后仍回 Markdown 核验。

**v0.2 修订依据**：2026-11-07 按仓库 Markdown 原文逐份清点，修正 v0.1 中由网站解析口径（`explicit / table / headings / none`）反推造成的事实误判；把产物从「三份手写 JSON」改为「一份脚本生成的索引」，并明确服务 agent 的场景。

**v0.3 变更**：`duration` 允许为空，未记时长是合法状态而非数据缺口；计时粒度从场次级扩展到题目级，新增 `sessions[]` 与 `timingMode`，为后续按题计时预留字段与统计口径。修订摘要见 §11。

---

## 0. 一句话

把散落在 `paper.md` / `answer*.md` / `待重做.md` / 总结里的题目身份与作答，用**稳定 ID** 串成一份由脚本从 Markdown 生成的索引；agent 一次读取即可定位、回溯、核对，不引入 SQLite、不手写索引、不复制题干。

---

## 1. 背景与目标

### 1.1 为什么需要

现在能回答「哪天学了多久、哪卷做了多少题、卷面正确率多少」，但回答不了：

- 这道题我做过几次？上次错在哪？
- 某个考点（如「路程问题」）我一共错了多少题？
- 待重做的 12 题，分别对应题库里的哪一题？
- 我想按考点筛题、组一套练习。
- 新写一份 `answer` 时：这题以前错过几次、错因是什么、待重做清单里销账了没有？

这些都需要**题目级 ID**，而现在的 Markdown 没有。

**成本主要在 agent 一侧**：本仓四十多个 md、31 份 answer 文件；判定写法有四种，题号列写法有三种，还有 `## Q35 ~ 36` 这类合并标题。每次会话要回答一个跨卷问题，都得重新读十几个文件并在上下文里拼装，且容易拼错——按 `^## Q\d+` 抓取会把 Q36 判成「没做过」（实际在 `answer2.md` 的合并标题里）。把一次性的梳理成本固化下来，是做索引的主要理由，比「给网站加每题页」更迫切。

这也正是 AGENTS.md「进度按题库实际题号清点，不凭记忆估算」和批改流程第 1 条「逐页转录、回题库核对题号后再判题，不凭记忆对号」对机器版本的要求：索引负责定位，原文负责事实。

### 1.2 目标

| 目标 | 说明 |
|---|---|
| 稳定 ID | 每道题一个永不复用的 ID，题库、作答、错题本共用 |
| 题目索引 | 一题一条：卷、题号、板块、考点、题型、答案及其来源、可评分性 |
| 作答记录 | 一场练习 × 一道题一条；错因、答案、判定可追溯 |
| 一次读取 | agent 读一份索引即可回答跨卷问题，不必每次重新解析十几个 md |
| 可回溯 | 每条记录带 `source` 回指原文路径与题号，一键核验 |
| 可重建 | 索引随时由 Markdown 重新生成；与原文漂移时以原文为准 |
| 批改辅助 | 新作答时能自动查出重题、漏号、答案冲突、待重做是否漏录 |
| 可校验 | 一条命令检查题号覆盖、答案来源、判定一致性 |
| 可持续 | 新增卷/新增作答按同一约定写，不用回头补历史 |

### 1.3 非目标

- ❌ 不引入 SQLite / 任何运行时数据库：二进制、不能 `git diff`、agent 不能直接读，与本仓文本约定冲突
- ❌ 不手写索引：`data/index.json` 标「自动生成，勿手改」
- ❌ 不把题干搬进索引：要独立复算（批改流程第 2 条）必须回 `paper.md`
- ❌ 不改写题目原文（只允许加 front matter、ID 列等结构信息）
- ❌ 不重排题号、不重新编号已有题目
- ❌ 不做在线编辑、CMS、账号系统
- ❌ 不做全文搜索 / 组卷产品（先把数据基础打好）
- ❌ 不改网站代码；**但站点统计已读取 `data/index.json`**，索引是生产数据源而非可选产物（平台 2026-11-07 确认，见 §6.5）

---

## 2. 现状盘点（2026-11-07，按 Markdown 原文复核）

### 2.1 规模

| 卷 | Markdown 源 | 可评分题 | 含主观题 | 已练场次 | 逐题判定条数 |
|---|---|---:|---:|---:|---:|
| 2024 管综真题 | `2024年管综真题/paper.md` | 55 | **57**（+2 篇写作） | 11 | 约 52（部分缺判定） |
| 2025 英语二 | `2025年英语二/paper.md` | 45 | **48**（+翻译 1、写作 2） | 5 | 45 |
| 形式逻辑与综合推理 | `形式逻辑与综合推理/形式逻辑与综合推理一/二.md` | 30（两卷各 15） | 30 | 2 | 30 |
| 专项训练二 | `专项训练二-五大条件类推理题/paper.md` | 30 | 30 | 2（仅 12 题） | 12 |
| 数学应用题 | `数学应用题/应用题.md` | 81 | 81 | 11 | 81 |
| **合计** | | **241** | **246** | **31** | **约 220** |

> 清点依据：2024 `paper.md` 编号 1–57；形式逻辑一/二各 15；专项训练二 1–30；`应用题.md` 81 题（考点分布 10/14/19/1/9/4/4/11/3/6）；英语 45 客观题见 `试卷总结.md` 的完整答案串。网站当前只统计可评分题 241，索引纳入 5 道主观题并用 `scorable:false` 区分，共 246 条。

### 2.2 现有数据的结构差异（v0.2 重写）

**1. 题号不是全局唯一**

- 数学应用题按「考点」重新从 1 编号：考点2 的第 13 题，不是全书的第 13 题。
- 形式逻辑有两卷，每卷各自 1–15。
- 2024 真题是全局 1–55 + 写作 56–57（以卷面题号为准）。
- 专项训练二是全局 1–30；英语 Part B 在 `answer5.md` 里写 `### Q41: A ❌`，与试卷总结的 41–45 一致。

**2. 逐题判定比 v0.1 估计的充分得多**（最重要的修正）

| 卷 | 逐题判定形式 | 条数 |
|---|---|---:|
| 数学应用题 | 11 份「题号 \| 你的答案 \| 正确答案 \| 判定」表 | 81 |
| 形式逻辑 | 两份判定表，各 15 行 | 30 |
| 专项训练二 | 两份判定表（9 + 3） | 12 |
| 英语 | `【A】❌` / `[A]❌` / `### Q41: A ❌` 逐题行 | 45 |
| 2024 | `## Q1 ✅` 15 条 + `### Answer： D ✅` 37 行（33 行带符号） | 约 52 |

合计约 220 条**可直接转成逐题 attempt**，不是 v0.1 说的「只有卷面 a/b，需人工补」。这是「每题级错题追踪」最需要的原料。

**3. 作答格式至少四种**（v0.1 归为三种，且把 2024 判成「无判定」）

| 文件 | 形式 | 说明 |
|---|---|---|
| 2024 `answer1.md` | `## Q1 ✅` + `### answer : E` | 判定在标题；`answer` 行是**用户自己的作答**，不是正确答案 |
| 2024 `answer2–9.md` | `### Answer： D ✅` / `### Answer: B ❌` | 判定在 Answer 行；订正段另给正确答案 |
| 2024 `answer2.md` | `## Q35 ~ 36` + `### Answer 36: C ✅` | 合并题号标题，正则抓取会漏 Q36 |
| 2025 英语 `answer1` | `1. … 【D】❌` | 全角方括号 |
| 2025 英语 `answer2–4` | `21. … [A]❌` | 半角方括号 |
| 2025 英语 `answer5` | `### Q41: A ❌` | 另有翻译原文、逐句订正、两篇写作与估分，全在同一文件 |
| 数学 / 形式逻辑 / 专项二 | 四列判定表 + 显式「卷面 a/b」 | 判定表是主，卷面分只是汇总 |

> v0.1 §5.1 称「answer2–6 只有题号、没有判定，只能记 `correct:null`」与原文不符：这 29 个题号里 27 条有 Answer 行、24 条带明确 ✅/❌。照 v0.1 迁移会白白丢掉约 39 条判定。

**4. 题号列写法不统一**：数学 `answer1` 写 `1`、`answer2` 写 `利润 7`、`answer11` 写 `线规 1`；「正确答案」列还带说明文字（`**B**（最小值 2，无最大值）`、`D（23 天）`），生成脚本需要清洗规则。待重做.md 用的是简称（线规、至少至多），必须靠别名表转换。

**5. 错题清单是人工标签**：`数学应用题/待重做.md` 12 行，来源写 `answer1`、`answer10`，题目写「利润 6」「路程 13」，错因是带公式的自由文本。这些标签不是稳定 ID。

**6. 主观题**：2024 写作两篇估分 18/30、21/35；英语翻译 8/15、写作 A 6/10、写作 B 8/15。均无客观判定，`answerStatus: estimated` 存不下分数，需要 `score` 字段。

**7. 错因标签字典不齐**：AGENTS.md 列 6 类（模型选错 / 约束遗漏 / 倍数搞错 / 移项·符号 / 算术笔误 / 书写跳步），但 `全书总结.md` 的 13 道错题实际出现 8 类，多「方程设错」「填涂失误」；`待重做.md` 还有「算术笔误 + 书写跳步」这种复合标签。v0.1 「沿用五类」既数错数量，也装不下真实数据。

**8. 计时口径现状：31 场里 15 场有场次级 `duration`**（数学 11 + 形式逻辑 2 + 专项二 2），2024 全部 11 场、英语 5 场没有。**`duration` 允许为空**：未记时长是合法状态，不估算、不追问补录、不计入速度统计。现有 15 场都是整场用时，且口径并不纯——`形式逻辑与综合推理/answer1/answer1-1.md` 明确写「36 min 含当场对照订正时间，纯作答用时草稿未拆分」。后续若改为按题目计时，两种粒度的分母口径不同，数据模型与统计规则须一次预留到位（§4.5）。

**9. 题干更正历史**：git log 有两条「修正专项训练二第 4 题条件 (3) 转录」（补回「不售卖杨桃」的「不」字；「不选择丁」改「不选择壬」）。2026-11-07 对照原卷答案速查又发现 **2024 第 25 题条件 (2) 误录 $S_6=26$（原卷为 $S_9=26$）**，据此订正的正确答案 C 也跟着错，已改为 E。题目内容变过而 ID 不变，更正前的 attempt 基于旧题干，需要 `revision` 标记，否则「上次错在哪」会给出误导答案。

### 2.3 关于 v0.1 的网站聚合数字

v0.1 §2.3 把网站解析结果（31 场、15 场 duration、解析来源 explicit 15 / table 2 / lines 6 / headings 5 / none 2）当作交叉校验基准，**这正是 §2.2 几处误判的来源**：解析器把 2024 的 `### Answer： D ✅` 归成 headings/lines，没识别出其中的答案字母与判定；把数学归成「显式卷面」，忽略了 81 行判定表。

修正后的口径：

- **事实基准是 Markdown 原文**，按 AGENTS.md「按题库实际题号清点」；解析结果只作参考。
- 本仓不存在 `doc/requirements.md` 和网站代码，§3.1 的 slug 依据无法在本仓验证，因此 slug 字典收进本仓，ID 不随外部系统改名。
- 索引生成后，题量、场次、正确率应与原文清点结果一致；对不上时回原文复核，不反过来改原文去迁就索引。

---

## 3. ID 规则（必须先定，再写解析脚本）

### 3.1 卷 slug

沿用 v0.1 已用的 slug，避免两套命名；**该字典收进本仓 `volumes.json`，作为唯一依据**：

| 卷 | slug |
|---|---|
| 2024 管综真题 | `2024-exam` |
| 2025 英语二 | `2025-english` |
| 形式逻辑与综合推理 | `formal-logic` |
| 专项训练二-五大条件类推理题 | `reasoning-2` |
| 数学应用题 | `math-applied` |

### 3.2 题目 ID 格式

统一小写 ASCII、`-` 分隔；**一经分配永不复用、永不重排**。位数按卷固定：真题/英语用 3 位，其余用 2 位（本仓单卷最多 81 题，2 位够用）。

| 卷 | 格式 | 示例 |
|---|---|---|
| 2024 真题客观题 | `2024-exam-q<nnn>` | `2024-exam-q001` … `q055` |
| 2024 写作 | `2024-exam-essay1` / `essay2` | `2024-exam-essay1`（论证有效性分析） |
| 英语客观题 | `2025-english-q<nnn>` | `2025-english-q001` … `q045` |
| 英语翻译/写作 | `2025-english-translation` / `writing-a` / `writing-b` | `2025-english-writing-a` |
| 形式逻辑卷一 | `formal-logic-p1-q<nn>` | `formal-logic-p1-q01` … `q15` |
| 形式逻辑卷二 | `formal-logic-p2-q<nn>` | `formal-logic-p2-q01` … `q15` |
| 专项训练二 | `reasoning-2-q<nn>` | `reasoning-2-q01` … `q30` |
| 数学应用题 | `math-applied-<topic>-<nn>` | `math-applied-distance-13`（题号补零到 2 位） |

数学的 topic slug 与别名表（**供脚本解析判定表、待重做清单和校验共用，必须手写维护一次**）：

| 考点 | topic | 卷面/待重做里的简称 | 题数 |
|---|---|---|---:|
| 考点1 商品利润 | `profit` | 利润 | 10 |
| 考点2 路程问题 | `distance` | 路程 | 14 |
| 考点3 工程问题 | `engineering` | 工程 | 19 |
| 考点4 交叉比例法 | `cross-ratio` | 交叉、交叉比例 | 1 |
| 考点5 溶液浓度 | `concentration` | 浓度 | 9 |
| 考点6 分段计费 | `tiered-pricing` | 分段 | 4 |
| 考点7 集合 | `sets` | 集合 | 4 |
| 考点8 不定方程 | `diophantine` | 不定方程 | 11 |
| 考点9 线性规划 | `linear-programming` | 线规 | 3 |
| 考点10 至少至多 | `at-least-at-most` | 至少至多 | 6 |
| **合计** | | | **81** |

> 数学的 `number` 字段保留考点内题号（1–N），**不要**强行改成全书 1–81；`id` 里的 topic 已保证唯一。若未来需要全书序号，单独加 `globalIndex`，不要改 ID。

### 3.3 ID 禁忌

- 不要用中文、空格、下划线混排；不要用「第13题」这种随排版变化的字符串当 ID。
- 不要因为发现题号写错就改 ID；题号错了改 `number` / `notes`，ID 保持。
- **题干被更正时 ID 也保持**，用 `revision` 记更正日期与内容，并标记更正前的 attempt 基于旧题干。
- 不要用数组下标当 ID。

---

## 4. 数据模型

### 4.0 产物与职责

```text
mem/
├── data/
│   ├── volumes.json     # 手写：卷元数据 + topic 别名表（少量、稳定）
│   └── index.json       # 自动生成：questions[] + attempts[] + meta，禁止手改
└── scripts/
    ├── build_index.py   # 生成 + 校验一体，零依赖 Python 3.11
    └── query.py         # 只读查询层：筛选、档案、CSV 导出
```

| 文件 | 谁写 | 变更频率 | 说明 |
|---|---|---|---|
| `volumes.json` | 人 | 新增卷/新增考点时 | 唯一的手写结构化文件 |
| `index.json` | `build_index.py` | 每次批改后重生成 | 标「自动生成，勿手改」；丢了可重建 |
| Markdown | 人 | 每次练习 | **唯一内容真源** |

v0.1 的 `questions.json` / `attempts.json` 合并为 `index.json` 的两个数组：agent 一次 Read 拿到全部，不必跨文件拼装。**不设 SQLite**：索引几十 KB，扁平文本对 agent 更友好，且能 `git diff`；JSON 保持 `indent=2`，改一条记录只影响几行 diff。

`scripts/query.py` 是只读查询层，不写任何文件，把常用筛选封装成命令：

```bash
python3 scripts/query.py --topic 路程 --wrong-only       # 按考点筛错题，支持「线规」等简称
python3 scripts/query.py --redo                        # 待重做 12 题
python3 scripts/query.py --error-tag 模型选错           # 按错因筛
python3 scripts/query.py --question math-applied-distance-13   # 单题完整档案
python3 scripts/query.py --topic 路程 --csv > 路程错题.csv     # 给人看的表格视图
```

输出 ID、答案、作答次数、最近结果、错因与 `source` 回链。`--csv` 是**导出视图**（`csv` 模块正确转义 LaTeX 与中文标点），主数据仍是 `index.json`——不把 CSV 当真源，避免第二份要维护的数据。

### 4.1 `volumes.json`（手写）

```json
{
  "version": 1,
  "volumes": [
    {
      "slug": "math-applied",
      "name": "数学应用题",
      "subject": "管综",
      "papers": ["数学应用题/应用题.md"],
      "answerSources": ["数学应用题/answer*/answer*.md"],
      "totalQuestions": 81,
      "scorableQuestions": 81,
      "notes": "题号按考点重新编号；ID 必须带 topic"
    }
  ],
  "topicAliases": {
    "利润": "profit", "路程": "distance", "工程": "engineering",
    "交叉": "cross-ratio", "浓度": "concentration", "分段": "tiered-pricing",
    "集合": "sets", "不定方程": "diophantine", "线规": "linear-programming",
    "至少至多": "at-least-at-most"
  },
  "mathTopics": [
    { "section": 1, "name": "商品利润", "topic": "profit", "count": 10 }
  ]
}
```

| 字段 | 说明 |
|---|---|
| `answerSources` | string[]，答案来源文件（相对 `mem/`，支持 glob），生成 `answerSource` 与校验时用 |
| `answerOverrides` | object，答案的显式订正（题 ID → 字母）；**原文保留不改**，依据写进 `notes`，见 §5.3 |
| `topicAliases` | 判定表与 `待重做.md` 里的中文简称 → topic slug，供 ID 生成、题号映射、映射校验共用 |
| `mathTopics` | 考点序号、名称、slug、题数；用于生成数学 ID、校验题号 1–N 连续 |

`paper.md` 的 front matter 只放稳定标识（`slug`、`subject`），**不放题数**——计数由 `volumes.json` 一处维护，避免第二个计数源漂移。

### 4.2 `index.json`（自动生成）

```json
{
  "meta": {
    "generatedAt": "2026-11-07T01:50:00+08:00",
    "generator": "scripts/build_index.py",
    "sourceFiles": 31,
    "coverage": { "questions": 246, "attempts": 220, "sessions": 31, "redoRows": 12 },
    "timing": { "session": 15, "perQuestion": 0, "mixed": 0, "none": 16 },
    "errors": []
  },
  "questions": [],
  "sessions": [],
  "attempts": []
}
```

四个顶层数组 / 对象：`questions`（§4.3）、`sessions`（§4.5）、`attempts`（§4.4）与 `meta`。此处留空数组以保持示例为合法 JSON，实际内容见各节与附录 B。`meta.timing` 汇总计时口径分布，`none` 是合法值、不进 `errors`；`errors` 非空时索引不可信，必须回原文。

### 4.3 `questions[]` 字段

```json
{
  "id": "math-applied-linear-programming-01",
  "volume": "math-applied",
  "paper": "数学应用题/应用题.md",
  "number": 1,
  "section": "考点9 线性规划",
  "topic": "线规",
  "type": "problem",
  "answer": "B",
  "answerSource": "数学应用题/answer11/answer11.md 判定表",
  "answerStatus": "confirmed",
  "scorable": true,
  "source": "数学应用题/应用题.md#考点9-1",
  "revision": null,
  "notes": null
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | string | ✅ | §3.2 |
| `volume` / `paper` | string | ✅ | 卷 slug / 源文件相对 `mem/` |
| `number` | number | ✅ | 卷面或考点内题号 |
| `section` | string | ✅ | 板块或考点原文 |
| `topic` | string | ✅ | 知识点；用受控词表，无明确考点时填板块名并注明 |
| `type` | enum | ✅ | 见下 |
| `answer` | string/null | ✅ | 客观题答案；主观题 `null` |
| `answerSource` | string | ✅ | **答案从哪来**，见 §4.6；不得以「选项里有这个数」为依据 |
| `answerStatus` | enum | ✅ | `confirmed` / `estimated` / `missing` |
| `scorable` | boolean | ✅ | 能否客观判定 |
| `source` | string | ✅ | 回指原文路径 + 题号，agent 据此核验 |
| `revision` | object/null |  | 题干更正日期、内容、影响的 attempt |
| `tags` / `notes` | |  | 可选标签、特例说明 |

`type`：`problem`（问题求解）、`data-sufficiency`（条件充分性）、`logic`、`cloze`、`reading`、`new-type`、`translation`、`writing`、`essay`。

`answerStatus`：`confirmed`（有明确参考答案）、`estimated`（写作/翻译估分，无唯一答案）、`missing`（暂时没有答案，须显式列出）。

### 4.4 `attempts[]` 字段

```json
{
  "id": "2026-11-04-math-applied-11-linear-programming-01",
  "date": "2026-11-04",
  "sessionId": "math-applied-s11",
  "session": "数学应用题/answer11/answer11.md",
  "questionId": "math-applied-linear-programming-01",
  "userAnswer": "E",
  "correctAnswer": "B",
  "correct": false,
  "substantiveCorrect": false,
  "score": null, "scoreMax": null, "scoreBasis": null,
  "errorTags": ["模型选错"],
  "errorNote": "模型选错（非法复合不等式得假上界，未验有界性）",
  "isRedo": false,
  "durationMin": null,
  "durationSource": null,
  "source": "数学应用题/answer11/answer11.md 判定表首行",
  "verified": true
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | string | ✅ | `date-session-question`；同一题重做产生新记录 |
| `date` / `sessionId` / `session` | string | ✅ | 场次标识；`answer<N>` 在各卷重复，裸路径易混，故另给 `sessionId` |
| `questionId` | string | ✅ | 必须存在于 `questions[]` |
| `userAnswer` / `correctAnswer` | string/null |  | 未作答、主观题用 `null` |
| `correct` | boolean/null | ✅ | `null` = 未判定，不猜 |
| `substantiveCorrect` | boolean/null | ✅ | **卷面 vs 实质**（AGENTS.md 统计口径）。数学全书卷面 68/81、实质 69/81，差的是「利润 3：算出 25% 却选了 12%」；只有一个 `correct` 会与 `全书总结.md` 对不上 |
| `score` / `scoreMax` / `scoreBasis` | |  | 主观题估分，`scoreBasis: "estimated"` 时必填 |
| `errorTags` | string[] |  | 见 §4.7；复合标签用数组，不拼字符串 |
| `errorNote` | string |  | 保留待重做.md 里带公式的原话，不丢信息 |
| `isRedo` | boolean | ✅ | AGENTS.md「隔天不看批改、白纸重做、连续两次做对销账」，重做与首做要能区分 |
| `durationMin` | number/null |  | **该题用时（分钟，可小数）**；按题计时时有值，场次级计时或未计时为 `null` |
| `durationSource` | enum/null |  | `draft`（草稿/作答文件记录）/ `timer`（逐题计时器）；与 `durationMin` 同时有值或同时为空 |
| `source` | string | ✅ | 回指原文（文件 + 判定表行/标题），校验与核验都靠它 |
| `verified` | boolean | ✅ | 是否人工核对过 |

> 一个 `attempt` 只对应一道题、一场练习；同一题重做两次就是两条记录，不要用「上次结果」覆盖旧记录。

### 4.5 `sessions[]` 与计时模型（v0.3 新增）

时长有**两个层级**，都要能表达，且都允许为空：场次总用时记在 `sessions[]`，单题用时记在 `attempts[].durationMin`。Markdown 里 `duration` 是**可选字段**，未记录就整行省略或写 `duration: null`，这是合法状态，不是数据缺口。

```json
{
  "id": "math-applied-s11",
  "date": "2026-11-04",
  "file": "数学应用题/answer11/answer11.md",
  "volume": "math-applied",
  "questionCount": 9,
  "timingMode": "session",
  "durationMin": 76,
  "durationSource": "draft",
  "note": "整场用时；未拆分单题"
}
```

| 字段 | 说明 |
|---|---|
| `timingMode` | `session`（只记整场用时）/ `per-question`（逐题计时）/ `mixed`（部分题有计时）/ `none`（未记时长） |
| `durationMin` | 场次总用时，分钟，数值，`none` 时为 `null` |
| `durationSource` | `draft` / `timer`；与 `durationMin` 同时有值或同时为空 |
| `questionCount` | 本场题数，用于校验与速度分母 |

**Markdown 侧写法**：`duration` 兼容现有 `76min`、`36 min` 两种带单位写法，脚本统一解析为数值分钟。

```yaml
---
time: 2026-11-04 07:35
file: 应用题.md
duration: 76min        # 可选；未记录就整行省略
timingMode: session    # 可选；省略时按 duration 有无推断
---
```

按题计时时，在判定表追加「用时」列，或在逐题行末标注，两者都可解析：

```markdown
| 题号 | 你的答案 | 正确答案 | 判定 | ID | 用时 |
|---|---|---|---|---|---|
| 线规 1 | E | B | ❌ 假上界 | math-applied-linear-programming-01 | 4.5 |
```

或写 `### Q41: A ❌（2.5min）`。此时 `timingMode: per-question`，逐题用时写入 `attempts[].durationMin`，场次总用时可同时保留供交叉校验。

**速度口径**（对应 AGENTS.md「统计口径」）：

| 模式 | 单场速度 | 累计轨迹 |
|---|---|---|
| `session` | `sessions.durationMin ÷ questionCount`（现行口径） | 计入 |
| `per-question` | `Σ attempts.durationMin ÷ 有计时的题数`；另可给每题、分考点速度 | 计入，**另起一条轨迹** |
| `mixed` | 只对有计时的题算，注明覆盖率 | 分列 |
| `none` | 不计算，速度栏写「未计时」 | **不参与**，不估算 |

> **两种口径不能混着平均**：整场用时可能含订正、翻页、休息（`answer1-1.md` 的 36 min 就含当场订正），逐题用时通常只含解题。按题计时上线后，累计速度轨迹应单独起一条，不要和现有的 6.7 → 3.75 → 10.0 → 2.7 min/题 直接接在一起。

### 4.6 答案来源

`paper.md` 按 AGENTS.md 不写答案，因此 241 个答案必须从下列来源逐卷取，并逐条写 `answerSource`：

| 卷 | 答案来源 | 风险 |
|---|---|---|
| 专项训练二 | `答案速查.md`（30 题全） | 题干曾更正，需核对速查表对应版本 |
| 2025 英语二 | `试卷总结.md` 的完整答案串（完形 20 + 阅读 20 + Part B 5） | 无 |
| 形式逻辑 | `answer1-1.md` / `answer2-1.md` 的「书中参考答案」串（15 + 15） | 藏在批改段里，需提取 |
| 数学应用题 | 11 份判定表的「正确答案」列（81 行） | 单元格带说明文字，需清洗出字母；11 道充判题答案是 A–E 的充分性判定 |
| 2024 管综 | `答案速查.md`（55 题全，原卷速查表转录） | Q25 曾因题干转录错误把答案订正成 C，已改 E，见下 |

**2024 特别说明（2026-11-07 已解决）**：原卷「答案速查」已转录为 `2024年管综真题/答案速查.md`，55 个答案全部有权威来源，`answerSource` 统一指向该文件，**不再靠订正与用户答案回推**。转录后与 `answer1–9.md` 的 48 条带判定作答逐题比对，零冲突；其余 7 个题号为未作答或合并标题。

**一个必须记住的反例**：Q25 原把条件 (2) 误录为 $S_6=26$（原卷是 $S_9=26$），按错误题干独立复算自洽地推出 C，仓库批改与总结都记成 C；直到对照答案速查才发现应为 E。这正是「答案没有权威来源、靠自己复算回推」的风险——复算再严谨，题干错了结论就错。另外 `answer1.md` 的 `### answer : B` 是**用户自己的作答**（Q2 写 B，正确答案是 C），仍不能用解析器批量抓 `answer` 行当正确答案。

### 4.7 错因标签字典

索引保留**实际出现的 8 类**：`模型选错`、`约束遗漏`、`倍数搞错`、`移项·符号`、`算术笔误`、`书写跳步`（AGENTS.md 六类）+ `方程设错`、`填涂失误`（`全书总结.md` 实际使用）。复合标签拆成数组元素，原话进 `errorNote`。是否把后两类正式收进 AGENTS.md，见 §10 待确认。

---

## 5. 迁移要求（按卷）

### 5.1 2024 管综真题（57 题；55 可评分）

- 板块：问题求解 1–15、条件充分性 16–25、逻辑推理 26–55、写作 56–57；题源 `paper.md`。
- 作答 `answer1.md` … `answer11.md`，**合计覆盖 1–55 全部题号，无缺口**（`answer2.md` 的 `## Q35 ~ 36` 是合并标题，逐页转录才能抓到 Q36）。
- 判定情况（修正 v0.1）：
  - `answer1`：`## Qn ✅/❌` 15/15 全带判定；`### answer : X` 是用户作答。
  - `answer2–9`：`### Answer： X ✅/❌` 共 37 行、33 行带符号；`answer2` 有 `## Q35 ~ 36` 合并标题与 `### Answer 36: C ✅`。
  - 部分判定/空白：`answer2` 有 1 个题号缺 Answer 行，`answer3`/`answer6`/`answer9` 共 4 行无判定符号；Q25、Q43、Q54、Q55 等空白题按 `correct:null`，不猜。
  - **格式变体**：`answer3.md` 的 Q40 写成 `## Answer : E ✅`（二级标题，其余都是 `###`）。解析器需兼容 `#{2,3} Answer`，否则会把这题误判成空白。修正后 2024 客观题空白恰为 Q25、Q43、Q54、Q55 四道，与 `批改总结.md`「共有 4 道客观题空白」一致。
  - `answer10–11`：两篇写作，`correct:null`，`type: essay`/`writing`，估分 18/30、21/35 写入 `score`。
- 55 个答案取 `答案速查.md`（原卷速查表转录），`answerSource` 统一指向该文件；与 48 条带判定作答逐题核对零冲突。
- **Q25 题干转录已修正**：条件 (2) $S_6=26$ → $S_9=26$，正确答案 C → E；`answer9.md`、`批改总结.md` 同步更正。Q25 首做未作答、仍计错，36/55 与估分统计不变。`revision` 记此次更正，更正前的判定标注基于旧题干。
- 11 场作答都没有 `duration`：`timingMode: none`，不补录、不参与速度统计（§4.5）。

### 5.2 2025 英语二（48 题；45 可评分）

- 板块：完形 1–20、阅读 Part A 21–40、Part B 41–45、翻译、写作 A/B。
- 作答 `answer1–5`：三种判定格式（§2.2）；`answer5.md` 同时含 Part B、翻译原文与逐句订正、两篇写作与估分。
- 45 客观题答案取 `试卷总结.md`；翻译 1、写作 2 标 `scorable:false`、`answerStatus: estimated`，估分 8/15、6/10、8/15 写入 `score`。
- 5 份作答都**没有 `duration`**：`timingMode: none`，合法状态，不估算、不参与速度统计（§4.5）。

### 5.3 形式逻辑与综合推理（30 题）

- 两卷各 15 题：`形式逻辑与综合推理一.md`、`…二.md`；作答 `answer1/answer1-1.md`、`answer2/answer2-1.md`。
- 两份判定表各 15 行，均显式「卷面 8/15」；参考答案串写在批改段（卷一 `ECCBA / EEEED / BDDBC`），提取后标 `answerSource`。
- ID 必须带 `p1`/`p2`；唯一键要含 `paper`，否则两卷 `number` 1–15 会撞车。
- **卷二第 4 题答案冲突（2026-11-07 由校验脚本抓出）**：参考答案串 `DDCEE / DEEDB / DEBAB` 第 4 位是 E，判定表与逐题分析是 C。独立复算：断定二为假 →「有的女生喜欢」确定真；Ⅰ 的「男生都喜欢」、Ⅱ 的「有的男生喜欢」都与断定一（所有男生不喜欢）矛盾，确定假；只有 Ⅲ 的「女生都喜欢」不定 → 选 **C**。判定表 `| 4 | C | C | ✅ |` 与卷面 8/15 自洽，故以 C 为准：`volumes.json` 用 `answerOverrides` 显式覆盖，`answer2-1.md` 追加核对说明，**速查串原文保留不改**。这是「两个独立答案源互相校验」的第一个实际收益。

### 5.4 专项训练二（30 题；已练 12）

- 题源 `paper.md`（全局 1–30）；作答 `answer2/answer2-1.md`（Q1–9）、`answer2/answer2-2.md`（Q10–12），判定表 9 + 3 行。
- 其余 18 题在 `questions[]` 中 `answerStatus: confirmed`（答案见 `答案速查.md`），但**没有 attempt**。
- 题干更正历史：`paper.md` 第 4 题条件 (3) 两次转录修正（补「不售卖杨桃」的「不」字；「不选择丁」改「不选择壬」）。`revision` 记更正日期；更正前的 attempt 标注基于旧题干，避免误导「上次错在哪」。

### 5.5 数学应用题（81 题，10 个考点）

- 题源 `应用题.md`，题号在每个考点内从 1 重新开始；作答 `answer1` … `answer11`，11 份判定表共 81 行。
- 11 场对应关系（已核对）：answer1 利润 1–6；answer2 利润 7–10 + 路程 1–4；answer3 路程 5–9；answer4 路程 10–14；answer5 工程 1–11；answer6 工程 12–19；answer7 交叉 1 + 浓度 1–9；answer8 分段 1–4 + 集合 1–4；answer9 不定方程 1；answer10 不定方程 2–11；answer11 线规 1–3 + 至少至多 1–6。
- **11 道条件充分性题**：路程 8–14（7 题）、不定方程 8–11（4 题），`type: data-sufficiency`；判定表「你的答案」写成 `(1)√(2)× → A`，清洗时取最终字母。
- 题号列写法三种（`1` / `利润 7` / `线规 1`），按 §3.2 别名表 + 段落标题的「考点 + 区间」映射，**不要按数组顺序硬编号**。
- 答案取判定表「正确答案」列，去掉括号说明后标 `answerSource`。

### 5.6 `待重做.md`（12 行）

映射由脚本按「来源场次 + 简称 + 题号」经别名表自动生成，**不手写映射表**：

| 原标签 | 应映射到 |
|---|---|
| `answer1 利润 6` | `math-applied-profit-06` |
| `answer2 路程 4` | `math-applied-distance-04` |
| `answer4 路程 13` | `math-applied-distance-13` |
| `answer4 路程 14` | `math-applied-distance-14` |
| `answer8 集合 1` | `math-applied-sets-01` |
| `answer10 不定方程 3` | `math-applied-diophantine-03` |
| `answer10 不定方程 4` | `math-applied-diophantine-04` |
| `answer10 不定方程 5` | `math-applied-diophantine-05` |
| `answer11 线规 1` | `math-applied-linear-programming-01` |
| `answer11 线规 2` | `math-applied-linear-programming-02` |
| `answer11 至少至多 2` | `math-applied-at-least-at-most-02` |
| `answer11 至少至多 3` | `math-applied-at-least-at-most-03` |

要求：12/12 都能落到 `questionId`，且题目存在。可选给 `待重做.md` 加一列 `ID`（仅新行），**保留「来源 / 题目」两列**给人看；旧行不回填，避免双维护。重做结果仍以 `待重做.md` 的「状态 / 重做记录」为人工台账，索引的 `isRedo` 记录机器事实，两者由校验脚本对账。

---

## 6. 编写约定（索引上线后生效）

### 6.1 题目文件

- `paper.md` 顶部加 front matter，只放 `slug`、`subject`（不放题数）：
  ```yaml
  ---
  slug: math-applied
  subject: 管综
  ---
  ```
- 题号继续用现有格式，不为索引重排题目；题干是唯一内容源。
- **ID 锚点**：题号行**末尾**追加 `<a id="<questionId>"></a>`（仅结构信息，不改题意、不改题号）。由 `scripts/add_anchors.py` 幂等生成，可重复运行；锚点必须留在行尾，保持 `**N.**` / `N. ` 在行首，否则会破坏 `check_source_numbers` 等行首题号正则。索引的 `source` 写成 `文件#<questionId>` 指向它。
- 新增卷时先加 `volumes.json` 条目与别名，跑一次 `add_anchors.py`，再写作答。

### 6.2 作答文件

- 判定表在原有四列**之后追加**一列 `ID`，保留人读题号：
  ```markdown
  | 题号 | 你的答案 | 正确答案 | 判定 | ID |
  |---|:---:|:---:|---|---|
  | 线规 1 | E | B | ❌ 假上界 | math-applied-linear-programming-01 |
  ```
  v0.1 把「题号」列替换成 `ID`，批改时看不到「线规 1」，与 AGENTS.md 固定的四列表头冲突，已修正。
- 旧的判定表**保留原文、不回填**；映射由脚本按别名表完成。新写的表带 `ID` 列。
- 逐题行格式保持不变，靠题号映射到 ID。
- `duration` 是**可选**字段：没记时长就整行省略，不写 `0`、不估算、`--check` 不报错；已记的沿用 `76min` / `36 min` 写法。计时口径用可选的 `timingMode`（`session` / `per-question` / `mixed` / `none`），省略时按 `duration` 有无推断。
- 按题计时：判定表再加一列「用时」（分钟，可小数），或逐题行写 `（2.5min）`。`ID` 与「用时」两列并存，顺序为 `题号 | 你的答案 | 正确答案 | 判定 | ID | 用时`；写法见 §4.5。

### 6.3 新增 / 重做

- 重做一题：新增一条 attempt，`date` 用重做日、`isRedo: true`、`session` 指向重做文件；**不改原来的 `correct`**。
- 错因从 §4.7 字典选，可多标签；不确定留空，不编。
- 未记时长的场次，末尾「本场与累计速度」写「未计时」，不估算、不并入累计轨迹（§4.5）。
- 每次批改后重跑 `build_index.py`，让 `index.json` 与原文同步。

### 6.4 AGENTS.md 入口

索引再好，下次会话的 agent 不知道它存在也白搭。AGENTS.md 需补：

- 目录树列出 `doc/`、`data/`、`scripts/`；
- 一条约定：**「查询题目/错因/进度先读 `data/index.json`，结论必须回原文核验；`index.json` 由脚本生成，禁止手改；题干与判定以 Markdown 为准」**；
- 「作答」条把 `duration` 从「必带」改为可选（未记录就留空，不估算）；「专项练习排布」与「统计口径」补未计时场次的写法，以及 `session` / `per-question` 两种速度算法与不混算规则（§4.5）。

### 6.5 站点消费与改动后同步（平台 2026-11-07 确认）

站点判断场次靠两条：文件路径必须是 `answer*.md`、front matter 里有 `time`。**改内容不会新增场次**：同一个 `answer3.md` 无论改多少次，HEAD 里始终算 1 场，旧版本不从 git 历史再生成一场。

| 操作 | 场次 | 影响 |
|---|---|---|
| 改旧答卷/题库文字，`time` 不变 | 不变 | 原文页更新，产生一个新 commit |
| 改 `time` | 不变（同一场） | 场次移到新日期，周报/热力图跟着变 |
| 改 `duration` / 分数 | 不变 | 该场用时、正确率变化 |
| 新增 `answer13.md` | **+1 场** | 新文件即新场次 |
| 重命名旧文件 | 可能变新场次 | 旧路径消失、新路径新增 |

**索引同步规则**：站点统计读 `data/index.json`。改动任何被索引读取的 Markdown（题目、作答、总结、答案速查）后，必须跑 `python3 scripts/build_index.py` 并把 `data/index.json` 一起提交；不重生成则原文页已变、统计仍是旧 JSON。重新生成后仍是同一场，只刷新该场数据，不增加场次。`--check` 只校「生成结果 vs 原文一致」，**查不出「忘了生成」**，所以这一步不能省。

> 提交本身算活动：改旧答卷后当天提交数 +1、日页出现该提交；若当天没有新作答，首页可能显示「今天有提交，还没有作答」，今天也可能进入热力图/学习日。这是**提交活动，不是作答场次**，`本周场次` 不增加。给题库加锚点这类纯结构改动同样只产生提交活动。

### 6.6 Git

- 提交信息中文、动词开头，一次提交只做一类事。
- `data/index.json` 可入库（文本、可 diff），提交信息注明「重新生成索引」。
- 本任务只本地修改，**不要 push**，等用户明确要求。
- `doc/` 目前仍是未跟踪状态（`?? doc/`）；提交前确认没有 `.DS_Store`、PDF、图片。

---

## 7. 生成与校验

一条命令，零依赖（Python 3.11）：

```bash
python3 scripts/build_index.py            # 重新生成 data/index.json
python3 scripts/build_index.py --check    # 只校验，不写文件；有错误 exit 1
```

**校验对象是「生成结果 vs Markdown 原文」**，不是 JSON 内部自洽——只校内部查不出「两边都漏了」。至少检查：

1. `questions[].id` 唯一；唯一键用 `volume + paper + number + section`（含 `paper`，否则形式逻辑两卷撞车）。
2. 每卷题目数 = `volumes.json` 的 `totalQuestions`；可评分题数 = `scorableQuestions`。
3. **题号覆盖**：逐卷核对题号 1–N 连续、无重复、无遗漏；特别处理 `## Q35 ~ 36` 合并标题。解析失败的记录进 `errors`，不静默丢弃。
4. 每个 `attempt.questionId` 存在；`correctAnswer` 与题库答案一致（若都有）；`answerSource` 非空。
5. 每个可评分题都有 `answer`，或显式 `answerStatus: missing` 并列出。
6. 逐题判定可提取数 = 原文实际有判定的题数；部分判定、空白题单独列为「已知例外」，不笼统标 partial。
7. `待重做.md` 12 行全部映射，且题目存在；「状态 / 重做记录」与 `isRedo` 对账。
8. 数学 ID 的 topic 与 `section` 的考点一致——依赖 §3.2 别名表，无别名表时该项不可实现。
9. `source` 路径可解析；题干更正过的题目有 `revision`，且受影响 attempt 已标注。
10. 不出现重复 `attempt.id`；同一题同一天同一 session 不重复（重做须 `isRedo: true`）。
11. **计时一致性**：`timingMode: none` 时场次与逐题 `durationMin` 均为 `null`，**合法且不计入 errors**；`session` 模式要求场次有值；`per-question` 模式要求逐题有值（部分缺失标 `mixed`）；`durationMin` 与 `durationSource` 成对出现。场次总用时与 `Σ 逐题用时` 同时存在时只记录差异、不判错（口径不同）。
12. **ID 锚点**：每个 `questions[].source` 的 `#fragment` 必须能在对应题库文件里找到 `<a id="...">`，缺一个就报错，防止回链退化成伪锚点。
13. 输出各卷统计 + 锚点覆盖 + 计时分布 + 错误列表；有错误时 exit 1 且 `meta.errors` 非空。

建议输出：

```text
volumes: 5
questions: 246 (scorable 241, 有答案 241)
sessions: 31 | attempts: 228 (有判定 219, 未判定 9)
timing: none 16 / session 15
redo rows: 12/12 mapped
anchors: 246/246 verified
answer overrides: 1（volumes.json 显式订正，原文保留）
  2024-exam        questions  57/57  attempts 57
  2025-english     questions  48/48  attempts 48
  formal-logic     questions  30/30  attempts 30
  reasoning-2      questions  30/30  attempts 12
  math-applied     questions  81/81  attempts 81
known exceptions (4): Q25 / Q43 / Q54 / Q55 未作答
errors: 0
```

> 以上是 2026-11-07 首次全量运行的实测输出，不是示例。`known exceptions` 的 4 道与 `批改总结.md`「共有 4 道客观题空白」一致；另 5 条未判定是写作/翻译主观题。

---

## 8. 验收标准

- [x] `index.json` 共 **246** 条 question，可评分 **241** 条；分卷 57/48/30/30/81。
- [x] 所有 ID 唯一、符合 §3.2；数学题 ID 带 topic；唯一键含 `paper`。
- [x] 241 道可评分题都有答案且逐条标 `answerSource`；2024 的 55 个答案由 `答案速查.md` 覆盖并与作答逐题核对，Q25 题干与批改结论已更正。
- [x] 5 道主观题存在且 `scorable:false`；估分 8/15、6/10、8/15、18/30、21/35 均写入 `score` / `scoreMax` / `scoreBasis`。
- [x] 228 条 attempt 全部迁移，其中 219 条有判定；9 条 `correct:null` 逐条注明原因（4 道空白 + 5 道主观题），不猜。
- [x] 卷面与实质双口径可分别统计，数学实测 **68/81 与 69/81**，与 `全书总结.md` 吻合。
- [x] `待重做.md` 12 行全部映射，无悬空 ID，错因标签与原文说明已挂到对应 attempt。
- [x] `python3 scripts/build_index.py --check` 0 error；删掉 `index.json` 后能完整重建。
- [x] 现有 `paper.md` 题目原文未被改写；**唯一例外**是 Q25 条件 (2) 的转录纠错（$S_6$ → $S_9$），已在 `答案速查.md` 留痕。
- [x] AGENTS.md 已补目录项与「先读索引、回原文核验」约定，且 `duration` 改为可选。
- [x] `sessions[]` 31 条与 31 份 answer 文件一一对应，`timingMode` 分布与 `meta.timing` 一致。
- [x] 16 场未记时长为 `timingMode: none` / `durationMin: null`，`--check` 不报错、不计入速度统计。
- [x] 题库原文题号覆盖校验：2024 1–57、形式逻辑两卷 1–15、专项二 1–30、数学 10 个考点 1–N、英语完形 1–20，全部连续无重复。
- [x] 查询层可用：按考点（含中文简称）、错因、待重做、题目 ID 筛选，输出含 `source` 回链；`--csv` 导出视图。
- [x] **246 个 ID 锚点**已写入 6 个题库文件的题号行末（含英语 46/47/48 三道主观题），`source` 统一为 `文件#<questionId>`；`--check` 会校验每个回链锚点真实存在。
- [ ] 按题计时的字段与写法已预留，但**尚未造 `per-question` 样本**验证解析器能填出 `attempts[].durationMin` 并算出单场速度。
- [x] 站点统计已读取 `data/index.json`（平台 2026-11-07 确认）；改 Markdown 后重生成索引只刷新该场数据、不增加场次（§6.5）。

---

## 9. 分阶段建议

| 阶段 | 内容 | 产出 | 状态（2026-11-07） |
|---|---|---|---|
| **P0（新增前置）** | 定错因字典与「简称 ↔ slug」别名表；把 `duration` 改为可选、定 `timingMode` 与场次/单题两层时长字段 | `volumes.json`、计时约定 | ✅ 已完成；仅「两类错因是否写入 AGENTS.md」待拍板 |
| P1 | 写 `build_index.py` 的解析层（四种判定格式、合并标题、题号列清洗）+ 生成 246 条骨架 | 索引骨架、`meta.coverage` | ✅ 已完成 |
| P2 | 补答案 / 题型 / 考点 / `answerSource`，标 11 道充判题 | 241 条可评分题完整 | ✅ 已完成（同一脚本一次生成） |
| P3 | 迁移约 220 条逐题判定 + 12 条待重做映射 + 主观题估分 | `attempts[]` 完整 | ✅ 已完成（实测 228 条） |
| P4 | 校验规则 + `--check` + AGENTS.md 入口约定 | 校验 0 error | ✅ 已完成 |
| P5 | 站点消费索引做统计 / 组卷 | 另行开发 | ✅ 站点统计已读取 index.json（平台确认）；组卷未做 |

P0 是硬前置：v0.1 从 P1「建 246 条骨架」直接开始，但 ID 别名表没定，骨架填不出来。P1 先写解析器再生成骨架，**不手写 JSON**。每批提交都必须能通过 `--check`（允许阶段性 `missing`，但要显式列出）。**「确认 2024 答案来源」已于 2026-11-07 由 `答案速查.md` 解决，移出 P0**；P0 现在只需定别名表、错因字典与计时口径。

**2026-11-07 补记**：只读查询层 `scripts/query.py` 已随 P4 落地，不产生新数据。它把 §1.1 的「按考点筛题、组一套练习」推进到「产出一份可照着读的题目清单」；题干仍不进索引。剩下唯一让「组卷」不顺手的是 `source` 为伪锚点，见 §8。

**补 16 场 `duration` 已从 P0 移除**——未记时长是合法状态，不再阻塞任何阶段；但计时字段与速度口径必须在 P1 写解析器前定好（§4.5），否则将来按题计时上线时要重扫全部历史作答。

**迁移过程暴露的缺口本身就是第一份产出**：Q36 合并标题、15 场整场用时口径混杂（部分含当场订正时间）、8 类错因、**Q25 题干转录错误（已修正，并连带纠正了答案）**、11 道充判题，应整理成「数据缺口清单」交付，而不是当噪音跳过。未记时长的 16 场**不列入缺口**，2024 答案源也已补齐。

---

## 10. 待确认

v0.1 的六问已按前述分析收敛，仅剩两项需要拍板：

1. **错因字典**：是否把「方程设错」「填涂失误」正式收进 AGENTS.md？建议收录（索引保留真实标签，AGENTS.md 同步；若不想动约定，则在索引里注明这两类为「仓库实际使用、约定外」）。
2. **题干更正的影响范围**：`revision` 只记更正日期与内容，还是要把更正前的 attempt 标成 `invalid` 并排除出正确率统计？建议先标记、不排除，等真的出现重判时再定口径。

已定事项：纳入主观题（246 条，`scorable:false` + `score`）；attempt 一题一条、重做新增并带 `isRedo`；数学 ID 用 topic 前缀 + 别名表；旧判定表不回填；不引 SQLite；产物集中 `data/` 且只有一份生成索引；**`duration` 允许为空、未记时长不是数据缺口**；计时粒度预留「场次 + 单题」两层（`sessions[]` / `timingMode` / `attempts[].durationMin`），按题计时上线后累计速度另起轨迹。

---

## 11. 修订摘要（v0.1 → v0.3）

| 位置 | 修订 |
|---|---|
| 全文定位 | 首要消费者从「网站」改为「agent」；明确 Markdown 唯一真源、索引是自动生成的导航层 |
| §0 / §1 | 补 agent 每次会话重新解析的成本；新增「批改辅助」目标；非目标加「不手写索引」「不复制题干」 |
| §2.2 | 按原文重写：修正 2024 判定误判、补 123 条专项逐题判定表、四种作答格式、题号列不统一、8 类错因、计时口径现状、题干更正历史 |
| §2.3 | 网站聚合数字降级为参考，说明误判来源，事实基准改为 Markdown 原文 |
| §3.2 / §3.3 | 统一 ID 位数规则；新增「简称 ↔ slug」别名表；题干更正用 `revision` |
| §4 | 三份手写 JSON → `volumes.json`（手写）+ `index.json`（生成）+ `build_index.py`；新增 `source`、`answerSource`、`substantiveCorrect`、`score*`、`errorTags`/`errorNote`、`isRedo`、`sessionId`、`revision`、`meta` |
| §5 | 修正各卷事实错误；补 2024 答案拼接路径、11 道充判题、Q36 合并标题、待重做 12 行完整映射 |
| §6.2 | 判定表 `ID` 改为追加第五列，保留人读题号列；旧表不回填 |
| §6.4 | 新增 AGENTS.md 入口约定 |
| §7 / §8 | 校验对象改为「生成结果 vs 原文」；验收去掉「31 场至少一条 attempt」的弱标准，改为逐题判定覆盖 + 双口径统计 |
| §9 | 新增 P0 前置阶段；P1 先写解析器再生成骨架 |
| §10 | 六问收敛为两项 |

### v0.3 增补（`duration` 可空 + 按题计时预留）

| 位置 | 修订 |
|---|---|
| §2.2 / §5.1 / §5.2 | 16 场未记时长从「数据债 / 待补项」改为合法状态 `timingMode: none`，不估算、不追问补录 |
| §4.2 | `index.json` 增加 `sessions[]` 顶层数组；`meta.coverage.sessions` 与 `meta.timing` 分布 |
| §4.4 | 移除 `durationKnown`，改为 `durationMin` / `durationSource`（题目级，可空） |
| §4.5（新增） | `sessions[]` 字段、`timingMode` 四种取值、Markdown 写法（判定表「用时」列 / 逐题 `（2.5min）`）、四种速度口径、两种口径不混算 |
| §4.6 / §4.7 | 原答案来源与错因字典顺延编号；答案拼接精确为「19 道错题（含 4 道空白）+ 36 道答对题」 |
| §6.2 / §6.3 / §6.4 | `duration` 改为可选；未计时场次速度栏写「未计时」；AGENTS.md 同步改「必带 duration」与统计口径 |
| §7 / §8 | 新增计时一致性校验（`none` 不报错）；验收加 `sessions[]` 与 `per-question` 样本 |
| §9 / §10 | 补 16 场 duration 从 P0 移除、缺口清单不再列入；已定事项补计时预留 |

### 2026-11-07 答案速查补录

- 新增 `2024年管综真题/答案速查.md`（55 个客观题答案，按原卷速查表转录）。**2024 答案源不再缺失**，§4.6 的「靠订正与用户答案回推」方案作废，`answerSource` 统一指向该文件。
- 全量核对：48 条带判定作答与速查表零冲突；其余 7 个题号为未作答或合并标题。
- 发现并修正 Q25 题干转录错误（$S_6=26$ → $S_9=26$），正确答案 C → E；`paper.md`、`answer9.md`、`批改总结.md` 同步更正。Q25 首做未作答仍计错，36/55 与估分不变。
- §2.2、§4.6、§5.1、§8、§9 同步更新；P0 移除「确认 2024 答案来源」一项。

### P1 落地记录（2026-11-07）

- 新增 `data/volumes.json`（手写）、`scripts/build_index.py`（生成 + 校验，零依赖）、`data/index.json`（自动生成，约 282 KB）。`--scan` 只读报告、`--check` 只校验、默认重建索引；实测 `--check` 0 error。
- 实测覆盖：**246 题 / 241 有答案、31 场、228 条 attempt（219 有判定、9 未判定）、12/12 待重做映射**，timing 15 `session` / 16 `none`。数学双口径实测 **68/81 与 69/81**，与 `全书总结.md` 吻合。
- 校验脚本当场抓出并留痕两处历史问题：
  - **形式逻辑卷二第 4 题**：参考答案串 E 与判定表 C 冲突，独立复算判 C，用 `answerOverrides` 显式覆盖、串原文保留（§5.3）。
  - **2024 Q40**：作答行写成 `## Answer : E ✅`（二级标题，其余都是 `###`）；解析器兼容 `#{2,3}` 后，2024 客观题空白恰为 Q25/Q43/Q54/Q55 四道，与 `批改总结.md` 一致（§5.1）。
- `volumes.json` 补充 `answerSources` / `answerOverrides` / `mathTopics` 三个字段，§4.1 已同步。
- 新增 `scripts/query.py`（只读查询层）：`--topic` / `--error-tag` / `--redo` / `--question` / `--csv`；实测「路程错题 3 道」「模型选错 4 道」「待重做 12 题」与原 Markdown 一致，`--csv` 由 `csv` 模块转义 LaTeX 与中文标点。
- 平台 2026-11-07 确认：站点按 `answer*.md` 路径 + front matter 的 `time` 判场次，改内容不新增场次；站点统计读 `data/index.json`，故改 Markdown 后必须重生成索引（§6.5）。此项消解了「给题库加锚点会被误认为新作答」的顾虑，也把索引从「可选产物」变成生产数据源。
- **ID 锚点已落地（2026-11-07）**：`scripts/add_anchors.py` 幂等写入 246 个 `<a id>` 到 6 个题库文件题号行末；`build_index.py` 的 `source` 改为 `文件#<questionId>` 并新增 `check_anchors()` 校验，实测 246/246 存在、题号清点未受影响。英语 `paper.md` 的 46/47/48 是翻译与写作 Directions，同样有题号行，故 246 题全覆盖。锚点只在行尾，不动题干、题号与选项。
- 仍未完成：造一场 `per-question` 样本验证按题计时解析；「方程设错」「填涂失误」是否正式写入 AGENTS.md 待拍板。

---

## 附录 A：文件清单

```text
mem/
├── 2024年管综真题/          paper.md、答案速查.md、answer1–11.md、批改总结.md
├── 2025年英语二/            paper.md、answer1–5.md、试卷总结.md、生词本.md
├── 形式逻辑与综合推理/      形式逻辑与综合推理一.md / 二.md、answer1/、answer2/
├── 专项训练二-五大条件类推理题/  paper.md、答案速查.md、answer2/
├── 数学应用题/              应用题.md、answer1–11/、待重做.md、全书总结.md
├── doc/
│   └── question-bank.md     # 本文档
├── data/                    # 已落地
│   ├── volumes.json         # 手写：卷元数据 + topic 别名表
│   └── index.json           # 自动生成，勿手改
└── scripts/
    ├── build_index.py       # 生成 + 校验
    ├── add_anchors.py       # 幂等写入题库 ID 锚点
    └── query.py             # 只读查询 / CSV 导出
```

## 附录 B：最小示例

`volumes.json` 片段见 §4.1。

`index.json` 片段：

```json
{
  "meta": {
    "generatedAt": "2026-11-07T01:50:00+08:00",
    "generator": "scripts/build_index.py",
    "sourceFiles": 31,
    "coverage": { "questions": 246, "attempts": 220, "sessions": 31, "redoRows": 12 },
    "timing": { "session": 15, "perQuestion": 0, "mixed": 0, "none": 16 },
    "errors": []
  },
  "questions": [
    {
      "id": "math-applied-linear-programming-01",
      "volume": "math-applied",
      "paper": "数学应用题/应用题.md",
      "number": 1,
      "section": "考点9 线性规划",
      "topic": "线规",
      "type": "problem",
      "answer": "B",
      "answerSource": "数学应用题/answer11/answer11.md 判定表",
      "answerStatus": "confirmed",
      "scorable": true,
      "source": "数学应用题/应用题.md#考点9-1",
      "revision": null,
      "notes": null
    }
  ],
  "sessions": [
    {
      "id": "math-applied-s11",
      "date": "2026-11-04",
      "file": "数学应用题/answer11/answer11.md",
      "volume": "math-applied",
      "questionCount": 9,
      "timingMode": "session",
      "durationMin": 76,
      "durationSource": "draft",
      "note": "整场用时；未拆分单题"
    }
  ],
  "attempts": [
    {
      "id": "2026-11-04-math-applied-11-linear-programming-01",
      "date": "2026-11-04",
      "sessionId": "math-applied-s11",
      "session": "数学应用题/answer11/answer11.md",
      "questionId": "math-applied-linear-programming-01",
      "userAnswer": "E",
      "correctAnswer": "B",
      "correct": false,
      "substantiveCorrect": false,
      "errorTags": ["模型选错"],
      "errorNote": "模型选错（非法复合不等式得假上界，未验有界性）",
      "isRedo": false,
      "durationMin": null,
      "durationSource": null,
      "source": "数学应用题/answer11/answer11.md 判定表首行",
      "verified": true
    }
  ]
}
```
