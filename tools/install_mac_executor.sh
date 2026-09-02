#!/bin/bash
# Install the macOS VWX executor into the Vectorworks user plug-in folder.
#
#   tools/install_mac_executor.sh              # dry run: show what it would do
#   tools/install_mac_executor.sh --apply      # do it
#   tools/install_mac_executor.sh --apply --force   # also overwrite existing
#
# Copies ONLY the new macOS executor files.  It never touches commands.py,
# cc_commands.py, sl_commands.py, cc_build.py, vwx_pump.py or vwx_mcp_bridge.py
# -- a live bridge may be using those.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$REPO/vwx-plugin"
APPLY=0
FORCE=0
for arg in "$@"; do
  case "$arg" in
    --apply) APPLY=1 ;;
    --force) FORCE=1 ;;
    *) echo "unknown argument: $arg" >&2; exit 2 ;;
  esac
done

find_dir() {
  if [ -n "${VWX_PLUGIN_DIR:-}" ] && [ -d "$VWX_PLUGIN_DIR" ]; then
    echo "$VWX_PLUGIN_DIR"; return 0
  fi
  for root in "$HOME/Library/Application Support/Vectorworks" \
              "/Library/Application Support/Vectorworks"; do
    [ -d "$root" ] || continue
    for ver in $(ls -1 "$root" 2>/dev/null | grep -E '^[0-9]{4}$' | sort -r); do
      for name in VWX-MCP VW-MCP; do
        cand="$root/$ver/Plug-ins/$name"
        [ -d "$cand" ] && { echo "$cand"; return 0; }
      done
    done
  done
  return 1
}

DEST="$(find_dir)" || {
  echo "ERROR: no Vectorworks plug-in folder found." >&2
  echo "Expected ~/Library/Application Support/Vectorworks/<year>/Plug-ins/VWX-MCP" >&2
  echo "Set VWX_PLUGIN_DIR to override." >&2
  exit 1
}

echo "repo:        $REPO"
echo "plug-in dir: $DEST"
echo

FILES="mac_executor.py MacPump_MenuCommand.py MacPumpSelfTest_MenuCommand.py"
for f in $FILES; do
  if [ -e "$DEST/$f" ] && [ "$FORCE" -eq 0 ]; then
    echo "  skip (exists, use --force):  $f"
  else
    echo "  copy:                        $f"
    [ "$APPLY" -eq 1 ] && cp "$SRC/$f" "$DEST/$f"
  fi
done

echo "  mkdir:                       ipc/jobs ipc/results"
if [ "$APPLY" -eq 1 ]; then
  mkdir -p "$DEST/ipc/jobs" "$DEST/ipc/results"
  # Prime the heartbeat the MCP server's fail-fast reads.  Without a
  # native.alive file the very first job is discarded after VWX_ALIVE_GRACE
  # (20s) with VW_BRIDGE_DOWN, before anyone can press the hotkey.
  printf '%s 0' "$(date +%s)" > "$DEST/ipc/native.alive"
  echo "  wrote:                       ipc/native.alive (primed)"
fi

echo
if [ "$APPLY" -eq 0 ]; then
  echo "DRY RUN -- nothing was written.  Re-run with --apply."
  exit 0
fi

cat <<EOF
Installed.  Next:

1) VERIFY (5 min, no Vectorworks restart needed)
   In VW: Resource Manager > New Resource > Script > new palette, new script.
   SET THE LANGUAGE TO PYTHON (VectorScript is the default and silently
   mis-compiles Python).  Paste the contents of:
       $SRC/MacPumpSelfTest_MenuCommand.py
   Run it.  A non-zero bbox for 'Angle' means the parametric engine runs.

2) INSTALL THE HOTKEY EXECUTOR
   Tools > Plug-ins > Plug-in Manager > Custom Plug-ins > New... > Command,
   name "VWX Pump", Edit Script (LANGUAGE: PYTHON), paste:
       $SRC/MacPump_MenuCommand.py
   Tools > Workspaces > Edit Current Workspace: add "VWX Pump" to a menu and
   assign Cmd+Shift+B.  Restart Vectorworks.

3) POINT THE MCP SERVER AT THE FILE TRANSPORT
   export VWX_TRANSPORT=file
   export VWX_PLUGIN_DIR="$DEST"
   export VWX_ALIVE_MAX_AGE=604800     # no native palette on macOS
   export VWX_SOCKET_TIMEOUT=880       # time for you to press the hotkey

Full detail: domain/docs/MACOS-EXECUTOR.md
EOF
