#!/usr/bin/env bash
set -eEuo pipefail
SCRIPT_NAME="$(basename "$0")"
trap 'echo "[$SCRIPT_NAME] ERR line=$LINENO cmd=$BASH_COMMAND" >&2; exit 1' ERR

FFMPEG_BIN="${FFMPEG_BIN:-ffmpeg}"
ARMORFX_BIN="${ARMORFX_BIN:-./armorfx.sh}"

need_cmd(){ command -v "$1" >/dev/null 2>&1 || { echo "[$SCRIPT_NAME] error: missing dependency: $1" >&2; exit 1; }; }
need_cmd "$FFMPEG_BIN"

ROOT="."
OUT_DIR="./_armorfx_out"
JOBS="${JOBS:-}"
[[ -z "$JOBS" ]] && JOBS="$(command -v nproc >/dev/null 2>&1 && nproc || echo 8)"

DRY_RUN=0
VERBOSE=1
SKIP_EXISTING=0

SR=44100
OGG_Q=6

# Loudness normalize (non-compressing)
TARGET_LUFS="-16"
TRUE_PEAK="-2.0"   # more headroom than -1.0 (reduces peaking)
LRA="11"
LN_LINEAR=1        # linear=true

# Optional group gains (keep small)
GAIN_NORMAL_DB="0.0"
GAIN_HELMET_DB="0.0"

# Always-on post limiter to catch peaks/overs (0.85 ~= -1.4 dBFS)
# If you still see peaking, drop to 0.80.
LIMIT=0.85

# Restoration/sharpening
RESTORE_MODE="none"        # none|normal|helmet|both
RESTORE_STRENGTH="mild"    # mild|medium|strong

# Armor sound
ARMOR_PRESET="halo"
ARMOR_WET="0.65"
ARMOR_COMB_HZ="250"
ARMOR_COMB_DECAY="0.30"

log(){ [[ "$VERBOSE" == "1" ]] && echo "[$SCRIPT_NAME] $*" >&2; }

restore_chain() {
  case "$RESTORE_STRENGTH" in
    mild)
      echo "highpass=f=70,afftdn=nr=5:nf=-45:nt=w,highshelf=f=3500:g=2,aexciter=amount=0.35:drive=2.0:freq=6000:ceil=16000:blend=0:level_in=1:level_out=1,deesser=i=0.12:m=0.35:f=0.60"
      ;;
    medium)
      echo "highpass=f=70,afftdn=nr=7:nf=-45:nt=w,highshelf=f=3200:g=3,aexciter=amount=0.50:drive=2.2:freq=5800:ceil=16000:blend=0:level_in=1:level_out=1,deesser=i=0.16:m=0.45:f=0.55"
      ;;
    strong)
      echo "highpass=f=80,afftdn=nr=9:nf=-44:nt=w,highshelf=f=3000:g=4,aexciter=amount=0.70:drive=2.5:freq=5500:ceil=16000:blend=0:level_in=1:level_out=1,deesser=i=0.20:m=0.55:f=0.50"
      ;;
    *)
      echo "highpass=f=70,afftdn=nr=5:nf=-45:nt=w,highshelf=f=3500:g=2,aexciter=amount=0.35:drive=2.0:freq=6000:ceil=16000:blend=0:level_in=1:level_out=1,deesser=i=0.12:m=0.35:f=0.60"
      ;;
  esac
}

should_restore() {
  local which="$1"   # normal|helmet
  case "$RESTORE_MODE" in
    none)   echo "0" ;;
    both)   echo "1" ;;
    normal) [[ "$which" == "normal" ]] && echo "1" || echo "0" ;;
    helmet) [[ "$which" == "helmet" ]] && echo "1" || echo "0" ;;
    *)      echo "0" ;;
  esac
}

filters_for_lufs() {
  local gain_db="$1"
  local apply_restore="$2"   # 0/1

  local linear_flag="true"
  [[ "$LN_LINEAR" == "0" ]] && linear_flag="false"

  local ln="loudnorm=I=${TARGET_LUFS}:TP=${TRUE_PEAK}:LRA=${LRA}:linear=${linear_flag}"

  local base="$ln"
  if [[ "$apply_restore" == "1" ]]; then
    base="$(restore_chain),${ln}"
  fi

  # Always add limiter at the end to catch overs (codec/inter-sample style peaking)
  if [[ "$gain_db" == "0" || "$gain_db" == "0.0" || "$gain_db" == "+0" || "$gain_db" == "+0.0" || "$gain_db" == "-0" || "$gain_db" == "-0.0" ]]; then
    echo "${base},alimiter=limit=${LIMIT}"
  else
    echo "${base},volume=${gain_db}dB,alimiter=limit=${LIMIT}"
  fi
}

render_ffmpeg() {
  local in="$1" out="$2" af="$3"
  mkdir -p "$(dirname "$out")"
  local tmp
  tmp="$(mktemp -p "$(dirname "$out")" ".tmp_$(basename "$out").XXXXXX.ogg")"

  # attempt full chain
  if "$FFMPEG_BIN" -v error -y -i "$in" -ar "$SR" -ac 1 -af "$af" -c:a libvorbis -q:a "$OGG_Q" "$tmp"; then
    mv -f -- "$tmp" "$out"
    return 0
  fi

  # fallback: remove limiter if your ffmpeg lacks alimiter
  af2="$(echo "$af" | sed 's/,alimiter=limit=[^,]*//')"
  if "$FFMPEG_BIN" -v error -y -i "$in" -ar "$SR" -ac 1 -af "$af2" -c:a libvorbis -q:a "$OGG_Q" "$tmp"; then
    mv -f -- "$tmp" "$out"
    return 0
  fi

  # fallback 2: drop restore chain, keep loudnorm (+optional volume)
  af3="$(echo "$af2" | sed 's/^.*loudnorm/loudnorm/')"  # keep tail from loudnorm onward
  log "warn: restore chain failed; using loudnorm-only for: $out"
  "$FFMPEG_BIN" -v error -y -i "$in" -ar "$SR" -ac 1 -af "$af3" -c:a libvorbis -q:a "$OGG_Q" "$tmp"
  mv -f -- "$tmp" "$out"
}

armor_to() {
  local in="$1" out="$2"
  [[ "$DRY_RUN" == "1" ]] && { log "DRY armorfx: $in -> $out"; return 0; }
  mkdir -p "$(dirname "$out")"
  "$ARMORFX_BIN" apply -i "$in" -o "$out" \
    --preset "$ARMOR_PRESET" --wet "$ARMOR_WET" --comb-hz "$ARMOR_COMB_HZ" --comb-decay "$ARMOR_COMB_DECAY" \
    --no-normalize 2>/dev/null || \
  "$ARMORFX_BIN" apply -i "$in" -o "$out" \
    --preset "$ARMOR_PRESET" --wet "$ARMOR_WET" --comb-hz "$ARMOR_COMB_HZ" --comb-decay "$ARMOR_COMB_DECAY"
}

worker_apply() {
  local f="$1"
  local rel="${f#./}"

  local normal_out="$OUT_DIR/$rel"
  local helmet_out="$(dirname "$normal_out")/m_$(basename "$normal_out")"

  [[ "$SKIP_EXISTING" == "1" && -f "$helmet_out" ]] && return 0

  if [[ "$DRY_RUN" == "1" ]]; then
    log "DRY normal: $f -> $normal_out"
    log "DRY helmet: $f -> $helmet_out"
    return 0
  fi

  rn="$(should_restore normal)"
  afn="$(filters_for_lufs "$GAIN_NORMAL_DB" "$rn")"
  render_ffmpeg "$f" "$normal_out" "$afn"

  tmp_helmet="$(mktemp -p "$(dirname "$helmet_out")" ".tmp_$(basename "$helmet_out").XXXXXX.raw.ogg")"
  armor_to "$f" "$tmp_helmet"

  rh="$(should_restore helmet)"
  afh="$(filters_for_lufs "$GAIN_HELMET_DB" "$rh")"
  render_ffmpeg "$tmp_helmet" "$helmet_out" "$afh"
  rm -f -- "$tmp_helmet"
}

if [[ "${1-}" == "__worker_apply" ]]; then
  shift
  f="${1-}"; [[ -n "$f" ]] || exit 0
  worker_apply "$f"
  exit 0
fi

usage(){
  cat <<EOF
Usage:
  $SCRIPT_NAME apply [options]

Options:
  --root DIR
  --out-dir DIR
  --jobs N
  --dry-run
  --quiet
  --skip-existing

Loudness:
  --lufs -16
  --tp -2.0
  --lra 11
  --nonlinear
  --oggq 6

Peak control:
  --limit 0.85

Restore/sharpen:
  --restore none|normal|helmet|both
  --restore-strength mild|medium|strong

Group gains (optional):
  --normal-db -1.0
  --helmet-db +1.0
EOF
}

sub="${1-}"; shift || true
[[ "$sub" == "apply" ]] || { usage; exit 1; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --root) ROOT="$2"; shift 2 ;;
    --out-dir) OUT_DIR="$2"; shift 2 ;;
    --jobs) JOBS="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift 1 ;;
    --quiet) VERBOSE=0; shift 1 ;;
    --skip-existing) SKIP_EXISTING=1; shift 1 ;;

    --lufs) TARGET_LUFS="$2"; shift 2 ;;
    --tp) TRUE_PEAK="$2"; shift 2 ;;
    --lra) LRA="$2"; shift 2 ;;
    --nonlinear) LN_LINEAR=0; shift 1 ;;
    --oggq) OGG_Q="$2"; shift 2 ;;

    --limit) LIMIT="$2"; shift 2 ;;

    --restore) RESTORE_MODE="$2"; shift 2 ;;
    --restore-strength) RESTORE_STRENGTH="$2"; shift 2 ;;

    --normal-db) GAIN_NORMAL_DB="$2"; shift 2 ;;
    --helmet-db) GAIN_HELMET_DB="$2"; shift 2 ;;

    -h|--help) usage; exit 0 ;;
    *) echo "[$SCRIPT_NAME] error: unknown arg: $1" >&2; exit 1 ;;
  esac
done

[[ -x "$ARMORFX_BIN" ]] || { echo "[$SCRIPT_NAME] error: armorfx not executable: $ARMORFX_BIN" >&2; exit 1; }

cd "$ROOT"
mkdir -p "$OUT_DIR"

OUT_ESC="${OUT_DIR#./}"

log "apply root=$(pwd) out=$OUT_DIR jobs=$JOBS"
log "loudnorm I=$TARGET_LUFS TP=$TRUE_PEAK linear=$LN_LINEAR limit=$LIMIT oggq=$OGG_Q"
log "restore=$RESTORE_MODE strength=$RESTORE_STRENGTH"

listfile="$(mktemp)"
find . -type f -iname '*.ogg' \
  ! -name 'm_*.ogg' \
  ! -name '.tmp_*.ogg' \
  ! -path "./${OUT_ESC}/*" \
  -print0 > "$listfile"

export FFMPEG_BIN ARMORFX_BIN
export SR OGG_Q TARGET_LUFS TRUE_PEAK LRA LN_LINEAR LIMIT
export GAIN_NORMAL_DB GAIN_HELMET_DB RESTORE_MODE RESTORE_STRENGTH
export ARMOR_PRESET ARMOR_WET ARMOR_COMB_HZ ARMOR_COMB_DECAY
export OUT_DIR DRY_RUN VERBOSE SKIP_EXISTING

xargs -0 -r -n 1 -P "$JOBS" "$0" __worker_apply < "$listfile" || true
rm -f "$listfile"
log "done"
