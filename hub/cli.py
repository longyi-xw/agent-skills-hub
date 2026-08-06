"""skills-hub 命令行入口。"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from . import agents as agents_mod
from . import doctor as doctor_mod
from . import linker, profiles, registry, scaffold, validate
from .config import (
    HUB_HOME,
    HUB_SKILLS,
    SCOPES,
    load_categories,
    load_state,
    repo_root,
    save_state,
)
from .util import (
    bold,
    cyan,
    die,
    dim,
    green,
    header,
    human_size,
    info,
    ok,
    red,
    run,
    warn,
    yellow,
)

VERSION = "1.0.0"


# ------------------------------------------------------------------ 辅助输出


def _print_sync(result: linker.SyncResult, label: str) -> None:
    parts = []
    if result.linked:
        parts.append(f"接入 {len(result.linked)}")
    if result.removed:
        parts.append(f"移除 {len(result.removed)}")
    if result.skipped:
        parts.append(f"跳过 {len(result.skipped)}")
    ok(f"{label}: {', '.join(parts) if parts else '无变更'}")
    for name, reason in result.skipped:
        info(dim(f"跳过 {name} —— {reason}"))


# ------------------------------------------------------------------- install


def cmd_install(args) -> int:
    root = repo_root()
    state = load_state()
    state["repo"] = str(root)
    save_state(state)

    header(f"skills-hub 安装 · 仓库 {root}")
    HUB_SKILLS.mkdir(parents=True, exist_ok=True)
    ok(f"规范 hub: {HUB_SKILLS}")

    profile = args.profile or state.get("profile") or "default"
    if profile not in profiles.available() and profile != "all":
        warn(f"组合 '{profile}' 不存在，回退到 all")
        profile = "all"

    hub_result, _ = linker.apply_profile(profile, "copy" if args.copy else None)
    _print_sync(hub_result, f"组合 '{profile}' 写入 hub")
    info(linker.link_mode_note(hub_result.mode))

    if args.agent:
        wanted = [a.strip() for a in args.agent.split(",") if a.strip()]
        specs = []
        for agent_id in wanted:
            spec = agents_mod.resolve(agent_id)
            if spec is None:
                warn(f"未知 agent: {agent_id}")
            else:
                specs.append(spec)
    else:
        specs = agents_mod.detected()

    if not specs:
        warn("未检测到可接入的 agent，可稍后用 `skills-hub agent link <id>` 手动接入")
    for spec in specs:
        result = linker.link_agent(spec, "copy" if args.copy else None)
        _print_sync(result, f"{spec.name} ({spec.global_dir})")

    header("完成")
    info(f"当前组合: {profile}   技能数: {len(linker.hub_entries())}")
    info("下一步: skills-hub status / skills-hub doctor")
    return 0


# ---------------------------------------------------------------------- sync


def cmd_sync(args) -> int:
    root = repo_root()
    header(f"同步 · {root}")

    if not args.no_pull and (root / ".git").exists():
        result = run(["git", "pull", "--ff-only"], cwd=root)
        if result.returncode == 0:
            ok(f"git pull: {result.stdout.strip().splitlines()[-1] if result.stdout.strip() else '已是最新'}")
        else:
            warn(f"git pull 失败（继续用本地内容）: {result.stderr.strip().splitlines()[-1] if result.stderr.strip() else ''}")

    issues = validate.validate()
    errors, _ = validate.summarize(issues)
    if errors and not args.force:
        for issue in issues:
            if issue.severity == validate.SEVERITY_ERROR:
                print(f"  {red('✗')} {issue.skill}: {issue.message}")
        die(f"{errors} 个技能未通过校验，同步中止（--force 可强制继续）")

    state = load_state()
    profile = args.profile or state.get("profile") or "default"
    hub_result, per_agent = linker.apply_profile(profile)
    _print_sync(hub_result, f"组合 '{profile}'")
    for agent_id, result in per_agent.items():
        _print_sync(result, agents_mod.resolve(agent_id).name)
    return 0


# ---------------------------------------------------------------------- list


def cmd_list(args) -> int:
    skills = registry.discover(tuple(args.scope) if args.scope else SCOPES)
    if args.category:
        skills = [s for s in skills if s.category == args.category]
    if args.profile:
        wanted = set(profiles.resolve(args.profile))
        skills = [s for s in skills if s.name in wanted]

    active = set(linker.hub_entries())

    if args.json:
        print(json.dumps([{
            "name": s.name, "scope": s.scope, "category": s.category,
            "status": s.status, "tags": s.tags, "active": s.name in active,
            "description": s.description, "path": str(s.path),
        } for s in skills], indent=2, ensure_ascii=False))
        return 0

    if not skills:
        warn("没有匹配的技能")
        return 0

    grouped: dict[str, list] = {}
    for skill in skills:
        grouped.setdefault(skill.category, []).append(skill)

    for category, items in grouped.items():
        header(f"{registry.category_label(category)}  {dim(category)}")
        for skill in items:
            mark = green("●") if skill.name in active else dim("○")
            scope_tag = cyan("[team]") if skill.scope == "team" else yellow("[local]")
            print(f"  {mark} {bold(skill.name):<34} {scope_tag}")
            if skill.description and not args.quiet:
                desc = skill.description
                print(f"      {dim(desc[:110] + ('…' if len(desc) > 110 else ''))}")

    print(f"\n{dim('● = 当前组合已启用    ○ = 仓库中存在但未启用')}")
    print(dim(f"共 {len(skills)} 个技能，其中 {sum(1 for s in skills if s.name in active)} 个已启用"))
    return 0


# ----------------------------------------------------------------------- new


def cmd_new(args) -> int:
    try:
        path = scaffold.create(args.name, args.category, args.scope, args.description or "")
    except (ValueError, FileExistsError) as exc:
        die(str(exc))
    ok(f"已创建 {path}")
    info(f"编辑 {path / 'SKILL.md'}，然后 `skills-hub validate {path.name}`")
    if args.scope == "local":
        info(dim("local 技能不会进 git；打磨好后用 `skills-hub promote` 提升到 team"))
    return 0


def cmd_adopt(args) -> int:
    try:
        path = scaffold.adopt(Path(args.path), args.category, args.scope, args.name, args.move)
    except (FileNotFoundError, FileExistsError) as exc:
        die(str(exc))
    ok(f"已收编到 {path}")
    return 0


def cmd_promote(args) -> int:
    try:
        path = scaffold.promote(args.name, args.category)
    except (KeyError, FileExistsError) as exc:
        die(str(exc))
    ok(f"已提升为 team 技能：{path}")
    info("接下来：skills-hub validate → git commit → 提 PR，评审通过后其他成员 `skills-hub sync` 即可获得")
    return 0


# ------------------------------------------------------------------ validate


def cmd_validate(args) -> int:
    issues = validate.validate(args.names or None)
    errors, warns = validate.summarize(issues)

    for issue in issues:
        icon = red("✗") if issue.severity == validate.SEVERITY_ERROR else yellow("!")
        print(f"  {icon} {bold(issue.skill)}: {issue.message}")

    total = len(registry.discover())
    if not issues:
        ok(f"{total} 个技能全部通过校验")
        return 0
    print()
    if errors:
        fail_line = f"{errors} 个错误"
        print(f"{red('✗')} {fail_line}，{warns} 个警告（共检查 {total} 个技能）")
        return 1
    ok(f"无错误，{warns} 个警告（共检查 {total} 个技能）")
    return 0


# ------------------------------------------------------------------- profile


def cmd_profile(args) -> int:
    if args.action in (None, "list"):
        state = load_state()
        current = state.get("profile")
        header("技能组合")
        for name in profiles.available() + ["all"]:
            mark = green("●") if name == current else dim("○")
            try:
                count = len(profiles.resolve(name))
            except KeyError:
                count = 0
            print(f"  {mark} {bold(name):<20} {dim(str(count) + ' 个技能')}  {profiles.label(name)}")
        print(f"\n{dim('切换: skills-hub profile use <name>')}")
        return 0

    if args.action == "show":
        name = args.name or load_state().get("profile")
        try:
            names = profiles.resolve(name)
        except KeyError:
            die(f"组合 '{name}' 不存在")
        header(f"{name} · {profiles.label(name)}")
        known = registry.index()
        for skill_name in names:
            skill = known[skill_name]
            print(f"  {bold(skill_name):<34} {dim(skill.category)}")
        gap = profiles.missing(name)
        if gap:
            warn(f"组合中点名但仓库缺失: {', '.join(gap)}")
        print(f"\n{dim(f'共 {len(names)} 个技能')}")
        return 0

    if args.action == "use":
        if not args.name:
            die("用法: skills-hub profile use <name>")
        try:
            hub_result, per_agent = linker.apply_profile(args.name)
        except KeyError:
            die(f"组合 '{args.name}' 不存在，可用：{', '.join(profiles.available() + ['all'])}")
        _print_sync(hub_result, f"切换到 '{args.name}'")
        for agent_id, result in per_agent.items():
            _print_sync(result, agents_mod.resolve(agent_id).name)
        info(f"当前启用 {len(linker.hub_entries())} 个技能")
        return 0

    if args.action == "create":
        if not args.name:
            die("用法: skills-hub profile create <name> [--categories a,b] [--skills x,y]")
        data = {
            "label": args.label or args.name,
            "description": "",
            "extends": [e for e in (args.extends or "").split(",") if e],
            "categories": [c for c in (args.categories or "").split(",") if c],
            "skills": [s for s in (args.skills or "").split(",") if s],
            "exclude": [],
        }
        profiles.save(args.name, data)
        ok(f"已创建组合 {profiles.path_for(args.name)}")
        return 0

    die(f"未知子命令: {args.action}")
    return 1


# --------------------------------------------------------------------- agent


def cmd_agent(args) -> int:
    if args.action in (None, "list"):
        state = load_state()
        linked = set(state.get("agents") or [])
        header("Agent 接入状态")
        for spec in agents_mod.AGENTS:
            if spec.native_hub:
                status = green("原生读取 hub")
            elif spec.id in linked:
                status = green("已接入")
            elif spec.global_dir.exists() or spec.global_dir.parent.exists():
                status = yellow("已安装未接入")
            else:
                status = dim("未安装")
            print(f"  {bold(spec.id):<14} {status:<24} {dim(str(spec.global_dir))}")
        print(f"\n{dim('接入: skills-hub agent link <id>   全部: --all')}")
        return 0

    if args.action == "link":
        specs = agents_mod.detected() if args.all else _specs_from(args.name)
        for spec in specs:
            result = linker.link_agent(spec)
            _print_sync(result, spec.name)
        return 0

    if args.action == "unlink":
        for spec in _specs_from(args.name):
            removed = linker.unlink_agent(spec)
            ok(f"{spec.name}: 移除 {len(removed)} 条链接")
        return 0

    die(f"未知子命令: {args.action}")
    return 1


def _specs_from(names: str | None):
    if not names:
        die("请指定 agent id，或用 --all")
    specs = []
    for name in names.split(","):
        spec = agents_mod.resolve(name)
        if spec is None:
            die(f"未知 agent '{name}'，可用：{', '.join(agents_mod.all_ids())}")
        specs.append(spec)
    return specs


# -------------------------------------------------------------------- status


def cmd_status(args) -> int:
    state = load_state()
    root = repo_root()
    skills = registry.discover()
    active = linker.hub_entries()

    header("skills-hub 状态")
    print(f"  仓库        {root}")
    print(f"  规范 hub    {HUB_SKILLS}")
    print(f"  链接方式    {state.get('link_mode') or '未初始化'}")
    print(f"  当前组合    {bold(str(state.get('profile')))}  ({len(active)} 个技能已启用)")
    print(f"  仓库技能    {len(skills)} 个"
          f"  (team {sum(1 for s in skills if s.scope == 'team')} /"
          f" local {sum(1 for s in skills if s.scope == 'local')})")

    linked = state.get("agents") or []
    print(f"  已接入      {', '.join(linked) if linked else '（无）'}")

    if (root / ".git").exists():
        branch = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=root).stdout.strip()
        dirty = run(["git", "status", "--porcelain"], cwd=root).stdout.strip()
        print(f"  git         {branch}{'  ' + yellow('有未提交改动') if dirty else '  干净'}")
    return 0


# -------------------------------------------------------------- doctor/clean


def cmd_doctor(args) -> int:
    report = doctor_mod.scan([Path(p).expanduser() for p in (args.extra or [])])
    if args.json:
        print(json.dumps({
            "duplicates": [{"name": d.name, "locations": [str(p) for p in d.locations],
                            "wasted": d.wasted} for d in report.duplicates],
            "dangling": [[str(p), n] for p, n in report.dangling],
            "reclaimable": [[str(p), n, s] for p, n, s in report.reclaimable],
            "unmanaged": [str(p) for p in report.unmanaged],
        }, indent=2, ensure_ascii=False))
        return 0
    header("环境体检")
    print(doctor_mod.format_report(report))
    if report.reclaimable or report.dangling:
        print(f"\n{dim('清理: skills-hub clean          (默认只预演)')}")
        print(dim("执行: skills-hub clean --apply"))
    return 0


def cmd_clean(args) -> int:
    report = doctor_mod.scan()
    targets = list(report.reclaimable)
    total = sum(size for _, _, size in targets)

    header("清理预演" if not args.apply else "执行清理")
    if not targets and not report.dangling:
        ok("没有需要清理的内容")
        return 0

    for path, note, size in sorted(targets, key=lambda x: -x[2]):
        print(f"  {human_size(size):>7}  {path}")
        print(f"           {dim(note)}")
    for path, note in report.dangling:
        print(f"  {'失效':>7}  {path}  {dim(note)}")

    if not args.apply:
        print(f"\n{yellow('预演模式')}：以上共可回收 {bold(human_size(total))}，加 --apply 实际删除")
        return 0

    freed = 0
    for path, _note, size in targets:
        try:
            shutil.rmtree(path)
            freed += size
            ok(f"已删除 {path}")
        except OSError as exc:
            warn(f"删除失败 {path}: {exc}")
    for path, _note in report.dangling:
        try:
            path.unlink()
            ok(f"已移除失效链接 {path}")
        except OSError as exc:
            warn(f"移除失败 {path}: {exc}")
    print(f"\n共释放 {bold(human_size(freed))}")
    return 0


# ------------------------------------------------------------------- project


def cmd_project(args) -> int:
    project = Path(args.path).expanduser().resolve()
    if not project.is_dir():
        die(f"目录不存在: {project}")
    try:
        result = linker.project_link(project)
    except FileExistsError as exc:
        die(str(exc))
    ok(f"已在项目中挂载技能: {result['path']}  ({result['mode']})")
    info(dim("建议把 .agents/ 加入项目 .gitignore"))
    return 0


def cmd_path(args) -> int:
    print(HUB_SKILLS if not args.repo else repo_root())
    return 0


# --------------------------------------------------------------------- 解析


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="skills-hub",
        description="通用 Agent 技能仓库管理器 —— 单一副本、多 agent 共享、团队/本地双轨、组合可切换",
    )
    parser.add_argument("--version", action="version", version=f"skills-hub {VERSION}")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("install", help="首次安装：建立规范 hub 并接入本机 agent")
    p.add_argument("--profile", help="安装时启用的技能组合")
    p.add_argument("--agent", help="指定接入的 agent（逗号分隔），默认自动检测")
    p.add_argument("--copy", action="store_true", help="用复制代替软链（无软链权限时）")
    p.set_defaults(func=cmd_install)

    p = sub.add_parser("sync", help="拉取团队技能并重建所有链接")
    p.add_argument("--profile", help="同步后启用的组合，默认沿用当前")
    p.add_argument("--no-pull", action="store_true", help="跳过 git pull")
    p.add_argument("--force", action="store_true", help="校验失败也继续")
    p.set_defaults(func=cmd_sync)

    p = sub.add_parser("list", aliases=["ls"], help="查看技能")
    p.add_argument("--category", help="按分类过滤")
    p.add_argument("--scope", action="append", choices=list(SCOPES), help="按作用域过滤")
    p.add_argument("--profile", help="只看某组合内的技能")
    p.add_argument("--json", action="store_true")
    p.add_argument("-q", "--quiet", action="store_true", help="不显示描述")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("new", help="新建技能")
    p.add_argument("name")
    p.add_argument("--category", required=True)
    p.add_argument("--scope", choices=list(SCOPES), default="local")
    p.add_argument("--description")
    p.set_defaults(func=cmd_new)

    p = sub.add_parser("adopt", help="收编主机上已有的技能进仓库")
    p.add_argument("path")
    p.add_argument("--category", required=True)
    p.add_argument("--scope", choices=list(SCOPES), default="team")
    p.add_argument("--name", help="重命名")
    p.add_argument("--move", action="store_true", help="收编后删除原目录")
    p.set_defaults(func=cmd_adopt)

    p = sub.add_parser("promote", help="把 local 技能提升为 team 技能")
    p.add_argument("name")
    p.add_argument("--category")
    p.set_defaults(func=cmd_promote)

    p = sub.add_parser("validate", help="校验技能（团队评审门禁，CI 同款）")
    p.add_argument("names", nargs="*")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("profile", help="技能组合：list / show / use / create")
    p.add_argument("action", nargs="?", choices=["list", "show", "use", "create"])
    p.add_argument("name", nargs="?")
    p.add_argument("--label")
    p.add_argument("--extends")
    p.add_argument("--categories")
    p.add_argument("--skills")
    p.set_defaults(func=cmd_profile)

    p = sub.add_parser("agent", help="agent 接入：list / link / unlink")
    p.add_argument("action", nargs="?", choices=["list", "link", "unlink"])
    p.add_argument("name", nargs="?")
    p.add_argument("--all", action="store_true")
    p.set_defaults(func=cmd_agent)

    p = sub.add_parser("status", help="查看当前状态")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("doctor", help="体检：重复副本、失效链接、可回收缓存")
    p.add_argument("--extra", action="append", help="额外扫描目录")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("clean", help="清理冗余（默认预演）")
    p.add_argument("--apply", action="store_true", help="实际删除")
    p.set_defaults(func=cmd_clean)

    p = sub.add_parser("project", help="在某个项目里挂载技能")
    p.add_argument("path", nargs="?", default=".")
    p.set_defaults(func=cmd_project)

    p = sub.add_parser("path", help="打印 hub 路径")
    p.add_argument("--repo", action="store_true", help="改为打印仓库路径")
    p.set_defaults(func=cmd_path)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 0
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print()
        return 130


if __name__ == "__main__":
    sys.exit(main())
