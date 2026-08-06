"""外部技能源：登记、克隆缓存、扫描其中的技能。

源是本地仓库之外的技能来源（GitHub 仓库等）。它们不进本仓库 git，
而是浅克隆到 ~/.agents/.hub-cache/sources/<id>，供 search 扫描、供 add 导入。
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from .config import SOURCES_CACHE, sources_file
from .registry import Skill, _load_skill  # 复用技能加载与 frontmatter 解析
from .util import read_json, run, write_json


@dataclass
class Source:
    id: str
    name: str
    type: str            # git | local
    repo: str            # owner/repo（git）
    skills_path: str     # 仓库内技能根目录（相对）
    meta: dict

    @property
    def license(self) -> str:
        return str(self.meta.get("license", "unknown"))

    @property
    def trust(self) -> str:
        return str(self.meta.get("trust", "community"))

    @property
    def description(self) -> str:
        return str(self.meta.get("description", ""))

    @property
    def local_mirror(self) -> Path | None:
        mirror = self.meta.get("local_mirror")
        return Path(mirror).expanduser() if mirror else None

    def clone_url(self) -> str:
        return f"https://github.com/{self.repo}.git"

    def cache_dir(self) -> Path:
        return SOURCES_CACHE / self.id


def _load() -> dict:
    data = read_json(sources_file(), default={"version": 1, "sources": {}})
    return data if isinstance(data, dict) else {"version": 1, "sources": {}}


def all_sources() -> list[Source]:
    data = _load().get("sources", {})
    result = []
    for sid, meta in sorted(data.items()):
        if not isinstance(meta, dict):
            continue
        result.append(Source(
            id=sid,
            name=str(meta.get("name", sid)),
            type=str(meta.get("type", "git")),
            repo=str(meta.get("repo", "")),
            skills_path=str(meta.get("skills_path", "skills")),
            meta=meta,
        ))
    return result


def get(source_id: str) -> Source | None:
    for source in all_sources():
        if source.id == source_id:
            return source
    return None


def add_source(source_id: str, repo: str, name: str = "", skills_path: str = "skills",
               license: str = "unknown", trust: str = "community") -> None:
    if not re.match(r"^[a-z0-9][a-z0-9-]*$", source_id):
        raise ValueError(f"源 id '{source_id}' 需为 kebab-case")
    data = _load()
    data.setdefault("sources", {})[source_id] = {
        "name": name or source_id,
        "type": "git",
        "repo": repo,
        "skills_path": skills_path,
        "license": license,
        "trust": trust,
        "description": "",
    }
    write_json(sources_file(), data)


def remove_source(source_id: str) -> bool:
    data = _load()
    if source_id in data.get("sources", {}):
        del data["sources"][source_id]
        write_json(sources_file(), data)
        cache = SOURCES_CACHE / source_id
        if cache.exists():
            shutil.rmtree(cache, ignore_errors=True)
        return True
    return False


# --------------------------------------------------------------- 克隆 / 更新


def _skills_root(source: Source) -> Path | None:
    """返回该源在本机上可扫描的技能根目录：优先本地镜像，其次克隆缓存。"""
    mirror = source.local_mirror
    if mirror and mirror.is_dir():
        return mirror
    cache = source.cache_dir()
    if cache.is_dir():
        base = cache / source.skills_path if source.skills_path else cache
        return base if base.is_dir() else cache
    return None


def sync_source(source: Source) -> tuple[bool, str]:
    """浅克隆或更新一个 git 源到缓存。返回 (成功, 信息)。"""
    if source.type != "git" or not source.repo:
        return False, "非 git 源，跳过"
    if source.local_mirror and source.local_mirror.is_dir():
        return True, f"使用本地镜像 {source.local_mirror}"

    cache = source.cache_dir()
    cache.parent.mkdir(parents=True, exist_ok=True)
    if (cache / ".git").is_dir():
        res = run(["git", "-C", str(cache), "pull", "--ff-only", "--depth", "1"])
        return res.returncode == 0, (res.stdout or res.stderr).strip().splitlines()[-1] if (res.stdout or res.stderr).strip() else "已更新"
    res = run(["git", "clone", "--depth", "1", source.clone_url(), str(cache)])
    if res.returncode != 0:
        return False, (res.stderr or "").strip().splitlines()[-1] if (res.stderr or "").strip() else "克隆失败"
    return True, "已克隆"


# ------------------------------------------------------------------- 扫描


def _iter_skill_dirs(root: Path, max_depth: int = 4):
    import os
    root_depth = len(root.parts)
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        current = Path(dirpath)
        if len(current.parts) - root_depth > max_depth:
            dirnames[:] = []
            continue
        dirnames[:] = [d for d in dirnames if d not in {".git", "node_modules", "__pycache__"}]
        if "SKILL.md" in filenames:
            yield current
            dirnames[:] = []


def index_source(source: Source) -> list[Skill]:
    """扫描一个源里的所有技能（不改动仓库，仅读取缓存）。"""
    root = _skills_root(source)
    if root is None:
        return []
    skills: list[Skill] = []
    for skill_dir in _iter_skill_dirs(root):
        skill = _load_skill(skill_dir, scope=f"source:{source.id}", category=source.id)
        if skill:
            skills.append(skill)
    return skills


def find_skill_dir(source: Source, skill_name: str) -> Path | None:
    """在源里按技能名定位其目录（供 add 使用）。"""
    for skill in index_source(source):
        if skill.name == skill_name or skill.path.name == skill_name:
            return skill.path
    return None
