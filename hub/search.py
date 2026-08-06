"""统一搜索：仓库 → 已登记源 → 网络（结构化优先，兜底通用）。

设计原则（对应需求）：
  · 一个入口 `skills-hub search <query>`，但结果**分区展示**，明确区分来源。
  · 先在本地仓库和已缓存的外部源里找；只有都没有，才走网络搜索。
  · 网络结果尽量给出 owner/repo[:path] 形式，可直接交给 `skills-hub add`。
"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from . import registry, sources
from .util import run


@dataclass
class Hit:
    name: str
    origin: str            # "repo" | "source:<id>" | "network"
    description: str = ""
    ref: str = ""          # 可 add 的引用：owner/repo[:path] 或 source:skill
    extra: str = ""        # 附注：stars、license 等
    score: float = 0.0


@dataclass
class SearchResult:
    repo: list[Hit] = field(default_factory=list)
    sources: list[Hit] = field(default_factory=list)
    network: list[Hit] = field(default_factory=list)
    network_kind: str = ""   # "structured" | "general" | "none"
    fallback_urls: list[tuple[str, str]] = field(default_factory=list)


def _tokens(text: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9]+", text.lower()) if t]


def _score(query: str, name: str, description: str, tags: list[str]) -> float:
    q = query.lower().strip()
    qtokens = set(_tokens(query))
    if not qtokens:
        return 0.0
    hay_name = name.lower()
    hay = f"{name} {description} {' '.join(tags)}".lower()
    score = 0.0
    if q == hay_name:
        score += 100
    if q in hay_name:
        score += 40
    if q in hay:
        score += 15
    haytokens = set(_tokens(hay))
    overlap = qtokens & haytokens
    score += 10 * len(overlap)
    nametokens = set(_tokens(name))
    score += 8 * len(qtokens & nametokens)
    return score


# ------------------------------------------------------------------- 各层


def search_repo(query: str) -> list[Hit]:
    hits = []
    for skill in registry.discover():
        s = _score(query, skill.name, skill.description, skill.tags + [skill.category])
        if s > 0:
            hits.append(Hit(
                name=skill.name, origin="repo", description=skill.description,
                ref=skill.name, extra=f"{skill.scope}/{skill.category}", score=s,
            ))
    return sorted(hits, key=lambda h: -h.score)


def search_sources(query: str, only_cached: bool = True) -> list[Hit]:
    hits = []
    for source in sources.all_sources():
        skills = sources.index_source(source)   # 仅读已缓存/镜像的源
        if not skills and only_cached:
            continue
        for skill in skills:
            s = _score(query, skill.name, skill.description, skill.tags)
            if s > 0:
                hits.append(Hit(
                    name=skill.name, origin=f"source:{source.id}",
                    description=skill.description,
                    ref=f"{source.id}:{skill.name}",
                    extra=f"{source.name} · {source.license}", score=s,
                ))
    return sorted(hits, key=lambda h: -h.score)


def _gh_available() -> bool:
    return shutil.which("gh") is not None


def _gh_json(args: list[str]) -> list | None:
    res = run(["gh"] + args)
    if res.returncode != 0 or not res.stdout.strip():
        return None
    try:
        return json.loads(res.stdout)
    except json.JSONDecodeError:
        return None


def search_network_structured(query: str, limit: int = 8) -> list[Hit]:
    """结构化网络搜索：优先用已认证的 gh CLI 搜 GitHub。

    两路：① 搜含 SKILL.md 的代码路径（直接可 add 到具体技能）
          ② 搜相关仓库（可 add 整仓后再选）
    """
    if not _gh_available():
        return []

    hits: list[Hit] = []

    # ① 代码搜索：定位具体的 SKILL.md
    code = _gh_json([
        "search", "code", query, "--filename", "SKILL.md",
        "--limit", str(limit), "--json", "repository,path",
    ])
    for item in code or []:
        repo_full = item.get("repository", {}).get("nameWithOwner", "")
        path = item.get("path", "")
        skill_dir = str(Path(path).parent) if path.endswith("SKILL.md") else path
        name = Path(skill_dir).name or repo_full.split("/")[-1]
        if not repo_full:
            continue
        ref = f"{repo_full}:{skill_dir}" if skill_dir and skill_dir != "." else repo_full
        hits.append(Hit(
            name=name, origin="network", description=f"{repo_full} 中的技能",
            ref=ref, extra="GitHub code", score=50,
        ))

    # ② 仓库搜索：相关技能仓库
    if len(hits) < limit:
        repos = _gh_json([
            "search", "repos", f"{query} skills",
            "--limit", str(limit), "--json", "fullName,description,stargazersCount",
        ])
        seen = {h.ref.split(":")[0] for h in hits}
        for item in repos or []:
            full = item.get("fullName", "")
            if not full or full in seen:
                continue
            hits.append(Hit(
                name=full.split("/")[-1], origin="network",
                description=(item.get("description") or "")[:100],
                ref=full, extra=f"★{item.get('stargazersCount', 0)} · GitHub repo",
                score=30,
            ))
    return hits[:limit]


def general_fallback_urls(query: str) -> list[tuple[str, str]]:
    """兜底通用搜索入口（结构化无命中时给出，供人工/agent 继续）。"""
    from urllib.parse import quote
    q = quote(query)
    return [
        ("skills.sh", f"https://skills.sh/?q={q}"),
        ("SkillsMP", f"https://skillsmp.com/?q={q}"),
        ("GitHub", f"https://github.com/search?q={q}+SKILL.md&type=code"),
    ]


# ----------------------------------------------------------------- 顶层入口


def search(query: str, want_network: bool = True) -> SearchResult:
    result = SearchResult()
    result.repo = search_repo(query)
    result.sources = search_sources(query)

    has_local = bool(result.repo or result.sources)

    # 仓库/源都没有 → 才走网络（结构化优先）
    if want_network and not has_local:
        structured = search_network_structured(query)
        if structured:
            result.network = structured
            result.network_kind = "structured"
        else:
            result.network_kind = "general"
            result.fallback_urls = general_fallback_urls(query)
    elif want_network and has_local:
        # 本地有结果时，网络层作为「更多」提示但不喧宾夺主
        result.network_kind = "skipped"

    return result
