"""环境体检：扫描主机上的技能副本、悬空链接与可回收的缓存/备份。

只做只读扫描并给出建议；真正的删除由 `hub clean --apply` 在用户确认后执行。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from . import agents as agents_mod
from .config import HUB_SKILLS, repo_root
from .util import dir_size, human_size, is_link, link_target

HOME = Path.home()

# 扫描根：各 agent 家目录 + 常见工程目录
SCAN_ROOTS = [
    HOME / ".claude",
    HOME / ".codex",
    HOME / ".grok",
    HOME / ".codeium",
    HOME / ".cursor",
    HOME / ".gemini",
    HOME / ".agents",
    HOME / ".config" / "opencode",
]

# 可安全回收的缓存 / 备份目录模式：(glob, 说明, 分级)
#   safe   —— 纯历史备份 / 临时产物，删了无副作用
#   cache  —— 可再生缓存，删后下次拉取/启动自动重建，可能有一次变慢
# 刻意不含 ~/.claude/plugins/cache 与各 agent 的 skills 目录 ——
# 那里放的是**正在使用**的插件与技能，误删会中断当前会话。
RECLAIM_PATTERNS = [
    (".codex/.tmp/plugins-backup-*", "Codex 插件同步的历史备份，可重新生成", "safe"),
    (".codex/.tmp/bundled-marketplaces", "Codex 内置市场缓存，下次启动自动重建", "cache"),
    (".grok/marketplace-cache", "Grok 市场缓存，下次拉取自动重建", "cache"),
]


@dataclass
class Duplicate:
    name: str
    locations: list[Path] = field(default_factory=list)

    @property
    def wasted(self) -> int:
        """除第一份外的体积视为冗余。"""
        if len(self.locations) < 2:
            return 0
        return sum(dir_size(p) for p in self.locations[1:])


@dataclass
class Report:
    duplicates: list[Duplicate]
    dangling: list[tuple[Path, str]]
    reclaimable: list[tuple[Path, str, int]]
    unmanaged: list[Path]
    hub_ok: bool
    hub_count: int


def _iter_skill_dirs(root: Path, max_depth: int = 6):
    """在 root 下查找含 SKILL.md 的目录，不跟随软链，控制深度。"""
    if not root.is_dir():
        return
    root_depth = len(root.parts)
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        current = Path(dirpath)
        if len(current.parts) - root_depth >= max_depth:
            dirnames[:] = []
            continue
        dirnames[:] = [d for d in dirnames if d not in {".git", "node_modules", "__pycache__"}]
        if "SKILL.md" in filenames:
            yield current
            dirnames[:] = []


def scan(extra_roots: list[Path] | None = None) -> Report:
    roots = [r for r in SCAN_ROOTS if r.is_dir()]
    roots += [r for r in (extra_roots or []) if r.is_dir()]

    hub_real = HUB_SKILLS.resolve() if HUB_SKILLS.exists() else None
    repo_real = repo_root().resolve()

    by_name: dict[str, list[Path]] = {}
    for root in roots:
        for skill_dir in _iter_skill_dirs(root):
            resolved = skill_dir.resolve()
            # hub 与仓库本身是「唯一副本」，不参与重复统计
            if hub_real and _under(resolved, hub_real):
                continue
            if _under(resolved, repo_real):
                continue
            by_name.setdefault(skill_dir.name, []).append(skill_dir)

    duplicates = [
        Duplicate(name, sorted(set(paths), key=lambda p: len(str(p))))
        for name, paths in sorted(by_name.items())
        if len({p.resolve() for p in paths}) > 1
    ]

    dangling: list[tuple[Path, str]] = []
    for spec in agents_mod.AGENTS:
        directory = spec.global_dir
        if not directory.is_dir():
            continue
        for entry in sorted(directory.iterdir()):
            if is_link(entry) and not entry.resolve().exists():
                dangling.append((entry, f"{spec.id}: 指向 {link_target(entry)} 已失效"))

    reclaimable: list[tuple[Path, str, int]] = []
    for pattern, note, tier in RECLAIM_PATTERNS:
        label = "备份" if tier == "safe" else "缓存"
        for path in sorted(HOME.glob(pattern)):
            if path.is_dir():
                reclaimable.append((path, f"[{label}] {note}", dir_size(path)))

    unmanaged: list[Path] = []
    if HUB_SKILLS.is_dir():
        for entry in sorted(HUB_SKILLS.iterdir()):
            if entry.name.startswith("."):
                continue
            if not is_link(entry):
                unmanaged.append(entry)

    hub_count = len([p for p in HUB_SKILLS.iterdir() if not p.name.startswith(".")]) \
        if HUB_SKILLS.is_dir() else 0

    return Report(
        duplicates=duplicates,
        dangling=dangling,
        reclaimable=reclaimable,
        unmanaged=unmanaged,
        hub_ok=HUB_SKILLS.is_dir(),
        hub_count=hub_count,
    )


def _under(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False


def format_report(report: Report) -> str:
    lines: list[str] = []

    lines.append(f"规范 hub: {HUB_SKILLS}  ({report.hub_count} 个技能)"
                 if report.hub_ok else f"规范 hub 尚未建立: {HUB_SKILLS}")

    if report.duplicates:
        total = sum(d.wasted for d in report.duplicates)
        lines.append(f"\n重复技能副本 {len(report.duplicates)} 组，冗余约 {human_size(total)}：")
        for dup in report.duplicates:
            lines.append(f"  • {dup.name}  ({len(dup.locations)} 份, 冗余 {human_size(dup.wasted)})")
            for loc in dup.locations:
                lines.append(f"      {loc}")
    else:
        lines.append("\n未发现重复技能副本。")

    if report.dangling:
        lines.append(f"\n失效链接 {len(report.dangling)} 条：")
        for path, note in report.dangling:
            lines.append(f"  • {path}  —— {note}")

    if report.reclaimable:
        total = sum(size for _, _, size in report.reclaimable)
        lines.append(f"\n可回收缓存/备份，合计 {human_size(total)}：")
        for path, note, size in sorted(report.reclaimable, key=lambda x: -x[2]):
            lines.append(f"  • {human_size(size):>7}  {path}")
            lines.append(f"            {note}")

    if report.unmanaged:
        lines.append(f"\nhub 中未纳管的真实目录 {len(report.unmanaged)} 个（建议 `hub adopt` 收编）：")
        for path in report.unmanaged:
            lines.append(f"  • {path}")

    return "\n".join(lines)
