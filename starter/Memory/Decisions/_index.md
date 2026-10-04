# 决策索引（_index）

> 紧凑导航视图，一眼扫完全部决策；详论证见各 `Decisions/*.md` 详笔记。
> 格式：`[YYYY-MM-DD] [分类] 决策项 → 选定方案 | 原因 | via:来源`
> 分类前缀：[架构] / [工具] / [约定] / [性能] / [安全]
> 维护：新增决策时同步补一行（与详笔记同日）。**本页是专用格式页，手工维护**（其余各层 `_index.md` 由脚本生成）；季度归档见 Rule 目录页「定期维护」。

## 架构（[架构]）

- [2026-10-04] [架构] live-panel-skill 重写为自有 skill live-diagram → 核心理念保留（seek(t) 确定性/状态机产日志/帧检查），实现全自研：stdlib WebSocket 驱动 Chrome（替代 POSIX fd 管道，Windows 原生可用）、render/check/build 单 CLI、5 种画幅 | 原脚本 Windows 跑不起来（sh -c 传 fd）；备选与论证见详笔记 | via:ZCode 会话 10-04（[[Decisions/live-diagram重写为自有skill与跨平台驱动]]）

## 工具（[工具]）

（暂无）

## 约定（[约定]）

（暂无）

---
> 条数与分类计数**不在此维护**（本页列表即事实源，复述必漂）。季度归档时本索引同步裁剪（已归档项移入 `Archive/decisions-YYYY-QX.md` 并保留 wikilink）。
