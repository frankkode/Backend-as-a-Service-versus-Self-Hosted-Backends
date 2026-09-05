#!/usr/bin/env bash
# Operational-effort measurement harness (thesis Section 3.5 / 5.3).
#
# Converts the operational-effort input of the TCO model from an estimate into
# measured task durations x documented frequencies.
#
# Usage:
#   ./scripts/measure_ops_effort.sh start  <variant> <task_id>
#   ./scripts/measure_ops_effort.sh stop   <variant> <task_id> ["optional note"]
#   ./scripts/measure_ops_effort.sh na     <variant> <task_id> ["reason"]   # log a 0-duration N/A
#   ./scripts/measure_ops_effort.sh status                                   # show running timers
#   ./scripts/measure_ops_effort.sh reset                                    # clear ALL running timers
#
#   <variant> : supabase | django
#   <task_id> : os_patching | image_update | backup_run | backup_verify
#               health_check | dependency_triage | tls_renewal
#
# Example:
#   ./scripts/measure_ops_effort.sh start django os_patching
#   ... actually do the work, start to finish ...
#   ./scripts/measure_ops_effort.sh stop django os_patching "14 packages, 1 reboot"
#
# For tasks the platform handles for you (Supabase OS patching, etc.):
#   ./scripts/measure_ops_effort.sh na supabase os_patching "platform-managed"
#
# Rules for a defensible measurement:
#   - Time the WHOLE task: from opening the terminal/dashboard to being satisfied it is done.
#   - Include waiting time you must supervise; exclude time you walked away.
#   - Run each task at least twice on different days and use the mean (variance matters).
#   - Do not rehearse. The first honest run is the representative one.
#
# Safety: a timer older than STALE_HOURS is treated as abandoned. 'start' will discard it
# and begin a fresh measurement rather than silently timing from a forgotten start.
#
# Output: results/ops_effort_log.csv  (append-only; commit it as raw evidence)

set -euo pipefail
cd "$(dirname "$0")/.."

LOG="results/ops_effort_log.csv"
STATE_DIR=".ops_timer"
STALE_HOURS=4
VALID_TASKS="os_patching image_update backup_run backup_verify health_check dependency_triage tls_renewal"

mkdir -p "$STATE_DIR" results
if [ ! -f "$LOG" ]; then
  echo "variant,task_id,started_at,ended_at,duration_seconds,duration_minutes,note" > "$LOG"
fi

fmt_time() { date -r "$1" '+%Y-%m-%d %H:%M:%S' 2>/dev/null || date -d "@$1" '+%Y-%m-%d %H:%M:%S'; }

append_row() {  # variant task start_epoch end_epoch note
  local dur mins started ended clean
  dur=$(( $4 - $3 ))
  mins=$(awk "BEGIN{printf \"%.2f\", $dur/60}")
  started=$(fmt_time "$3"); ended=$(fmt_time "$4")
  clean=$(printf '%s' "${5:-}" | tr ',' ';' | tr -d '\n')
  echo "$1,$2,$started,$ended,$dur,$mins,$clean" >> "$LOG"
  echo "$mins"
}

ACTION="${1:-}"

# --- actions that take no variant/task ---
case "$ACTION" in
  status)
    shopt -s nullglob
    found=0
    for f in "$STATE_DIR"/*; do
      found=1
      age=$(( $(date +%s) - $(cat "$f") ))
      printf '  running: %-32s started %s (%d min ago)\n' \
        "$(basename "$f")" "$(fmt_time "$(cat "$f")")" "$(( age / 60 ))"
    done
    [ "$found" -eq 0 ] && echo "  no timers running."
    exit 0 ;;
  reset)
    rm -f "$STATE_DIR"/* 2>/dev/null || true
    echo "All running timers cleared. (The measurement log $LOG was NOT touched.)"
    exit 0 ;;
esac

VARIANT="${2:-}"; TASK="${3:-}"; NOTE="${4:-}"

if [ -z "$ACTION" ] || [ -z "$VARIANT" ] || [ -z "$TASK" ]; then
  sed -n '2,32p' "$0" | sed 's/^# \{0,1\}//'
  exit 1
fi

case "$VARIANT" in
  supabase|django) ;;
  *) echo "ERROR: variant must be 'supabase' or 'django' (got '$VARIANT')"; exit 1 ;;
esac

case " $VALID_TASKS " in
  *" $TASK "*) ;;
  *) echo "ERROR: unknown task '$TASK'"; echo "Valid: $VALID_TASKS"; exit 1 ;;
esac

STATE_FILE="$STATE_DIR/${VARIANT}_${TASK}"

case "$ACTION" in
  start)
    if [ -f "$STATE_FILE" ]; then
      prev=$(cat "$STATE_FILE")
      age_h=$(( ( $(date +%s) - prev ) / 3600 ))
      if [ "$age_h" -ge "$STALE_HOURS" ]; then
        echo "NOTE: discarding an abandoned timer for $VARIANT/$TASK (started $(fmt_time "$prev"), ${age_h}h ago)."
        rm -f "$STATE_FILE"
      else
        echo "ERROR: a timer for $VARIANT/$TASK is already running (started $(fmt_time "$prev"))."
        echo "       Finish it with 'stop', or discard it with:"
        echo "         ./scripts/measure_ops_effort.sh reset"
        exit 1
      fi
    fi
    date +%s > "$STATE_FILE"
    echo "[start] $VARIANT / $TASK at $(date '+%H:%M:%S') -- do the task now, then run 'stop'."
    ;;
  stop)
    if [ ! -f "$STATE_FILE" ]; then
      echo "ERROR: no running timer for $VARIANT/$TASK. Did you run 'start' first?"; exit 1
    fi
    start_epoch=$(cat "$STATE_FILE"); end_epoch=$(date +%s)
    age_h=$(( ( end_epoch - start_epoch ) / 3600 ))
    if [ "$age_h" -ge "$STALE_HOURS" ]; then
      echo "REFUSED: that timer has been running ${age_h}h -- almost certainly abandoned, not a real task."
      echo "         Nothing was logged. Clear it and measure again:"
      echo "           ./scripts/measure_ops_effort.sh reset"
      exit 1
    fi
    mins=$(append_row "$VARIANT" "$TASK" "$start_epoch" "$end_epoch" "$NOTE")
    rm -f "$STATE_FILE"
    echo "[stop]  $VARIANT / $TASK = ${mins} min -> appended to $LOG"
    ;;
  na)
    now=$(date +%s)
    append_row "$VARIANT" "$TASK" "$now" "$now" "N/A - ${NOTE:-platform-managed}" >/dev/null
    rm -f "$STATE_FILE" 2>/dev/null || true
    echo "[n/a]   $VARIANT / $TASK logged as 0 min (${NOTE:-platform-managed})"
    ;;
  *)
    echo "ERROR: action must be one of: start | stop | na | status | reset"; exit 1 ;;
esac
