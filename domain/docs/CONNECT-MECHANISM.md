# How a ConnectCAD circuit connects to a device socket

**Status: PARTIALLY SOLVED — and the blocker is not ConnectCAD, it is the bridge.**

Established live against Vectorworks 2026 (31.7.0.1), ConnectCAD built-in,
document `AI TESTING .vwx`, 2026-09-01/02.

| Question | Answer |
|---|---|
| Do sockets attach to devices from script? | **YES, verified** by `CC_GetDevice`. Mechanism: the socket must be a **direct child of the Device PIO**, and the only call that puts it there is `vs.HDuplicate` of a socket already inside that device. |
| Do circuits bind to sockets from script? | **NO. Not by any route tried.** `CC_GetCircuitSource` returned `(nil,nil,nil,nil)` in every experiment. |
| Why not? | **Plug-in-object regeneration does not run in the bridge's execution context.** This is not ConnectCAD-specific — stock Vectorworks PIOs also generate zero geometry here. ConnectCAD establishes the circuit↔socket bind inside the Circuit PIO's recalculate, which therefore never fires. |
| Is "exact" wiring achievable from script today? | **Not end-to-end.** Device + socket topology: yes. Real circuit bindings: no, until the regeneration blocker is fixed or a human runs one ConnectCAD menu command. |

---

## 1. The oracle and what it says

`vs.CC_GetCircuitSource(hCircuit)` / `CC_GetCircuitDest` return a 4-tuple
`(device, devSocket, adapter, socket)`. `vs.CC_GetDevice(hSocket, skipAdapters)`
returns the socket's parent device. These are the only trustworthy tests; the
drawing and the record fields both lie.

Every result below is from those calls, not from appearances.

---

## 2. Sockets → devices: SOLVED

### 2.1 The object model (ground truth)

Read out of `Libraries/ConnectCAD/Samples/Sample Worksheets.vwx`, symbol
`VidJack2`, imported with `BuildResourceListN(16, path)` +
`ImportResourceToCurrentFile` — no need to open the file:

```
Symbol definition "VidJack2"
└── Device PIO            name = "<DEV>{4F3BBF5B-676B-11EA-9F0B-7085C28E5E60}"
    ├── group             (the Top/Plan 2D component — a duplicate render)
    │   ├── Socket PIO    name = "{4F3BBF5D-...}"   record Socket.name = "PORT05"
    │   ├── Socket PIO    name = "{4F3BBF5F-...}"   record Socket.name = "PORT29"
    │   └── symbol        VJX_label
    ├── Socket PIO        (unnamed — the live pair)
    ├── Socket PIO
    └── symbol            VJX_label
```

Facts:

* **Sockets are direct children of the Device PIO**, reachable with
  `vs.FInGroup(hDevice)` → `vs.NextObj`. Nothing else links them: the Socket
  record has 22 fields and **not one references a device**.
* `CC_GetDevice(socket, False)` returns the containing Device handle for these
  sockets. **Verified.**
* Sockets **survive** `vs.ResetObject(hDevice)` — they are persistent contents
  of the PIO, not regenerated geometry. **Verified** (count and record values
  unchanged across reset).
* ConnectCAD names its objects with GUIDs: device `<DEV>{GUID}`, socket
  `{GUID}`. `vs.CreateUUID()` produces exactly that braced form.
* `Socket.ConnSymbol` / `Socket.TextSymbol` are **prefixes**, not symbol names.
  `skt_con_vjf_` + `type` → `skt_con_vjf_IO`; `skt_txt_vjf_` + `Orientation`
  → `skt_txt_vjf_L`. Generic equivalents are `skt_con_` (+`IN`/`OUT`/`IO`) and
  `skt_txt_` (+`L`/`R`). Those symbols must exist in the document or the socket
  draws nothing.
* Child bounding boxes are in the **device's local frame**. World = local +
  `vs.GetSymLoc(hDevice)`; confirmed against `vs.GetEntityMatrix(hDevice)`,
  which returns the same translation.

### 2.2 The call sequence that works

```python
seed = <a Device PIO that already contains ≥1 Socket>   # see 2.3
dev  = vs.HDuplicate(seed, 0, 0)      # lands in the seed's container
vs.SetParent(dev, vs.ActLayer())      # device → layer: this direction WORKS
vs.SetName(dev, '<DEV>' + vs.CreateUUID())
vs.SetRField(dev, 'Device', 'name',  'CAM-1')     # fields are LOWERCASE

skt0 = <first Socket child of dev>                 # FInGroup / NextObj
skt1 = vs.HDuplicate(skt0, 0, dy)                  # ← adds a socket to dev
vs.SetName(skt1, vs.CreateUUID())
vs.SetRField(skt1, 'Socket', 'name', 'SDI OUT')
vs.SetRField(skt1, 'Socket', 'type', 'OUT')        # direction lives in `type`
vs.SetRField(skt1, 'Socket', 'ConnSymbol', 'skt_con_')
vs.SetRField(skt1, 'Socket', 'TextSymbol', 'skt_txt_')

assert str(vs.CC_GetDevice(skt1, False)) == str(dev)     # ← the proof
```

Deleting a socket is plain `vs.DelObject`. Growing/shrinking the socket set by
duplicate-and-delete is how `cc_build.cc_make_device` works.

### 2.3 Where to get a seed device

Only two shipped symbols contain a device **with** sockets. Both are reachable
without opening the file:

| Symbol | File | Sockets |
|---|---|---|
| `VidJack2` | `Libraries/ConnectCAD/Samples/Sample Worksheets.vwx` (also `Defaults/ConnectCAD/Jacks/Jacks.vwx`) | 2 (`IO`) |
| `VidTP` | `Libraries/Defaults/ConnectCAD/Panels/Panels.vwx` | 1 (`IO`) |

`Basic Device`, `Basic Distributor`, `Basic Lighting Device` (`Defaults/
ConnectCAD/Device/Devices.vwx`) and `DAdevice` all contain **zero** sockets and
cannot seed anything.

### 2.4 What FAILED, and how

| Attempt | Result |
|---|---|
| `vs.SetParent(socket, device)` | returns **False**; socket stays on the layer. The Device PIO is not a `SetParent` container. |
| `vs.BeginGroupN(device)` … `CreateCustomObjectN('Socket')` … `EndGroup()` | silently ignored — socket lands on the layer, `CC_GetDevice` → nil. |
| Geometric overlap: socket created at the device's left edge / inside / centre / right edge, then `ResetObject` on both | `CC_GetDevice` → nil at every position. There is no proximity tolerance because there is no proximity rule. |
| `vs.Group()` the device and socket together | `CC_GetDevice` → nil. Sibling containment is not the link. |
| Set `Device.make` / `Device.model` to a row in `ConnectCAD Devices DB.txt`, then `ResetObject` | **No sockets generated.** The device DB is read by the *insert tool*, not by the Device PIO. |
| `CreateCustomObjectN('Socket', x, y, 0, False)` on a layer | Creates a Socket PIO with all fields blank and a **zero bounding box**. It never draws and never binds. |

---

## 3. Circuits → sockets: NOT ACHIEVED

### 3.1 Writing the record fields is cosmetic

```python
vs.SetRField(cir, 'Circuit', 'Src_Dev_Name', 'CAM-1')   # CamelCase here
vs.SetRField(cir, 'Circuit', 'Src_Skt_Name', 'SDI OUT')
vs.SetRField(cir, 'Circuit', 'Dst_Dev_Name', 'SW-1')
vs.SetRField(cir, 'Circuit', 'Dst_Skt_Name', 'SDI IN 1')
vs.ResetObject(cir)

vs.CC_GetCircuitSource(cir)   # → (None, None, None, None)
```

The values persist and would show in a worksheet, so the drawing *reads* wired.
`__Src_ID` / `__Dst_ID` stay **empty**. This is exactly the "looks wired, is
not" failure the mission warned about. **Do not ship it.**

### 3.2 Every other route also returned nil

| Attempt | Result |
|---|---|
| `__RECONNECT = 'True'` + `ResetObject` | Flag persists as `True` — it is never *consumed*. No bind. |
| `__ISNEW = 'True'` + `ResetObject` | Same. `__ISNEW` is already `True` from creation and stays `True` forever. |
| Geometry: `MoveTo`/`LineTo` endpoint placed exactly on the socket, then `CC_CircuitFromShape`. Swept 10 candidate points — socket bbox corners, all four edge midpoints, bbox centre, and `GetSymLoc` — in **world coordinates verified against `GetEntityMatrix`** | `CC_GetCircuitSource` → nil at every one of the 10 points. No tolerance was found because no geometric rule fired. |
| Same, re-checked in a **separate** script execution after `ReDrawAll()` (in case regeneration were merely deferred) | still nil, `__ISNEW` still `True`. |
| `__Src_ID` = the socket's object name (`{GUID}`), device named `<DEV>{GUID}`, matching ConnectCAD's own naming | `vs.GetObject(name)` resolves the socket fine, but `CC_GetCircuitSource` → nil. |
| `vs.CC_ReloadData()` then `DoMenuTextByName('Reset All Plug-Ins', 0)` | No change. |

### 3.3 The real reason — and it is not ConnectCAD

`CC_CircuitFromShape` produces a Circuit PIO whose **bounding box is
(0,0)–(0,0)**. It has a path (`GetCustomObjectPath` returns a *copy* of the
source line, living inside the circuit — so deleting the source line is still
correct), but it generated no output geometry at all.

The generalising test:

```python
for nm in ('Angle', 'Ball Bearing', 'Base Cabinet'):
    h = vs.CreateCustomObjectN(nm, 5.0, 5.0, 0, False)
    vs.GetBBox(h)        # → ((0,0),(0,0))  — and FInGroup(h) is empty
```

**Stock Vectorworks plug-in objects, nothing to do with ConnectCAD, also
generate zero geometry from this bridge.** Corroborating: setting
`Device.symbol` to a different label symbol and calling `ResetObject` left the
drawn symbol unchanged.

The cause is architectural. `vwx-plugin/vwx_mcp_bridge.py:397` runs the bridge
inside `vs.RunLayoutDialog(dlg, _cb)` and dispatches every script from that
modal dialog's **timer-event callback**. While that dialog owns the event loop,
Vectorworks does not run the parametric engine. Object creation and record
writes are direct data operations and work fine; *regeneration* does not.

ConnectCAD establishes the circuit↔socket bind inside the Circuit PIO's
recalculate (that is what consumes `__ISNEW` and fills `__Src_ID`). It cannot
run, so no bind can be made. Devices survive this only because
`CC_DeviceFromShape` builds its geometry itself, and because `HDuplicate`
copies geometry that already exists.

### 3.4 Do not repeat this — it crashed Vectorworks

Trying to force regeneration killed the application (no crash report; VW simply
disappeared). The script ran, in order, on a selected stock PIO:

```
ResetObject → ResetBBox → SetLayerScale(2.0) → SetLayerScale(1.0)
→ HMove + ResetObject → SetSelect + DoMenuTextByName('Reset All Plug-Ins', 0)
→ SetRField + ResetObject → ReDrawAll → UpdatePIOFromStyle() → …
```

Most likely culprits are `vs.SetLayerScale` (a document-wide PIO reset invoked
from the dialog-timer context) and `vs.UpdatePIOFromStyle()`. `DoMenuTextByName
('Reset All Plug-Ins', 0)` on its own had completed safely earlier in the
session, so it is probably not the trigger, but it was in the same script and
is not exonerated.

`vwx-plugin/vwx_pump.py` already documents the rule this violated: from a
non-dispatch context, *opening a dialog crashes Vectorworks*. Treat
"force a document-wide regeneration from the bridge" as the same class of
operation.

**No data was lost** — the document had never been saved from script, and
`AI TESTING .vwx` on disk is byte-identical to its pre-session state. A stale
`.AI TESTING .lck` lock file is left in `~/Downloads/`; delete it or
Vectorworks will offer the file read-only on next open.

---

## 4. The supported bulk path — real, but human-gated

ConnectCAD ships exactly the workflow this project wants. From
`Workspaces/ConnectCAD.vww` and the plug-in binary:

| Menu universal name | Internal | What it does |
|---|---|---|
| `Make Connections from List` | `CC_MakeConnectionsFromList` | Reads a worksheet of src device / src socket / dst device / dst socket / signal / cable number and **creates genuinely bound circuits**. |
| `Create Devices From BoM` | `CC_CreateDevicesFromWorksheet`, `CC_MakeDevicesFromList` | Creates devices from a BoM worksheet, pulling socket sets out of the device database. |
| `Check Drawing`, `CompareListDrawingMenu` | `CC_CompareCableListAndDrawing` | Reconciles the drawing against the list. |

None of them is a `vs.*` function. `dir(vs)` on the live document returns
**exactly 13** `CC_*` names — the 7 getters plus `CC_*FromShape` ×4,
`CC_OnFindAndReplace`, `CC_ReloadData`. `CC_CreateDevicesFromWorksheet` and
friends exist only as menu commands.

Both commands open dialogs (`DlgSelectWorksheet`, `DlgWSColumnsAssignment`), so
`vs.DoMenuTextByName` **must not** be used to fire them from the bridge — that
is the documented crash path.

The device database is a plain 24-column TSV, 17 126 rows, UTF-8 BOM, CRLF:
`Libraries/Defaults/ConnectCAD/ConnectCAD_Database/ConnectCAD Devices DB.txt`

```
0 make  1 model  2 width(mm)  3 height  4 depth  5 weight  6 power
7 modular  8 nslots  9–13 (unused)
14 connector  15 qty  16 side(L/R)  17 socket name  18 signal  19 direction
20 (unused)  21 category  22 subcategory  23 (unused)
```
The first row of a device carries columns 0–8 and 21–22; each additional socket
is a continuation row with only columns 14–19 populated.

---

## 5. What to do about the 25-device tour diagram

Ranked, honestly:

1. **Fix the bridge context.** Everything else is a workaround. The bridge needs
   a dispatch path where the parametric engine runs — genuine command dispatch,
   per `vwx_pump.py`'s own context map — not a `RunLayoutDialog` timer callback.
   Until then no script can make a real circuit binding, by any API.

2. **Script the data, let a human click once.** Generate the device set with
   `cc_build.cc_make_device` (bindings verified), write a circuit-list worksheet,
   and have the operator run *Make Connections from List*. One click for 25
   devices, and the bindings are ConnectCAD's own.

3. **Do not ship label-only circuits.** `cc_make_circuit` returns
   `verified: False` on purpose. A diagram whose `Src_Dev_Name` fields are
   populated but whose `__Src_ID` is empty will pass a visual review and fail
   every cable schedule, length calculation and signal trace downstream.

### The one experiment still worth running

Untested, because running it requires ending the bridge that is the only way to
run anything: **does regeneration happen deferred, once the dialog closes?**

1. Build two devices and one circuit via `cc_build`. Leave them.
2. Click **Stop** on the bridge dialog. Watch whether the circuit draws.
3. Restart the bridge and query `CC_GetCircuitSource`.

If it binds, the whole approach is viable with a "commit by closing the bridge"
step. If it does not, item 1 above is the only road.

---

## 6. Corrections to `domain/docs/records/connectcad-records-VW2026.md`

* "Both FromShape calls leave the source shape in the document — delete it" is
  right, and now explained: `CC_CircuitFromShape` **copies** the line into the
  circuit (`GetCustomObjectPath` returns the copy, handle differs from the
  source). Deleting the original does not damage the circuit.
* Socket `ConnSymbol` / `TextSymbol` are prefixes, completed with `type` and
  `Orientation` respectively.
* A Socket PIO outside a Device is inert: blank fields, zero bbox, no bind.

## 7. APIs confirmed absent

`CC_DeviceSockets` does not exist — enumerate with `FInGroup`/`NextObj` and
filter on `GetName(GetParametricRecord(h)) == 'Socket'`. Neither does any
`vs.CC_*` for the worksheet workflows.
