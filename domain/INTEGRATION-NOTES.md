# INTEGRATION-NOTES — where `cc_*` / `sl_*` plug into vwx-mcp

Owner: Integration Agent. Audience: ConnectCAD Agent, Spotlight Agent, Bridge Agent.

This maps the seams. It contains **no domain logic** — no `cc_*`/`sl_*` handler
bodies, no record field names. Those belong to the domain agents and must come
from a live document dump (TASKS T1.1–T1.3), never from this file.

Line numbers are against the working tree on `feat/showtech-domain` at the time
of writing. They move as other agents add code; the anchors named next to each
(function names, section banners) do not.

---

## 0. The one-paragraph model

Three layers, three files, one name.

```
MCP client
  └─ mcp-server/vwx_mcp_server.py     @vtool def cc_list_devices(...) -> cmd("cc_list_devices", {...})
       └─ transport (file IPC on Win, TCP :9878 on mac)
            └─ vwx-plugin/vwx_pump.py       getattr(commands, "cc_list_devices")   [Win]
               vwx-plugin/vwx_mcp_bridge.py getattr(commands, "cc_list_devices")   [mac]
                 └─ vwx-plugin/commands.py  ← re-exports cc_commands.py / sl_commands.py
                      └─ vs.*
```

The verb name is the contract across all three layers. It is also, today, the
*only* input to the read-only decision — which is the defect fixed in §2.

---

## 1. Insertion points

### 1a. Bridge handler — `vwx-plugin/commands.py`

**Shape** (non-negotiable, this is what `getattr(commands, cmd)(params)` expects):

```python
def cc_list_devices(p):
    """One-line doc — this line is what list_commands shows an agent."""
    ...
    return {'status': 'ok', 'devices': [...]}      # or {'error': '...'}
```

Plain module-level function, single `dict` parameter conventionally named `p`,
returns a JSON-serialisable `dict`. `vwx_pump._dispatch()`
(`vwx-plugin/vwx_pump.py:167`, `getattr` at :170) and
`vwx_mcp_bridge._dispatch()` (`vwx-plugin/vwx_mcp_bridge.py:124`, `getattr` at
:128) both resolve verbs this way, and neither passes anything else.

> **This is NOT the shape in `domain/reference_handlers.py`.** That file is the
> greenfield ShowCAD design: an `@handler("name")` registry, an `args` dict, a
> `{"ok":…, "data":…}` envelope, its own `pump_all()` and its own
> `~/showcad-ipc` tree. None of that exists in this host. Mine it for the
> *algorithms* (`cc_trace_signal`'s frontier walk, `sl_patch_report`'s duplicate
> detection) and discard the plumbing. Same for `domain/tests/test_roundtrip.py`,
> which imports `vw-plugin/pump.py` and `mcp-server/server.py` — neither path
> exists here; the test needs a rewrite against `commands.py` before it can run.

**Where the code goes**: not in `commands.py`. See §3 — `cc_commands.py` and
`sl_commands.py`, re-exported from the end of `commands.py` (append after
`commands.py:4403`, currently the last line, `set_object_style`).

**Shared helpers already in `commands.py`** (do not re-implement, do not copy):

| Helper | Line | What it does |
|---|---|---|
| `_oid(h)` | 56 | handle → UUID string (`object_id` in every result) |
| `_h(oid)` | 62 | UUID string → handle |
| `_safe(fn, default)` | 71 | swallow a `vs.*` raise, return default |
| `_summary(h)` | 89 | id/type/name/class/layer/bounds for any object |
| `_collect(criteria, limit)` | 102 | `ForEachObject` into a list — collect first, mutate after |
| `vsig(name)` / `vcheck(name, argc)` | 36 / 40 | signature lookup + arity guard from `vs_index.json` |

`vcheck` **fails open** — an unknown name passes. That matters in §5.

Two verbs that will pick up new domain functions for free once they are
re-exported: `list_commands` (`commands.py:3788` — walks `globals()` with
`inspect.isfunction`, skips `_`-prefixed, so imported functions ARE listed) and
`_batch` (`commands.py:3885` — `globals().get(name)`, same story).

### 1b. Pump dispatch + read-only classification — `vwx-plugin/vwx_pump.py`

**Dispatch: no change needed.** `_dispatch` is name-generic; a re-exported
`cc_list_devices` resolves the moment `commands.py` has it as an attribute.

**Read-only classification** — this is where the recon was half right:

| Line | What |
|---|---|
| 84–87 | `_RO_NAMES` — literal fallback set |
| 88 | `_RO_PREFIXES = ('get_','list_','count_','find_')` — fallback rule |
| 103–133 | `_readonly_manifest()` — reads `ipc/readonly.json`, **written by the MCP server** |
| 136–140 | `_is_readonly(cmd)` — **manifest first**, prefixes only if the manifest is absent/unreadable |

So the pump is *not* purely prefix-based. The server exports the authoritative
set (`_export_readonly_manifest`, `vwx_mcp_server.py:632`, called from `main()`
at :2985) and the pump prefers it. **The prefix rule is the fallback, and the
server's classifier — which IS prefix-based — is what fills the manifest.** The
bug therefore lives on the server side and propagates into the manifest; fixing
it at the server fixes both.

Note the failure direction of the pump's *fallback* for our names:
`cc_list_devices` does not match `('get_','list_',…)`, so with no manifest the
pump treats it as a mutation → the job waits for genuine dispatch → it still
runs, correctly, just without the fast background path. **Slow, not unsafe.**
Do **not** teach the pump's fallback about `cc_`/`sl_` namespaces: that would
let the pump promote a verb to the crash-prone OnIdle context on its own
judgement, which is exactly the two-heuristics-that-drift problem the manifest
was built to end.

**Hot-reload of the new submodules: broken.** See §3 — `_get_commands`
(`vwx_pump.py:150`) stats only `commands.py`.

### 1c. MCP tool registration — `mcp-server/vwx_mcp_server.py`

**Insert a new section immediately before the Resources banner at line 2750**
(i.e. after `screenshot` ends, ~line 2747). That keeps the domain block after
every generic section and before the non-tool material, so the diff never
collides with the enrichment blocks other agents touch.

```python
# ═══════════════════════════════════════════════════════════════════
# Entertainment domain — ConnectCAD (cc_*) / Spotlight (sl_*)
# ═══════════════════════════════════════════════════════════════════
# Bodies live in vwx-plugin/cc_commands.py and sl_commands.py.

@vtool
def cc_list_devices(ctx: Context, layer: str = None) -> str:
    """..."""
    p = {}
    if layer: p["layer"] = layer
    return cmd("cc_list_devices", p)

@vtool(readonly=True)          # see §2 — name carries no read-only prefix
def cc_trace_signal(ctx: Context, device: str, socket: str = None) -> str:
    """..."""
    p = {"device": device}
    if socket: p["socket"] = socket
    return cmd("cc_trace_signal", p)
```

Body is always exactly `return cmd("<verb>", params)`. Nothing else.

Registration facts that bite:

- **`vtool` is defined at line 590** and derives everything from `f.__name__`:
  tag (`TOOL_TAGS.get(name)`, imported at :513), per-call timeout, MCP
  annotations, `anthropic/alwaysLoad` and `anthropic/maxResultSizeChars` meta.
- **A name missing from `TOOL_TAGS` registers with NO tag** — and
  `mcp.enable(tags=…, only=True)` can only select *tagged* tools, so an
  untagged tool vanishes under **every** preset, not just `showtech`. The nine
  T2.3/T2.4 names are already in `tool_tags.py` (§4), so the map leads and the
  code follows. Add Phase 3 names there *before* writing their `@vtool`.
- **Large results**: `sl_patch_report` and `cc_list_circuits` on a real show
  file will exceed the client's default result threshold and get spilled to a
  file reference. Add them to `_MAX_RESULT_CHARS` (`vwx_mcp_server.py:560–577`)
  — e.g. `"sl_patch_report": 250_000, "cc_list_circuits": 250_000` — the same
  way `get_objects` and `get_worksheet_data` are handled.
- **Do not** add domain verbs to `_CACHEABLE` (:2936). Fixture patch and circuit
  wiring change under the user's hands while the document is open; that list is
  strictly for things that cannot (`get_document_units`, `vs_signature`).
- **Follow-up outside my edit scope**: `set_toolset`'s docstring
  (`vwx_mcp_server.py:2862`) enumerates the presets by hand — `full | gis |
  modeling | baumkataster | minimal`. It must gain `showtech` or agents will
  never learn the preset exists. Same one-liner in `AGENTS.md:35` and
  `README.md:99`. Whoever next edits `vwx_mcp_server.py` should take it.

---

## 2. The read-only-classification fix

### The defect

`vwx_mcp_server.py:581`

```python
def _is_readonly(name):
    return name in _RO_NAMES or name.startswith(_RO_PREFIXES)   # ('get_','list_','count_','find_')
```

Every domain namespace puts the verb in the **second** segment. The rule reads
`cc` / `sl`, matches nothing, and returns False. Consequences, in order of
severity:

1. `READONLY_TOOLS` (:578) never gains the name → `ipc/readonly.json` says the
   verb is a mutation → the pump refuses the OnIdle fast path and queues it for
   genuine dispatch. A pure query now needs the accelerator hop (Windows) and
   cannot drain while Vectorworks is unfocused.
2. `readOnlyHint=False` / `idempotentHint=False` on the annotation
   (:612, :614) → a correct client asks for confirmation before a read, and
   loses the right to retry it freely.

Of the nine T2.3/T2.4 verbs, **four** are misclassified even after namespace
stripping: `cc_trace_signal`, `cc_audit_unconnected`, `sl_patch_report`,
`sl_positions`. So namespace-awareness alone does not close it.

### The asymmetry that dictates the design

Wrong in one direction costs latency. Wrong in the other **crashes
Vectorworks** — `docs/ARCHITECTURE.md`'s context map is unambiguous that a
document mutation in the OnIdle notification context is a hard crash, and the
manifest is what tells the pump a verb is safe there.

- read-only marked as mutation → slow, correct, safe.
- mutation marked as read-only → runs in OnIdle → **crash**.

Therefore **no inferred rule may produce a false positive**, which rules out
every "token appears anywhere in the name" scheme. A tempting one —
"`report`/`audit`/`trace` anywhere means read-only" — would immediately promote
`create_report_worksheet` (a mutation, 4403 lines away in `commands.py`) to the
crash path. The classifier must fail closed: silence means mutation.

### Proposal (diff-ready)

Two changes, both in `mcp-server/vwx_mcp_server.py`. Nothing in `vwx_pump.py`.

**(a) Namespace-aware name derivation** — covers the five verbs whose stem
already reads as a query, so the common case stays decorator-free.

```diff
@@ mcp-server/vwx_mcp_server.py:530
 _RO_PREFIXES = ("get_", "list_", "count_", "find_")
+
+# Domain namespaces. cc_list_devices / sl_list_fixtures put the verb in the
+# SECOND segment, so the prefix rule reads "cc"/"sl", matches nothing, and
+# stamps a pure query as a mutation. Strip one known namespace and re-test, so
+# cc_list_devices classifies exactly like list_devices. Stripping is one level
+# deep and the namespace list is closed — this widens the rule by the smallest
+# amount that makes it true, and by nothing else.
+_NAMESPACES = ("cc_", "sl_", "x_")
@@ mcp-server/vwx_mcp_server.py:581
-def _is_readonly(name):
-    return name in _RO_NAMES or name.startswith(_RO_PREFIXES)
+def _is_readonly(name):
+    if name in _RO_NAMES or name.startswith(_RO_PREFIXES):
+        return True
+    for ns in _NAMESPACES:
+        if name.startswith(ns):
+            stem = name[len(ns):]
+            return stem in _RO_NAMES or stem.startswith(_RO_PREFIXES)
+    return False
```

**(b) An explicit opt-in on the decorator** — for the four that no naming rule
can reach without becoming unsafe.

```diff
@@ mcp-server/vwx_mcp_server.py:590
-def vtool(fn=None, **kwargs):
+def vtool(fn=None, readonly=None, **kwargs):
     """@vtool + declarative tag, per-call timeout, MCP annotations and client meta.
 
     Everything here is derived from the function name at registration time, so
     adding a tool stays a one-decorator affair — no parallel table to update.
+
+    `readonly=` is the single exception, for a verb whose honest name carries no
+    read-only prefix (cc_trace_signal, sl_patch_report). It is declared ON the
+    tool rather than in a set 2000 lines away, and omitting it fails CLOSED: an
+    unannotated verb is treated as a mutation, which costs a fast path, never
+    safety. Only pass readonly=True when the handler touches NOTHING — see the
+    contract below.
     """
     def deco(f):
         name = f.__name__
@@ mcp-server/vwx_mcp_server.py:606
-        readonly = _is_readonly(name)
-        if readonly:
+        ro = _is_readonly(name) if readonly is None else bool(readonly)
+        if ro:
             READONLY_TOOLS.add(name)
@@
         kwargs.setdefault("annotations", ToolAnnotations(
-            readOnlyHint=readonly,
+            readOnlyHint=ro,
             destructiveHint=_is_destructive(name),
-            idempotentHint=readonly,
+            idempotentHint=ro,
             openWorldHint=False,
         ))
```

`@vtool` bare and `@vtool(readonly=True)` both work — the existing
`return deco(fn) if callable(fn) else deco` already handles both call forms.

Applied to T2.3/T2.4:

| Verb | Classified by | Needs `readonly=True`? |
|---|---|---|
| `cc_list_devices`, `cc_list_circuits`, `cc_get_device` | (a) stem `list_`/`get_` | no |
| `sl_list_fixtures`, `sl_get_fixture` | (a) stem `list_`/`get_` | no |
| `cc_trace_signal` | — | **yes** |
| `cc_audit_unconnected` | — | **yes** |
| `sl_patch_report` | — | **yes** |
| `sl_positions` | — | **yes** |

### Weighing it against "derived from the name, no parallel table"

The docstring's target is a *parallel table*: a second registry, far from the
code, that must be kept in sync and silently rots. Judged against that:

- **Rejected — extend `_RO_NAMES`** with the four names. This is precisely the
  parallel table the docstring warns about (and `_RO_NAMES` already has 13
  entries, so precedent exists — it is still the worst option). The declaration
  would sit at line 524 while the tool is at line 2760; a rename breaks the link
  silently and in the *unsafe* direction only if someone renames a mutation into
  the set, but in practice it rots by omission.
- **Rejected — substring/token rules.** Unsafe, per the asymmetry above.
- **Accepted — (a) + (b).** (a) is still pure name derivation, just aware that
  names have namespaces now. (b) is not a table at all: it is one keyword at the
  definition site, visible in the same three lines as the tool it describes,
  impossible to leave behind in a rename, and inert when omitted. The docstring
  stays true in spirit; I extended it to say so.

**Hard contract for `readonly=True`** (state this to the domain agents, it is
load-bearing): the handler must make *zero* document changes. No `SetRField`,
no `ResetObject`, no `SetSelect`/selection change, no active-layer or
active-class switch, no `CC_ReloadData()`, no object creation, no dialog, no
redraw. Concretely: `cc_audit_unconnected` reports the dangling sockets, it does
not select them. `sl_patch_report` reports duplicate channels, it does not
renumber them. If a verb ever needs to do either, drop the flag in the same
commit — a `readonly=True` verb that mutates will crash Vectorworks from the
OnIdle path, and the crash will look unrelated to the change that caused it.

### Two consequences worth knowing

- **The manifest also covers the generic dispatcher.** A job's `type` is the
  verb name whether it arrived via `@vtool cc_trace_signal` or via
  `vwx("cc_trace_signal", …)`, and the pump classifies by that name. So the
  moment a verb is registered `readonly=True`, even dispatcher calls to it take
  the background path.
- **Dispatcher-only verbs never reach the manifest.** `READONLY_TOOLS` is filled
  by `vtool` alone, so a domain read verb that exists in `cc_commands.py` but
  has no `@vtool` wrapper is a mutation as far as the pump is concerned. Safe,
  slow. If you want the fast path, wrap it.

---

## 3. Splitting the handlers into their own modules

### Layout

```
vwx-plugin/cc_commands.py     ConnectCAD Agent owns — nobody else edits
vwx-plugin/sl_commands.py     Spotlight Agent owns — nobody else edits
vwx-plugin/commands.py        shared; gains ONE block, at the end
```

### What actually landed (audited, not assumed)

Both modules now exist and are **self-contained**: each duplicates the small
helpers (`_safe`/`_oid`/`_h`/`_collect`) locally and exposes a `set_vs(module)`
test hook rather than reaching into `commands.py`. That is a legitimate choice —
it sidesteps the circular-import question entirely and makes the modules
testable outside Vectorworks — so keep it. The cost is helper drift; if
`_collect`'s guard rails ever change in `commands.py`, three copies must change.
Acceptable for now, worth a `vwx_common.py` extraction later.

Audit of the two files against the re-export mechanism:

| | `cc_commands.py` | `sl_commands.py` |
|---|---|---|
| `__all__` | **missing** | present |
| public functions | 8 | 6 |
| public non-function names | 33 | 5 |
| collides with `commands.py` | `traceback` | none |
| registry dict | `COMMANDS` | `SL_HANDLERS`, `SL_READONLY` |

**Action for the ConnectCAD Agent: add `__all__` to `cc_commands.py`.** Without
it, `from cc_commands import *` injects all 33 public names into `commands.py`'s
namespace. Today that is survivable — the only collision is `traceback`, and it
rebinds to the same module object — but it demonstrates the mechanism exactly:
`import *` runs last and **silently overwrites** whatever `commands.py` had
under that name. One future `import json as re` in a domain module and a verb
1500 lines away stops working, with nothing pointing at the cause. Two further
consequences without `__all__`:

- `set_vs` is a public function, so it appears in `list_commands` as a fake
  verb an agent can call.
- Both modules define `set_vs`; whichever imports last wins in `commands.py`'s
  namespace, so a test that injects a mock through `commands.set_vs` reaches
  only one of the two modules. Call `cc_commands.set_vs` / `sl_commands.set_vs`
  directly in tests.

`__all__` should list the `cc_*` verbs and nothing else. `_`-prefix every
helper that is not a verb.

**Note the convergence on read-only.** `sl_commands.py` already declares an
`SL_READONLY` set — the Spotlight Agent independently reached for the same
declarative registry §2 argues for. Mirror it as `CC_READONLY` for symmetry and
documentation value, but be clear about authority: **the bridge-side set cannot
feed the manifest.** `ipc/readonly.json` is written by the MCP server from
`READONLY_TOOLS`, which only `vtool` fills, and the server never reads the
bridge modules. `@vtool(readonly=True)` in `vwx_mcp_server.py` remains the one
authority; the bridge-side sets are documentation that must agree with it.

### The re-export block — append at the end of `commands.py` (after line 4403)

```python
# ── Entertainment domain (ConnectCAD / Spotlight) ────────────────────────────
# The verbs live in their own modules so the ConnectCAD and Spotlight agents
# never collide in this file. They are re-exported HERE because the pump and
# the TCP bridge both resolve a verb with getattr(commands, name): a function
# that is not an attribute of this module is not reachable.
#
# The reload below is not optional. importlib.reload(commands) re-runs the
# import lines, but `import cc_commands` then hits sys.modules and hands back
# the CACHED module — so without this, an edit to cc_commands.py is invisible
# no matter how many times commands.py reloads.
import importlib as _importlib
import sys as _sys

_DOMAIN_ERRORS = {}
for _mod in ('cc_commands', 'sl_commands'):
    try:
        if _mod in _sys.modules:
            _importlib.reload(_sys.modules[_mod])
        else:
            _importlib.import_module(_mod)
    except Exception as _e:
        # One broken domain module must never take the other 320 verbs down
        # with it — a bare `from cc_commands import *` on a file with a syntax
        # error makes the whole bridge answer "Unknown command" for EVERYTHING.
        _DOMAIN_ERRORS[_mod] = '%s: %s' % (type(_e).__name__, _e)

if 'cc_commands' not in _DOMAIN_ERRORS:
    from cc_commands import *       # noqa: F401,F403
if 'sl_commands' not in _DOMAIN_ERRORS:
    from sl_commands import *       # noqa: F401,F403

def domain_status(p):
    """Which domain modules loaded, and why one did not. No params."""
    return {'status': 'ok',
            'loaded': [m for m in ('cc_commands', 'sl_commands')
                       if m not in _DOMAIN_ERRORS],
            'errors': _DOMAIN_ERRORS}
```

`domain_status` matches `_RO_PREFIXES`? No — it does not, and that is fine: it
is a bridge-side diagnostic reached through `vwx`, and being classified as a
mutation costs it nothing but the fast path. (Register it `readonly=True` if it
ever gets a `@vtool`.)

### Hot-reload: it does NOT work, plainly

`_get_commands()` (`vwx-plugin/vwx_pump.py:150`) does exactly this:

```python
mt = os.path.getmtime(os.path.join(_DIR, 'commands.py'))
if getattr(commands, '_vwx_loaded_mtime', None) != mt:
    importlib.reload(commands)
```

Two independent failures for a submodule split:

1. **It stats only `commands.py`.** Editing `cc_commands.py` leaves that mtime
   untouched, so no reload happens at all. The bridge serves the old handler
   until Vectorworks restarts.
2. **Even reloading `commands.py` is not enough.** `importlib.reload(commands)`
   re-executes `from cc_commands import *`, which resolves through
   `sys.modules` and returns the cached submodule. So "touch commands.py to
   force a reload" — the obvious workaround — **does not work either**. This is
   the part that will waste someone's afternoon.

The same holds on macOS for a different reason: `vwx_mcp_bridge._dispatch`
(`vwx-plugin/vwx_mcp_bridge.py:124–127`) calls `importlib.reload(commands)` on
*every* dispatch, ungated — so `commands.py` edits are always live there, and
`cc_commands.py` edits are *never* live, because of failure (2).

**Fix — both halves are needed.** The reload loop in the re-export block above
fixes macOS and fixes Windows-once-commands.py-changes. Windows also needs the
pump to notice a submodule-only edit:

```diff
@@ vwx-plugin/vwx_pump.py:150
+# Files whose mtime can invalidate the loaded command surface. commands.py
+# re-exports the domain modules, and reloading it does NOT reload them (the
+# import hits sys.modules), so the domain modules are reloaded there — but the
+# pump still has to NOTICE they changed, or nothing reloads at all.
+_HOT_FILES = ('commands.py', 'cc_commands.py', 'sl_commands.py')
+
 def _get_commands():
     import importlib, commands
-    try:
-        mt = os.path.getmtime(os.path.join(_DIR, 'commands.py'))
-    except Exception:
-        mt = 0.0
-    if getattr(commands, '_vwx_loaded_mtime', None) != mt:
+    stamp = []
+    for _f in _HOT_FILES:
+        try:
+            stamp.append(os.path.getmtime(os.path.join(_DIR, _f)))
+        except Exception:
+            stamp.append(0.0)       # absent file: stable marker, not an error
+    stamp = tuple(stamp)
+    if getattr(commands, '_vwx_loaded_mtime', None) != stamp:
         importlib.reload(commands)
-        commands._vwx_loaded_mtime = mt
+        commands._vwx_loaded_mtime = stamp
     return commands
```

The marker changes type (float → tuple); `!=` handles that, costing exactly one
extra reload on the first call after the upgrade. A missing domain file records
`0.0` rather than raising, so the pump keeps working on a deployment that has
not shipped the domain modules yet.

Ordering note: the reload of the submodules happens *inside* `commands.py`'s
own module body, so `importlib.reload(commands)` reloads the submodules first
and then re-runs `import *` over the fresh namespace. Do not reload the
submodules from the pump instead — the pump would then have to know the module
list, which is the second place to keep it in sync.

---

## 4. `tool_tags.py` — done, in this branch

`mcp-server/tool_tags.py` now carries:

- Nine `"showtech"` entries in `TOOL_TAGS` for the T2.3/T2.4 read verbs:
  `cc_list_devices`, `cc_get_device`, `cc_list_circuits`, `cc_trace_signal`,
  `cc_audit_unconnected`, `sl_list_fixtures`, `sl_get_fixture`,
  `sl_patch_report`, `sl_positions`. Listed ahead of the code deliberately —
  an untagged tool is invisible under *every* preset, so the map must lead.
- A `"showtech"` preset:
  `{"showtech", "records", "query", "symbols", "document", "layers", "escape"}`
  → 75 of 259 mapped tools. The per-tag justification is a comment in the file
  (short version: `escape` is mandatory or the agent cannot call `set_toolset`
  back — and is doubly needed here because domain verbs are reachable only
  through `vwx` until their wrappers land; `records` because the domain *is*
  record access; `query` because enumeration is by criteria; `document` for the
  saved-doc guardrail and the VW-version handshake; `layers` because positions
  and schematic pages are layers; `symbols` because fixtures are inserted by
  symbol name. `worksheets` deliberately excluded until T4.2.)

Verified: `preset_tags('showtech')` resolves, `escape` present, every preset
still contains `escape`, `all_tags()` gains exactly one entry.

Cosmetic, not worth fixing: `set_toolset` reports its tool count from
`TOOL_TAGS` (`vwx_mcp_server.py:2876`), so it will report 75 for `showtech`
before the nine wrappers exist. It counts the map, not the registry.

---

## 5. Deployment

### The macOS path story — coherent, with three caveats

Confirmed correct: `VWX_TRANSPORT` defaults to `tcp` off Windows
(`vwx_mcp_server.py:96`); the native palette is Windows-only; the mac path is
`vwx-plugin/vwx_mcp_bridge.py`, newline-delimited JSON on 127.0.0.1:9878;
the plugin folder `~/Library/Application Support/Vectorworks/2026/Plug-ins/VWX-MCP/`
exists and its five files are **byte-identical to the repo** (verified by diff).
`START_BRIDGE_MAC.py` injects a real `__file__` before `exec`, which is what
makes the whole thing work — see caveat 1.

1. **`vwx_mcp_bridge.py` cannot find its own directory on macOS without the
   launcher.** Its fallback probe (lines 27–55) walks `%APPDATA%\Nemetschek\…`;
   `APPDATA` is unset on macOS, so `_DIR` becomes a bogus relative path,
   `sys.path` gets garbage, and `import commands` fails — every verb answers
   with an import error. `START_BRIDGE_MAC.py` is not a convenience, it is
   load-bearing. Running `vwx_mcp_bridge.py` directly from Run Script is the
   failure mode to expect from anyone who skips the README.
2. **`vwx_pump.py` is dead weight in the mac folder.** `_vw_roots()` is
   `APPDATA`-based and the file transport is Windows-only. Harmless — keep it
   deployed for parity — but the `_get_commands` fix in §3 buys macOS nothing.
   macOS is fixed by the reload loop inside `commands.py`, and only by that.
3. **There is no read-only manifest on macOS.** `_export_readonly_manifest`
   resolves its target through `_plugin_dir()` (`vwx_mcp_server.py:121`), which
   is `APPDATA`-only, so it silently no-ops. That has no safety consequence —
   the TCP bridge has no OnIdle/genuine-dispatch split and runs everything
   through the same modal timer pump — but it does mean **the read-only fix in
   §2 is unobservable on macOS except through the annotations.** Test the
   classification on Windows, or by reading `READONLY_TOOLS` directly.

Bonus: `tools/vwx_cli.py` (untracked, present in the tree) talks the bridge
protocol directly — `python3 tools/vwx_cli.py vs_signature '{"name":"..."}'`.
It needs only the bridge dialog open, no MCP server and no Claude Code restart.
That is the fastest loop for the runtime probes in §6.

### Files to copy to `~/Library/Application Support/Vectorworks/2026/Plug-ins/VWX-MCP/`

| File | New? | If stale / missing |
|---|---|---|
| `commands.py` | changed (re-export block) | **The single most likely failure.** Without the block, `getattr(commands,'cc_list_devices')` is `None` → every domain verb answers `{"error": "Unknown command: cc_list_devices"}`. Reads like the verb was never written. |
| `cc_commands.py` | **new** | Stale → verbs exist and return *wrong data*, silently, with no error anywhere. Missing while `commands.py` imports it → the try/except in §3 contains it to that namespace; **without** the try/except, `commands.py` fails to import and all 320 verbs die. That is why the guard is not optional. |
| `sl_commands.py` | **new** | same |
| `vs_index.json` | unchanged | Stale → `vs_signature` lies and `vcheck` fails open on unknown names, so agents guess arities and trip modal VW engine-error dialogs, which then block the bridge. |
| `vwx_mcp_bridge.py` | unchanged unless §3 pump-side work lands | Stale → mac-specific bridge behaviour only. |
| `START_BRIDGE_MAC.py` | unchanged | Stale/absent → see caveat 1: the bridge cannot locate its own folder. |
| `vwx_pump.py` | changed (`_HOT_FILES`) | Irrelevant on macOS (unused). On Windows, stale → submodule-only edits never hot-reload; you debug a handler that is not the one running. |

Server side (`mcp-server/`, run from the repo or `~/.local/share/vwx-mcp/`):

| File | If stale |
|---|---|
| `tool_tags.py` | `TOOL_TAGS.get("cc_list_devices")` → `None` → the tool registers **untagged** → it disappears from the catalogue as soon as *any* preset is applied (`only=True` selects by tag). Symptom: "the tool worked yesterday and now Claude can't see it." |
| `vwx_mcp_server.py` | No `@vtool` wrappers → the verbs are reachable only through `vwx('cc_list_devices', …)`. Also: without §2, every domain read is annotated as a mutation. |

Restart rules: the MCP server must be restarted for `tool_tags.py` /
`vwx_mcp_server.py` changes (tags are fixed at registration — mutating
`tool.tags` afterwards does nothing for the Visibility API). The VW side does
**not** need a restart once §3 lands; before it lands, a `cc_commands.py` edit
needs a full Vectorworks restart.

---

## 6. Two blockers the domain agents must clear before writing code

Neither is mine to fix, both stop T2.3 dead if ignored.

**(a) The `CC_*` getters that `cc_trace_signal` is built on are not in the
index.** `vwx-plugin/vs_index.json` holds **6** ConnectCAD functions, all of
them the 2022-era `*FromShape` constructors:

```
CC_CircuitFromShape(hObj)   CC_DeviceFromShape(hObj)   CC_RoomFromShape(hObj)
CC_RouteFromShape(hObj)     CC_OnFindAndReplace(hObject, fieldName, fieldValue)
CC_ReloadData()
```

`CC_GetCircuitSource`, `CC_GetCircuitDest`, `CC_GetDevice`,
`CC_GetEquipmentItem`, `CC_GetSignalData`, `CC_GetCableTypeData`,
`CC_GetConnectorData` — the 2025/2025.2 functions that `RESEARCH.md` §2 and
`domain/reference_handlers.py` both depend on — are **absent**, and so is
`CC_DeviceSockets`, which `reference_handlers.py:76` calls and which does not
exist under any name. Either the index is stale relative to the SDK stub or the
Python stub genuinely omits them. `vcheck()` fails open on unknown names, so
nothing will warn you: the call reaches `vs.` and raises
`module 'vs' has no attribute 'CC_GetCircuitSource'` at runtime.

Probe before designing around them — one call, no MCP server needed:

```
python3 tools/vwx_cli.py execute_script '{"code":"import vs\nns=[n for n in dir(vs) if n.startswith(\"CC_\")]\nprint(sorted(ns))"}'
```

If they are absent from the live `vs` module, `cc_trace_signal` has to be built
on record-field reads over the Circuit PIO instead of the handle getters, which
is a different design — decide that before writing, not after. If they are
present but merely missing from the index, rebuild it
(`python3 tools/build_vs_index.py <path-to-SDK>/vs.py`) and redeploy
`vs_index.json`; note the SDK `vs.py` stub is **not** inside
`/Applications/Vectorworks 2026`, so that needs the SDK download.

**(b) Spotlight has more API than `RESEARCH.md` credits it with.** The index
has a **Spotlight** category with **71** functions, including the officially
sanctioned Lighting Device parameter accessors:

```
LDevice_GetParamStr (handle, cellIndex, accessoryIndex, universalName) -> STRING
LDevice_GetParamLong/Real/Bool   (same four args)
LDevice_SetParamStr/Long/Real/Bool(handle, cellIndex, accessoryIndex, universalName, newValue)
LDevice_GetCellCount(handle) -> LONGINT      LDevice_GetAccCount(handle, cellIndex)
LDevice_Reset(h)   LDevice_ResetVisual(h)    IsLDSchematicViewObj(handle) -> BOOLEAN
GetLoadParent(handle) -> HANDLE              SetVisionMapping(color, universe, gobo, name, channel, fixtureid)
```

`RESEARCH.md` §3's "no `SL_*` family, use generic `vs.*`" is only half true —
there is an `LDevice_*` family, it addresses **multi-cell fixtures** (which a
flat `GetRField` on "Lighting Device" cannot), and `universalName` means the
parameter key is version-stable in a way a localised record field name is not.
`sl_get_fixture` / `sl_list_fixtures` should probably read through
`LDevice_GetParamStr` with `GetRField` as the fallback — Spotlight Agent's call,
but make it knowingly. Also present: 37 **Truss Analysis** functions
(`OLD*`/`HP_*`/hoist + load data) — unclaimed territory for a later `sl_loads`
/ Braceworks-adjacent verb set. Still hard rule: pull the exact signature from
the index before every call, never from memory.

---

## 7. Corrections to the recon I was handed

Everything else in the brief checked out. Four amendments:

1. **"Read-only detection is prefix-based … the pump would refuse to serve
   them"** — right about the outcome, wrong about the mechanism and the owner.
   The pump prefers a server-written manifest (`ipc/readonly.json`,
   `vwx_pump.py:103–140`); its own prefixes are only the fallback. The prefix
   bug is on the **server** (`vwx_mcp_server.py:581`) and *propagates into* the
   manifest. Fix it there and both layers are fixed at once — see §2. The
   pump's fallback also fails in the safe direction for `cc_`/`sl_` names
   (mutation → queued → slow but correct), so this is a latency and annotation
   defect, not a crash risk.
2. **"Verify the mtime hot-reload still behaves … it likely only stats
   commands.py"** — correct, and worse than suspected: touching `commands.py`
   is **not** a workaround, because `importlib.reload(commands)` re-runs
   `import *` against the cached submodule. Two fixes needed, not one (§3), and
   macOS needs the one that lives in `commands.py`, not the one in the pump.
3. **The mac path story is coherent but load-bearing on `START_BRIDGE_MAC.py`**
   — `vwx_mcp_bridge.py`'s own directory probe is `%APPDATA%`-only and cannot
   work on macOS. Also worth knowing: the mac bridge reloads `commands.py` on
   *every* dispatch, ungated (`vwx_mcp_bridge.py:127`) — the mtime gate is
   Windows-only — and `_export_readonly_manifest` silently no-ops on macOS, so
   §2's effect there is limited to the MCP annotations.
4. **`domain/reference_handlers.py` is not a template for this host.** Different
   handler shape (`@handler` registry, `args`, `{"ok","data"}` envelope,
   `~/showcad-ipc`), and it calls at least one function that does not exist
   (`vs.CC_DeviceSockets`) plus several that are missing from the index (§6a).
   Treat it as algorithm reference only. `domain/tests/test_roundtrip.py`
   likewise imports `vw-plugin/pump.py` and `mcp-server/server.py`, neither of
   which exists in this repo.
