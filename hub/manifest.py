"""外部技能索引（manifest）—— 仓库只存指针，sync 时按索引从在线源下载。

核心理念：
  · 仓库不保存外部技能的内容，只在 registry/manifest.json 里登记「从哪个源、
    哪个路径、哪个版本」取。文件因此不会随技能增多而膨胀。
  · sync 读取索引 → 下载/更新到 ~/.agents/.hub-cache → 再链接进 hub。
  · 在线源始终是最新版；改索引里的 ref 再 sync 即可一键更新。
  · 卸载 = 删索引条目；重装 = 加回条目再 sync。

只有**团队原创**、线上不存在的技能才作为内容留在仓库里（它们以本仓库为家）。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import sources as sources_mod
from .config import SOURCES_CACHE, manifest_file
from .util import read_json, run, write_json


@dataclass
class Entry:
    name: str
    source: str          # sources.json 里的源 id，或 "owner/repo"
    category: str
    path: str | None     # 源仓库内技能路径；None → 由源推断
    ref: str             # 分支/标签/commit；"" 或 "latest" → 默认分支
    pin: bool
    description: str      # 用途说明 —— 让人不下载也能看懂这技能干嘛、用在哪
    tags: list[str]      # 应用范围标签


def _load() -> dict:
    data = read_json(manifest_file(), default={"version": 1, "skills": {}})
    return data if isinstance(data, dict) else {"version": 1, "skills": {}}


def entries() -> list[Entry]:
    result = []
    for name, meta in sorted(_load().get("skills", {}).items()):
        if not isinstance(meta, dict):
            continue
        raw_tags = meta.get("tags", [])
        tags = [t.strip() for t in raw_tags.split(",")] if isinstance(raw_tags, str) \
            else [str(t) for t in raw_tags]
        result.append(Entry(
            name=name,
            source=str(meta.get("source", "")),
            category=str(meta.get("category", "misc")),
            path=meta.get("path"),
            ref=str(meta.get("ref", "") or ""),
            pin=bool(meta.get("pin", False)),
            description=str(meta.get("description", "")).strip(),
            tags=[t for t in tags if t],
        ))
    return result


def get(name: str) -> Entry | None:
    for entry in entries():
        if entry.name == name:
            return entry
    return None


def add_entry(name: str, source: str, category: str,
              path: str | None = None, ref: str = "",
              description: str = "", tags: list[str] | None = None) -> None:
    data = _load()
    entry: dict = {"source": source, "category": category}
    if path:
        entry["path"] = path
    if ref:
        entry["ref"] = ref
    if description:
        entry["description"] = description
    if tags:
        entry["tags"] = tags
    data.setdefault("skills", {})[name] = entry
    write_json(manifest_file(), data)


def update_entry_meta(name: str, description: str = "", tags: list[str] | None = None) -> None:
    """回填索引条目的描述/标签（add 下载后自动从 frontmatter 抓取）。"""
    data = _load()
    entry = data.get("skills", {}).get(name)
    if not isinstance(entry, dict):
        return
    if description and not entry.get("description"):
        entry["description"] = description
    if tags and not entry.get("tags"):
        entry["tags"] = tags
    write_json(manifest_file(), data)


def remove_entry(name: str) -> bool:
    data = _load()
    if name in data.get("skills", {}):
        del data["skills"][name]
        write_json(manifest_file(), data)
        return True
    return False


# ------------------------------------------------------- 源解析与缓存定位


def _clone_dir(entry: Entry) -> Path:
    """该条目对应源仓库的克隆缓存目录（同源多技能共享一份克隆）。"""
    src = sources_mod.get(entry.source)
    if src:
        # 有本地镜像的源，直接用镜像根（其内即技能目录）
        if src.local_mirror and src.local_mirror.is_dir():
            return src.local_mirror
        return src.cache_dir()
    # 直接 owner/repo
    return SOURCES_CACHE / entry.source.replace("/", "__")


def _skill_subpath(entry: Entry) -> str:
    if entry.path:
        return entry.path
    src = sources_mod.get(entry.source)
    if src:
        # 有本地镜像时，镜像根下直接是 <name>
        if src.local_mirror and src.local_mirror.is_dir():
            return entry.name
        base = src.skills_path.strip("/")
        return f"{base}/{entry.name}" if base else entry.name
    return entry.name


def installed_dir(entry: Entry) -> Path:
    """条目下载后，其技能内容在本机的目录。"""
    return _clone_dir(entry) / _skill_subpath(entry)


def is_installed(entry: Entry) -> bool:
    return (installed_dir(entry) / "SKILL.md").is_file()


# ---------------------------------------------------------------- 下载/更新


def _repo_url(entry: Entry) -> str | None:
    src = sources_mod.get(entry.source)
    if src:
        if src.local_mirror and src.local_mirror.is_dir():
            return None  # 用镜像，无需下载
        return src.clone_url()
    if "/" in entry.source:
        return f"https://github.com/{entry.source}.git"
    return None


def fetch(entry: Entry, update: bool = False) -> tuple[bool, str]:
    """按条目下载/更新源到缓存。返回 (成功, 信息)。"""
    src = sources_mod.get(entry.source)
    if src and src.local_mirror and src.local_mirror.is_dir():
        return is_installed(entry), f"本地镜像 {src.local_mirror}"

    url = _repo_url(entry)
    if not url:
        return False, f"无法解析源 '{entry.source}'"

    clone = _clone_dir(entry)
    clone.parent.mkdir(parents=True, exist_ok=True)
    ref = entry.ref if entry.ref and entry.ref != "latest" else ""

    if (clone / ".git").is_dir():
        if update and not entry.pin:
            run(["git", "-C", str(clone), "fetch", "--depth", "1", "origin",
                 ref or "HEAD"])
            run(["git", "-C", str(clone), "checkout", ref or "FETCH_HEAD"]) if ref else \
                run(["git", "-C", str(clone), "reset", "--hard", "FETCH_HEAD"])
            msg = "已更新"
        else:
            msg = "已存在缓存"
    else:
        args = ["git", "clone", "--depth", "1"]
        if ref:
            args += ["--branch", ref]
        args += [url, str(clone)]
        res = run(args)
        if res.returncode != 0:
            # 指定 ref 作为分支失败时，退回默认分支再 checkout
            res2 = run(["git", "clone", "--depth", "1", url, str(clone)])
            if res2.returncode != 0:
                return False, (res2.stderr or res.stderr or "克隆失败").strip().splitlines()[-1]
            if ref:
                run(["git", "-C", str(clone), "fetch", "--depth", "1", "origin", ref])
                run(["git", "-C", str(clone), "checkout", ref])
        msg = "已下载"

    if not is_installed(entry):
        return False, f"下载成功但未找到技能路径 {_skill_subpath(entry)}"
    return True, msg


def fetch_all(update: bool = False) -> list[tuple[str, bool, str]]:
    results = []
    for entry in entries():
        ok, msg = fetch(entry, update=update)
        results.append((entry.name, ok, msg))
    return results


def current_ref(entry: Entry) -> str:
    """已下载条目当前所在的 commit（短哈希），用于展示版本。"""
    clone = _clone_dir(entry)
    if not (clone / ".git").is_dir():
        return "mirror" if sources_mod.get(entry.source) and \
            sources_mod.get(entry.source).local_mirror else "-"
    res = run(["git", "-C", str(clone), "rev-parse", "--short", "HEAD"])
    return res.stdout.strip() if res.returncode == 0 else "-"
