# scripts —— 门禁与运维脚本

四个脚本全部**仅用 Python 标准库**（3.9+），无第三方依赖。

## 记忆库定位（三个入口脚本共用）

按序取：

1. 环境变量 `AI_MEMORY_DIR`（直接指向 `Memory/` 目录）
2. 从当前目录 / 脚本位置**向上探测**名为 `Memory` 且含 `Todo.md` / `_index.md` / `rule/` 之一的目录

把脚本放在 vault 根或其子目录运行即可自动命中；也可以显式 `export AI_MEMORY_DIR=...` 后在任何位置运行。

## `mem_index.py` —— 索引生成 / 校验（门禁 ①⑤）

各层 `_index.md` 的**派生器 + 门禁**。背景：手工索引必然漂移，索引必须是派生物。

```bash
python mem_index.py --write          # 生成/更新（幂等；新增自动补行，人工润色的「一句话」保留）
python mem_index.py --check          # 门禁：缺行/失效行/地图页漏列/成对表漂移/读时时效失明 → 退出码 1
python mem_index.py --write --layer Lessons   # 只处理某层
```

- 覆盖层：`Preferences` `Plans` `Lessons` `Workflows` `Projects`（**`Decisions` 除外**——其 `_index.md` 是专用格式，手工维护）
- **门禁 ⑤**：比对「库根 `AGENTS.md` §同名文件消歧 ↔ `Memory/_index.md` §同名文件消歧」两张互称逐字一致的手工表，只报告不自动改
- **读时时效门**：校验 `Memory/_index.md` 的「读时时效」小节在场、判据指针（默认指向 `Lessons/批量改写脚本的自检失明.md`，可在脚本顶部 `READTIME_POINTER` 常量改）未被抽走——改名/删除即报红

## `todo_audit.py` —— 待办归档体检（门禁 ②④ + 成本报告）

把「**完成 = 移走**」变成可校验项。

```bash
python todo_audit.py                 # 全量报告 → scripts/_out/todo_audit.txt
python todo_audit.py --check         # 门禁：完成信号残留/分组名不映射/Todo 假声明/type 词表外取值 → 退出码 1
python todo_audit.py --cost-check    # 门禁：开场三件套成本超标 → 退出码 1（季度维护用）
python todo_audit.py --scope-check   # 门禁：scope 非法取值/冗余出现 → 退出码 1（季度维护用）
```

- **词表不写在脚本里**：`type` 合法值机读自 `Memory/rule/写入与禁止.md` 第 5 条的括号清单（解析失败 = 退出码 1，不静默通过）；`scope` 合法值 = `Projects/` 实盘目录名 ∪ `global`，实盘推导
- **阈值在脚本、数字不进文档**：`LIMIT_INDEX` / `LIMIT_TODO` / `LIMIT_OVERVIEW` / `LIMIT_TRIO_WORST` / `LIMIT_STAGING_CHARS` 是策略常量；实测只进报告
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
python sync_memory_instructions.py --check      # 只读比对 + 真源裸控制符体检 → 漂移退出码 1
python sync_memory_instructions.py --projects   # 部署项目级钩子（只新建不覆盖；无唯一代码根只报告不猜）
```

- 真源 = `Memory/Workflows/AI工具自定义指令-完整版.md`（唯一可编辑来源）
- **部署目标在脚本顶部 `TARGETS` 配置，默认全注释——clone 后直接跑不会碰你的工具位**；启用分发时解开你要的工具（支持 `~` 展开；`file` 软链退化复制 / `json-inject` 注入 JSON 键两种形态），未安装的工具自动 SKIP
- **先 `--check` 再部署**：定位类脚本的输出面是别人的配置文件，写下去就不是本地可逆动作
- 项目级钩子含真实路径 → **只留本地**，所在 git 仓用 `.git/info/exclude` 忽略（不要写 `.gitignore`——提交它就会把钩子文件名披露给远端）

## 收尾 / 季度维护怎么挂

见 `../starter/Memory/rule/收尾与维护.md`：每次会话收尾跑 `mem_index.py --check` + `todo_audit.py --check` + `sync_memory_instructions.py --check`；季度再加 `--cost-check` / `--scope-check` / `encoding_guard.py`。
