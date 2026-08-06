---
name: script-development
description: 自动化脚本与命令行小工具的开发规范，偏向 Python/Shell。当用户要求「写个脚本」「批量处理这些文件/数据」「自动化这个流程」「写个 CLI 工具」「定时跑一下」「清洗/转换这批数据」时，使用本技能。强调：参数化而非写死、幂等可重跑、干跑（dry-run）预演、清晰日志与退出码、以及对破坏性操作的保护。适用于一次性数据处理脚本，也适用于要长期维护的运维/自动化工具。Use this skill when writing automation scripts, CLI tools, batch processors, or any throwaway-to-durable utility.
category: backend
tags: [scripting, automation, cli, python, shell]
status: verified
---

# 脚本开发

## 何时使用本技能

- 批量处理文件 / 数据 / 接口
- 把一段手工流程自动化
- 写命令行小工具、运维脚本、定时任务

## 一次性脚本也要守的三条底线

哪怕「只跑一次」，也很可能被再跑第二次、被别人复制去改。所以：

1. **参数化**：路径、数量、开关做成命令行参数或顶部常量，不写死在逻辑里
2. **幂等**：重复跑同一个脚本，结果一致、不重复副作用（重复插入、重复发送）
3. **可预演**：任何会改动数据/文件/发请求的脚本，默认支持 `--dry-run` 只打印将要做什么

## 执行流程

### 1. 骨架先立起来

Python 脚本推荐结构：

```python
#!/usr/bin/env python3
"""一句话说明这个脚本干什么。"""
import argparse
import logging
import sys

log = logging.getLogger("script")

def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("input")
    p.add_argument("--dry-run", action="store_true", help="只预演不实际执行")
    p.add_argument("-v", "--verbose", action="store_true")
    return p.parse_args(argv)

def main(argv=None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    # ... 实际工作 ...
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

要点：有 `main()`、有退出码、日志走 logging 而不是 print、能被 import 也能直接跑。

### 2. 破坏性操作的保护

删除、覆盖、批量写库、批量发消息，属于破坏性操作。规则：

- 默认 `--dry-run`，真正执行要显式加 `--apply` / `--yes`
- 执行前打印**将要影响的对象数量与样例**，让人有机会中止
- 删除前先看目标存不存在、是不是预期的东西
- 大批量操作可加 `--limit` 先小规模试跑

### 3. 幂等与断点续跑

- 处理前先判断「是否已处理过」（看标记、看目标是否存在、查去重键）
- 长任务把进度落盘（已处理 id 列表 / 游标），中断后能续跑
- 批处理逐条 `try/except`，单条失败记录并继续，不要一条挂掉全盘皆输，最后汇总失败清单

### 4. 输入输出

- 读大文件用流式（逐行 / 分块），不要一次性读进内存
- 输出结构化数据优先 JSON Lines / CSV，方便下游再处理
- 路径用 `pathlib`，不手拼字符串；跨平台不写死 `/` 或 `\`
- 编码显式指定 `encoding="utf-8"`

### 5. Shell 脚本补充

若确实用 Shell（简单胶水场景）：

```bash
#!/usr/bin/env bash
set -euo pipefail          # 出错即停、未定义变量报错、管道错误不吞
IFS=$'\n\t'
```

- 变量一律加引号 `"$var"`，防路径空格与词分裂
- 逻辑一旦超过几十行或需要数据结构，改用 Python
- 依赖的外部命令先 `command -v` 检查存在性

## 自测清单

- [ ] `--dry-run` 跑过，输出的「将要做什么」符合预期
- [ ] 重复跑两次，结果一致（幂等）
- [ ] 空输入 / 单条 / 大批量三种规模都试过
- [ ] 中途 Ctrl-C 不会留下损坏的中间状态
- [ ] 破坏性操作有二次确认或 `--apply` 开关
- [ ] 退出码正确（成功 0，失败非 0）

## 反面案例

| 不要这样 | 要这样 |
|---|---|
| 路径/数量写死在代码里 | argparse 参数或顶部常量 |
| 删除脚本上来就删 | 默认 dry-run，`--apply` 才动手 |
| 一次 `read().splitlines()` 读 2G 文件 | 逐行流式处理 |
| 批处理一条报错整个崩 | 逐条 try/except，末尾汇总失败 |
| 用 print 输出进度和结果混在一起 | 进度走 logging(stderr)，数据走 stdout |
| Shell 里 `rm -rf $dir` | `"$dir"` 加引号 + 先校验 + set -euo pipefail |
