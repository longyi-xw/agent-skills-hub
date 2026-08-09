"""从实时数据生成 README 中的技能清单与组合表。

README 里用成对标记圈出自动生成的区域，`skills-hub readme --sync` 重写标记之间的内容：

    <!-- SKILLS:BEGIN --> ... <!-- SKILLS:END -->
    <!-- PROFILES:BEGIN --> ... <!-- PROFILES:END -->

标记之外的手写内容不会被动到。`--check` 用于 CI：清单过期就报错。
"""

from __future__ import annotations

import re
from pathlib import Path

from . import manifest as manifest_mod
from . import profiles as profiles_mod
from . import registry
from .config import load_categories, repo_root

# 分类展示顺序；未列出的分类按字母序排在后面
CATEGORY_ORDER = [
    "requirements", "analysis", "frontend", "backend",
    "quality", "agent-ops", "workflow", "documents", "knowledge",
]

SOURCE_LABEL = {
    "superpowers": "superpowers",
    "anthropic": "anthropic",
    "vercel": "vercel",
    "shadcn": "shadcn/ui",
}


def readme_path() -> Path:
    return repo_root() / "README.md"


def _cell(text: str) -> str:
    """表格单元格转义：竖线会破坏 Markdown 表格。"""
    return text.replace("|", "丨").replace("\n", " ").strip()


def _ordered_categories(present: set[str]) -> list[str]:
    ordered = [c for c in CATEGORY_ORDER if c in present]
    ordered += sorted(present - set(ordered))
    return ordered


def generate_inventory() -> str:
    skills = registry.discover()
    manifest_names = {e.name for e in manifest_mod.entries()}
    categories = load_categories()

    by_cat: dict[str, list] = {}
    for skill in skills:
        by_cat.setdefault(skill.category, []).append(skill)

    original = sum(1 for s in skills if s.name not in manifest_names)
    indexed = len(skills) - original

    lines: list[str] = []
    lines.append(f"共 **{len(skills)} 个**技能：**{original} 个原创**（内容在本仓库）"
                 f" + **{indexed} 个索引**（指针在仓库，内容 sync 时下载）。")
    lines.append("用 `skills-hub list` 查看实时状态，`skills-hub list --category <分类>` 按分类筛选。")

    for cat in _ordered_categories(set(by_cat)):
        meta = categories.get(cat, {})
        label = meta.get("label", cat) if isinstance(meta, dict) else cat
        lines.append("")
        lines.append(f"#### {label} `{cat}`")
        lines.append("| 技能 | 归属 | 用途 |")
        lines.append("|---|---|---|")
        # 原创在前、索引在后，各自按名称排序
        for skill in sorted(by_cat[cat], key=lambda s: (s.name in manifest_names, s.name)):
            if skill.name in manifest_names:
                entry = manifest_mod.get(skill.name)
                src = SOURCE_LABEL.get(entry.source, entry.source)
                owner = f"索引 · {src}"
            else:
                owner = "原创"
            lines.append(f"| `{skill.name}` | {owner} | {_cell(skill.summary)} |")

    lines.append("")
    lines.append("> **原创** = 内容在本仓库 `skills/team/`，本仓库即其来源。  ")
    lines.append("> **索引** = 只在 `registry/manifest.json` 存指针，`sync` 时从上游下载最新版，"
                 "不占仓库体积。")
    return "\n".join(lines)


def generate_profiles() -> str:
    lines = ["| 组合 | 技能数 | 内容 |", "|---|---|---|"]
    for name in profiles_mod.available():
        profile = profiles_mod.load(name) or {}
        try:
            count = len(profiles_mod.resolve(name))
        except KeyError:
            count = 0
        desc = profile.get("description") or profile.get("label") or name
        lines.append(f"| `{name}` | {count} | {_cell(str(desc))} |")
    lines.append(f"| `all` | {len(registry.discover())} | 仓库全部技能（内置组合） |")
    return "\n".join(lines)


BLOCKS = {
    "SKILLS": generate_inventory,
    "PROFILES": generate_profiles,
}


def _replace_block(text: str, key: str, body: str) -> tuple[str, bool]:
    begin, end = f"<!-- {key}:BEGIN -->", f"<!-- {key}:END -->"
    # 非贪婪且允许标记之间为空 —— 首次插入的占位标记就是紧挨着的两行
    pattern = re.compile(re.escape(begin) + r".*?" + re.escape(end), re.DOTALL)
    if not pattern.search(text):
        return text, False
    return pattern.sub(f"{begin}\n{body}\n{end}", text), True


def render(text: str) -> tuple[str, list[str]]:
    """把各生成块写进文本，返回 (新文本, 缺失标记的块名)。"""
    missing = []
    for key, gen in BLOCKS.items():
        text, found = _replace_block(text, key, gen())
        if not found:
            missing.append(key)
    return text, missing


def sync(check_only: bool = False) -> tuple[bool, list[str]]:
    """同步 README。返回 (是否已是最新, 缺失的标记块)。"""
    path = readme_path()
    original = path.read_text(encoding="utf-8")
    updated, missing = render(original)
    if updated == original:
        return True, missing
    if not check_only:
        path.write_text(updated, encoding="utf-8")
    return False, missing
