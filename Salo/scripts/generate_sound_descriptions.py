#!/usr/bin/env python3
"""
generate_sound_descriptions.py

For each top-level language variant folder (e.g. player_eng, dialogs_eng),
copies .description files from the matching base (Russian) folder at the
same relative path.

Example:
  player/hit_by_burn/.description  ->  player_eng/hit_by_burn/.description

Usage:
  python generate_sound_descriptions.py
  python generate_sound_descriptions.py gamedata/sounds/characters_voice
  python generate_sound_descriptions.py --dry-run
  python generate_sound_descriptions.py --overwrite
"""

import argparse
import shutil
from pathlib import Path

_DEFAULT_ROOT = Path(__file__).parent.parent / 'gamedata/sounds/characters_voice'

_LANG_SUFFIXES = ('_eng',)


def is_lang_variant(name: str) -> bool:
    return any(name.endswith(s) for s in _LANG_SUFFIXES)


def find_pairs(root: Path) -> list[tuple[Path, Path]]:
    """Return (base_dir, lang_dir) pairs for all top-level language variants."""
    pairs = []
    for d in sorted(root.iterdir()):
        if not d.is_dir():
            continue
        for suffix in _LANG_SUFFIXES:
            if d.name.endswith(suffix):
                base = root / d.name[: -len(suffix)]
                if base.is_dir():
                    pairs.append((base, d))
    return pairs


def create_missing(root: Path, base_dirs: set[Path], dry_run: bool) -> int:
    """Create empty .description in every base (Russian) subfolder that lacks one."""
    created = 0
    for folder in sorted(root.rglob('*')):
        if not folder.is_dir():
            continue
        # Skip language variant folders and their subtrees
        if any(part for part in folder.relative_to(root).parts if is_lang_variant(part)):
            continue
        desc = folder / '.description'
        if desc.exists():
            continue
        print(f'  create (empty): {folder.relative_to(root)}/.description')
        if not dry_run:
            desc.touch()
        created += 1
    return created


def sync_pair(base: Path, lang: Path, overwrite: bool, dry_run: bool) -> int:
    """Copy every .description from base into lang at the same relative path."""
    copied = 0
    for src in sorted(base.rglob('.description')):
        rel = src.relative_to(base)
        dst = lang / rel
        if dst.exists() and not overwrite:
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        print(f'  {base.name}/{rel}  ->  {lang.name}/{rel}')
        if not dry_run:
            shutil.copy2(src, dst)
        copied += 1
    return copied


def run(root: Path, overwrite: bool, dry_run: bool) -> int:
    if not root.is_dir():
        print(f'Error: directory not found: {root}')
        return 1

    prefix = '[DRY RUN] ' if dry_run else ''
    print(f'{prefix}Scanning: {root.resolve()}\n')

    pairs = find_pairs(root)
    base_dirs = {base for base, _ in pairs}

    print('--- creating missing .description in Russian folders ---')
    created = create_missing(root, base_dirs, dry_run)

    print(f'\n--- syncing to language variants ---')
    copied = 0
    for base, lang in pairs:
        copied += sync_pair(base, lang, overwrite, dry_run)

    verb = 'Would' if dry_run else 'Done:'
    print(f'\n{verb} create {created}, copy {copied} .description file(s).')
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Sync .description files from base (Russian) folders to _eng variants.'
    )
    parser.add_argument(
        'root',
        nargs='?',
        default=str(_DEFAULT_ROOT),
        help=f'Path to characters_voice directory (default: {_DEFAULT_ROOT})',
    )
    parser.add_argument(
        '--overwrite',
        action='store_true',
        help='Overwrite existing .description files in lang folders',
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Print what would be done without writing anything',
    )
    args = parser.parse_args()
    return run(Path(args.root), args.overwrite, args.dry_run)


if __name__ == '__main__':
    raise SystemExit(main())
