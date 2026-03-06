#!/usr/bin/env python3
"""
index_sounds.py

Ensures every .ogg file under gamedata/sounds/characters_voice has a numeric
index suffix (_1, _2, ...). Files that already end with _N are left untouched;
files that don't get _1 appended before the extension.

Example:
  DontLoot_ComClose.ogg    ->  DontLoot_ComClose_1.ogg
  m_DontLoot_ComClose.ogg  ->  m_DontLoot_ComClose_1.ogg
  Bleed_1.ogg              ->  (unchanged)
"""

import re
import argparse
from pathlib import Path

ALREADY_INDEXED = re.compile(r'_\d+\.ogg$', re.IGNORECASE)


def process(root: Path, dry_run: bool) -> None:
    renamed = 0
    skipped = 0

    for f in sorted(root.rglob('*.ogg')):
        if ALREADY_INDEXED.search(f.name):
            skipped += 1
            continue

        dest = f.with_name(f.stem + '_1' + f.suffix)
        if dest.exists():
            print(f"  [CONFLICT] target already exists, skipping: {dest.relative_to(root)}")
            continue

        rel = f.relative_to(root)
        print(f"  {rel}  ->  {dest.name}")
        if not dry_run:
            f.rename(dest)
        renamed += 1

    print(f"\n{'Would rename' if dry_run else 'Renamed'} {renamed} file(s), skipped {skipped} already-indexed.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Add _1 index suffix to .ogg files that lack a numeric suffix."
    )
    parser.add_argument(
        'sounds_dir',
        nargs='?',
        default='gamedata/sounds/characters_voice',
        help='Path to characters_voice directory (default: gamedata/sounds/characters_voice)',
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be renamed without actually renaming anything',
    )
    args = parser.parse_args()

    root = Path(args.sounds_dir)
    if not root.is_dir():
        print(f"Error: directory not found: {root}")
        return 1

    print(f"{'[DRY RUN] ' if args.dry_run else ''}Indexing sounds under: {root.resolve()}")
    process(root, args.dry_run)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
