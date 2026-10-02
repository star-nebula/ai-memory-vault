"use strict";
/*
 * 知识工作台（knowledge-workspace）
 * 博客 · 知识库 · 记忆 三层结构的个人工作台首页。
 * 运行时通过 Obsidian vault API 实时扫描真实数据，无需烘焙快照。
 *
 * 结构（参考成熟 Dashboard 的「视图切换」模式，内容分区不堆叠）：
 *   头部（品牌 + 操作）→ 视图导航 pill（Home / Todo / 知识地图 / 记忆库 / 日记 / 全部笔记）
 *   ├ Todo：我的待办（插件 data.json 记录：增删改查 / 逾期·今天·以后·无日期分组 / @日期截止）+ 待审核速览
 *   ├ 知识库：知识地图（单行统计条 + 嵌入 Obsidian 原生图谱，点芯片点亮按分区过滤）+ 最近更新 + 快速打开 + 内容体检
 *   ├ 全部笔记：Knowledge 区全量索引（分组折叠 + 即时过滤，接替已删除的 All notes-MOC.md）
 *   ├ 记忆库：记忆系统（子 tab：待办 / 项目 / 待审核）
 *   └ 日记：DailyNotes 自动聚合（单页整合：统计瓦片 + 年份芯片过滤 + 年份分组列表，接替 DailyNotes-MOC.md 的 dataviewjs）
 *
 * 数据来源（vault 相对路径）：
 *   Knowledge/{AI,Engineering,Methods,Life,_mocs}   -> 篇数
 *   Memory/{Preferences,Plans,Decisions,Lessons,Workflows,Projects} -> 篇数/项目数
 *   Memory/Projects/_index.md   -> 项目列表（name/desc/status/updated）
 *   Memory/Todo.md              -> 待办（## 分组 + - 条目 + ~~完成~~）
 *   Memory/Inbox/*.md           -> 「- [ ] 待审核」计数
 *   自媒体内容/文稿/*.md        -> frontmatter「发布状态」+ 归档计数
 *   作坊 / 档案                 -> 篇数
 *   DailyNotes/{YYYY}/YYYY_MM_DD.md -> 日记聚合（日期/年份从文件名解析；兼容根层直放）
 */
const { Plugin, ItemView, Notice, TFile, TFolder, Modal, WorkspaceLeaf } = require("obsidian");

const VIEW_TYPE = "knowledge-workspace";

/* 知识地图 MOC 图谱范围：Knowledge 二级目录枚举 + 根层散件。
   不能用 path:"Knowledge"——path: 是对完整路径（含文件名）不分大小写的子串匹配，
   Memory/Projects/knowledge/ 等同名路径会假命中漏进图谱（实测 21 个文件）。
   也不用超长 OR——v1.8.3 实测 300+ 词超出原生过滤器解析能力（失效=全库），此处仅 6 项安全。
   维护点：Knowledge 新增二级目录或根层散 md 时，在数组补一项（已实测 5 目录枚举在 Knowledge/ 外零假命中）。 */
const GRAPH_SCOPE_PARTS = [
  'path:"Knowledge/AI"',
  'path:"Knowledge/Engineering"',
  'path:"Knowledge/Methods"',
  'path:"Knowledge/Life"',
  'path:"Knowledge/_mocs"',
];
/* 范围注记：原第 6 项 path:"All notes-MOC" 随该文件 2026-09-28 删除而移除——其「Knowledge 全量索引」
   作用由工作台「全部笔记」视图接替，Knowledge 根层现已无散件。 */
const GRAPH_SCOPE_QUERY = GRAPH_SCOPE_PARTS.join(" OR ");

/* 知识地图芯片过滤：单分区查询词（与 GRAPH_SCOPE_PARTS 同一套 path: 子串语义，命中面一致） */
function kbFilterQuery(path) {
  return 'path:"' + path + '"';
}

/* 样式模型：工作台始终跟随 Obsidian 主题（根节点固定 data-style="theme"，配色取主题变量，明暗自动适配）。
   Soft UI 的亮/暗变量块仍保留在下方 CSS 中，但 UI 不再提供切换入口（用户 2026-09-26 裁定），仅作回退底稿。 */

/* ============================ 工具函数 ============================ */

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function countMd(folder) {
  if (!folder || !Array.isArray(folder.children)) return 0;
  return folder.children.filter((c) => c.extension === "md").length;
}

function isFolder(node) {
  return !!(node && Array.isArray(node.children));
}

/* ============================ 日记模块（DailyNotes 聚合） ============================ */

/* 日记首句预览：口径与 DailyNotes-MOC 的 dataviewjs 一致 —— 跳过 frontmatter / 空行 /
   标题 / 引用 / 表格 / 代码块，取首条有内容的行截 40 字。 */
function diaryPreview(text) {
  const lines = String(text == null ? "" : text).split("\n");
  let inFrontmatter = false;
  let fmClosed = false;
  for (const raw of lines) {
    const s = raw.trim();
    if (!fmClosed) {
      if (s === "---") { inFrontmatter = !inFrontmatter; fmClosed = !inFrontmatter; continue; }
      if (inFrontmatter) continue;
      fmClosed = true;
    }
    if (!s || s.startsWith("#") || s.startsWith(">") || s.startsWith("|") || s.startsWith("```")) continue;
    return s.length > 40 ? s.slice(0, 40) + "…" : s;
  }
  return "（空）";
}

/* 预览缓存：键 = path|mtime。vault 实时联动（modify/create/…）高频重扫，205 篇日记逐次全量
   重读不可接受；mtime 不变的文件直接取缓存，编辑过的文件键变化自然失效。模块级对象是
   scan 的唯一有状态旁路（scan 本体仍保持「传 app 即可复现」的纯函数形态）。 */
const DIARY_PREVIEW_CACHE = {};

/* 星期标注（日记行用）：解析失败返回空串不显示 */
function diaryWeekday(dateStr) {
  const d = new Date(dateStr + "T00:00:00");
  return isNaN(d.getTime()) ? "" : ["周日", "周一", "周二", "周三", "周四", "周五", "周六"][d.getDay()];
}

/* ============================ Todo 模块（个人待办，插件 data.json 记录） ============================ */

function localToday() {
  const d = new Date();
  const p = (x) => String(x).padStart(2, "0");
  return d.getFullYear() + "-" + p(d.getMonth() + 1) + "-" + p(d.getDate());
}

/* 分类与优先级预设（分类按用户实际工作线归纳：项目开发 / 内容创作 / 学习 / 求职 / 知识库 / 日常） */
const TODO_PRIORITIES = [
  { key: "", label: "无" },
  { key: "high", label: "高" },
  { key: "medium", label: "中" },
  { key: "low", label: "低" },
];
const TODO_CATEGORIES = [
  { key: "", label: "" },
  { key: "dev", label: "💻 开发" },
  { key: "content", label: "✍️ 内容" },
  { key: "study", label: "📚 学习" },
  { key: "job", label: "🎯 求职" },
  { key: "kb", label: "🛠️ 知识库" },
  { key: "daily", label: "🏠 日常" },
  { key: "other", label: "📌 其他" },
];

/* 兼容旧结构（{text}）并补默认字段 */
function normalizeTodo(t) {
  return {
    id: t.id || newTodoId(),
    title: t.title || t.text || "（无标题）",
    notes: t.notes || "",
    priority: t.priority || "",
    category: t.category || "",
    due: t.due || null,
    time: t.time || null,
    done: !!t.done,
  };
}

/* 输入解析：结尾 @YYYY-MM-DD [HH:MM] 设截止；仅 @HH:MM 视为今天 + 时间 */
function parseTodoInput(raw) {
  const text = String(raw == null ? "" : raw).trim();
  let m = text.match(/@(\d{4}-\d{2}-\d{2})(?:\s+(\d{1,2}:\d{2}))?\s*$/);
  if (m) return { text: text.slice(0, m.index).trim(), due: m[1], time: m[2] || null };
  m = text.match(/@(\d{1,2}:\d{2})\s*$/);
  if (m) return { text: text.slice(0, m.index).trim(), due: localToday(), time: m[1] };
  return { text: text, due: null, time: null };
}

function newTodoId() {
  return "t" + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
}

/* ============================ 扫描逻辑（纯函数） ============================ */

async function scan(app) {
  const vault = app.vault;
  const read = (p) => vault.adapter.read(p);
  const getFolder = (p) => vault.getAbstractFileByPath(p);

  // 知识库篇数
  const k = {
    AI: countMd(getFolder("Knowledge/AI")),
    Engineering: countMd(getFolder("Knowledge/Engineering")),
    Methods: countMd(getFolder("Knowledge/Methods")),
    Life: countMd(getFolder("Knowledge/Life")),
    _mocs: countMd(getFolder("Knowledge/_mocs")),
  };
  k.total = k.AI + k.Engineering + k.Methods + k.Life + k._mocs + countMd(getFolder("Knowledge"));

  // 全部笔记索引（全部笔记索引，2026-09-29 起分类口径 = frontmatter category（与 MOC 对应的体系），
  // 不再用磁盘目录。无 category 时：MOC 文档（_mocs/ 下或文件名含 MOC）归「MOC」，其余归「未分类」。）
  const knowledgeNotes = [];
  const isMocPath = (p, name) =>
    String(p).indexOf("Knowledge/_mocs/") === 0 || String(name).indexOf("MOC") >= 0;
  const mocSourceName = (p) => {
    const base = String(p).split("/").pop().replace(/\.md$/, "");
    return base.indexOf("MOC") >= 0 ? base : null;
  };
  // 解析 frontmatter category 数组：["🤖 AI大模型", "机器学习"] → 去掉前导 emoji 的路径数组
  const stripEmoji = (s) => String(s).replace(/^\p{Extended_Pictographic}\uFE0F?\s*/u, "").trim();
  const parseCats = (f) => {
    try {
      const fm = app.metadataCache.getFileCache(f)?.frontmatter;
      const val = fm && fm.category;
      if (Array.isArray(val)) return val.map(stripEmoji).filter(Boolean);
      if (typeof val === "string" && val.trim()) {
        // 行内 [a, b] 或单字符串
        const inner = val.trim().replace(/^\[/, "").replace(/\]$/, "");
        return inner.split(",").map(stripEmoji).filter(Boolean);
      }
    } catch (e) { /* metadataCache 未就绪则按未分类处理 */ }
    return [];
  };
  vault.getMarkdownFiles().forEach((f) => {
    if (f.path.indexOf("Knowledge/") !== 0) return;
    const parts = f.path.split("/");
    const mocs = [];
    try {
      const backs = app.metadataCache && app.metadataCache.getBacklinksForFile(f);
      if (backs && typeof backs.forEach === "function") {
        backs.forEach((links, src) => {
          const name = mocSourceName(src);
          if (name && mocs.indexOf(name) < 0) mocs.push(name);
        });
      }
    } catch (e) { /* metadataCache 未就绪则暂缺所属 MOC，随下次扫描补全 */ }
    mocs.sort();
    // 展示标题：frontmatter title（思维导图节点等展示用，缺省回退文件名）；
    // 简介：frontmatter abstract（AI/工作台检索与全部笔记视图展示用），缺省空串
    let abstract = "";
    let title = "";
    try {
      const cache = app.metadataCache.getFileCache(f);
      const fmv = cache && cache.frontmatter;
      const val = fmv && fmv.abstract;
      if (typeof val === "string") abstract = val.trim();
      else if (Array.isArray(val)) abstract = val.join(" · ").trim();
      const tval = fmv && fmv.title;
      if (typeof tval === "string") title = tval.trim();
      else if (typeof tval === "number") title = String(tval);
    } catch (e) { /* metadataCache 未就绪则暂缺，随下次扫描补全 */ }
    const cats = parseCats(f);
    // 分类路径：category 主名 → 末级（若不同）；无 category 时：MOC 文档归「MOC」，其余归「未分类」
    const area = cats.length ? cats[0] : (isMocPath(f.path, f.name) ? "MOC" : "未分类");
    const sub = cats.length >= 2 ? cats[cats.length - 1] : "";
    const ia = CATEGORY_ORDER.indexOf(area);
    const _rank = { r: ia < 0 ? (area === "MOC" ? 95 : 90) : ia, area, sub };
    const baseName = parts[parts.length - 1].replace(/\.md$/, "");
    knowledgeNotes.push({ path: f.path, name: baseName, title: title || baseName, area, sub, mocs, abstract, _rank });
  });
  // 排序：分类优先（category 主名 → 末级），名称次之；zh() 为模块级中文拼音序比较器
  // （按文件名排 = 列表形态的既有顺序；思维导图内部另按展示标题排）
  knowledgeNotes.sort((a, b) => {
    const ra = a._rank, rb = b._rank;
    return ra.r - rb.r || zh(ra.area, rb.area) || zh(ra.sub, rb.sub) || zh(a.name, b.name);
  });

  // 主分类名 → MOC 页路径：扫 _mocs/ 下文件名含 MOC 的页，用其 category 主名（去 emoji）匹配
  const mocPaths = {};
  vault.getMarkdownFiles().forEach((f) => {
    if (f.path.indexOf("Knowledge/_mocs/") !== 0) return;
    const base = f.path.split("/").pop().replace(/\.md$/, "");
    if (base.indexOf("MOC") < 0) return;
    const cats = parseCats(f);
    const key = cats.length ? cats[0] : stripEmoji(base.replace(/-?MOC.*$/, ""));
    if (key && !mocPaths[key]) mocPaths[key] = f.path.replace(/\.md$/, "");
  });

  // 记忆系统篇数 + 项目数
  const mem = {
    Preferences: countMd(getFolder("Memory/Preferences")),
    Plans: countMd(getFolder("Memory/Plans")),
    Decisions: countMd(getFolder("Memory/Decisions")),
    Lessons: countMd(getFolder("Memory/Lessons")),
    Workflows: countMd(getFolder("Memory/Workflows")),
  };
  const projFolder = getFolder("Memory/Projects");
  mem.Projects = projFolder ? projFolder.children.filter(isFolder).length : 0;

  // 项目列表（解析 Projects/_index.md 表格）
  const projects = [];
  try {
    const pidx = await read("Memory/Projects/_index.md");
    for (const line of pidx.split("\n")) {
      const m = line.match(/^\|\s*`Projects\/([^`/]+)\/`\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*([\d-]+)\s*\|/);
      if (!m) continue;
      let desc = m[2].replace(/[`*]/g, "").trim();
      let status = "";
      if (desc.includes("🟢")) status = "进行中";
      else if (desc.includes("⏸")) status = "暂停";
      else if (desc.includes("🔒")) status = "封存";
      else if (desc.includes("⚠️")) status = "外部";
      desc = desc.replace(/🟢|⏸|🔒|⚠️/g, "").trim();
      projects.push({ name: m[1], desc, status, updated: m[4] });
    }
  } catch (e) { /* 文件缺失则空列表 */ }

  // Todo.md 解析
  const todo = [];
  try {
    const text = await read("Memory/Todo.md");
    let cur = null;
    for (const raw of text.split("\n")) {
      const line = raw.replace(/\r$/, "");
      const gm = line.match(/^##\s+(.+)$/);
      if (gm) { cur = gm[1].trim(); continue; }
      const im = line.match(/^-\s+(.+)$/);
      if (im && cur) {
        const t = im[1].trim();
        todo.push({ group: cur, text: t, done: t.startsWith("~~") });
      }
    }
  } catch (e) { /* 文件缺失则空列表 */ }

  // Inbox 待审核
  const inbox = [];
  try {
    const inboxFolder = getFolder("Memory/Inbox");
    if (inboxFolder) {
      const files = inboxFolder.children
        .filter((c) => c.extension === "md" && !c.name.startsWith("_"))
        .sort((a, b) => (a.name < b.name ? -1 : 1));
      for (const f of files) {
        const content = await read("Memory/Inbox/" + f.name);
        const cnt = (content.match(/^- \[ \] 待审核/gm) || []).length;
        inbox.push({ date: f.name.replace(/\.md$/, ""), count: cnt });
      }
    }
  } catch (e) { /* 目录缺失则空列表 */ }

  // 自媒体文稿（待发布 + 归档）
  const drafts = [];
  let archived = 0;
  try {
    const draftFolder = getFolder("自媒体内容/文稿");
    if (draftFolder) {
      for (const f of draftFolder.children) {
        if (f.extension === "md" && !f.name.startsWith("_")) {
          const head = (await read("自媒体内容/文稿/" + f.name)).slice(0, 400);
          const m = head.match(/^发布状态:\s*(.+)$/m);
          drafts.push({ file: f.name, status: m ? m[1].trim() : "" });
        }
      }
      archived = countMd(getFolder("自媒体内容/文稿/归档"));
    }
  } catch (e) { /* 目录缺失则空列表 */ }

  const workshop = countMd(getFolder("作坊"));
  const archive = countMd(getFolder("档案"));

  // 最近更新（全 vault，近 7 天，排除隐藏目录；按归属路径标注项目）
  const cut = Date.now() - 7 * 86400000;
  const recent = vault
    .getMarkdownFiles()
    .filter((f) => !f.path.startsWith(".") && f.stat.mtime >= cut)
    .sort((a, b) => b.stat.mtime - a.stat.mtime)
    .slice(0, 10)
    .map((f) => ({
      path: f.path,
      name: f.name.replace(/\.md$/, ""),
      mtime: f.stat.mtime,
      area: areaLabel(f.path),
    }));

  /* 热力值（GitHub 风格日历热力图）：全 vault md 文件按**修改日**分日计数，近 53 周。
     口径与「最近更新」同源（stat.mtime），排除隐藏目录；同日多次修改只计一次（按文件 × 天去重）。
     日历列 = 周（周日→周六），GitHub 同款。 */
  const p2 = (x) => String(x).padStart(2, "0");
  const HEAT_WEEKS = 53;
  const heatMap = {};
  let heatMax = 0, heatTotal = 0;
  {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const end = new Date(today);
    end.setDate(end.getDate() + (6 - end.getDay()));   // 本周周六
    const start = new Date(end);
    start.setDate(start.getDate() - (HEAT_WEEKS * 7 - 1));
    const floor = start.getTime();
    const ceil = end.getTime() + 86400000;
    vault.getMarkdownFiles().forEach((f) => {
      if (f.path.startsWith(".")) return;
      const t = f.stat.mtime;
      if (t < floor || t >= ceil) return;
      const dd = new Date(t);
      const key = `${dd.getFullYear()}-${p2(dd.getMonth() + 1)}-${p2(dd.getDate())}`;
      heatMap[key] = (heatMap[key] || 0) + 1;
      heatTotal++;
      if (heatMap[key] > heatMax) heatMax = heatMap[key];
    });
  }
  const heat = {
    map: heatMap, max: heatMax, total: heatTotal,
    start: (function () { const t = new Date(); t.setHours(0, 0, 0, 0); t.setDate(t.getDate() + (6 - t.getDay()) - (HEAT_WEEKS * 7 - 1)); return t.getTime(); })(),
    weeks: HEAT_WEEKS,
  };

  /* 日记聚合（DailyNotes 下所有 YYYY_MM_DD.md，兼容年份子目录与根层直放）：
     日期/年份从文件名解析；首句预览需读文件 → 按 path|mtime 缓存。按日期倒序，diaries[0] 即最近一篇。 */
  const diaries = [];
  vault.getMarkdownFiles().forEach((f) => {
    if (f.path.indexOf("DailyNotes/") !== 0) return;
    const base = f.name.replace(/\.md$/, "");
    const m = base.match(/^(\d{4})_(\d{2})_(\d{2})$/);
    if (!m) return;
    diaries.push({
      path: f.path, name: base,
      date: m[1] + "-" + m[2] + "-" + m[3], year: m[1],
      mtime: f.stat.mtime, preview: "",
    });
  });
  diaries.sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : 0));
  for (const entry of diaries) {
    const key = entry.path + "|" + entry.mtime;
    if (DIARY_PREVIEW_CACHE[key] !== undefined) { entry.preview = DIARY_PREVIEW_CACHE[key]; continue; }
    try { entry.preview = diaryPreview(await read(entry.path)); }
    catch (e) { entry.preview = ""; }
    DIARY_PREVIEW_CACHE[key] = entry.preview;
  }

  const d = new Date();
  const scanTime = `${d.getFullYear()}-${p2(d.getMonth() + 1)}-${p2(d.getDate())} ${p2(d.getHours())}:${p2(d.getMinutes())}`;

  return {
    scanTime, knowledge: k, memory: mem, projects, todo, inbox,
    zimeiti_drafts: drafts, zimeiti_archived: archived, workshop, archive,
    recent, knowledgeNotes, mocPaths, heat, diaries,
  };
}

/* ============================ 渲染逻辑（纯函数） ============================ */

const CSS = `
.ws-root{
  --kw-bg:#f8fafc; --kw-card:#ffffff; --kw-card-soft:#f6f7fb;
  --kw-text:#1e293b; --kw-text2:#64748b; --kw-text3:#94a3b8;
  --kw-primary:#6366f1; --kw-primary-soft:#eef2ff; --kw-primary-deep:#4f46e5;
  --kw-violet:#8b5cf6;
  --kw-indigo:#6366f1; --kw-indigo-soft:#eef2ff;
  --kw-emerald:#10b981; --kw-emerald-soft:#d1fae5;
  --kw-amber:#f59e0b; --kw-amber-soft:#fef3c7;
  --kw-rose:#f43f5e; --kw-rose-soft:#ffe4e6;
  --kw-line:#eef1f6; --kw-hover:#eef1f8; --kw-ok-border:#cbd5e1;
  --kw-logo-bg:#6366f1;
  --kw-radius-lg:24px; --kw-radius-md:18px; --kw-radius-sm:14px;
  --kw-shadow-sm:0 1px 2px rgba(100,116,139,.06),0 1px 3px rgba(100,116,139,.08);
  --kw-shadow-md:0 4px 12px rgba(99,102,241,.08),0 2px 6px rgba(100,116,139,.08);
  --kw-shadow-lg:0 12px 28px rgba(99,102,241,.14),0 4px 12px rgba(100,116,139,.10);
  --kw-shadow-logo:0 4px 14px rgba(99,102,241,.22);
  --kw-shadow-tab:0 4px 12px rgba(99,102,241,.32);
  --kw-ease:cubic-bezier(.4,0,.2,1);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"PingFang SC","Microsoft YaHei",sans-serif;
  background:var(--kw-bg); color:var(--kw-text);
  line-height:1.6; min-height:100%; padding-bottom:env(safe-area-inset-bottom);
}
/* 暗色模式（Soft UI dark）：低饱和深蓝底、柔和发光阴影 */
.ws-root[data-theme="dark"]{
  --kw-bg:#0f172a; --kw-card:#1e293b; --kw-card-soft:#273549;
  --kw-text:#e2e8f0; --kw-text2:#94a3b8; --kw-text3:#64748b;
  --kw-primary:#818cf8; --kw-primary-soft:#312e81; --kw-primary-deep:#a5b4fc;
  --kw-violet:#a78bfa;
  --kw-indigo:#818cf8; --kw-indigo-soft:#312e81;
  --kw-emerald:#34d399; --kw-emerald-soft:#064e3b;
  --kw-amber:#fbbf24; --kw-amber-soft:#451a03;
  --kw-rose:#fb7185; --kw-rose-soft:#4c0519;
  --kw-line:#334155; --kw-hover:#334155; --kw-ok-border:#475569;
  --kw-logo-bg:#818cf8;
  --kw-shadow-sm:0 1px 2px rgba(0,0,0,.3),0 1px 3px rgba(0,0,0,.3);
  --kw-shadow-md:0 4px 14px rgba(0,0,0,.35),0 2px 6px rgba(0,0,0,.3);
  --kw-shadow-lg:0 12px 30px rgba(0,0,0,.45),0 4px 14px rgba(0,0,0,.35);
  --kw-shadow-logo:0 4px 16px rgba(129,140,248,.35);
  --kw-shadow-tab:0 4px 12px rgba(129,140,248,.35);
}
/* ========== 工作台皮肤：始终跟随 Obsidian 主题（data-style="theme"，唯一启用预设） ==========
   配色全部取自 Obsidian 主题变量 —— 自动契合当前主题（Things）与强调色，明暗随 Obsidian 外观自动切换。
   本块只覆盖变量层；下方 Soft UI 亮/暗变量块按用户裁定（2026-09-26）保留但 UI 不再触达，
   仅作回退底稿：如需恢复双预设，把 buildHtml 根节点 data-style 改回动态并恢复风格切换按钮即可。
   注意：必须位于暗色块之后 —— 与 [data-theme="dark"] 同特异性，靠源码顺序取得覆盖权。 */
.ws-root[data-style="theme"]{
  --kw-bg:var(--background-primary);
  --kw-card:var(--background-secondary);
  --kw-card-soft:var(--background-primary);
  --kw-text:var(--text-normal);
  --kw-text2:var(--text-muted);
  --kw-text3:var(--text-faint);
  --kw-primary:var(--interactive-accent);
  --kw-primary-deep:var(--interactive-accent-hover,var(--interactive-accent));
  --kw-primary-soft:color-mix(in srgb,var(--interactive-accent) 14%,transparent);
  --kw-violet:var(--interactive-accent);
  --kw-indigo:var(--interactive-accent);
  --kw-indigo-soft:color-mix(in srgb,var(--interactive-accent) 14%,transparent);
  --kw-emerald:var(--text-success,#34d399);
  --kw-emerald-soft:color-mix(in srgb,var(--text-success,#34d399) 15%,transparent);
  --kw-amber:var(--text-warning,#fbbf24);
  --kw-amber-soft:color-mix(in srgb,var(--text-warning,#fbbf24) 15%,transparent);
  --kw-rose:var(--text-error,#fb7185);
  --kw-rose-soft:color-mix(in srgb,var(--text-error,#fb7185) 15%,transparent);
  --kw-line:var(--background-modifier-border);
  --kw-hover:var(--background-modifier-hover);
  --kw-ok-border:var(--background-modifier-border);
  --kw-logo-bg:var(--kw-primary-soft);
  --kw-radius-lg:16px; --kw-radius-md:12px; --kw-radius-sm:8px;
  --kw-shadow-sm:0 1px 2px rgba(0,0,0,.10);
  --kw-shadow-md:0 3px 10px rgba(0,0,0,.10);
  --kw-shadow-lg:0 8px 22px rgba(0,0,0,.14);
  --kw-shadow-logo:0 4px 12px color-mix(in srgb,var(--interactive-accent) 30%,transparent);
  --kw-shadow-tab:0 4px 12px color-mix(in srgb,var(--interactive-accent) 30%,transparent);
  font-family:var(--font-interface,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"PingFang SC","Microsoft YaHei",sans-serif);
}
/* 主题模式下，待审核/发布等彩色语义走主题语义色（Soft UI 保持上方类规则里的原硬编码色） */
.ws-root *{box-sizing:border-box;margin:0;padding:0}
.ws-root .wrap{max-width:1120px;margin:0 auto;padding:24px 20px 72px}

/* ---------- 头部 ---------- */
.ws-root header{display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap;padding:4px 0 22px}
.ws-root .brand{display:flex;align-items:center;gap:14px}
.ws-root .logo{width:48px;height:48px;border-radius:50%;background:var(--kw-primary-soft);display:flex;align-items:center;justify-content:center;color:var(--kw-primary-deep);flex:0 0 auto;box-shadow:var(--kw-shadow-logo)}
.ws-root .brand h1{font-size:22px;font-weight:600;letter-spacing:.3px;color:var(--kw-text)}
.ws-root .brand p{font-size:12.5px;color:var(--kw-text2)}
.ws-root .head-actions{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
.ws-root .snapshot{font-size:12px;color:var(--kw-text3);display:flex;align-items:center;gap:6px;padding:7px 12px;background:var(--kw-card);border-radius:999px;box-shadow:var(--kw-shadow-sm)}
.ws-root button{font-family:inherit;cursor:pointer;border:none;font-size:14px;transition:all .3s var(--kw-ease)}
.ws-root .btn{display:inline-flex;align-items:center;gap:6px;padding:10px 18px;background:var(--kw-card);color:var(--kw-text2);font-weight:500;border-radius:999px;box-shadow:var(--kw-shadow-sm)}
.ws-root .btn:hover{color:var(--kw-primary-deep);box-shadow:var(--kw-shadow-md);transform:translateY(-1px)}
.ws-root .btn:active{transform:scale(.96)}
.ws-root .btn-sm{padding:8px 14px;font-size:13px}

/* ---------- 视图导航 pill ---------- */
.ws-root .viewnav{display:flex;gap:8px;margin-bottom:26px;flex-wrap:wrap}
.ws-root .view-btn{display:inline-flex;align-items:center;gap:8px;padding:10px 22px;background:var(--kw-card);color:var(--kw-text2);font-size:13.5px;font-weight:600;border-radius:999px;box-shadow:var(--kw-shadow-sm)}
.ws-root .view-btn svg{opacity:.85}
.ws-root .view-btn:hover{color:var(--kw-primary-deep);transform:translateY(-1px);box-shadow:var(--kw-shadow-md)}
.ws-root .view-btn:active{transform:scale(.96)}
.ws-root .view-btn.active,.ws-root .view-btn.active:hover{color:#fff;background:var(--kw-primary);box-shadow:var(--kw-shadow-tab)}

/* ---------- 分区头：眉标 + 标题（右对齐说明） ---------- */
.ws-root section{background:var(--kw-card);border-radius:var(--kw-radius-lg);box-shadow:var(--kw-shadow-md);padding:24px;margin-bottom:24px}
.ws-root .sec-head{display:flex;align-items:flex-end;justify-content:space-between;gap:12px;margin-bottom:18px}
.ws-root .eyebrow{font-size:10.5px;font-weight:700;letter-spacing:2px;color:var(--kw-text3);text-transform:uppercase;margin-bottom:3px}
.ws-root .sec-title{font-size:17px;font-weight:600;color:var(--kw-text);line-height:1.3}
.ws-root .sec-sub{font-size:12px;color:var(--kw-text3);font-weight:400;white-space:nowrap;padding-bottom:2px}
.ws-root .empty{padding:20px;text-align:center;color:var(--kw-text3);font-size:13.5px}
.ws-root .tag{display:inline-flex;align-items:center;gap:4px;padding:3px 10px;border-radius:999px;font-size:11.5px;font-weight:600;white-space:nowrap}
.ws-root .tag-primary{background:var(--kw-indigo-soft);color:var(--kw-primary-deep)}
.ws-root .tag-warn{background:var(--kw-amber-soft);color:var(--kw-amber)}
.ws-root .tag-green{background:var(--kw-emerald-soft);color:var(--kw-emerald)}
.ws-root .tag-cat{background:var(--kw-line);color:var(--kw-text2)}
.ws-root .tag-gray{background:var(--kw-line);color:var(--kw-text3)}

/* ---------- 聚焦瓦片（今日视图顶部） ---------- */
.ws-root .focus{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-bottom:24px}
.ws-root .ftile{background:var(--kw-card);border-radius:var(--kw-radius-md);box-shadow:var(--kw-shadow-md);padding:18px 20px;display:flex;flex-direction:column;gap:2px;transition:all .3s var(--kw-ease)}
.ws-root .ftile:hover{transform:translateY(-3px);box-shadow:var(--kw-shadow-lg)}
.ws-root .ftile .v{font-size:27px;font-weight:700;line-height:1.2;color:var(--kw-text)}
.ws-root .ftile .k{font-size:12px;color:var(--kw-text3)}

/* ---------- Todo 模块（个人待办，插件 data.json 记录） ---------- */
.ws-root .todo-add{display:flex;gap:10px;margin-bottom:16px}
.ws-root .todo-add input{flex:1;min-width:0;padding:11px 16px;font-size:14px;font-family:inherit;color:var(--kw-text);background:var(--kw-card-soft);border:1px solid var(--kw-line);border-radius:999px;outline:none;transition:all .3s var(--kw-ease)}
.ws-root .todo-add input:focus{border-color:var(--kw-primary);background:var(--kw-card)}
.ws-root .todo-add input::placeholder{color:var(--kw-text3)}
.ws-root .todo-add button{padding:10px 22px;border-radius:999px;background:var(--kw-primary);color:#fff;font-weight:600}
.ws-root .todo-add button:active{transform:scale(.96)}
.ws-root .todo-sec{font-size:11px;font-weight:700;letter-spacing:2px;color:var(--kw-text3);margin:16px 2px 8px}
.ws-root .todo-item{display:flex;align-items:center;gap:12px;padding:11px 14px;border-radius:var(--kw-radius-sm);background:var(--kw-card-soft);border-left:3px solid var(--kw-line);margin-bottom:8px;cursor:pointer;transition:all .3s var(--kw-ease)}
.ws-root .todo-item:hover{background:var(--kw-hover)}
.ws-root .todo-item.over{border-left-color:var(--kw-rose)}
.ws-root .todo-item.tdy{border-left-color:var(--kw-amber)}
.ws-root .todo-item .ck{width:18px;height:18px;border:2px solid var(--kw-ok-border);border-radius:6px;flex:0 0 auto;cursor:pointer;position:relative;transition:all .2s var(--kw-ease)}
.ws-root .todo-item .ck:hover{border-color:var(--kw-emerald)}
.ws-root .todo-item.done .ck{background:var(--kw-emerald);border-color:var(--kw-emerald)}
.ws-root .todo-item.done .ck::after{content:'';position:absolute;left:5px;top:2px;width:5px;height:9px;border:solid #fff;border-width:0 2px 2px 0;transform:rotate(45deg)}
.ws-root .todo-item .tx{flex:1;min-width:0;font-size:14px;color:var(--kw-text);word-break:break-all}
.ws-root .todo-item.done .tx{text-decoration:line-through;color:var(--kw-text3)}
.ws-root .prio{flex:0 0 auto;font-size:11px;font-weight:700;padding:2px 9px;border-radius:999px}
.ws-root .prio.p-high{background:var(--kw-rose-soft);color:var(--kw-rose)}
.ws-root .prio.p-medium{background:var(--kw-amber-soft);color:var(--kw-amber)}
.ws-root .prio.p-low{background:var(--kw-line);color:var(--kw-text3)}
.ws-root .cat{flex:0 0 auto;font-size:11px;color:var(--kw-text2);background:var(--kw-line);padding:2px 9px;border-radius:999px;white-space:nowrap}
.ws-root .todo-item .due{flex:0 0 auto;font-size:11px;font-weight:600;padding:2px 10px;border-radius:999px;background:var(--kw-line);color:var(--kw-text2)}
.ws-root .todo-item .due.over{background:var(--kw-rose-soft);color:var(--kw-rose)}
.ws-root .todo-item .due.tdy{background:var(--kw-amber-soft);color:var(--kw-amber)}
.ws-root .todo-done-head{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-top:18px;padding:10px 14px;border-radius:var(--kw-radius-sm);background:var(--kw-card-soft);color:var(--kw-text3);font-size:13px;cursor:pointer;user-select:none}
.ws-root .todo-done-head:hover{background:var(--kw-hover)}
.ws-root .todo-clear{font-size:12px;color:var(--kw-text3);padding:2px 10px;border-radius:999px;background:none}
.ws-root .todo-clear:hover{color:var(--kw-rose);background:var(--kw-rose-soft)}

/* ---------- Todo 编辑小窗（Modal：用 Obsidian 原生变量，自动跟随主题） ---------- */
.kw-todo-modal .kw-form{display:flex;flex-direction:column;gap:14px}
.kw-todo-modal .kw-field{display:flex;flex-direction:column;gap:4px}
.kw-todo-modal .kw-field > span{font-size:12px;font-weight:600;color:var(--text-muted)}
.kw-todo-modal .kw-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.kw-todo-modal .kw-grid .kw-field select,
.kw-todo-modal .kw-grid .kw-field input{width:100%}
.kw-todo-modal textarea{min-height:76px;resize:vertical}
.kw-todo-modal .kw-foot{display:flex;gap:8px;align-items:center;margin-top:4px}
.kw-todo-modal .kw-foot .spacer{flex:1}
.kw-todo-modal .kw-confirm{display:flex;gap:8px;align-items:center;font-size:12.5px;color:var(--text-error)}

/* ---------- 双栏（Todo 视图） ---------- */
.ws-root .twocol{display:grid;grid-template-columns:1.5fr 1fr;gap:20px;align-items:start}
.ws-root .twocol section{margin-bottom:0}

/* ---------- 统一列表行：彩色左边框 + 右对齐元数据 + hover 箭头 ---------- */
.ws-root .rows{display:flex;flex-direction:column;gap:10px}
.ws-root .row{display:flex;align-items:center;gap:12px;padding:13px 16px;border-radius:var(--kw-radius-sm);background:var(--kw-card-soft);border-left:3px solid var(--kw-line);cursor:pointer;transition:all .3s var(--kw-ease)}
.ws-root .row:hover{background:var(--kw-hover);transform:translateY(-1px);box-shadow:var(--kw-shadow-sm)}
.ws-root .row:active{transform:scale(.99)}
.ws-root .row .rt{flex:1;min-width:0;font-size:14px;font-weight:500;color:var(--kw-text);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.ws-root .row .rm{display:flex;align-items:center;gap:8px;flex:0 0 auto}
.ws-root .row .arr{color:var(--kw-text3);opacity:0;transition:opacity .2s var(--kw-ease);display:flex}
.ws-root .row:hover .arr{opacity:1}

/* ---------- 知识库视图（知识地图＝统计条+原生图谱 / 最近更新 / 快速打开 / 体检） ---------- */
.ws-root .kbstats{display:flex;flex-wrap:wrap;align-items:center;gap:8px;padding:12px 16px;background:var(--kw-card-soft);border-radius:var(--kw-radius-sm);margin-bottom:20px}
.ws-root .kbstat-total{font-size:13px;font-weight:700;color:var(--kw-text);margin-right:4px}
.ws-root .kbstat{display:inline-flex;align-items:center;gap:6px;font-size:12px;color:var(--kw-text2);background:var(--kw-line);padding:3px 11px;border-radius:999px;cursor:pointer;transition:all .2s var(--kw-ease)}
.ws-root .kbstat:hover{color:#fff;background:var(--kw-primary)}
.ws-root .kbstat.active{color:#fff;background:var(--kw-primary);box-shadow:var(--kw-shadow-tab)}
.ws-root .kbstat b{font-weight:600}
.ws-root .kb-graphwrap{border:1px solid var(--kw-line);border-radius:var(--kw-radius-md);overflow:hidden;background:var(--kw-bg)}
.ws-root .native-embed{height:640px;position:relative}
.ws-root .native-embed > .graph-view,
.ws-root .native-embed .graph-view{height:100%;width:100%}
.ws-root .kb-search input{width:100%;padding:11px 16px;font-size:14px;font-family:inherit;color:var(--kw-text);background:var(--kw-card-soft);border:1px solid var(--kw-line);border-radius:999px;outline:none;transition:all .3s var(--kw-ease)}
.ws-root .kb-search input:focus{border-color:var(--kw-primary);background:var(--kw-card)}
.ws-root .kb-search input::placeholder{color:var(--kw-text3)}
.ws-root .kb-search #kbSearchResults{margin-top:10px}
/* 全部笔记：分类芯片条（复用 kbstat 芯片样式） */
.ws-root .notechips{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:12px}
/* 全部笔记：双行行（标题 + 简介小字），简介缺省时退化为普通单行。
   前缀样式：悬停高亮块——平时无标记，hover 整行变亮 + 左侧浮出主题色竖条（取代原常驻左竖线） */
.ws-root .row.row2line{flex-direction:column;align-items:stretch;gap:4px;padding:10px 14px;border-left:3px solid transparent}
.ws-root .row.row2line:hover{border-left-color:var(--kw-primary)}
.ws-root .row .rmain{display:flex;align-items:center;gap:12px}
.ws-root .row .row-abs{font-size:12px;line-height:1.5;color:var(--kw-text3);overflow:hidden;text-overflow:ellipsis;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}
.ws-root .kblink{color:var(--kw-primary-deep);cursor:pointer}
.ws-root .kb-audit{margin-bottom:10px}
.ws-root .kb-audit-sum{font-size:13px;color:var(--kw-text2);margin-bottom:6px}
.ws-root .kbcols{grid-template-columns:1fr 1fr;align-items:start}
.ws-root .kbright section{margin-bottom:20px}
.ws-root .rows-compact{gap:6px}
.ws-root .rows-compact .row{padding:7px 12px}
.ws-root .rows-compact .row .rt{font-size:13px}
.ws-root .row .cat{max-width:150px;overflow:hidden;text-overflow:ellipsis}
/* ---------- 热力值（Home 顶部，GitHub 风格日历热力图；卡片宽 = 内容宽） ---------- */
.ws-root .heat-wrap{display:flex;flex-direction:column;gap:8px}
.ws-root .heat-sum{font-size:12.5px;color:var(--kw-text2)}
.ws-root .heat-sum b{color:var(--kw-text);font-weight:600}
.ws-root .heat-scroll{overflow-x:hidden;overflow-y:hidden;padding-bottom:2px}
/* 固定尺寸格子（12px + 3px 间距），不用自适应拉伸 —— flex 均分 / aspect-ratio 在不同窗口宽度下
   易出渲染异常（2026-09-30 用户实测），固定像素在所有环境下稳定一致。
   53 列总宽 792px；更窄的窗口交给横向滚动。行列结构 = 每周一个 flex 列
   （二维 grid 的 1fr 行轨道在容器高度不定时会被 Chrome 解析成固定 40px，弃用）。 */
.ws-root .heat-cols{display:flex;gap:3px;align-items:flex-start}
/* 列宽必须与格子同为固定 12px：若交给内容自适应，月份标签（"10月" 约 20-30px 宽）会把
   带标签的列撑宽 → 列距忽宽忽窄、格子错位（2026-09-30 实测）。标签溢出用 overflow:visible。 */
.ws-root .heat-col{width:12px;display:flex;flex-direction:column;gap:3px}
.ws-root .heat-month{height:12px;margin-bottom:3px;font-size:10px;line-height:12px;color:var(--kw-text3);white-space:nowrap;overflow:visible}
.ws-root .heat-col .heat-cell{width:12px;height:12px;border-radius:2px;
  transition:transform .15s var(--kw-ease)}
/* 卡片宽 = 网格 792 + 左右内边距 48，右侧不留空；末列月份标签溢出 ~8px 由 scroll 容器收纳 */
.ws-root .heat-sec{max-width:840px}
.ws-root .heat-cell:hover{transform:scale(1.25)}
.ws-root .heat-l0{background:color-mix(in srgb,var(--kw-text3) 14%,transparent)}
.ws-root .heat-l1{background:color-mix(in srgb,var(--kw-primary) 28%,transparent)}
.ws-root .heat-l2{background:color-mix(in srgb,var(--kw-primary) 52%,transparent)}
.ws-root .heat-l3{background:color-mix(in srgb,var(--kw-primary) 76%,transparent)}
.ws-root .heat-l4{background:var(--kw-primary)}
.ws-root .heat-cell-blank{background:transparent;pointer-events:none}
.ws-root .heat-foot{display:flex;align-items:center;justify-content:space-between;gap:10px;font-size:11.5px;color:var(--kw-text3)}
.ws-root .heat-legend{display:inline-flex;align-items:center;gap:4px}
.ws-root .heat-legend .heat-cell{width:10px;height:10px;flex:0 0 auto;cursor:default}
.ws-root .heat-legend .heat-cell:hover{transform:none}
/* 全部笔记：形态切换（列表 / 导图）+ 思维导图（按 category 连线的横向树）。
   形态切换复用模块既有切换按钮样式（tab-bar / tab-btn，与「记忆系统」子 tab 同一套），仅紧凑化 —— 不另造一套。 */
.ws-root .notes-head-right{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.ws-root .notes-seg{margin-bottom:0;padding:3px;gap:2px;flex:0 0 auto}
.ws-root .notes-seg .tab-btn{flex:0 0 auto;padding:5px 14px;font-size:12.5px}
.ws-root .mm-wrap{position:relative}
.ws-root .mm-tools{position:absolute;top:10px;right:10px;z-index:2;display:flex;gap:4px;background:var(--kw-card);border:1px solid var(--kw-line);border-radius:999px;padding:4px 6px;box-shadow:var(--kw-shadow-sm)}
.ws-root .mm-tool{padding:4px 10px;font-size:12px;font-weight:600;color:var(--kw-text2);background:none;border-radius:999px}
.ws-root .mm-tool:hover{color:var(--kw-primary-deep);background:var(--kw-hover)}
/* 画布背景 = 列表笔记块同一底色（--kw-card-soft，用户 2026-09-29 指定），与节点形成对比 */
.ws-root .mm-viewport{height:min(78vh,860px);overflow:hidden;border:1px solid var(--kw-line);border-radius:var(--kw-radius-md);
  background:var(--kw-card-soft);cursor:grab;position:relative;touch-action:none;user-select:none;-webkit-user-select:none}.ws-root .mm-viewport.dragging{cursor:grabbing}
.ws-root .mm-svg{display:block;transform-origin:0 0;will-change:transform}
.ws-root .mm-edge{fill:none;stroke:color-mix(in srgb,var(--kw-text3) 62%,transparent);stroke-width:1.4}
.ws-root .mm-node{cursor:pointer}
.ws-root .mm-box{stroke-width:1.2;transition:stroke-width .2s var(--kw-ease)}
.ws-root .mm-node:hover .mm-box{stroke-width:2.2}
.ws-root .mm-label{font-size:12px;font-weight:600;fill:var(--kw-text);pointer-events:none}
.ws-root .mm-badge{font-size:10px;font-weight:600;fill:var(--kw-text3);pointer-events:none}
.ws-root .mm-chev{font-size:9px;fill:var(--kw-text3);pointer-events:none}
/* 根：实心主题色 */
.ws-root .mm-root .mm-box{fill:var(--kw-primary);stroke:var(--kw-primary)}
.ws-root .mm-root .mm-label{fill:#fff;font-size:13px}
.ws-root .mm-root .mm-badge{fill:rgba(255,255,255,.9)}
/* 主类：色相明显的色块（分类一眼可辨）*/
.ws-root .mm-area .mm-box{fill:color-mix(in srgb,hsl(var(--mm-h,222) 58% 48%) 26%,var(--kw-card));
  stroke:color-mix(in srgb,hsl(var(--mm-h,222) 52% 42%) 62%,transparent)}
.ws-root .mm-area .mm-label{fill:color-mix(in srgb,hsl(var(--mm-h,222) 58% 28%) 88%,var(--kw-text))}
.ws-root[data-theme="dark"] .mm-area .mm-label{fill:color-mix(in srgb,hsl(var(--mm-h,222) 64% 78%) 90%,var(--kw-text))}
/* 末级：同色系浅块 */
.ws-root .mm-sub .mm-box{fill:color-mix(in srgb,hsl(var(--mm-h,222) 50% 50%) 12%,var(--kw-card));
  stroke:color-mix(in srgb,hsl(var(--mm-h,222) 45% 45%) 34%,transparent)}
/* 笔记：卡片底 + 色相浅描边（标题为主，不喧宾夺主）*/
.ws-root .mm-note .mm-box{fill:var(--kw-card);stroke:color-mix(in srgb,hsl(var(--mm-h,222) 45% 50%) 30%,var(--kw-line))}
.ws-root .mm-note .mm-label{font-weight:500}
.ws-root .mm-note:hover .mm-box{stroke:color-mix(in srgb,hsl(var(--mm-h,222) 60% 48%) 82%,transparent);fill:var(--kw-hover)}
.ws-root .mm-hint{position:absolute;left:12px;bottom:10px;font-size:11.5px;color:var(--kw-text3);background:color-mix(in srgb,var(--kw-card) 88%,transparent);padding:3px 10px;border-radius:999px;pointer-events:none}

/* ---------- 记忆系统子 tab ---------- */
.ws-root .tab-bar{display:flex;gap:6px;margin-bottom:18px;background:var(--kw-card-soft);padding:5px;border-radius:999px}
.ws-root .tab-btn{flex:1;padding:10px 16px;background:none;font-size:13.5px;font-weight:600;color:var(--kw-text2);border-radius:999px;transition:all .3s var(--kw-ease)}
.ws-root .tab-btn:hover{color:var(--kw-text)}
.ws-root .tab-btn.active{color:#fff;background:var(--kw-primary);box-shadow:var(--kw-shadow-tab)}

/* ---------- 日记模块（四列统计瓦片 + 复用 rows / group；年份芯片过滤见 renderDiaryList） ---------- */
.ws-root .focus.cols4{grid-template-columns:repeat(4,1fr)}
.ws-root .ftile .v.v-sm{font-size:17px;font-weight:600;line-height:1.5;padding:5px 0}
@media(max-width:768px){.ws-root .focus.cols4{grid-template-columns:repeat(2,1fr)}}

/* ---------- 待办分组 ---------- */
.ws-root .group{border-radius:var(--kw-radius-md);overflow:hidden;margin-bottom:12px;background:var(--kw-card-soft)}
.ws-root .group-head{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:13px 18px;cursor:pointer;user-select:none;transition:all .3s var(--kw-ease)}
.ws-root .group-head:hover{background:var(--kw-hover)}
.ws-root .group-head .gname{font-size:14px;font-weight:600;display:flex;align-items:center;gap:8px;color:var(--kw-text)}
.ws-root .group-head .gcnt{font-size:11.5px;color:var(--kw-text3)}
.ws-root .group-body{padding:8px 18px 14px}
.ws-root .todo-line{display:flex;gap:10px;padding:8px 0;font-size:13.5px;border-bottom:1px solid var(--kw-line)}
.ws-root .todo-line:last-child{border-bottom:none}
.ws-root .todo-line.done{opacity:.5}
.ws-root .todo-line.done .txt{text-decoration:line-through}
.ws-root .todo-line .txt{flex:1;word-break:break-all;color:var(--kw-text)}
.ws-root .todo-line .ok{width:18px;height:18px;border:2px solid var(--kw-ok-border);border-radius:6px;flex:0 0 auto;margin-top:2px}
.ws-root .todo-line.done .ok{background:var(--kw-emerald);border-color:var(--kw-emerald);position:relative}
.ws-root .todo-line.done .ok::after{content:'';position:absolute;left:5px;top:2px;width:5px;height:9px;border:solid #fff;border-width:0 2px 2px 0;transform:rotate(45deg)}

/* ---------- 项目列表 ---------- */
.ws-root .proj-list{display:flex;flex-direction:column;gap:8px}
.ws-root .proj-item{display:flex;align-items:center;gap:10px;font-size:13px;padding:11px 14px;border-radius:var(--kw-radius-sm);background:var(--kw-card-soft)}
.ws-root .proj-item .pname{font-weight:600;flex:0 0 auto;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;color:var(--kw-text)}
.ws-root .proj-item .pdesc{color:var(--kw-text2);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1;min-width:0}
.ws-root .st{font-size:11px;padding:3px 10px;border-radius:999px;font-weight:600;flex:0 0 auto}
.ws-root .st-run{background:var(--kw-emerald-soft);color:var(--kw-emerald)}
.ws-root .st-pause{background:var(--kw-amber-soft);color:var(--kw-amber)}
.ws-root .st-lock{background:var(--kw-line);color:var(--kw-text3)}
.ws-root .st-ext{background:var(--kw-rose-soft);color:var(--kw-rose)}

/* ---------- 待审核（记忆库视图，按日全量） ---------- */
.ws-root .inbox-line{display:flex;align-items:center;justify-content:space-between;padding:11px 14px;border-radius:var(--kw-radius-sm);font-size:13px;background:var(--kw-card-soft);margin-bottom:8px}
.ws-root .inbox-line .cnt{font-weight:700;color:var(--kw-text)}
.ws-root .inbox-line .cnt.zero{color:var(--kw-text3);font-weight:400}

/* ---------- 发布状态 ---------- */
.ws-root .pubgrid{display:grid;grid-template-columns:repeat(2,1fr);gap:16px}
.ws-root .pubcol{background:var(--kw-card-soft);border-radius:var(--kw-radius-md);padding:18px;display:flex;flex-direction:column;gap:10px}
.ws-root .pubcol h4{font-size:14px;font-weight:600;display:flex;align-items:center;gap:8px;color:var(--kw-text)}
.ws-root .pubcol .n{font-size:12px;color:var(--kw-text2);font-weight:600;background:var(--kw-card);padding:2px 10px;border-radius:999px;box-shadow:var(--kw-shadow-sm)}
.ws-root .pubrow{display:flex;align-items:center;justify-content:space-between;gap:10px;font-size:13px;padding:10px 12px;background:var(--kw-card);border-radius:var(--kw-radius-sm)}
.ws-root .pubrow .p{color:var(--kw-text2);font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}

.ws-root footer{text-align:center;color:var(--kw-text3);font-size:12px;padding:12px 0 0}
@media(max-width:768px){
  .ws-root .wrap{padding:18px 14px 64px}
  .ws-root .focus{gap:10px}
  .ws-root .ftile{padding:14px 12px}
  .ws-root .ftile .v{font-size:21px}
  .ws-root .twocol{grid-template-columns:1fr;gap:20px}
  .ws-root .twocol section{margin-bottom:0}
  .ws-root .kbstats{padding:10px 12px;gap:6px}
  .ws-root .pubgrid{grid-template-columns:1fr}
  .ws-root header{flex-direction:column;align-items:flex-start}
  .ws-root .brand h1{font-size:19px}
  .ws-root .viewnav{flex-wrap:nowrap;overflow-x:auto;padding-bottom:4px;-webkit-overflow-scrolling:touch}
  .ws-root .view-btn{flex:0 0 auto}
  .ws-root section{padding:20px}
  .ws-root .mm-viewport{height:420px}
  .ws-root .mm-hint{display:none}
}
/* 减少动态效果：关掉过渡与卡片位移。**必须排除 SVG 导图节点** ——
   它们的 transform 是几何定位（不是动画），被 transform:none 清掉会让整棵树叠到原点。 */
@media(prefers-reduced-motion:reduce){
  .ws-root *{transition:none!important}
  .ws-root *:not(.mm-node):not(.mm-svg){transform:none!important}
}
`;

const ICONS = {
  blog: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2Z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/><path d="M9 7h7M9 11h7" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>',
  kb: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none"><path d="M12 5c-2 0-3.5-.7-4.5-1.5C6.4 4.6 6 6 6 8v10c0 2 .4 3.4 1.5 4.5C8.5 21.3 10 20 12 20s3.5 1.3 4.5.5c1.1-1.1 1.5-2.5 1.5-4.5V8c0-2-.4-3.4-1.5-4.5C15.5 4.3 14 5 12 5Z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/><path d="M12 5v15" stroke="currentColor" stroke-width="1.8"/></svg>',
  mem: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="3.2" stroke="currentColor" stroke-width="1.8"/><path d="M12 3a9 9 0 0 0-9 9 9 9 0 0 0 9 9 9 9 0 0 0 9-9 9 9 0 0 0-9-9Z" stroke="currentColor" stroke-width="1.8"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>',
  navNotes: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none"><path d="M8 6h13M8 12h13M8 18h13" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/><path d="M3.5 6h.01M3.5 12h.01M3.5 18h.01" stroke="currentColor" stroke-width="2.6" stroke-linecap="round"/></svg>',
  clock: '<svg width="13" height="13" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="8.5" stroke="currentColor" stroke-width="2"/><path d="M12 7v5l3 2" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
  logo: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M4 5a1 1 0 0 1 1-1h4l2 2h8a1 1 0 0 1 1 1v11a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V5Z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/><path d="M9 13l2 2 4-4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  moon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/></svg>',
  sun: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="4" stroke="currentColor" stroke-width="1.8"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>',
  arrow: '<svg width="13" height="13" viewBox="0 0 24 24" fill="none"><path d="M7 17 17 7M9 7h8v8" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  navToday: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none"><rect x="3.5" y="3.5" width="17" height="17" rx="5" stroke="currentColor" stroke-width="1.8"/><path d="m8.5 12.3 2.3 2.3 4.7-4.9" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  navHome: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none"><path d="m3.5 10.5 8.5-7 8.5 7" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/><path d="M5.5 9v10.5a1 1 0 0 0 1 1h11a1 1 0 0 0 1-1V9" stroke="currentColor" stroke-width="1.8"/><path d="M9.5 20.5v-6h5v6" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/></svg>',
  navKb: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none"><path d="m9 3.5-5.5 2v15L9 18.5l6 2 5.5-2v-15L15 5.5l-6-2Z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/><path d="M9 3.5v15M15 5.5v15" stroke="currentColor" stroke-width="1.8"/></svg>',
  navMem: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none"><path d="M12 4.5a3.8 3.8 0 0 0-3.8 3.8v.4A3.5 3.5 0 0 0 5 12a3.5 3.5 0 0 0 2 3.15v1.05A3.3 3.3 0 0 0 10.3 19.5c1 0 1.7-.4 1.7-.4V4.5Z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/><path d="M12 4.5a3.8 3.8 0 0 1 3.8 3.8v.4A3.5 3.5 0 0 1 19 12a3.5 3.5 0 0 1-2 3.15v1.05a3.3 3.3 0 0 1-3.3 3.3c-1 0-1.7-.4-1.7-.4" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/></svg>',
  navDiary: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none"><rect x="3.5" y="4.5" width="17" height="16" rx="4" stroke="currentColor" stroke-width="1.8"/><path d="M3.5 9.5h17" stroke="currentColor" stroke-width="1.8"/><path d="M8 2.5v3M16 2.5v3" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/><path d="m9 14.5 2.2 2.2 4-4.2" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>',
};

/* Todo 视图：聚焦瓦片（我的待办 / 逾期 / 待审核 —— 项目待办计数移除，全量见记忆库模块） */
function renderFocusTiles(data, todos) {
  todos = todos || [];
  const td = localToday();
  const open = todos.filter((t) => !t.done);
  const over = open.filter((t) => t.due && t.due < td).length;
  const pendingInbox = data.inbox.reduce((s, i) => s + i.count, 0);
  const tiles = [
    [open.length, "我的待办", open.length ? "var(--kw-primary)" : "var(--kw-emerald)"],
    [over, "逾期未完成", over ? "var(--kw-rose)" : "var(--kw-emerald)"],
    [pendingInbox, "待审核条目", pendingInbox ? "var(--kw-amber)" : "var(--kw-emerald)"],
  ];
  return tiles.map(([v, k, c]) =>
    '<div class="ftile"><span class="v" style="color:' + c + '">' + v + '</span><span class="k">' + k + '</span></div>'
  ).join("");
}

/* Todo 视图：我的待办模块（纯函数；分组 逾期/今天/以后/无日期 + 已完成折叠区；点击行 → 详情小窗） */
function renderTodoModule(todos, today) {
  todos = todos || [];
  const td = today || localToday();
  const open = todos.filter((t) => !t.done);
  const done = todos.filter((t) => t.done);
  const prRank = { high: 0, medium: 1, low: 2 };
  const byPr = (a, b) => (prRank[a.priority] ?? 3) - (prRank[b.priority] ?? 3);
  const row = (t) => {
    const over = !t.done && t.due && t.due < td;
    const tdy = !t.done && t.due === td;
    const cat = TODO_CATEGORIES.find((c) => c.key === t.category);
    const dueLabel = t.due ? (tdy ? "今天" : t.due.slice(5).replace("-", "/")) + (t.time ? " " + t.time : "") : "";
    return '<div class="todo-item' + (t.done ? " done" : "") + (over ? " over" : "") + (tdy ? " tdy" : "") + '" data-todo="' + t.id + '" title="点击编辑详情">' +
      '<span class="ck" data-check="' + t.id + '" title="' + (t.done ? "标记未完成" : "完成") + '"></span>' +
      '<span class="tx">' + esc(t.title) + '</span>' +
      (t.priority ? '<span class="prio p-' + t.priority + '">' + (TODO_PRIORITIES.find((p) => p.key === t.priority) || {}).label + '</span>' : "") +
      (cat && cat.key ? '<span class="cat">' + cat.label + '</span>' : "") +
      (t.due ? '<span class="due' + (over ? " over" : tdy ? " tdy" : "") + '">' + dueLabel + '</span>' : "") +
      '</div>';
  };
  let html = '<div class="todo-add">' +
    '<input id="todoInput" placeholder="添加待办；结尾加 @2026-09-26 14:30 设截止" />' +
    '<button id="todoAddBtn">添加</button></div>';
  const groups = [
    ["逾期", open.filter((t) => t.due && t.due < td).sort(byPr)],
    ["今天", open.filter((t) => t.due === td).sort(byPr)],
    ["以后", open.filter((t) => t.due && t.due > td).sort(byPr)],
    ["无日期", open.filter((t) => !t.due).sort(byPr)],
  ];
  let any = false;
  for (const g of groups) {
    if (!g[1].length) continue;
    any = true;
    html += '<div class="todo-sec">' + g[0] + ' · ' + g[1].length + '</div>' + g[1].map(row).join("");
  }
  if (!any) html += '<div class="empty">还没有待办，在上面输入一条吧</div>';
  html += '<div class="todo-done-head" data-toggle><span>已完成 · ' + done.length + '</span>' +
    (done.length ? '<button class="todo-clear" data-clear>清除</button>' : "") + '</div>' +
    '<div class="todo-done-body"' + (done.length ? "" : ' style="display:none"') + '>' +
    (done.length ? done.map(row).join("") : '<div class="empty">暂无已完成</div>') + '</div>';
  return html;
}

/* Todo 视图：待审核速览（最近 5 天，点击打开当日登记文件） */
function renderInboxRecent(data) {
  const recent = data.inbox.slice(-5).reverse();
  if (!recent.length) return '<div class="empty">暂无登记</div>';
  return recent.map((i) =>
    '<div class="row" data-open="Memory/Inbox/' + esc(i.date) + '.md" style="border-left-color:' + (i.count ? "var(--kw-amber)" : "var(--kw-emerald)") + '">' +
    '<span class="rt">' + esc(i.date) + '</span>' +
    '<span class="rm"><span class="tag ' + (i.count ? "tag-warn" : "tag-green") + '">' + i.count + ' 条</span><span class="arr">' + ICONS.arrow + '</span></span></div>'
  ).join("");
}

/* 知识库视图：知识地图（单行统计条：总数 + 各领域篇数收进一枚小模块；
   点芯片 = 点亮并让下方图谱只看该分区，再点同芯片恢复全图；activePath 为当前点亮分区） */
function renderKbMap(data, activePath) {
  const k = data.knowledge;
  const areas = [
    ["AI", k.AI, "Knowledge/AI"], ["Engineering", k.Engineering, "Knowledge/Engineering"],
    ["Methods", k.Methods, "Knowledge/Methods"], ["Life", k.Life, "Knowledge/Life"],
    ["MOC", k._mocs, "Knowledge/_mocs"], ["作坊", data.workshop, "作坊"], ["档案", data.archive, "档案"],
  ];
  return '<div class="kbstats"><span class="kbstat-total">共 ' + k.total + ' 篇</span>' +
    areas.map(([name, n, path]) =>
      '<span class="kbstat' + (path === activePath ? " active" : "") + '" data-kbfilter="' + esc(path) + '" title="图谱只看 ' + esc(name) + '/（再点一次恢复全部）">' + esc(name) + ' <b>' + n + '</b></span>'
    ).join("") + '</div>';
}

/* 全部笔记视图：Knowledge 区全量索引（接替已删除的 All notes-MOC.md）。
   分类 = frontmatter category（与 MOC 对应体系，2026-09-29 起，不再用磁盘目录）。
   两种展现形态（用户 2026-09-29 追加「思维导图」）：
   ├ 列表：分类芯片 + 平铺折叠块（右侧标注分类 / 所属 MOC）
   └ 思维导图：按 category 连线的横向树（主类 → 末级 → 笔记），节点显示 frontmatter title
   分类芯片与搜索框两形态共用；形态切换 / 芯片点击只重渲染 #allNotesList，不重建整个工作台，
   搜索框焦点与输入得以保留。 */
/* category 主名固定序（与博客站根分类一致）；「MOC」为虚拟汇总分类（收拢全库 MOC 页），
   未分类殿后。scan 里 _rank.r 的 90 号段即未分类 */
const CATEGORY_ORDER = ["AI大模型", "AI框架与Agent", "RAG", "OpenClaw", "工程工具", "个人知识管理", "生活", "创业启示", "MOC"];
/* 中文拼音序比较器（scan 排序与渲染层 MOC 子块排序共用） */
function zh(a, b) {
  return String(a).localeCompare(String(b), "zh-Hans-CN");
}
/* 判定 MOC 文档：路径在 Knowledge/_mocs/ 下，或文件名含 MOC */
function isMocNote(n) {
  return n.path.indexOf("Knowledge/_mocs/") === 0 || n.name.indexOf("MOC") >= 0;
}
/* 分类标注：category 末级（主名/末级 不同时显示「主名 / 末级」，仅主名时显示主名）；未分类无子标注 */
function noteSubLabel(n) {
  return n.area === "未分类" ? "" : (n.sub || "");
}
/* 全部笔记：搜索命中（展示标题 / 文件名 / 所属 MOC / 末级 / 主类，全部小写子串） */
function noteHit(n, kw) {
  if (!kw) return true;
  return (n.title || "").toLowerCase().indexOf(kw) >= 0 ||
    n.name.toLowerCase().indexOf(kw) >= 0 ||
    (n.mocs || []).some((m) => m.toLowerCase().indexOf(kw) >= 0) ||
    noteSubLabel(n).toLowerCase().indexOf(kw) >= 0 ||
    n.area.toLowerCase().indexOf(kw) >= 0;
}
/* 全部笔记：分类序列（主类按固定序；「MOC」虚拟分类收拢全库 MOC 页，排在未分类前） */
function noteAreas(notes) {
  const areas = [];
  notes.forEach((n) => { if (areas.indexOf(n.area) < 0) areas.push(n.area); });
  if (notes.filter(isMocNote).length && areas.indexOf("MOC") < 0) areas.push("MOC");
  areas.sort((a, b) => {
    const ia = CATEGORY_ORDER.indexOf(a), ib = CATEGORY_ORDER.indexOf(b);
    return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib) || (a < b ? -1 : a > b ? 1 : 0);
  });
  return areas;
}
/* 全部笔记：过滤后的可见集合（列表 / 导图共用；activeArea 空 = 全部） */
function notesVisible(notes, filter, activeArea) {
  const kw = String(filter || "").trim().toLowerCase();
  return notes.filter((n) =>
    (!activeArea || n.area === activeArea || (activeArea === "MOC" && isMocNote(n))) && noteHit(n, kw));
}
/* 全部笔记：分类芯片条（列表 / 导图共用；复用 kbstat 芯片样式） */
function notesChipsHtml(notes, activeArea) {
  const areas = noteAreas(notes);
  const mocCount = notes.filter(isMocNote).length;
  return '<div class="notechips">' +
    '<span class="kbstat' + (!activeArea ? " active" : "") + '" data-notearea="">全部 <b>' + notes.length + '</b></span>' +
    areas.map((a) =>
      '<span class="kbstat' + (activeArea === a ? " active" : "") + '" data-notearea="' + esc(a) + '" title="只看 ' + esc(a) + '（再点一次恢复全部）">' +
      esc(a) + ' <b>' + (a === "MOC" ? mocCount : notes.filter((n) => n.area === a).length) + '</b></span>'
    ).join("") + '</div>';
}
/* 全部笔记：芯片 + 可见集合（列表与导图两种形态共用的前处理） */
function notesPane(notes, filter, activeArea) {
  return { chips: notesChipsHtml(notes, activeArea), list: notesVisible(notes, filter, activeArea), areas: noteAreas(notes) };
}
function renderAllNotes(data, filter, activeArea) {
  const notes = (data && data.knowledgeNotes) || [];
  const pane = notesPane(notes, filter, activeArea);
  const chips = pane.chips, list = pane.list, areas = pane.areas;
  const kw = String(filter || "").trim();
  if (!list.length)
    return chips + '<div class="empty">' + (kw ? "没有匹配「" + esc(filter) + "」的笔记" : activeArea ? "该分类下暂无笔记" : "Knowledge 区暂无笔记") + '</div>';
  /* 按分类分块（细分到末级）：主分类无末级的直接成块（块头=主名），
     有末级的主名下再按末级各成块（块头=「主名 / 末级」）。块头纯文本，无 MOC 链接。
     块内排序继承 scan 结果（末级分类 → 名称拼音序），行右侧只留所属 MOC 标注。
     块体默认展开，块头点击仍可折叠。
     「MOC」为虚拟汇总块：全部/激活 MOC 时追加在最后（未分类前），列出全库 MOC 页；
     各主分类块中 MOC 页照常保留（不去重，按用户裁定）。 */
  const blockHtml = (rows0, title) => {
    if (!rows0.length) return "";
    const head = '<div class="group-head" data-toggle><span class="gname">' + esc(title) +
      '</span><span class="gcnt">' + rows0.length + ' 篇</span></div>';
    const body = '<div class="group-body">' + rows0.map((n) => {
      const meta = (n.mocs || []).filter(Boolean).join(" · ");
      return '<div class="row row2line" data-open="' + esc(n.path) + '">' +
        '<div class="rmain"><span class="rt" title="' + esc(n.path) + '">' + esc(n.name) + '</span>' +
        '<span class="rm">' + (meta
          ? '<span class="gcnt" title="所属 MOC（反向链接推断）">' + esc(meta) + '</span>' : "") +
        '<span class="arr">' + ICONS.arrow + '</span></span></div>' +
        (n.abstract ? '<div class="row-abs">' + esc(n.abstract) + '</div>' : "") +
        '</div>';
    }).join("") + '</div>';
    return '<div class="group">' + head + body + '</div>';
  };
  const areasHtml = areas.map((a) => {
    // MOC 虚拟分类：仅在全部视图或激活 MOC 芯片时输出。
    // 只按 category 主名（第一个标签）分组 → 8 大类各一块，块头即主名；
    // 无 category 的 MOC 页归入「MOC」本体块，固定在最前。
    if (a === "MOC") {
      if (activeArea && activeArea !== "MOC") return "";
      const mocs0 = list.filter(isMocNote);
      const mains = [];
      mocs0.forEach((n) => {
        if (mains.indexOf(n.area) < 0) mains.push(n.area);
      });
      mains.sort((x, y) => {
        const xm = x === "MOC", ym = y === "MOC";
        if (xm !== ym) return xm ? -1 : 1;
        return zh(x, y);
      });
      return mains.map((main) =>
        blockHtml(mocs0.filter((n) => n.area === main), main),
      ).join("");
    }
    // 激活 MOC 芯片时普通块全部让位（list 里虽含 MOC 页，但只进 MOC 汇总块）
    if (activeArea === "MOC") return "";
    // 该主分类下按末级细分（无末级的归 "" 组）
    const subs = [];
    list.filter((n) => n.area === a).forEach((n) => {
      const s = noteSubLabel(n);
      if (subs.indexOf(s) < 0) subs.push(s);
    });
    return subs.map((s) => {
      const rows0 = list.filter((n) => n.area === a && noteSubLabel(n) === s);
      return blockHtml(rows0, s ? a + " / " + s : a);
    }).join("");
  }).join("");
  return chips + '<div style="margin-top:12px">' + areasHtml + '</div>';
}

/* ---------- 全部笔记 · 思维导图形态（按 category 连线的横向树） ----------
   结构 = 根「知识库」→ 主类（category 第一项）→ 末级 → 笔记叶子，节点显示 frontmatter title。
   与列表同源：同一份 knowledgeNotes + 同一套芯片/搜索过滤，只是换一种空间化展现。
   布局用经典 tidy-tree（后序游标：叶子占一行、父节点居中于子节点），
   横向展开、层距固定 → 输出绝对坐标 SVG，交点处画贝塞尔连线。 */

/* 主类色相（hue）：与 CATEGORY_ORDER 顺序对应，末位留灰给未分类 / MOC 之外的兜底 */
const MM_HUES = [222, 268, 320, 190, 152, 30, 355, 96, 240];

/* 构建导图树：主类 → 末级 → 笔记。MOC 页只按自身 category 进树（此处不做虚拟汇总，
   汇总由芯片「MOC」过滤完成，避免同一篇在树里出现两次）。
   色相（hue）由主类下传给末级与笔记，供三层按同一色系着色，结构一眼可辨。 */
function buildMindTree(notes, areas) {
  const root = { kind: "root", label: "知识库", count: notes.length, children: [] };
  const areaIdx = {};
  areas.forEach((a, i) => { areaIdx[a] = i; });
  const areaMap = {};
  notes.forEach((n) => {
    const a = n.area || "未分类";
    if (!areaMap[a]) {
      areaMap[a] = { kind: "area", label: a, count: 0, hue: MM_HUES[(areaIdx[a] >= 0 ? areaIdx[a] : MM_HUES.length - 1) % MM_HUES.length], subMap: {}, children: [] };
    }
    const an = areaMap[a];
    an.count++;
    const s = noteSubLabel(n);
    if (!an.subMap[s]) an.subMap[s] = { kind: "sub", label: s || a, count: 0, hue: an.hue, children: [] };
    const sn = an.subMap[s];
    sn.count++;
    sn.children.push({ kind: "note", label: n.title || n.name, name: n.name, path: n.path, count: 0, hue: an.hue, children: [] });
  });
  areas.forEach((a) => {
    const an = areaMap[a];
    if (!an) return;
    // 末级按名称排序；笔记按展示标题拼音序（与列表的「末级 → 名称」同序）
    Object.keys(an.subMap).sort(zh).forEach((s) => {
      const sn = an.subMap[s];
      sn.children.sort((x, y) => zh(x.label, y.label));
      an.children.push(sn);
    });
    root.children.push(an);
  });
  return root;
}

/* tidy-tree 布局：后序游标分配 y（叶子逐行），父节点垂直居中于首末子节点。
   横向 x = 深度 × 层距 + 缩进（父节点按自身标签宽度再右移，短标签不被长标签挤远）。 */
function layoutMindTree(root, opts) {
  opts = opts || {};
  const rowH = opts.rowH || 26;        // 叶子行高
  const nodeH = opts.nodeH || 26;
  const levelGap = opts.levelGap || 58; // 层级间隙（父标签宽 + 此值 = 下一层起点）
  const padX = opts.padX || 18;
  const padY = opts.padY || 18;
  const nodes = [];
  let cursor = 0;

  // 首趟：后序定 y
  const walkY = (n, depth) => {
    n.depth = depth;
    if (!n.children.length) {
      n.y = cursor;
      cursor += rowH;
      return n.y;
    }
    const ys = n.children.map((c) => walkY(c, depth + 1));
    n.y = (ys[0] + ys[ys.length - 1]) / 2;
    return n.y;
  };
  walkY(root, 0);
  const height = Math.max(cursor, rowH);

  // 次趟：前序定 x（父节点占位 = 标签宽；子层起点 = 父 x + 父标签宽 + levelGap）
  const walkX = (n) => {
    if (n.x === undefined) n.x = padX;
    n.y = n.y + padY;
    nodes.push(n);
    const nextX = n.x + n.selfW + levelGap;
    n.children.forEach((c) => { c.x = nextX; walkX(c); });
  };
  walkX(root);
  let width = 0;
  nodes.forEach((n) => { width = Math.max(width, n.x + n.selfW); });
  width += padX;
  return { nodes: nodes, width: Math.max(width, 200), height: height + padY * 2, rowH: rowH, nodeH: nodeH };
}

/* 标签宽度估算（无 canvas 测量的离线友好版）：CJK / 全角按 1 em、其余按 0.56 em 计。 */
function mmTextWidth(s, fontPx) {
  const t = String(s == null ? "" : s);
  let units = 0;
  for (const ch of t) {
    const c = ch.codePointAt(0);
    units += (c >= 0x2e80 && c <= 0x9fff) || (c >= 0xf900 && c <= 0xfaff) || (c >= 0xff00 && c <= 0xff60) ||
      (c >= 0x3000 && c <= 0x303f) || (c >= 0x1f300 && c <= 0x1faff) ? 1 : 0.56;
  }
  return units * fontPx;
}

/* 给每个节点算自身占位宽（含内边距），供 tidy 布局定位子层。
   父节点（根/主类/末级）宽度 = 标签 + 计数徽标，避免子节点压字。 */
function mmMeasure(root) {
  const walk = (n) => {
    const isNote = n.kind === "note";
    const fontPx = n.kind === "root" ? 13 : isNote ? 12 : 12;
    let w = mmTextWidth(n.label, fontPx) + (isNote ? 22 : 18);
    if (!isNote) {
      const badge = n.kind === "root" ? String(n.count) : String(n.count);
      w += mmTextWidth(badge, 10) + 8;
    }
    n.selfW = Math.min(Math.max(w, n.kind === "root" ? 76 : 58), isNote ? 240 : 210);
    n.labelW = n.selfW;
    n.children.forEach(walk);
  };
  walk(root);
  return root;
}

/* 节点稳定键：折叠状态以「形态 + 标识」标识，跨重渲染保持。
   坑（2026-09-29 实测）：早先用 `\u0000` 作分隔符，该字符写进 HTML 属性时会被解析器替换成
   U+FFFD，读回来的键与 Set 里的对不上 → 点节点折叠静默失效。改用可打印分隔符 + URI 编码，
   编码后不会出现裸 `|`，故 `kind|标识` 无歧义。 */
function mmKey(n) {
  return n.kind + "|" + encodeURIComponent(n.path || n.label);
}

/* 默认折叠态：仅「超大图」先收起到主类 → 末级（撑不住全展时才收，保可读与可导航），
   其余一律直接展开到每篇笔记标题（用户需求本就是要看到标题）。
   实测规模：全库 280 篇（收起）；单主类最大 85 篇、AI大模型 74 篇（均展开）。
   force = true 时无论多少都收起到末级（「收起分支」按钮）。 */
const MM_AUTO_COLLAPSE_OVER = 150;
function mmDefaultCollapsed(tree, total, force) {
  const s = new Set();
  if (!force && total <= MM_AUTO_COLLAPSE_OVER) return s;
  tree.children.forEach((an) => an.children.forEach((sn) => s.add(mmKey(sn))));
  return s;
}

/* 节点 SVG：圆角矩形 + 标签 + 计数徽标（父节点）/ 折叠指示（有子时提示可折叠）。
   以节点左中为原点（translate 到 x,y），矩形 y ∈ [-h/2, h/2]，文字统一 y=0 垂直居中。 */
function mmNodeHtml(n, collapsed) {
  const isNote = n.kind === "note";
  const h = isNote ? 20 : n.kind === "root" ? 30 : 26;
  const hueStyle = n.hue === undefined ? "" : ' style="--mm-h:' + n.hue + '"';
  let svg = '<g class="mm-node mm-' + n.kind + '"' + hueStyle + ' data-mmkind="' + esc(n.kind) + '"' +
    (n.kind === "note" ? ' data-open="' + esc(n.path) + '"' : ' data-mmtoggle="' + esc(mmKey(n)) + '"') +
    ' transform="translate(' + n.x.toFixed(1) + ',' + n.y.toFixed(1) + ')">';
  svg += '<title>' + esc(isNote ? n.path : n.label + ' · ' + n.count + ' 篇') + '</title>';
  svg += '<rect class="mm-box" x="0" y="' + (-h / 2).toFixed(1) + '" width="' + n.selfW.toFixed(1) + '" height="' + h + '" rx="' + (isNote ? 6 : 9) + '"></rect>';
  let labelMax = n.selfW - 14;
  if (!isNote) {
    const badge = String(n.count);
    svg += '<text class="mm-badge" x="' + (n.selfW - 8).toFixed(1) + '" y="0" text-anchor="end" dominant-baseline="middle">' + esc(badge) + '</text>';
    labelMax = n.selfW - 14 - (mmTextWidth(badge, 10) + 8);
  }
  const label = mmEllipsis(n.label, Math.max(labelMax, 20), 12);
  svg += '<text class="mm-label" x="7" y="0" dominant-baseline="middle">' + esc(label) + '</text>';
  if (!isNote && n.children.length) {
    const chevX = Math.max(7 + mmTextWidth(label, 12) + 4, n.selfW - mmTextWidth(String(n.count), 10) - 18);
    if (chevX < n.selfW - 12) {
      svg += '<text class="mm-chev" x="' + chevX.toFixed(1) + '" y="0" dominant-baseline="middle">' + (collapsed ? "▸" : "▾") + '</text>';
    }
  }
  svg += '</g>';
  return svg;
}

/* 文本截断：按字符宽度累加，超出加省略号（离屏环境无真实测量，用估算宽度） */
function mmEllipsis(s, maxPx, fontPx) {
  const t = String(s == null ? "" : s);
  if (mmTextWidth(t, fontPx) <= maxPx) return t;
  let out = "";
  let w = 0;
  const ell = mmTextWidth("…", fontPx);
  for (const ch of t) {
    const cw = mmTextWidth(ch, fontPx);
    if (w + cw + ell > maxPx) break;
    out += ch;
    w += cw;
  }
  return out + "…";
}

/* 连线：父右中点 → 子左中点，三次贝塞尔 */
function mmEdgePath(px, py, pw, cx, cy) {
  const x1 = px + pw, y1 = py, x2 = cx, y2 = cy;
  const dx = Math.max(14, (x2 - x1) * 0.5);
  return "M" + x1.toFixed(1) + "," + y1.toFixed(1) + " C" + (x1 + dx).toFixed(1) + "," + y1.toFixed(1) +
    " " + (x2 - dx).toFixed(1) + "," + y2.toFixed(1) + " " + x2.toFixed(1) + "," + y2.toFixed(1);
}

/* 思维导图整体：分类芯片 + 视口（SVG 树 + 右上工具条：展开全部 / 收起分支 / 重置视图）
   collapsed 为 null/undefined 时按规模自动取默认折叠态（笔记多先收起到末级层）；
   显式传 Set（含空 Set）则按传入值渲染 —— 用户手动展收后即以该状态为准。 */
function renderMindMap(data, filter, activeArea, collapsed) {
  const notes = (data && data.knowledgeNotes) || [];
  const pane = notesPane(notes, filter, activeArea);
  const chips = pane.chips, list = pane.list, areas = pane.areas;
  const kw = String(filter || "").trim();
  if (!list.length)
    return chips + '<div class="empty">' + (kw ? "没有匹配「" + esc(filter) + "」的笔记" : activeArea ? "该分类下暂无笔记" : "Knowledge 区暂无笔记") + '</div>';

  const tree = buildMindTree(list, areas);
  mmMeasure(tree);
  const collapsedSet = collapsed instanceof Set ? collapsed : mmDefaultCollapsed(tree, list.length, false);

  /* 折叠 = 该节点子层不参与布局。做法：按可见性重建一棵同构子树（保留 x/y 之外的字段），
     这样折叠节点的后代在视觉上完全消失（而非仅隐藏子节点、留空白）。 */
  const visibleOf = (n, out) => {
    out.push(n);
    if (!collapsedSet.has(mmKey(n))) n.children.forEach((c) => visibleOf(c, out));
  };
  const visible = [];
  visibleOf(tree, visible);
  const visibleSet = new Set(visible);
  const layoutRoot = Object.assign({}, tree, { children: [] });
  const rebuild = (src, dst) => {
    dst.children = src.children.filter((c) => visibleSet.has(c)).map((c) => {
      const copy = Object.assign({}, c, { children: [] });
      rebuild(c, copy);
      return copy;
    });
  };
  rebuild(tree, layoutRoot);

  const layout = layoutMindTree(layoutRoot, { rowH: 26, levelGap: 58, padX: 18, padY: 18 });

  // 边：仅连可见父子
  const edges = [];
  const walkEdges = (n) => {
    n.children.forEach((c) => {
      edges.push(mmEdgePath(n.x, n.y, n.selfW, c.x, c.y));
      walkEdges(c);
    });
  };
  walkEdges(layoutRoot);
  const nodeSvg = layout.nodes.map((n) => mmNodeHtml(n, collapsedSet.has(mmKey(n)))).join("");
  const edgeSvg = edges.map((d) => '<path class="mm-edge" d="' + d + '"></path>').join("");

  /* SVG 按布局单位 1:1 出图（width/height = 布局尺寸），缩放交由视口的 transform 承担；
     viewBox 与尺寸一致 → 文字不随视口压缩，始终按 CSS 像素渲染，保证可读性。 */
  const svgW = Math.max(1, Math.round(layout.width));
  const svgH = Math.max(1, Math.round(layout.height));
  const svg = '<svg class="mm-svg" width="' + svgW + '" height="' + svgH +
    '" viewBox="0 0 ' + svgW + ' ' + svgH + '" data-mmsize="' + svgW + 'x' + svgH + '"><g class="mm-layer">' + edgeSvg + nodeSvg + '</g></svg>';

  const tools = '<div class="mm-tools">' +
    '<button class="mm-tool" data-mmtool="expand" title="展开全部分支">展开全部</button>' +
    '<button class="mm-tool" data-mmtool="collapse" title="收起全部分支（只留分类与末级）">收起分支</button>' +
    '<button class="mm-tool" data-mmtool="reset" title="重置缩放与平移">重置视图</button>' +
    '</div>';
  const rootY = layoutRoot.y || 0;

  return chips +
    '<div class="mm-wrap" style="margin-top:12px">' + tools +
    '<div class="mm-viewport" id="mmViewport" data-mmanchor="' + rootY.toFixed(1) + '">' + svg + '</div>' +
    '<div class="mm-hint">滚轮缩放 · 拖动平移 · 点分类折叠 · 点笔记打开</div>' +
    '</div>';
}

/* 全部笔记：形态分发（list = 分组列表；map = 思维导图）。两形态共用芯片/过滤/折叠数据源。 */
function renderNotesForm(data, form, filter, activeArea, collapsed) {
  return form === "map"
    ? renderMindMap(data, filter, activeArea, collapsed)
    : renderAllNotes(data, filter, activeArea);
}

/* ---------- Home · 热力值（GitHub 风格日历热力图） ----------
   数据 = scan().heat（{ map, max, total, start, weeks }）；格子 = 一天，列 = 一周（周日→周六）。
   分档：0 空 / 1..4 四档（相对 max 取四等分，GitHub 同款「相对强度 + 绝对空档」口径）。
   格子 title 给出「日期 · N 篇」，可复现可核对；横向溢出走滚动。 */
function renderHeat(heat) {
  heat = heat || {};
  const map = heat.map || {};
  const weeks = heat.weeks || 53;
  const start = heat.start || Date.now();
  const pad = (x) => String(x).padStart(2, "0");
  const dayKey = (t) => { const d = new Date(t); return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()); };
  const max = heat.max || 0;
  /* 分档用**分位数**而非线性 max：库内存在批量导入/批量编辑造成的长尾（实测单日峰值 399 篇、
     中位数仅 3 篇），按 max 线性四等分会把全部日常压进最低档、梯度失效。
     取非零日计数的 p40 / p65 / p85 作三档阈值（tail 一档收长尾），与 GitHub 的可读性取向一致。 */
  const nz = Object.keys(map).map((k) => map[k]).filter((n) => n > 0).sort((a, b) => a - b);
  const q = (p) => (nz.length ? nz[Math.min(nz.length - 1, Math.floor(nz.length * p))] : 1);
  const th = [q(0.40), q(0.65), q(0.85)];
  const level = (n) => {
    if (!n) return 0;
    if (n <= th[0]) return 1;
    if (n <= th[1]) return 2;
    if (n <= th[2]) return 3;
    return 4;
  };

  const today = new Date(); today.setHours(0, 0, 0, 0);
  const todayTime = today.getTime();
  const cols = [];
  let activeDays = 0;
  for (let w = 0; w < weeks; w++) {
    const cellHtml = [];
    let monthHere = -1;
    for (let dow = 0; dow < 7; dow++) {
      const t = start + (w * 7 + dow) * 86400000;
      if (t > todayTime) { cellHtml.push('<div class="heat-cell heat-cell-blank" aria-hidden="true"></div>'); continue; }
      const k = dayKey(t);
      const n = map[k] || 0;
      if (n > 0) activeDays++;
      const d = new Date(t);
      if (monthHere < 0) monthHere = d.getMonth();
      const label = (d.getMonth() + 1) + "月" + d.getDate() + "日 · " + n + " 篇";
      cellHtml.push('<div class="heat-cell heat-l' + level(n) + '" title="' + esc(label) + '" data-heat="' + esc(k) + '"></div>');
    }
    cols.push({ html: cellHtml.join(""), month: monthHere });
  }
  // 月份标签并入每周列（每列都有标签占位，保证 7 格跨列水平对齐）；仅在月份变化的列标注。
  // 首列是「上月残周」（只含上月最后几天，用户 2026-09-30 裁定不标），从下一个完整月份开始标，
  // 否则「9月 / 10月」两个标签挤在最前面，既难读又无信息量。
  const colsHtml = cols.map((c, i) => {
    const lbl = (i > 0 && c.month !== cols[i - 1].month) ? (c.month + 1) + "月" : "";
    return '<div class="heat-col"><div class="heat-month">' + esc(lbl) + '</div>' + c.html + '</div>';
  }).join("");

  const legend = '<span class="heat-legend">少' +
    '<span class="heat-cell heat-l0"></span><span class="heat-cell heat-l1"></span>' +
    '<span class="heat-cell heat-l2"></span><span class="heat-cell heat-l3"></span>' +
    '<span class="heat-cell heat-l4"></span>多</span>';

  return '<div class="heat-wrap">' +
    '<div class="heat-sum">近 12 个月共 <b>' + (heat.total || 0) + '</b> 次笔记变动 · 有记录 <b>' + activeDays + '</b> 天' +
    (max ? ' · 单日最多 <b>' + max + '</b> 篇' : '') + '</div>' +
    '<div class="heat-scroll"><div class="heat-cols">' + colsHtml + '</div></div>' +
    '<div class="heat-foot"><span>每日被修改的笔记数（全 vault）</span>' + legend + '</div>' +
    '</div>';
}

/* 归属路径标注：Memory/Projects 下的显示项目名，其余显示一级/两级目录 */
function areaLabel(path) {
  const parts = String(path).split("/");
  if (parts[0] === "Memory" && parts[1] === "Projects" && parts[2]) return parts[2];
  if (parts.length >= 3) return parts[0] + "/" + parts[1];
  return parts[0] || path;
}

/* 知识库视图：最近更新（归属徽标 + 时间，点击打开） */
function renderRecent(recent) {
  recent = recent || [];
  if (!recent.length) return '<div class="empty">最近 7 天没有笔记变动</div>';
  const p2 = (x) => String(x).padStart(2, "0");
  return recent.map((r) => {
    const d = new Date(r.mtime);
    const when = p2(d.getMonth() + 1) + "-" + p2(d.getDate()) + " " + p2(d.getHours()) + ":" + p2(d.getMinutes());
    return '<div class="row" data-open="' + esc(r.path) + '">' +
      '<span class="cat" title="归属：' + esc(r.area || "") + '">' + esc(r.area || "") + '</span>' +
      '<span class="rt" title="' + esc(r.path) + '">' + esc(r.name) + '</span>' +
      '<span class="rm"><span class="gcnt">' + when + '</span><span class="arr">' + ICONS.arrow + '</span></span></div>';
  }).join("");
}

/* 记忆库视图：子 tab 分区（待办 / 项目 / 待审核） */
function renderMemory(data) {
  // 待办 tab：Todo 全部分组
  const byGroup = {};
  data.todo.forEach((t) => { (byGroup[t.group] = byGroup[t.group] || []).push(t); });
  // Todo 分组显示顺序：默认按 Todo.md 中的出现顺序；如需置顶某些分组，把分组名写进下面数组
  const order = [];
  const rest = Object.keys(byGroup).filter((g) => !order.includes(g));
  const allGroups = order.concat(rest);
  const todoHtml = allGroups.map((g) => {
    const items = byGroup[g];
    if (!items) return "";
    const open = items.filter((i) => !i.done).length;
    const lines = items.map((t) => '<div class="todo-line' + (t.done ? " done" : "") + '"><span class="ok"></span><span class="txt">' + esc(t.text) + '</span></div>').join("");
    return '<div class="group"><div class="group-head" data-toggle><span class="gname">' + esc(g) + '</span><span class="gcnt">' + open + '/' + items.length + '</span></div><div class="group-body">' + lines + '</div></div>';
  }).join("") || '<div class="empty">暂无待办</div>';

  // 项目 tab：按状态排序（进行中在前）
  const rank = { "进行中": 0, "暂停": 1, "": 2, "封存": 3, "外部": 4 };
  const sortedProj = data.projects.slice().sort((a, b) => (rank[a.status] ?? 9) - (rank[b.status] ?? 9));
  const stCls = { "进行中": "st-run", "暂停": "st-pause", "封存": "st-lock", "外部": "st-ext" };
  const projHtml = '<div class="proj-list">' + sortedProj.map((p) => {
    const st = p.status ? '<span class="st ' + (stCls[p.status] || "") + '">' + esc(p.status) + '</span>' : "";
    return '<div class="proj-item"><span class="pname">' + esc(p.name) + '</span><span class="pdesc" title="' + esc(p.desc) + '">' + esc(p.desc) + '</span>' + st + '</div>';
  }).join("") + '</div>';

  // 待审核 tab：Inbox 全部按日
  const inboxHtml = data.inbox.slice().reverse().map((i) =>
    '<div class="inbox-line"><span style="color:var(--kw-text2)">' + esc(i.date) + '</span><span class="cnt' + (i.count === 0 ? " zero" : "") + '">' + i.count + ' 条</span></div>'
  ).join("") || '<div class="empty">暂无待审核</div>';

  return '<div class="tab-bar">' +
    '<button class="tab-btn active" data-tab="todo">待办 <span class="gcnt">' + data.todo.length + '</span></button>' +
    '<button class="tab-btn" data-tab="projects">项目 <span class="gcnt">' + data.projects.length + '</span></button>' +
    '<button class="tab-btn" data-tab="inbox">待审核 <span class="gcnt">' + data.inbox.length + '</span></button>' +
    '</div>' +
    '<div data-pane="todo">' + todoHtml + '</div>' +
    '<div data-pane="projects" style="display:none">' + projHtml + '</div>' +
    '<div data-pane="inbox" style="display:none">' + inboxHtml + '</div>';
}

/* 知识库视图：发布状态（待发布 + 归档） */
function renderPublish(data) {
  const drafts = data.zimeiti_drafts.filter((d) => d.status === "待发布" || !d.status);
  const draftHtml = drafts.map((d) =>
    '<div class="pubrow"><span class="p" title="' + esc(d.file) + '">' + esc(d.file.replace(/\.md$/, "")) + '</span><span class="tag tag-warn">待发布</span></div>'
  ).join("") || '<div class="empty">暂无待发布</div>';
  const archivedHtml = '<div class="pubrow"><span class="p">文稿/归档/</span><b>' + data.zimeiti_archived + ' 篇</b></div>';
  return '<div class="pubcol"><h4><span style="color:var(--kw-amber)">待发布</span><span class="n">' + drafts.length + '</span></h4>' + draftHtml + '</div>' +
    '<div class="pubcol"><h4><span style="color:var(--kw-text3)">已归档</span><span class="n">' + data.zimeiti_archived + '</span></h4>' + archivedHtml + '</div>';
}

/* ---------- 日记模块（DailyNotes 自动聚合；单页整合：统计瓦片 + 年份芯片过滤 + 年份分组列表） ----------
   2026-10-01 用户裁定精简：不分多模块，统计与年份整合到一起，删除「最近」「标签」；
   点年份芯片只看该年（再点同芯片恢复全部）。行点击打开日记，分组折叠复用 handleDomClick
   的通用 [data-toggle] 逻辑。 */

/* 统计瓦片：总数 / 年份跨度 / 最近一篇 / 本月篇数 */
function renderDiaryStats(diaries) {
  diaries = diaries || [];
  const years = {};
  diaries.forEach((d) => { years[d.year] = (years[d.year] || 0) + 1; });
  const ys = Object.keys(years).sort();
  const now = new Date();
  const thisMonth = now.getFullYear() + "-" + String(now.getMonth() + 1).padStart(2, "0");
  const monthCount = diaries.filter((d) => d.date.indexOf(thisMonth) === 0).length;
  const latest = diaries[0];
  if (!diaries.length) return '<div class="empty">DailyNotes 下还没有日记（文件名 YYYY_MM_DD.md 即自动进这里）</div>';
  const tiles = [
    [diaries.length + " 篇", "日记总数", false],
    [ys[0] + " — " + ys[ys.length - 1], "年份跨度", true],
    [latest ? latest.date : "—", "最近一篇", true],
    [monthCount + " 篇", "本月（" + thisMonth + "）", false],
  ];
  return '<div class="focus cols4">' + tiles.map(([v, k, small]) =>
    '<div class="ftile"><span class="v' + (small ? " v-sm" : "") + '">' + esc(v) + '</span><span class="k">' + esc(k) + '</span></div>'
  ).join("") + '</div>';
}

/* 日记行（双行形态）：主行 = 日期 + 星期，副行 = 首句预览；点击打开日记 */
function diaryRow(d, withYear) {
  const label = (withYear ? d.date : d.date.slice(5)) + (diaryWeekday(d.date) ? " · " + diaryWeekday(d.date) : "");
  return '<div class="row row2line" data-open="' + esc(d.path) + '">' +
    '<div class="rmain"><span class="rt" title="打开 ' + esc(d.name) + '">' + esc(label) + '</span>' +
    '<span class="rm"><span class="arr">' + ICONS.arrow + '</span></span></div>' +
    (d.preview && d.preview !== "（空）" ? '<div class="row-abs">' + esc(d.preview) + '</div>' : "") +
    '</div>';
}

/* 年份芯片 + 年份分组列表（activeYear = 只看该年；芯片点击由视图层 [data-diaryyear] 处理，
   只重渲染本函数所在容器 #diaryListPane，不动统计瓦片与折叠状态） */
function renderDiaryList(diaries, activeYear) {
  diaries = diaries || [];
  const byYear = {};
  diaries.forEach((d) => { (byYear[d.year] = byYear[d.year] || []).push(d); });
  const years = Object.keys(byYear).sort().reverse();
  const chips = '<div class="notechips" style="margin-bottom:12px">' +
    '<span class="kbstat' + (!activeYear ? " active" : "") + '" data-diaryyear="" title="显示全部年份">全部 <b>' + diaries.length + '</b></span>' +
    years.map((y) =>
      '<span class="kbstat' + (activeYear === y ? " active" : "") + '" data-diaryyear="' + y +
      '" title="只看 ' + y + ' 年（再点一次恢复全部）">' + y + ' <b>' + byYear[y].length + '</b></span>'
    ).join("") + '</div>';
  const shown = (activeYear && byYear[activeYear] ? [activeYear] : years).map((y) => {
    const list = byYear[y]; // 组内保持 scan 的倒序：最新日记在最上方（用户 2026-10-01 裁定，覆盖此前的「组内正序顺读」）
    return '<div class="group"><div class="group-head" data-toggle><span class="gname">' + y + ' 年</span>' +
      '<span class="gcnt">' + list.length + ' 篇</span></div>' +
      '<div class="group-body"><div class="rows">' + list.map((d) => diaryRow(d, false)).join("") + '</div></div></div>';
  }).join("");
  return chips + (shown || '<div class="empty">该年份暂无日记</div>');
}

/* 日记模块整体：统计瓦片（静态）+ 年份过滤与分组列表（#diaryListPane，年份切换只重渲染这一层） */
function renderDiary(data, activeYear) {
  const diaries = (data && data.diaries) || [];
  const stats = renderDiaryStats(diaries);
  if (!diaries.length) return stats;
  return stats + '<div id="diaryListPane" style="margin-top:16px">' + renderDiaryList(diaries, activeYear) + '</div>';
}

function buildHtml(data, view, todos, kbFilter, noteArea, noteForm, mmCollapsed, diaryYear) {
  todos = todos || [];
  // 视图键：home（最近更新 + 快速打开）/ todo / kb（知识地图）/ mem / diary / notes；
  // 旧存档 "kb" 视图名不变（图谱构建逻辑绑定其上），home 缺省回落 todo
  const v = ["home", "todo", "kb", "mem", "diary", "notes"].indexOf(view) >= 0 ? view : "todo";
  const navBtn = (key, icon, label) =>
    '<button class="view-btn' + (v === key ? " active" : "") + '" data-view="' + key + '">' + icon + label + '</button>';
  const paneAttr = (key) => ' data-viewpane="' + key + '"' + (v === key ? "" : ' style="display:none"');

  return '<style>' + CSS + '</style>' +
    '<div class="ws-root" data-theme="light" data-style="theme"><div class="wrap">' +
    '<header>' +
    '<div class="brand"><div class="logo">' + ICONS.logo + '</div><div><h1>知识工作台</h1><p>博客 · 知识库 · 记忆 三层结构</p></div></div>' +
    '<div class="head-actions">' +
    '<span class="snapshot">' + ICONS.clock + '<span id="scanTime">' + esc(data.scanTime) + '</span></span>' +
    '<button class="btn btn-sm" id="btnTheme" title="切换亮/暗模式">' + ICONS.moon + '</button>' +
    '<button class="btn btn-sm" id="btnRefresh" title="重新扫描 vault 数据">刷新</button>' +
    '<button class="btn btn-sm" id="btnExport" title="导出当前真实数据快照为 JSON">导出</button>' +
    '</div></header>' +

    '<nav class="viewnav">' +
    navBtn("home", ICONS.navHome, "Home") +
    navBtn("todo", ICONS.navToday, "Todo") +
    navBtn("kb", ICONS.navKb, "知识地图") +
    navBtn("mem", ICONS.navMem, "记忆库") +
    navBtn("diary", ICONS.navDiary, "日记") +
    navBtn("notes", ICONS.navNotes, "全部笔记") +
    '</nav>' +

    /* ---- Home（热力值整宽置顶 + 最近更新 + 快速打开 双栏） ---- */
    '<div' + paneAttr("home") + '>' +
    '<section class="heat-sec"><div class="sec-head"><div><div class="eyebrow">Heat</div><div class="sec-title">热力值</div></div><span class="sec-sub">近 12 个月笔记变动</span></div>' + renderHeat(data.heat) + '</section>' +
    '<div class="twocol kbcols">' +
    '<section><div class="sec-head"><div><div class="eyebrow">Recent</div><div class="sec-title">最近更新</div></div><span class="sec-sub">全 vault · 近 7 天</span></div><div class="rows rows-compact">' + renderRecent(data.recent) + '</div></section>' +
    '<div class="kbright">' +
    '<section><div class="sec-head"><div><div class="eyebrow">Find</div><div class="sec-title">快速打开</div></div><span class="sec-sub">Knowledge / 作坊 / 档案</span></div><div class="kb-search"><input id="kbSearch" placeholder="输入笔记名关键词" /></div><div id="kbSearchResults" class="rows rows-compact"></div></section>' +
    '</div></div></div>' +

    /* ---- Todo ---- */
    '<div' + paneAttr("todo") + '>' +
    '<div class="focus" id="focusTiles">' + renderFocusTiles(data, todos) + '</div>' +
    '<div class="twocol">' +
    '<section><div class="sec-head"><div><div class="eyebrow">Todo</div><div class="sec-title">我的待办</div></div><span class="sec-sub">插件记录 · 点击行编辑详情 · @日期时间快捷添加</span></div><div id="todoModule">' + renderTodoModule(todos) + '</div></section>' +
    '<section><div class="sec-head"><div><div class="eyebrow">Inbox</div><div class="sec-title">待审核速览</div></div><span class="sec-sub">最近 5 天 · 点击打开登记</span></div><div class="rows">' + renderInboxRecent(data) + '</div></section>' +
    '<section><div class="sec-head"><div><div class="eyebrow">Publish</div><div class="sec-title">发布状态</div></div><span class="sec-sub">自媒体文稿</span></div><div class="pubgrid">' + renderPublish(data) + '</div></section>' +
    '</div></div>' +

    /* ---- 知识地图（原「知识库」，仅保留地图） ---- */
    '<div' + paneAttr("kb") + '>' +
    '<section><div class="sec-head"><div><div class="eyebrow">Map</div><div class="sec-title">知识地图</div></div><span class="sec-sub"><span class="kblink" data-goto="notes">全部笔记</span></span></div>' + renderKbMap(data, kbFilter) +
    '<div id="nativeGraphHost" class="kb-graphwrap native-embed"></div></section>' +
    '</div>' +

    /* ---- 记忆库 ---- */
    '<div' + paneAttr("mem") + '>' +
    '<section><div class="sec-head"><div><div class="eyebrow">Memory</div><div class="sec-title">记忆系统</div></div><span class="sec-sub">待办 · 项目 · 待审核</span></div>' + renderMemory(data) + '</section>' +
    '</div>' +

    /* ---- 日记（DailyNotes 自动聚合） ---- */
    '<div' + paneAttr("diary") + '>' +
    '<section><div class="sec-head"><div><div class="eyebrow">Diary</div><div class="sec-title">日记总览</div></div>' +
    '<span class="sec-sub">DailyNotes · 共 ' + (data.diaries || []).length + ' 篇 · 新增日记自动进这里</span></div>' +
    renderDiary(data, diaryYear) + '</section>' +
    '</div>' +

    /* ---- 全部笔记（列表 / 思维导图两种形态） ---- */
    '<div' + paneAttr("notes") + '>' +
    '<section><div class="sec-head"><div><div class="eyebrow">Index</div><div class="sec-title">全部笔记</div></div>' +
    '<span class="sec-sub notes-head-right">' +
    '<span>Knowledge 区 · 共 ' + ((data.knowledgeNotes || []).length) + ' 篇</span>' +
    '<span class="tab-bar notes-seg">' +
    '<button class="tab-btn' + (noteForm !== "map" ? " active" : "") + '" data-noteform="list" title="分组列表形态">列表</button>' +
    '<button class="tab-btn' + (noteForm === "map" ? " active" : "") + '" data-noteform="map" title="思维导图形态（按 category 连线，节点显示标题）">思维导图</button>' +
    '</span></span></div>' +
    '<div class="kb-search"><input id="notesSearch" placeholder="按标题 / 文件名 / 子分类 / 所属 MOC 过滤" /></div>' +
    '<div id="allNotesList" style="margin-top:12px">' + renderNotesForm(data, noteForm, "", noteArea || "", mmCollapsed) + '</div></section>' +
    '</div>' +

    '<footer>实时扫描 vault 真实数据 · 文件变动自动刷新</footer>' +
    '</div></div>';
}

/* ============================ 导出快照 ============================ */

function exportSnapshot(data) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "知识工作台快照_" + data.scanTime.slice(0, 10) + ".json";
  a.click();
  URL.revokeObjectURL(a.href);
  new Notice("已导出真实数据快照 JSON");
}

/* ============================ 纯 DOM 交互（与渲染分离，供视图与离线测试共用） ============================ */

/*
 * 处理工作台内部的纯 DOM 交互：视图切换 / 分组折叠 / 子 tab / 跳转。
 * 返回 true 表示已处理；openPath 回调由视图注入，测试环境传空函数即可。
 * 渲染函数之间不互调，所有联动由事件层统一调度（防循环依赖）。
 */
function handleDomClick(rootEl, target, openPath, onKbFilter) {
  // 顶层视图切换（今日 / 知识库 / 记忆库）
  const viewBtn = target.closest("[data-view]");
  if (viewBtn) {
    const key = viewBtn.getAttribute("data-view");
    const nav = viewBtn.parentElement;
    nav.querySelectorAll("[data-view]").forEach((b) => b.classList.remove("active"));
    viewBtn.classList.add("active");
    rootEl.querySelectorAll("[data-viewpane]").forEach((p) => {
      p.style.display = p.getAttribute("data-viewpane") === key ? "" : "none";
    });
    try { localStorage.setItem("kw_view", key); } catch (e) { /* file:// 等环境可能受限，忽略 */ }
    return true;
  }

  // 待办分组折叠
  const head = target.closest("[data-toggle]");
  if (head) {
    const body = head.nextElementSibling;
    if (body) body.style.display = body.style.display === "none" ? "" : "none";
    return true;
  }

  // 记忆系统子 tab（待办 / 项目 / 待审核）
  const tabBtn = target.closest("[data-tab]");
  if (tabBtn) {
    const bar = tabBtn.parentElement;
    bar.querySelectorAll("[data-tab]").forEach((b) => b.classList.remove("active"));
    tabBtn.classList.add("active");
    const key = tabBtn.getAttribute("data-tab");
    const root = bar.parentElement;
    root.querySelectorAll("[data-pane]").forEach((p) => {
      p.style.display = p.getAttribute("data-pane") === key ? "" : "none";
    });
    return true;
  }

  // 知识地图统计条芯片：点亮 → 图谱只看该分区（再点同芯片恢复全图）；回调缺省时（离线测试）仅选中态由渲染层负责
  const chip = target.closest("[data-kbfilter]");
  if (chip && typeof onKbFilter === "function") {
    onKbFilter(chip.getAttribute("data-kbfilter"));
    return true;
  }

  // 列表行 / 卡片跳转
  const opener = target.closest("[data-open]");
  if (opener) {
    openPath(opener.getAttribute("data-open"));
    return true;
  }
  return false;
}

/* ============================ 视图 ============================ */

class KnowledgeWorkspaceView extends ItemView {
  constructor(leaf, plugin) {
    super(leaf);
    this.plugin = plugin || null;
  }

  getViewType() { return VIEW_TYPE; }
  getDisplayText() { return "知识工作台"; }
  getIcon() { return "layout-dashboard"; }

  async onOpen() {
    this.contentEl.addClass("knowledge-workspace-view");
    // 事件委托：DOM 交互统一走 handleDomClick，按钮类交互在此分发
    this.contentEl.addEventListener("click", (e) => {
      const target = e.target instanceof Element ? e.target : null;
      if (!target) return;

      // 清除已完成：必须先于 handleDomClick（按钮在 data-toggle 折叠头内，避免被折叠逻辑吞掉）
      if (target.closest("[data-clear]")) { if (this.plugin) this.plugin.clearDone(); return; }

      // 头部快捷入口（如知识地图分区头 → 全部笔记视图）
      const goto = target.closest("[data-goto]");
      if (goto) { this.switchView(goto.getAttribute("data-goto")); return; }

      // 思维导图视口内的点击（节点打开 / 折叠）由 wireMindMap 的 pointerup 统一处理：
      // setPointerCapture 会把 click 的 target 改写成视口，此路径在导图内不可靠，须在此放行，
      // 否则「程序化派发能开、真实鼠标点击打不开」且会与 pointerup 双重触发。
      if (target.closest("#mmViewport")) return;

      const handled = handleDomClick(this.contentEl, target, (p) => this.openPath(p), (path) => this.toggleKbFilter(path));
      if (handled) {
        // 切到知识库视图时嵌入原生图谱（隐藏状态拿不到宽度，只能此时建）
        const viewBtn = target.closest("[data-view]");
        if (viewBtn && viewBtn.getAttribute("data-view") === "kb") this.buildGraphView();
        return;
      }

      const chk = target.closest("[data-check]");
      if (chk) { if (this.plugin) this.plugin.toggleTodo(chk.getAttribute("data-check")); return; }
      const item = target.closest("[data-todo]");
      if (item) { this.openTodoModal(item.getAttribute("data-todo")); return; }
      if (target.closest("#todoAddBtn")) { this.addFromInput(); return; }
      if (target.closest("#kbAuditBtn")) { this.runKnowledgeAudit(); return; }

      if (target.closest("#btnTheme")) { this.toggleTheme(); return; }
      if (target.closest("#btnRefresh")) { this.render(); return; }
      if (target.closest("#btnExport")) {
        exportSnapshot(Object.assign({}, this.data, { todos: this.plugin ? this.plugin.todoData.todos : [] }));
        return;
      }
    });
    // 待办快速添加：输入框内回车
    this.contentEl.addEventListener("keydown", (e) => {
      const el = e.target;
      if (el && el.id === "todoInput" && e.key === "Enter") this.addFromInput();
    });
    // 知识库：快速打开过滤（input 事件冒泡，可委托）
    this.contentEl.addEventListener("input", (e) => {
      if (e.target && e.target.id === "kbSearch") this.renderKbSearch(e.target.value);
      if (e.target && e.target.id === "notesSearch") {
        this._noteFilter = e.target.value;
        this.refreshAllNotesList();
      }
    });
    // 全部笔记：分类芯片点击（委托 change 之外再补 click，kbstat 是 span 非按钮）
    this.contentEl.addEventListener("click", (e) => {
      const t = e.target instanceof Element ? e.target : null;
      if (!t) return;
      const chip = t.closest("[data-notearea]");
      if (chip) {
        const area = chip.getAttribute("data-notearea") || "";
        this._noteArea = this._noteArea === area ? "" : area;
        this.refreshAllNotesList();
        return;
      }
      // 全部笔记：形态切换（列表 / 思维导图）
      const formBtn = t.closest("[data-noteform]");
      if (formBtn) {
        this._noteForm = formBtn.getAttribute("data-noteform") === "map" ? "map" : "list";
        try { localStorage.setItem("kw_noteform", this._noteForm); } catch (err) { /* 受限环境忽略 */ }
        this.refreshAllNotesList();
        return;
      }
      // 日记·年份芯片：点亮只看该年（再点同芯片恢复全部）；只重渲染列表层，不动统计瓦片与折叠状态
      const dyear = t.closest("[data-diaryyear]");
      if (dyear) {
        const year = dyear.getAttribute("data-diaryyear") || "";
        this._diaryYear = this._diaryYear === year ? "" : year;
        const pane = this.contentEl.querySelector("#diaryListPane");
        if (pane) pane.innerHTML = renderDiaryList((this.data && this.data.diaries) || [], this._diaryYear);
        return;
      }
      // 全部笔记·思维导图：节点点击由 wireMindMap 的 pointerup 统一接管（因 setPointerCapture
      // 会改写 click 的 target，click 路径在导图内不可靠）；此处直接放行，避免双重触发。
      if (t.closest("#mmViewport")) return;
    });
    // Obsidian 明暗切换后同步工作台（跟随主题模式下 CSS 变量自动刷新，此处同步 data-theme 与按钮图标）
    this.registerEvent(this.app.workspace.on("css-change", () => this.applyTheme()));
    await this.render();
  }

  async onClose() {
    this.releaseNativeGraph();
  }

  // 当前生效主题：始终镜像 Obsidian 实际明暗（工作台样式无本地覆盖）
  effectiveTheme() {
    return document.body.classList.contains("theme-dark") ? "dark" : "light";
  }

  applyTheme() {
    const theme = this.effectiveTheme();
    const root = this.contentEl.querySelector(".ws-root");
    if (root) root.setAttribute("data-theme", theme);
    this.updateThemeIcon(theme);
  }

  updateThemeIcon(theme) {
    const btn = this.contentEl.querySelector("#btnTheme");
    if (!btn) return;
    const dark = theme === "dark";
    btn.innerHTML = dark ? ICONS.moon : ICONS.sun;
    btn.title = dark ? "当前暗色 · 点击切换亮色" : "当前亮色 · 点击切换暗色";
  }

  async toggleTheme() {
    // 工作台样式始终跟随 Obsidian：本按钮切换 Obsidian 全局明暗，视图经 css-change 同步。
    // 坑：executeCommandById 对不存在的命令「静默返回」不抛错 —— 调用后必须校验 body 类是否真的翻转。
    // 命令 ID 以本机 obsidian.asar 实测为准：1.9.x 为 theme:toggle-light-dark；旧版本叫 appearance:toggle-dark-light。
    const before = document.body.classList.contains("theme-dark");
    const flipped = () => document.body.classList.contains("theme-dark") !== before;
    const ids = ["theme:toggle-light-dark", "appearance:toggle-dark-light"];
    for (const id of ids) {
      try {
        this.app.commands.executeCommandById(id);
      } catch (e) { /* 命令异常时走兜底 */ }
      await new Promise((resolve) => setTimeout(resolve, 60));
      if (flipped()) { this.applyTheme(); return; }
    }
    // 兜底：等价于 Obsidian 自身的切换流程 —— 切 body 类 + 持久化到 appearance 配置
    try {
      document.body.classList.remove(before ? "theme-dark" : "theme-light");
      document.body.classList.add(before ? "theme-light" : "theme-dark");
      if (typeof this.app.vault.setConfig === "function") {
        this.app.vault.setConfig("theme", before ? "moonstone" : "obsidian");
      }
      this.applyTheme();
      new Notice(before ? "已切换到亮色模式" : "已切换到暗色模式");
    } catch (e) {
      new Notice("切换失败：请用 Ctrl+P 搜索「light/dark mode」执行");
    }
  }

  async openPath(path) {
    const af = this.app.vault.getAbstractFileByPath(path);
    if (af instanceof TFile) {
      await this.app.workspace.getLeaf("tab").openFile(af);
    } else if (af instanceof TFolder) {
      // 目录：在文件列表中定位展开，不新开标签页
      const fe = this.app.internalPlugins && this.app.internalPlugins.getPluginById("file-explorer");
      if (fe && fe.instance && fe.instance.revealInFolder) fe.instance.revealInFolder(af);
      else new Notice("未找到文件列表面板，无法定位：" + path);
    } else {
      new Notice("入口不存在：" + path);
    }
  }

  // 顶层视图切换（导航 pill 与头部快捷入口共用；key = todo / kb / mem / notes）
  switchView(key) {
    const btn = this.contentEl.querySelector('[data-view="' + key + '"]');
    if (!btn) return;
    this.contentEl.querySelectorAll("[data-view]").forEach((b) => b.classList.toggle("active", b === btn));
    this.contentEl.querySelectorAll("[data-viewpane]").forEach((p) => {
      p.style.display = p.getAttribute("data-viewpane") === key ? "" : "none";
    });
    try { localStorage.setItem("kw_view", key); } catch (e) { /* file:// 等环境可能受限，忽略 */ }
    if (key === "kb") this.buildGraphView();
  }

  // 从输入框添加待办（Enter / 添加按钮共用）
  async addFromInput() {
    const input = this.contentEl.querySelector("#todoInput");
    if (!input || !this.plugin) return;
    const raw = input.value;
    if (!raw.trim()) { new Notice("先写点内容再添加"); return; }
    input.value = "";
    const okAdded = await this.plugin.addTodo(raw);
    if (!okAdded) new Notice("待办内容为空（若只输入了 @日期，请在前面写上事项）");
  }

  // 仅重渲染 Todo 相关区块（瓦片 + 待办模块），不重建整视图
  refreshTodoUI() {
    const todos = this.plugin ? this.plugin.todoData.todos : [];
    const tiles = this.contentEl.querySelector("#focusTiles");
    if (tiles) tiles.innerHTML = renderFocusTiles(this.data, todos);
    const mod = this.contentEl.querySelector("#todoModule");
    if (mod) mod.innerHTML = renderTodoModule(todos);
  }

  // 知识库：快速打开（按笔记名/路径过滤 Knowledge/作坊/档案）
  renderKbSearch(q) {
    const box = this.contentEl.querySelector("#kbSearchResults");
    if (!box) return;
    q = (q || "").trim().toLowerCase();
    if (!q) { box.innerHTML = ""; return; }
    const results = this.app.vault.getMarkdownFiles()
      .filter((f) => /^(Knowledge|作坊|档案)\//.test(f.path) && f.path.toLowerCase().includes(q))
      .sort((a, b) => (a.path < b.path ? -1 : 1))
      .slice(0, 8);
    box.innerHTML = results.length
      ? results.map((f) =>
          '<div class="row" data-open="' + esc(f.path) + '">' +
          '<span class="rt" title="' + esc(f.path) + '">' + esc(f.name.replace(/\.md$/, "")) + '</span>' +
          '<span class="rm"><span class="gcnt">' + esc(f.parent ? f.parent.name : "") + '</span><span class="arr">' + ICONS.arrow + '</span></span></div>'
        ).join("")
      : '<div class="empty">无匹配笔记</div>';
  }

  // 知识库：内容体检（按需扫描 Knowledge/**：无 category / 疑似空笔记）
  async runKnowledgeAudit() {
    if (this._auditing) return;
    this._auditing = true;
    const btn = this.contentEl.querySelector("#kbAuditBtn");
    if (btn) { btn.disabled = true; btn.textContent = "体检中…"; }
    const files = this.app.vault.getMarkdownFiles().filter((f) => f.path.startsWith("Knowledge/"));
    const noCat = [];
    const blank = [];
    for (const f of files) {
      let c = "";
      try { c = await this.app.vault.adapter.read(f.path); } catch (e) { continue; }
      if (!/^category:/m.test(c.slice(0, 600))) noCat.push(f);
      const body = c.replace(/^---\r?\n[\s\S]*?\r?\n---\r?\n?/, "").trim();
      if (body.length < 50) blank.push(f);
    }
    const box = this.contentEl.querySelector("#kbAuditResults");
    if (box) {
      const list = (arr) => arr.slice(0, 15).map((f) =>
        '<div class="row" data-open="' + esc(f.path) + '">' +
        '<span class="rt" title="' + esc(f.path) + '">' + esc(f.name.replace(/\.md$/, "")) + '</span>' +
        '<span class="rm"><span class="arr">' + ICONS.arrow + '</span></span></div>'
      ).join("");
      const more = (arr) => (arr.length > 15 ? '<div class="empty">其余 ' + (arr.length - 15) + ' 篇略</div>' : "");
      box.innerHTML =
        '<div class="kb-audit-sum">共 ' + files.length + ' 篇 · 无 category ' + noCat.length + ' 篇 · 疑似空笔记 ' + blank.length + ' 篇</div>' +
        (noCat.length ? '<div class="todo-sec">无 category（不进侧边栏 / MOC）· ' + noCat.length + '</div>' + list(noCat) + more(noCat) : "") +
        (blank.length ? '<div class="todo-sec">疑似空笔记 · ' + blank.length + '</div>' + list(blank) + more(blank) : "") +
        (!noCat.length && !blank.length ? '<div class="empty">✅ 未发现问题</div>' : "");
    }
    if (btn) { btn.disabled = false; btn.textContent = "重新体检"; }
    this._auditing = false;
  }

  // 知识地图：嵌入原生图谱（唯一引擎，默认全 MOC 范围，芯片点亮时为单分区）；宿主隐藏时拿不到宽度，切到知识库视图时再建
  async buildGraphView() {
    const host = this.contentEl.querySelector("#nativeGraphHost");
    if (!host) return;
    if (host.clientWidth < 60) return;
    try {
      await this.embedNativeGraph(host, this._kbFilter ? kbFilterQuery(this._kbFilter) : GRAPH_SCOPE_QUERY);
    } catch (e) {
      console.error("原生图谱嵌入失败：", e);
      host.innerHTML = '<div class="empty">原生图谱嵌入失败：' + esc(e && e.message ? e.message : "") + '</div>';
    }
  }

  /* 原生图谱嵌入：创建游离 graph Leaf，把其容器嫁接进本视图（DOM 复用，拖拽/缩放/过滤/点击打开全为原生交互）。
     query 缺省 = 全 MOC 范围；芯片过滤时传单分区查询词，查询变化走 Leaf 重建分支（重建后引擎读新 options）。 */
  async embedNativeGraph(host, query) {
    if (!this.plugin) throw new Error("插件未就绪");
    query = query || GRAPH_SCOPE_QUERY;
    await this.plugin.applyGraphOptions(query);
    /* 查询变化或 Leaf 缺失/损坏 → 重建（重建后 onload 自动读 instance.options = 已更新的新值） */
    if (this.plugin.graphLeaf && (this._graphFilterQuery !== query || !this.plugin.graphLeaf.view || this.plugin.graphLeaf.view.getViewType() !== "graph")) {
      try { this.plugin.graphLeaf.detach(); } catch (e) { /* 已分离 */ }
      this.plugin.graphLeaf = null;
    }
    if (!this.plugin.graphLeaf) {
      const leaf = new WorkspaceLeaf(this.app);
      await leaf.setViewState({ type: "graph", state: {} });
      if (!leaf.view || leaf.view.getViewType() !== "graph") throw new Error("graph 视图创建失败");
      this.plugin.graphLeaf = leaf;
      this._graphFilterQuery = query;
    }
    const view = this.plugin.graphLeaf.view;
    const el = view.containerEl;
    if (el.parentElement !== host) host.appendChild(el);
    el.style.height = "100%";
    if (typeof view.onResize === "function") view.onResize();
    /* 复用 Leaf 时的运行时刷新：官方通道 = 引擎 setOptions（分发 filter/color/display/force 各收集器并 render）。
       视图对象（view）上没有 setOptions——v1.10.1 及以前调 view.setOptions 是 undefined 静默失败，
       过滤从未运行时生效过，只有重建 Leaf 才间接生效。 */
    const engine = view.dataEngine;
    if (engine && typeof engine.setOptions === "function") {
      try {
        engine.setOptions({ search: query, colorGroups: this.plugin.lastColorGroups || [] });
      } catch (e) {
        console.error("engine.setOptions 失败（过滤可能未应用）：", e);
      }
    }
  }

  releaseNativeGraph() {
    if (this.plugin) this.plugin.releaseGraphLeaf();
  }

  /* 全部笔记：只重渲染列表内层（形态 + 芯片点亮态 + 过滤词），不动搜索框，焦点与输入得以保留。
     形态切换按钮在列表之外（分区头），故此处必须一并同步其 active 态 —— 否则点了按钮内容已切、
     按钮高亮不动（2026-09-29 实测 bug）。 */
  refreshAllNotesList() {
    const list = this.contentEl.querySelector("#allNotesList");
    if (list && this.data) {
      const form = this._noteForm || "list";
      list.innerHTML = renderNotesForm(this.data, form, this._noteFilter || "", this._noteArea || "", this._mmCollapsed);
      this.contentEl.querySelectorAll("[data-noteform]").forEach((b) => {
        b.classList.toggle("active", b.getAttribute("data-noteform") === form);
      });
      this.wireMindMap();
    }
  }

  /* 全部笔记·思维导图：视口交互（滚轮缩放 / 拖动平移 / 工具条）绑定。
     重渲染会重建 SVG，缩放平移状态随之复位 —— 只有点节点折叠/展开时保留（由 _mmCollapsed 承载）。 */
  wireMindMap() {
    const vp = this.contentEl.querySelector("#mmViewport");
    if (!vp) return;
    const svg = vp.querySelector(".mm-svg");
    if (!svg) return;
    let scale = 1, tx = 0, ty = 0;
    const applyVP = () => svg.setAttribute("style", "transform:translate(" + tx.toFixed(1) + "px," + ty.toFixed(1) + "px) scale(" + scale.toFixed(3) + ")");
    /* 初始视图：横向树的主轴是宽度 —— 只按宽度适配（不放大超过 1），纵向溢出靠拖动 / 滚轮浏览。
       这样文字始终接近 1:1 渲染（可读），而不是把整棵树压到视口里变成一片糊。
       树比视口高时，以根节点（导图枢纽）为垂直锚点定位，避免停在树顶只见分支不见根。 */
    const fit = () => {
      const vw = vp.clientWidth, vh = vp.clientHeight;
      if (!vw || !vh) return;
      const sw = parseFloat(svg.getAttribute("width")) || 1;
      const sh = parseFloat(svg.getAttribute("height")) || 1;
      scale = Math.min(1, vw / (sw + 24));
      if (scale < 0.4) scale = 0.4;   // 极宽兜底：不低于 0.4，其余靠横向拖动
      tx = Math.max(0, (vw - sw * scale) / 2);
      const TOP = 42;                                  // 为右上工具条预留，避免初始视图节点被压住
      const avail = Math.max(60, vh - TOP);
      const scaledH = sh * scale;
      if (scaledH < avail) {
        ty = TOP + (avail - scaledH) / 2;              // 整图可容纳 → 预留区下方居中
      } else {
        const anchor = (parseFloat(vp.getAttribute("data-mmanchor")) || 0) * scale;
        ty = Math.min(TOP, Math.max(vh - scaledH, TOP + avail / 2 - anchor)); // 根节点对齐预留区中心
      }
      applyVP();
    };
    this._mmFit = fit;
    fit();
    // 滚轮缩放（以光标为中心）
    vp.addEventListener("wheel", (e) => {
      e.preventDefault();
      const rect = vp.getBoundingClientRect();
      const mx = e.clientX - rect.left, my = e.clientY - rect.top;
      const next = Math.min(3, Math.max(0.15, scale * (e.deltaY < 0 ? 1.12 : 1 / 1.12)));
      const k = next / scale;
      tx = mx - (mx - tx) * k;
      ty = my - (my - ty) * k;
      scale = next;
      applyVP();
    }, { passive: false });
    /* 拖动平移 + 点击判定。
       坑（2026-09-29 实测）：`setPointerCapture` 会把后续 click 的 target 改写成视口本身，
       `closest("[data-open]")` 再也匹配不到节点 → **真实鼠标点击打不开笔记**（仅程序化 dispatch 能过）。
       故不依赖 click，改在 pointerup 按位移判定：位移 < 阈值 = 点击，按命中节点打开笔记 / 折叠分支；
       否则视为拖动平移。命中用坐标反查（elementFromPoint），不受 capture 改写 target 影响。 */
    let dragging = false, moved = false, sx = 0, sy = 0, ox = 0, oy = 0, downTarget = null;
    const DRAG_TOL = 5; // px，位移小于此值算点击
    vp.addEventListener("pointerdown", (e) => {
      if (e.button !== 0) return;
      dragging = true; moved = false; sx = e.clientX; sy = e.clientY; ox = tx; oy = ty;
      downTarget = e.target instanceof Element ? e.target : null;
      vp.classList.add("dragging");
      try { vp.setPointerCapture(e.pointerId); } catch (err) { /* 旧环境无指针捕获 */ }
    });
    vp.addEventListener("pointermove", (e) => {
      if (!dragging) return;
      if (Math.abs(e.clientX - sx) > DRAG_TOL || Math.abs(e.clientY - sy) > DRAG_TOL) moved = true;
      tx = ox + (e.clientX - sx);
      ty = oy + (e.clientY - sy);
      applyVP();
    });
    const endDrag = (e) => {
      if (!dragging) return;
      dragging = false;
      vp.classList.remove("dragging");
      if (moved) return;                       // 拖动过 → 不触发点击
      // 点击：优先用按下时的 target，其次用坐标反查（capture 改写 target 时的兜底）
      let el = downTarget;
      if (!(el instanceof Element) || !vp.contains(el)) {
        el = document.elementFromPoint(e.clientX, e.clientY);
      }
      if (!(el instanceof Element)) return;
      const noteNode = el.closest("[data-open]");
      if (noteNode && vp.contains(noteNode)) { this.openPath(noteNode.getAttribute("data-open")); return; }
      const toggleNode = el.closest("[data-mmtoggle]");
      if (toggleNode && vp.contains(toggleNode)) {
        const key = toggleNode.getAttribute("data-mmtoggle") || "";
        if (!(this._mmCollapsed instanceof Set)) {
          const notes = (this.data && this.data.knowledgeNotes) || [];
          const visible = notesVisible(notes, this._noteFilter || "", this._noteArea || "");
          this._mmCollapsed = mmDefaultCollapsed(buildMindTree(visible, noteAreas(notes)), visible.length, false);
        }
        if (this._mmCollapsed.has(key)) this._mmCollapsed.delete(key);
        else this._mmCollapsed.add(key);
        this.refreshAllNotesList();
      }
    };
    vp.addEventListener("pointerup", endDrag);
    vp.addEventListener("pointercancel", endDrag);
    // 工具条：展开全部 / 收起分支（只留主类与末级）/ 重置视图
    const wrap = vp.parentElement;
    if (wrap) {
      wrap.querySelectorAll("[data-mmtool]").forEach((btn) => {
        btn.addEventListener("click", () => {
          const act = btn.getAttribute("data-mmtool");
          if (act === "reset") { fit(); return; }
          if (act === "expand") this._mmCollapsed = new Set();
          if (act === "collapse") {
            const notes = (this.data && this.data.knowledgeNotes) || [];
            const visible = notesVisible(notes, this._noteFilter || "", this._noteArea || "");
            const tree = buildMindTree(visible, noteAreas(notes));
            this._mmCollapsed = mmDefaultCollapsed(tree, visible.length, true);
          }
          this.refreshAllNotesList();
        });
      });
    }
  }

  /* 知识地图芯片：点亮/熄灭分区过滤（点同芯片恢复全图；跨视图重渲染时 _kbFilter 保持点亮态） */
  async toggleKbFilter(path) {
    const next = this._kbFilter === path ? null : path;
    this._kbFilter = next;
    this.contentEl.querySelectorAll(".kbstat[data-kbfilter]").forEach((el) => {
      el.classList.toggle("active", el.getAttribute("data-kbfilter") === next);
    });
    await this.applyGraphFilter(next ? kbFilterQuery(path) : GRAPH_SCOPE_QUERY);
  }

  /* 图谱过滤热切换：权威通道先写 instance.options（同 applyGraphOptions），运行时再 engine.setOptions 免重建；
     引擎不可用才走 embedNativeGraph 重建分支。不改动 colorGroups 生成逻辑，配色保持原样。 */
  async applyGraphFilter(query) {
    if (!this.plugin) return;
    try { await this.plugin.applyGraphOptions(query); } catch (e) { /* graph.json 写不进则仅本次会话生效 */ }
    const view = this.plugin.graphLeaf && this.plugin.graphLeaf.view;
    const engine = view && view.dataEngine;
    if (engine && typeof engine.setOptions === "function") {
      try { engine.setOptions({ search: query, colorGroups: this.plugin.lastColorGroups || [] }); } catch (e) {
        console.error("engine.setOptions 失败（过滤可能未应用）：", e);
      }
      this._graphFilterQuery = query; /* 与 embedNativeGraph 的重建判定保持一致 */
    } else {
      const host = this.contentEl.querySelector("#nativeGraphHost");
      if (host && host.clientWidth >= 60) {
        try { await this.embedNativeGraph(host, query); } catch (e) { console.error("图谱过滤切换失败：", e); }
      }
    }
  }

  // 点击待办行 → 编辑小窗
  openTodoModal(id) {
    if (!this.plugin) return;
    const todo = this.plugin.todoData.todos.find((x) => x.id === id);
    if (!todo) return;
    new TodoEditModal(this.plugin, todo).open();
  }

  async render() {
    const data = await scan(this.app);
    this.data = data;
    const savedView = localStorage.getItem("kw_view");
    if (!this._noteForm) {
      let savedForm = "";
      try { savedForm = localStorage.getItem("kw_noteform") || ""; } catch (e) { /* 受限环境忽略 */ }
      this._noteForm = savedForm === "map" ? "map" : "list";
    }
    this.contentEl.innerHTML = buildHtml(data, savedView, this.plugin ? this.plugin.todoData.todos : [], this._kbFilter, this._noteArea, this._noteForm, this._mmCollapsed, this._diaryYear);
    this.applyTheme();
    this.buildGraphView();
    this.wireMindMap();
    // 全部笔记视图：重渲染后恢复上次的过滤词（芯片点亮态由 buildHtml → renderNotesForm 读取 _noteArea）
    if (savedView === "notes" && this._noteFilter) {
      const input = this.contentEl.querySelector("#notesSearch");
      if (input) input.value = this._noteFilter;
      this.refreshAllNotesList();
    }
  }
}

/* ============================ Todo 编辑小窗 ============================ */

class TodoEditModal extends Modal {
  constructor(plugin, todo) {
    super(plugin.app);
    this.plugin = plugin;
    this.todo = todo;
  }

  onOpen() {
    const t = this.todo;
    this.modalEl.addClass("kw-todo-modal");
    this.modalEl.style.maxWidth = "620px";
    const c = this.contentEl;
    c.createEl("h3", { text: "编辑待办" });
    const form = c.createDiv("kw-form");

    const field = (parent, label) => {
      const f = parent.createDiv("kw-field");
      f.createEl("span", { text: label });
      return f;
    };

    const fTitle = field(form, "标题（待办事项）");
    const title = fTitle.createEl("input", { type: "text" });
    title.value = t.title || "";
    title.placeholder = "待办标题";

    const fNotes = field(form, "内容或计划");
    const notes = fNotes.createEl("textarea");
    notes.value = t.notes || "";
    notes.placeholder = "补充说明、计划步骤…";

    const grid = form.createDiv("kw-grid");
    const fPr = field(grid, "优先级");
    const pr = fPr.createEl("select");
    TODO_PRIORITIES.forEach((p) => {
      const o = pr.createEl("option", { text: p.label });
      o.value = p.key;
    });
    pr.value = t.priority || "";

    const fCat = field(grid, "分类");
    const cat = fCat.createEl("select");
    TODO_CATEGORIES.forEach((x) => {
      const o = cat.createEl("option", { text: x.label || "无" });
      o.value = x.key;
    });
    cat.value = t.category || "";

    const fDue = field(grid, "截止日期");
    const due = fDue.createEl("input", { type: "date" });
    due.value = t.due || "";

    const fTime = field(grid, "时间");
    const time = fTime.createEl("input", { type: "time" });
    time.value = t.time || "";

    const foot = form.createDiv("kw-foot");
    const save = foot.createEl("button", { text: "保存" });
    save.addClass("mod-cta");
    const cancel = foot.createEl("button", { text: "取消" });
    foot.createDiv("spacer");
    const confirmWrap = foot.createDiv("kw-confirm");
    confirmWrap.style.display = "none";
    const del = foot.createEl("button", { text: "删除" });
    del.addClass("mod-warning");

    const saveAndClose = async () => {
      const titleVal = title.value.trim();
      if (!titleVal) { new Notice("标题不能为空"); return; }
      await this.plugin.updateTodo(t.id, {
        title: titleVal,
        notes: notes.value.trim(),
        priority: pr.value,
        category: cat.value,
        due: due.value || null,
        time: time.value || null,
      });
      this.close();
    };

    save.addEventListener("click", saveAndClose);
    title.addEventListener("keydown", (e) => { if (e.key === "Enter") saveAndClose(); });
    cancel.addEventListener("click", () => this.close());

    // 两步确认删除，避免误删
    del.addEventListener("click", () => {
      del.style.display = "none";
      confirmWrap.style.display = "";
      confirmWrap.empty();
      confirmWrap.createEl("span", { text: "确认删除该待办？" });
      const yes = confirmWrap.createEl("button", { text: "确认删除" });
      yes.addClass("mod-warning");
      const no = confirmWrap.createEl("button", { text: "保留" });
      yes.addEventListener("click", async () => {
        await this.plugin.deleteTodo(t.id);
        this.close();
      });
      no.addEventListener("click", () => {
        confirmWrap.style.display = "none";
        del.style.display = "";
      });
    });
  }

  onClose() {
    this.contentEl.empty();
  }
}

/* ============================ 插件 ============================ */

class KnowledgeWorkspacePlugin extends Plugin {
  async onload() {
    this.graphLeaf = null;
    // 个人待办数据存插件 data.json（用户 2026-09-26 裁定：插件记录，不新建待办 md 文件）
    const saved = await this.loadData();
    this.todoData = { todos: saved && Array.isArray(saved.todos) ? saved.todos.map(normalizeTodo) : [] };
    this.registerView(VIEW_TYPE, (leaf) => new KnowledgeWorkspaceView(leaf, this));

    this.addRibbonIcon("layout-dashboard", "打开知识工作台", () => this.activateView());
    this.addCommand({
      id: "open-workspace",
      name: "打开知识工作台",
      callback: () => this.activateView(),
    });

    // 首页：启动时若尚无工作台视图，则自动打开并聚焦
    this.app.workspace.onLayoutReady(() => {
      if (this.app.workspace.getLeavesOfType(VIEW_TYPE).length === 0) {
        this.activateView();
      }
    });

    // 数据实时联动：vault 文件变动后防抖刷新
    const refresh = () => this.scheduleRefresh();
    this.registerEvent(this.app.vault.on("modify", refresh));
    this.registerEvent(this.app.vault.on("create", refresh));
    this.registerEvent(this.app.vault.on("delete", refresh));
    this.registerEvent(this.app.vault.on("rename", refresh));
  }

  /* 图谱选项写入（权威通道，asar 实证）：
     vault.setConfig("graph") 只改内存 config，vault.saveConfig 只落盘 app/appearance 两文件——
     写 graph 配置用它根本不会进 graph.json（v1.10.1 重启后旧值复现的根因）。
     graph.json 的权威读写 = 图谱核心插件 instance.options + instance.saveOptions()（saveData→writeConfigJson("graph")）。
     视图 onload 时用 instance.options 初始化引擎——先更新实例选项再建/重建 Leaf，新值自然生效。 */
  async applyGraphOptions(query) {
    if (!this.app) return;
    const graphManager = this.app.internalPlugins && this.app.internalPlugins.getPluginById("graph");
    const inst = graphManager && graphManager.instance;
    if (!inst || typeof inst.saveOptions !== "function") return;
    /* 备份用户原值（释放时还原，不污染独立图谱页） */
    if (this._graphPrevSearch === undefined) this._graphPrevSearch = typeof inst.options.search === "string" ? inst.options.search : "";
    if (this._graphPrevColorGroups === undefined) this._graphPrevColorGroups = Array.isArray(inst.options.colorGroups) ? inst.options.colorGroups : [];
    /* 自动分组着色：按 Knowledge 二级目录 + 作坊/档案 生成原生 colorGroups */
    const groups = [];
    const dirs = new Set();
    if (typeof this.app.vault.getMarkdownFiles === "function") {
      for (const f of this.app.vault.getMarkdownFiles()) {
        if (f.path.startsWith("Knowledge/")) {
          const parts = f.path.split("/");
          if (parts.length >= 3) dirs.add("Knowledge/" + parts[1]);
        } else if (f.path.startsWith("作坊/")) dirs.add("作坊");
        else if (f.path.startsWith("档案/")) dirs.add("档案");
      }
    }
    if (dirs.size) {
      const PALETTE = [0xe05252, 0x52a8e0, 0x7bd86b, 0xd86bd8, 0xe0a852, 0x52d8d0, 0xb0b0b0];
      for (const d of [...dirs].sort()) {
        groups.push({ query: 'path:"' + d + '"', color: { a: 1, rgb: PALETTE[groups.length % PALETTE.length] } });
      }
    }
    this.lastColorGroups = groups;
    this._graphLastSearch = query; /* 记录本插件最后写入的过滤词，供 releaseGraphLeaf 还原守卫识别（含芯片动态查询） */
    const changedSearch = inst.options.search !== query;
    const changedColor = JSON.stringify(inst.options.colorGroups) !== JSON.stringify(groups);
    if (!changedSearch && !changedColor) return;
    inst.options = Object.assign({}, inst.options, { search: query, colorGroups: groups });
    inst.saveOptions(); /* → .obsidian/graph.json 落盘 */
  }

  /* 释放嵌入图谱 Leaf，并把图谱的过滤与颜色分组恢复为用户原值（不污染独立图谱页） */
  releaseGraphLeaf() {
    if (!this.app) return;
    if (this.graphLeaf) {
      const leaf = this.graphLeaf;
      this.graphLeaf = null;
      try { leaf.detach(); } catch (e) { /* 已分离 */ }
    }
    const needSearch = this._graphPrevSearch !== undefined;
    const needColor = this._graphPrevColorGroups !== undefined;
    if (!needSearch && !needColor) return;
    try {
      const graphManager = this.app.internalPlugins && this.app.internalPlugins.getPluginById("graph");
      const inst = graphManager && graphManager.instance;
      if (inst && typeof inst.saveOptions === "function") {
        let dirty = false;
        const opts = Object.assign({}, inst.options);
        if (needSearch && (opts.search === 'file:"MOC"' || opts.search === 'path:"Knowledge"' || opts.search === GRAPH_SCOPE_QUERY || opts.search === this._graphLastSearch)) {
          opts.search = this._graphPrevSearch;
          dirty = true;
        }
        if (needColor && Array.isArray(opts.colorGroups) && opts.colorGroups.some((g) => g && g.query === 'path:"Knowledge/AI"')) {
          opts.colorGroups = this._graphPrevColorGroups;
          dirty = true;
        }
        if (dirty) {
          inst.options = opts;
          inst.saveOptions();
        }
      }
    } catch (e) { /* 配置不可写则跳过 */ }
    this._graphPrevSearch = undefined;
    this._graphPrevColorGroups = undefined;
  }

  onunload() {
    /* 释放嵌入的原生图谱 Leaf（其容器嫁接在工作台视图内，视图销毁前先分离），并恢复图谱过滤 */
    this.releaseGraphLeaf();
    this.app.workspace.getLeavesOfType(VIEW_TYPE).forEach((leaf) => leaf.detach());
  }

  async activateView() {
    const { workspace } = this.app;
    let leaf = workspace.getLeavesOfType(VIEW_TYPE)[0];
    if (!leaf) {
      leaf = workspace.getLeaf("tab");
      await leaf.setViewState({ type: VIEW_TYPE, active: true });
    }
    workspace.revealLeaf(leaf);
  }

  /* ---------- Todo 数据（个人待办，持久化到插件 data.json） ---------- */

  async persistTodos() {
    await this.saveData({ todos: this.todoData.todos });
    this.refreshTodoViews();
  }

  // 只重渲染 Todo 区块，不写盘（用于未修改也退出编辑态等场景）
  refreshTodoViews() {
    this.app.workspace.getLeavesOfType(VIEW_TYPE).forEach((leaf) => {
      if (leaf.view instanceof KnowledgeWorkspaceView) leaf.view.refreshTodoUI();
    });
  }

  async addTodo(raw) {
    const p = parseTodoInput(raw);
    if (!p.text) return false;
    this.todoData.todos.push(normalizeTodo({ id: newTodoId(), title: p.text, due: p.due, time: p.time, done: false }));
    await this.persistTodos();
    return true;
  }

  async toggleTodo(id) {
    const t = this.todoData.todos.find((x) => x.id === id);
    if (!t) return;
    t.done = !t.done;
    await this.persistTodos();
  }

  async deleteTodo(id) {
    const i = this.todoData.todos.findIndex((x) => x.id === id);
    if (i >= 0) {
      this.todoData.todos.splice(i, 1);
      await this.persistTodos();
    }
  }

  async updateTodo(id, patch) {
    const t = this.todoData.todos.find((x) => x.id === id);
    if (!t) return false;
    Object.assign(t, patch);
    await this.persistTodos();
    return true;
  }

  async clearDone() {
    const n = this.todoData.todos.filter((t) => t.done).length;
    if (!n) return;
    this.todoData.todos = this.todoData.todos.filter((t) => !t.done);
    await this.persistTodos();
    new Notice("已清除 " + n + " 条已完成待办");
  }

  scheduleRefresh() {
    if (this._t) clearTimeout(this._t);
    this._t = setTimeout(() => {
      this.app.workspace.getLeavesOfType(VIEW_TYPE).forEach((leaf) => {
        const view = leaf.view;
        if (view instanceof KnowledgeWorkspaceView) view.render();
      });
    }, 400);
  }
}

module.exports = KnowledgeWorkspacePlugin;

// 导出纯函数供离线自测（Obsidian 运行时忽略这些附加属性）
KnowledgeWorkspacePlugin.scan = scan;
KnowledgeWorkspacePlugin.buildHtml = buildHtml;
KnowledgeWorkspacePlugin.handleDomClick = handleDomClick;
KnowledgeWorkspacePlugin.parseTodoInput = parseTodoInput;
KnowledgeWorkspacePlugin.renderTodoModule = renderTodoModule;
KnowledgeWorkspacePlugin.localToday = localToday;
KnowledgeWorkspacePlugin.normalizeTodo = normalizeTodo;
KnowledgeWorkspacePlugin.renderKbMap = renderKbMap;
KnowledgeWorkspacePlugin.renderAllNotes = renderAllNotes;
KnowledgeWorkspacePlugin.renderRecent = renderRecent;
KnowledgeWorkspacePlugin.renderHeat = renderHeat;
KnowledgeWorkspacePlugin.renderNotesForm = renderNotesForm;
KnowledgeWorkspacePlugin.renderMindMap = renderMindMap;
KnowledgeWorkspacePlugin.buildMindTree = buildMindTree;
KnowledgeWorkspacePlugin.layoutMindTree = layoutMindTree;
KnowledgeWorkspacePlugin.mmTextWidth = mmTextWidth;
KnowledgeWorkspacePlugin.mmKey = mmKey;
KnowledgeWorkspacePlugin.mmDefaultCollapsed = mmDefaultCollapsed;
KnowledgeWorkspacePlugin.noteAreas = noteAreas;
KnowledgeWorkspacePlugin.notesVisible = notesVisible;
KnowledgeWorkspacePlugin.areaLabel = areaLabel;
KnowledgeWorkspacePlugin.diaryPreview = diaryPreview;
KnowledgeWorkspacePlugin.diaryWeekday = diaryWeekday;
KnowledgeWorkspacePlugin.renderDiary = renderDiary;
KnowledgeWorkspacePlugin.renderDiaryStats = renderDiaryStats;
KnowledgeWorkspacePlugin.renderDiaryList = renderDiaryList;
KnowledgeWorkspacePlugin.View = KnowledgeWorkspaceView;
