import html
import json
from dataclasses import asdict

from .diff import KINDS, Change
from .snapshot import Snapshot


def display(value: str) -> str:
    return "".join(char if char.isprintable() else ascii(char)[1:-1] for char in value)


def _counts(changes: list[Change]) -> dict[str, int]:
    counts = dict.fromkeys(KINDS, 0)
    for change in changes:
        counts[change.kind] += 1
    return counts


def text_report(changes: list[Change]) -> str:
    if not changes:
        return "No changes."
    lines = []
    for change in changes:
        path = display(change.path)
        if change.previous_path is not None:
            path = f"{display(change.previous_path)} → {path}"
        lines.append(f"{KINDS[change.kind]:<7}  {path}")
    counts = _counts(changes)
    summary = " · ".join(f"{count} {kind}" for kind, count in counts.items() if count)
    return "\n".join([*lines, "", summary])


def json_report(before: Snapshot, after: Snapshot, changes: list[Change]) -> str:
    return json.dumps(
        {
            "before": before.captured_at,
            "after": after.captured_at,
            "counts": _counts(changes),
            "bytes_delta": sum(change.delta for change in changes),
            "changes": [asdict(change) for change in changes],
        },
        indent=2,
    )


def html_report(before: Snapshot, after: Snapshot, changes: list[Change]) -> str:
    def escaped(value: str) -> str:
        return html.escape(display(value))

    filters = "".join(
        f'<option value="{kind}">{KINDS[kind]} ({count:,})</option>'
        for kind, count in _counts(changes).items()
    )
    rows = []
    for change in changes:
        previous = ""
        if change.previous_path is not None:
            previous = f'<span class="previous">from {escaped(change.previous_path)}</span>'
        delta = f"{change.delta:+,}" if change.delta else "0"
        rows.append(
            f'<tr data-kind="{change.kind}">'
            f'<td><span class="kind {change.kind}">{KINDS[change.kind]}</span></td>'
            f'<td class="path">{escaped(change.path)}{previous}</td>'
            f'<td class="number">{delta}</td></tr>'
        )
    delta = sum(change.delta for change in changes)
    total = f"{delta:+,}" if delta else "0"
    return (
        _HTML_HEAD
        + f"""<main>
  <header class="hero">
    <p class="brand">Driftmark</p>
    <h1>Directory changes</h1>
    <dl class="dates">
      <div><dt>Baseline</dt><dd>{escaped(before.captured_at)}</dd></div>
      <div><dt>Compared</dt><dd>{escaped(after.captured_at)}</dd></div>
    </dl>
  </header>
  <section class="report" aria-label="Change report">
    <dl class="totals">
      <div><dt>Changes</dt><dd>{len(changes):,}</dd></div>
      <div><dt>Net bytes</dt><dd>{total}</dd></div>
    </dl>
    <div class="filters" hidden>
      <label>Search paths<input id="query" type="search" placeholder="e.g. notes/"></label>
      <label>Change type<select id="kind"><option value="">All changes</option>{filters}</select></label>
    </div>
    <table{' hidden' if not changes else ''}>
      <thead><tr><th scope="col">Change</th><th scope="col">Path</th><th scope="col" class="number">Bytes Δ</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
    <p id="empty" class="empty" role="status"{' hidden' if changes else ''}>No changes.</p>
  </section>
</main>
"""
        + _HTML_END
    )


_HTML_HEAD = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Directory changes · Driftmark</title>
<style>
:root { color-scheme: light; background: #f3f5f1; color: #182722;
        font: 16px/1.5 system-ui, sans-serif; }
* { box-sizing: border-box; }
[hidden] { display: none !important; }
body { margin: 0; }
main { max-width: 65rem; margin: clamp(0.75rem, 5vw, 4rem) auto; padding: 0 1rem; }
.hero { padding: clamp(1.3rem, 6vw, 4rem); border-radius: 1.25rem 1.25rem 0 0;
        background: #16382e; color: #f5fbf6; }
.brand { margin: 0; font-weight: 750; color: #b6e4c5; }
h1 { margin: .3rem 0 1.5rem; font-size: clamp(2.1rem, 7vw, 4.4rem);
     line-height: 1; letter-spacing: -.055em; }
dl { display: flex; gap: 1.25rem 2.5rem; flex-wrap: wrap; margin: 0; }
dt { font-weight: 650; font-size: .83rem; }
dd { margin: .15rem 0 0; font-variant-numeric: tabular-nums; }
.dates { color: #d7e6dd; }
.dates dd { font-size: .93rem; overflow-wrap: anywhere; }
.report { background: #fff; padding: clamp(1rem, 4vw, 2.75rem); border: 1px solid #dce6df;
          border-top: 0; border-radius: 0 0 1.25rem 1.25rem; }
.totals { padding-bottom: 1.35rem; }
.totals dd { font-size: 1.85rem; font-weight: 700; line-height: 1.1; }
.filters { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: .75rem;
           margin: .5rem 0 1.25rem; }
label { font-size: .85rem; font-weight: 650; }
input, select { display: block; width: 100%; margin-top: .3rem; padding: .55rem .6rem;
                font: inherit; font-weight: 400; color: inherit; background: white;
                border: 1px solid #a5b9ad; border-radius: .4rem; }
:focus-visible { outline: 2px solid #276047; outline-offset: 2px; }
table { width: 100%; border-collapse: collapse; text-align: left; }
th, td { padding: .8rem .45rem; border-bottom: 1px solid #e2eae4; vertical-align: top; }
th { color: #43594d; font-size: .85rem; }
.number { text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; }
.path { font: .88rem/1.65 ui-monospace, monospace; overflow-wrap: anywhere; }
.previous { display: block; color: #4e6458; font-size: .8rem; margin-top: .2rem; }
.kind { font-size: .79rem; font-weight: 700; padding: .2rem .45rem; border-radius: .3rem; }
.edited { background: #f9edd0; color: #643d05; }
.moved { background: #dfeafb; color: #233b63; }
.added { background: #d9f0e2; color: #16492c; }
.removed { background: #f8e0dd; color: #872f27; }
.empty { margin: .75rem 0 0; color: #43594d; }
@media (max-width: 30rem) { .filters { grid-template-columns: 1fr; } }
</style>
</head>
<body>
"""


_HTML_END = """<script>
const query = document.querySelector('#query');
const kind = document.querySelector('#kind');
const empty = document.querySelector('#empty');
const rows = Array.from(document.querySelectorAll('tbody tr'));
function filterRows() {
  const search = query.value.trim().toLowerCase();
  let visible = 0;
  for (const row of rows) {
    const path = row.querySelector('.path').textContent.toLowerCase();
    row.hidden = Boolean((kind.value && row.dataset.kind !== kind.value) || !path.includes(search));
    if (!row.hidden) visible++;
  }
  empty.textContent = 'No changes match the filters.';
  empty.hidden = visible > 0;
}
if (rows.length) {
  document.querySelector('.filters').hidden = false;
  query.addEventListener('input', filterRows);
  kind.addEventListener('change', filterRows);
}
</script>
</body>
</html>
"""
