# knowledge-workspace · 知识工作台插件

Obsidian 插件：**博客 · 知识库 · 记忆 三层结构的个人工作台首页**，运行时实时扫描 vault 真实数据，无需烘焙快照。作者是本记忆库体系的作者，插件是这套体系的 Obsidian 侧门户——记忆库页签直接读取 `Memory/Todo.md`、`Inbox/` 待审核数与 `Projects/_index.md`。

## 视图结构

头部（品牌 + 操作）→ 视图导航 pill：

| 视图 | 内容 |
|---|---|
| **Todo** | 我的待办（插件 data.json 记录：增删改查 / 逾期·今天·以后·无日期分组 / `@日期` 截止）+ 记忆库 `Inbox/` 待审核速览 |
| **知识地图** | 单行统计条 + 嵌入 Obsidian 原生图谱（点芯片点亮按分区过滤）+ 最近更新 + 快速打开 + 内容体检 |
| **全部笔记** | 知识区全量索引（分组折叠 + 即时过滤） |
| **记忆库** | 记忆系统（子 tab：待办 / 项目 / 待审核）——读 `Memory/Todo.md`（`##` 分组 + `-` 条目 + `~~完成~~` 删除线识别）、`Memory/Projects/_index.md`、`Memory/Inbox/*.md` 的 `- [ ] 待审核` 计数 |
| **日记** | DailyNotes 自动聚合（统计瓦片 + 年份芯片过滤 + 年份分组列表） |

## 安装

1. 把本目录（含 `main.js` / `manifest.json` / `package.json`）拷到 `<vault>/.obsidian/plugins/knowledge-workspace/`
2. Obsidian → 设置 → 第三方插件 → 关闭安全模式 → 启用「知识工作台」
3. 命令面板执行「knowledge-workspace: 打开工作台」或点击左侧 ribbon 图标

## 目录约定

插件按以下 **vault 相对路径**扫描数据（与 starter 骨架一致；如果你的目录名不同，改 `main.js` 顶部的路径常量）：

```text
Knowledge/{AI,Engineering,Methods,Life,_mocs}   -> 篇数（知识地图）
Memory/{Preferences,Plans,Decisions,Lessons,Workflows,Projects} -> 篇数/项目数
Memory/Projects/_index.md   -> 项目列表（name/desc/status/updated）
Memory/Todo.md              -> 待办（## 分组 + - 条目 + ~~完成~~）
Memory/Inbox/*.md           -> 「- [ ] 待审核」计数
DailyNotes/{YYYY}/YYYY_MM_DD.md -> 日记聚合（兼容根层直放）
```

## 说明

- `main.js` 为**手写单文件源码**（CommonJS，无构建步骤、无 sourcemap），约 2400 行
- `data.json`（插件运行时个人数据）不入库
- 版本沿革见 `manifest.json`（当前 1.13.x，minAppVersion 1.4.0，桌面/移动均可用）
