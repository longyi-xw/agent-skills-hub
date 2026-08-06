# 第三方技能归属声明

本仓库 `skills/team/workflow/` 下的部分技能通过 `skills-hub add` / `adopt` 从外部开源项目
导入（vendor）而来。每个技能的 `SKILL.md` frontmatter 中的 `source:` 字段标注了来源。
在此集中声明归属与许可：

| 技能 | 来源 | 许可 | 原作者 |
|---|---|---|---|
| `brainstorming` | [obra/superpowers](https://github.com/obra/superpowers) | MIT | Jesse Vincent |
| `systematic-debugging` | [obra/superpowers](https://github.com/obra/superpowers) | MIT | Jesse Vincent |
| `test-driven-development` | [obra/superpowers](https://github.com/obra/superpowers) | MIT | Jesse Vincent |
| `writing-skills` | [obra/superpowers](https://github.com/obra/superpowers) | MIT | Jesse Vincent |
| `skill-creator` | OpenAI Codex 内置系统技能 | 见各技能目录内 `license.txt` | OpenAI |

## 说明

- 导入的技能保留其原始内容，仅在 frontmatter 追加 `source` / `imported_via` 标记，
  并对齐 `name` 与目录名以通过本仓库校验。
- superpowers 系列以 MIT 许可发布，允许在保留版权与许可声明的前提下自由使用与再分发。
  本文件即为相应的归属声明。
- 若你要移除某个 vendored 技能：`skills-hub` 仓库中直接删除对应目录即可；
  它与上游是**拷贝**关系（带来源标记），不会自动跟随上游更新——需要更新时重新 `add`。
- 更多可搜索但未 vendor 的源见 `registry/sources.json`，用 `skills-hub search` 查找、
  `skills-hub add` 按需导入。
