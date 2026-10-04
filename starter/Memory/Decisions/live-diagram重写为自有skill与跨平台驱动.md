---
type: decision
scope: live-diagram
status: implemented
created: 2026-10-04
updated: 2026-10-04
tags: [live-diagram, skill, 架构, windows, 决策]
via: ZCode 会话 2026-10-04（用户指派：重构 ythx-101/live-panel-skill 为自有 skill）
---

# live-diagram 重写为自有 skill 与跨平台驱动

## 决策

把 [ythx-101/live-panel-skill](https://github.com/ythx-101/live-panel-skill) **重写**为自有 skill `live-diagram`（安装于 AI 工具 skills 目录），核心理念原样保留（`seek(t)` 纯函数确定性、版面固定动的是系统状态、三节奏叠加、日志由状态机产出、DOM 帧检查、示意标注），实现全部自研：

1. **Chrome 驱动改 stdlib WebSocket**：`--remote-debugging-port=0` + 从 `DevToolsActivePort` 文件探测端口 + 手写最小 WS 客户端（握手/掩码/分片/ping-pong，约百行）。
2. **三脚本合一**：`livediagram.py render|check|build` 单文件 CLI。
3. **画幅扩到 5 种**（原 3 种）：新增 `9:16`、`16:9`。
4. **文档中文化**、调色板与字体栈按 Windows（Cascadia/Consolas/雅黑兜底）重设；示例为原创内容（RAG 管线面板），不搬运原仓署名示例。

## 背景

原 skill 在 Windows 上**无法运行**：其 Chrome 驱动用 `sh -c 'exec "$@" 3<&… 4>&…'` 传 POSIX 文件描述符。且需要自有命名、自有文档、可长期自行维护的实现。

## 备选方案

- **直接安装原 skill**：被否——Windows 跑不起来；且描述/示例/署名均是他人的，不符合"自己的 skill"。
- **只修补原脚本的跨平台性**：被否——`sh -c` 管道深嵌其渲染/检查两个脚本，改动面不小且后续仍维护一份别人的代码结构；WS 方案把"驱动"收敛成独立一层，反而更短。
- **Playwright / pyppeteer 等第三方库**：被否——引入 pip 依赖树，违背原 skill"仅标准库"的部署优点；能力上只用到 evaluate + screenshot，手写 WS 更划算。
- **每帧冷启动 Chrome `--screenshot`**：被否——900 帧 × 每次数百 ms 启动，渲染时间不可接受。

## 结果

2026-10-04 实施完成：双主题 DOM 自检 0 问题、`--repeat` 回放 0 像素可见差异、两支 900 帧成片（示例 RAG 面板 + AI Memory Vault 面板）渲染成功。验证过程中修掉的语义/健壮性问题（gauge `bad` 侧、bar `max` 归一化、`worst` 字段命名、`off/t0` 缺省 NaN）已沉淀在引擎与配置字段表。
