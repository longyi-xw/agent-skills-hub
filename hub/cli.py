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
from . import manifest as manifest_mod
from . import search as search_mod
from . import sources as sources_mod
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

    # 按索引下载外部技能到缓存（这是「不存内容、按需下载」的核心）
    manifest_entries = manifest_mod.entries()
    if manifest_entries:
        header("下载索引技能")
        dl, failed = 0, 0
        for name, ok_flag, msg in manifest_mod.fetch_all(update=args.update):
            if ok_flag:
                dl += 1
                if args.update or "已下载" in msg:
                    info(f"{green('▽')} {name}  {dim(msg)}")
            else:
                failed += 1
                warn(f"{name}: {msg}")
        ok(f"索引技能就绪 {dl}/{len(manifest_entries)}" + (f"，{failed} 个失败" if failed else ""))

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

    def _scope_tag(skill) -> str:
        if skill.origin == "indexed":
            return cyan("[索引:已装]") if skill.installed else dim("[索引:待同步]")
        return cyan("[team]") if skill.scope == "team" else yellow("[local]")

    for category, items in grouped.items():
        header(f"{registry.category_label(category)}  {dim(category)}")
        for skill in items:
            mark = green("●") if skill.name in active else dim("○")
            suffix = dim("  ↓" + skill.source) if skill.origin == "indexed" else ""
            print(f"  {mark} {bold(skill.name):<34} {_scope_tag(skill)}{suffix}")
            if skill.description and not args.quiet:
                desc = skill.description
                print(f"      {dim(desc[:110] + ('…' if len(desc) > 110 else ''))}")
            if skill.tags and not args.quiet:
                print(f"      {dim('适用: ' + ' · '.join(skill.tags[:6]))}")

    idx = sum(1 for s in skills if s.origin == "indexed")
    print(f"\n{dim('● = 当前组合已启用    ○ = 未启用    [索引] = 不存内容，sync 时下载')}")
    print(dim(f"共 {len(skills)} 个技能（原创 {len(skills) - idx} + 索引 {idx}），"
              f"{sum(1 for s in skills if s.name in active)} 个已启用"))
    return 0


# ----------------------------------------------------------------------- new


SKILL_CREATOR_HINT = (
    "本命令用于**从零创作**技能，默认遵循 skill-creator 方法论：\n"
    "  1. 先想清楚「agent 在什么场景下、缺了什么会失败」——这决定 description 的触发词\n"
    "  2. SKILL.md 只写触发条件 + 主流程 + 反面案例；细节拆到 references/ 按需加载\n"
    "  3. 把 frontmatter 里的 summary 占位改成真实用途（会进 README 清单，validate 会拦）\n"
    "  4. 写完用 `skills-hub validate <name>` 自检\n"
    "  （若已 vendor 了 skill-creator 技能，可让 agent 直接调用它协助创作）"
)


def cmd_new(args) -> int:
    try:
        path = scaffold.create(args.name, args.category, args.scope,
                               args.description or "", summary=args.summary or "")
    except (ValueError, FileExistsError) as exc:
        die(str(exc))
    ok(f"已创建 {path}")
    header("下一步 · skill-creator 方法论")
    for line in SKILL_CREATOR_HINT.split("\n"):
        info(line)
    creator = registry.index().get("skill-creator")
    if creator:
        info(dim(f"参考已装的 skill-creator：{creator.skill_file}"))
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


def _parse_add_ref(ref: str) -> tuple[str, str, str | None]:
    """把 add 引用解析成 (source, skill_name, path)。

      <源id>:<技能>            → source=源id, name=技能, path=None
      owner/repo               → source=owner/repo, name=repo名, path=None(自动找)
      owner/repo:path/to/skill → source=owner/repo, name=末段, path=路径
    """
    if ":" in ref and "/" not in ref.split(":", 1)[0]:
        src, skill = ref.split(":", 1)
        if sources_mod.get(src):
            return src, skill, None
    if ":" in ref:
        repo_part, sub = ref.split(":", 1)
        return repo_part, Path(sub).name, sub
    parts = ref.split("/")
    if len(parts) > 2:
        repo_part = "/".join(parts[:2])
        sub = "/".join(parts[2:])
        return repo_part, Path(sub).name, sub
    return ref, parts[-1], None


def cmd_add(args) -> int:
    """把一个外部技能加入索引并下载（不拷贝内容进仓库；区别于 new 的从零创作）。"""
    header(f"加入索引 · {args.ref}")
    source, name, path = _parse_add_ref(args.ref)
    name = args.name or name

    manual_tags = [t.strip() for t in (args.tags or "").split(",") if t.strip()]
    manifest_mod.add_entry(name, source, args.category, path=path,
                           ref=args.ref_version or "",
                           description=args.description or "", tags=manual_tags or None)
    ok(f"已写入索引：{name}  ←  {source}" + (f":{path}" if path else ""))

    entry = manifest_mod.get(name)
    fetched, msg = manifest_mod.fetch(entry, update=True)
    if not fetched:
        manifest_mod.remove_entry(name)
        die(f"下载失败，已回滚索引条目：{msg}")
    ok(f"已下载到缓存：{msg}")

    # 从下载到的 SKILL.md 自动回填描述/标签，让索引条目自描述（未提供时）
    content = manifest_mod.installed_dir(entry) / "SKILL.md"
    if content.is_file():
        fm = registry.parse_frontmatter(content.read_text(encoding="utf-8"))
        auto_tags = fm.get("tags")
        if isinstance(auto_tags, str):
            auto_tags = [t.strip() for t in auto_tags.split(",") if t.strip()]
        manifest_mod.update_entry_meta(
            name,
            description=str(fm.get("description", "")).strip(),
            tags=auto_tags if isinstance(auto_tags, list) else None,
        )
        desc = manifest_mod.get(name).description
        if desc:
            info(dim(f"用途：{desc[:100]}"))

    issues = validate.validate([name])
    errors, warns = validate.summarize(issues)
    for issue in issues:
        icon = red("✗") if issue.severity == validate.SEVERITY_ERROR else yellow("!")
        print(f"  {icon} {issue.message}")
    if errors:
        warn(f"该技能有 {errors} 个校验问题（不影响使用，仅提示）")
    ok(f"就绪。加入某个组合或 `skills-hub sync` 后即可被各 agent 使用")
    info(dim("卸载: skills-hub uninstall " + name + "   更新: skills-hub update " + name))
    info(dim("从零创作技能请用 `skills-hub new`；本命令用于索引在线已有技能"))
    return 0


def cmd_update(args) -> int:
    names = args.names
    targets = [manifest_mod.get(n) for n in names] if names else manifest_mod.entries()
    header("更新索引技能")
    changed = 0
    for entry in targets:
        if entry is None:
            warn(f"索引中没有: {names}")
            continue
        before = manifest_mod.current_ref(entry)
        ok_flag, msg = manifest_mod.fetch(entry, update=True)
        after = manifest_mod.current_ref(entry)
        if ok_flag:
            moved = before != after and before != "-" and after != "-"
            mark = green("▲ " + before + "→" + after) if moved else dim("已是最新")
            print(f"  {entry.name:<28} {mark}")
            changed += 1 if moved else 0
        else:
            warn(f"{entry.name}: {msg}")
    ok(f"更新完成，{changed} 个有变化。运行 `skills-hub sync` 让改动生效")
    return 0


def cmd_uninstall(args) -> int:
    entry = manifest_mod.get(args.name)
    if entry is None:
        die(f"索引中没有技能 '{args.name}'（原创技能请直接删目录或用 promote 反向操作）")
    manifest_mod.remove_entry(args.name)
    ok(f"已从索引移除 {args.name}")
    # 从 hub / agent 目录解链
    dst = linker.HUB_SKILLS / args.name
    if linker.is_link(dst):
        linker.remove_link(dst)
    for agent_id in load_state().get("agents") or []:
        spec = agents_mod.resolve(agent_id)
        if spec and not spec.native_hub:
            adst = spec.global_dir / args.name
            if linker.is_link(adst):
                linker.remove_link(adst)
    if args.purge:
        import shutil
        clone = manifest_mod._clone_dir(entry)
        # 只有当没有其它索引条目共用该克隆时才删
        others = [e for e in manifest_mod.entries() if manifest_mod._clone_dir(e) == clone]
        if not others and clone.exists() and str(clone).startswith(str(manifest_mod.SOURCES_CACHE)):
            shutil.rmtree(clone, ignore_errors=True)
            ok(f"已清理缓存 {clone}")
    ok("重装：skills-hub add 回来再 sync；或把条目加回 manifest.json")
    return 0


def cmd_search(args) -> int:
    result = search_mod.search(args.query, want_network=not args.no_net)

    if args.json:
        print(json.dumps({
            "repo": [h.__dict__ for h in result.repo],
            "sources": [h.__dict__ for h in result.sources],
            "network": [h.__dict__ for h in result.network],
            "network_kind": result.network_kind,
            "fallback_urls": result.fallback_urls,
        }, indent=2, ensure_ascii=False))
        return 0

    def _row(hit: search_mod.Hit, addable: bool) -> None:
        add_ref = cyan(hit.ref) if addable else dim(hit.ref)
        print(f"  {bold(hit.name):<32} {dim(hit.extra)}")
        if hit.description:
            print(f"      {dim(hit.description[:96])}")
        if addable:
            print(f"      {dim('导入:')} skills-hub add {add_ref} --category <分类>")

    header(f"搜索 “{args.query}”")

    print(bold("\n【仓库】") + dim("  已在本地仓库中"))
    if result.repo:
        for hit in result.repo[:12]:
            mark = green("●") if hit.name in linker.hub_entries() else dim("○")
            print(f"  {mark} {bold(hit.name):<30} {dim(hit.extra)}")
            if hit.description:
                print(f"      {dim(hit.description[:96])}")
    else:
        print(dim("  （无）"))

    if result.sources:
        print(bold("\n【已登记源】") + dim("  已缓存的外部源，可直接导入"))
        for hit in result.sources[:12]:
            _row(hit, addable=True)

    if result.network_kind == "structured" and result.network:
        print(bold("\n【网络·结构化】") + dim("  GitHub 检索，结果可直接导入"))
        for hit in result.network:
            _row(hit, addable=True)
    elif result.network_kind == "general":
        print(bold("\n【网络·通用兜底】") + dim("  结构化无命中，可在以下入口继续查找"))
        for label, url in result.fallback_urls:
            print(f"  · {label}: {cyan(url)}")
    elif result.network_kind == "skipped":
        print(dim("\n（本地已有结果，未触发网络搜索；加 --net-only 可强制联网）"))

    return 0


def cmd_sources(args) -> int:
    action = args.action or "list"

    if action == "list":
        header("外部技能源")
        for source in sources_mod.all_sources():
            cached = source.cache_dir().is_dir() or (source.local_mirror and source.local_mirror.is_dir())
            state = green("已缓存") if cached else dim("未同步")
            trust_c = green if source.trust == "high" else yellow
            print(f"  {bold(source.id):<14} {state:<16} {trust_c('信任:' + source.trust):<20} {dim(source.repo)}")
            if source.description:
                print(f"      {dim(source.description[:92])}")
        print(f"\n{dim('同步: skills-hub sources sync [id]   新增: skills-hub sources add <id> <owner/repo>')}")
        return 0

    if action == "sync":
        targets = [sources_mod.get(args.id)] if args.id else sources_mod.all_sources()
        for source in targets:
            if source is None:
                die(f"未知源: {args.id}")
            ok_flag, msg = sources_mod.sync_source(source)
            (ok if ok_flag else warn)(f"{source.id}: {msg}")
            if ok_flag:
                n = len(sources_mod.index_source(source))
                info(dim(f"扫描到 {n} 个技能"))
        return 0

    if action == "add":
        if not args.id or not args.repo:
            die("用法: skills-hub sources add <id> <owner/repo> [--skills-path skills] [--license MIT]")
        try:
            sources_mod.add_source(args.id, args.repo, args.name or "",
                                   args.skills_path, args.license or "unknown")
        except ValueError as exc:
            die(str(exc))
        ok(f"已登记源 {args.id} → {args.repo}")
        info("同步: skills-hub sources sync " + args.id)
        return 0

    if action == "remove":
        if not args.id:
            die("用法: skills-hub sources remove <id>")
        if sources_mod.remove_source(args.id):
            ok(f"已移除源 {args.id}")
        else:
            warn(f"源 {args.id} 不存在")
        return 0

    die(f"未知子命令: {action}")
    return 1


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
    idx = [s for s in skills if s.origin == "indexed"]
    installed_idx = sum(1 for s in idx if s.installed)
    print(f"  原创技能    {len(skills) - len(idx)} 个"
          f"  (team {sum(1 for s in skills if s.scope == 'team')} /"
          f" local {sum(1 for s in skills if s.scope == 'local')})")
    print(f"  索引技能    {len(idx)} 个  (已下载 {installed_idx})")

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


def cmd_readme(args) -> int:
    from . import readme as readme_mod

    if args.print:
        print(readme_mod.generate_inventory())
        return 0

    up_to_date, missing = readme_mod.sync(check_only=args.check)
    for key in missing:
        warn(f"README 里找不到 <!-- {key}:BEGIN --> / <!-- {key}:END --> 标记，该块未生成")
    if missing:
        # 标记缺失时内容不可能是最新的，别用「已是最新」误导
        die(f"{len(missing)} 个生成块缺少标记，请先在 README 中放置标记对")

    if args.check:
        if up_to_date:
            ok("README 技能清单已是最新")
            return 0
        fail_msg = "README 技能清单已过期，请运行 `skills-hub readme --sync`"
        print(f"{red('✗')} {fail_msg}", file=sys.stderr)
        return 1

    if up_to_date:
        ok("README 已是最新，无需改动")
    else:
        ok(f"已更新 {readme_mod.readme_path()}")
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

    p = sub.add_parser("sync", help="拉取团队索引 + 下载外部技能 + 重建所有链接")
    p.add_argument("--profile", help="同步后启用的组合，默认沿用当前")
    p.add_argument("--no-pull", action="store_true", help="跳过 git pull")
    p.add_argument("--update", action="store_true", help="顺便把索引技能更新到在线最新")
    p.add_argument("--force", action="store_true", help="校验失败也继续")
    p.set_defaults(func=cmd_sync)

    p = sub.add_parser("list", aliases=["ls"], help="查看技能")
    p.add_argument("--category", help="按分类过滤")
    p.add_argument("--scope", action="append", choices=list(SCOPES), help="按作用域过滤")
    p.add_argument("--profile", help="只看某组合内的技能")
    p.add_argument("--json", action="store_true")
    p.add_argument("-q", "--quiet", action="store_true", help="不显示描述")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("new", help="从零创作技能（默认走 skill-creator 方法论）")
    p.add_argument("name")
    p.add_argument("--category", required=True)
    p.add_argument("--scope", choices=list(SCOPES), default="local")
    p.add_argument("--description")
    p.add_argument("--summary", help="一句话用途，显示在 README 技能清单里")
    p.set_defaults(func=cmd_new)

    p = sub.add_parser("add", help="把在线技能加入索引并下载（owner/repo[:path] 或 <源id>:<技能>）")
    p.add_argument("ref", help="owner/repo、owner/repo:路径、或 <源id>:<技能名>")
    p.add_argument("--category", required=True)
    p.add_argument("--name", help="重命名")
    p.add_argument("--ref-version", help="锁定分支/标签/commit，缺省取最新")
    p.add_argument("--description", help="用途说明（缺省自动从技能 frontmatter 回填）")
    p.add_argument("--tags", help="应用范围标签，逗号分隔（缺省自动回填）")
    p.set_defaults(func=cmd_add)

    p = sub.add_parser("update", help="更新索引技能到在线最新（默认全部）")
    p.add_argument("names", nargs="*")
    p.set_defaults(func=cmd_update)

    p = sub.add_parser("uninstall", aliases=["rm-skill"], help="从索引移除并解链某技能")
    p.add_argument("name")
    p.add_argument("--purge", action="store_true", help="连同下载缓存一起删除")
    p.set_defaults(func=cmd_uninstall)

    p = sub.add_parser("search", help="统一搜索：仓库 → 已登记源 → 网络（结构化优先）")
    p.add_argument("query")
    p.add_argument("--json", action="store_true")
    p.add_argument("--no-net", action="store_true", help="只搜本地，不联网")
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("sources", help="外部源：list / sync / add / remove")
    p.add_argument("action", nargs="?", choices=["list", "sync", "add", "remove"])
    p.add_argument("id", nargs="?")
    p.add_argument("repo", nargs="?", help="add 时的 owner/repo")
    p.add_argument("--name")
    p.add_argument("--skills-path", default="skills")
    p.add_argument("--license")
    p.set_defaults(func=cmd_sources)

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

    p = sub.add_parser("readme", help="从实时数据重新生成 README 的技能清单与组合表")
    p.add_argument("--sync", action="store_true", help="写回 README（默认行为）")
    p.add_argument("--check", action="store_true", help="只校验是否过期，CI 用（过期返回 1）")
    p.add_argument("--print", action="store_true", help="只打印清单，不写文件")
    p.set_defaults(func=cmd_readme)

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
