"""仓库定位与运行时状态。

三层路径模型：

  1. 仓库（source of truth）  <repo>/skills/team|local/<category>/<skill>/SKILL.md
  2. 规范 hub（唯一副本）     ~/.agents/skills/<skill>  ->  链接到仓库
  3. 各 agent 目录            ~/.claude/skills/<skill>  ->  链接到规范 hub

主机上任何 agent 看到的都是同一份文件，不存在多份技能副本。
"""

from __future__ import annotations

import os
from pathlib import Path

from .util import read_json, write_json

# 规范 hub —— 与 vercel-labs/skills(`npx skills`) 生态约定保持一致
HUB_HOME = Path(os.environ.get("SKILLS_HUB_HOME", Path.home() / ".agents")).expanduser()
HUB_SKILLS = HUB_HOME / "skills"
STATE_FILE = HUB_HOME / "hub-state.json"
# 外部源克隆缓存（不进 git，可随时清理重建）
HUB_CACHE = HUB_HOME / ".hub-cache"
SOURCES_CACHE = HUB_CACHE / "sources"

SCOPES = ("team", "local")

DEFAULT_STATE = {
    "version": 1,
    "repo": None,          # 仓库绝对路径
    "profile": "default",  # 当前激活的技能组合
    "agents": [],          # 已接入的 agent id
    "link_mode": None,     # symlink | junction | copy
    "linked": {},          # skill -> {scope, category, source}
}


def repo_root() -> Path:
    """定位仓库根目录：环境变量 > 运行时状态 > 包所在位置。"""
    env = os.environ.get("SKILLS_HUB_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    state = load_state()
    if state.get("repo") and Path(state["repo"]).is_dir():
        return Path(state["repo"]).resolve()
    return Path(__file__).resolve().parent.parent


def load_state() -> dict:
    data = read_json(STATE_FILE, default=None)
    if not isinstance(data, dict):
        return dict(DEFAULT_STATE)
    merged = dict(DEFAULT_STATE)
    merged.update(data)
    return merged


def save_state(state: dict) -> None:
    write_json(STATE_FILE, state)


def skills_dir(scope: str) -> Path:
    return repo_root() / "skills" / scope


def profiles_dir() -> Path:
    return repo_root() / "profiles"


def categories_file() -> Path:
    return repo_root() / "registry" / "categories.json"


def sources_file() -> Path:
    return repo_root() / "registry" / "sources.json"


def manifest_file() -> Path:
    return repo_root() / "registry" / "manifest.json"


def load_categories() -> dict:
    data = read_json(categories_file(), default={})
    return data.get("categories", {}) if isinstance(data, dict) else {}
