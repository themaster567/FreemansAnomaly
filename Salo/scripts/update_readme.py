#!/usr/bin/env python3
"""
update_readme.py

Scans characters_voice for .description files and inserts/replaces a markdown
table in README.md immediately after the "<voice lines start here>" marker.
Everything after the marker is overwritten on each run.

Columns: parent folder | folder | description

Skips _eng variant folders (descriptions are copies of the Russian ones).

Usage:
  python update_readme.py
  python update_readme.py --dry-run
"""

import argparse
from pathlib import Path

_ROOT   = Path(__file__).parent.parent / 'gamedata/sounds/characters_voice'
_README = Path(__file__).parent.parent / 'README.md'
_MARKER = '<voice lines start here>'
_LANG_SUFFIXES = ('_eng',)


def is_lang_variant(name: str) -> bool:
    return any(name.endswith(s) for s in _LANG_SUFFIXES)


def collect_rows(root: Path) -> list[tuple[str, str, str]]:
    """
    Walk root, skip _eng subtrees.
    Return (parent_folder, folder, description) for every folder with .description.
    parent_folder is empty string for top-level folders.
    """
    rows = []
    for folder in sorted(root.rglob('*')):
        if not folder.is_dir():
            continue
        parts = folder.relative_to(root).parts
        if any(is_lang_variant(p) for p in parts):
            continue
        desc_file = folder / '.description'
        if not desc_file.exists():
            continue
        description = desc_file.read_text(encoding='utf-8').strip()
        parent = parts[-2] if len(parts) >= 2 else ''
        name   = parts[-1]
        rows.append((parent, name, description))
    return rows


def build_table(rows: list[tuple[str, str, str]]) -> str:
    lines = [
        '| Parent folder | Folder | Description |',
        '|---|---|---|',
    ]
    for parent, folder, desc in rows:
        cell = '<br>'.join(line.replace('|', '\\|') for line in desc.splitlines() if line.strip())
        lines.append(f'| {parent} | {folder} | {cell} |')
    return '\n'.join(lines) + '\n'


def update_readme(readme: Path, table: str, dry_run: bool) -> bool:
    text = readme.read_text(encoding='utf-8')

    idx = text.find(_MARKER)
    if idx == -1:
        print(f'Error: marker "{_MARKER}" not found in {readme}')
        return False

    # Keep everything up to and including the marker line
    newline = text.find('\n', idx)
    cut = (newline + 1) if newline != -1 else len(text)
    new_text = text[:cut] + '\n' + table

    if dry_run:
        print(new_text[max(0, cut - len(_MARKER) - 5):])
        return True

    readme.write_text(new_text, encoding='utf-8')
    print(f'Updated {readme}')
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Rebuild the voice-lines table in README.md.'
    )
    parser.add_argument('--root',   default=str(_ROOT),   help='characters_voice directory')
    parser.add_argument('--readme', default=str(_README), help='README.md path')
    parser.add_argument('--dry-run', action='store_true', help='Print output without writing')
    args = parser.parse_args()

    rows = collect_rows(Path(args.root))
    print(f'Collected {len(rows)} row(s).\n')

    table = build_table(rows)
    update_readme(Path(args.readme), table, args.dry_run)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
