# Vibe coding 大型项目开发规则（Rule 分节）

> **大型项目开发时读本文件**：代码项目里进行多文件、跨会话、或涉及架构/技术选型的开发任务。单文件修改、一次性脚本、单轮问答不触发。
> 三条核心规则的短版常驻 `AGENTS.md`（系统提示层生效）；季度自检挂接见 `rule\收尾与维护.md`「定期维护」。

## A. 决策笔记格式与生命周期

`Decisions/` 每条笔记 frontmatter 必须含 `status`，正文必须含「备选方案」节：

```markdown
---
type: decision
scope: <项目名或 global>
status: proposed | implemented | rejected-<一句话理由> | superseded-by-[[新笔记]] | archived-YYYY-QX
created: YYYY-MM-DD
updated: YYYY-MM-DD
tags: [...]
---
# <决策标题>
## 背景      （动机，独立于方案可读）
## 决策      （implemented 用现在时；proposed 用将来时）
## 备选方案  （强制：每条真实备选 + 为什么没选。无法重建时留 `<!-- alternatives-not-recorded (历史遗留) -->`）
## 后果      （付出了什么 + 换到了什么）
```

生命周期规则：

1. **新增决策前 grep `Decisions/` 标题关键词**：同主题旧笔记存在 → 互链。完全推翻 → 旧笔记加 `status: superseded-by-[[新笔记]]`；部分推翻 → 两条都留 active、互链，并更新旧笔记中仍现行的事实（决策反转的完整规则见 `rule\写入与禁止.md`「写入」第 6 条，此处不复述）。
2. **落地后改现在时**：`proposed` → `implemented` 时，`## 决策` 改现在时，验收标准（若有）折进 `## 后果`。不留 "should / 将要"。
3. **归档**：>90 天、已固化、不再指导未来工作的 implemented 决策，按 `rule\收尾与维护.md`「定期维护」归档到 `Archive/decisions-YYYY-QX.md`，原位留 `status: archived-YYYY-QX` + wikilink。归档后冻结，不作现行依据。

## B. 流程笔记格式

`Workflows/` 每条 SOP 必须是步骤化 how-to：

```markdown
## 前提
（开始前必须已成立的状态 / 文件 / 工具）
## 步骤
1. <动作> → 验证：<可观测的成功信号>
2. <动作> → 验证：...
## 收尾
（归档 / 登记 / Todo 同步动作）
```

规则：

1. **每步带验证点**：验证点 = 文件存在、脚本退出码、输出含某字符串等可观测信号——不是「做 X」，而是「做 X → 验证 Y」。
2. **不复述决策论证**：流程里涉及「为什么这么做」，链向 `Decisions/<笔记>`。
3. **流程变更同步更新手册**：会话内改流程就改对应 `Workflows/` 笔记，不留「以后补」。
