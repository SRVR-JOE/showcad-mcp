# VWX Pump Self-Test -- paste as a second Python MENU COMMAND named
# "VWX Pump Self-Test", or (faster, no VW restart) as a Script Palette script:
#   Resource Manager > New Resource > Script > ... > LANGUAGE: PYTHON.
#
# THE ACCEPTANCE TEST.  It answers one question: does the Vectorworks
# parametric engine run in this execution context?
#
#   phase 1  CreateCustomObjectN('Angle'|'Ball Bearing'|'Base Cabinet', 5, 5,
#            0, False) -> bbox.  Under the legacy dialog bridge every bbox is
#            ((0,0),(0,0)) and FInGroup is empty.  A NON-ZERO bbox is the pass.
#            The probe objects are deleted again.
#   phase 2  if exactly one ConnectCAD circuit is selected: read its bbox,
#            toggle a boolean field, ResetObject, read the bbox again, then put
#            the field back.  A changed bbox means the PIO really recalculated.
#
# Results are shown in a dialog AND written to ipc/selftest.json in the plug-in
# folder, so they can be read from outside Vectorworks.
import os
import sys
import io
import json
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


import vs

_dir = _find_dir()
if _dir and _dir not in sys.path:
    sys.path.insert(0, _dir)

if not _dir:
    vs.AlrtDialog('VWX Self-Test: plug-in folder not found. Expected '
                  '~/Library/Application Support/Vectorworks/<year>/'
                  'Plug-ins/VWX-MCP/ containing mac_executor.py.')
else:
    import mac_executor
    try:
        _mt = os.path.getmtime(os.path.join(_dir, 'mac_executor.py'))
    except Exception:
        _mt = 0.0
    if getattr(mac_executor, '_vwx_loaded_mtime', None) != _mt:
        importlib.reload(mac_executor)
        mac_executor._vwx_loaded_mtime = _mt

    report = {'phase1_parametric_engine': mac_executor.self_test(),
              'status': mac_executor.status()}
    # Phase 2 only runs when something is selected, so the test never touches
    # the drawing unless the user pointed it at an object.
    try:
        if vs.FSActLayer():
            report['phase2_connectcad_circuit'] = mac_executor.circuit_test()
        else:
            report['phase2_connectcad_circuit'] = {
                'skipped': 'nothing selected - select one ConnectCAD circuit '
                           'and run again for phase 2'}
    except Exception as e:
        report['phase2_connectcad_circuit'] = {'error': str(e)}

    try:
        _out = os.path.join(_dir, 'ipc', 'selftest.json')
        os.makedirs(os.path.dirname(_out), exist_ok=True)
        with io.open(_out, 'w', encoding='utf-8') as _fh:
            _fh.write(json.dumps(report, indent=2, ensure_ascii=False,
                                 default=str))
    except Exception:
        _out = '(could not write ipc/selftest.json)'

    _p1 = report['phase1_parametric_engine']
    _lines = [_p1.get('verdict', '?'), '']
    for _pr in _p1.get('probes', []):
        _lines.append('%-14s bbox=%s children=%s'
                      % (_pr.get('name'), _pr.get('bbox'), _pr.get('children')))
    _p2 = report['phase2_connectcad_circuit']
    _lines.append('')
    _lines.append('phase 2: ' + str(_p2.get('verdict')
                                    or _p2.get('skipped')
                                    or _p2.get('error')))
    _lines.append('')
    _lines.append('full report: ' + str(_out))
    vs.AlrtDialog('\n'.join(_lines))
