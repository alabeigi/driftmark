import hashlib
import json
import os
import re
import stat
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from fnmatch import fnmatchcase
from pathlib import Path, PurePosixPath
from tempfile import NamedTemporaryFile
from typing import Optional


@dataclass(frozen=True)
class FileMark:
    bytes: int
    sha256: str


@dataclass(frozen=True)
class Snapshot:
    captured_at: str
    excludes: tuple[str, ...]
    files: dict[str, FileMark]


def _fingerprint(info: os.stat_result) -> tuple[int, ...]:
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _mark(path: Path, listed: os.stat_result) -> FileMark:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    flags |= getattr(os, "O_BINARY", 0)
    digest = hashlib.sha256()
    count = 0
    with os.fdopen(os.open(path, flags), "rb") as stream:
        start = os.fstat(stream.fileno())
        if not stat.S_ISREG(start.st_mode) or _fingerprint(start) != _fingerprint(listed):
            raise OSError(f"file changed before it could be read: {path}")
        while block := stream.read(1024 * 1024):
            digest.update(block)
            count += len(block)
        end = os.fstat(stream.fileno())
        current = path.lstat()
    if count != start.st_size or any(
        _fingerprint(info) != _fingerprint(start) for info in (end, current)
    ):
        raise OSError(f"file changed while it was being read: {path}")
    return FileMark(count, digest.hexdigest())


def _raise_walk_error(error: OSError) -> None:
    raise error


def capture(
    root: Path, excludes: tuple[str, ...] = (), *, omit: Optional[Path] = None
) -> Snapshot:
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError(f"expected a directory: {root}")

    omitted = omit.parent.resolve() / omit.name if omit is not None else None
    captured_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    files = {}

    def excluded(path: Path) -> bool:
        relative = path.relative_to(root).as_posix()
        return any(
            fnmatchcase(relative if "/" in pattern else path.name, pattern)
            for pattern in excludes
        )

    for directory, folders, names in os.walk(root, onerror=_raise_walk_error):
        parent = Path(directory)
        folders[:] = sorted(name for name in folders if not excluded(parent / name))
        for name in sorted(names):
            path = parent / name
            if path == omitted or excluded(path):
                continue
            listed = path.lstat()
            if stat.S_ISREG(listed.st_mode):
                files[path.relative_to(root).as_posix()] = _mark(path, listed)

    return Snapshot(captured_at, excludes, files)


def write_text(path: Path, content: str) -> None:
    """Replace a completed output in one operation."""
    temp_path = None
    try:
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=path.parent, delete=False
        ) as stream:
            temp_path = Path(stream.name)
            stream.write(content)
        temp_path.replace(path)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def save(snapshot: Snapshot, path: Path) -> None:
    payload = {
        "format": 1,
        "captured_at": snapshot.captured_at,
        "excludes": snapshot.excludes,
        "files": {name: asdict(mark) for name, mark in sorted(snapshot.files.items())},
    }
    write_text(path, json.dumps(payload, indent=2) + "\n")


def load(path: Path) -> Snapshot:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or type(data.get("format")) is not int or data["format"] != 1:
        raise ValueError(f"unsupported snapshot format in {path}")

    captured_at, excludes, entries = (data.get(key) for key in ("captured_at", "excludes", "files"))
    if not (
        isinstance(captured_at, str)
        and isinstance(excludes, list)
        and all(isinstance(pattern, str) for pattern in excludes)
        and isinstance(entries, dict)
    ):
        raise ValueError(f"invalid snapshot header in {path}")

    files = {}
    for name, entry in entries.items():
        relative = PurePosixPath(name)
        if not (
            name not in ("", ".")
            and "\0" not in name
            and not relative.is_absolute()
            and ".." not in relative.parts
            and relative.as_posix() == name
            and isinstance(entry, dict)
            and type(entry.get("bytes")) is int
            and entry["bytes"] >= 0
            and isinstance(entry.get("sha256"), str)
            and re.fullmatch(r"[0-9a-f]{64}", entry["sha256"])
        ):
            raise ValueError(f"invalid file entry {name!r} in {path}")
        files[name] = FileMark(entry["bytes"], entry["sha256"])
    return Snapshot(captured_at, tuple(excludes), files)
