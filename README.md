# agent-skills-hub

> 通用 Agent 技能仓库 —— 单一副本、多 agent 共享、团队/本地双轨、组合可切换、跨平台脚本化管理。

主机上装了 Claude Code、Codex、Cursor、Grok、Gemini…… 每个 agent 都要一份技能副本？
本仓库把所有技能收敛成**唯一一份**，通过链接分发给每个 agent，一处修改，处处生效。

```
仓库 (source of truth)          规范 hub (唯一副本)         各 agent
skills/team|local/<cat>/<skill>  ──►  ~/.agents/skills/<skill>  ──►  ~/.claude/skills/<skill>
                                                              ├──►  ~/.codex/skills/<skill>
                                                              ├──►  ~/.cursor/skills/<skill>
                                                              └──►  …（软链，非拷贝）
```

N 个 agent 共享 1 份技能文件，磁盘上不再有多份副本。

---

## 快速开始

```bash
git clone https://github.com/<you>/agent-skills-hub.git
cd agent-skills-hub

# macOS / Linux
./bin/skills-hub install            # 建立规范 hub 并自动接入本机已装的 agent

# Windows (PowerShell)
.\bin\skills-hub.ps1 install
# Windows (CMD)
bin\skills-hub.cmd install
```

装完后把 `bin/` 加进 PATH，就能在任何地方直接 `skills-hub <命令>`。

**依赖**：只需 Python 3.9+，零第三方库。软链不可用时（如未开发者模式的 Windows）自动回退到目录联结 / 复制。

---

## 核心概念

### 三层路径

| 层 | 位置 | 作用 |
|---|---|---|
| 仓库 | `skills/team|local/<分类>/<技能>/` | 技能的唯一事实来源，进 git |
| 规范 hub | `~/.agents/skills/`（可用 `SKILLS_HUB_HOME` 改） | 主机上技能的唯一落地路径 |
| agent 目录 | `~/.claude/skills`、`~/.codex/skills`… | 指向 hub 的链接，各 agent 各自读取 |

> `~/.agents/skills` 是 `npx skills`（vercel-labs/skills）生态的公认约定路径，Cline / Amp / Zed / Warp 等直接读它，无需再建链。

### 团队 / 本地双轨

| 作用域 | 位置 | 进 git？ | 谁能同步 |
|---|---|---|---|
| **team** | `skills/team/` | ✅ | 所有成员 `sync` 拉取 |
| **local** | `skills/local/` | ❌（.gitignore） | 只属于你，不上传 |

同名时 **local 覆盖 team** —— 可在本地临时改写团队技能而不影响别人。打磨好了用 `promote` 提升为 team 技能，走校验 + PR 后共享。

### 技能组合（profile）

不同项目/场合需要不同的技能组合。profile 就是「一组启用哪些技能」的命名快照，一条命令切换：

```bash
skills-hub profile use reverse      # 逆向分析场景
skills-hub profile use frontend     # 前端项目
skills-hub profile use review       # 只做代码审核，不加载实现类技能
```

切换会重建 hub 并刷新所有已接入 agent。内置组合：

<!-- PROFILES:BEGIN -->
| 组合 | 技能数 | 内容 |
|---|---|---|
| `backend-python` | 9 | Python 服务端与自动化脚本开发，含安全审核。 |
| `base` | 4 | 任何场景都应常驻的技能：需求澄清 + Agent 记忆与上下文管理。其它组合通过 extends 继承本层。 |
| `default` | 9 | 日常开发默认组合：需求整理、项目理解、记忆与上下文、代码安全审核。不含前端/逆向等重型技能。 |
| `documents` | 8 | 处理 Word/Excel/PPT/PDF 等办公文档时启用，叠加基础层。 |
| `frontend` | 13 | 前端 / 桌面端开发：界面实现 + 视觉验证测试 + 需求与项目理解。 |
| `minimal` | 2 | 只保留记忆与上下文管理，适合上下文紧张的长会话或小改动。 |
| `reverse` | 9 | 客户端/协议逆向与取证分析：逆向流程、脚本开发、安全审核，不加载前端与需求类技能以省上下文。 |
| `review` | 7 | 只做代码审核与验证：漏洞审核 + 视觉验证 + 项目理解，不加载实现类技能，避免 agent 顺手改代码。 |
| `workflow` | 12 | 常驻的通用工作方法：头脑风暴、TDD、系统化调试、写技能。适合叠加在任何开发场景之上。 |
| `all` | 30 | 仓库全部技能（内置组合） |
<!-- PROFILES:END -->

自定义：`skills-hub profile create mine --categories backend,quality --skills agent-memory`

---

## 技能清单

> 本节由 `skills-hub readme --sync` 从实时数据生成，请勿手改标记之间的内容。
> 增删技能后跑一次即可；CI 用 `skills-hub readme --check` 拦住忘记同步的 PR。

<!-- SKILLS:BEGIN -->
共 **30 个**技能：**12 个原创**（内容在本仓库） + **18 个索引**（指针在仓库，内容 sync 时下载）。
用 `skills-hub list` 查看实时状态，`skills-hub list --category <分类>` 按分类筛选。

#### 需求整理 `requirements`
| 技能 | 归属 | 用途 |
|---|---|---|
| `requirement-analysis` | 原创 | 把 PRD / MRD / 立项文档翻译成研发能落地的流程图、架构图与实施难点 |

#### 功能梳理与项目理解 `analysis`
| 技能 | 归属 | 用途 |
|---|---|---|
| `feature-mapping` | 原创 | 深挖单条功能链路：入口→数据流→出口，给出影响面清单 |
| `project-onboarding` | 原创 | 陌生仓库快速上手：结构、技术栈、数据流、新功能该加在哪 |

#### 前端开发 `frontend`
| 技能 | 归属 | 用途 |
|---|---|---|
| `frontend-development` | 原创 | 前端/桌面端实现规范：先复用后新建、状态选型、可访问性、自测清单 |
| `frontend-design` | 索引 · anthropic | 有辨识度的界面视觉设计指导 |
| `shadcn` | 索引 · shadcn/ui | shadcn 组件的增删查改、样式与组合、Radix→Base UI 迁移 |

#### 后端开发 `backend`
| 技能 | 归属 | 用途 |
|---|---|---|
| `python-backend` | 原创 | Python 服务端：接口分层、同步/异步选型、DB、密钥、日志 |
| `reverse-engineering` | 原创 | 授权场景下的逆向：静态+动态、Frida、抓包、加固对抗 |
| `script-development` | 原创 | 自动化脚本：参数化、幂等、dry-run、破坏性操作保护 |
| `mcp-builder` | 索引 · anthropic | 构建高质量 MCP 服务端 |

#### 质量与安全 `quality`
| 技能 | 归属 | 用途 |
|---|---|---|
| `security-audit` | 原创 | 漏洞审核：注入/越权/密钥/SSRF/反序列化，产出定位到行的清单 |
| `visual-verification` | 原创 | 界面改动的截图验证：多视口/主题/状态矩阵、前后对比 |
| `verification-before-completion` | 索引 · superpowers | 宣称「完成」前必须先跑验证并确认输出 |
| `webapp-testing` | 索引 · anthropic | 用 Playwright 驱动真实浏览器测试本地 Web 应用 |

#### Agent 记忆与上下文 `agent-ops`
| 技能 | 归属 | 用途 |
|---|---|---|
| `agent-memory` | 原创 | 长期记忆：什么值得记、怎么存、召回时如何判断可信度 |
| `context-management` | 原创 | 上下文预算：分层加载、外置中间结果、子任务隔离、交接固化 |

#### 研发流程与方法论 `workflow`
| 技能 | 归属 | 用途 |
|---|---|---|
| `brainstorming` | 索引 · superpowers | 创造性工作动手前先探索意图与设计 |
| `dispatching-parallel-agents` | 索引 · superpowers | 独立任务并行拆分给子 agent |
| `executing-plans` | 索引 · superpowers | 按已写好的方案分阶段执行、带评审点 |
| `skill-creator` | 索引 · anthropic | 官方技能创作/优化/评测指南（new 命令默认参考） |
| `systematic-debugging` | 索引 · superpowers | 提修复方案前先做系统化根因定位 |
| `test-driven-development` | 索引 · superpowers | 红-绿-重构，先写测试再写实现 |
| `using-git-worktrees` | 索引 · superpowers | 用 worktree 隔离工作区 |
| `writing-plans` | 索引 · superpowers | 多步任务动代码前先写方案 |
| `writing-skills` | 索引 · superpowers | 把 TDD 思路套用到技能文档编写 |

#### 文档处理 `documents`
| 技能 | 归属 | 用途 |
|---|---|---|
| `docx` | 索引 · anthropic | Word 文档读取、生成、编辑 |
| `pdf` | 索引 · anthropic | PDF 解析、提取、表单处理 |
| `pptx` | 索引 · anthropic | PPT 幻灯片生成与编辑 |
| `xlsx` | 索引 · anthropic | Excel 表格与数据处理 |

#### 知识与学习 `knowledge`
| 技能 | 归属 | 用途 |
|---|---|---|
| `study-notes` | 原创 | 读书/学习笔记的校对、答疑与分级总结 |

> **原创** = 内容在本仓库 `skills/team/`，本仓库即其来源。  
> **索引** = 只在 `registry/manifest.json` 存指针，`sync` 时从上游下载最新版，不占仓库体积。
<!-- SKILLS:END -->

---

## 统一搜索与获取技能

一个入口找技能，**分层、分区展示**，来源一目了然：

```bash
skills-hub search "react form"
```

搜索顺序（前面命中就不惊动后面）：

```
【仓库】     本地仓库里已有的技能
   ↓ 没有
【已登记源】 已缓存的外部源（superpowers / anthropic / vercel / shadcn…）里的技能，可直接导入
   ↓ 没有
【网络】     结构化优先：用已认证的 gh 搜 GitHub，结果带 owner/repo:path，可直接导入
   ↓ 结构化也没有
【网络·通用兜底】 给出 skills.sh / SkillsMP / GitHub 搜索入口链接
```

### 两条获取路径，分工明确

| 你要做的 | 用哪个命令 | 落地方式 |
|---|---|---|
| **从零创作**一个新技能 | `skills-hub new <名> --category <分类>` | 作为**内容**写进仓库（原创技能以本仓库为家），默认走 **skill-creator** 方法论 |
| **索引**一个在线已有技能 | `skills-hub add <ref> --category <分类>` | 只往索引 `manifest.json` 写一条**指针**，内容 sync 时才下载到缓存 |

`add` 的 `<ref>` 支持三种写法：

```bash
skills-hub add superpowers:systematic-debugging --category workflow   # 从已登记源
skills-hub add owner/repo --category backend                          # 整仓（自动找 SKILL.md）
skills-hub add owner/repo:path/to/skill --category backend            # 仓库内指定技能
skills-hub add superpowers:brainstorming --ref-version v6.1.0 ...     # 锁定版本，缺省取最新
```

---

## 索引模型：仓库存指针，技能按需下载

**外部技能不进仓库**，仓库里只有一份索引 `registry/manifest.json`（每条几行 JSON）。
这样做的理由：

- **仓库不膨胀**：技能再多，仓库里也只是指针；内容躺在缓存 `~/.agents/.hub-cache`（不进 git）。
- **永远拿最新**：`sync` 从在线源下载，`update` 一键拉取上游更新——在线版才是最新版。
- **配置即状态**：改 `manifest.json`（或用 `add`/`uninstall`）就是安装/卸载/换版本，改完 `sync` 生效。
- **索引自描述**：每条指针都带 `description` 与 `tags`（用途与应用范围），**不下载也能看懂
  这技能干嘛、用在哪**；`add` 时会自动从技能的 frontmatter 回填，也可用 `--description`/`--tags` 覆盖。

```jsonc
// registry/manifest.json 里的一条指针
"systematic-debugging": {
  "source": "superpowers",          // 来自哪个源
  "category": "workflow",           // 归入的分类
  "ref": "main",                    // 版本；缺省取最新
  "description": "遇到 bug、测试失败时，先做系统化根因定位再改",  // 不下载也看得懂
  "tags": ["调试", "排障", "根因分析", "测试"]                    // 应用范围
}
```

```
索引 manifest.json ──sync──▶ 下载到缓存 ~/.agents/.hub-cache ──▶ 链接进 hub ──▶ 各 agent
   (进 git, 几行指针)          (不进 git, 随时可删可重建)
```

| 命令 | 作用 |
|---|---|
| `skills-hub add <ref> --category <分类>` | 加一条索引并立即下载 |
| `skills-hub sync` | 按索引下载所有外部技能 + 重建链接（团队成员拉到最新索引后一步到位） |
| `skills-hub sync --update` / `skills-hub update [名…]` | 把索引技能更新到在线最新 |
| `skills-hub uninstall <名> [--purge]` | 从索引移除并解链（`--purge` 连缓存一起删） |

> **原创 vs 索引**：你用 `new` 写的、线上不存在的技能，作为内容留在仓库 `skills/team|local/`
> （它们以本仓库为唯一来源，本身就是「最新」）；从社区来的技能一律走索引，不占仓库体积。
> `list` / `status` 会用 `[team]` `[local]` `[索引]` 清楚标注每个技能的归属与下载状态。

### 外部源管理

```bash
skills-hub sources list                       # 查看已登记源与缓存状态
skills-hub sources sync [id]                  # 浅克隆/更新源到缓存，供 search 扫描
skills-hub sources add myteam org/skills-repo # 登记自定义源
```

内置源见 [`registry/sources.json`](registry/sources.json)：superpowers、anthropic、vercel、shadcn。
已 vendor 进仓库的第三方技能归属见 [`docs/THIRD_PARTY.md`](docs/THIRD_PARTY.md)。

---

## 命令一览

| 命令 | 作用 |
|---|---|
| `install` | 首次安装：建 hub + 接入本机 agent |
| `sync` | `git pull` + 校验 + 重建所有链接（团队成员日常同步） |
| `search <词>` | 统一搜索：仓库 → 已登记源 → 网络（`--no-net` 只搜本地） |
| `list` / `ls` | 查看技能（`--category` `--scope` `--profile` `--json`） |
| `new <名> --category <分类>` | **从零创作**技能，作为内容进仓库（走 skill-creator，默认 local） |
| `add <ref> --category <分类>` | **索引**在线技能：写指针 + 下载（不进仓库） |
| `update [名…]` | 把索引技能更新到在线最新 |
| `uninstall <名> [--purge]` | 从索引移除并解链 |
| `sources list\|sync\|add\|remove` | 外部源管理 |
| `profile list\|show\|use\|create` | 技能组合管理 |
| `agent list\|link\|unlink` | agent 接入管理 |
| `adopt <路径> --category <分类>` | 收编主机上已有的技能进仓库 |
| `promote <名>` | 把 local 技能提升为 team |
| `validate [名…]` | 校验技能（团队评审门禁，CI 同款） |
| `status` | 当前状态总览 |
| `doctor` | 体检：重复副本、失效链接、可回收缓存 |
| `clean [--apply]` | 清理冗余（默认只预演） |
| `readme --sync` | 从实时数据重新生成 README 的技能清单与组合表（`--check` 供 CI 校验是否过期） |
| `project [路径]` | 在某个项目里挂载技能（`.agents/skills`） |
| `path [--repo]` | 打印 hub / 仓库路径 |

---

## 团队协作流程

```bash
# 成员 A 新建并贡献一个技能
skills-hub new deploy-checklist --category backend --scope local
#   ...编辑 skills/local/backend/deploy-checklist/SKILL.md...
skills-hub validate deploy-checklist        # 本地过校验
skills-hub promote deploy-checklist          # local → team
git add . && git commit -m "feat: deploy-checklist 技能" && git push
#   ...提 PR，CI 跑 skills-hub validate 作为门禁，评审合并...

# 成员 B 同步
skills-hub sync                              # git pull + 校验 + 重建链接，立即获得新技能
```

CI 门禁示例见 [`docs/ci-example.yml`](docs/ci-example.yml)。

---

## 收编与清理现有环境

一条命令把散落在主机各处的技能收编进仓库：

```bash
skills-hub adopt ~/some/path/my-skill --category backend --scope team
```

体检并清理多 agent 环境里的重复副本、失效链接和可再生缓存：

```bash
skills-hub doctor          # 只读扫描，列出重复副本 / 失效链接 / 可回收缓存
skills-hub clean           # 预演将要删除什么
skills-hub clean --apply   # 确认后实际删除
```

> `clean` **绝不**触碰正在使用的插件与技能目录，只回收 `.tmp` 历史备份与可再生的市场缓存，且默认预演。

---

## 技能编写规范

每个技能是一个目录，含一个 `SKILL.md`（可选 `references/` 放按需加载的细节）：

```markdown
---
name: my-skill                 # kebab-case，须与目录名一致
description: 一句话说清「什么场景下触发」——agent 靠它决定是否启用本技能
summary: 简短用途，用于 README 清单等目录场景（缺省则截断 description）
category: backend              # 须在 registry/categories.json 登记
tags: [python, cli]
status: verified               # team 技能须 verified；local 可 draft
---

# 标题
## 何时使用本技能
## 执行流程
## 反面案例
```

`skills-hub validate` 会检查：命名规范、name 与目录一致、description 长度与触发词、分类已登记、正文不泄漏本机绝对路径、引用文件存在等。

---

## 目录结构

```
agent-skills-hub/
├── bin/                    跨平台入口（sh / ps1 / cmd）
├── hub/                    Python 核心引擎（零依赖）
│   ├── cli.py              命令行
│   ├── config.py           三层路径模型
│   ├── agents.py           各 agent 目录注册表
│   ├── registry.py         技能扫描（原创 + 索引）+ frontmatter 解析
│   ├── manifest.py         外部技能索引：按指针下载/更新
│   ├── sources.py          外部源登记与克隆缓存
│   ├── search.py           统一分层搜索（仓库→源→网络）
│   ├── profiles.py         组合解析
│   ├── linker.py           软链/联结/复制分发
│   ├── validate.py         校验门禁
│   ├── scaffold.py         new / adopt / promote
│   └── doctor.py           环境体检与清理
├── registry/
│   ├── categories.json     分类登记
│   ├── sources.json        外部源
│   └── manifest.json       外部技能索引（指针，不含内容）
├── profiles/*.json           技能组合
├── skills/team/<分类>/        团队原创技能（进 git）
├── skills/local/             本地私有技能（不进 git）
└── docs/                     文档
```

---

## 设计说明

- **为什么用链接不用复制**：一处修改处处生效，且省磁盘。复制模式仅作无软链权限时的回退。
- **为什么按技能粒度建链而非整目录替换**：保留各 agent 自带的内置技能（如 Codex 的 `.system`、Grok 的 docx/pptx），不破坏原有环境。
- **为什么零第三方依赖**：跨平台免安装，`clone` 即用。frontmatter 用内置解析器而非 PyYAML。

更多见 [`docs/design.md`](docs/design.md)。
