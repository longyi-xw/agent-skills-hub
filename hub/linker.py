"""链接分发：仓库 -> 规范 hub -> 各 agent 技能目录。

规范 hub 是主机上技能的唯一落地路径。所有 agent 目录里的条目都是
指向 hub 的链接，因此 N 个 agent 共享 1 份技能文件，不产生副本。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import agents as agents_mod
from . import profiles as profiles_mod
from . import registry
from .config import HUB_CACHE, HUB_SKILLS, load_state, repo_root, save_state
from .util import (
    LINK_COPY,
    is_link,
    link_kind_available,
    link_target,
    make_link,
    remove_link,
)


@dataclass
class SyncResult:
    linked: list[str]
    removed: list[str]
    skipped: list[tuple[str, str]]   # (名称, 原因)
    mode: str


def _owned_by_hub(path: Path) -> bool:
    """判断某条目是否由本工具管理 —— 只有这样的条目才允许被清理。"""
    if not is_link(path):
        return False
    target = link_target(path)
    if target is None:
        return False
    resolved = (path.parent / target).resolve() if not target.is_absolute() else target.resolve()
    bases = [HUB_SKILLS.resolve(), repo_root().resolve(), HUB_CACHE.resolve()]
    # 有本地镜像的源（如 superpowers）不在上述路径下，也应视为本工具管理
    try:
        from . import manifest as manifest_mod
        for entry in manifest_mod.entries():
            content = manifest_mod.installed_dir(entry).resolve()
            bases.append(content)
            bases.append(content.parent)
    except Exception:
        pass
    for base in bases:
        try:
            resolved.relative_to(base)
            return True
        except ValueError:
            continue
    return False


def _link_mode(state: dict) -> str:
    mode = state.get("link_mode")
    return mode if mode else link_kind_available()


# ------------------------------------------------------------------ 规范 hub


def sync_hub(skill_names: list[str], mode: str | None = None) -> SyncResult:
    """让 ~/.agents/skills 精确等于给定技能集合（链接到仓库）。"""
    state = load_state()
    mode = mode or _link_mode(state)
    HUB_SKILLS.mkdir(parents=True, exist_ok=True)

    known = registry.index()
    wanted = {n for n in skill_names if n in known}

    linked, removed, skipped = [], [], []

    # 清掉不再需要的旧链接；他人手工放进来的真实目录一律保留
    for entry in sorted(HUB_SKILLS.iterdir()):
        if entry.name.startswith("."):
            continue
        if entry.name in wanted:
            continue
        if _owned_by_hub(entry):
            remove_link(entry)
            removed.append(entry.name)
        elif is_link(entry):
            skipped.append((entry.name, "外部链接，保留"))
        else:
            skipped.append((entry.name, "非本仓库管理的真实目录，保留"))

    for name in sorted(wanted):
        skill = known[name]
        if skill.origin == "indexed" and not skill.installed:
            skipped.append((name, "索引技能未下载，先运行 sync"))
            continue
        if not (skill.path / "SKILL.md").is_file():
            skipped.append((name, "内容缺失，跳过"))
            continue
        dst = HUB_SKILLS / name
        if dst.exists() and not is_link(dst):
            skipped.append((name, "同名真实目录已存在"))
            continue
        # wanted 名称由本工具主张所有权：不存在则建，已是链接则更新指向最新目标
        # （make_link 会先移除旧链接，从而修正诸如镜像→缓存这类目标漂移）
        make_link(skill.path, dst, mode)
        linked.append(name)

    state["link_mode"] = mode
    state["linked"] = {
        n: {"scope": known[n].scope, "category": known[n].category,
            "source": str(known[n].path)}
        for n in sorted(wanted)
    }
    save_state(state)
    return SyncResult(linked, removed, skipped, mode)


def hub_entries() -> list[str]:
    if not HUB_SKILLS.is_dir():
        return []
    return sorted(p.name for p in HUB_SKILLS.iterdir() if not p.name.startswith("."))


# ---------------------------------------------------------------- agent 分发


def link_agent(spec: agents_mod.AgentSpec, mode: str | None = None) -> SyncResult:
    """把规范 hub 里的技能按条目链接进某个 agent 的技能目录。"""
    state = load_state()
    mode = mode or _link_mode(state)

    if spec.native_hub:
        return SyncResult([], [], [(spec.id, "原生读取规范 hub，无需建链")], mode)

    spec.global_dir.mkdir(parents=True, exist_ok=True)
    wanted = set(hub_entries())
    linked, removed, skipped = [], [], []

    for entry in sorted(spec.global_dir.iterdir()):
        if entry.name.startswith("."):
            continue  # 保留 agent 自带的 .system 等隐藏内置技能
        if entry.name in wanted:
            continue
        if _owned_by_hub(entry):
            remove_link(entry)
            removed.append(entry.name)

    for name in sorted(wanted):
        dst = spec.global_dir / name
        if dst.exists() and not is_link(dst):
            skipped.append((name, f"{spec.id} 已有同名内置技能"))
            continue
        if is_link(dst) and not _owned_by_hub(dst):
            skipped.append((name, f"{spec.id} 已有外部链接"))
            continue
        make_link(HUB_SKILLS / name, dst, mode)
        linked.append(name)

    agents_state = set(state.get("agents") or [])
    agents_state.add(spec.id)
    state["agents"] = sorted(agents_state)
    state["link_mode"] = mode
    save_state(state)
    return SyncResult(linked, removed, skipped, mode)


def unlink_agent(spec: agents_mod.AgentSpec) -> list[str]:
    """移除某 agent 目录下由本工具建立的链接，不动它自带的技能。"""
    removed = []
    if spec.global_dir.is_dir() and not spec.native_hub:
        for entry in sorted(spec.global_dir.iterdir()):
            if _owned_by_hub(entry):
                remove_link(entry)
                removed.append(entry.name)

    state = load_state()
    state["agents"] = [a for a in (state.get("agents") or []) if a != spec.id]
    save_state(state)
    return removed


def apply_profile(profile_name: str, mode: str | None = None) -> tuple[SyncResult, dict[str, SyncResult]]:
    """切换技能组合：重建 hub，再刷新所有已接入 agent。"""
    names = profiles_mod.resolve(profile_name)
    hub_result = sync_hub(names, mode)

    state = load_state()
    state["profile"] = profile_name
    save_state(state)

    per_agent: dict[str, SyncResult] = {}
    for agent_id in load_state().get("agents") or []:
        spec = agents_mod.resolve(agent_id)
        if spec:
            per_agent[agent_id] = link_agent(spec, mode)
    return hub_result, per_agent


def project_link(project: Path, mode: str | None = None) -> dict[str, str]:
    """在某个项目里落一份 .agents/skills 链接（供项目级 agent 读取）。"""
    state = load_state()
    mode = mode or _link_mode(state)
    dst = project / ".agents" / "skills"
    dst.parent.mkdir(parents=True, exist_ok=True)
    if is_link(dst):
        remove_link(dst)
    elif dst.exists():
        raise FileExistsError(f"{dst} 已存在且不是链接")
    used = make_link(HUB_SKILLS, dst, mode)
    return {"path": str(dst), "mode": used}


def link_mode_note(mode: str) -> str:
    if mode == LINK_COPY:
        return "当前使用复制模式（本机不支持软链），技能是副本，需 `sync` 更新"
    return f"链接方式：{mode}"
