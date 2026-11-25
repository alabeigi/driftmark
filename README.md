# Driftmark

Before you copy a project, regenerate an export, or clean up a directory, take a snapshot with Driftmark. Check the folder afterward to see which files were added, removed, edited, or moved. A saved snapshot contains paths, sizes, and SHA-256 hashes, so you can compare two snapshots even after the original folders are gone.

## Quick start

Run from this checkout with Python 3.9 or later. Driftmark has no runtime dependencies.

```sh
python -m driftmark snapshot ./project -o before.json -x '.git' -x '*.tmp'
python -m driftmark check before.json ./project --html changes.html
```

Open `changes.html` in a browser to search paths or filter by change type. The report works offline. For automation, use `--json` to get change records with byte counts before and after each change.

Two saved snapshots can be compared directly.

```sh
python -m driftmark snapshot ./project -o after.json -x '.git' -x '*.tmp'
python -m driftmark diff before.json after.json --json
```

Install with `python -m pip install .` to use the `driftmark` command from anywhere.

## A sample comparison

```text
Edited   assets/palette.json
Moved    notes/setup.md → docs/setup.md
Added    assets/icons/compass.svg
Removed  scratch.txt

1 edited · 1 moved · 1 added · 1 removed
```

`check` and `diff` return `0` for a match, `1` for changes, and `2` for an error. A valid `snapshot` returns `0`.

## What gets recorded

- File contents determine whether a path was edited. Timestamps and permissions do not affect the comparison.
- A move is inferred when exactly one removed path and one added path share the same content. When several candidates match, the report lists the additions and removals separately.
- The scan covers regular files and skips symlinks and empty directories. Run it while the directory is idle for a consistent snapshot.
- Exclusion globs without `/` match names at any depth. Globs with `/` match paths relative to the root. Matching directories are skipped along with their contents. Quote globs so the shell passes them through.
- `check` reuses the baseline exclusions. Driftmark skips the manifest when writing it inside the scanned tree or checking against it there. Keep other generated reports outside the tree or exclude them explicitly.

Run the tests with `python -m unittest discover -s tests`.
