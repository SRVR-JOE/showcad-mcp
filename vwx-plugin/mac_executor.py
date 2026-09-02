#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VWX macOS executor -- the safe mutation/regeneration context for Vectorworks
on macOS.  Pure ASCII on purpose (see NOTE 1).

WHY THIS FILE EXISTS
--------------------
`vwx_mcp_bridge.py` (the legacy TCP bridge) dispatches every script from the
timer callback of a modal `vs.RunLayoutDialog`.  While that dialog owns the
event loop, Vectorworks does NOT run the parametric engine: object creation
and record writes work, but plug-in objects never regenerate.  Proof, live:

    for nm in ('Angle', 'Ball Bearing', 'Base Cabinet'):
        h = vs.CreateCustomObjectN(nm, (5.0, 5.0), 0, False)
        vs.GetBBox(h)        # -> ((0,0),(0,0)),  FInGroup(h) empty

Stock Vectorworks plug-ins, nothing to do with ConnectCAD.  So no ConnectCAD
circuit can ever bind from that bridge: the bind is established inside the
Circuit PIO's recalculate, which never fires.

Upstream solved this on Windows with a three-role split (docs/ARCHITECTURE.md):
a native C++ palette (TRIGGER) posts a Ctrl+Shift+B accelerator, which fires a
Python MENU COMMAND (EXECUTOR) -- VW's own script-plugin runner, the one
context verified to carry a full document/undo context -- which drains the
file-IPC job queue (WORK).  The palette is Windows-only C++.

On macOS the EXECUTOR and the WORK halves port unchanged.  Only the TRIGGER
has no equivalent, and every automated substitute is either unavailable to a
non-admin user (AppleScript `System Events` keystrokes need Accessibility,
which requires an admin unlock) or absent from VW's Python API (there is no
`RegisterNotificationProcedure` in `vs` -- the OnIdle hook is C++ only; the
only Python timer, `RegisterDialogForTimerEvents`, requires exactly the modal
dialog that caused the bug).

So the macOS trigger is a HUMAN KEYSTROKE: one hotkey press drains the whole
queue.  Batch aggressively (`vwx_batch` / `execute_script`) and one press
services an entire build.

NOTE 1 -- Vectorworks' embedded Python runs with an ASCII locale.  Keep this
file ASCII and always pass encoding='utf-8' to open(); a bare open() on a
UTF-8 file raises UnicodeDecodeError inside VW.

NOTE 2 -- this module deliberately does NOT import `vwx_pump`.  vwx_pump
resolves its plug-in directory from %APPDATA% at import time and would need
six private globals monkeypatched to work here.  The IPC contract below is a
faithful twin of vwx_pump's: same job/result file layout, same atomic claim,
same "a crash loses the job (visible timeout) rather than re-running it".
If you change the contract on one side, change it on the other.

NOTE 3 -- there is no read-only/mutation split here.  That split exists on
Windows only because reads can drain in the C++ OnIdle context.  macOS has no
such context, so everything drains in the single safe one.

ENTRY POINTS
------------
    run()          -- what the menu command calls: drain + heartbeat + toast
    pump_all()     -- one full drain of the queue, then return   (PROVEN model)
    pump_window()  -- hold the safe context open for N seconds   (EXPERIMENTAL)
    self_test()    -- the acceptance test: does the parametric engine run here?
    circuit_test() -- phase 2: a selected ConnectCAD circuit, SetRField+Reset
    status()       -- diagnostics dict (paths, queue depth, config)
"""

import io
import os
import json
import sys
import time
import traceback

VERSION = 'mac_executor 1.0'

try:
    import vs
except Exception:                      # importable outside VW for syntax checks
    vs = None


# --------------------------------------------------------------------------
# Plug-in directory discovery
# --------------------------------------------------------------------------
# Order: this module's own directory (it IS the plug-in dir, by construction)
# -> VWX_PLUGIN_DIR -> vs.FindFileInPluginFolder -> filesystem scan of the
# macOS user/workgroup plug-in roots.  The later probes exist for the
# menu-command wrapper, which VW executes as <string> and therefore has no
# __file__ of its own.

_PLUGIN_NAMES = ('VWX-MCP', 'VW-MCP')

_MAC_ROOTS = (
    os.path.expanduser('~/Library/Application Support/Vectorworks'),
    '/Library/Application Support/Vectorworks',
)


def _scan_roots():
    """macOS plug-in dirs holding this project, newest VW version first."""
    forced = os.environ.get('VWX_VW_VERSION')
    out = []
    for root in _MAC_ROOTS:
        if forced:
            versions = [forced]
        else:
            try:
                versions = sorted((d for d in os.listdir(root)
                                   if len(d) == 4 and d.isdigit()),
                                  reverse=True)
            except Exception:
                versions = []
        for v in versions:
            for name in _PLUGIN_NAMES:
                cand = os.path.join(root, v, 'Plug-ins', name)
                if os.path.isdir(cand):
                    out.append(cand)
    return out


def find_plugin_dir(marker='mac_executor.py'):
    """Resolve the plug-in directory from anywhere, including <string> scripts."""
    env = os.environ.get('VWX_PLUGIN_DIR')
    if env and os.path.isdir(env):
        return env
    if vs is not None:
        try:
            found = vs.FindFileInPluginFolder(marker)
            # VW returns (BOOLEAN, path) for functions with an output param;
            # tolerate a bare path too rather than assuming one shape.
            path = None
            if isinstance(found, (tuple, list)):
                if len(found) >= 2 and found[0]:
                    path = found[1]
            elif isinstance(found, str) and found:
                path = found
            if path and os.path.isfile(path):
                return os.path.dirname(path)
        except Exception:
            pass
    hits = _scan_roots()
    return hits[0] if hits else None


try:
    _DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:                      # exec'd as <string>
    _DIR = find_plugin_dir()
if _DIR is None:
    _DIR = ''
if _DIR and _DIR not in sys.path:
    sys.path.insert(0, _DIR)

_IPC = os.path.join(_DIR, 'ipc')
_JOBS = os.path.join(_IPC, 'jobs')
_RESULTS = os.path.join(_IPC, 'results')
_STAMP = os.path.join(_IPC, 'pump.stamp')
_ALIVE = os.path.join(_IPC, 'native.alive')
_CONFIG = os.path.join(_IPC, 'mac_executor.json')
_LOG = os.path.join(_DIR, 'bridge.log')

RESULT_TTL = 3600.0
SWEEP_EVERY = 60.0

# Marionette executions can tear down this Python context on frame return:
# their ack is written BEFORE dispatch, exactly as vwx_pump does it.
_FIRE_AND_FORGET = frozenset({'marionette_recalc'})


# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------
_DEFAULTS = {
    # 0 = drain once and return.  This is the PROVEN Windows model and the
    # default on purpose.  > 0 enables the EXPERIMENTAL hold-open window --
    # read the warning on pump_window() before turning it on.
    'window_seconds': 0.0,
    'window_idle_exit': 3.0,       # end the window after this long with no jobs
    'window_poll': 0.05,           # seconds between queue checks in a window
    'progress_dialog': True,       # window mode: show a cancellable progress UI
    'heartbeat': True,             # write ipc/native.alive (server fail-fast)
    'toast': True,                 # vs.Message() summary after a drain
    'max_passes': 64,              # backstop against an unclaimable job
}


def _config():
    cfg = dict(_DEFAULTS)
    try:
        with io.open(_CONFIG, 'r', encoding='utf-8') as fh:
            user = json.load(fh)
        if isinstance(user, dict):
            for k, v in user.items():
                if k in cfg:
                    cfg[k] = v
    except Exception:
        pass
    return cfg


# --------------------------------------------------------------------------
# Plumbing
# --------------------------------------------------------------------------
def _log(msg):
    try:
        with io.open(_LOG, 'a', encoding='utf-8') as fh:
            fh.write(u"[%s] mac_executor: %s\n"
                     % (time.strftime('%H:%M:%S'), msg))
    except Exception:
        pass


def _write_json(path, obj):
    tmp = path + '.tmp'
    with io.open(tmp, 'w', encoding='utf-8') as fh:
        fh.write(json.dumps(obj, ensure_ascii=False))
    os.replace(tmp, path)              # atomic: no reader sees a partial file


_dirs_ready = False
_last_sweep = 0.0


def _ensure_dirs():
    global _dirs_ready
    if _dirs_ready:
        return
    for d in (_JOBS, _RESULTS):
        try:
            os.makedirs(d, exist_ok=True)
        except Exception:
            pass
    _dirs_ready = True


def _heartbeat():
    """Write ipc/native.alive so the MCP server's fail-fast sees a live bridge.

    On Windows the native palette rewrites this every 100ms and the server
    discards a job whose heartbeat is older than VWX_ALIVE_MAX_AGE (8s).  Here
    it is only refreshed when a human presses the hotkey, so the macOS setup
    MUST raise VWX_ALIVE_MAX_AGE (see domain/docs/MACOS-EXECUTOR.md) or every
    job is discarded 20s after submission, before anyone can press the key.
    """
    try:
        with io.open(_ALIVE, 'w', encoding='utf-8') as fh:
            fh.write(u"%f 0" % time.time())
    except Exception:
        pass


def _housekeep():
    global _last_sweep
    _ensure_dirs()
    try:
        with io.open(_STAMP, 'w', encoding='utf-8') as fh:
            fh.write(u"%f" % time.time())
    except Exception:
        pass
    now = time.time()
    if now - _last_sweep < SWEEP_EVERY:
        return
    _last_sweep = now
    try:
        for fn in os.listdir(_RESULTS):
            p = os.path.join(_RESULTS, fn)
            if now - os.path.getmtime(p) > RESULT_TTL:
                os.remove(p)
    except Exception:
        pass


def _list_jobs():
    try:
        return sorted(fn for fn in os.listdir(_JOBS) if fn.endswith('.json'))
    except Exception:
        return []


def _get_commands():
    """Import commands.py once; reload only when it changed on disk."""
    import importlib
    import commands
    try:
        mt = os.path.getmtime(os.path.join(_DIR, 'commands.py'))
    except Exception:
        mt = 0.0
    if getattr(commands, '_vwx_loaded_mtime', None) != mt:
        importlib.reload(commands)
        commands._vwx_loaded_mtime = mt
    return commands


def _dispatch(cmd, params):
    try:
        commands = _get_commands()
        fn = getattr(commands, cmd, None)
        if fn is None:
            return {'error': 'Unknown command: %s' % cmd}
        return fn(params)
    except Exception as e:
        return {'error': str(e), 'traceback': traceback.format_exc()}


def _claim_and_run(fn):
    """Atomically claim one job file and execute it.  Returns True if it ran.

    The claim is a rename; the claimed file is then removed BEFORE dispatch so
    that a hard crash loses the job (the caller sees a visible timeout) rather
    than replaying a mutation on the next drain.  Same contract as vwx_pump.
    """
    src = os.path.join(_JOBS, fn)
    work = src + '.working'
    try:
        os.replace(src, work)
    except Exception:
        return False                   # someone else got it
    try:
        with io.open(work, 'r', encoding='utf-8') as fh:
            msg = json.load(fh)
    except Exception as e:
        _log("bad job %s: %s" % (fn, e))
        try:
            os.remove(work)
        except Exception:
            pass
        return False
    try:
        os.remove(work)
    except Exception:
        pass
    cid = str(msg.get('_cid', fn))
    cmd = msg.get('type', '')
    params = msg.get('params', {}) or {}
    rpath = os.path.join(_RESULTS, cid + '.json')
    if cmd in _FIRE_AND_FORGET and not params.get('_sync'):
        _write_json(rpath, {'status': 'triggered',
                            'note': 'Marionette execution - ack before dispatch.'})
        _log("fire-and-forget cid=%s cmd=%s" % (cid, cmd))
        _dispatch(cmd, params)
        return True
    t0 = time.time()
    result = _dispatch(cmd, params)
    try:
        _write_json(rpath, result)
    except Exception as e:
        _write_json(rpath, {'error': 'result not serializable: %s' % e})
    _log("cid=%s cmd=%s ms=%d %s"
         % (cid, cmd, (time.time() - t0) * 1000,
            'ERR' if isinstance(result, dict) and result.get('error') else 'ok'))
    return True


# --------------------------------------------------------------------------
# Entry points
# --------------------------------------------------------------------------
def pump_all(quiet=False):
    """Drain EVERY queued job, then return.

    Call ONLY from VW's Python menu-command runner (a real hotkey press or
    menu click).  That is the single verified context on both platforms where
    document mutation is safe AND the parametric engine runs.
    """
    _housekeep()
    cfg = _config()
    done = 0
    for _pass in range(int(cfg['max_passes'])):
        jobs = _list_jobs()
        if not jobs:
            break
        ran = 0
        for fn in jobs:
            if _claim_and_run(fn):
                ran += 1
        done += ran
        if ran == 0:                   # nothing claimable: stop, do not spin
            break
    if done and not quiet:
        _log("pump_all: %d job(s)" % done)
    return done


def pump_window(seconds=None, idle_exit=None):
    """EXPERIMENTAL -- hold the safe dispatch context open and keep draining.

    Motivation: one hotkey press per MCP round-trip is correct but tedious.
    A bounded window lets a single press service a whole conversation.

    THE RISK, stated plainly: this is UNVERIFIED.  The whole bug is that a
    context which hands the event loop to a dialog loses the parametric
    engine.  A progress dialog plus ProgressDlgYield also pumps the event
    loop.  The difference -- and the reason this is worth trying -- is that
    here the script runs on the menu command's own dispatch stack with its
    document/undo context intact, and the progress dialog is passive UI rather
    than the owner of the script's execution.  That reasoning may be wrong.

    Do not enable this until you have run self_test_in_window() and seen a
    NON-ZERO bbox.  If it returns zero bboxes, window mode reproduces the
    original bug: set window_seconds back to 0 and stay on pump_all().

    Set progress_dialog=false in ipc/mac_executor.json to run the window with
    no dialog at all (VW will look frozen for the duration; that removes the
    event-loop question entirely at the cost of a beachball).
    """
    cfg = _config()
    budget = float(cfg['window_seconds'] if seconds is None else seconds)
    idle = float(cfg['window_idle_exit'] if idle_exit is None else idle_exit)
    poll = max(0.01, float(cfg['window_poll']))
    if budget <= 0:
        return 0
    steps = max(1, int(budget / poll))
    use_dlg = bool(cfg['progress_dialog']) and vs is not None
    if use_dlg:
        try:
            vs.ProgressDlgOpen('VWX pump - drain window', True)
            vs.ProgressDlgSetTopMsg('Draining VWX job queue')
            vs.ProgressDlgStart(100.0, steps)
        except Exception as e:
            _log("progress dialog unavailable (%s) - running silent" % e)
            use_dlg = False
    total = 0
    last_job = time.time()
    _log("window open: %.1fs budget, %.1fs idle exit" % (budget, idle))
    try:
        for _i in range(steps):
            n = pump_all(quiet=True)
            if n:
                total += n
                last_job = time.time()
            elif time.time() - last_job > idle:
                break
            if cfg['heartbeat']:
                _heartbeat()
            time.sleep(poll)
            if use_dlg:
                try:
                    vs.ProgressDlgYield(1)
                    if vs.ProgressDlgHasCancel():
                        _log("window cancelled by user")
                        break
                except Exception:
                    use_dlg = False
    finally:
        if use_dlg:
            try:
                vs.ProgressDlgEnd()
            except Exception:
                pass
            try:
                vs.ProgressDlgClose()
            except Exception:
                pass
    _log("window closed: %d job(s)" % total)
    return total


def run():
    """The menu command's entry point: drain, heartbeat, report."""
    cfg = _config()
    if not _DIR:
        if vs is not None:
            vs.AlrtDialog('VWX: plug-in directory not found. Set VWX_PLUGIN_DIR '
                          'or install under ~/Library/Application Support/'
                          'Vectorworks/<year>/Plug-ins/VWX-MCP/.')
        return 0
    _ensure_dirs()
    if cfg['heartbeat']:
        _heartbeat()
    n = pump_all()
    if float(cfg['window_seconds']) > 0:
        n += pump_window()
    if cfg['heartbeat']:
        _heartbeat()
    if cfg['toast'] and vs is not None:
        try:
            vs.Message('VWX pump: %d job(s) drained  [%s]'
                       % (n, time.strftime('%H:%M:%S')))
        except Exception:
            pass
    return n


# --------------------------------------------------------------------------
# Acceptance test
# --------------------------------------------------------------------------
_PROBE_PIOS = ('Angle', 'Ball Bearing', 'Base Cabinet')


def _bbox(h):
    """GetBBox as (x1, y1, x2, y2); tolerant of both return shapes."""
    raw = vs.GetBBox(h)
    if raw is None:
        return None
    flat = []
    for item in raw:
        if isinstance(item, (tuple, list)):
            flat.extend(item)
        else:
            flat.append(item)
    if len(flat) < 4:
        return None
    return [float(v) for v in flat[:4]]


def _create_pio(name, x, y):
    """CreateCustomObjectN(objectName, p, rotationAngle, showPref) -- p is a POINT.

    The flattened five-argument form is WRONG and does not raise TypeError:
    Vectorworks accepts the call, reads x into `p`, y into `rotationAngle`,
    and fails inside the plug-in with "incorrect angle format ... unexpected
    characters expected in angle".  That surfaced as a user-visible error, so
    the tuple form is the only one used here.
    """
    return vs.CreateCustomObjectN(name, (x, y), 0, False)


def _count_children(h):
    n = 0
    try:
        c = vs.FInGroup(h)
        while c is not None and n < 10000:
            n += 1
            c = vs.NextObj(c)
    except Exception:
        pass
    return n


def self_test(delete=True):
    """THE ACCEPTANCE TEST. Non-zero bbox == the parametric engine is running.

    Creates each stock probe PIO at (5, 5) on the active layer, measures its
    bounding box and child count, then deletes it.  Under the dialog bridge
    every bbox is ((0,0),(0,0)) and every child count 0.
    """
    out = {'version': VERSION, 'plugin_dir': _DIR, 'context': 'menu command',
           'probes': []}
    if vs is None:
        out['error'] = 'not running inside Vectorworks'
        return out
    for name in _PROBE_PIOS:
        rec = {'name': name}
        h = None
        try:
            h = _create_pio(name, 5.0, 5.0)
            rec['created'] = bool(h)
            if h:
                box = _bbox(h)
                rec['bbox'] = box
                if box:
                    rec['width'] = abs(box[2] - box[0])
                    rec['height'] = abs(box[3] - box[1])
                    rec['regenerated'] = (rec['width'] > 1e-9
                                          or rec['height'] > 1e-9)
                rec['children'] = _count_children(h)
        except Exception as e:
            rec['error'] = str(e)
        finally:
            if h and delete:
                try:
                    vs.DelObject(h)
                    rec['deleted'] = True
                except Exception as e:
                    rec['deleted'] = False
                    rec['delete_error'] = str(e)
        out['probes'].append(rec)
    out['parametric_engine'] = any(p.get('regenerated') for p in out['probes'])
    out['verdict'] = ('PASS - plug-in objects regenerate in this context'
                      if out['parametric_engine'] else
                      'FAIL - zero bboxes: the parametric engine is NOT running here')
    _log("self_test: %s" % out['verdict'])
    return out


def self_test_in_window():
    """Run the acceptance test INSIDE an open progress dialog + yield.

    This is the only honest way to find out whether pump_window() preserves
    the parametric engine.  PASS here means window mode is safe to enable;
    FAIL means window mode reproduces the dialog-bridge bug -- keep
    window_seconds at 0.
    """
    if vs is None:
        return {'error': 'not running inside Vectorworks'}
    opened = False
    started = False
    try:
        vs.ProgressDlgOpen('VWX self-test (window context)', True)
        opened = True
        vs.ProgressDlgStart(100.0, 4)
        started = True
        vs.ProgressDlgYield(1)
        out = self_test()
        out['context'] = 'menu command + progress dialog window'
        vs.ProgressDlgYield(1)
    except Exception as e:
        out = {'error': str(e), 'traceback': traceback.format_exc(),
               'context': 'menu command + progress dialog window'}
    finally:
        if started:
            try:
                vs.ProgressDlgEnd()
            except Exception:
                pass
        if opened:
            try:
                vs.ProgressDlgClose()
            except Exception:
                pass
    return out


def circuit_test(field='ShowEnd'):
    """Phase 2: does a REAL ConnectCAD circuit react to SetRField + ResetObject?

    Select exactly one ConnectCAD Circuit in the drawing, then run this.  It
    toggles one boolean field, resets the object, compares the bounding box,
    and then puts the field back the way it was.
    """
    out = {'version': VERSION, 'field': field}
    if vs is None:
        out['error'] = 'not running inside Vectorworks'
        return out
    h = vs.FSActLayer()
    if not h:
        out['error'] = ('nothing selected - select one ConnectCAD circuit on '
                        'the active layer and run this again')
        return out
    try:
        rec = vs.GetParametricRecord(h)
        recname = vs.GetName(rec) if rec else None
    except Exception as e:
        out['error'] = 'not a plug-in object: %s' % e
        return out
    out['record'] = recname
    if not recname:
        out['error'] = 'selected object is not a plug-in object'
        return out
    try:
        before = _bbox(h)
        out['bbox_before'] = before
        cur = vs.GetRField(h, recname, field)
        out['value_before'] = cur
        new = 'False' if str(cur).strip().lower() in ('true', '1') else 'True'
        vs.SetRField(h, recname, field, new)
        vs.ResetObject(h)
        after = _bbox(h)
        out['value_set'] = new
        out['bbox_after'] = after
        out['bbox_changed'] = (before != after)
        # restore, so the test leaves the drawing as it found it
        vs.SetRField(h, recname, field, cur)
        vs.ResetObject(h)
        out['restored'] = True
        src = getattr(vs, 'CC_GetCircuitSource', None)
        if src is not None:
            try:
                out['CC_GetCircuitSource'] = [str(v) for v in src(h)]
            except Exception as e:
                out['CC_GetCircuitSource_error'] = str(e)
    except Exception as e:
        out['error'] = str(e)
        out['traceback'] = traceback.format_exc()
    out['verdict'] = ('PASS - the circuit regenerated'
                      if out.get('bbox_changed') else
                      'INCONCLUSIVE - bbox unchanged (either the engine is not '
                      'running, or this field does not alter geometry)')
    _log("circuit_test: %s" % out.get('verdict'))
    return out


def status():
    """Diagnostics: where everything is and how deep the queue is."""
    jobs = _list_jobs()
    try:
        results = os.listdir(_RESULTS)
    except Exception:
        results = []
    alive = None
    try:
        with io.open(_ALIVE, 'r', encoding='utf-8') as fh:
            alive = fh.read().strip()
    except Exception:
        pass
    return {'version': VERSION, 'plugin_dir': _DIR, 'ipc': _IPC,
            'queued_jobs': len(jobs), 'job_files': jobs[:20],
            'pending_results': len(results), 'native_alive': alive,
            'config': _config(), 'config_file': _CONFIG,
            'inside_vw': vs is not None}


def _pretty(obj):
    return json.dumps(obj, indent=2, ensure_ascii=False, default=str)
