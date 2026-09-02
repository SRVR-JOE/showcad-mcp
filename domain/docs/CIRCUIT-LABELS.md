# Circuit end labels — the mechanism, from the compiled plug-in

Source of truth for this document: disassembly + resource decoding of
`/Applications/Vectorworks 2026/Plug-Ins/connectCAD.vwlibrary/Contents/MacOS/connectCAD`
(the arm64 slice; the symbol table is **not** stripped — every `connectCAD::` method
name is present, which is what made this tractable). Everything marked **[BIN]** is
read directly out of that binary and is not an inference. Companion doc:
`CONNECTCAD-LABELS-RESEARCH.md` (documentation-side research, by the docs agent).

---

## 0. The one-line answer

**The arrow formula resolves PER END. One formula string produces different text at
each end, and each end names the FAR end.** You author it in `Src_*` terms; ConnectCAD
substitutes `Dst_*` when it draws the source-end arrow.

**But it only renders when `Circuit Type` is `arrow` (or `ext link src` / `ext link dst`).**
All 220 circuits in DOJA26_SRVR_V1 are `polyline`, so the arrow-label code path is
never entered. That is the whole reason nothing we have set so far has appeared.

---

## 1. The per-end question — SETTLED **[BIN]**

### 1.1 The resolver takes an "which end" flag

```
connectCAD::CCircGraphicsDataHandler::GetArrowFormulaValue(char** hCircuit, bool bFarEnd) const
    @ 0x3e8d58 (arm64)
```

When `bFarEnd` is **true**, it builds a `unordered_map<TXString,TXString>` of
**parameter-name redirects** and passes it to `GetFormulaValue()`:

| formula token reads | is served the value of |
|---|---|
| `Src_Dev_Name`  | `Dst_Dev_Name` |
| `Src_Dev_Tag`   | `Dst_Dev_Tag` |
| `Src_Skt_Name`  | `Dst_Skt_Name` |
| `Src_Skt_Tag`   | `Dst_Skt_Tag` |
| `Src_Signal`    | `Dst_Signal` |
| `Src_Skt_Conn`  | `Dst_Skt_Conn` |
| `Src_Skt_Circs` | `Dst_Skt_Circs` |
| `Src_Room`      | `Dst_Room` |
| `Src_Rack`      | `Dst_Rack` |
| `Src_RackU`     | `Dst_RackU` |
| `Src_Slot`      | `Dst_Slot` |

When `bFarEnd` is **false** the map is empty and `Src_*` resolves normally.

It then picks the socket context the same way:

```
0x3e907c   cbz  w20, 0x3e9088          ; w20 == bFarEnd
0x3e9080   bl   CAssociationsHandler::GetCircuitDestinationSocket()   ; bFarEnd == true
0x3e9088   bl   CAssociationsHandler::GetCircuitSourceSocket()        ; bFarEnd == false
0x3e9094   bl   GetDeviceFromSocket(...)
```

so `#Socket.*#` and `#Device.*#` tokens follow the same end as the `Src_*` tokens.

### 1.2 Two call sites, one per end

```
cCADCircuitObj_EventSink::DrawSourceArrowLabel(...)  @ 0xdfd60:  mov w2, #0x1  -> bFarEnd = TRUE
cCADCircuitObj_EventSink::DrawDestArrowLabel(...)    @ 0xe0aa4:  mov w2, #0x0  -> bFarEnd = FALSE
```

**Therefore: the arrow at the SOURCE end prints the DESTINATION's data; the arrow at
the DESTINATION end prints the SOURCE's data.** Each end names the far end. It is not
a render-once-stamp-twice implementation.

### 1.3 Independent corroboration from the string table

`connectCAD.vwr/Strings/cCADCircuitObj.vwstrings` carries a block commented, verbatim:

```
// Arrow end circuit params
"Src_Dev_Name"	= "Device Name";
"Src_Dev_Tag"	= "Device Tag";
"Src_Skt_Name"	= "Socket Name";
"Src_Skt_Tag"	= "Socket Tag";
"Src_Signal"	= "Socket Signal";
"Src_Skt_Conn"	= "Socket Connector";
"Src_Skt_Circs"	= "Socket Circuit(s)";
"Src_Room"	= "Room";
"Src_Rack"	= "Rack";
"Src_RackU"	= "Rack U";
"Src_Slot"	= "Slot";
"CircuitLayer"	= "Layer";
```

Only the `Src_*` half is exposed, and it is exposed under **unqualified** labels
("Device Name", not "Source Device Name"). That is exactly the design the swap map
implements, and it is why the forum screenshot showed `#Circuit.Device Tag#` with no
Src/Dst prefix. `CCircGraphicsDataHandler::InitCircuitFields()` @ 0x3e7440 builds the
Insert Field popup from precisely this list.

---

## 2. The gate — why nothing has appeared yet **[BIN]**

`cCADCircuitObj_EventSink::Recalculate()` @ 0xe0e60 reads the `Circuit Type` param as a
string and dispatches on it. The stored values are **lower-case**:

| stored `Circuit Type` | OIP label | what is drawn |
|---|---|---|
| `polyline` | Polyline | `DrawPolygonCircuit` — a line. No arrow label. |
| `rounded`  | Rounded  | `DrawRoundedCircuit` — a line. No arrow label. |
| `chamfer`  | Chamfer  | `DrawChamferCircuit` — a line. No arrow label. |
| `arrow`    | Arrow    | `SetupArrowLabelText` → `CreateSourceArrow` + `CreateDestArrow`. **Labels here.** |
| `ext link dst` | (legacy Link tool) | `CreateSourcePill` on class `CC-Circuit-Label` |
| `ext link src` | (legacy Link tool) | `CreateDestPill` on class `CC-Circuit-Label` |

The literal comparison chain, resolved from the disassembly:

```
0xe1da8  bl operator==(TXString,TXString)   ; vs "arrow"        -> arrow branch
0xe1f3c  bl operator==(TXString,TXString)   ; vs "ext link dst" -> source pill
         ...                                ; vs "ext link src" -> dest pill
0xa42038 = "rounded"   0xa42080 = "chamfer"   0xa420c8 = "arrow"
0xa42110 = "ext link dst"   0xa42158 = "ext link src"
```

`DrawSourceArrowLabel` / `DrawDestArrowLabel` are reachable ONLY from
`CreateSourceArrow` / `CreateDestArrow` / `CreateSourcePill` / `CreateDestPill`, all of
which live inside those last three branches. **On a `polyline` circuit the arrow-text
code is dead. `__CustomizeArrow`, `__ArrowFormula` and `__ArrowStyle` are read but never
drawn.**

Arrow / pill text is drawn on class **`CC-Circuit-Label`** (literal `"CC-Circuit-Label"`
appears at 0xe1fe0, 0xe20c0, 0xe223c, 0xe23c8, always paired with
`"ConnectCADClasses"`). That class must be visible.

### `__ArrowStyle` is an index, and 0 means nothing draws

`CDlgCircuitGraphics::FillArrowStyles()` @ 0x3e7440-region fills the popup in this order:

| value | style |
|---|---|
| 0 | `ArrowStyle_None` |
| 1 | `ArrowStyle_Arrow` |
| 2 | `ArrowStyle_Pill` |
| 3 | `ArrowStyle_Feather` |
| 4 | `ArrowStyle_Reference` |
| 5 | `ArrowStyle_Wireless` |

All 220 circuits currently hold `__ArrowStyle='0'`. If you set `__CustomizeArrow='True'`
you **must** also set a non-zero style or you get no graphic. `4` (Reference) is the
cross-reference chevron and is the closest match to the client's house style.

### `ShowEnd` is dead code **[BIN]**

Across the entire arm64 slice, the parameter-name string `ShowEnd` (bss global
`0xcf54b8`) is referenced **exactly once** — in the static initializer at `0x3eb5d0`
that constructs the name string itself. Nothing ever calls `GetParamBool("ShowEnd")` or
`SetParamBool("ShowEnd")`. It is a vestigial parameter. Setting it to `'True'` on all
220 circuits did nothing and can be reverted or left alone; it is not the mechanism.
(The same is true of `Label` @ `0xcf5500` — never read by the draw path — although
`Label` is still reachable *as a formula token*, see §3.)

---

## 3. The formula language **[BIN]**

### Syntax

`CCircGraphicsDataHandler::ComposeLinkFormula(TXString a, TXString b)` @ 0x3e9600-region
formats with the literal:

```
#%s.%s#
```

So a token is **`#<RecordName>.<FieldName>#`** — the `CustomLinkFormulas.xml` dialect
(`#Device.make#`), **not** the `CustomSymbolLinkFormulas.xml` dialect (`#Device#.#make#`).
Text outside `#…#` is literal. Concatenate freely.

### Stored form vs displayed form

`GetArrowLocalizedFormula()` / `GetArrowUniversalFormula()` /
`TranslateFormula(TXString, vector<SCircuitField>, bool)` convert between the two. The
dialog shows the **localized** labels ("Device Tag"); `__ArrowFormula` stores the
**universal** record-parameter names. `GetArrowFormulaValue` composes its own
substitutions using the universal literals `"Circuit"` (bss `0xcfb7b8`) and
`"CircuitLayer"` (bss `0xcfd4b0`), confirming the stored formula is universal.

So the string to write into `__ArrowFormula` is, e.g.:

```
#Circuit.Src_Dev_Name#
#Circuit.Src_Dev_Name# . #Circuit.Src_Skt_Name#
```

⚠️ **Confidence: high but not proven end-to-end.** Do not bulk-write 220 records on
this assumption. See the one-circuit calibration step in §4.

### Complete Insert Field vocabulary

Three record namespaces, from `InitCircuitFields()` / `InitDeviceFields()` /
`InitSocketFields()`. Record token = the plug-in's `localized_name`.

**`Circuit`** (`cCADCircuitObj`)

| universal field name (stored) | popup label | per-end? |
|---|---|---|
| `Number` | Number | no |
| `Cable` | Cable | no |
| `Signal` | Signal | no |
| `Circuits` | Circuits | no |
| `Cable Type` | Cable Type | no |
| `Cable Outside Diameter` | Cable Ouside Diameter *(sic — typo is in the shipped file)* | no |
| `CableCalculatedLength` | Calculated Cable Length | no |
| `Src_Dev_Name` | Device Name | **YES** |
| `Src_Dev_Tag` | Device Tag | **YES** |
| `Src_Skt_Name` | Socket Name | **YES** |
| `Src_Skt_Tag` | Socket Tag | **YES** |
| `Src_Signal` | Socket Signal | **YES** |
| `Src_Skt_Conn` | Socket Connector | **YES** |
| `Src_Skt_Circs` | Socket Circuit(s) | **YES** |
| `Src_Room` | Room | **YES** |
| `Src_Rack` | Rack | **YES** |
| `Src_RackU` | Rack U | **YES** |
| `Src_Slot` | Slot | **YES** |
| `CircuitLayer` | Layer | **YES** (gated on `__SameLayer`; prints the other end's `__DstLayer`) |

**`Device`** (`cCADDeviceObj`) — resolved against the far end's device:
`Symbol`, `Display Tag`, `Description`, `Device Name`, `Make`, `Model`, `Height`,
`Width`, `Depth`, `Power`, `BTU`, `Weight`, `Modular`, `Number of slots`, `Room`,
`Rack`, `Rack U`, `Slot`.

**`Socket`** (`cCADSocketObj`) — resolved against the far end's socket:
`Socket Name`, `Display Tag`, `Signal`, `Connector on Cable`.

Plus any **custom record format** attached to the circuit (documented behaviour).

### The trap

`GetFormulaValue()` enumerates the record generically (`VWRecordObj::GetParamName(i)`
→ `ComposeLinkFormula` → `GetParamValue`), so `#Circuit.Dst_Dev_Name#` **also resolves** —
but only through the literal path, never through the swap map. It would print the
destination device at *both* ends. **Always author with `Src_*`. Never use `Dst_*` in an
arrow formula.**

---

## 4. Recipe

### The user's requirement

For `OG DA - 01 -> DIR.SDI_IN 01`: at the DIR end show `OG DA - 01`; at the OG DA end
show `SDI_IN 01`.

Note this is asymmetric — device name at one end, socket name at the other. A single
formula cannot do that, because the formula is symmetric by construction. The nearest
achievable, and almost certainly what is actually wanted, is:

```
#Circuit.Src_Dev_Name#.#Circuit.Src_Skt_Name#
```

which renders `DIR.SDI_IN 01` at the OG DA end and `OG DA - 01.<its socket>` at the DIR
end — the same `Device.Socket` idiom as the client's as-built. If the user genuinely
wants the bare forms, use `#Circuit.Src_Dev_Name#` and accept device-name-only at both
ends, or use Option B (§5) which allows a different formula per end.

### Option A — native circuit arrows. Confidence: HIGH. Cost: changes the drawing's look.

Per circuit, set:

| field | value |
|---|---|
| `Circuit Type` | `arrow` ← **the gate; nothing works without it** |
| `__CustomizeArrow` | `True` |
| `__ArrowFormula` | `#Circuit.Src_Dev_Name#.#Circuit.Src_Skt_Name#` |
| `__ArrowStyle` | `1` (Arrow) or `4` (Reference) — **never `0`** |

And at document level:

- class `CC-Circuit-Label` **visible**
- class `CC-Circuit-Connector` **hidden** (already done — this is the "cable type" text)

**The cost, stated plainly:** an `arrow` circuit is not drawn as a connecting line. The
`DrawPolygonCircuit` call is skipped entirely; you get a short stub off each socket with
an arrowhead and the far-end label. Converting all 220 circuits turns the schematic from
a wired diagram into a from/to list. Get the user to eyeball **one** converted circuit
before touching the rest.

#### Calibration step — do this first, it is not optional

1. Pick one circuit. Right-click → **Edit Circuit Graphics…** (context menu string
   `cmEditCircuitGraphics`). Tick *Customize arrow*, build the formula with the
   **Insert Field** popup, pick an Arrow Style, OK.
2. Read `__ArrowFormula`, `__ArrowStyle`, `__CustomizeArrow` back off that circuit.
3. Whatever serialization comes back is ground truth. Copy that exact string to the
   other 219. This sidesteps the localized-vs-universal question in §3 entirely.

Also set the document default while you are there: **ConnectCAD ▸ ConnectCAD Settings ▸
General ▸ Edit Default Circuit Graphics**. `DrawSourceArrowLabel` falls back to a stored
default text (handler member `+0x88`; `DrawDestArrowLabel` uses `+0xd0`) whenever
`__CustomizeArrow` is false — so setting the default means new circuits inherit it and
you never have to touch `__CustomizeArrow` at all.

### Option B — Data Tags. Confidence: MEDIUM-HIGH. Cost: 440 objects. Keeps the geometry.

This is the escape hatch if the user rejects the look of Option A, and it is the only
route that gives genuinely **different** text at the two ends.

ConnectCAD registers worksheet/data-tag functions with explicit far-end addressing
(`connectCAD.vwr/WSFunctionsHelp/Opt Desc DB.vwstrings`, verbatim):

```
ObjectData('eval circuit destination device', '<RecordName>', '<FieldName>')
ObjectData('eval circuit destination socket', '<RecordName>', '<FieldName>')
ObjectData('eval circuit source device',      '<RecordName>', '<FieldName>')
ObjectData('eval circuit source socket',      '<RecordName>', '<FieldName>')
ObjectData('eval socket device',              '<RecordName>', '<FieldName>')
```

Two tag styles, placed one at each end of each circuit:

- at the **source** end → `ObjectData('eval circuit destination device', 'Device', 'Device Name')`
- at the **destination** end → `ObjectData('eval circuit source socket', 'Socket', 'Socket Name')`

Since the circuit record already carries the denormalised `Dst_Dev_Name` /
`Src_Skt_Name`, a plain record-field data tag works too and is simpler.
Shipped starting point: `/Applications/Vectorworks 2026/Libraries/Annotations/Data Tag (styles)/Entertainment/ConnectCAD.vwx`.

Unverified: whether a data tag will anchor to a specific *end* of a circuit PIO rather
than its centre. If it will not, place them manually-offset or fall back to Option A.

### Option C — Panel Connectors. Confidence: HIGH that this is what the as-built did. Cost: remodelling.

**Correcting a premise in the brief:** the `Main CTP.Matrix In09` text in
*Disguise GX3 FullSize As Built.pdf* is **not** a circuit arrow. The drawing's own
LEGEND (top-right, ~x3069–3234 / y1940–2210 in PDF user space) spells the notation out:

```
Uncombined Panel Connector: Input    ->  Panel.Way / Panel Connector / <-- / Rack  U
Uncombined Panel Connector: Output   ->  Panel.Way / Panel Connector / --> / Rack  U
Combined Panel Connector: Input      ->  Panel / Rack U / CNUM / Way / Panel Connector <--
Combined Panel Connectors: Output    ->  Panel / Rack U / CNUM / Way / Panel Connector -->
```

`Main CTP.Matrix In09` is **`Panel.Way`** of an *uncombined* Panel Connector
(`PanelConnectorObj`, classes `CC-PanelConnector-DisplayTag`, `-Symbol`,
`-Connected-Device`, `-Connected-Socket`). The `HDMI Out01 … HDMI Out16` column under a
single `Main CTP` heading is the *combined* form — panel name once, Way per connector.
The `<--` / `-->` glyphs are part of the panel-connector symbol, not arrow text. The
inconsistent naming across that sheet (`HDMI Out01` here, `Main CTP.MV_IN13` there) is
the signature of hand-set panel/way names, not of a formula.

If the user's real goal is "make my drawing look like the Adlib as-built", the honest
answer is: model the patch panels as ConnectCAD Connection Panels and let the Panel
Connectors carry the cross-reference. That is a remodelling job, not a field edit.

---

## 5. Show or Hide Details — fully decoded **[BIN]**

`DlgShowHideDetails` (`DialogLayout/DlgShowHideDetails.vs`, plain UTF-8 — the byte-swap
warning does not apply to the `.vs` files) is a five-checkbox document-wide toggle,
menu title *"Show or Hide Details…"*, menu category **Legacy**:

| control | label |
|---|---|
| `kDescriptionsChBox` | Descriptions |
| `kJFTPNumbersChBox` | Jack / Terminal Panel numbers |
| `kCableNumbersChBox` | Cable numbers |
| `kLocationsChBox` | Locations |
| `kConnectorTypesChBox` | **Connector types** |

That last one is the user's complaint. It is the same thing as hiding
`CC-Circuit-Connector` (drawn by `cCADCircuitObj_EventSink::PlaceConnType()` @ 0xe1be8
and 0xe1c50, skipped when the connector value is the `"---"` sentinel). Since the class
has already been hidden on the live drawing, this dialog is now redundant — but it is
the supported UI route and is worth telling the user about, because it survives class
re-import and it is one click.

The dialog is a pure show/hide of existing geometry. It does **not** choose *what* the
circuit ends say — only whether the connector text is among the things they say.

---

## 6. Confidence ledger

| claim | confidence | basis |
|---|---|---|
| Arrow formula resolves per end; each end names the far end | **Certain** | swap map + two call sites with `w2=1` / `w2=0`, `GetCircuitDestinationSocket` vs `GetCircuitSourceSocket` **[BIN]** |
| Arrow/pill labels require `Circuit Type` ∈ {`arrow`, `ext link src`, `ext link dst`} | **Certain** | `Recalculate()` string-compare dispatch **[BIN]** |
| `ShowEnd` is inert | **Certain** | one reference in the whole slice, in its own name-string ctor **[BIN]** |
| `__ArrowStyle` 0=None … 5=Wireless | **Certain** | `FillArrowStyles()` fill order **[BIN]** |
| Token syntax `#Record.Field#` | **Certain** | `ComposeLinkFormula` format literal `#%s.%s#` **[BIN]** |
| Field vocabulary as listed in §3 | **Certain** | `InitCircuitFields` / `InitDeviceFields` / `InitSocketFields` **[BIN]** |
| `__ArrowFormula` is stored universal (`Src_Dev_Name`, not `Device Name`) | **High** | `TranslateFormula` + universal literals `"Circuit"` / `"CircuitLayer"` used in the resolver. **Verify by round-trip before bulk write.** |
| Class `CC-Circuit-Label` carries the arrow/pill text | **High** | class-name literal paired with the four Create* calls **[BIN]** |
| As-built's `Main CTP.Matrix In09` = Panel Connector `Panel.Way` | **High** | the drawing's own legend, transcribed |
| Data Tags can anchor to a specific circuit end | **Unverified** | needs a live test |
| Whether converting to `arrow` is visually acceptable | **Unknown — ask the user** | it removes the connecting line |

## 7. Recommended next action for the live agent

1. Convert **one** circuit to `Circuit Type='arrow'`, set the formula through the
   **Edit Circuit Graphics** dialog (not by writing the record), set Arrow Style to
   Reference, and screenshot it.
2. Read the four fields back and record the exact serialization here.
3. Show the user. If they accept the look → bulk-apply. If they do not → Option B.
4. Either way, set **Edit Default Circuit Graphics** at document level so the fix is
   inherited rather than stamped 220 times.

---

## 8. BUILT: `tools/vw_datatag_labels.py` (Option B, chosen)

The user rejected converting circuits to `Circuit Type='arrow'`. Option B is now
the deliverable. Script: `tools/vw_datatag_labels.py`. It runs as a **Resource
Manager script resource (Python)**, not through the bridge — the bridge's modal
dialog is why the parametric engine does not run, and it crashed VW twice.

### Mechanism

Two Data Tags per circuit, associated to the circuit, positioned at its two
ends, each reading the FAR end out of the circuit's own record:

| tag sits at | class | style | reads | for `OG DA - 01 -> DIR.SDI_IN 01` |
|---|---|---|---|---|
| source end | `SHOWCAD-EndLabel-AtSource` | `ShowCAD Far End At Source` | `Circuit.Dst_Skt_Name` | `SDI_IN 01` |
| dest end | `SHOWCAD-EndLabel-AtDest` | `ShowCAD Far End At Dest` | `Circuit.Src_Dev_Name` | `OG DA - 01` |

Circuit geometry is untouched — no `Circuit Type` change, no arrow stubs.
Neither class is `CC-Circuit-Connector`; that class stays hidden.

### The text is LIVE, not static

Nothing is stamped. The tag reads the record field at draw time, and
`cCADCircuitObj_EventSink::Recalculate()` rewrites `Src_*`/`Dst_*` on every
recalculation via `UpdateSourceSocketDetails()` @ `0xe14e8` and
`UpdateDestinationSocketDetails()` @ `0xe1508` **[BIN]**. Repatch a circuit and
the record changes; the tag follows. `DT_ResetAllDataTags()` is called once at
the end of a placement pass and is the documented recovery if any tag renders
stale.

### Why the tag styles are hand-made, not scripted

A Data Tag's text comes from a *layout symbol* whose text object carries a
"Use dynamic text" flag plus a serialized field definition
(`DataTag::Interfaces::CDataTagText::SetIsCalculatedField`,
`DataTag::Formula::CFormulaParserHelper::GetRecordType`). That serialization is
undocumented and untestable from here, so fabricating it in script would be
exactly the plausible-but-wrong output to avoid. Instead the user builds the two
styles once through the documented **Define Tag Field** dialog
(Advanced calculated field → Data Source: Record Format → Format Name:
`Circuit` → Field Name → *Add to Definition*), and the script only places,
styles, associates and verifies instances. The script **refuses to run** and
prints the click-path if the styles are absent.

### Association safety

`DT_AssociateWithObj` returns BOOLEAN and is asserted on. Where the unindexed
`DT_IsValid` is present it is used as a second, independent check
(`getattr`-guarded — it is in `vs_index_drift.json → live_only`). A tag that
fails either check is **deleted**, not left behind: an orphaned tag renders
plausibly while bound to the wrong object, which is the hazard
`SPOTLIGHT-DESIGN.md` documents. The report separates `tags_created` from
`tags_verified` and never claims a bind it cannot prove.

### API used — all checked against `vs_index.json` and `vs_index_drift.json`

Indexed and not in the dead list: `CreateCustomObjectN`, `SetPluginStyle`,
`IsNewCustomObject`, `DT_AssociateWithObj`, `DT_BeginMultipleMove`,
`DT_EndMultipleMove`, `DT_ResetAllDataTags`, `SetClass`, `NameClass`,
`ShowClass`, `ActiveClass`, `GetParametricRecord`, `GetName`, `GetRField`,
`ForEachObject`, `FInGroup`, `NextObj`, `HCenter`, `GetBBox`, `GetTypeN`,
`GetLayer`, `GetLName`, `Layer`, `ActLayer`, `DelObject`, `ResetObject`,
`NameUndoEvent`, `AlrtDialog`, `Message`, `ClrMessage`,
`SetVPClassVisibility`. `getattr`-guarded because unindexed-but-live:
`DT_IsValid`.

### Untested — read this before running

Nothing below was executed; Vectorworks was closed after the crash.

1. **Anchor positions.** The primary anchor walks the Circuit PIO for
   `CC-Circuit-Connector` sub-objects and takes the first two. It is guarded:
   any point falling outside the circuit's own world bbox is rejected (that is
   the symptom of reading the PIO's **local** frame, the hazard
   `CONNECT-MECHANISM.md` records for Device children) and the run falls back to
   bbox-plus-`Orientation`. The DRY_RUN report prints the
   `anchor_methods` histogram so you can see which path actually fired **before
   writing anything**.
2. **`SetPluginStyle` on a freshly created Data Tag.** Signature is indexed;
   behaviour on this PIO is assumed.
3. **`DT_IsValid` arity.** Probed, and a raise is treated as "unknown", not as
   a failed association.
4. **`ForEachObject "(ALL)"` reach.** Does not visit hidden or greyed layers.
   If `circuits_found` is not 220, that is why.
5. **Viewport class visibility.** Off by default (`SET_VIEWPORT_CLASS_VIS`).
   Reported, not changed.

### Five-minute verification

1. Build the two tag styles (TAG STYLE SETUP block at the top of the script).
2. Paste the script into a Resource Manager Python script resource. Run it
   as-is — `DRY_RUN = True`. Nothing is written.
3. Open `~/showcad_datatag_report.json`. Check `circuits_found == 220`,
   `tags_planned == 440`, `errors == 0`, and read `anchor_methods`. If it says
   `connector_loci=220` the geometry path works; if it says `bbox_orient_L=218`
   the fallback is carrying it and the tags will sit at the bbox edges, which
   may still be fine.
4. Set `DRY_RUN = False`, run. Check `tags_verified == tags_created` and
   `tags_rolled_back == 0`.
5. Zoom to one known circuit. Confirm the destination end reads the source
   device and the source end reads the destination socket. Then **Cmd-Z** and
   confirm they all vanish — that proves the whole pass is one undo step before
   you commit to it. Redo, then save.

Reversal at any later point: `REMOVE_ALL = True`, `DRY_RUN = False`. It deletes
only Data Tags on the two `SHOWCAD-EndLabel-*` classes.
