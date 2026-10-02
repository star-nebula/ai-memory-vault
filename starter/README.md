# starter —— 可整体拷走的记忆库骨架

本目录是整套体系的**最小可运行形态**：把里面的内容拷进你的 Obsidian 库根，替换占位符，跑一次索引生成，记忆库即上线。

## 拷贝

```bash
# 把本目录内容拷进你的 Obsidian 库根（AGENTS.md / Templates/ / Memory/）
cp -r starter/* /path/to/your-vault/
```

## 上线四步

1. **替换占位符**：全局搜索 `<VAULT>`（替换为你的库根绝对路径）与 `<项目区>`（替换为你的代码项目根目录）。涉及：`AGENTS.md`、`Memory/AGENTS.md`、`Memory/rule/` 四件、`Memory/Workflows/` 两个文件。
2. **生成索引**：`python scripts/mem_index.py --write`——各层 `_index.md` 是派生物，以后新增笔记重跑即可，手工只润色"一句话定位"。
3. **接入 AI 工具**：把 `Memory/Workflows/AI工具自定义指令-完整版.md`（完整版）或 `AGENTS.md`（最小版，会自动读项目根 `AGENTS.md` 的工具适用）按 `Memory/Workflows/AI工具自定义指令.md` 的落点对照表分发到你的各工具。
4. **挂上门禁**：把会话收尾 checklist（`Memory/rule/收尾与维护.md`）交给你的 AI 工具执行，季度跑一次全部门禁（见 scripts/README.md）。

## 自检

```bash
export AI_MEMORY_DIR=/path/to/your-vault/Memory    # 或在库根直接运行（脚本自动探测 ./Memory）
python scripts/mem_index.py --check     # 应输出 OK：无漂移
python scripts/todo_audit.py --check    # 应输出 [ok] 干净
```

## 示例项目

`Memory/Projects/示例项目/` 是一个占位项目，演示项目层的三件套结构（`_overview.md` + `working/{journal,completed}.md`）与 `Todo.md` 分组的对应关系。改名为你的第一个真实项目即可（改名后同步改 `Todo.md` 的 `## 分组` 标题——分组名必须等于项目目录名，门禁会查）。

## 安全提示

- 记忆层**不要**放进任何有公开远端的 git 仓库；若与公开内容共用仓库，参考 docs/03 的"隐私边界"一节配置 `.gitignore` + `pre-commit` 守卫。
- 含真实路径的项目级钩子（`--projects` 生成物）只留本地，用 `.git/info/exclude` 忽略，**不要写进 `.gitignore` 提交**。
