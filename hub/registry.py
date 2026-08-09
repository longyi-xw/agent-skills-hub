"""技能索引：扫描仓库、解析 SKILL.md frontmatter。

仓库布局：  skills/<scope>/<category>/<skill-name>/SKILL.md
            scope    = team | local
            category = registry/categories.json 中登记的分类
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .config import SCOPES, load_categories, skills_dir

# ------------------------------------------------------- 零依赖 frontmatter 解析

_FM_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", re.DOTALL)
_KV_RE = re.compile(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$")


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def parse_frontmatter(text: str) -> dict:
    """解析 SKILL.md 顶部的 YAML frontmatter。

    只支持 Agent Skills 规范实际用到的子集：标量、行内列表、`-` 列表、
    以及 `>`/`|` 折叠块。刻意不引入 PyYAML，保证零依赖跨平台可跑。
    """
    match = _FM_RE.match(text)
    if not match:
        return {}

    data: dict = {}
    key: str | None = None
    block_indent = 0
    mode: str | None = None  # "fold" | "literal" | "list"

    for raw in match.group(1).split("\n"):
        line = raw.rstrip()
        if not line.strip():
            if mode in ("fold", "literal") and key:
                data[key] = (data.get(key, "") + "\n").rstrip() + "\n"
            continue

        indent = len(line) - len(line.lstrip())

        if mode in ("fold", "literal") and key and indent > block_indent:
            piece = line.strip()
            sep = "\n" if mode == "literal" else " "
            data[key] = (data[key] + sep + piece).strip() if data.get(key) else piece
            continue

        if mode == "list" and key and line.lstrip().startswith("- "):
            data[key].append(_strip_quotes(line.lstrip()[2:].strip()))
            continue

        kv = _KV_RE.match(line.strip())
        if not kv:
            continue
        key, value = kv.group(1), kv.group(2).strip()
        block_indent = indent
        mode = None

        if value in (">", ">-", "|", "|-"):
            mode = "literal" if value.startswith("|") else "fold"
            data[key] = ""
        elif value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            data[key] = [_strip_quotes(p.strip()) for p in inner.split(",") if p.strip()]
        elif value == "":
            mode = "list"
            data[key] = []
        else:
            data[key] = _strip_quotes(value)

    return data


# ----------------------------------------------------------------- 技能模型


@dataclass
class Skill:
    name: str
    scope: str          # team | local | indexed
    category: str
    path: Path          # 技能目录（indexed 技能指向缓存，可能尚未下载）
    meta: dict
    origin: str = "repo"     # repo | indexed
    installed: bool = True    # indexed 技能是否已下载
    source: str = ""         # indexed 技能的来源（源 id 或 owner/repo）

    @property
    def description(self) -> str:
        desc = str(self.meta.get("description", "")).strip()
        if not desc and self.origin == "indexed" and not self.installed:
            return "（未同步，运行 skills-hub sync 下载）"
        return desc

    @property
    def summary(self) -> str:
        """一句话用途，用于 README 清单等目录场景。

        原创技能写在 SKILL.md 的 `summary:` 字段；索引技能写在 manifest 条目里。
        都没有时退化为截断的 description（可读性较差，应尽量补 summary）。
        """
        explicit = str(self.meta.get("summary", "")).strip()
        if explicit:
            return explicit
        desc = self.description
        return desc[:60] + "…" if len(desc) > 60 else desc

    @property
    def status(self) -> str:
        """team 技能默认视为已评审通过；local 技能标记为 local；indexed 单列。"""
        if self.origin == "indexed":
            return "indexed" if self.installed else "index-pending"
        explicit = self.meta.get("status")
        if explicit:
            return str(explicit)
        return "verified" if self.scope == "team" else "local"

    @property
    def tags(self) -> list[str]:
        raw = self.meta.get("tags", [])
        if isinstance(raw, str):
            return [t.strip() for t in raw.split(",") if t.strip()]
        return [str(t) for t in raw]

    @property
    def skill_file(self) -> Path:
        return self.path / "SKILL.md"

    def rel(self) -> str:
        return f"{self.scope}/{self.category}/{self.name}"


def _load_skill(skill_dir: Path, scope: str, category: str) -> Skill | None:
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return None
    try:
        meta = parse_frontmatter(skill_md.read_text(encoding="utf-8"))
    except OSError:
        meta = {}
    name = str(meta.get("name") or skill_dir.name).strip()
    return Skill(name=name, scope=scope, category=category, path=skill_dir, meta=meta)


def discover(scopes: tuple[str, ...] = SCOPES,
             include_indexed: bool = True) -> list[Skill]:
    """扫描技能：仓库原创内容（team/local）+ 索引声明的外部技能（indexed）。"""
    found: list[Skill] = []
    for scope in scopes:
        base = skills_dir(scope)
        if not base.is_dir():
            continue
        for category_dir in sorted(base.iterdir()):
            if not category_dir.is_dir() or category_dir.name.startswith("."):
                continue
            for skill_dir in sorted(category_dir.iterdir()):
                if not skill_dir.is_dir() or skill_dir.name.startswith("."):
                    continue
                skill = _load_skill(skill_dir, scope, category_dir.name)
                if skill:
                    found.append(skill)

    if include_indexed:
        repo_names = {s.name for s in found}
        found.extend(_discover_indexed(exclude=repo_names))

    return sorted(found, key=lambda s: (s.category, s.name))


def _discover_indexed(exclude: set[str]) -> list[Skill]:
    """把 manifest 里声明的外部技能纳入 —— 已下载则读真实 frontmatter，否则占位。"""
    from . import manifest as manifest_mod  # 延迟导入避免循环

    skills: list[Skill] = []
    for entry in manifest_mod.entries():
        if entry.name in exclude:
            continue
        content_dir = manifest_mod.installed_dir(entry)
        installed = (content_dir / "SKILL.md").is_file()
        meta: dict = {}
        if installed:
            try:
                meta = parse_frontmatter((content_dir / "SKILL.md").read_text(encoding="utf-8"))
            except OSError:
                meta = {}
        # 索引里登记的描述/标签作为「目录卡片」——即便尚未下载也能看懂用途与范围
        meta.setdefault("name", entry.name)
        if entry.description:
            meta.setdefault("description", entry.description)
        if entry.tags:
            meta.setdefault("tags", entry.tags)
        # summary 以索引里登记的为准 —— 上游 frontmatter 通常没有这个字段
        if entry.summary:
            meta["summary"] = entry.summary
        skills.append(Skill(
            name=entry.name,
            scope="indexed",
            category=entry.category,
            path=content_dir,
            meta=meta,
            origin="indexed",
            installed=installed,
            source=entry.source,
        ))
    return skills


def index() -> dict[str, Skill]:
    """按技能名索引。同名时 local 覆盖 team —— 本地私有版本优先生效。"""
    result: dict[str, Skill] = {}
    for skill in discover():
        if skill.name in result and skill.scope == "team":
            continue
        result[skill.name] = skill
    return result


def by_category() -> dict[str, list[Skill]]:
    grouped: dict[str, list[Skill]] = {}
    for skill in discover():
        grouped.setdefault(skill.category, []).append(skill)
    return grouped


def category_label(category: str) -> str:
    meta = load_categories().get(category)
    if isinstance(meta, dict):
        return str(meta.get("label", category))
    return category
