#!/usr/bin/env bash
set -eEuo pipefail

SCRIPT_NAME="$(basename "$0")"
DEBUG="${DEBUG:-0}"
TRACE="${TRACE:-0}"

log() { echo "[$SCRIPT_NAME] $*" >&2; }
die() { echo "[$SCRIPT_NAME] error: $*" >&2; exit 1; }

trap 'log "ERR line=$LINENO cmd=$BASH_COMMAND"; exit 1' ERR

if [[ "$TRACE" == "1" ]]; then
  set -x
fi

need_cmd() { command -v "$1" >/dev/null 2>&1 || die "missing dependency: $1"; }

AWK_BIN="awk"
if command -v gawk >/dev/null 2>&1; then
  AWK_BIN="gawk"
fi

SOX_BIN="${SOX_BIN:-sox_ng}"
SOXI_BIN="${SOXI_BIN:-soxi_ng}"
PLAY_BIN="${PLAY_BIN:-play_ng}"

need_cmd "$SOX_BIN"
need_cmd "$SOXI_BIN"
need_cmd "$AWK_BIN"
"$AWK_BIN" 'BEGIN{print log(10)}' >/dev/null 2>&1 || die "$AWK_BIN lacks log(); install gawk/mawk"

DEV_SR=44100

presets_list() {
  cat <<'EOF'
halo (aka marine)  - mild power-armor vibe (recommended start)
mild              - very subtle helmet hint
heavy             - stronger, more enclosed/metallic
radio             - narrowband comms
EOF
}

preset_apply() {
  local p="${1:-halo}"

  wet="0.30"
  wetGain="1.00"

  hipass="240"
  lopass="7200"
  innerLP="3600"   # now used: dulls the echo/ring

  combHz="220"
  combDecay="0.18" # echo tap decay 0..1
  slapMs="7"
  slapDecay="0.10"

  # IMPORTANT: widths are Q, so include "q"
  eq1_f="900";  eq1_w="1.2q"; eq1_g="3.0"
  eq2_f="2400"; eq2_w="1.0q"; eq2_g="2.2"

  headroomDb="1.0"
  normalize="1"
  oggQuality="5"

  case "$p" in
    halo|marine)
      wet="0.34"
      combHz="235"
      combDecay="0.20"
      lopass="7200"
      eq1_g="3.5"
      eq2_g="2.5"
      ;;
    mild)
      wet="0.24"
      combDecay="0.14"
      eq1_g="2.0"
      eq2_g="1.5"
      ;;
    heavy)
      wet="0.55"
      wetGain="1.10"
      hipass="280"
      lopass="5600"
      innerLP="3000"
      combHz="250"
      combDecay="0.32"
      slapDecay="0.14"
      eq1_g="5.0"
      eq2_g="3.5"
      headroomDb="1.5"
      oggQuality="6"
      ;;
    radio)
      wet="0.28"
      hipass="500"
      lopass="3200"
      innerLP="2200"
      combHz="210"
      combDecay="0.12"
      slapDecay="0.06"
      eq1_g="1.5"
      eq2_g="1.2"
      ;;
    *)
      die "unknown preset: $p"
      ;;
  esac
}

tmpdir=""
keep_tmp=0
cleanup() {
  if [[ "$keep_tmp" == "1" ]]; then
    [[ -n "${tmpdir:-}" ]] && log "keeping tmpdir: $tmpdir"
    return 0
  fi
  [[ -n "${tmpdir:-}" && -d "$tmpdir" ]] && rm -rf "$tmpdir"
}
trap cleanup EXIT

mk_tmpdir() {
  tmpdir="$(mktemp -d -t armorfx.XXXXXX)"
  if [[ "$DEBUG" == "1" ]]; then
    log "tmpdir: $tmpdir"
  fi
}

clamp01() {
  local x="$1"
  "$AWK_BIN" -v x="$x" 'BEGIN{ if(x<0)x=0; if(x>1)x=1; printf "%.3f", x }'
}

calc_ms_from_hz() {
  local hz="$1"
  "$AWK_BIN" -v hz="$hz" 'BEGIN{ if(hz<=0){print 5; exit} printf "%.3f", (1000.0/hz) }'
}

# If width is a plain number, treat it as Q by appending "q"
normalize_width() {
  local w="$1"
  if [[ "$w" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
    echo "${w}q"
  else
    echo "$w"
  fi
}

decode_to_wav_44100_mono() {
  local in="$1"
  local outwav="$2"

  if "$SOX_BIN" "$in" -r "$DEV_SR" -c 1 "$outwav" >/dev/null 2>&1; then
    return 0
  fi

  if command -v ffmpeg >/dev/null 2>&1; then
    log "$SOX_BIN could not decode '$in'; using ffmpeg fallback (decode only)"
    ffmpeg -v error -y -i "$in" -ar "$DEV_SR" -ac 1 "$outwav"
    return 0
  fi

  die "cannot decode '$in' with $SOX_BIN (and ffmpeg not available)"
}

encode_ogg_44100_mono() {
  local inwav="$1"
  local outogg="$2"

  if "$SOX_BIN" -r "$DEV_SR" -c 1 -C "$oggQuality" "$inwav" "$outogg" >/dev/null 2>&1; then
    return 0
  fi

  if command -v ffmpeg >/dev/null 2>&1; then
    log "$SOX_BIN could not encode ogg; using ffmpeg fallback (encode only)"
    ffmpeg -v error -y -i "$inwav" -ar "$DEV_SR" -ac 1 -c:a libvorbis -q:a 5 "$outogg"
    return 0
  fi

  die "could not encode ogg with $SOX_BIN (and ffmpeg not available)"
}

dump_params() {
  local combMs
  combMs="$(calc_ms_from_hz "$combHz")"
  cat <<EOF
resolved parameters:
  wet=$wet wetGain=$wetGain (effective wet = clamped wet*wetGain)
  hipass=$hipass lopass=$lopass innerLP=$innerLP
  combHz=$combHz combMs=$combMs combDecay=$combDecay
  slapMs=$slapMs slapDecay=$slapDecay
  eq1: f=$eq1_f w=$eq1_w g=$eq1_g
  eq2: f=$eq2_f w=$eq2_w g=$eq2_g
  normalize=$normalize headroomDb=$headroomDb oggQuality=$oggQuality
EOF
}

apply_effect() {
  local in="$1"
  local out="$2"
  local dry_run="$3"
  local print_cmd="$4"
  local play_after="$5"
  local dump="$6"
  local wet_only="$7"

  [[ -f "$in" ]] || die "input not found: $in"
  [[ "${out,,}" == *.ogg ]] || die "output must be .ogg: $out"

  log "apply start: in=$in out=$out sr=$DEV_SR"

  mk_tmpdir
  local drywav="$tmpdir/dry.wav"
  local wetwav="$tmpdir/wet.wav"
  local mixwav="$tmpdir/mix.wav"
  local finalwav="$tmpdir/final.wav"

  wet="$("$AWK_BIN" -v w="$wet" -v g="$wetGain" 'BEGIN{w=w*g; if(w<0)w=0; if(w>1)w=1; printf "%.3f", w}')"
  local dry_level
  dry_level="$("$AWK_BIN" -v w="$wet" 'BEGIN{printf "%.6f", (1.0-w)}')"

  local combMs
  combMs="$(calc_ms_from_hz "$combHz")"

  eq1_w="$(normalize_width "$eq1_w")"
  eq2_w="$(normalize_width "$eq2_w")"

  if [[ "$dump" == "1" ]]; then
    dump_params
  fi

  local wet_chain=(
    highpass "$hipass"
    lowpass "$lopass"
    equalizer "$eq1_f" "$eq1_w" "$eq1_g"
    equalizer "$eq2_f" "$eq2_w" "$eq2_g"
    lowpass "$innerLP"
    echo 0.75 0.75 "$slapMs" "$slapDecay" "$combMs" "$combDecay"
    lowpass "$lopass"
  )

  local cmd_decode=( "$SOX_BIN" "$in" -r "$DEV_SR" -c 1 "$drywav" )
  local cmd_wet=( "$SOX_BIN" "$drywav" "$wetwav" "${wet_chain[@]}" )
  local cmd_mix=( "$SOX_BIN" -m -v "$dry_level" "$drywav" -v "$wet" "$wetwav" "$mixwav" )

  local cmd_gain=()
  if [[ "$normalize" == "1" ]]; then
    cmd_gain=( "$SOX_BIN" "$mixwav" "$finalwav" gain -n "-$headroomDb" )
  else
    cmd_gain=( "$SOX_BIN" "$mixwav" "$finalwav" gain -3 )
  fi

  if [[ "$print_cmd" == "1" || "$dry_run" == "1" ]]; then
    echo
    echo "sox_ng decode:"
    printf '  %q' "${cmd_decode[@]}"; echo
    echo "sox_ng wet:"
    printf '  %q' "${cmd_wet[@]}"; echo
    echo "sox_ng mix:"
    printf '  %q' "${cmd_mix[@]}"; echo
    echo "sox_ng final:"
    printf '  %q' "${cmd_gain[@]}"; echo
    echo
  fi

  if [[ "$dry_run" == "1" ]]; then
    log "dry-run: not executing"
    return 0
  fi

  decode_to_wav_44100_mono "$in" "$drywav"
  "${cmd_wet[@]}"

  if [[ "$wet_only" == "1" ]]; then
    encode_ogg_44100_mono "$wetwav" "$out"
    log "wrote (wet-only): $out"
    return 0
  fi

  "${cmd_mix[@]}"
  "${cmd_gain[@]}"
  encode_ogg_44100_mono "$finalwav" "$out"
  log "wrote: $out"

  if [[ "$play_after" == "1" ]]; then
    if command -v "$PLAY_BIN" >/dev/null 2>&1; then
      "$PLAY_BIN" "$out" >/dev/null 2>&1 || true
    elif command -v play >/dev/null 2>&1; then
      play "$out" >/dev/null 2>&1 || true
    fi
  fi
}

usage() {
  cat <<EOF
$SCRIPT_NAME (sox_ng) outputs mono .ogg @ 44.1k

Commands:
  presets
  apply -i in.ogg -o out.ogg [options]

apply options:
  --preset halo|mild|heavy|radio
  --wet N
  --wet-gain N
  --hipass HZ
  --lopass HZ
  --innerlp HZ
  --comb-hz HZ
  --comb-decay N
  --slap-ms MS
  --slap-decay N
  --eq1 f width gainDb     (width can be "1.2q" or just "1.2")
  --eq2 f width gainDb
  --headroom DB
  --no-normalize
  --quality N
  --wet-only               output only the processed path (debug)
  --print-cmd
  --dry-run
  --dump-params
  --keep-tmp
  --play

Debug:
  TRACE=1 ./armorfx.sh ...
EOF
}

cmd="${1:-}"
shift || true

case "$cmd" in
  presets)
    presets_list
    ;;
  apply)
    in=""; out=""
    preset="halo"
    dry_run=0
    print_cmd=0
    play_after=0
    dump=0
    wet_only=0

    preset_apply "$preset"

    while [[ $# -gt 0 ]]; do
      case "$1" in
        -i|--in) in="$2"; shift 2 ;;
        -o|--out) out="$2"; shift 2 ;;
        --preset) preset="$2"; preset_apply "$preset"; shift 2 ;;
        --wet) wet="$(clamp01 "$2")"; shift 2 ;;
        --wet-gain) wetGain="$2"; shift 2 ;;
        --hipass) hipass="$2"; shift 2 ;;
        --lopass) lopass="$2"; shift 2 ;;
        --innerlp) innerLP="$2"; shift 2 ;;
        --comb-hz) combHz="$2"; shift 2 ;;
        --comb-decay) combDecay="$2"; shift 2 ;;
        --slap-ms) slapMs="$2"; shift 2 ;;
        --slap-decay) slapDecay="$2"; shift 2 ;;
        --eq1) eq1_f="$2"; eq1_w="$3"; eq1_g="$4"; shift 4 ;;
        --eq2) eq2_f="$2"; eq2_w="$3"; eq2_g="$4"; shift 4 ;;
        --headroom) headroomDb="$2"; shift 2 ;;
        --no-normalize) normalize="0"; shift 1 ;;
        --quality) oggQuality="$2"; shift 2 ;;
        --wet-only) wet_only=1; shift 1 ;;
        --print-cmd) print_cmd=1; shift 1 ;;
        --dry-run) dry_run=1; shift 1 ;;
        --dump-params) dump=1; shift 1 ;;
        --keep-tmp) keep_tmp=1; shift 1 ;;
        --play) play_after=1; shift 1 ;;
        -h|--help) usage; exit 0 ;;
        *) die "unknown arg: $1" ;;
      esac
    done

    [[ -n "$in" && -n "$out" ]] || die "apply requires -i INPUT -o OUTPUT.ogg"
    apply_effect "$in" "$out" "$dry_run" "$print_cmd" "$play_after" "$dump" "$wet_only"
    ;;
  ""|-h|--help|help)
    usage
    ;;
  *)
    die "unknown command: $cmd"
    ;;
esac
