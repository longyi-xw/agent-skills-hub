"""技能组合（profile）：在不同项目 / 场合下手动切换启用的技能集合。

profiles/<name>.json
{
  "label":       "Python 后端",
  "description": "...",
  "extends":     ["base"],          // 可继承其它组合
  "categories":  ["backend"],       // 整个分类纳入
  "skills":      ["security-audit"],// 追加单个技能
  "exclude":     ["frontend-development"]
}
"""

from __future__ import annotations

from pathlib import Path

from .config import profiles_dir
from .util import read_json, write_json
from . import registry


def available() -> list[str]:
    directory = profiles_dir()
    if not directory.is_dir():
        return []
    return sorted(p.stem for p in directory.glob("*.json"))


def path_for(name: str) -> Path:
    return profiles_dir() / f"{name}.json"


def load(name: str) -> dict | None:
    return read_json(path_for(name), default=None)


def save(name: str, data: dict) -> None:
    write_json(path_for(name), data)


def resolve(name: str, _seen: set[str] | None = None) -> list[str]:
    """把组合展开成具体技能名列表（去重、稳定排序）。

    `all` 是内置组合，表示仓库中的全部技能。
    """
    if name == "all":
        return sorted(registry.index().keys())

    seen = _seen or set()
    if name in seen:
        return []
    seen.add(name)

    profile = load(name)
    if profile is None:
        raise KeyError(name)

    names: set[str] = set()

    parents = profile.get("extends") or []
    if isinstance(parents, str):
        parents = [parents]
    for parent in parents:
        names.update(resolve(parent, seen))

    grouped = registry.by_category()
    for category in profile.get("categories") or []:
        names.update(s.name for s in grouped.get(category, []))

    names.update(profile.get("skills") or [])
    names.difference_update(profile.get("exclude") or [])

    known = registry.index()
    return sorted(n for n in names if n in known)


def missing(name: str) -> list[str]:
    """组合里点名了、但仓库中不存在的技能。"""
    profile = load(name)
    if profile is None:
        return []
    known = registry.index()
    return sorted(s for s in (profile.get("skills") or []) if s not in known)


def label(name: str) -> str:
    if name == "all":
        return "全部技能"
    profile = load(name) or {}
    return str(profile.get("label") or name)
