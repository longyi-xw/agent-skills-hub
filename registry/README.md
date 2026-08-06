# registry

技能分类的登记表。`categories.json` 定义了仓库支持哪些分类，
每个技能的 `category` 字段必须在这里登记过，否则 `skills-hub validate` 会报错。

新增分类：在 `categories.json` 的 `categories` 下加一项 `{ "label": "...", "description": "..." }`。
