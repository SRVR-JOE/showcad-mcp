# VWX Pump (macOS) -- paste this as the script of a Python MENU COMMAND plugin.
#
#   Tools > Plug-ins > Plug-in Manager > Custom Plug-ins > New...
#     Type: Command      Name: VWX Pump
#     Edit Script...  ->  SET THE LANGUAGE TO PYTHON  <- VectorScript is the
#     default and silently mis-compiles this file.
#   Then Tools > Workspaces > Edit Current Workspace: put "VWX Pump" on a menu
#   and give it Cmd+Shift+B.  Restart Vectorworks.
#
# One press drains the entire MCP job queue.  This is VW's own Python
# menu-command runner -- the only context, on either platform, verified to
# carry a full document/undo context AND run the parametric engine, which is
# what the legacy RunLayoutDialog bridge could not do.
#
# The same body also works pasted into a Script Palette script (Resource
# Manager > New Resource > Script), which is the fastest way to test it
# without restarting Vectorworks.
import os
import sys
import importlib

_PLUGIN_NAMES = ('VWX-MCP', 'VW-MCP')
_ROOTS = (os.path.expanduser('~/Library/Application Support/Vectorworks'),
          '/Library/Application Support/Vectorworks')


def _find_dir():
    env = os.environ.get('VWX_PLUGIN_DIR')
    if env and os.path.isdir(env):
        return env
    try:
        import vs
        found = vs.FindFileInPluginFolder('mac_executor.py')
        path = None
        if isinstance(found, (tuple, list)) and len(found) >= 2 and found[0]:
            path = found[1]
        elif isinstance(found, str) and found:
            path = found
        if path and os.path.isfile(path):
            return os.path.dirname(path)
    except Exception:
        pass
    forced = os.environ.get('VWX_VW_VERSION')
    for root in _ROOTS:
        if forced:
            versions = [forced]
        else:
            try:
                versions = sorted((d for d in os.listdir(root)
                                   if len(d) == 4 and d.isdigit()), reverse=True)
            except Exception:
                versions = []
        for v in versions:
            for name in _PLUGIN_NAMES:
                cand = os.path.join(root, v, 'Plug-ins', name)
                if os.path.isdir(cand):
                    return cand
    return None


_dir = _find_dir()
if _dir and _dir not in sys.path:
    sys.path.insert(0, _dir)

if not _dir:
    import vs
    vs.AlrtDialog('VWX Pump: plug-in folder not found. Expected '
                  '~/Library/Application Support/Vectorworks/<year>/'
                  'Plug-ins/VWX-MCP/ containing mac_executor.py.')
else:
    import mac_executor
    # Hot-reload only when the file actually changed on disk: the mtime marker
    # rides on the module object, which survives in sys.modules between menu
    # invocations, so an edited executor takes effect on the next press without
    # paying a recompile on every press.
    try:
        _mt = os.path.getmtime(os.path.join(_dir, 'mac_executor.py'))
    except Exception:
        _mt = 0.0
    if getattr(mac_executor, '_vwx_loaded_mtime', None) != _mt:
        importlib.reload(mac_executor)
        mac_executor._vwx_loaded_mtime = _mt
    mac_executor.run()
