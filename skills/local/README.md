# 本地私有技能（local scope）

这个目录用来放**只属于你自己、不上传、不同步给团队**的技能。

- 本目录内容默认被 `.gitignore` 忽略（除了这个 README 和 `.gitkeep`），不会进 git。
- `skills-hub` 会把 local 技能和 team 技能一起纳入 profile、一起链接分发。
- 同名时 **local 覆盖 team** —— 你可以在本地临时改写某个团队技能而不影响别人。

## 新建本地技能

```bash
skills-hub new my-private-tool --category backend --scope local
```

## 打磨好了想分享给团队？

```bash
skills-hub promote my-private-tool        # 从 local 移到 team
skills-hub validate my-private-tool       # 过评审门禁
# 然后 git commit + 提 PR，评审通过后其他成员 sync 即可获得
```
