"""新建技能 与 收编（adopt）已有技能。"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from .config import SOURCES_CACHE, load_categories, skills_dir
from .registry import parse_frontmatter
from .validate import NAME_RE

TEMPLATE = """---
name: {name}
description: {description}
category: {category}
tags: [{tags}]
status: {status}
---

# {title}

## 何时使用本技能

- 当用户……时
- 当需要……时

## 前置检查

1. 先确认……
2. 再确认……

## 执行流程

### 1. ……

### 2. ……

### 3. ……

## 输出要求

- ……

## 反面案例

| 不要这样 | 要这样 |
|---|---|
| …… | …… |
"""


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.strip().lower()).strip("-")
    return re.sub(r"-{2,}", "-", slug)


def create(name: str, category: str, scope: str = "local",
           description: str = "", force: bool = False) -> Path:
    slug = _slug(name)
    if not NAME_RE.match(slug):
        raise ValueError(f"技能名 '{name}' 无法转换为合法的 kebab-case")

    categories = load_categories()
    if categories and category not in categories:
        raise ValueError(
            f"分类 '{category}' 未登记，可用分类：{', '.join(sorted(categories))}"
        )

    target = skills_dir(scope) / category / slug
    if target.exists() and not force:
        raise FileExistsError(f"技能已存在：{target}")
    target.mkdir(parents=True, exist_ok=True)
    (target / "references").mkdir(exist_ok=True)

    content = TEMPLATE.format(
        name=slug,
        description=description or f"当用户需要 {name} 时使用本技能。请补全触发场景描述。",
        category=category,
        tags=category,
        status="draft" if scope == "local" else "verified",
        title=name,
    )
    (target / "SKILL.md").write_text(content, encoding="utf-8")
    (target / "references" / ".gitkeep").write_text("", encoding="utf-8")
    return target


def adopt(source: Path, category: str, scope: str = "team",
          rename: str | None = None, move: bool = False) -> Path:
    """把主机上散落的现成技能收编进仓库。

    source 可以是技能目录，也可以直接是 SKILL.md。
    """
    source = source.expanduser().resolve()
    if source.is_file() and source.name == "SKILL.md":
        source = source.parent
    if not (source / "SKILL.md").is_file():
        raise FileNotFoundError(f"{source} 下没有 SKILL.md")

    meta = parse_frontmatter((source / "SKILL.md").read_text(encoding="utf-8"))
    slug = _slug(rename or str(meta.get("name") or source.name))
    target = skills_dir(scope) / category / slug
    if target.exists():
        raise FileExistsError(f"目标已存在：{target}")

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target, symlinks=False,
                    ignore=shutil.ignore_patterns(".git", "__pycache__", ".DS_Store"))

    # 收编后把 frontmatter 的 name 对齐目录名，避免校验失败
    skill_md = target / "SKILL.md"
    text = skill_md.read_text(encoding="utf-8")
    if str(meta.get("name", "")) != slug:
        text = re.sub(r"^name:.*$", f"name: {slug}", text, count=1, flags=re.M)
        skill_md.write_text(text, encoding="utf-8")

    if move:
        shutil.rmtree(source)
    return target


def _set_frontmatter_fields(skill_md: Path, fields: dict[str, str]) -> None:
    """在 SKILL.md 的 frontmatter 里写入/更新若干标量字段（用于打来源标记）。"""
    text = skill_md.read_text(encoding="utf-8")
    m = re.match(r"\A(---\s*\n)(.*?)(\n---\s*\n)(.*)\Z", text, re.DOTALL)
    if not m:
        # 没有 frontmatter：补一个最小的
        fm = "".join(f"{k}: {v}\n" for k, v in fields.items())
        skill_md.write_text(f"---\n{fm}---\n\n{text}", encoding="utf-8")
        return
    head, body_fm, close, rest = m.groups()
    for key, value in fields.items():
        if re.search(rf"^{re.escape(key)}\s*:", body_fm, flags=re.M):
            body_fm = re.sub(rf"^{re.escape(key)}\s*:.*$", f"{key}: {value}", body_fm, count=1, flags=re.M)
        else:
            body_fm = body_fm.rstrip("\n") + f"\n{key}: {value}"
    skill_md.write_text(f"{head}{body_fm}{close}{rest}", encoding="utf-8")


def _parse_ref(ref: str) -> tuple[str, str, str | None]:
    """解析 add 的引用。

    返回 (kind, locator, subpath)：
      kind="source"  → locator=源id, subpath=技能名        （<source-id>:<skill>）
      kind="git"     → locator=owner/repo, subpath=仓库内路径或None
    """
    from . import sources as sources_mod

    if ":" in ref and "/" not in ref.split(":", 1)[0]:
        left, right = ref.split(":", 1)
        if sources_mod.get(left):
            return "source", left, right
    # owner/repo 或 owner/repo:path 或 owner/repo/path...
    if ":" in ref:
        repo_part, sub = ref.split(":", 1)
    else:
        parts = ref.split("/")
        if len(parts) > 2:
            repo_part = "/".join(parts[:2])
            sub = "/".join(parts[2:])
        else:
            repo_part, sub = ref, None
    return "git", repo_part, sub


def _clone_repo(repo: str) -> Path:
    from .util import run

    cache = SOURCES_CACHE / "_add" / repo.replace("/", "__")
    cache.parent.mkdir(parents=True, exist_ok=True)
    if (cache / ".git").is_dir():
        run(["git", "-C", str(cache), "pull", "--ff-only", "--depth", "1"])
    else:
        res = run(["git", "clone", "--depth", "1", f"https://github.com/{repo}.git", str(cache)])
        if res.returncode != 0:
            raise RuntimeError(f"克隆 {repo} 失败：{(res.stderr or '').strip().splitlines()[-1:]}")
    return cache


def _resolve_skill_source(ref: str) -> tuple[Path, str]:
    """把 add 引用解析成 (本机技能目录, 来源标记字符串)。"""
    from . import sources as sources_mod

    kind, locator, sub = _parse_ref(ref)

    if kind == "source":
        source = sources_mod.get(locator)
        sources_mod.sync_source(source)
        skill_dir = sources_mod.find_skill_dir(source, sub)
        if skill_dir is None:
            raise FileNotFoundError(f"源 '{locator}' 中找不到技能 '{sub}'")
        return skill_dir, f"{source.repo or locator} ({source.license})"

    # git
    root = _clone_repo(locator)
    if sub:
        candidate = root / sub
        if (candidate / "SKILL.md").is_file():
            skill_dir = candidate
        elif candidate.is_dir():
            # 目录下再找一个 SKILL.md
            found = next((p.parent for p in candidate.rglob("SKILL.md")), None)
            skill_dir = found or candidate
        else:
            raise FileNotFoundError(f"{locator} 中路径 '{sub}' 下没有 SKILL.md")
    else:
        found = next((p.parent for p in root.rglob("SKILL.md")), None)
        if found is None:
            raise FileNotFoundError(f"{locator} 仓库里没有找到 SKILL.md")
        skill_dir = found
    return skill_dir, locator


def add_external(ref: str, category: str, scope: str = "local",
                 rename: str | None = None) -> Path:
    """从外部源/仓库导入一个技能进本仓库，并打上来源标记（区别于 new 的从零创建）。"""
    categories = load_categories()
    if categories and category not in categories:
        raise ValueError(
            f"分类 '{category}' 未登记，可用：{', '.join(sorted(categories))}"
        )

    skill_dir, provenance = _resolve_skill_source(ref)
    target = adopt(skill_dir, category, scope=scope, rename=rename, move=False)

    _set_frontmatter_fields(target / "SKILL.md", {
        "source": provenance,
        "imported_via": "skills-hub add",
    })
    return target


def promote(name: str, category: str | None = None) -> Path:
    """把 local 技能提升为 team 技能（走完校验后由 PR 合入）。"""
    from . import registry

    matches = [s for s in registry.discover(("local",)) if s.name == name]
    if not matches:
        raise KeyError(f"local 作用域下没有技能 '{name}'")
    skill = matches[0]

    target_category = category or skill.category
    target = skills_dir("team") / target_category / skill.name
    if target.exists():
        raise FileExistsError(f"team 下已存在同名技能：{target}")

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(skill.path), str(target))

    skill_md = target / "SKILL.md"
    text = skill_md.read_text(encoding="utf-8")
    if re.search(r"^status:", text, flags=re.M):
        text = re.sub(r"^status:.*$", "status: verified", text, count=1, flags=re.M)
    skill_md.write_text(text, encoding="utf-8")
    return target
