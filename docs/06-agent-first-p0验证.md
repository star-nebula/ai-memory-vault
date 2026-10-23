# Agent-first 记忆启动 P0 验证

> 分支：`codex/agent-boot-p0`（本地验证分支，不推送云端）
> 范围：只改发行版仓库 `ai-memory-vault`，不改运行中的 `E:\knowledge\vault\Memory`。

## 目标

把默认读取从“先看索引、再读 Todo、再读项目概况”改为：

1. 普通任务不默认扫描记忆库；
2. 项目任务只生成有界启动包；
3. 查历史/原因/排障只用有界检索返回片段；
4. `_index.md` 降级为生成/校验目录，不参与 Agent 启动。

## 新增命令

```bash
python scripts/memory_boot.py --cwd <项目根> --json
python scripts/memory_query.py "关键词" --cwd <项目根> --limit 5 --budget 5000
```

### `memory_boot.py`

输入固定为四类：

- `Memory/BOOT.md`：唯一常驻热层；
- `Projects/<项目名>/_overview.md`：稳定项目卡片，去除 frontmatter；
- `Projects/<项目名>/_state.md`：当前目标、阻塞、下一步，去除 frontmatter；
- `Todo.md` 的当前项目切片。

不读取 `_index.md` 或各层 `_index.md`。`--budget` 是硬上限，`--json` 返回实际字符数、原始字符数、是否截断和实际读取文件列表。

### `memory_query.py`

- 默认只搜活跃笔记，排除 `archived` / `superseded`；
- 默认跳过 `Inbox/`、`Archive/`、`working/`；
- 返回路径、类型、scope、status、更新日期和片段，不展开整篇；
- `--include-inactive` 查历史状态，`--include-history` 查过程历史。

## 入口收缩

`starter/` 的入口文件改成：

| 文件 | 角色 |
|---|---|
| `AGENTS.md` | 工作区门牌、硬规则、启动/查询命令 |
| `Memory/AGENTS.md` | 记忆库短钩子，不要求读 `_index` |
| `Memory/Rule.md` | 写入/收尾/维护时才读的规则路由 |
| `Memory/BOOT.md` | 唯一常驻热层 |

`_index.md` 保留用于 `mem_index.py` 校验与诊断，但明确标注“Agent 启动不读”。

## 本次验证数据

在 `starter/` 示例工作区：

| 指标 | 结果 |
|---|---:|
| 根 `AGENTS.md` | 2,233 字符 |
| `Memory/AGENTS.md` | 969 字符 |
| `Memory/Rule.md` | 768 字符 |
| `Memory/BOOT.md` | 469 字符 |
| 进入 `_index` 前的入口合计 | 4,439 字符 |
| 示例项目启动包 | 1,335 字符 |
| 启动包预算 | 6,000 字符 |
| `_index.md` 是否参与启动 | 否 |

与旧 starter 的“三件套”对比：旧路径约为 `_index.md` 4,129 + `Todo.md` 355 + 最大 overview 1,452 = **5,936 字符**；新启动包为 **1,335 字符**，约减少 **77.5%**。`_index.md` 仍保留用于门禁，但不再进入启动上下文。

验证命令：

```bash
python -m unittest discover -s scripts/tests -p "test_*.py" -v
python scripts/mem_index.py --check
python scripts/todo_audit.py --check
python scripts/todo_audit.py --cost-check
python scripts/encoding_guard.py starter --no-ctrl
python scripts/sync_memory_instructions.py --check
```

当前结果：单元测试通过；索引门禁通过；待办门禁通过；`--cost-check` 通过；编码检查通过；指令声明位检查通过。

## 真实库只读压测

对 `E:\knowledge\vault\Memory` 只读运行、未写入：

- 项目 `记忆库` 的启动包：**2,607 字符**，读取 `Projects/记忆库/_overview.md` + `Todo.md`；`_index.md` 未读。
- 查询 `开场成本`：返回 5/10 条命中，输出 **2,826 字符**（预算 5,000）。
- 查询 `索引瘦身`：返回 3/3 条命中，输出 **1,755 字符**。

当前运行库还没有 `BOOT.md` 和项目 `_state.md`，所以这次是“迁移前只读基线”；加入两者后，启动包仍受 `--budget` 硬限制。

## 未进入本批的范围

- 移除 `_index.md` 与 `mem_index.py` 的兼容依赖；
- Todo 按项目物理拆分（当前先由 `memory_boot.py` 做虚拟切片）；
- journal / completed 物理分片；
- 生命周期字段、定时后台蒸馏、事务性写入器；
- 把本机运行库 `E:\knowledge\vault\Memory` 切换到新结构。

在这些项目完成前，`_index.md` 仍是校验派生物，但不是 Agent 启动上下文。
