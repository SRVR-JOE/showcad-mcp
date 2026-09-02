#!/usr/bin/env python3
"""vw_probe.py — one-shot, STRICTLY READ-ONLY interrogation of the live
Vectorworks document through the VWX-MCP bridge.

This ORCHESTRATES; it does not reimplement. The record/format census and the
PON-vs-REC namespace reconciliation already exist in vwx-plugin/cc_commands.py
(`cc_dump_records`, `cc_capabilities`) and vwx-plugin/sl_commands.py
(`sl_dump_records`). The probe invokes those and owns only the answers they do
not give:

  Q1  The COMPLETE vs.CC_* surface from dir(vs) — an inventory, not a
      fixed-name checklist, so a getter that shipped under a name nobody
      guessed still shows up. cc_capabilities supplies the verdict alongside.
  Q4  Document census: name / path / version and the layer table.

  Q2 (real record + field names) and Q3 (does the PON name match the record
  name) are delegated to cc_dump_records and sl_dump_records.

REACHING THE DOMAIN VERBS — a three-rung ladder, because vwx_pump._dispatch
resolves verbs with getattr(commands, cmd), and cc_commands/sl_commands are
neither merged into commands.py nor present in the deployed plug-in folder
(~/Library/Application Support/Vectorworks/2026/Plug-ins/VWX-MCP/, verified
2026-09-01 — it holds only commands.py, vwx_mcp_bridge.py, vwx_pump.py,
vs_index.json, START_BRIDGE_MAC.py):
  1. native bridge verb          — works once the merge lands
  2. import the module inside VW — works once the file is deployed
  3. inject the repo source text and exec it in a throwaway namespace
                                 — works right now; deploys nothing, writes
                                   nothing, and touches no global state
Rungs are tried in order and the winner is recorded in `_source`.

SAFETY — this runs against the user's real open work.
  * Read-only is ENFORCED, not asserted. Every in-VW body reaches Vectorworks
    through `V`, a read-only proxy over the real `vs` module that raises on any
    mutating call and records the attempt in `_tripwires_fired`. The domain
    modules are handed that same proxy through their `set_vs()` hook, so their
    calls are policed too. The real `vs` module is never monkeypatched: a probe
    that died mid-run must not leave the user's Vectorworks Python broken.
  * CC_* functions are ONLY inspected with dir()/hasattr()/getattr().__doc__,
    never called — CC_CircuitFromShape / CC_DeviceFromShape / CC_RouteFromShape
    / CC_RoomFromShape all CREATE objects, and CC_ReloadData mutates app state.
  * Every body's return value passes through `_clean()` before it leaves VW. A
    raw handle in a result would make the bridge's json.dumps raise inside its
    socket handler, which then sends no reply at all and hangs the client until
    timeout.
  * Each probe owns its own slot and its own try/except, and the JSON file is
    rewritten after every probe, so one failure cannot cost the other answers.

Usage:
    python3 tools/vw_probe.py [--out PATH] [--timeout SECONDS] [--quiet]

Exit codes: 0 all probes ok · 1 one or more probes errored · 2 bridge unreachable.
"""

import argparse
import datetime
import importlib.util
import json
import os
import pathlib
import socket
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent

START_BRIDGE_HINT = (
    "The VWX-MCP bridge is not listening on 127.0.0.1:9878.\n"
    "\n"
    "To start it, in Vectorworks 2026:\n"
    "    Tools > Plug-ins > Run Script...\n"
    "    choose  START_BRIDGE_MAC.py\n"
    "    and LEAVE THE DIALOG OPEN (closing it stops the bridge).\n"
    "\n"
    "Then re-run:  python3 tools/vw_probe.py"
)


def _load_call():
    """Import call() from the sibling vwx_cli.py without depending on cwd."""
    path = HERE / "vwx_cli.py"
    if not path.exists():
        print("FATAL: %s not found — vw_probe.py needs it for the bridge "
              "protocol." % path, file=sys.stderr)
        raise SystemExit(2)
    spec = importlib.util.spec_from_file_location("vwx_cli", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.call


# ── in-Vectorworks script bodies ────────────────────────────────────────────
# Each is exec'd by commands.execute_script under params {'code': ...}; the
# handler hands back {'output', 'error', 'result'} where 'result' is whatever
# the body assigns to __result__. `vs` is injected by execute_script — the
# bodies never import it.

# Prepended to EVERY body: the read-only tripwire proxy and the JSON sanitiser.
PREAMBLE = r"""
_TRIPPED = []    # mutating calls actually attempted (must stay empty)
_RESOLVED = []   # mutating names merely looked up (capability probing)

# Explicit mutators, then prefix rules. Any hit raises before Vectorworks is
# touched, so a mistake in a probe body cannot reach the user's drawing.
_BLOCK_EXACT = set([
    'SetRField', 'SetRecord', 'RemoveRecord', 'AttachRecord', 'DelObject',
    'ResetObject', 'SelectObj', 'DSelectAll', 'SetSelect', 'Layer',
    'NameClass', 'SetName', 'SetClass', 'SetParent', 'HMove', 'HRotate',
    'HScale2D', 'HDuplicate', 'Scale', 'DoMenuTextByName', 'AlrtDialog',
    'Message', 'SaveActiveDocument', 'SetLScale', 'CC_ReloadData',
    'CC_OnFindAndReplace', 'CC_CircuitFromShape', 'CC_DeviceFromShape',
    'CC_RouteFromShape', 'CC_RoomFromShape',
])
_BLOCK_PREFIX = ('Set', 'Del', 'Create', 'Insert', 'Remove', 'Move', 'Rotate',
                 'Duplicate', 'Save', 'Import', 'Export', 'DoMenu', 'Alrt',
                 'Dialog', 'Select', 'DSelect', 'Reset')


def _blocked(n):
    return n in _BLOCK_EXACT or n.startswith(_BLOCK_PREFIX)


# Read-only view of the vs module. Never patches the real module.
#
# Blocks the CALL, not the lookup. cc_capabilities has to resolve
# vs.CC_CircuitFromShape to report whether this build has it, and raising on
# that getattr would both break the answer and misreport the function as
# absent. So a blocked name still resolves -- to a stub that inspects like the
# real function (callable, same __doc__) and detonates if invoked. A name the
# real vs does NOT have still raises AttributeError, so presence reporting
# stays truthful.
class _ReadOnlyVS(object):
    __slots__ = ('_m',)

    def __init__(self, m):
        object.__setattr__(self, '_m', m)

    def __getattr__(self, n):
        real = getattr(object.__getattribute__(self, '_m'), n)
        if not _blocked(n):
            return real
        _RESOLVED.append(n)

        def _tripwire(*a, **k):
            _TRIPPED.append(n)
            raise RuntimeError('TRIPWIRE: blocked mutating call vs.%s' % n)

        _tripwire.__name__ = str(n)
        try:
            _tripwire.__doc__ = getattr(real, '__doc__', None)
        except Exception:
            pass
        return _tripwire

    def __setattr__(self, n, v):
        _TRIPPED.append('setattr:' + n)
        raise RuntimeError('TRIPWIRE: probe attempted to patch vs.%s' % n)


V = _ReadOnlyVS(vs)


def _clean(o, d=0):
    if d > 14:
        return '<max depth>'
    if o is None or isinstance(o, (bool, int, float, str)):
        return o
    if isinstance(o, dict):
        return dict((str(k), _clean(v, d + 1)) for k, v in o.items())
    if isinstance(o, (list, tuple, set)):
        return [_clean(v, d + 1) for v in o]
    return str(o)
"""

# Q1 — the full CC_* inventory. This is the probe's own answer and the fastest
# one available: cc_capabilities checks a fixed list of names, while dir(vs)
# cannot miss a getter that shipped under a name nobody guessed.
S_CC_SURFACE = PREAMBLE + r"""
WANT = ["CC_GetCircuitSource", "CC_GetCircuitDest", "CC_GetDevice",
        "CC_GetEquipmentItem", "CC_GetSignalData", "CC_GetCableTypeData",
        "CC_GetConnectorData", "CC_DeviceSockets"]
allnames = dir(vs)
cc = sorted(n for n in allnames if n.startswith("CC_"))
detail = {}
for n in cc:
    try:
        o = getattr(vs, n)           # getattr only — NEVER called
        doc = (getattr(o, "__doc__", "") or "").strip().replace("\n", " ")
        detail[n] = {"callable": bool(callable(o)), "doc": doc[:240]}
    except Exception as e:
        detail[n] = {"error": str(e)}
kw = ("circuit", "socket", "signal", "cabletype", "cable_type", "connector",
      "equipment", "adapter", "connectcad")
related = sorted(n for n in allnames
                 if not n.startswith("CC_") and any(k in n.lower() for k in kw))
__result__ = _clean({
    "vs_name_count": len(allnames),
    "cc_names": cc,
    "cc_count": len(cc),
    "expected_present": dict((w, bool(hasattr(vs, w))) for w in WANT),
    "cc_detail": detail,
    "other_names_matching_cc_keywords": related[:250],
    "_tripwires_fired": _TRIPPED,
                     "_mutators_resolved": sorted(set(_RESOLVED)),
})
"""

# Q4 — document + layer table. Neither dump verb reports layers.
S_LAYERS = PREAMBLE + r"""
out = []
h = V.FLayer()
n = 0
while h and n < 500:
    n += 1
    row = {}
    for key, fn in (("name", lambda: V.GetLName(h)),
                    ("object_count", lambda: int(V.NumObj(h) or 0)),
                    ("scale", lambda: V.GetLScale(h))):
        try:
            row[key] = fn()
        except Exception as e:
            row[key] = "<%s>" % e
    try:
        row["kind"] = "sheet" if V.GetObjectVariableInt(h, 154) == 2 else "design"
    except Exception:
        row["kind"] = None
    try:
        row["visible"] = (V.GetObjectVariableInt(h, 153) == 0)
    except Exception:
        row["visible"] = None
    out.append(row)
    try:
        h = V.NextLayer(h)
    except Exception:
        break
doc = {}
for key, fn in (("name", "GetFName"), ("path", "GetFPathName"),
                ("version", "GetVersion")):
    try:
        doc[key] = getattr(V, fn)()
    except Exception as e:
        doc[key] = "<%s>" % e
__result__ = _clean({"document": doc, "layer_count": len(out), "layers": out,
                     "_tripwires_fired": _TRIPPED,
                     "_mutators_resolved": sorted(set(_RESOLVED))})
"""

# Q2/Q3 rung 2 — import the deployed module inside VW and call it through the
# proxy. The module's own `vs` global is restored afterwards, so the probe
# leaves no trace in the VW session.
S_DOMAIN_IMPORT = PREAMBLE + r"""
import importlib, json
MODULE, VERB, PARAMS = json.loads(__PAYLOAD__)
m = importlib.import_module(MODULE)
_orig = getattr(m, "vs", None)
try:
    m.set_vs(V)
    data = getattr(m, VERB)(PARAMS)
finally:
    try:
        m.set_vs(_orig)
    except Exception:
        pass
__result__ = _clean({"_source": "vw_import",
                     "_module_file": getattr(m, "__file__", None),
                     "_tripwires_fired": _TRIPPED,
                     "_mutators_resolved": sorted(set(_RESOLVED)),
                     "data": data})
"""

# Q2/Q3 rung 3 — inject the repo's module source and exec it in a throwaway
# namespace. Touches no global state and needs nothing deployed.
S_DOMAIN_INJECT = PREAMBLE + r"""
import json
SOURCE, VERB, PARAMS = json.loads(__PAYLOAD__)
ns = {}
exec(compile(SOURCE, "<injected>", "exec"), ns)
ns["set_vs"](V)
data = ns[VERB](PARAMS)
__result__ = _clean({"_source": "injected_source",
                     "_tripwires_fired": _TRIPPED,
                     "_mutators_resolved": sorted(set(_RESOLVED)),
                     "data": data})
"""

# Domain verbs this probe delegates to, and the repo file each lives in.
# (verb, module_name, repo_relative_source, params)
DOMAIN_CALLS = (
    ("cc_capabilities", "cc_commands", "vwx-plugin/cc_commands.py", {}),
    ("cc_dump_records", "cc_commands", "vwx-plugin/cc_commands.py",
     {"samples_per_type": 2, "include_values": True}),
    ("sl_dump_records", "sl_commands", "vwx-plugin/sl_commands.py",
     {"samples_per_type": 2, "include_values": True}),
)

class Probe:
    def __init__(self, call, timeout, quiet, rung="auto"):
        self.call = call
        self.timeout = timeout
        self.quiet = quiet
        self.rung = rung
        self.results = {}
        self.failures = []
        self.out_path = None

    def log(self, msg):
        if not self.quiet:
            print(msg, flush=True)

    def flush(self):
        """Rewrite the JSON after every probe, so a probe that hangs or kills
        the bridge cannot cost us the answers already collected."""
        if not self.out_path:
            return
        tmp = str(self.out_path) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False, default=str)
        os.replace(tmp, self.out_path)

    def _raw(self, verb, params):
        try:
            return self.call(verb, params, timeout=self.timeout)
        except (ConnectionRefusedError, ConnectionError, socket.timeout, OSError) as e:
            return {"error": "bridge call failed: %s: %s" % (type(e).__name__, e)}
        except json.JSONDecodeError as e:
            return {"error": "bridge returned non-JSON: %s" % e}
        except Exception as e:                                  # never traceback
            return {"error": "%s: %s" % (type(e).__name__, e)}

    def verb(self, slot, verb, params=None, expect_error=False):
        """Run a plain bridge verb into its own slot.

        expect_error=True for lookups where "not found" IS the answer (the
        vs_signature miss on CC_GetCircuitSource is a result, not a failure)."""
        self.log("  · %-26s (%s)" % (slot, verb))
        r = self._raw(verb, params or {})
        if isinstance(r, dict) and r.get("error") and not expect_error:
            self.results[slot] = {"error": r["error"]}
            self.failures.append(slot)
        else:
            self.results[slot] = r
        self.flush()
        return self.results[slot]

    def script(self, slot, code, record=True):
        """Run one small in-VW body. Never raises.

        record=False returns the outcome without writing a slot or marking a
        failure — the ladder in domain() uses that to try a rung and move on."""
        if record:
            self.log("  · %-26s (execute_script)" % slot)
        r = self._raw("execute_script", {"code": code})
        if isinstance(r, dict) and r.get("error"):
            # transport error, or execute_script caught an exception in the body
            out = {"error": r["error"], "output": r.get("output")}
        elif isinstance(r, dict):
            out = r.get("result")
            if not isinstance(out, dict):
                out = {"result": out}
            if r.get("output"):
                out["_stdout"] = r["output"]
        else:
            out = {"error": "unexpected reply: %r" % (r,)}
        if not record:
            return out
        self.results[slot] = out
        if isinstance(out, dict) and out.get("error"):
            self.failures.append(slot)
        self.flush()
        return out

    def domain(self, slot, verb, module, src_rel, params):
        """Reach a cc_/sl_ domain verb by whichever rung works.

        1. native bridge verb        (once cc_/sl_commands are merged into
                                      commands.py — vwx_pump._dispatch resolves
                                      verbs with getattr(commands, cmd))
        2. import the module in VW   (once the file is in the plug-in folder)
        3. inject the repo source    (always works; deploys nothing)
        """
        attempts = []
        want = self.rung

        # rung 1 — native verb
        if want in ("auto", "verb"):
            self.log("  · %-26s (verb %s)" % (slot, verb))
            r = self._raw(verb, params)
        else:
            r = {"error": "skipped (--rung %s)" % want}
        if isinstance(r, dict) and not r.get("error"):
            r["_source"] = "bridge_verb"
            self.results[slot] = r
            self.flush()
            return r
        attempts.append({"rung": "bridge_verb",
                         "error": (r or {}).get("error") if isinstance(r, dict)
                                  else str(r)})

        # rung 2 — import inside VW
        if want in ("auto", "import"):
            self.log("  · %-26s (import %s in VW)" % (slot, module))
            payload = json.dumps(json.dumps([module, verb, params]))
            r = self.script(slot, S_DOMAIN_IMPORT.replace("__PAYLOAD__", payload),
                            record=False)
        else:
            r = {"error": "skipped (--rung %s)" % want}
        if isinstance(r, dict) and not r.get("error"):
            r["_attempts"] = attempts
            self.results[slot] = r
            self.flush()
            return r
        attempts.append({"rung": "vw_import",
                         "error": (r or {}).get("error") if isinstance(r, dict)
                                  else str(r)})

        # rung 3 — inject the repo source
        if want not in ("auto", "inject"):
            self.results[slot] = {"error": "all selected rungs failed",
                                  "_attempts": attempts}
            self.failures.append(slot)
            self.flush()
            return self.results[slot]
        src_path = REPO / src_rel
        self.log("  · %-26s (inject %s)" % (slot, src_rel))
        if not src_path.exists():
            attempts.append({"rung": "injected_source",
                             "error": "source not found: %s" % src_path})
            self.results[slot] = {"error": "all rungs failed",
                                  "_attempts": attempts}
            self.failures.append(slot)
            self.flush()
            return self.results[slot]
        src = src_path.read_text(encoding="utf-8")
        payload = json.dumps(json.dumps([src, verb, params]))
        r = self.script(slot, S_DOMAIN_INJECT.replace("__PAYLOAD__", payload),
                        record=False)
        if isinstance(r, dict) and not r.get("error"):
            r["_attempts"] = attempts
            r["_injected_bytes"] = len(src)
            self.results[slot] = r
        else:
            attempts.append({"rung": "injected_source",
                             "error": (r or {}).get("error")
                                      if isinstance(r, dict) else str(r)})
            self.results[slot] = {"error": "all rungs failed",
                                  "_attempts": attempts}
            self.failures.append(slot)
        self.flush()
        return self.results[slot]



def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=None, help="output JSON path")
    ap.add_argument("--timeout", type=float, default=180.0,
                    help="per-call socket timeout (bridge itself gives up at 120s)")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--rung", choices=("auto", "verb", "import", "inject"),
                    default="auto",
                    help="force one rung of the domain-verb ladder. Use "
                         "'inject' to guarantee the REPO copy of "
                         "cc_/sl_commands.py runs rather than a stale "
                         "deployed one (default: auto — try all three).")
    args = ap.parse_args(argv)

    call = _load_call()

    # ── reachability first: fail clean, never traceback ───────────────────
    try:
        pong = call("ping", {}, timeout=10.0)
    except (ConnectionRefusedError, ConnectionError, socket.timeout, OSError) as e:
        print("BRIDGE UNREACHABLE (%s)\n" % e, file=sys.stderr)
        print(START_BRIDGE_HINT, file=sys.stderr)
        return 2
    except Exception as e:
        print("BRIDGE HANDSHAKE FAILED (%s: %s)\n" % (type(e).__name__, e),
              file=sys.stderr)
        print(START_BRIDGE_HINT, file=sys.stderr)
        return 2

    ts = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    out_path = pathlib.Path(args.out) if args.out else \
        REPO / "domain" / "docs" / "records" / ("probe-%s.json" % ts)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    p = Probe(call, args.timeout, args.quiet, rung=args.rung)
    p.out_path = out_path
    p.results["_meta"] = {
        "probe_version": 1,
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
        "read_only": True,
        "ping": pong,
    }
    p.flush()

    p.log("Bridge is up. Probing (read-only)…")

    # Q4 — cheapest, and tells us which document we are looking at.
    p.verb("document_info", "get_document_info")
    p.script("layers", S_LAYERS)

    # Q1 — the probe's own answer: the complete CC_* inventory from dir(vs).
    p.script("cc_surface", S_CC_SURFACE)
    # A miss here is the expected answer (the shipped index has no CC_ getters);
    # it confirms the deployed vs_index.json matches the one in this repo.
    p.verb("vs_index_cc_getcircuitsource", "vs_signature",
           {"name": "CC_GetCircuitSource"}, expect_error=True)

    # Q2/Q3 — delegated to the domain modules, via whichever rung works.
    for verb, module, src_rel, params in DOMAIN_CALLS:
        p.domain(verb, verb, module, src_rel, params)

    _summary(p)
    print("\nJSON written to: %s" % out_path)
    if p.failures:
        print("Probes that errored: %s" % ", ".join(p.failures))
        return 1
    return 0


def _summary(p):
    r = p.results
    W = lambda s="": print(s)

    def E(x, n=240):
        return " ".join(str(x).split())[:n]

    def L(x):
        """Rows as a list, whether the verb returned a list or a dict."""
        if isinstance(x, dict):
            return list(x.values())
        if isinstance(x, (list, tuple)):
            return list(x)
        return []

    W("\n" + "=" * 72)
    W("PROBE SUMMARY")
    W("=" * 72)

    # ── Q4 ────────────────────────────────────────────────────────────────
    doc = r.get("document_info") or {}
    lay = r.get("layers") or {}
    ldoc = (lay.get("document") if isinstance(lay, dict) else None) or {}
    W("\n[Q4] Document")
    W("  name : %s" % (doc.get("name") or ldoc.get("name")))
    W("  path : %s" % (doc.get("path") or ldoc.get("path")))
    W("  vers : %s" % (doc.get("vw_version") or ldoc.get("version")))
    if isinstance(lay, dict) and lay.get("layers"):
        W("  layers (%d):" % lay.get("layer_count", 0))
        for L in lay["layers"]:
            W("    %-34s %-7s objs=%-6s vis=%s"
              % (L.get("name"), L.get("kind"), L.get("object_count"),
                 L.get("visible")))
    elif isinstance(lay, dict) and lay.get("error"):
        W("  layers: ERROR %s" % E(lay["error"], 200))

    # ── Q1 ────────────────────────────────────────────────────────────────
    cc = r.get("cc_surface")
    W("\n[Q1] vs.CC_* surface in the live module  (dir(vs) — the full inventory)")
    if isinstance(cc, dict) and "cc_names" in cc:
        W("  vs exposes %d names, %d of them CC_*:"
          % (cc.get("vs_name_count", -1), cc.get("cc_count", 0)))
        for n in cc["cc_names"]:
            W("    %s" % n)
        W("  the eight getters RESEARCH.md §2 claims shipped in 2025/2025.2:")
        for n, present in (cc.get("expected_present") or {}).items():
            W("    %-24s %s" % (n, "PRESENT" if present else "ABSENT"))
        other = cc.get("other_names_matching_cc_keywords") or []
        if other:
            W("  non-CC_ names matching circuit/socket/signal/connector/…:")
            for n in other[:30]:
                W("    %s" % n)
            if len(other) > 30:
                W("    … +%d more (see JSON)" % (len(other) - 30))
    else:
        W("  ERROR: %s" % E(cc, 300))

    caps = r.get("cc_capabilities")
    if isinstance(caps, dict):
        d = caps.get("data") or caps
        if isinstance(d, dict) and d.get("verdict"):
            W("  cc_capabilities verdict (via %s):" % caps.get("_source", "?"))
            W("    %s" % d["verdict"])
            W("    edge_mode: %s" % d.get("edge_mode"))
        elif caps.get("error"):
            W("  cc_capabilities: ERROR %s" % E(caps["error"], 200))

    # ── Q2 / Q3 ───────────────────────────────────────────────────────────
    for slot, label in (("cc_dump_records", "ConnectCAD"),
                        ("sl_dump_records", "Spotlight")):
        blob = r.get(slot)
        W("\n[Q2/Q3] %s — %s" % (label, slot))
        if not isinstance(blob, dict):
            W("  ERROR: %s" % E(blob, 300))
            continue
        if blob.get("error"):
            W("  ERROR: %s" % E(blob["error"], 300))
            for a in blob.get("_attempts") or []:
                W("    rung %-16s %s" % (a.get("rung"), E(a.get("error"), 150)))
            continue
        W("  answered via: %s" % blob.get("_source"))
        d = blob.get("data") or {}
        if not isinstance(d, dict):
            W("  unexpected payload: %s" % E(d, 200))
            continue
        W("  objects walked: %s   record formats: %s"
          % (d.get("objects_walked"), d.get("record_format_count")))
        census = L(d.get("pio_census"))
        if census:
            W("  PIO census (the PON namespace, discovered not assumed):")
            for row in census[:25]:
                W("    %-32s n=%s" % (row.get("pio_name"), row.get("count")))
        fmts = L(d.get("record_formats"))
        if fmts:
            W("  record formats (the REC namespace) — first 25:")
            for f in fmts[:25]:
                names = [x.get("name") for x in (f.get("fields") or [])]
                W("    %-32s %d fields%s"
                  % (f.get("name"), f.get("field_count", 0),
                     "  [parametric]" if f.get("parametric") else ""))
                if names:
                    W("      %s" % ", ".join(str(x) for x in names[:18]))
                    if len(names) > 18:
                        W("      … +%d more (see JSON)" % (len(names) - 18))
        wanted = d.get("connectcad_types") or d.get("spotlight_types") or {}
        if isinstance(wanted, (list, tuple)):
            wanted = dict((str(i), v) for i, v in enumerate(wanted))
        if wanted:
            W("  PON vs REC reconciliation (the TBV constants):")
            for pon, e in wanted.items():
                if not isinstance(e, dict):
                    continue
                if e.get("found"):
                    ok = e.get("rec_constant_valid")
                    W("    %-24s FOUND n=%-5s rec %r %s"
                      % (pon, e.get("count"), e.get("rec_constant"),
                         "OK" if ok else "MISMATCH -> %s"
                         % e.get("record_names_on_samples")))
                else:
                    W("    %-24s NOT FOUND  near=%s  rec_exists=%s"
                      % (pon, e.get("near_matches"), e.get("rec_constant_found")))
        for n in L(d.get("notes")):
            W("  note: %s" % E(n, 200))

    # ── read-only enforcement ─────────────────────────────────────────────
    fired = []
    for slot, blob in r.items():
        if isinstance(blob, dict):
            fired.extend((slot, t) for t in (blob.get("_tripwires_fired") or []))
    W("\n[SAFETY] mutating-call tripwires")
    if fired:
        W("  *** FIRED — a probe tried to mutate the document: ***")
        for slot, t in fired:
            W("    %s -> vs.%s" % (slot, t))
    else:
        W("  none fired — no mutating vs.* call was attempted")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        sys.exit(1)
    except SystemExit:
        raise
    except Exception as _e:
        # The probe gets one shot at a live document; an unexpected failure
        # must still say what happened and where the partial JSON landed.
        print("\nvw_probe failed unexpectedly: %s: %s" % (type(_e).__name__, _e),
              file=sys.stderr)
        print("Any probes that completed were already flushed to "
              "domain/docs/records/probe-*.json (or --out).", file=sys.stderr)
        sys.exit(1)
