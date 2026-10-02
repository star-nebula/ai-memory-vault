# starter —— 可整体拷走的记忆库骨架

本目录是整套体系的**最小可运行形态**：把里面的内容拷进你的 Obsidian 库根，记忆库即上线——没有占位符替换、没有依赖安装、没有服务部署。

## 拷贝（唯一的"安装"动作）

```bash
cp -r starter/* /path/to/your-vault/
```

拷完即用：AI 工具进入工作区自动读到根 `AGENTS.md`，按 `Memory/_index.md` 路由读写记忆。规则文本全部按**相对路径**表述，不需要改任何一行。

## 两个可选动作（不改也不影响运行）

1. **生成各层索引**（派生物）：`python scripts/mem_index.py --write`——之后新增笔记重跑即可，手工只润色"一句话定位"。
2. **接入 AI 工具的用户级全局指令**：把 `Memory/Workflows/AI工具自定义指令-完整版.md` 按 `Memory/Workflows/AI工具自定义指令.md` 的落点对照表分发到你的各工具。默认文案相对路径、即贴即用；仅当需要跨工作区全局访问时，才把真源首句替换为一次记忆库绝对路径，再用 `scripts/sync_memory_instructions.py` 一键分发。

## 自检

```bash
python scripts/mem_index.py --check     # 应输出 OK：无漂移
python scripts/todo_audit.py --check    # 应输出 [ok] 干净
```

脚本自动探测记忆库位置（从当前目录向上找 `Memory/`）；在任何位置运行时也可 `export AI_MEMORY_DIR=/path/to/your-vault/Memory` 显式指定。

## 示例项目

`Memory/Projects/示例项目/` 是一个占位项目，演示项目层的三件套结构（`_overview.md` + `working/{journal,completed}.md`）与 `Todo.md` 分组的对应关系。改名为你的第一个真实项目即可（改名后同步改 `Todo.md` 的 `## 分组` 标题——分组名必须等于项目目录名，门禁会查）。

## 安全提示

- 记忆层**不要**放进任何有公开远端的 git 仓库；若与公开内容共用仓库，参考 docs/03 的"隐私边界"一节配置 `.gitignore` + `pre-commit` 守卫。
- 含真实路径的项目级钩子（`--projects` 生成物）只留本地，用 `.git/info/exclude` 忽略，**不要写进 `.gitignore` 提交**。
