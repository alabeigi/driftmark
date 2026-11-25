from collections import defaultdict
from dataclasses import dataclass
from typing import Optional

from .snapshot import FileMark, Snapshot


KINDS = {"edited": "Edited", "moved": "Moved", "added": "Added", "removed": "Removed"}


@dataclass(frozen=True)
class Change:
    kind: str
    path: str
    before_bytes: Optional[int] = None
    after_bytes: Optional[int] = None
    previous_path: Optional[str] = None

    @property
    def delta(self) -> int:
        return (self.after_bytes or 0) - (self.before_bytes or 0)


def _by_content(files: dict[str, FileMark], paths: set[str]) -> dict[FileMark, list[str]]:
    groups = defaultdict(list)
    for path in paths:
        groups[files[path]].append(path)
    return groups


def compare(before: Snapshot, after: Snapshot) -> list[Change]:
    old, new = before.files, after.files
    removed, added = old.keys() - new.keys(), new.keys() - old.keys()
    changes = [
        Change("edited", path, old[path].bytes, new[path].bytes)
        for path in old.keys() & new.keys()
        if old[path] != new[path]
    ]

    old_groups = _by_content(old, removed)
    new_groups = _by_content(new, added)
    for mark, sources in old_groups.items():
        destinations = new_groups.get(mark, [])
        if len(sources) == len(destinations) == 1:
            source, destination = sources[0], destinations[0]
            changes.append(Change("moved", destination, mark.bytes, mark.bytes, source))
            removed.remove(source)
            added.remove(destination)

    changes.extend(Change("added", path, after_bytes=new[path].bytes) for path in added)
    changes.extend(Change("removed", path, before_bytes=old[path].bytes) for path in removed)
    order = {kind: index for index, kind in enumerate(KINDS)}
    return sorted(changes, key=lambda change: (order[change.kind], change.path))
