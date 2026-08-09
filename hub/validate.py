"""技能校验 —— 团队评审门禁。

`hub validate` 在本地和 CI 里跑同一套规则：只有通过校验的技能才允许
从 local 提升到 team，其他成员 sync 到的因此总是合规的技能。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .config import load_categories
from .registry import Skill, discover

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
DESC_MAX = 1024
BODY_SOFT_MAX = 500          # SKILL.md 正文建议行数上限，超出应拆到 references/
HOME_LEAK_RE = re.compile(r"(/Users/[A-Za-z0-9._-]+|/home/[A-Za-z0-9._-]+|C:\\Users\\[A-Za-z0-9._-]+)")

SEVERITY_ERROR = "error"
SEVERITY_WARN = "warn"


@dataclass
class Issue:
    skill: str
    severity: str
    message: str


def _check(skill: Skill) -> list[Issue]:
    issues: list[Issue] = []

    # 索引技能尚未下载时无内容可校验 —— 跳过（sync 后自然会校验缓存里的真实内容）
    if getattr(skill, "origin", "repo") == "indexed" and not getattr(skill, "installed", True):
        return issues

    def err(msg: str) -> None:
        issues.append(Issue(skill.rel(), SEVERITY_ERROR, msg))

    def warn(msg: str) -> None:
        issues.append(Issue(skill.rel(), SEVERITY_WARN, msg))

    meta = skill.meta
    if not meta:
        err("SKILL.md 缺少 YAML frontmatter")
        return issues

    name = str(meta.get("name", "")).strip()
    if not name:
        err("frontmatter 缺少 name")
    else:
        if not NAME_RE.match(name):
            err(f"name '{name}' 不是 kebab-case（只允许小写字母、数字与连字符）")
        if name != skill.path.name:
            err(f"name '{name}' 与目录名 '{skill.path.name}' 不一致")

    description = str(meta.get("description", "")).strip()
    if not description:
        err("frontmatter 缺少 description —— agent 靠它决定何时触发本技能")
    else:
        if len(description) > DESC_MAX:
            err(f"description 长度 {len(description)} 超过 {DESC_MAX} 字符上限")
        if len(description) < 40:
            warn("description 过短，建议写清「什么场景下触发」，否则 agent 不会命中")
        if not re.search(r"(when|use this|使用本技能|当用户|适用于)", description, re.I):
            warn("description 建议明确触发条件（如「当用户……时使用本技能」）")

    summary = str(meta.get("summary", "")).strip()
    if not summary:
        warn("缺少 summary —— README 技能清单会退化成截断的 description")
    elif "请用一句话写清用途" in summary:
        err("summary 仍是 `new` 生成的占位文字，请改成真实用途")
    elif len(summary) > 60:
        warn(f"summary 长度 {len(summary)} 偏长，清单里建议 30 字以内的一句话")

    categories = load_categories()
    if categories and skill.category not in categories:
        err(f"分类 '{skill.category}' 未在 registry/categories.json 中登记")

    try:
        text = skill.skill_file.read_text(encoding="utf-8")
    except OSError as exc:
        err(f"无法读取 SKILL.md: {exc}")
        return issues

    body = text.split("---", 2)[-1]
    lines = body.count("\n")
    if lines > BODY_SOFT_MAX:
        warn(f"正文 {lines} 行，建议把细节拆到 references/ 下按需加载")

    leak = HOME_LEAK_RE.search(body)
    if leak and skill.scope == "team":
        err(f"正文含本机绝对路径 '{leak.group(0)}'，团队技能不应泄漏个人路径")

    for ref in re.findall(r"\]\((?!https?://|#)([^)]+)\)", body):
        ref_path = (skill.path / ref.split("#")[0]).resolve()
        if not ref_path.exists():
            warn(f"引用的文件不存在: {ref}")

    if skill.scope == "team" and str(meta.get("status", "")).lower() == "draft":
        err("team 作用域下不允许 status: draft —— 请先在 local 打磨")

    return issues


def validate(names: list[str] | None = None) -> list[Issue]:
    skills = discover()
    if names:
        wanted = set(names)
        skills = [s for s in skills if s.name in wanted or s.rel() in wanted]
    issues: list[Issue] = []
    seen_names: dict[str, str] = {}
    for skill in skills:
        issues.extend(_check(skill))
        if skill.name in seen_names and seen_names[skill.name] != skill.scope:
            issues.append(Issue(
                skill.rel(), SEVERITY_WARN,
                f"与 {seen_names[skill.name]} 作用域下的同名技能冲突，local 版本会覆盖 team 版本",
            ))
        seen_names[skill.name] = skill.scope
    return issues


def summarize(issues: list[Issue]) -> tuple[int, int]:
    errors = sum(1 for i in issues if i.severity == SEVERITY_ERROR)
    warns = sum(1 for i in issues if i.severity == SEVERITY_WARN)
    return errors, warns
