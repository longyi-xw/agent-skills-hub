# 设计说明

## 问题

一台开发机上往往同时装了多个 AI coding agent（Claude Code、Codex、Cursor、Grok、Gemini、Windsurf…）。
每个 agent 都在自己的家目录下读技能：

```
~/.claude/skills/    ~/.codex/skills/    ~/.cursor/skills/    ~/.grok/skills/  …
```

朴素做法是给每个 agent 各拷一份技能，于是同一个技能在磁盘上有 N 份副本：
改一处要改 N 处，版本还容易漂移。本仓库解决的就是这个问题。

## 三层路径模型

```
┌─ 仓库 (git, source of truth) ───────────────────────────┐
│  skills/team/<分类>/<技能>/SKILL.md                       │
│  skills/local/<分类>/<技能>/SKILL.md                      │
└───────────────┬─────────────────────────────────────────┘
                │ 按 profile 选中的技能建链
                ▼
┌─ 规范 hub (主机唯一副本) ────────────────────────────────┐
│  ~/.agents/skills/<技能>  ──► 指向仓库对应目录            │
└───────────────┬─────────────────────────────────────────┘
                │ 按技能粒度建链
                ▼
┌─ 各 agent 目录 ──────────────────────────────────────────┐
│  ~/.claude/skills/<技能>  ──► 指向规范 hub                │
│  ~/.codex/skills/<技能>   ──► 指向规范 hub                │
│  …                                                        │
└──────────────────────────────────────────────────────────┘
```

- **规范 hub = `~/.agents/skills`**：这是 `npx skills`（vercel-labs/skills）生态约定的共享路径，
  Cline / Amp / Zed / Warp 等 agent 原生读取它，对这些 agent 无需第二跳。
- **两跳链接**：agent → hub → 仓库。这样切换 profile 时只需重建 hub 一层，
  agent 那一跳（指向 hub 里的固定名字）大多不动。

## 关键决策

### 为什么两跳而不是 agent 直接指向仓库

规范 hub 这一层是「当前启用了哪些技能」的物化。profile 切换 = 重写 hub。
agent 目录只跟随 hub，逻辑简单、职责单一；同时满足了「打包后的唯一路径作为通用 agent 目录」的诉求。

### 为什么按技能粒度建链，而不是把整个 skills 目录换成一个链接

各 agent 家目录里常有自带内置技能：Codex 的 `~/.codex/skills/.system`、
Grok 的 `~/.grok/skills/{docx,pptx,xlsx…}`。若把整个目录替换成链接会抹掉它们。
按技能名逐个建链，只管自己放进去的，隐藏目录（`.system`）和已存在的真实目录一律保留跳过。

### 为什么用软链，复制只是回退

软链让「一处修改处处生效」，且不占额外磁盘。
Windows 默认不给普通用户软链权限，因此：

1. 先探测软链是否可用（在 TEMP 里试建一个）
2. 不行则回退到目录联结（junction，无需提权）
3. 再不行回退到复制（`--copy`）

复制模式下技能是独立副本，改仓库后需要 `sync` 才更新——这是有意的权衡，保证在任何环境都能用。

### 为什么零第三方依赖

要做到 `git clone` 即用、三平台一致，就不能依赖 `pip install`。
所以 frontmatter 用内置的小解析器（覆盖 Agent Skills 规范实际用到的 YAML 子集），
而不是引入 PyYAML；链接、体积统计等全部用标准库。

## 安全边界

- `clean` 只回收白名单里的 `.tmp` 历史备份和可再生市场缓存，**绝不**列入任何正在使用的
  插件缓存（如 `~/.claude/plugins/cache`）或 agent 的 skills 目录；默认预演，`--apply` 才删。
- 建链时若目标已是「非本工具管理的真实目录」或「外部链接」，一律跳过并提示，绝不覆盖。
- 移除链接只 `unlink` 链接本身，绝不递归删除链接指向的真实内容。
- team 技能校验会拦截正文里的本机绝对路径，避免把个人环境泄漏进共享仓库。

## 与 `npx skills` 的关系

本工具与 vercel-labs 的 `skills` CLI 生态**兼容而非竞争**：

- 复用同一个规范路径 `~/.agents/skills`，`npx skills` 装的技能（如 `find-skills`）会被识别并保留；
- 补齐了 `npx skills` 没有的能力：团队/本地双轨、profile 组合切换、评审门禁、环境体检清理、
  以及「单一副本多 agent 共享」的两跳链接模型。
