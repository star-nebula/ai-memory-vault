# scripts —— 门禁与运维脚本

六个脚本全部**仅用 Python 标准库**（3.9+），无第三方依赖。

## 记忆库定位（Agent 脚本与门禁共用）

按序取：

1. 环境变量 `AI_MEMORY_DIR`（直接指向 `Memory/` 目录）
2. 从当前目录 / 脚本位置**向上探测**名为 `Memory` 且含 `BOOT.md` / `Todo.md` / `rule/` 之一的目录

把脚本放在 vault 根或其子目录运行即可自动命中；也可以显式 `export AI_MEMORY_DIR=...` 后在任何位置运行。

## `memory_boot.py` —— Agent 启动包

```bash
python memory_boot.py --cwd . --json
python memory_boot.py --project demo --budget 6000
```

- 普通任务不自动扫描记忆库；项目任务只生成一个小型启动包。
- 输入固定：`BOOT.md` + 当前项目 `_overview.md` + `_state.md` + `Todo.md` 当前项目切片；Todo 可能被完整读取以切片，但不会整份注入。
- 只读取显式输入；不预读整棵记忆树。
- `--budget` 约束返回的 `text` 字段；JSON 元数据另计，不会被重复计入 text。`--json` 返回 `chars`、`source_chars`、`assembled_chars`、`truncated` 与实际读取文件列表。

## `memory_query.py` —— 有界检索

```bash
python memory_query.py "关键词" --cwd . --limit 5 --budget 5000
python memory_query.py "旧方案" --include-inactive --include-history --json
python memory_query.py "关键词" --all-projects --json
```

- 默认只排除 archived/superseded，其他 status 保留；`--include-inactive` 显式放开。
- 无法识别项目时默认只搜 `scope: global`；跨项目检索必须显式加 `--all-projects`。
- 指定项目时，`Projects/<项目>` 之外的项目树不会进入结果；跨层笔记必须 `scope` 为该项目的名称或 `global`。
- 默认跳过 `Inbox/`、`Archive/`、`working/`；查历史时加 `--include-history`。
- `text` 返回路径、类型、scope、status、更新日期和片段，不展开整篇笔记；`--json` 的 `matches` 只放元数据，避免重复正文。
## `todo_audit.py` —— 待办归档体检（门禁 ②④ + 报告项）

把「**完成 = 移走**」变成可校验项。

```bash
python todo_audit.py                 # 全量报告 → scripts/_out/todo_audit.txt
python todo_audit.py --check         # 门禁：完成信号残留/分组名不映射/Todo 假声明/type 词表外取值 → 退出码 1
python todo_audit.py --cost-check    # 硬门禁：BOOT 源政策 / 实际 assembled 启动包超标 → 退出码 1
python todo_audit.py --content-check # 严格内容债门禁：overview/state/section 截断/缺 state → 退出码 1
python todo_audit.py --scope-check   # 门禁：scope 非法取值/冗余出现 → 退出码 1（季度维护用）
python todo_audit.py --inbox <目录> --audit-date YYYY-MM-DD   # 积压计数 fixture（日常不用）
```

- **词表不写在脚本里**：`type` 合法值机读自 `Memory/rule/写入与禁止.md` 第 5 条的括号清单（解析失败 = 退出码 1，不静默通过）；`scope` 合法值 = `Projects/` 实盘目录名 ∪ `global`，实盘推导
- **阈值在脚本、数字不进文档**：`LIMIT_BOOT` / `LIMIT_OVERVIEW` / `LIMIT_STATE` / `LIMIT_BOOT_APPROX` / `LIMIT_STAGING_CHARS` 是策略常量；实测只进报告
- **暂存层判压面只收 `journal.md`**：`working/completed.md` 属终态层，只进「最重几份」观测面，不判压
- **每日 Inbox 审核积压**（报告第十节）：`Inbox/` 根下登记日期早于运行当天的文件份数；**只报不拦**，成因可能是审核任务没跑，也可能是审过但「待本人决定」把整份扣住
- 默认报告写文件而非 stdout（Windows 控制台 GBK 吞输出的环境教训）；`-o` 可改落点

## `encoding_guard.py` —— 编码守卫 + 裸控制符门（门禁 ③）

```bash
python encoding_guard.py <路径>                 # 体检：有非 UTF-8 或权威面裸控制符 → 退出码 1
python encoding_guard.py <路径> --fix --backup  # GBK/GB18030/BOM → 纯 UTF-8（先备份）
python encoding_guard.py <路径> --no-ctrl       # 跳过控制符段（超大树快扫）
```

- 裸控制符 = AI 把 `\a \b \f \r \t \v` 当转义吃掉后残留的 C0/DEL（含不构成 CRLF 的裸 CR、吞字形态的 TAB）——**这类文件会被 ripgrep 判为二进制，对一切基于检索的审计隐形**
- **控制符只报告不自动改**：被吞的是原文那个字母，须逐处核对原意后手工补回
- 权威面判据 = 路径含 `Memory`（脚本顶部 `GATE_MARKS`）；其余面只报告——恒红的门禁等于没有门禁

## `sync_memory_instructions.py` —— 指令分发同步器（收尾 ④）

```bash
python sync_memory_instructions.py              # 部署真源到各工具位（幂等）
python sync_memory_instructions.py --check      # 只读比对 + 真源裸控制符 + 声明位伪值 → 漂移退出码 1
python sync_memory_instructions.py --projects   # 部署项目级钩子（只新建不覆盖；无唯一代码根只报告不猜）
```

- 真源 = `Memory/Workflows/AI工具自定义指令-完整版.md`（唯一可编辑来源）
- **声明位伪值门**：检查真源 / 分发手册 / `Memory/AGENTS.md` / `Memory/Rule.md` 里「当前项目名」后面不得出现 `<项目名>`；项目名只能由 `memory_boot.py` / `memory_query.py` 在运行时判定
- **部署目标在脚本顶部 `TARGETS` 配置，默认全注释——clone 后直接跑不会碰你的工具位**；启用分发时解开你要的工具（支持 `~` 展开；`file` 软链退化复制 / `json-inject` 注入 JSON 键两种形态），未安装的工具自动 SKIP
- **先 `--check` 再部署**：定位类脚本的输出面是别人的配置文件，写下去就不是本地可逆动作
- 项目级钩子含真实路径 → **只留本地**，所在 git 仓用 `.git/info/exclude` 忽略（不要写 `.gitignore`——提交它就会把钩子文件名披露给远端）

## 收尾 / 季度维护怎么挂

见 `../starter/Memory/rule/收尾与维护.md`：每次会话收尾跑 `todo_audit.py --check` + `sync_memory_instructions.py --check`，并对记忆库跑 `encoding_guard.py`；结构变化时加 `--cost-check` / `--content-check`，季度再加 `--scope-check`。
