#!/bin/zsh
set -euo pipefail

timestamp="$(date '+%Y%m%d-%H%M%S')"
session_root="${TRIAD_DEBUG_CAPTURE_ROOT:-$HOME/Desktop/triad_debug_sessions}"
session_dir="$session_root/triad-debug-$timestamp"
triad_home="${TRIAD_HOME:-$HOME/.triad}"
triad_app="/Applications/Triad.app"
triad_bin="$triad_app/Contents/MacOS/Triad"
triad_app_server="$triad_app/Contents/Resources/codex"
desktop_logs_root="$HOME/Library/Logs/com.triad.orchestrator"
app_support_dir="$HOME/Library/Application Support/Triad"
proxy_log_path="$triad_home/logs/triad-proxy.log"

mkdir -p "$session_dir"

meta_log="$session_dir/meta.log"
process_log="$session_dir/processes.log"
desktop_log="$session_dir/desktop.log"
proxy_log="$session_dir/proxy.log"
triad_stdout_log="$session_dir/triad-stdout.log"

process_watcher_pid=""
desktop_watcher_pid=""
proxy_watcher_pid=""
launched_pid=""

log() {
  local line="[$(date '+%Y-%m-%dT%H:%M:%S%z')] $*"
  print -r -- "$line" | tee -a "$meta_log" >/dev/null
}

copy_if_exists() {
  local src="$1"
  local dst="$2"
  if [[ -e "$src" ]]; then
    cp -R "$src" "$dst"
  fi
}

snapshot_state() {
  mkdir -p "$session_dir/state"
  copy_if_exists "$triad_home/.codex-global-state.json" "$session_dir/state/.codex-global-state.json"
  copy_if_exists "$triad_home/config.toml" "$session_dir/state/config.toml"
  copy_if_exists "$triad_home/config.yaml" "$session_dir/state/config.yaml"
  copy_if_exists "$app_support_dir/Preferences" "$session_dir/state/Preferences"
}

track_processes() {
  while true; do
    {
      print -r -- ""
      print -r -- "=== $(date '+%Y-%m-%d %H:%M:%S') ==="
      ps ax -o pid=,ppid=,pgid=,state=,etime=,command= \
        | grep -E 'Triad|/Applications/Triad.app|/Applications/Triad.app/Contents/Resources/codex|triad app-server' \
        | grep -v 'grep -E' || true
    } >>"$process_log"
    sleep 1
  done
}

track_latest_desktop_log() {
  local last_log=""
  local tail_pid=""

  while true; do
    local latest_log
    latest_log="$(python3 - "$desktop_logs_root" <<'PY'
from pathlib import Path
import sys
root = Path(sys.argv[1])
logs = sorted(root.rglob("codex-desktop-*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
print(logs[0] if logs else "")
PY
)"
    if [[ -n "$latest_log" && "$latest_log" != "$last_log" ]]; then
      if [[ -n "$tail_pid" ]]; then
        kill "$tail_pid" 2>/dev/null || true
      fi
      print -r -- "" >>"$desktop_log"
      print -r -- "=== tracking $latest_log ===" >>"$desktop_log"
      tail -n 200 -F "$latest_log" >>"$desktop_log" 2>&1 &
      tail_pid="$!"
      last_log="$latest_log"
      log "tracking desktop log: $latest_log"
    fi
    sleep 1
  done
}

track_proxy_log() {
  mkdir -p "$(dirname "$proxy_log_path")"
  : >>"$proxy_log_path"
  tail -n 200 -F "$proxy_log_path" >>"$proxy_log" 2>&1
}

cleanup() {
  local exit_code="$?"
  log "stopping debug capture (exit=$exit_code)"

  if [[ -n "$process_watcher_pid" ]]; then
    kill "$process_watcher_pid" 2>/dev/null || true
  fi
  if [[ -n "$desktop_watcher_pid" ]]; then
    kill "$desktop_watcher_pid" 2>/dev/null || true
  fi
  if [[ -n "$proxy_watcher_pid" ]]; then
    kill "$proxy_watcher_pid" 2>/dev/null || true
  fi

  snapshot_state
}

trap cleanup EXIT INT TERM

snapshot_state

log "session_dir=$session_dir"
log "triad_home=$triad_home"
log "triad_bin=$triad_bin"

track_processes &
process_watcher_pid="$!"

track_latest_desktop_log &
desktop_watcher_pid="$!"

track_proxy_log &
proxy_watcher_pid="$!"

log "killing stale Triad processes"
pkill -f "$triad_app_server app-server" 2>/dev/null || true
pkill -f "$triad_bin" 2>/dev/null || true
pkill -x Triad 2>/dev/null || true
sleep 1

log "launching Triad with Electron logging enabled"
(
  export TRIAD_HOME="$triad_home"
  export CODEX_HOME="$triad_home"
  export TRIAD_DEBUG_STARTUP=1
  export TRIAD_DEBUG_SESSION_DIR="$session_dir"
  export ELECTRON_ENABLE_LOGGING=1
  export ELECTRON_ENABLE_STACK_DUMPING=1
  exec "$triad_bin"
) >>"$triad_stdout_log" 2>&1 &
launched_pid="$!"

log "launch_pid=$launched_pid"
log "reproduce the gray screen, then stop this script with Ctrl+C"

wait "$launched_pid" || true
