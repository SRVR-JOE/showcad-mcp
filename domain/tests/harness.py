"""Test harness — drives this repo's dispatcher against mock_vs.

Three things live here that the old standalone harness did not need:

1. **`vs` injection by sys.modules.** `vwx-plugin/commands.py` line 20 does a
   hard ``import vs`` at module scope. There is no ``set_vs()`` hook in this
   repo (the old ``vw-plugin/pump.py`` had one, see
   ``domain/reference_handlers.py:26``). So the mock must be bound to the name
   ``vs`` in ``sys.modules`` BEFORE any plugin module is imported.

2. **Verb lookup across three modules.** ``vwx_pump._dispatch`` only ever does
   ``getattr(commands, cmd)`` — it does NOT know about ``cc_commands.py`` or
   ``sl_commands.py``. The harness resolves verbs across all three and reports
   which module answered, so a verb that exists but is unreachable through the
   production pump is visible rather than silently "passing".

3. **Two dispatch modes.** ``dispatch_pump`` is the real production path (and
   swallows exceptions into ``{'error': ...}``, so "never raises" is trivially
   true through it). ``dispatch_direct`` is the raw
   ``getattr(module, cmd)(params)`` contract with NO safety net, which is what
   actually proves a verb handles bad input itself.
"""
import importlib
import os
import sys
import traceback

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(TESTS_DIR))
PLUGIN_DIR = os.path.join(REPO_ROOT, 'vwx-plugin')

for _p in (TESTS_DIR, PLUGIN_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ── step 1: bind the mock to the name `vs` before anything imports it ───────
import mock_vs                                             # noqa: E402

if sys.modules.get('vs') is not mock_vs:
    if 'vs' in sys.modules:
        raise RuntimeError('a real `vs` module is already imported — refusing '
                           'to shadow it')
    sys.modules['vs'] = mock_vs

# ── step 2: lazy, non-fatal imports of the plugin modules ──────────────────
# cc_commands.py / sl_commands.py are being written concurrently and may not
# exist yet. Absence is a clean SKIP, never an error.

MODULE_NAMES = ('cc_commands', 'sl_commands', 'commands')
_modules = {}
_import_errors = {}


def load_modules(force=False):
    """Import (or re-import) the plugin modules. Returns {name: module}."""
    if _modules and not force:
        return _modules
    _modules.clear()
    _import_errors.clear()
    for name in MODULE_NAMES:
        path = os.path.join(PLUGIN_DIR, name + '.py')
        if not os.path.exists(path):
            _import_errors[name] = 'not written yet (%s does not exist)' % path
            continue
        try:
            if name in sys.modules:
                mod = importlib.reload(sys.modules[name])
            else:
                mod = importlib.import_module(name)
            _modules[name] = mod
        except Exception as e:
            _import_errors[name] = '%s: %s' % (type(e).__name__, e)
    return _modules


def import_errors():
    load_modules()
    return dict(_import_errors)


def module_status():
    """Human-readable one-liner per plugin module."""
    load_modules()
    out = []
    for name in MODULE_NAMES:
        if name in _modules:
            n = len([k for k in dir(_modules[name])
                     if k.startswith(('cc_', 'sl_', 'doc_'))])
            out.append('%-12s loaded  (%d cc_/sl_/doc_ verbs)' % (name, n))
        else:
            out.append('%-12s SKIP    %s' % (name, _import_errors.get(name, '?')))
    return out


# ── step 3: verb resolution ────────────────────────────────────────────────

def resolve(cmd):
    """Find a verb across the plugin modules.

    Returns (module_name, callable) or (None, None). Tries the exact name
    first, then a small set of naming variants so a verb named slightly
    differently is still found and reported rather than silently missing.
    """
    load_modules()
    candidates = [cmd]
    if cmd.startswith(('cc_', 'sl_')):
        candidates.append(cmd[3:])                 # cc_list_devices -> list_devices
    candidates.append(cmd.replace('cc_', '').replace('sl_', ''))
    for name in MODULE_NAMES:
        mod = _modules.get(name)
        if mod is None:
            continue
        for cand in candidates:
            fn = getattr(mod, cand, None)
            if callable(fn):
                return name, fn
    return None, None


def pump_reachable(cmd):
    """True if ``getattr(commands, cmd)`` resolves — i.e. the REAL
    ``vwx_pump._dispatch`` can reach this verb. A verb living only in
    cc_commands.py is NOT reachable and will answer
    ``{'error': 'Unknown command: ...'}`` in production."""
    load_modules()
    mod = _modules.get('commands')
    return bool(mod is not None and callable(getattr(mod, cmd, None)))


# ── step 4: dispatch ───────────────────────────────────────────────────────

class Raised(Exception):
    """A verb raised out of the raw dispatcher contract."""

    def __init__(self, cmd, exc):
        Exception.__init__(self, '%s raised %s: %s'
                           % (cmd, type(exc).__name__, exc))
        self.cmd = cmd
        self.exc = exc
        self.tb = traceback.format_exc()


def dispatch_direct(cmd, params=None):
    """The repo's raw contract: ``getattr(module, cmd)(params)``.

    NO try/except — a verb that raises here fails the "never raises" rule.
    Raises Raised (wrapping the original) or KeyError if the verb is missing.
    """
    modname, fn = resolve(cmd)
    if fn is None:
        raise KeyError('no such verb in %s: %s' % (list(_modules), cmd))
    try:
        return fn(params if params is not None else {})
    except Exception as e:
        raise Raised(cmd, e)


_pump = None


def dispatch_pump(cmd, params=None):
    """The production path: ``vwx_pump._dispatch``.

    Only reaches ``commands.py`` — that is the point of running it.
    """
    global _pump
    if _pump is None:
        _pump = importlib.import_module('vwx_pump')
    return _pump._dispatch(cmd, params if params is not None else {})


# ── step 5: result-shape helpers ───────────────────────────────────────────
# Old harness asserted on BARE LISTS (``len(devs) == 6``). This repo's contract
# is dict-per-command. These helpers accept either so the ported content checks
# still say something useful, while the dict contract is asserted separately.

_ROW_KEYS = ('devices', 'circuits', 'fixtures', 'rows', 'items', 'results',
             'issues', 'hops', 'positions', 'data', 'list')


def rows(result):
    """Extract the row list from a verb result, dict-or-list tolerant."""
    if isinstance(result, list):
        return result
    if not isinstance(result, dict):
        return []
    for k in _ROW_KEYS:
        v = result.get(k)
        if isinstance(v, list):
            return v
    lists = [v for v in result.values() if isinstance(v, list)]
    return lists[0] if len(lists) == 1 else []


def is_error(result):
    return isinstance(result, dict) and bool(result.get('error'))


def field(row, *names):
    """Read the first present key from a row, tolerating naming variants.
    Used ONLY to locate content, never to assert a name is correct."""
    if not isinstance(row, dict):
        return None
    for n in names:
        if n in row and row[n] not in (None, ''):
            return row[n]
    return None


def flatten(obj):
    """All scalar strings anywhere in a nested result — lets content checks
    ('is SRV 1 / DP OUT 2 in here?') survive an unknown result schema."""
    out = []
    stack = [obj]
    while stack:
        o = stack.pop()
        if isinstance(o, dict):
            stack.extend(o.values())
        elif isinstance(o, (list, tuple)):
            stack.extend(o)
        elif isinstance(o, str):
            out.append(o)
    return out
