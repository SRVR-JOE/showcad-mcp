# MCP prior art — who has driven Vectorworks from outside, and how

_Compiled 2026-09-02 by reading source, not READMEs. Every claim is tagged
**VERIFIED** (I read the code, the official reference page, or the commit) or
**CLAIMED** (a README/issue says so and I could not independently confirm it)._

Supersedes and extends `RESEARCH.md` §1, which was compiled from README-level
information and is missing four projects.

---

## 0. The direct answer

**Has anyone made scripted plug-in-object regeneration work on macOS
Vectorworks?**

**No. Nobody has demonstrated PIO regeneration on macOS — but that is not the
same as nobody having solved our problem, and the evidence says our problem is
probably not the one we think it is.**

Three findings, in descending order of how much they should change what we do
next.

### 0.1 Our bbox measurement is invalid per official Vectorworks documentation

This is the headline and it is not from a forum — it is from the official
`ResetObject` reference page, in the Remarks section:

> "there are some things that you cannot do, **like reset another object and
> then check its bounding box for differences. Bounding boxes only get changed
> when the geometry of an object changes, and this won't happen until the
> object has regenerated**, and if you're still within the script of another
> object, this hasn't happened yet."

And the mechanism, same page:

> "In order to improve performance of object regeneration, the VectorScript
> interpreter looks for all of the PIOs of a certain type that have been
> flagged for regeneration (**ResetObject sets this flag**), and it will
> regenerate all of them before unloading that PIO code and loading the PIO
> code for the next PIO type."

> "VectorScript doesn't do multi-tasking — it is only capable of running one
> script at a time. If one object is regenerating, and this object calls
> ResetObject on another object, the other object will not regenerate until the
> first script has fully completed."

**VERIFIED** — https://github.com/Vectorworks/developer-scripting/blob/main/Function%20Reference/Functions/ResetObject.md
(the GitHub repo is the official mirror of `developer.vectorworks.net`, which
403s direct fetches).

`ResetObject` is **flag-and-defer**, not do-it-now. It marks the object and
returns. The regeneration pass is batched by PIO type and run by the
interpreter *after the script completes*. So:

- `CreateCustomObjectN(...)` then `GetBBox(h)` **in the same script** is
  documented to be meaningless. `((0,0),(0,0))` is the expected reading for an
  object that has been created but not yet regenerated.
- `SetRField` + `ResetObject` then `GetBBox` **in the same script** is
  documented to be meaningless for the same reason. A byte-identical bbox is
  the expected reading.

`CONNECT-MECHANISM.md` §3.3 draws the conclusion "the parametric engine is
dead" from exactly these two same-script measurements. **That conclusion is not
supported by the evidence we collected.** The caveat in the mission brief — "we
have NOT yet run a control test" — turns out to be the crux, and the official
docs say the control test would have failed too.

Corroboration, community rather than official: a forum thread on
`CreateCustomObjectN` objects missing from a PDF exported in the same script
diagnoses it as "objects are not instantiated until the script run completes",
and reports that `ReDrawAll()`, `ResetObject()` and bbox resets all failed to
fix it; the only thing that helped was splitting the work across two separate
script runs. **CLAIMED** —
https://forum.vectorworks.net/index.php?/topic/112850-vscreatecustomobjectn-not-showing-in-pdf-export/

Note the honest limit of this finding: the official paragraph is framed around
being "within the script of another object", i.e. inside a PIO's own
regeneration script. Ours is a menu command, not a PIO script. The described
mechanism (a flag consumed by a batched, per-type pass driven by the
interpreter) is general, and the forum thread reports the same behaviour from a
top-level script, but I did not find an official sentence that says it in so
many words for the menu-command case. **This needs the experiment in §6.1, not
more reading.**

### 0.2 The macOS execution-context problem has been solved, by someone else, in public

Not the regeneration problem — the *trigger* problem, the one `MACOS-EXECUTOR.md`
§4.3 declared unavailable and §4.7 deferred as out of scope.

`chandz102` ported vicquick's Windows-only native palette to macOS from
scratch, against the VW 2026 Mac SDK, and reports it working end-to-end on a
live document including writes while Vectorworks is backgrounded.

- Issue: https://github.com/vicquick/vwx-mcp/issues/8 (opened 2026-07-29, still
  open, no maintainer reply)
- Branch: https://github.com/chandz102/vwx-mcp/tree/macos-native-port
- **VERIFIED** the branch and directory exist and contain real work:
  `native-macos/` holds `PORT_NOTES.md` (7,270 bytes), `Source/`,
  `VwxBridge.vwr/` and **`VwxBridge.xcodeproj/`**. This is a buildable Xcode
  project, not a sketch.
- **CLAIMED** that reads and writes both work end-to-end. I have not built it.

**The single most valuable line in the whole survey**, from `PORT_NOTES.md`:

> "macOS has no direct equivalent, so instead of simulating input at all, the
> native timer calls the SDK's own `gSDK->DoMenuName("VWX Bridge Start", 0)`
> directly. This is an in-process call into Vectorworks' own command dispatcher
> rather than a synthetic OS-level event, so — usefully — **it works regardless
> of whether Vectorworks is the focused/frontmost application.** Confirmed
> live: triggered a document write via MCP while Finder was frontmost and
> Vectorworks was fully backgrounded."

`gSDK->DoMenuName()` fires the Python menu command from inside the process.
**No Accessibility grant, no admin password, no keystroke injection, no
macropad.** That kills the blocker in `MACOS-EXECUTOR.md` §4.3 outright — the
entire "Rejected — AppleScript keystroke via System Events" analysis, and the
QMK macropad fallback in §4.8, are moot if we build a native plugin.

The cost is unchanged and real: it is a C++/Xcode project, it needs the
Vectorworks Mac SDK, and per `docs/PLUGIN_CREDENTIALS.md` a credentials file
per VW version. But it is now a *port of a working reference implementation*
rather than research.

Other hard-won details from the same notes, all **CLAIMED** but specific enough
to be worth having (they will each cost a day if rediscovered):

| Trap | Symptom |
|---|---|
| Xcode product name must equal `DefaultPluginVWRIdentifier()`'s return string | `VWFC::PluginSupport::GetStandardURL()` dereferences an uninitialised file identifier → instant `EXC_BAD_ACCESS` on palette open |
| `.vwstrings` must be **UTF-16LE with BOM**, not UTF-8 | `BuildVWR` parse error: "Found unexpected character when expecting open quote for string key" |
| Build **Release 64**, not Debug | Debug symlinks the `.vwr` folder; the symlink breaks the moment the bundle moves |
| Move the built bundle with `ditto -c -k --sequesterRsrc --keepParent` | plain `cp`/`scp` loses the ad-hoc code signature |
| `CFAbsoluteTimeGetCurrent() * 1000.0` overflows `uint32_t` | ~7.9×10¹¹ vs `UINT32_MAX` ~4.3×10⁹; UB, saturates, permanently jams the debounce so every job after the first silently never fires |

Still stubbed on macOS: auto-dismiss-error-dialogs (needs `AXUIElement` and the
Accessibility grant we cannot get). Stated failure mode is benign — a stuck job
times out client-side, nothing corrupts.

**Caveat that matters to us specifically:** this port routes mutations through
the same Python menu-command context we already tested and found
non-regenerating. It automates the keypress; it does not change the context.
If §0.1 is right the context was never the problem. If §0.1 is wrong, this port
does not fix us either.

### 0.3 If we ever do need to leave the Python context, the design is settled

`BhaveshY/vectorworks-mcp` implements the textbook answer in C++ and
live-verified it on Windows: background socket threads enqueue work into a
`CadRequestQueue`; a hidden message-only window with a 50 ms `WM_TIMER` running
on Vectorworks' main thread drains it. **VERIFIED by reading the source**
(`native_bridge/src/VectorworksMCPBridge.cpp`, `CadRequestQueue.hpp`). The API
is explicit about the contract:
`TryDequeueOnVectorworksMainContext()` → `DispatchCadRequestOnVectorworksMainContext()`
→ `CompleteFromVectorworksMainContext()`.

The macOS equivalent of that pump is a `CFRunLoopTimer` / `dispatch_async` onto
the main queue. **Nobody has written it** — see §3.4; the project's own
non-Windows branch is a stub that returns `"unavailable"`.

---

## 1. Landscape (corrected and extended)

`RESEARCH.md` §1 listed four projects. There are at least nine, and two of its
four rows need correction.

| Project | What it really is | Platform | Transport | Native plugin? | Licence | Last commit |
|---|---|---|---|---|---|---|
| **[chandz102/vwx-mcp @ macos-native-port](https://github.com/chandz102/vwx-mcp/tree/macos-native-port)** | **The macOS native palette port. Most important repo in this table.** | **macOS** | file-IPC | yes (Xcode) | MIT (inherited) | 2026-07-29 |
| [BhaveshY/vectorworks-mcp](https://github.com/BhaveshY/vectorworks-mcp) | Best-engineered. Main-thread request queue, transactions, self-verifying writes | Windows | TCP 127.0.0.1:9877 | yes (required) | **none** | 2026-08-31 |
| [vicquick/vwx-mcp](https://github.com/vicquick/vwx-mcp) | Our upstream. 248 tools, verified context map | Windows | file-IPC (`tcp` fallback) | yes | MIT | 2026-08-25 |
| [upipibi/claude-vectorworks-mcp](https://github.com/upipibi/claude-vectorworks-mcp) | The only *built* macOS plugin. Background-threaded, unsafe by its own admission | **macOS/ARM** | Unix socket | yes | MIT + VW SDK EULA | 2026-07-04 |
| [mako-357/vectorworks-mcp](https://github.com/mako-357/vectorworks-mcp) = [chronista-club/…](https://github.com/chronista-club/vectorworks-mcp) | Same repo, same SHA `c4b8c48`. **Not buildable.** | claims both | Unix socket | yes (no build files) | MIT | 2026-04-15 |
| [randneto-lab/vwx-mpc-server-plugin](https://github.com/randneto-lab/vwx-mpc-server-plugin) | Repackaging of vicquick's Python half, no native plugin | Windows | file-IPC | no | **none** | 2026-07-12 |
| [edmacovaz/rt-vectorworks-mcp](https://github.com/edmacovaz/rt-vectorworks-mcp) | Read-only PoC on the modal dialog bridge | **macOS** | socket in dialog timer | no | none stated | 2026-07-08 |
| [Gribiche64/vectorworks-bridge](https://github.com/Gribiche64/vectorworks-bridge) | **Spotlight fixtures via Lightwright XML. Our domain.** No live session at all | any | file watch | no | MIT | 2026-06-10 |
| [togawamanabu/vectorworks-mcp](https://github.com/togawamanabu/vectorworks-mcp) | Docs RAG server. Does not touch a document | n/a | WebSocket | no | none stated | 2025-09-26 |

**No first-party MCP or automation API exists.** VW 2026's AI features are
UI-assist only (command search, auto-dimension, AI Visualizer rendering). The
forum request
https://forum.vectorworks.net/topic/134256-official-model-context-protocol/
(opened 2026-07-28) still has **zero Nemetschek staff response**. There is no
VW 2027 announcement indexed as of 2026-09-02.

Corrections to `RESEARCH.md` §1:
- mako-357 and chronista-club are **one repo**, not two, and it is not usable.
- vicquick is listed as "VW 2026, background writes" — true, but its macOS
  story is *the modal dialog bridge*, i.e. the thing we already proved dead.
- `RESEARCH.md` §3 says "No `SL_*` family". There is one, it is just small:
  `SL_UpdateSAcc`, `SL_UpdateUID`. More usefully there is
  **`LDevice_Reset(h)`** and **`LDevice_ResetVisual(h)`** — see §5.3.

---

## 2. The execution-context map, reconciled

Three projects published context findings that appear to contradict each other.
They do not, once you separate **what code is being run** from **where it runs
from**. This reconciliation is the most useful thing in this document after
§0.1.

| Context | Read | Mutate | Source |
|---|---|---|---|
| CEF web-palette sync callback | OK | **CRASH** | vicquick, live-tested |
| OnIdle notification (`RegisterNotificationProcedure`) | OK | **CRASH** (opening a dialog crashes) | vicquick, live-tested |
| Native code calling `IPythonScriptEngine::ExecuteScript` | OK | **CRASH — twice, live** | vicquick, live-tested |
| **VW's own Python menu-command runner** (script plugin) | OK | **works** | vicquick, live-tested |
| **Native `gSDK->*` calls from a main-thread timer/queue** | OK | **works** | BhaveshY, live-verified `main_context_pump_ready=true` |
| Native `gSDK->*` calls from a background `std::thread` | "works" | **corrupts / crashes** | upipibi's own README |
| `vs.RunLayoutDialog` timer callback | OK | ? | our bridge; edmacovaz uses it read-only |

The apparent vicquick↔BhaveshY contradiction resolves cleanly. vicquick's
comment is precise about what crashed — **VERIFIED** by reading
`native/Source/Bridge/VwxBridgePalette.cpp:265`:

> "Read-only drain — safe in the OnIdle notification context. There is NO
> native full-drain: mutations run exclusively in the 'VWX Bridge Start' Python
> menu command (**VW's own script-plugin runner wraps them correctly; the raw
> engine call from native code does not — crashed live, twice**)."

So the thing that crashes is **invoking the Python engine from native code**,
not **mutating from the main thread**. BhaveshY never touches Python; it calls
`gSDK->` directly from a main-thread pump and it works. The operative rules
are therefore:

1. **Never call the SDK from a background thread.** upipibi does exactly this
   and says so in its own limitations: *"SDK calls run on the socket's
   background thread; the Vectorworks SDK is not guaranteed thread-safe for
   document access, so writes and scripts can crash or silently corrupt the
   open document... A proper fix (marshalling SDK calls onto Vectorworks' main
   thread) **is not yet implemented**."* (**VERIFIED**, `README.md:153-157`;
   the code confirms it — `SocketBridge.h:22` "NOTE: it is invoked on the
   socket's background thread", and `SocketBridge.cpp:177` calls `m_handler`
   inline on that thread with no marshalling.)
2. **Never invoke the Python engine from native code.** Use `DoMenuName` to
   make *Vectorworks* run the Python menu command in its own runner.
3. **Direct `gSDK->` calls are fine from a main-thread timer**, which is what
   BhaveshY does.

---

## 3. Project-by-project

### 3.1 chandz102/vwx-mcp `macos-native-port` — the one that matters

Covered in §0.2. Not merged, not acknowledged by the upstream maintainer,
single contributor, one month old. It is a fork branch, so it could disappear;
**mirror it now if we intend to use it.**

### 3.2 vicquick/vwx-mcp — our upstream

MIT, 12★, most actively maintained. Windows architecture, **VERIFIED** by
reading `VwxBridgePalette.cpp`: a native palette runs a 20–150 ms adaptive
`SetTimer` heartbeat; when jobs are queued it fires (A) `NotifyLayerChange`
with a magic value to get a read-only drain from OnIdle, and (B) a
`Ctrl+Shift+B` keystroke — `keybd_event` in the foreground, or
`SetKeyboardState` + `PostMessage(WM_KEYDOWN)` into VW's queue when
backgrounded — to reach the `VWX Bridge Start` accelerator, whose `DoInterface`
runs `vwx_pump.pump_all()`. Mutations run only there, structurally enforced.

Why it works on Windows and does not port: every part of the trigger is Win32
(`keybd_event`, `PostMessage`, `TranslateAccelerator`, `EnumWindows`). Their
own `docs/ARCHITECTURE.md` says so — *"The native palette + posted-key trigger
are Windows-only"* — and directs macOS users to `VWX_TRANSPORT=tcp` and the
modal dialog bridge. A "macOS trigger daemon (AppleScript `System Events`
keystroke)" is a roadmap item. chandz102's `DoMenuName` approach is
**strictly better** than that roadmap item and should replace it in our plans.

On regeneration, upstream is more useful than it looks:
- `_apply_pio_params()` and `set_pio_parameter()` do `SetRField` + `ResetObject`
  and **never verify the result**. Their sweep (`TOOL_COVERAGE.md`: 164 ok / 56
  handled-error) counts a call as "ok" if it returns without error. **There is
  no evidence anywhere in that repo that a PIO was verified to have
  regenerated.** Do not read their green sweep as proof PIO regen works on
  Windows.
- `commands.py:3949` documents, for Marionette: *"Re-execution trigger:
  `vs.ResetObject`/`HMove`/`HScale2D` **do NOTHING** for Marionette.
  `vs.Scale(1.0,1.0)` with ONLY the wrapper selected re-executes the network
  (forum-confirmed)."* So upstream, on Windows, in the blessed menu-command
  context, has independently hit "ResetObject does nothing" for a PIO class and
  needed a **selection-based** workaround. See §6.2.

### 3.3 BhaveshY/vectorworks-mcp — best engineering, no licence

Windows-only (the only string `macos` in the repo is in `.gitignore`).
**VERIFIED**: the main-context pump is wrapped in
`#if VECTORWORKS_MCP_HAS_SDK && defined(_WINDOWS)`; the `#else` branch is a
stub where `StartMainContextPump()` returns `false` and `MainContextPumpName()`
returns `"unavailable"`. Since `CadApiSafe()` is
`kCadHandlersImplemented && MainContextPumpReady()`, **on macOS this bridge
would report `cad_api_safe=false` and refuse every document-touching tool by
design.** It is not a macOS option; it is a design to copy.

Its honesty is its main value. `SMOKE_REPORT_2026-08-18.md` verdict: *"not
release-ready and not capability-complete"*. Ordinary geometry, atomic commits
and file exports worked. **Space, Slab and Roof each failed live** and left
source-profile geometry behind; Door and Window could not be discovered through
the parametric-schema path. In other words: even the best-engineered project,
with a verified main-thread pump, **has not demonstrated working parametric
object creation.** Note also that its verification after `ResetObject` is a
*parameter readback* (`GetParamReal` within tolerance), never a geometry or
bbox check — consistent with §0.1's warning that a same-script bbox check is
not a valid test.

No `LICENSE` file. Treat as all-rights-reserved; read it for ideas, do not
vendor it.

### 3.4 upipibi/claude-vectorworks-mcp — the honest macOS failure

Derived from mako-357, MIT + VW SDK EULA, macOS/Apple Silicon/VW 2026. The
plugin is real and built (`plugin/BUILD.md`, ad-hoc signing notes about
`SIGKILL` on stale signatures). But it is the mako design with the same defect
and, to its credit, says so — see §2 rule 1. It exposes `run_script` for both
VectorScript and Python via `IVectorScriptEngine`/`IPythonScriptEngine`
`ExecuteScript` **called from the socket worker thread**, which is precisely
the call vicquick reports crashed VW twice.

**Do not run this against a real ShowCAD document.** Its own README says "work
on a throwaway copy".

### 3.5 mako-357 / chronista-club — vapourware

**VERIFIED unbuildable.** 12 files, one commit (2026-04-15), no `.xcodeproj`,
no `CMakeLists.txt`, no `.vcxproj`, no `StdAfx.h` (which every source file
`#include`s), no SDK vendoring, no release binary. The handler is invoked on
`m_serverThread` with no marshalling (`SocketBridge.cpp:177`). The `run_script`
Python branch is dead placeholder code that calls
`gSDK->RunTempTool(nullptr, nullptr)`, ignores the result, and returns
`success: false` with "Python execution via SDK is limited."

It creates only lines, rectangles and ovals — **primitives, which need no
regeneration**. It never calls `ResetObject` or `CreateCustomObject`. It has
never encountered our problem. Its "world's first Vectorworks MCP" claim and
its PulseMCP/LobeHub listings are the most visible thing in this space and the
least substantial. `RESEARCH.md` §1 describing it as a working macOS route was
the single biggest error in our prior research.

### 3.6 randneto-lab — repackaging

Windows, VW 2026, no native plugin at all: a hand-registered Python menu
command plus file-IPC, i.e. vicquick's Python half with the automation removed.
Its Python files **differ** substantially from vicquick's (548 diff lines in
`vwx_pump.py`), so it is a fork, not a copy. No licence file. Its
"Known modeling limits" are real but generic: `vs.JoinWalls` does not reproduce
the manual Wall Join Tool for T-joins; *"Real wall-hosted doors/windows require
resources or PIOs configured for wall insertion"*; prefer `CreateSlab` over
extrusions. Nothing about regeneration.

### 3.7 edmacovaz/rt-vectorworks-mcp — macOS, and read-only for a reason

A proof of concept for one architecture firm, macOS + VW 2026. **VERIFIED** it
uses exactly our failed approach #1: `DISPATCH_MODE = "dialog"`,
`TIMER_MS = 50`, `RunLayoutDialog` + `RegisterDialogForTimerEvents`, with
`SetupDialogC = 12255`. Its entire dispatch surface is `read_classes`. Nobody
who has built the dialog-timer bridge on macOS has shipped a write through it.

### 3.8 Gribiche64/vectorworks-bridge — our domain, and a warning

The only project in the entertainment domain, and it sidesteps the execution
problem entirely: it watches the **Lightwright Data Exchange XML** that
Spotlight writes automatically on focus-loss (Spotlight Preferences →
Lightwright → "Use automatic Lightwright Data Exchange"), parses it, and writes
patches back for VW's watcher to import. MCP tools `get_fixture_counts`,
`write_fixture_patch`, `plot_qc`. Vectorworks does not even need to be running
to read. MIT.

**Read `VW_SELECTABILITY_BUG_BRIEF.md` before considering this route.** On a
live Céline Dion residency file it wrote a patch whose target `Symbol_Name`s
were not in the document's resource library. VW imported it, applied the data
fields, could not resolve the symbols, and left 254 fixtures across three
layers with dangling symbol-instance pointers — fixtures that were no longer
selectable. VW autosaved the damage. Cmd-Z reverted the data fields but could
not restore the binary symbol references. Their verdict: *"DAMAGE IS
IRREVERSIBLE via the MCP. Restore from May 13 backup required."* — a 1 GB
file, five days of work lost.

Their shipped mitigation (commit `e0e0f46`) is worth stealing wholesale: the
writer **hard-refuses any patch whose target `Symbol_Name` is not already in
use by an existing fixture**. That is the same class of guard as our "looks
wired, is not" rule in `CONNECT-MECHANISM.md` §3.1, and it is the reason to
keep that rule.

---

## 4. Is `ResetObject` even the right call?

Yes, it is the documented one — but see §0.1 for what it actually does.
Checked against the official function reference and our 3,077-signature index.

| Call | Exists | What the official page says |
|---|---|---|
| `ResetObject(h)` | yes | "Update the specified object using the current settings and parameter values. **This will reset the bounding box of the object.** If the object is in a wall, then the wall is reset also." Sets a flag; regeneration is batched and deferred. |
| `ResetBBox(h)` | yes | Recomputes the bbox "**based on the objects' current geometry**" — it measures existing geometry, it does not generate any. Useless if there is no geometry yet. Remark: "This doesn't seem to work on symdefs." |
| `UpdatePIOFromStyle()` | yes | Zero-arg. Re-syncs a PIO to its **style resource** only. Irrelevant to an unstyled object. One of the two prime suspects for the §3.4 crash in `CONNECT-MECHANISM.md`. |
| `ReDraw` / `ReDrawAll` | yes | **Screen** redraw only, not regeneration. The `ReDraw` page's Remarks explicitly say a PIO "will not regen, even if you use redraw or redrawall" and suggest `HMove(h,0,0)` instead. |
| `HMove(h, 0, 0)` | yes | A plain zero-distance relative move. Community-standard way to fire a PIO's "Reset on Move" event. See §6.2. |
| `ResetAllPIOs` | **no** | Does not exist as a script function. "Reset All Plug-ins" is a menu command only (`DoMenuTextByName`). |
| `SetParametricRecalculate` | **no** | Does not exist. |
| `PIOToGroup` | **no** | Does not exist. |
| `SetObjectVariableBoolean` | yes | Generic property setter keyed by Appendix G selectors. **Nothing documented ties any selector to a PIO dirty/regen flag.** No evidence for the "mark it dirty" theory. |

Per-object-type resets that **do** exist and that we have not tried:

| Call | Category | Doc |
|---|---|---|
| **`LDevice_Reset(h)`** | Spotlight | "Reset the specified lighting device object." |
| **`LDevice_ResetVisual(h)`** | Spotlight | "Cleans up the visual/drawing cache for the specified lighting device object." |
| `Space_FullyReset(space)` | SpaceObjectCoreTools | "Allow a full res[e]t of the Space obj, including Boundary" |
| `DT_ResetAllDataTags()` | Data Tag | Resets all Data Tags in the document |

The existence of `Space_FullyReset` and `LDevice_Reset` is itself informative:
Vectorworks ships per-PIO reset entry points **because generic `ResetObject` is
not always sufficient**. There is no ConnectCAD equivalent — the circuit/device
surface offers only `CC_ReloadData()` (reloads the device DB and signal tables,
not object geometry).

On `CreateCustomObjectN(name, p, angle, showPref)`: **VERIFIED** that
`showPref` only controls whether the Object Properties dialog appears. It has
nothing to do with regeneration; passing `False` is correct and is not the
cause of anything. Separately, the non-`N` `CreateCustomObject` carries the
Remark that its objects "don't resolve as 'new objects' after creation" — i.e.
`IsNewCustomObject` never fires for them. `CreateCustomObjectN` is the right
choice and we are already using it.

---

## 5. macOS vs Windows

I found **no evidence of any macOS-specific difference in PIO regeneration
semantics** — no official statement, no forum thread, nothing in any of the
nine codebases. This is a **negative result**, reported as such.

What *is* macOS-specific is entirely about **getting code to run**, and it is
the constraint every project hits:

> "Vectorworks' Python API offers exactly one way to get periodic main-thread
> callbacks: `vs.RegisterDialogForTimerEvents` on a layout dialog shown with
> `vs.RunLayoutDialog` — which is modal. There is no modeless dialog, no idle
> handler, no timer without a dialog in the `vs` module. A true background
> bridge... requires a C++ SDK plugin with an idle/timer event handler."
> — vicquick, `legacy/README.md`

That matches our own finding (`MACOS-EXECUTOR.md` §3): in 3,078 indexed `vs`
functions the only `Notif*` name is `NotifyPullDownClicked` and there is no
`*Idle*` at all. **Confirmed independently; that door is closed.** The answer
is native, and §0.2 is the answer.

---

## 6. What to do next, in order

### 6.1 Run the control test before spending anything else. Half an hour.

This is now the highest-value experiment in the project, because §0.1 says our
existing evidence does not support our existing conclusion. From the Python
menu command (approach 3, the blessed context), **in two separate runs**:

```python
# RUN 1 — create only. Do not measure. Let the script END.
import vs
h = vs.CreateCustomObjectN('Ball Bearing', (5,5), 0, False)
vs.SetName(h, 'REGEN_PROBE')

# RUN 2 — a separate invocation of the menu command.
import vs
r = vs.CreateRectangle(0,0,1,1)          # CONTROL: does GetBBox work at all?
print('rect  ', vs.GetBBox(r))            # expect a real, non-zero bbox
h = vs.GetObject('REGEN_PROBE')
print('pio   ', vs.GetBBox(h))            # THE ANSWER
print('kids  ', vs.FInGroup(h))
```

Interpretation:
- **Rect non-zero, PIO non-zero** → the engine was never dead, `ResetObject`
  works, our §3.3 conclusion was a measurement artefact, and the ConnectCAD
  bind should be retried across two script runs. Everything unblocks.
- **Rect non-zero, PIO zero** → `GetBBox` is sound, the PIO genuinely did not
  regenerate even across runs. Then go to §6.2, then §6.3.
- **Rect zero** → `GetBBox` is broken in this context and every measurement in
  `CONNECT-MECHANISM.md` §3 must be redone with a different observable
  (`FInGroup`, `Count` of children, a screenshot).

Then repeat the same two-run split for the actual ConnectCAD case:
`SetRField` the four `Src_*`/`Dst_*` fields and `ResetObject` in run 1; check
`CC_GetCircuitSource` in run 2. `CONNECT-MECHANISM.md` §3.2 says a cross-run
recheck was done for the *bind* — do it again cleanly now that we know the
mechanism, and record which run each call happened in.

### 6.2 Then try the three regeneration triggers we have never tried. Free.

In order of evidence strength, all in the menu-command context:

1. **`vs.HMove(h, 0, 0)`** — the official `ReDraw` page's own Remark
   recommends it where redraw and `ResetObject` fail. Requires the PIO to have
   "Reset on Move" enabled, which ConnectCAD circuits plausibly do.
2. **`vs.DSelectAll(); vs.SetSelect(h); vs.Scale(1.0, 1.0); vs.DSelectAll()`** —
   upstream's documented, forum-confirmed workaround for the one PIO class
   where `ResetObject` provably does nothing. Selection-based, so it goes
   through a different engine path than `ResetObject`.
   ⚠ Upstream warns this can pop a **modal** dialog on error, which in a bridge
   context blocks everything — make it the last call in a batch.
3. **`vs.LDevice_Reset(h)` / `vs.LDevice_ResetVisual(h)`** for Spotlight
   lighting devices. Not applicable to ConnectCAD circuits, but it is the
   sanctioned reset for the other half of our domain and we should know whether
   it behaves differently from `ResetObject`.

Do **not** repeat the §3.4 crash sequence. `SetLayerScale` and
`UpdatePIOFromStyle()` stay on the forbidden list.

### 6.3 Only then, the native macOS plugin

If and only if §6.1 and §6.2 both come back negative, the C++ SDK is the route
— and it is now a port, not research:

1. Mirror `chandz102/vwx-mcp @ macos-native-port` immediately (it is an
   unmerged fork branch).
2. Build it with the traps in §0.2 pre-loaded. Requires the VW 2026 Mac SDK
   and a credentials file.
3. Replace the trigger with `gSDK->DoMenuName("VWX Bridge Start", 0)` on a
   `CFRunLoopTimer` — no Accessibility grant, works backgrounded. This deletes
   `MACOS-EXECUTOR.md` §4.3 and §4.8 as concerns.
4. If Python-in-menu-command still will not regenerate, escalate to BhaveshY's
   model: drop Python entirely and call `gSDK->` directly from the main-thread
   pump. **Never** call `IPythonScriptEngine::ExecuteScript` from native code
   (§2 rule 2), and **never** call the SDK off the main thread (§2 rule 1).

### 6.4 Steal Gribiche64's guard regardless

Any write path we ship must refuse a patch that references a symbol or resource
not already present in the document. §3.8 is what happens without it, on a real
show file, in our exact industry.

---

## 7. Bluntly

- **Nobody has demonstrated scripted PIO regeneration on macOS.** Also nobody
  has demonstrated it on **Windows**: upstream never verifies it, and the one
  project that tries hardest reports Space, Slab and Roof failing live.
- **But the C++ SDK is probably not yet the answer for us**, and I would not
  authorise that spend today. Our evidence that the engine is dead consists of
  two same-script bbox comparisons that the official `ResetObject` page
  explicitly says are invalid tests. §6.1 costs half an hour and can overturn
  the entire premise.
- **The macOS execution-context problem — the thing that actually looked
  unsolvable — is solved and public.** `gSDK->DoMenuName()` from a native timer
  needs no Accessibility permission and works while VW is backgrounded. That
  removes the blocker `MACOS-EXECUTOR.md` §4.3 spent its length on.
- The two projects most visible in the MCP directories (mako-357 and its
  chronista-club mirror) are **unbuildable and have never touched a plug-in
  object.** Discount directory listings entirely; read source.

---

## 8. Sources

Official:
- ResetObject — https://github.com/Vectorworks/developer-scripting/blob/main/Function%20Reference/Functions/ResetObject.md
- ResetBBox — https://github.com/Vectorworks/developer-scripting/blob/main/Function%20Reference/Functions/ResetBBox.md
- CreateCustomObjectN — https://github.com/Vectorworks/developer-scripting/blob/main/Function%20Reference/Functions/CreateCustomObjectN.md
- CreateCustomObject — https://github.com/Vectorworks/developer-scripting/blob/main/Function%20Reference/Functions/CreateCustomObject.md
- IsNewCustomObject — https://github.com/Vectorworks/developer-scripting/blob/main/Function%20Reference/Functions/IsNewCustomObject.md
- ReDraw — https://github.com/Vectorworks/developer-scripting/blob/main/Function%20Reference/Functions/ReDraw.md
- HMove — https://github.com/Vectorworks/developer-scripting/blob/main/Function%20Reference/Functions/HMove.md
- Developer wiki (403s direct; the repo above is the mirror) — https://developer.vectorworks.net/
- SDK repo — https://github.com/Vectorworks/developer-sdk

Projects:
- https://github.com/chandz102/vwx-mcp/tree/macos-native-port + https://github.com/vicquick/vwx-mcp/issues/8
- https://github.com/vicquick/vwx-mcp
- https://github.com/BhaveshY/vectorworks-mcp
- https://github.com/upipibi/claude-vectorworks-mcp
- https://github.com/mako-357/vectorworks-mcp / https://github.com/chronista-club/vectorworks-mcp
- https://github.com/randneto-lab/vwx-mpc-server-plugin
- https://github.com/edmacovaz/rt-vectorworks-mcp
- https://github.com/Gribiche64/vectorworks-bridge
- https://github.com/togawamanabu/vectorworks-mcp

Forum (403s direct fetches; reached via search snippets / text proxy):
- CreateCustomObjectN not showing in PDF export — https://forum.vectorworks.net/index.php?/topic/112850-vscreatecustomobjectn-not-showing-in-pdf-export/
- Official MCP request, no staff reply — https://forum.vectorworks.net/topic/134256-official-model-context-protocol/
- Third-party MCP review request — https://forum.vectorworks.net/topic/134312-review-request-vectorworks-mcp-server-from-a-third-party/
- AppleScript to trigger Python scripts — https://forum.vectorworks.net/index.php?/topic/93284-using-applescript-to-trigger-python-scripts-in-vw/
