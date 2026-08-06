---
name: project-onboarding
description: 快速理解并总结一个陌生代码仓库，帮助开发者在新入职或接手新项目时迅速缕清整体结构、技术栈、业务需求、目录职责、功能分块与数据流，并明确「新功能该加在哪里」。当用户说「帮我看看这个项目」「这个仓库是干嘛的」「我刚接手一个项目」「梳理一下项目结构」「这个项目怎么跑起来」「新功能加哪」「项目上手」「onboarding」「读一下这个代码库」，或在一个陌生项目目录中希望快速了解全貌时，使用本技能。即使用户没有点名「skill」，只要意图是理解一个现有项目的结构和逻辑，就应使用本技能。偏向前端 / 桌面端（Electron、Tauri）/ 移动端项目，但同样适用于后端、全栈、CLI 等各类仓库。
---

# Project Onboarding（项目快速上手）

帮助开发者在接手陌生项目时，用最短时间建立准确的「项目心智地图」：技术栈是什么、怎么跑起来、目录各司其职、业务在做什么、数据怎么流动、以及最关键的——**要加新功能时该动哪些文件、遵循什么既有模式**。

最终交付一份结构化的 Markdown 文档，写到项目根目录，文件名 `PROJECT_OVERVIEW.md`（若已存在则改名为 `PROJECT_OVERVIEW_<时间戳>.md`，绝不覆盖用户已有文件）。

---

## 核心工作流

按以下五个阶段推进。**先确定扫描模式**，再逐层分析，最后产出文档。

### 阶段 0：确定扫描模式

本技能有两种模式，开始前要明确用户想要哪一种（若用户已表明则直接用；若未说明，默认走「快速模式」并在文档开头注明，同时告诉用户可以让你切到「深度模式」）：

| 模式 | 适用 | 做什么 | 不做什么 |
|------|------|--------|----------|
| **快速模式（quick）** | 几秒到一两分钟内建立全局认知 | 读元信息、目录树、入口、路由、依赖、README | 不逐个读源码实现 |
| **深度模式（deep）** | 需要真正理解业务逻辑与实现 | 在快速模式基础上，精读关键源码：核心业务模块、状态管理、API 层、IPC/通信层、典型页面实现 | 仍跳过测试、第三方 vendor、构建产物 |

用户表述映射：「快速看一眼」「大概是什么」→ quick；「深入理解」「读懂业务」「我要改这块」→ deep。

### 阶段 1：识别项目类型（自动 + 必要时询问）

**先靠特征文件自动判断，不要上来就问用户。** 扫描根目录及一两层子目录的标志性文件，对照 `references/project-types.md` 判定类型。

快速命令（按需使用）：
```bash
ls -la                                    # 根目录全貌
cat package.json 2>/dev/null              # Node 系核心信息
find . -maxdepth 2 -name "*.config.*" -o -name "Cargo.toml" -o -name "tauri.conf.json" -o -name "pubspec.yaml" 2>/dev/null | grep -v node_modules
```

判定要点（完整对照表见 `references/project-types.md`）：
- `package.json` → Node 生态，再看 `dependencies` 区分框架
- `src-tauri/` + `tauri.conf.json` → **Tauri 桌面应用**
- 依赖含 `electron` / 有主进程入口 → **Electron 桌面应用**
- `capacitor.config.*` / `ionic` / `App.vue` + 移动路由 → **移动端 / 混合应用**
- `next.config.*` / `nuxt.config.*` / `vite.config.*` → 对应 Web 框架
- `Cargo.toml`（无 src-tauri）→ Rust；`pubspec.yaml` → Flutter；`pyproject.toml`/`requirements.txt` → Python；`pom.xml`/`build.gradle` → Java

**只有当自动判断不确定时**（如多技术栈 monorepo、特征冲突、缺少标志文件），才用一句话向用户确认，例如：「这个仓库同时含 `electron` 和 `src-tauri`，主体是 Tauri 桌面应用、Electron 是历史遗留吗？」不要在已能确定时反问。

> 使用者倾向桌面端 / 移动端前端（Electron、Tauri 等），但本技能不局限于此——按实际特征文件判定，别先入为主。

### 阶段 2：分层扫描（宏观 → 微观）

按下面六层逐层建立认知。**快速模式只做第 1–4 层的结构性扫描；深度模式追加第 5–6 层的源码精读。**

**第 1 层 · 元信息**：项目名、技术栈、关键依赖（区分运行时依赖与工具链）、`scripts` 命令（怎么 install / dev / build / test）、Node/语言版本要求。这是「怎么跑起来」的答案。

**第 2 层 · 目录结构**：生成目录树（忽略 `node_modules`、`dist`、`.git`、构建产物），并为每个核心目录标注职责。
```bash
# 推荐：尊重 .gitignore 的目录树
git ls-files 2>/dev/null | head -200    # 若是 git 仓库，这是最干净的文件清单
# 或回退到 find
find . -maxdepth 3 -type d -not -path '*/node_modules/*' -not -path '*/.git/*' -not -path '*/dist/*' 2>/dev/null
```

**第 3 层 · 入口与路由**：从入口文件（`main.*` / `App.*` / `index.*` / `src-tauri/src/main.rs`）追到路由表，缕清「页面/视图 ↔ 文件」的映射。桌面应用要分清主进程入口与渲染进程入口。

**第 4 层 · 业务模块分块**：识别功能分区——状态管理（Pinia/Vuex/Redux/Zustand）、API/请求层、组件库、工具函数、类型定义、常量/配置。说明每块在哪、负责什么。

**第 5 层 · 数据流与通信**（深度模式）：状态如何流转、API 怎么调用、与后端/IPC 如何通信。**桌面应用尤其关键**：Electron 的 `ipcMain`/`ipcRenderer`/`contextBridge`、Tauri 的 `#[tauri::command]`/`invoke`，要讲清前后端边界。

**第 6 层 · 约定与规范**（深度模式）：命名规范、代码风格（ESLint/Prettier 配置）、提交规范、目录组织约定——这些决定了新代码要「长成什么样」才合群。

### 阶段 3：推断业务需求（不要只看代码）

业务逻辑往往不在代码里，而在文档和注释中。**优先读这些来源**，再用代码补全细节：
1. `README.md` / `README_*.md`（含中文 README）—— 通常是业务意图最直接的来源
2. `docs/` 目录、`CHANGELOG.md`、`*.md` 设计文档
3. 路由名 / 页面名 / 目录名（往往直接对应业务模块，如 `views/order`、`pages/dashboard`）
4. 关键模块的文件头注释、JSDoc、类型定义里的语义命名
5. i18n 文案文件（`locales/`、`zh-CN.json`）—— 文案直接暴露产品在做什么

把推断出的业务，用「这个项目是为了解决什么、给谁用、核心功能有哪几块」的形式表达。无法确定的部分明确标注「待与团队确认」，不要编造。

### 阶段 4：生成「新功能落点指南」（本技能的重点产出）

这是使用者最关心的部分。基于前面的分析，针对当前项目类型，给出**「要加一个新功能时的标准动作清单」**：动哪些文件、按什么顺序、遵循什么既有模式。

不同项目类型的落点模式见对应 reference 文件（`references/project-types.md` 末尾「新功能落点指南」分节）。通用骨架：
- 新增一个**页面/视图**：建组件 → 注册路由 → 加菜单/导航入口 → 接数据（store/api）
- 新增一个**接口调用**：在 api 层加方法 → 定义类型 → 在 store/组件中消费
- 新增一个**桌面端原生能力**：Electron 在主进程加 handler + preload 暴露 + 渲染进程调用；Tauri 加 `#[command]` + 在 `invoke_handler` 注册 + 前端 `invoke`
- 新增一个**全局状态**：在 store 加 module/slice → 定义类型 → 组件订阅

要给出**具体到本项目的文件路径示例**（「参照现有的 `src/views/Order/index.vue` 和 `src/api/order.ts` 的写法」），而非泛泛而谈。

### 阶段 5：产出 Markdown 文档

按 `references/output-template.md` 的模板生成 `PROJECT_OVERVIEW.md`，写到**项目根目录**。

**文件已存在处理**：先 `ls PROJECT_OVERVIEW.md`，若存在，新文件命名为 `PROJECT_OVERVIEW_YYYYMMDD_HHMMSS.md`（用 `date +%Y%m%d_%H%M%S` 取时间戳），并在对话中告知用户「检测到已有文档，已另存为 …，未覆盖原文件」。**任何情况下都不覆盖用户已有文件。**

**Mermaid 图**：在文档中嵌入 Mermaid 图让结构更直观（程序员熟悉、GitHub/编辑器可渲染）。至少包含：
- 目录/模块结构图（`graph TD`）
- 路由或页面流转图（视项目而定）
- 深度模式下追加数据流 / IPC 通信时序图（`sequenceDiagram`）

生成后用 `present_files` 把文档呈现给用户（若有该工具），并在对话里给一段 3–5 句的口头摘要（这个项目是什么、怎么跑、最重要的一两个上手提示）。

---

## 关键原则

- **从宏观到微观，永远先给全局再给细节**——使用者要的是「快速缕清」，不是被实现细节淹没。
- **诚实标注不确定性**——推断的业务、猜测的约定，明确写「待确认」，绝不编造。
- **落点指南要具体到本项目文件**——这是与「泛泛的项目介绍」拉开差距的关键。
- **尊重 .gitignore / 忽略噪音**——不要把 `node_modules`、构建产物、lock 文件当成项目结构。
- **快速模式要真的快**——别在快速模式里陷入读源码；该深入时让用户切到深度模式。

---

## 参考文件

- `references/project-types.md` —— 各类项目的特征文件识别对照表 + 每种类型的目录约定与「新功能落点指南」。**阶段 1 判定类型后，读取对应分节。**
- `references/output-template.md` —— `PROJECT_OVERVIEW.md` 的完整输出模板（含 Mermaid 图样例与章节结构）。**阶段 5 生成文档前读取。**
