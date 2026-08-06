"""跨平台工具函数：路径、终端输出、软链/联结/复制。"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

IS_WINDOWS = os.name == "nt"

# ---------------------------------------------------------------- 终端输出


def _supports_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if not sys.stdout.isatty():
        return False
    if IS_WINDOWS and not os.environ.get("WT_SESSION") and not os.environ.get("TERM"):
        return False
    return True


_COLOR = _supports_color()


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _COLOR else text


def bold(t: str) -> str:
    return _c("1", t)


def dim(t: str) -> str:
    return _c("2", t)


def green(t: str) -> str:
    return _c("32", t)


def yellow(t: str) -> str:
    return _c("33", t)


def red(t: str) -> str:
    return _c("31", t)


def cyan(t: str) -> str:
    return _c("36", t)


def info(msg: str) -> None:
    print(f"  {msg}")


def ok(msg: str) -> None:
    print(f"{green('✓')} {msg}")


def warn(msg: str) -> None:
    print(f"{yellow('!')} {msg}")


def fail(msg: str) -> None:
    print(f"{red('✗')} {msg}", file=sys.stderr)


def header(msg: str) -> None:
    print(f"\n{bold(msg)}")


def die(msg: str, code: int = 1) -> "NoReturn":  # type: ignore[name-defined]
    fail(msg)
    raise SystemExit(code)


def human_size(num: float) -> str:
    for unit in ("B", "K", "M", "G", "T"):
        if abs(num) < 1024.0:
            return f"{num:.0f}{unit}" if unit == "B" else f"{num:.1f}{unit}"
        num /= 1024.0
    return f"{num:.1f}P"


def dir_size(path: Path) -> int:
    """统计目录体积，不跟随软链（避免把共享目标重复计入）。"""
    total = 0
    for root, dirs, files in os.walk(path, followlinks=False):
        for name in files:
            fp = Path(root) / name
            try:
                if not fp.is_symlink():
                    total += fp.stat().st_size
            except OSError:
                pass
    return total


# ---------------------------------------------------------------- JSON 读写


def read_json(path: Path, default=None):
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    tmp.replace(path)


# ---------------------------------------------------------------- 链接原语

LINK_SYMLINK = "symlink"
LINK_JUNCTION = "junction"
LINK_COPY = "copy"


def link_kind_available() -> str:
    """探测本机可用的最佳链接方式。"""
    if not IS_WINDOWS:
        return LINK_SYMLINK
    # Windows：开发者模式或管理员下 symlink 可用，否则退回 junction（目录联结，无需提权）
    probe = Path(os.environ.get("TEMP", ".")) / ".skills-hub-linkprobe"
    src = probe / "src"
    dst = probe / "dst"
    try:
        shutil.rmtree(probe, ignore_errors=True)
        src.mkdir(parents=True, exist_ok=True)
        os.symlink(src, dst, target_is_directory=True)
        return LINK_SYMLINK
    except (OSError, NotImplementedError, AttributeError):
        return LINK_JUNCTION
    finally:
        shutil.rmtree(probe, ignore_errors=True)


def is_link(path: Path) -> bool:
    """软链或 Windows 目录联结都算链接。"""
    if path.is_symlink():
        return True
    if IS_WINDOWS and path.exists():
        try:
            return bool(path.stat().st_reparse_tag)  # type: ignore[attr-defined]
        except (AttributeError, OSError):
            return False
    return False


def link_target(path: Path) -> Path | None:
    try:
        if path.is_symlink():
            return Path(os.readlink(path))
        if IS_WINDOWS and is_link(path):
            return path.resolve()
    except OSError:
        return None
    return None


def remove_link(path: Path) -> None:
    """安全移除链接（绝不递归删除链接指向的真实内容）。"""
    if not is_link(path) and not path.exists():
        return
    if is_link(path):
        try:
            path.unlink()
            return
        except (OSError, PermissionError):
            if IS_WINDOWS and path.is_dir():
                os.rmdir(path)
                return
            raise


def make_link(src: Path, dst: Path, mode: str) -> str:
    """把 src 链接到 dst，返回实际使用的方式。dst 已存在的链接会被替换。"""
    dst.parent.mkdir(parents=True, exist_ok=True)
    if is_link(dst):
        remove_link(dst)
    elif dst.exists():
        raise FileExistsError(f"{dst} 已存在且不是链接，拒绝覆盖")

    if mode == LINK_SYMLINK:
        os.symlink(src, dst, target_is_directory=src.is_dir())
        return LINK_SYMLINK
    if mode == LINK_JUNCTION:
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(dst), str(src)],
            check=True,
            capture_output=True,
        )
        return LINK_JUNCTION
    shutil.copytree(src, dst)
    return LINK_COPY


def run(cmd: list[str], cwd: Path | None = None, check: bool = False):
    return subprocess.run(
        cmd, cwd=str(cwd) if cwd else None, check=check,
        capture_output=True, text=True,
    )
