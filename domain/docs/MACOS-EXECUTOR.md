# The macOS executor — giving Vectorworks back its parametric engine

**Status: BUILT, NOT YET RUN. Everything below is offline work. The five-minute
verification in §7 is the first live contact.**

The blocker this removes: we can write ConnectCAD record fields from script and
they persist, but plug-in objects never regenerate, so nothing we change ever
appears in the drawing — and no ConnectCAD circuit can ever bind, because the
bind is established inside the Circuit PIO's recalculate.

---

## 1. The mechanism, in one paragraph

Stop dispatching scripts from a modal dialog's timer callback. Dispatch them
from **Vectorworks' own Python menu-command runner**, exactly as the Windows
build already does. On Windows a native C++ palette presses the hotkey for you;
that palette does not exist on macOS and every automated substitute is either
missing from VW's Python API or requires a permission this user cannot be
granted (§4). So on macOS **the human presses the hotkey** — one press drains
the whole queue. Batch aggressively (`vwx_batch`, `execute_script`) and one
press services an entire build.

| | Windows | macOS (this design) |
|---|---|---|
| TRIGGER | `VwxBridge.vlb` C++ palette posts Ctrl+Shift+B | **a human presses Cmd+Shift+B** |
| EXECUTOR | "VWX Bridge Start" Python menu command | "VWX Pump" Python menu command |
| WORK | `vwx_pump.pump_all()` → `commands.py` | `mac_executor.pump_all()` → `commands.py` |
| TRANSPORT | file IPC (`ipc/jobs` → `ipc/results`) | **same file IPC, unchanged** |

Only the trigger differs. The executor and the transport port over untouched.

---

## 2. Why the dialog bridge cannot work

`vwx-plugin/vwx_mcp_bridge.py:397` runs the whole bridge inside
`vs.RunLayoutDialog(dlg, _cb)` and dispatches every command from that modal
dialog's timer-event callback (`_cb` → `_pump`, line 349). While that dialog
owns the event loop Vectorworks does not run the parametric engine.

Direct data operations still work — that is what makes this so easy to miss.
Object creation, `SetRField`, `SetName`, `HDuplicate` all behave. Only
*regeneration* is dead. So a script reports success, the record fields read
back correctly, and the drawing shows nothing.

The generalising proof from `domain/docs/CONNECT-MECHANISM.md` §3.3, run live:

```python
for nm in ('Angle', 'Ball Bearing', 'Base Cabinet'):
    h = vs.CreateCustomObjectN(nm, 5.0, 5.0, 0, False)
    vs.GetBBox(h)        # -> ((0,0),(0,0)),  and FInGroup(h) is empty
```

Those are **stock Vectorworks plug-ins**. Nothing to do with ConnectCAD. Re-run
on a real circuit the same day: `SetRField('ShowEnd','True')` persisted,
`ResetObject` ran, the bbox did not move.

This is also not a bug to be worked around from inside that context. Forcing a
document-wide regeneration from there **crashed Vectorworks** (CONNECT-MECHANISM
§3.4). See §8 for the specific calls that must not be repeated.

`vwx-plugin/vwx_pump.py` already states the rule the crash violated, in its own
module docstring, and `docs/ARCHITECTURE.md` carries the full context map from
eight live crash tests:

| Context | read-only Python | document mutation | open dialog |
|---|---|---|---|
| CEF web-palette sync callback | ok | **CRASH** | — |
| OnIdle notification | ok | **CRASH** | **CRASH** |
| WM_TIMER + raw `ExecuteScript` | ok | parks/hangs | — |
| native menu `DoInterface` + raw `ExecuteScript` | ok | **CRASH** | — |
| **VW's Python menu-command runner** | ok | **ok** | ok |

The last row is the whole answer. We were on none of these rows: we were on a
sixth, the modal-dialog timer callback, which mutates fine and regenerates not
at all.

---

## 3. What the Windows path actually buys, and which half ports

`vwx-plugin/BridgeStart_MenuCommand.py` is a 59-line stub whose only real work
is `vwx_pump.pump_all()`. All of its value is *where it runs*: pasted as the
script of a Python menu-command plug-in, VW wraps its execution in a full
document/undo context.

`vwx_pump.py` splits the drain in two on purpose:

* `pump_readonly()` — drains only `get_/list_/count_/find_/ping` jobs. Safe in
  the C++ OnIdle notification context, so reads happen while VW is unfocused.
* `pump_all()` — drains everything. Called from the menu command and **nowhere
  else**, enforced structurally: no other code path calls it, so a misfiring
  trigger can only leave jobs queued (visible timeout), never crash VW.

**On macOS the read/write split has no purpose and is not implemented.**
`RegisterNotificationProcedure` is a C++ SDK entry point; it is absent from
`vs` (verified against `vwx-plugin/vs_index.json`: the only `Notif*` name in
3078 functions is `NotifyPullDownClicked`, and there is no `*Idle*` at all).
Without an OnIdle hook there is no second context, so everything drains in the
one safe context.

---

## 4. The macOS trigger: options, ranked

The constraint: something must invoke the menu command repeatedly **without a
modal dialog holding the event loop**.

### 4.1 Chosen — human hotkey on a Python menu command

One `Cmd+Shift+B` press runs `mac_executor.run()` → `pump_all()`, which drains
every queued job and returns. Byte-for-byte the proven Windows execution model;
the only thing removed is the robot that pressed the key.

* **Correct by construction** — it is the exact context the context map blesses.
* **Zero new risk** — no new API surface, no new execution context.
* **Cost** — one keypress per batch. Mitigated by `vwx_batch` and
  `execute_script`: a 25-device ConnectCAD build is *one* job, so *one* press.

### 4.2 Chosen, optional, EXPERIMENTAL — a bounded drain window

`pump_window()` keeps the same menu-command dispatch open for N seconds,
draining as jobs arrive, with a cancellable progress dialog so VW repaints.
One press then services a whole conversation.

**This is unverified and off by default (`window_seconds: 0`).** The honest
worry: the entire bug is a context that hands the event loop to a dialog, and
`ProgressDlgYield` also pumps the event loop. The reason it is still worth
trying is that here the script runs on the menu command's own dispatch stack
with its document/undo context intact, and the progress dialog is passive UI
rather than the owner of the script's execution. That reasoning may be wrong,
which is why `self_test_in_window()` exists: it runs the same acceptance test
*inside* an open progress window. Non-zero bbox → window mode is safe. Zero
bbox → window mode reproduces the original bug; leave `window_seconds` at 0.

### 4.3 Rejected — AppleScript keystroke via System Events

Would be the natural port of the Windows palette. It requires **Accessibility**
(TCC `kTCCServiceAccessibility`) for whatever process sends the keystroke.

**Verified on this machine, offline:**

```
$ dseditgroup -o checkmember -m Joseph.Bradley admin
no Joseph.Bradley is NOT a member of admin
$ sw_vers    ->  macOS 26.6.2 (build 25G83)
```

On current macOS, adding an app to Privacy & Security > Accessibility, or
toggling an entry already listed there, requires authenticating as an
administrator. The consent prompt itself only deep-links into System Settings;
it does not grant anything. A standard user cannot complete it. **Not
available.** Same verdict, same reason, for Automator "Watch Me Do", the
Shortcuts app, Keyboard Maestro, BetterTouchTool and Stream Deck's Hotkey
action — all of them post synthetic events and all of them need the same grant.

### 4.4 Rejected — VW OnIdle / notification queue from Python

No API. See §3. Even if there were, the context map says mutation there
**crashes**, so it could only ever have carried reads.

### 4.5 Rejected — a Python-side scheduler inside VW that is not RunLayoutDialog

The only timer in `vs` is `RegisterDialogForTimerEvents(dialogID, ms)` — it
takes a dialog id, so it requires exactly the construct that caused the bug.
There is no `SetPref`-driven timer: `SetPref` sets document/application
preferences and has no callback. Nothing else in the 3078-function index
schedules a Python callback.

### 4.6 Rejected — a self-regenerating PIO that pumps on redraw

A plug-in object's script runs inside the parametric engine by definition, so
the engine is trivially available there. But a PIO script is contractually
allowed to create only *its own* geometry; mutating other objects from a PIO
regeneration is a documented way to corrupt a document or crash VW, and the PIO
does not regenerate on its own without a document change anyway. **Do not.**

### 4.7 Not rejected, just out of scope — a native macOS palette

The correct long-term answer: port `native/` to a macOS `.vlb` (Xcode + the VW
2026 SDK), giving the same OnIdle read drain and a legal in-process trigger.
That is a C++ project, needs the SDK and a build toolchain, and per
`docs/PLUGIN_CREDENTIALS.md` also needs a credentials file per VW version.
Worth doing; not worth blocking on.

### 4.8 Worth knowing — a QMK/VIA macropad

The one keystroke source that needs **no macOS permission at all**: a
programmable keyboard or macropad that emits real USB HID events from its own
firmware. macOS cannot tell it from a human. Bind one key to Cmd+Shift+B — or a
key that auto-repeats — and the trigger is automated with no admin involvement.
Hardware, so listed as an option rather than a dependency.

---

## 5. What was built

| File | Role |
|---|---|
| `vwx-plugin/mac_executor.py` | the executor: job drain, heartbeat, config, acceptance test, diagnostics |
| `vwx-plugin/MacPump_MenuCommand.py` | paste-in body for the "VWX Pump" menu command (the hotkey) |
| `vwx-plugin/MacPumpSelfTest_MenuCommand.py` | paste-in body for "VWX Pump Self-Test" (the acceptance test) |
| `tools/install_mac_executor.sh` | copies the three files, creates `ipc/`, primes the heartbeat |

Nothing else was touched. `commands.py`, `cc_commands.py`, `sl_commands.py`,
`cc_build.py`, `vwx_pump.py` and `vwx_mcp_bridge.py` are all unmodified — a live
bridge is using them.

### 5.1 Entry points

```python
mac_executor.run()                 # what the menu command calls
mac_executor.pump_all()            # one full drain, then return  (PROVEN model)
mac_executor.pump_window()         # hold the context open        (EXPERIMENTAL)
mac_executor.self_test()           # the acceptance test
mac_executor.self_test_in_window() # the acceptance test, inside a progress window
mac_executor.circuit_test()        # phase 2: selected ConnectCAD circuit
mac_executor.status()              # paths, queue depth, config
```

### 5.2 IPC contract

Identical to `vwx_pump.py`, deliberately:

| Path (under the plug-in dir) | Writer | Meaning |
|---|---|---|
| `ipc/jobs/<ts>-<cid>.json` | MCP server | pending command (atomic tmp+replace) |
| `ipc/jobs/<...>.working` | executor | claimed (atomic rename) |
| `ipc/results/<cid>.json` | executor | result, consumed + deleted by the server, TTL 1h |
| `ipc/pump.stamp` | executor | epoch of the last drain |
| `ipc/native.alive` | executor | `<epoch> 0` — the server's fail-fast heartbeat |
| `ipc/mac_executor.json` | you | optional config, see §5.3 |
| `ipc/selftest.json` | self-test | last acceptance-test report, readable from outside VW |

A claimed job is **removed before dispatch**, so a crash loses the job (the
caller sees a visible timeout) rather than replaying a mutation. `commands.py`
hot-reloads only when its mtime changes.

`mac_executor.py` deliberately does **not** import `vwx_pump`: that module
resolves its directory from `%APPDATA%` at import time and would need six
private globals monkeypatched to work here. It is a faithful twin instead. *If
you change the IPC contract on one side, change it on the other.*

### 5.3 Config — `ipc/mac_executor.json` (all optional)

```json
{
  "window_seconds": 0,
  "window_idle_exit": 3.0,
  "window_poll": 0.05,
  "progress_dialog": true,
  "heartbeat": true,
  "toast": true,
  "max_passes": 64
}
```

`window_seconds: 0` = drain once and return (the default, and the proven
model). Raise it only after `self_test_in_window()` passes.

### 5.4 The heartbeat, and why the server env matters

`mcp-server/vwx_mcp_server.py` fails a job fast when `ipc/native.alive` is
older than `VWX_ALIVE_MAX_AGE` (default **8s**) for longer than
`VWX_ALIVE_GRACE` (**20s**) — on Windows the C++ palette rewrites that file
every 100ms. Here it is only refreshed when a human presses the hotkey, so with
the stock settings **every job would be discarded 20 seconds after submission,
before anyone could press the key.**

So the macOS setup must raise it (§6.3). The executor still writes
`native.alive` on every drain, and `install_mac_executor.sh --apply` primes the
file, so `bridge_state()` reports alive and the job simply waits in the queue
for `VWX_SOCKET_TIMEOUT` (default 880s ≈ 15 min) — which is exactly the
behaviour we want from a human trigger.

---

## 6. Install

### 6.0 Stop the dialog bridge first — mandatory

`vs.RunLayoutDialog` is **modal**. While the "VW MCP Bridge" dialog is open you
cannot reach a menu, a hotkey or the Resource Manager. Click **Stop** on it.
The two transports are mutually exclusive; nothing below works until it is
closed.

### 6.1 Copy the files

```bash
tools/install_mac_executor.sh              # dry run, shows what it would do
tools/install_mac_executor.sh --apply
```

It resolves `~/Library/Application Support/Vectorworks/<year>/Plug-ins/VWX-MCP`
(honours `VWX_PLUGIN_DIR`), copies only the three new files, never overwrites
without `--force`, and creates `ipc/jobs`, `ipc/results` and a primed
`ipc/native.alive`.

### 6.2 Create the plug-in — Plug-in Manager vs Resource Manager

Both routes run Python through VW's script runner. They differ in what they can
be bound to:

| Route | Where | Hotkey? | VW restart? | Use it for |
|---|---|---|---|---|
| **Script palette script** | Resource Manager > New Resource > **Script** | no | **no** | verifying *now* (§7) |
| **Menu command plug-in** | Tools > Plug-ins > **Plug-in Manager** > Custom Plug-ins > New… > **Command** | yes | yes | the real executor |

**In both routes you must set the language to Python.** The script editor
defaults to VectorScript, and VectorScript silently mis-compiles a Python body —
you get a compile error dialog, or worse, nothing. There is a Python/VectorScript
selector in the script-edit window; set it before pasting.

**The menu command:**

1. Tools > Plug-ins > Plug-in Manager > Custom Plug-ins > New…
2. Type **Command**, name **`VWX Pump`**.
3. Edit Script… → **language: Python** → paste
   `vwx-plugin/MacPump_MenuCommand.py` verbatim.
4. Repeat for **`VWX Pump Self-Test`** with
   `vwx-plugin/MacPumpSelfTest_MenuCommand.py`.
5. Tools > Workspaces > Edit Current Workspace… → Menus tab: drag **VWX Pump**
   onto a menu (Tools is fine) → Shortcuts tab: assign **Cmd+Shift+B**. If VW
   reports a conflict, pick anything free — nothing depends on the specific key.
6. **Restart Vectorworks.** New custom plug-ins are only picked up at launch.

The wrappers find the plug-in folder themselves (`VWX_PLUGIN_DIR` →
`vs.FindFileInPluginFolder('mac_executor.py')` → filesystem scan of the user
and workgroup roots), so nothing is hardcoded and they survive a VW version
bump.

### 6.3 Point the MCP server at the file transport

```bash
export VWX_TRANSPORT=file
export VWX_PLUGIN_DIR="$HOME/Library/Application Support/Vectorworks/2026/Plug-ins/VWX-MCP"
export VWX_ALIVE_MAX_AGE=604800   # no native palette on macOS — see 5.4
export VWX_SOCKET_TIMEOUT=880     # time for a human to press the hotkey
```

No server code change is needed: `_plugin_dir()` already honours
`VWX_PLUGIN_DIR` before falling back to the Windows `%APPDATA%` scan, and
`VWX_TRANSPORT` already selects `VwxFileTransport`. The macOS default is
`tcp` purely because there was nothing to talk to; there is now.

**Do not run the TCP dialog bridge and the file transport at the same time.**

---

## 7. Verification — five minutes, no restart

The acceptance test is self-validating: whatever context you run it in, a
non-zero bbox means the parametric engine runs *there*. Use that to check the
easy route first.

**Step 0** — In Vectorworks, click **Stop** on the "VW MCP Bridge" dialog if it
is open. Open any document (a blank one is fine).

**Step 1** — Run the installer: `tools/install_mac_executor.sh --apply`.

**Step 2** — Resource Manager > New Resource > **Script** > create a script
palette and a new script. **Set the language to Python.** Paste the whole of
`vwx-plugin/MacPumpSelfTest_MenuCommand.py`. Run it (double-click the script).

**Step 3** — Read the dialog:

```
PASS - plug-in objects regenerate in this context

Angle          bbox=[...]  children=N        <- N > 0, bbox not all zeros
Ball Bearing   bbox=[...]  children=N
Base Cabinet   bbox=[...]  children=N
```

* **Non-zero bbox → the blocker is gone.** That context runs the parametric
  engine, and the menu command uses the same runner.
* **All zeros → stop and report it.** It would mean the constraint is not the
  dialog after all, and §4 needs revisiting before anything else is built.

The full report is also written to `ipc/selftest.json`, so it can be read from
outside Vectorworks without retyping anything.

**Step 4 (phase 2, the one that matters for ConnectCAD)** — select **one**
ConnectCAD circuit in the drawing and run the script again. It reads the bbox,
toggles `ShowEnd`, calls `ResetObject`, reads the bbox again, then puts the
field back:

```
phase 2: PASS - the circuit regenerated
```

`bbox_changed: true` in `ipc/selftest.json` is the proof that
`SetRField` + `ResetObject` now reaches the recalculate — the thing that has
never happened from the dialog bridge. The report also carries
`CC_GetCircuitSource`, which is the only trustworthy oracle for a real bind.

**Step 5** — install the menu command (§6.2), restart VW, set the env (§6.3),
start the MCP server, call `ping`. It will sit in the queue; press
**Cmd+Shift+B**; the result comes back. Then a `draw_rectangle`, then a real
`cc_build` run.

**Step 6 (optional)** — only if you want window mode: change the last line of
the self-test script to `mac_executor.self_test_in_window()` and run it. Passes
→ set `window_seconds` in `ipc/mac_executor.json`. Fails → leave it at 0.

---

## 8. Hazards — do not do these

* **Never fire ConnectCAD's dialog-opening menu commands from script.**
  `Create Devices From BoM` (`CC_CreateDevicesFromWorksheet`) and
  `Make Connections from List` (`CC_MakeConnectionsFromList`) open
  `DlgSelectWorksheet` / `DlgWSColumnsAssignment`. Driving them with
  `vs.DoMenuTextByName` is the documented crash path. They stay human-clicked.
* **Never repeat the force-regeneration sequence** from CONNECT-MECHANISM §3.4:
  `ResetObject → ResetBBox → SetLayerScale(2)/(1) → HMove+Reset → SetSelect +
  DoMenuTextByName('Reset All Plug-Ins') → SetRField+Reset → ReDrawAll →
  UpdatePIOFromStyle()`. It killed Vectorworks. Prime suspects are
  `SetLayerScale` (a document-wide PIO reset) and `UpdatePIOFromStyle()`.
  Neither appears anywhere in `mac_executor.py`. Note also that `SetLayerScale`
  is **not in `vs_index.json`** at all — if it is ever needed, verify it live
  against the drift record first (`domain/docs/records/vs_index_drift.json`).
  The whole point of this work is that regeneration should now happen *by
  itself*, so nothing needs forcing.
* **Do not call `pump_all()` from anywhere but the menu command.** The safety
  property of the Windows design is structural: no other caller exists, so a
  misfiring trigger leaves jobs queued instead of crashing VW. Keep it that way.
* **Keep `mac_executor.py` ASCII and always pass `encoding='utf-8'` to
  `open()`.** VW's embedded Python runs with an ASCII locale; a bare `open()`
  on a UTF-8 file raises `UnicodeDecodeError` inside VW. This has already bitten
  this project once (`tools/START_BRIDGE_MAC.py` carries the same note).

---

## 9. What is untested

Everything. No line of this has run inside Vectorworks. Specifically:

| Claim | Confidence | How §7 settles it |
|---|---|---|
| The Python menu-command runner regenerates PIOs on macOS | high — it is the documented Windows contract and the same VW script runner | Step 3 |
| A Script Palette script is the same runner | medium — same engine, but the context map was written about menu commands | Step 3 (self-validating either way) |
| `vs.FindFileInPluginFolder` finds a file in a *subfolder* of Plug-ins | medium — falls back to a filesystem scan if not | Step 2; `status()` reports the resolved dir |
| `CreateCustomObjectN` takes the flattened 5-arg point form | high — that exact call is live-verified in CONNECT-MECHANISM §3.3; the tuple form is tried on `TypeError` | Step 3 |
| The file transport works on macOS with `VWX_PLUGIN_DIR` set | high — `_plugin_dir()` honours it before the `%APPDATA%` branch | Step 5 |
| `pump_window()` preserves the parametric engine | **unknown** | Step 6 |
| A ConnectCAD circuit binds once the engine runs | **unknown — this is the real prize** | Step 4 |

Step 4 is the one that decides whether ConnectCAD wiring becomes scriptable
end-to-end, or whether the human-gated *Make Connections from List* route
(CONNECT-MECHANISM §4) stays the only way to get genuine bindings. Regeneration
running is *necessary* for the bind; whether it is *sufficient* is the open
question.

---

## 10. Follow-ups, in order

1. Run §7. Record the result in `domain/docs/CONNECT-MECHANISM.md` §3.3 — it
   currently states the blocker as unresolved.
2. If phase 2 passes, retry every failed route in CONNECT-MECHANISM §3.2 from
   the new context. `__ISNEW`/`__RECONNECT` were never *consumed* because the
   recalculate never ran; they may consume now.
3. Fold the macOS path into `docs/ARCHITECTURE.md` §"macOS / remote", which
   still says the TCP dialog bridge is the only option, and into `README.md`.
4. Consider retiring `VWX_TRANSPORT=tcp` on macOS once this is proven. Leaving
   a transport in place that silently cannot regenerate is a trap.
5. Long-term: a native macOS palette (§4.7) restores unattended operation.
