---
type: project-fact
created: 2026-10-04
updated: 2026-10-04
tags: [live-diagram, journal, 工作态]
---

# live-diagram · 过程流水（暂存层）

> 时间倒序，每日一节；有长期价值的条目标「候选」，会话收尾蒸馏到最终位置。

## 2026-10-04（建档当日：skill 重写 + 首个应用成片）

- 【重写】以 ythx-101/live-panel-skill 为蓝本重构为自有 skill `live-diagram`：核心机制保留（seek(t) 纯函数、状态机产日志、DOM 自检、回放像素比对），代码全部重写。**原脚本在 Windows 不可跑**（`sh -c` + fd 传递），改为 stdlib WebSocket 客户端驱动 `--remote-debugging-port=0`（端口经 `DevToolsActivePort` 文件探测，读文件有短暂 PermissionError 竞态需重试）。决策与备选：[[Decisions/live-diagram重写为自有skill与跨平台驱动|live-diagram重写为自有skill与跨平台驱动]]。
- 【踩坑→已修】JS 对象字面量方法收尾括号数错（`}}}),` 多一括号一右括号）靠 `node --check` 逐次定位；`worst` 字段命名 `lowText/highText` 语义反直觉，改为 `okText/badText`；gauge 需 `bad:'high'|'low'` 指明坏侧（GPU 负载"越高越糟"与显存同向）；bar 只认 0..1，非分数值要配 `max` 归一化；`worker.off` / `alarm.t0` 缺省会 NaN（已加默认 0）；log 标题底部与首行文本擦碰 2px（标题上移 4px 解决）。
- 【验证】`check --samples 40 --repeat`：terminal-dark 与 light-pastel 双主题 0 问题；回放 0 像素可见差异（最大通道差 ≤2，亚像素噪声级）。
- 【首个应用】AI Memory Vault 运行面板（4:5 终端暗色）：主流程「AI 工具会话 → 根 AGENTS.md → 读取路由 → Memory/ 分层 → 写入登记 → 会话收尾」，右栏四道门禁脚本工位 + 库健康度仪表 + 门禁告警台（光束指向收尾盒），一条 `phase` cycle 主时间线推导全部高亮；内容取自本仓 README/docs 真实结构，数字标注示意。43 采样点 0 问题、回放一致、900 帧成片渲染完成。
- 【澄清】本地在用记忆库 ≠ 开源发布版（本仓为发布时点快照，本地持续演化）：面板画的是开源版结构，不代表本地在用版全貌。
- 【候选】`?t=` 单帧模式与 `--video` 从 mp4 切帧检查这两条便利功能尚未写入 SKILL.md 正文（schema 文档已记 `?t=`）。
