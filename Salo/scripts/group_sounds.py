#!/usr/bin/env python3
"""
group_sounds.py

For each folder under gamedata/sounds/characters_voice, groups .ogg files
into subfolders based on their base name (stripping m_ prefix and _N numeric suffix).

Example:
  buttoncomments/Bleed_1.ogg    -> buttoncomments/Bleed/Bleed_1.ogg
  buttoncomments/m_Bleed_1.ogg  -> buttoncomments/Bleed/m_Bleed_1.ogg
"""

import os
import re
import shutil
import argparse
from pathlib import Path

# Matches: optional m_ prefix, base name, underscore + digits, .ogg
FILE_PATTERN = re.compile(r'^(?:m_)?(.+)_(\d+)\.ogg$', re.IGNORECASE)


def group_folder(folder: Path, dry_run: bool) -> None:
    files = [f for f in folder.iterdir() if f.is_file() and f.suffix.lower() == '.ogg']
    if not files:
        return

    groups: dict[str, list[Path]] = {}
    for f in files:
        m = FILE_PATTERN.match(f.name)
        if m:
            groups.setdefault(m.group(1), []).append(f)
        else:
            print(f"  [SKIP] no numeric suffix, leaving in place: {f.name}")

    for group_name, group_files in sorted(groups.items()):
        dest_dir = folder / group_name
        if not dry_run:
            dest_dir.mkdir(exist_ok=True)
        for f in sorted(group_files):
            dest = dest_dir / f.name
            print(f"  {f.name}  ->  {group_name}/{f.name}")
            if not dry_run:
                shutil.move(str(f), str(dest))


def process(root: Path, dry_run: bool) -> None:
    # topdown=False so we process deepest dirs first; newly created subdirs
    # are not revisited because os.walk captures the tree at start.
    for dirpath, _dirs, filenames in os.walk(root, topdown=False):
        folder = Path(dirpath)
        if any(f.lower().endswith('.ogg') for f in filenames):
            print(f"\n{folder}")
            group_folder(folder, dry_run)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Group character voice .ogg files into subfolders by base name."
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
        help='Show what would be moved without actually moving anything',
    )
    args = parser.parse_args()

    root = Path(args.sounds_dir)
    if not root.is_dir():
        print(f"Error: directory not found: {root}")
        return 1

    print(f"{'[DRY RUN] ' if args.dry_run else ''}Grouping sounds under: {root.resolve()}")
    process(root, args.dry_run)
    print("\nDone.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
