#!/usr/bin/env python3
"""
fix_filenames.py

For every leaf folder under gamedata/sounds/characters_voice (excluding
commands and commands_eng), renames .ogg files so that:
  - the base name matches the parent folder name
  - muffled variants keep the m_ prefix
  - files are re-indexed sequentially from _1, sorted by their existing index

Example (folder: buttoncomments/Bleed/):
  old_name_3.ogg    ->  Bleed_1.ogg
  old_name_7.ogg    ->  Bleed_2.ogg
  m_old_name_3.ogg  ->  m_Bleed_1.ogg
  m_old_name_7.ogg  ->  m_Bleed_2.ogg
"""

import re
import argparse
from pathlib import Path

INDEXED_OGG  = re.compile(r'^(m_)?(.+?)(_(\d+))?\.ogg$', re.IGNORECASE)
EXCLUDED_TOP = {'commands', 'commands_eng'}


def extract_index(filename: str) -> int:
    """Return the numeric suffix of a file, or a large number if absent."""
    m = INDEXED_OGG.match(filename)
    if m and m.group(4):
        return int(m.group(4))
    return 10 ** 9


def process_folder(folder: Path, dry_run: bool) -> int:
    ogg_files = [f for f in folder.iterdir() if f.is_file() and f.suffix.lower() == '.ogg']
    if not ogg_files:
        return 0

    folder_name = folder.name

    # Split into muffled / non-muffled, sort each group by existing index then name
    non_muffled = sorted(
        [f for f in ogg_files if not f.name.lower().startswith('m_')],
        key=lambda f: (extract_index(f.name), f.name),
    )
    muffled = sorted(
        [f for f in ogg_files if f.name.lower().startswith('m_')],
        key=lambda f: (extract_index(f.name), f.name),
    )

    # Build desired rename list
    renames: list[tuple[Path, Path]] = []
    for i, f in enumerate(non_muffled, 1):
        target = folder / f'{folder_name}_{i}.ogg'
        if f.resolve() != target.resolve():
            renames.append((f, target))
    for i, f in enumerate(muffled, 1):
        target = folder / f'm_{folder_name}_{i}.ogg'
        if f.resolve() != target.resolve():
            renames.append((f, target))

    if not renames:
        return 0

    print(f'\n{folder}')
    for src, dst in renames:
        print(f'  {src.name}  ->  {dst.name}')

    if not dry_run:
        # Pass 1: move every source to a temp name to avoid mid-rename collisions
        staged: list[tuple[Path, Path]] = []
        for src, dst in renames:
            tmp = folder / f'__tmp_{src.name}'
            src.rename(tmp)
            staged.append((tmp, dst))
        # Pass 2: move temp names to final destinations
        for tmp, dst in staged:
            tmp.rename(dst)

    return len(renames)


def process(sounds_root: Path, dry_run: bool) -> None:
    total = 0
    for folder in sorted(sounds_root.rglob('*')):
        if not folder.is_dir():
            continue
        # Exclude commands / commands_eng subtrees
        try:
            rel = folder.relative_to(sounds_root)
        except ValueError:
            continue
        if rel.parts[0].lower() in EXCLUDED_TOP:
            continue

        total += process_folder(folder, dry_run)

    action = 'Would rename' if dry_run else 'Renamed'
    print(f'\n{action} {total} file(s) total.')


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Rename .ogg files to match their parent folder name and re-index from _1.'
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

    sounds_root = Path(args.sounds_dir)
    if not sounds_root.is_dir():
        print(f'Error: directory not found: {sounds_root}')
        return 1

    print(f'{"[DRY RUN] " if args.dry_run else ""}Fixing filenames under: {sounds_root.resolve()}')
    process(sounds_root, args.dry_run)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
