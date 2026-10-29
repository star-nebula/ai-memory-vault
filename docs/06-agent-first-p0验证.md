# Agent-first 记忆启动 P0 验证

> 范围：验证公开发行版和 starter 示例，不包含个人记忆数据或本机路径。
> 后续状态（2026-10-24）：P0 验证完成后，所有 `_index.md` 与 `mem_index.py` 已整体退役；本文保留当时的设计验证结果，现行命令不再包含索引。

## 目标

把默认读取从“先看索引、再读 Todo、再读项目概况”改为：

1. 普通任务不默认扫描记忆库；
2. 项目任务只生成有界启动包；
3. 查历史/原因/排障只用有界检索返回片段；
4. 不在启动时预读整棵记忆树；P0 后续批次已删除全部索引。

## 新增命令

```bash
python scripts/memory_boot.py --cwd . --json
python scripts/memory_query.py "关键词" --cwd . --limit 5 --budget 5000
```

### `memory_boot.py`

输入固定为四类：

- `Memory/BOOT.md`：唯一常驻热层；
- `Projects/<项目名>/_overview.md`：稳定项目卡片，去除 frontmatter；
- `Projects/<项目名>/_state.md`：当前目标、阻塞、下一步，去除 frontmatter；
- `Todo.md` 的当前项目切片（可能完整读取文件以做切片，但不会整份注入上下文）。

启动包只读取上述四类显式输入，不扫描其他笔记。`--budget` 约束返回的 `text` 字段；JSON 元数据另计。`--json` 返回 `chars`、`source_chars`、`assembled_chars`、是否截断和实际读取文件列表。

### `memory_query.py`

- 默认只排除 `archived` / `superseded` / `rejected`，其他 status 保留；
- 无法识别项目时默认只搜 `scope: global`；跨项目检索必须显式加 `--all-projects`；
- 指定项目时，`Projects/<项目>` 之外的项目树不会进入结果；跨层笔记必须 `scope` 为该项目或 `global`；
- 默认跳过 `Inbox/`、`Archive/`、`working/`；
- 返回路径、类型、scope、status、更新日期和片段，不展开整篇；
- `--include-inactive` 查历史状态，`--include-history` 查过程历史。

## 入口收缩

`starter/` 的入口文件改成：

| 文件 | 角色 |
|---|---|
| `AGENTS.md` | 工作区门牌、硬规则、启动/查询命令 |
| `Memory/AGENTS.md` | 记忆库短钩子，只声明启动/检索/写入契约 |
| `Memory/Rule.md` | 写入/收尾/维护时才读的规则路由 |
| `Memory/BOOT.md` | 唯一常驻热层 |

P0 当时暂时保留了索引作为校验面；后续切换已将其整体删除，现行结构不依赖索引。

## 本次验证数据

在 `starter/` 示例工作区：

| 指标 | 结果 |
|---|---:|
| 根 `AGENTS.md` | 2,212 字符 |
| `Memory/AGENTS.md` | 950 字符 |
| `Memory/Rule.md` | 749 字符 |
| `Memory/BOOT.md` | 460 字符 |
| 入口文件合计（不含启动包） | 4,371 字符 |
| 示例项目启动包 | 1,327 字符 |
| 启动包预算 | 6,000 字符 |
| 是否预读整棵记忆树 | 否 |

与旧 starter 的“三件套”对比：旧路径约为 `_index.md` 4,129 + `Todo.md` 355 + 最大 overview 1,452 = **5,936 字符**；新启动包为 **1,327 字符**，约减少 **77.6%**。这是 P0 的基线数据；索引已于后续批次删除。

验证命令：

```bash
# 从仓库根运行
python -m unittest discover -s scripts/tests -p "test_*.py" -v

# 进入 starter（contains Memory/）
Set-Location starter
python ..\scripts\todo_audit.py --check
python ..\scripts\todo_audit.py --cost-check
python ..\scripts\todo_audit.py --content-check
python ..\scripts\encoding_guard.py . --no-ctrl
python ..\scripts\sync_memory_instructions.py --check
```

当时结果：单元测试通过；待办门禁通过；`--cost-check` 通过；编码检查通过；指令声明位检查通过。索引门禁已随索引退役删除。

## 验证边界

公开验证以仓库自带的 starter 示例和自动化测试为准。个人运行库上的只读试跑曾用于评估迁移前的上下文成本；其项目名、查询主题、路径和数据规模不属于公开验证材料，因此不在此记录。

## 复审修复

Claude Code 的第一轮审查发现并已修复：

- 项目名路径穿越：显式 `--project` 与 `AGENTS.md` 声明都走同一个安全校验，只允许 `Memory/Projects/` 的直接子目录；非法值退出码 2。
- 项目查询隔离：查询 `demo` 时不会返回 `Projects/other/**`；跨层笔记必须 `scope` 为该项目或 `global`。
- 预算语义：`--budget` 只约束 `text`；JSON 元数据不重复携带正文，并在帮助文本中明确该口径。
- BOM：统一按 `utf-8-sig` 读取，BOM 不再绕过 status/scope 过滤。
- Todo 分组：启动和门禁共用同一个“去掉尾部括号说明”的归一化规则。
- 启动门禁：`--cost-check` 只拦 BOOT 源政策与实际 `assembled_chars`/最终预算截断；`--content-check` 才严格拦 overview/state 源超限、section 截断与缺 state。
- 入口页：记忆库钩子不再要求读取或维护人看索引。
- 项目状态：`live-diagram` 补了 `_state.md`；没有 `_state.md` 的活跃项目进入报告项。

新增回归测试后，当时共 **26** 个测试通过。

## 后续演进

P0 之后，公开模板完成了以下结构演进：

- 删除 `_index.md` 与 `mem_index.py`，用按需检索替代维护式索引；
- 以 `_state.md` 保存项目当前状态，journal 与 completed 改为按月 / 季度分片；
- 增加长期记忆生命周期与时效复核字段；
- 计划统一归入所属项目，不再设根级 `Plans/`。

这些变化已进入 starter、脚本和对应文档；本文前面的 P0 数据只描述当时的验证阶段。
