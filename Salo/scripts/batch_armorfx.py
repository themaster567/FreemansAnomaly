#!/usr/bin/env python3
"""
All credits go to @Varian for providing shell scripts

batch_armorfx.py

Python port of batch_armorfx.sh + armorfx.sh.

For every non-m_ .ogg file found under --root:
  1. <out-dir>/.../<file>.ogg   — loudness-normalised with ffmpeg
  2. <out-dir>/.../m_<file>.ogg — armor/helmet effect (sox_ng) then loudness-normalised

Requires: sox_ng (or sox as fallback), ffmpeg
https://www.ffmpeg.org/download.html#build-windows
https://codeberg.org/sox_ng/sox_ng/releases

Usage:
  python batch_armorfx.py apply --root gamedata/sounds --out-dir _out
  python batch_armorfx.py apply --root . --preset heavy --wet 0.55 --dry-run
  python batch_armorfx.py presets
  python scripts/batch_armorfx.py apply --root gamedata/sounds/characters_voice --in-place --helmet-only --sox .\\sox-ng\\sox_ng.exe --ffmpeg .\\ffmpeg\\bin\\ffmpeg.exe --preset halo --wet 0.65 --comb-hz 115 --comb-decay 0.75
"""

import argparse
import dataclasses
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

SR = 44100
log = logging.getLogger("batch_armorfx")

# ---------------------------------------------------------------------------
# Armor presets  (mirrors armorfx.sh preset_apply)
# ---------------------------------------------------------------------------

@dataclass
class ArmorPreset:
    wet:        float = 0.30
    wet_gain:   float = 1.00
    hipass:     int   = 240
    lopass:     int   = 7200
    inner_lp:   int   = 3600
    comb_hz:    float = 220.0
    comb_decay: float = 0.18
    slap_ms:    float = 7.0
    slap_decay: float = 0.10
    eq1_f:      int   = 900;  eq1_w: str = "1.2q"; eq1_g: float = 3.0
    eq2_f:      int   = 2400; eq2_w: str = "1.0q"; eq2_g: float = 2.2
    headroom_db: float = 1.0
    normalize:  bool  = True
    ogg_quality: int  = 5


PRESETS: dict[str, ArmorPreset] = {
    "halo": dataclasses.replace(ArmorPreset(),
        wet=0.34, comb_hz=235, comb_decay=0.20, lopass=7200,
        eq1_g=3.5, eq2_g=2.5,
    ),
    "mild": dataclasses.replace(ArmorPreset(),
        wet=0.24, comb_decay=0.14, eq1_g=2.0, eq2_g=1.5,
    ),
    "heavy": dataclasses.replace(ArmorPreset(),
        wet=0.55, wet_gain=1.10, hipass=280, lopass=5600, inner_lp=3000,
        comb_hz=250, comb_decay=0.32, slap_decay=0.14,
        eq1_g=5.0, eq2_g=3.5, headroom_db=1.5, ogg_quality=6,
    ),
    "radio": dataclasses.replace(ArmorPreset(),
        wet=0.28, hipass=500, lopass=3200, inner_lp=2200,
        comb_hz=210, comb_decay=0.12, slap_decay=0.06,
        eq1_g=1.5, eq2_g=1.2,
    ),
}
PRESETS["marine"] = PRESETS["halo"]   # alias

# ---------------------------------------------------------------------------
# ffmpeg restore/sharpen chains  (mirrors restore_chain() in batch_armorfx.sh)
# ---------------------------------------------------------------------------

RESTORE_CHAINS: dict[str, str] = {
    "mild":   "highpass=f=70,afftdn=nr=5:nf=-45:nt=w,highshelf=f=3500:g=2"
              ",aexciter=amount=0.35:drive=2.0:freq=6000:ceil=16000:blend=0:level_in=1:level_out=1"
              ",deesser=i=0.12:m=0.35:f=0.60",
    "medium": "highpass=f=70,afftdn=nr=7:nf=-45:nt=w,highshelf=f=3200:g=3"
              ",aexciter=amount=0.50:drive=2.2:freq=5800:ceil=16000:blend=0:level_in=1:level_out=1"
              ",deesser=i=0.16:m=0.45:f=0.55",
    "strong": "highpass=f=80,afftdn=nr=9:nf=-44:nt=w,highshelf=f=3000:g=4"
              ",aexciter=amount=0.70:drive=2.5:freq=5500:ceil=16000:blend=0:level_in=1:level_out=1"
              ",deesser=i=0.20:m=0.55:f=0.50",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(cmd: list[str], check: bool = True) -> int:
    log.debug("run: %s", " ".join(cmd))
    r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if check and r.returncode != 0:
        raise RuntimeError(f"command failed (rc={r.returncode}): {' '.join(cmd)}")
    return r.returncode


def _need(primary: str, fallback: Optional[str] = None) -> str:
    if shutil.which(primary) or Path(primary).is_file():
        return primary
    if fallback and (shutil.which(fallback) or Path(fallback).is_file()):
        log.debug("%r not found; using fallback %r", primary, fallback)
        return fallback
    raise RuntimeError(f"missing dependency: {primary!r}"
                       + (f" (fallback {fallback!r} also missing)" if fallback else ""))


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _normalize_width(w: str) -> str:
    """Append 'q' if the value is a plain number (sox EQ convention)."""
    try:
        float(w)
        return f"{w}q"
    except ValueError:
        return w


def _comb_ms(hz: float) -> float:
    return 1000.0 / hz if hz > 0 else 5.0


# ---------------------------------------------------------------------------
# sox_ng: armorfx pipeline  (mirrors apply_effect in armorfx.sh)
# ---------------------------------------------------------------------------

def _decode_to_wav(sox: str, ffmpeg: str, src: Path, dst: Path) -> None:
    if _run([sox, str(src), "-r", str(SR), "-c", "1", str(dst)], check=False) == 0:
        return
    log.debug("sox_ng decode failed for %s; trying ffmpeg", src.name)
    _run([ffmpeg, "-v", "error", "-y", "-i", str(src),
          "-ar", str(SR), "-ac", "1", str(dst)])


def _encode_to_ogg(sox: str, ffmpeg: str, src: Path, dst: Path, quality: int) -> None:
    if _run([sox, "-r", str(SR), "-c", "1", "-C", str(quality),
              str(src), str(dst)], check=False) == 0:
        return
    log.debug("sox_ng encode failed; trying ffmpeg")
    _run([ffmpeg, "-v", "error", "-y", "-i", str(src),
          "-ar", str(SR), "-ac", "1", "-c:a", "libvorbis", "-q:a", "5", str(dst)])


def apply_armorfx(sox: str, ffmpeg: str, src: Path, dst: Path, p: ArmorPreset) -> None:
    """
    Full armorfx pipeline:
      dry.wav  →  wet chain (highpass/lowpass/EQ/echo)  →  wet.wav
      dry.wav + wet.wav  →  mix  →  gain/normalize  →  dst.ogg
    """
    wet = _clamp01(p.wet * p.wet_gain)
    dry_level = 1.0 - wet
    comb_ms   = _comb_ms(p.comb_hz)
    eq1_w     = _normalize_width(p.eq1_w)
    eq2_w     = _normalize_width(p.eq2_w)

    dst.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="armorfx.") as td:
        t = Path(td)
        dry   = t / "dry.wav"
        wet_  = t / "wet.wav"
        mix   = t / "mix.wav"
        final = t / "final.wav"

        _decode_to_wav(sox, ffmpeg, src, dry)

        _run([sox, str(dry), str(wet_),
              "highpass",  str(p.hipass),
              "lowpass",   str(p.lopass),
              "equalizer", str(p.eq1_f), eq1_w,  str(p.eq1_g),
              "equalizer", str(p.eq2_f), eq2_w,  str(p.eq2_g),
              "lowpass",   str(p.inner_lp),
              "echo",      "0.75", "0.75",
                            str(p.slap_ms), str(p.slap_decay),
                            f"{comb_ms:.3f}", str(p.comb_decay),
              "lowpass",   str(p.lopass),
        ])

        _run([sox, "-m",
              "-v", f"{dry_level:.6f}", str(dry),
              "-v", f"{wet:.3f}",       str(wet_),
              str(mix),
        ])

        if p.normalize:
            _run([sox, str(mix), str(final), "gain", "-n", f"-{p.headroom_db}"])
        else:
            _run([sox, str(mix), str(final), "gain", "-3"])

        _encode_to_ogg(sox, ffmpeg, final, dst, p.ogg_quality)


# ---------------------------------------------------------------------------
# ffmpeg: loudnorm pass  (mirrors filters_for_lufs + render_ffmpeg in batch_armorfx.sh)
# ---------------------------------------------------------------------------

def _build_af(
    target_lufs: float,
    true_peak:   float,
    lra:         float,
    linear:      bool,
    limit:       float,
    gain_db:     float,
    restore:     bool,
    strength:    str,
) -> str:
    ln = (f"loudnorm=I={target_lufs}:TP={true_peak}"
          f":LRA={lra}:linear={'true' if linear else 'false'}")
    base = f"{RESTORE_CHAINS.get(strength, RESTORE_CHAINS['mild'])},{ln}" if restore else ln
    vol  = "" if gain_db == 0.0 else f",volume={gain_db:+g}dB"
    return f"{base}{vol},alimiter=limit={limit}"


def _render_ffmpeg(ffmpeg: str, src: Path, dst: Path, af: str, ogg_q: int) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.parent / f".tmp_{dst.name}.ogg"
    try:
        base_cmd = [ffmpeg, "-v", "error", "-y", "-i", str(src),
                    "-ar", str(SR), "-ac", "1",
                    "-c:a", "libvorbis", "-q:a", str(ogg_q)]

        # Try full chain
        if _run([*base_cmd, "-af", af, str(tmp)], check=False) == 0:
            tmp.replace(dst)
            return

        # Fallback 1: drop alimiter (older ffmpeg builds)
        af2 = ",".join(f for f in af.split(",") if not f.startswith("alimiter="))
        if _run([*base_cmd, "-af", af2, str(tmp)], check=False) == 0:
            tmp.replace(dst)
            return

        # Fallback 2: keep only loudnorm onward (drop restore chain)
        parts  = af2.split(",")
        tail   = parts[[i for i, p in enumerate(parts) if p.startswith("loudnorm")][0]:]
        log.warning("restore chain failed; using loudnorm-only for %s", dst.name)
        _run([*base_cmd, "-af", ",".join(tail), str(tmp)])
        tmp.replace(dst)

    except Exception:
        tmp.unlink(missing_ok=True)
        raise


# ---------------------------------------------------------------------------
# Per-file worker  (mirrors worker_apply in batch_armorfx.sh)
# ---------------------------------------------------------------------------

@dataclass
class Config:
    sox:    str
    ffmpeg: str
    out_dir: Path

    target_lufs:      float = -16.0
    true_peak:        float = -2.0
    lra:              float = 11.0
    linear:           bool  = True
    ogg_q:            int   = 6
    limit:            float = 0.85

    restore_mode:     str   = "none"   # none|normal|helmet|both
    restore_strength: str   = "mild"

    normal_db: float = 0.0
    helmet_db: float = 0.0

    armor_preset: ArmorPreset = field(default_factory=lambda: PRESETS["halo"])

    dry_run:       bool = False
    skip_existing: bool = False
    in_place:      bool = False   # write m_ next to source instead of out_dir
    helmet_only:   bool = False   # skip normal loudnorm pass


def _should_restore(mode: str, which: str) -> bool:
    return mode in ("both",) or mode == which


def process_file(src: Path, root: Path, cfg: Config) -> Optional[str]:
    """Returns an error string on failure, None on success."""
    rel = src.relative_to(root)

    if cfg.in_place:
        helmet_out = src.parent / f"m_{src.name}"
        normal_out = cfg.out_dir / rel   # only used when not helmet_only
    else:
        normal_out = cfg.out_dir / rel
        helmet_out = normal_out.parent / f"m_{normal_out.name}"

    if cfg.skip_existing and helmet_out.exists():
        log.debug("skip (exists): %s", rel)
        return None

    if cfg.dry_run:
        if not cfg.helmet_only:
            log.info("DRY normal: %s -> %s", rel, normal_out)
        log.info("DRY helmet: %s -> %s", rel, helmet_out)
        return None

    try:
        # 1. Normal loudnorm pass (skipped with --helmet-only)
        if not cfg.helmet_only:
            af_n = _build_af(cfg.target_lufs, cfg.true_peak, cfg.lra, cfg.linear,
                             cfg.limit, cfg.normal_db,
                             _should_restore(cfg.restore_mode, "normal"),
                             cfg.restore_strength)
            _render_ffmpeg(cfg.ffmpeg, src, normal_out, af_n, cfg.ogg_q)

        # 2. Armor: sox_ng effect → temp file
        with tempfile.TemporaryDirectory(prefix="armorfx_batch.") as td:
            raw = Path(td) / f"raw_{src.name}"
            apply_armorfx(cfg.sox, cfg.ffmpeg, src, raw, cfg.armor_preset)

            # 3. Helmet: ffmpeg loudnorm on the armored file
            af_h = _build_af(cfg.target_lufs, cfg.true_peak, cfg.lra, cfg.linear,
                             cfg.limit, cfg.helmet_db,
                             _should_restore(cfg.restore_mode, "helmet"),
                             cfg.restore_strength)
            _render_ffmpeg(cfg.ffmpeg, raw, helmet_out, af_h, cfg.ogg_q)

        log.info("ok: %s", rel)
        return None

    except Exception as exc:
        return f"{rel}: {exc}"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def cmd_presets() -> None:
    for name, p in PRESETS.items():
        if name == "marine":
            continue  # alias, skip duplicate
        print(f"  {name:<8}  wet={p.wet}  comb_hz={p.comb_hz}  comb_decay={p.comb_decay}")


def cmd_apply(args: argparse.Namespace) -> int:
    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="[batch_armorfx] %(message)s",
        stream=sys.stderr,
    )

    try:
        sox_bin    = _need(args.sox, "sox")
        ffmpeg_bin = _need(args.ffmpeg)
    except RuntimeError as e:
        log.error("%s", e)
        return 1

    preset = dataclasses.replace(PRESETS.get(args.preset, PRESETS["halo"]))
    if args.wet        is not None: preset = dataclasses.replace(preset, wet=_clamp01(args.wet))
    if args.wet_gain   is not None: preset = dataclasses.replace(preset, wet_gain=args.wet_gain)
    if args.comb_hz    is not None: preset = dataclasses.replace(preset, comb_hz=args.comb_hz)
    if args.comb_decay is not None: preset = dataclasses.replace(preset, comb_decay=args.comb_decay)

    cfg = Config(
        sox=sox_bin, ffmpeg=ffmpeg_bin,
        out_dir=Path(args.out_dir),
        target_lufs=args.lufs, true_peak=args.tp, lra=args.lra,
        linear=not args.nonlinear,
        ogg_q=args.oggq, limit=args.limit,
        restore_mode=args.restore, restore_strength=args.restore_strength,
        normal_db=args.normal_db, helmet_db=args.helmet_db,
        armor_preset=preset,
        dry_run=args.dry_run, skip_existing=args.skip_existing,
        in_place=args.in_place, helmet_only=args.helmet_only,
    )

    root    = Path(args.root).resolve()
    out_abs = cfg.out_dir.resolve()
    files   = sorted(
        f for f in root.rglob("*.ogg")
        if not f.name.lower().startswith("m_")
        and not f.name.startswith(".tmp_")
        and (cfg.in_place or not str(f.resolve()).startswith(str(out_abs)))
    )

    if not files:
        log.warning("no .ogg files found under %s", root)
        return 0

    log.info("root=%s  out=%s  jobs=%d", root, cfg.out_dir, args.jobs)
    log.info("loudnorm I=%g TP=%g linear=%s limit=%g oggq=%d",
             cfg.target_lufs, cfg.true_peak, cfg.linear, cfg.limit, cfg.ogg_q)
    log.info("restore=%s strength=%s", cfg.restore_mode, cfg.restore_strength)
    log.info("armor preset=%s wet=%g comb_hz=%g comb_decay=%g",
             args.preset, cfg.armor_preset.wet,
             cfg.armor_preset.comb_hz, cfg.armor_preset.comb_decay)

    errors: list[str] = []
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = {pool.submit(process_file, f, root, cfg): f for f in files}
        for fut in as_completed(futures):
            err = fut.result()
            if err:
                errors.append(err)
                log.error("FAIL: %s", err)

    log.info("done  files=%d  errors=%d", len(files), len(errors))
    return 1 if errors else 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Batch armor/helmet FX + loudness normalise for .ogg files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = p.add_subparsers(dest="command")

    sub.add_parser("presets", help="List available presets")

    ap = sub.add_parser("apply", help="Process a directory")
    ap.add_argument("--root",     default=".",             metavar="DIR")
    ap.add_argument("--out-dir",  default="./_armorfx_out",metavar="DIR")
    ap.add_argument("--jobs",     type=int, default=os.cpu_count() or 4, metavar="N")
    ap.add_argument("--dry-run",     action="store_true")
    ap.add_argument("--quiet",       action="store_true")
    ap.add_argument("--skip-existing", action="store_true")
    ap.add_argument("--in-place",    action="store_true",
                    help="Write m_ files next to the source files instead of --out-dir")
    ap.add_argument("--helmet-only", action="store_true",
                    help="Skip the normal loudnorm pass, produce only m_ files")

    ap.add_argument("--sox",    default="sox_ng", metavar="BIN")
    ap.add_argument("--ffmpeg", default="ffmpeg",  metavar="BIN")

    g = ap.add_argument_group("loudness")
    g.add_argument("--lufs",      type=float, default=-16.0, metavar="LUFS")
    g.add_argument("--tp",        type=float, default=-2.0,  metavar="DB")
    g.add_argument("--lra",       type=float, default=11.0,  metavar="LU")
    g.add_argument("--nonlinear", action="store_true")
    g.add_argument("--oggq",      type=int,   default=6,     metavar="Q")
    g.add_argument("--limit",     type=float, default=0.85,  metavar="PEAK")

    g = ap.add_argument_group("restore / sharpen")
    g.add_argument("--restore",          default="none",
                   choices=["none","normal","helmet","both"])
    g.add_argument("--restore-strength", default="mild",
                   choices=["mild","medium","strong"], metavar="STR")

    g = ap.add_argument_group("group gains")
    g.add_argument("--normal-db", type=float, default=0.0, metavar="DB")
    g.add_argument("--helmet-db", type=float, default=0.0, metavar="DB")

    g = ap.add_argument_group("armor preset")
    g.add_argument("--preset",      default="halo",
                   choices=[k for k in PRESETS if k != "marine"])
    g.add_argument("--wet",         type=float, default=None, metavar="N")
    g.add_argument("--wet-gain",    type=float, default=None, metavar="N")
    g.add_argument("--comb-hz",     type=float, default=None, metavar="HZ")
    g.add_argument("--comb-decay",  type=float, default=None, metavar="N")

    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "presets":
        cmd_presets()
        return 0
    if args.command == "apply":
        return cmd_apply(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
