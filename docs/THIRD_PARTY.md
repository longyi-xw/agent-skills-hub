# 第三方技能与归属

本仓库采用**索引模型**：外部技能的内容**不保存在本仓库**，只在
`registry/manifest.json` 里登记指针，`skills-hub sync` 时才从在线源下载到
本机缓存 `~/.agents/.hub-cache`。因此仓库不分发第三方技能内容，只是指向它们。

## 当前索引的外部技能

| 技能 | 在线源 | 许可 |
|---|---|---|
| `brainstorming` | [obra/superpowers](https://github.com/obra/superpowers) `skills/brainstorming` | MIT |
| `systematic-debugging` | [obra/superpowers](https://github.com/obra/superpowers) `skills/systematic-debugging` | MIT |
| `test-driven-development` | [obra/superpowers](https://github.com/obra/superpowers) `skills/test-driven-development` | MIT |
| `writing-skills` | [obra/superpowers](https://github.com/obra/superpowers) `skills/writing-skills` | MIT |
| `skill-creator` | [anthropics/skills](https://github.com/anthropics/skills) `skills/skill-creator` | 见该仓库 LICENSE |

## 说明

- 下载的内容遵循各自上游的许可，归属归原作者（superpowers 作者 Jesse Vincent 等）。
- 因为是**按索引下载**而非拷贝分发，上游更新后 `skills-hub update` 即可拿到最新版；
  上游若下线或改许可，本仓库不承担再分发责任。
- 增删外部技能只需改 `registry/manifest.json`（或用 `add` / `uninstall`），
  再 `sync` 即可，不会在本仓库留下第三方内容。
- 可搜索、可按需索引的更多源见 `registry/sources.json`。
