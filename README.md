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

| 组合 | 内容 |
|---|---|
| `default` | 需求整理 + 项目理解 + 记忆/上下文 + 安全审核 |
| `frontend` | 前端开发 + 视觉验证 + 需求/理解 |
| `backend-python` | Python 后端 + 脚本开发 + 安全审核 |
| `reverse` | 逆向分析 + 脚本 + 后端 + 功能梳理 |
| `review` | 漏洞审核 + 视觉验证 + 项目理解（不含实现类） |
| `minimal` | 只留记忆与上下文管理 |
| `all` | 仓库全部技能 |

自定义：`skills-hub profile create mine --categories backend,quality --skills agent-memory`

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
