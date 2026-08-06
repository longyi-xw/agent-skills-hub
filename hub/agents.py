"""主机上各 AI agent 的技能目录注册表（macOS / Linux / Windows 通用）。

采用「按技能粒度」建链而不是整目录替换，这样 agent 自带的内置技能
（如 ~/.codex/skills/.system、~/.grok/skills/*）不会被破坏。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from .config import HUB_SKILLS
from .util import IS_WINDOWS


def _config_home() -> Path:
    if IS_WINDOWS:
        return Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))


@dataclass(frozen=True)
class AgentSpec:
    id: str
    name: str
    global_dir: Path
    project_dir: str                    # 相对项目根的技能目录
    native_hub: bool = False            # True 表示该 agent 直接读规范 hub，无需建链
    aliases: tuple[str, ...] = field(default_factory=tuple)


_H = Path.home()

AGENTS: tuple[AgentSpec, ...] = (
    AgentSpec("claude", "Claude Code", _H / ".claude" / "skills", ".claude/skills"),
    AgentSpec("codex", "OpenAI Codex", _H / ".codex" / "skills", ".agents/skills"),
    AgentSpec("cursor", "Cursor", _H / ".cursor" / "skills", ".agents/skills"),
    AgentSpec("windsurf", "Windsurf / Codeium", _H / ".codeium" / "skills", ".agents/skills",
              aliases=("codeium",)),
    AgentSpec("grok", "Grok CLI", _H / ".grok" / "skills", ".agents/skills"),
    AgentSpec("gemini", "Gemini CLI", _H / ".gemini" / "skills", ".agents/skills"),
    AgentSpec("antigravity", "Antigravity", _H / ".antigravity" / "skills", ".agents/skills"),
    AgentSpec("opencode", "OpenCode", _config_home() / "opencode" / "skills", ".agents/skills"),
    AgentSpec("copilot", "GitHub Copilot", _H / ".copilot" / "skills", ".agents/skills"),
    AgentSpec("qwen", "Qwen Code", _H / ".qwen" / "skills", ".agents/skills"),
    AgentSpec("iflow", "iFlow CLI", _H / ".iflow" / "skills", ".agents/skills"),
    AgentSpec("kimi", "Kimi Code CLI", _H / ".kimi" / "skills", ".agents/skills"),
    AgentSpec("trae", "Trae", _H / ".trae" / "skills", ".agents/skills"),
    AgentSpec("droid", "Factory Droid", _H / ".factory" / "skills", ".agents/skills"),
    # 以下 agent 原生读取 ~/.agents/skills，本身就是规范 hub
    AgentSpec("cline", "Cline", HUB_SKILLS, ".agents/skills", native_hub=True),
    AgentSpec("amp", "Amp", HUB_SKILLS, ".agents/skills", native_hub=True),
    AgentSpec("zed", "Zed", HUB_SKILLS, ".agents/skills", native_hub=True),
    AgentSpec("warp", "Warp", HUB_SKILLS, ".agents/skills", native_hub=True),
)

BY_ID = {a.id: a for a in AGENTS}
for _a in AGENTS:
    for _alias in _a.aliases:
        BY_ID[_alias] = _a


def resolve(agent_id: str) -> AgentSpec | None:
    return BY_ID.get(agent_id.strip().lower())


def detected() -> list[AgentSpec]:
    """返回本机确实装了的 agent —— 技能目录或其父目录存在即算。"""
    found = []
    for spec in AGENTS:
        if spec.native_hub:
            continue
        if spec.global_dir.exists() or spec.global_dir.parent.exists():
            found.append(spec)
    return found


def all_ids() -> list[str]:
    return [a.id for a in AGENTS]
