---
type: index
created: 2026-10-02
updated: 2026-10-02
tags: [索引, 派生物, 记忆库, 分层路由, 门禁]
---

# Memory 目录（机器派生物：Agent 启动不读）

> **本文件是生成/校验用目录，不是 Agent 启动入口。**
> Agent 启动只运行 `scripts/memory_boot.py`；需要查历史/原因/踩坑时运行 `scripts/memory_query.py`。
> 本页供 `mem_index.py` 校验结构与诊断使用；正常任务不要读取整页。
> 权威执行规则见 `Rule.md`（目录页：操作→分节映射）+ `rule/` 分节文件（写入/收尾前按映射读对应分节）。

## 一、根文件与规则目录

| 文件 | 何时读 |
|---|---|
| `AGENTS.md` | **铁律正本** + 短版钩子（分发到各 AI 工具，常驻系统提示） |
| `Rule.md` | 规则**目录页**：「操作 → 分节文件」映射 + 读取指针；写入或收尾前按映射读对应分节，禁止通读 |
| `rule/` | 规则分节文件：`写入与禁止` / `收尾与维护` / `子代理与脚本` / `vibe-coding` |
| `Todo.md` | 找当前待办（按项目分组） |

## 二、分层地图与路由（6 层 + 3 个根目录）

| 层 | 是什么 | 什么时候读 | 逐篇索引 |
|---|---|---|---|
| `Preferences/` | 个人偏好：语言、代码风格、沟通方式、汇报口径 | 需要用户偏好 / 协作习惯 | `Preferences/_index.md` |
| `Plans/` | 长期规划、目标、路线图 | 需要长期规划与目标 | `Plans/_index.md` |
| `Decisions/` | 决策记录（背景 → 选择 → 备选方案，附日期） | 涉架构 / 技术选型，想知道「为什么这么定」 | `Decisions/_index.md`（专用格式，手工维护） |
| `Lessons/` | 踩坑与解法 | 踩坑 / 排障 / 找已知解法 | `Lessons/_index.md` |
| `Workflows/` | 固定流程手册 / SOP | 要找固定流程 / SOP / 操作手册 | `Workflows/_index.md` |
| `Projects/<项目名>/` | 项目记忆（必含 `_overview.md` 与 `_state.md`；历史在 `working/`） | 项目启动与当前状态 | `Projects/_index.md` |
| `Todo.md` | **全局总待办**（按项目分组，不用勾选框） | 找当前待办 | ← 本文件 §一 |
| `Inbox/` | 写入登记簿（agent 写完留登记，待审核） | 写入后登记 / 审核对账 | `Inbox/YYYY-MM-DD.md` |
| `Archive/` | 季度归档（`decisions-YYYY-QX.md` / `lessons-YYYY-QX.md`） | 找已归档决策 / 教训 | — |

> **条数不在此表维护**：以各层 `_index.md` 与 `Decisions/_index.md` 页脚为准——本表只管「是什么 / 什么时候读」。

**典型路由**（**本表为正本**）：

- 续开发某项目 → 运行 `memory_boot.py`；默认只取 `_overview.md` + `_state.md` + Todo 切片，不读 journal 全文
- 架构/技术选型 → `memory_query.py --types decision`，只展开必要的一篇
- 排障 / 踩坑 → `memory_query.py --types lesson`
- 用户偏好 / 协作习惯 → 先看 `BOOT.md`，不足时 `memory_query.py --types preference`
- 固定流程 / SOP → `memory_query.py --types workflow`

## 三、项目层结构（`Projects/<项目名>/`）

| 文件 | 内容 |
|---|---|
| `_overview.md` | 项目定位、关键路径、关联资产、稳定边界 |
| `_state.md` | 当前目标、阻塞、下一步；覆盖式更新，不累积历史 |
| `working/journal.md` | 过程流水（时间倒序，暂存层，收尾时蒸馏） |
| `working/plan.md` | 计划 |
| `working/completed.md` | 结案归档（带结案日期、结果、原因与来源） |

待办**不在这里**——统一在 `Todo.md` 按项目分组。

## 四、Inbox 与 Archive

| 目录 | 说明 |
|---|---|
| `Inbox/YYYY-MM-DD.md` | **写入登记簿**：agent 每次写记忆后追加登记（路径 + 一句话），等审核。同一天追加到同一文件，不散建 |
| `Inbox/Archive/` | 审核结案后的留档（保留日期名） |
| `Archive/` | 季度归档落点（`decisions-YYYY-QX.md`、`lessons-YYYY-QX.md`） |

## 五、Inbox 审核

本节实体已迁出 → `Workflows/记忆库自动审核与人工入口.md`。本节只留入口指针，不再展开审核 SOP。

- 自动审核：每天审「登记日期早于运行当天」的 Inbox 日记账；格式、落库存在性、重复/冲突、决策格式门检；全部通过才移入 `Inbox/Archive/`。
- 待裁定入口：只看结案记录、挂起事项与需要本人裁定的条目；对自动化结论有异议 → 直接改目标文件，并在当日登记中备注。
- 停跑可见性：`todo_audit.py` 的「待结积压」报告段会列出 `Inbox/` 根下早于当天的登记文件；**只报不拦**。

## 六、同名文件消歧（易混清单）

> **完整五组表只在工作区根正本**：`../AGENTS.md` §同名文件消歧（单一正本；本文件不再存副本，以免两份手工表各自漂移）。需要消歧时直接读正本节。
> 门禁 `scripts/mem_index.py --check` 会校验正本表结构完整与本指针有效；改名 / 删除 / 把表塞进代码围栏或注释都会报红。

## 七、Agent 读取成本约定

- **启动**：运行 `python scripts/memory_boot.py --cwd <项目根或当前目录>`；只读 `BOOT.md`、当前项目 `_overview.md`、`_state.md` 与 Todo 切片。
- **普通任务**：不默认扫描记忆库；需要偏好时只读 `BOOT.md`。
- **按需检索**：运行 `python scripts/memory_query.py "关键词" --cwd <项目根或当前目录>`，默认返回 top-k 片段，排除 archived/superseded。
- **不读本页**：`_index.md` 与各层 `_index.md` 是生成/校验派生物，不参与启动。
- **当前项目判定**：项目根 `AGENTS.md` 的 `当前项目名` → 工作目录推断 → 询问用户；由 `memory_boot.py` / `memory_query.py` 封装。
- **时效**：记忆是写下当天的快照；路径、文件存在性、工具行为引用前先复测。
## 八、维护

- 本文件由结构变化时**手工**更新（低频）；**各层 `_index.md` 中除 `Decisions/_index.md`（专用格式，手工维护）外，均由 `scripts/mem_index.py` 合并生成**：新增笔记自动补行，已有行的人工「一句话」会被保留。
- 防漂移：`python scripts/mem_index.py --check`（检查漏行/失效行、索引「更新」列滞旧、地图页漏列、同名消歧单一正本与指针、`Decisions/` 锚点守恒；有漂移退出码 1，跑 `--write` 修复生成层）。**「一句话定位 / 关键词」是人工润色值，`--write` 不覆盖已有人工行**；要强制按实盘重算两格用 `--write --refresh-cells`。
- `Decisions/_index.md` 只可 `--check`，不可 `--write`；它的一行可覆盖多个决策，机器只查「每张决策卡都有锚点、每个锚点都指向真实文件」。

## 九、读时时效（引用记忆里的断言前，先判它该不该信）

- **记忆是「写下那天为真」的快照，不是现状。** 凡断言关于**路径 / 文件是否存在 / 工具行为 / 环境版本 / 目录结构**，据此动手前先就地复测（`Read` / `Glob` / 一次探针），不要把笔记当成现状本身。
- **免费的时效信号**：各层 `_index.md` 行末「更新」列 = 该篇最后**改动**日期，只证明「动过笔」、不证明「核验过」——别当核验日期用。
- **判据正本（本条只指路，不复述）**：「结论是不存在 / 已落过 / 没问题时，先怀疑给出结论的那次读取」→ `Lessons/批量改写脚本的自检失明.md`。
- **权威级排序**：工具私有记忆位（含 auto-memory 影子层）**不是正本、也不算「已查过」**——查同名与引用一律以记忆库为准。
