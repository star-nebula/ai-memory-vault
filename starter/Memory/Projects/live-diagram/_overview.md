---
type: project-fact
created: 2026-10-04
updated: 2026-10-04
tags: [live-diagram, skill, 动态架构图, 动画, mp4, 项目概况]
summary: 真实示例：用本系统管理一个"活的架构图" skill 的研发记忆——JSON 配置渲染运行动画架构图，产出 mp4 / 动态网页。
via: ZCode 会话 2026-10-04（重构 ythx-101/live-panel-skill 为自有 skill）
---

# live-diagram — 活的架构图 skill · 项目概况

**状态：🟢 可用**（引擎自研完成，双主题帧检查 0 问题 + 回放逐像素一致，两支成片渲染交付）。

## 定位

自有 AI skill：把**一份 JSON 配置**渲染成版面固定的运行动画架构图（终端暗色风 / 浅色粉彩信息图风），产出 H.264 mp4（X / 小红书 / 抖音 / B 站）或可在浏览器直接打开的动态网页。核心理念重构自 [ythx-101/live-panel-skill](https://github.com/ythx-101/live-panel-skill) 并全部重写：`seek(t)` 纯函数确定性渲染、版面不动动的是系统状态、三节奏叠加、日志由状态机产出保证"处处一个事实"、DOM 帧检查、示意数据必须标注。工程改进：**Windows 原生支持**（stdlib WebSocket 驱动 Chrome，替代原 POSIX fd 管道）、三脚本合一单 CLI、画幅扩至 5 种（含 9:16 / 16:9）。决策与备选：[[Decisions/live-diagram重写为自有skill与跨平台驱动|live-diagram重写为自有skill与跨平台驱动]]。

## 关键路径

- **skill 本体**：AI 工具的 skills 安装目录（`~/.zcode/skills/live-diagram/`：`SKILL.md` + `assets/template.html` 引擎 + `scripts/livediagram.py` 唯一 CLI（render/check/build）+ `references/` 中文动法与字段表 + `examples/rag-pipeline/` 完整示例）
- **首个应用成片**：本机工作区 `memory-vault-panel/`——AI Memory Vault 项目运行面板（config.json + memory-vault.mp4 + 自包含 html）

## 关联

- 题材来源（首个成片）：[star-nebula/ai-memory-vault](https://github.com/star-nebula/ai-memory-vault)（即本仓）。**注意**：作者本地在用的记忆库与开源发布版不是完全一致——开源版是发布时点快照，本地持续演化；首个成片画的是开源版结构
- 上游方法来源：[ythx-101/live-panel-skill](https://github.com/ythx-101/live-panel-skill)（动法学自 @thedelost 的 Codex agent 面板 clip；本 skill 为独立重实现，未复制其示例与代码）
