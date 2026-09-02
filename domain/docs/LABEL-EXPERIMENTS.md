# Circuit end labels — what is TRUE of the live drawing

Established **live** against the user's real file `DOJA26_SRVR_V1.vwx`
(48 devices, 220 circuits, layer `Schematic`, layer scale 48, VW 2026 /
31.7.0.1), 2026-09-02, via the TCP bridge on 127.0.0.1:9878.

Everything in §1–§6 is a measurement, not an inference. Inference is labelled
as such. Where this contradicts `CONNECTCAD-LABELS-RESEARCH.md` (a
documentation-research doc) or the coordinator's summary, the live measurement
wins and the discrepancy is called out explicitly.

---

## 1. What draws the text at each end — SOLVED, with proof

**The end text is rendered at the two `CC-Circuit-Connector` loci inside the
Circuit plug-in object. The first locus renders `Circuit.Src_Skt_Conn`; the
second renders `Circuit.Dst_Skt_Conn`.**

### 1.1 The Circuit PIO's children

`FInGroup` / `NextObj` on a Circuit PIO is **not** empty. Every one of the 220
circuits has exactly the same four children:

```
text     [None]                        GetText='' , GetTextLength=-1
polyline [CC-Circuit-Signal-<SIGNAL>]  the cable line itself
locus    [CC-Circuit-Connector]        <- source end
locus    [CC-Circuit-Connector]        <- destination end
```

There is **no text object** carrying the connector text. The glyphs are painted
by the compiled ConnectCAD PIO at those loci. This is the plugin's house
pattern, confirmed on three unrelated object families — the socket label symbol
`skt_txt_L` contains only two loci, classed `CC-Socket-DisplayTag` and
`CC-Socket-MultiCircuit`; `dev_label_generic` contains only loci classed
`CC-Device-DisplayTag`, `CC-Device-Description`, `CC-Device-Location`. A locus
on a semantic class *is* a text anchor. The VW2026 help confirms the intent:
"class text styles … the text color is applied to the text objects in the
class."

### 1.2 The proof that those loci carry the connector string

A locus normally has no extent. These have a bbox, and **the width is a
function of the connector string at that end.** Surveyed across all 220
circuits:

| `Src_Skt_Conn` | `Dst_Skt_Conn` | locus widths (src, dst) |
|---|---|---|
| BNC   | BNC   | 0.2350, 0.2350 |
| DP    | DP    | 0.1554, 0.1554 |
| HDMI  | HDMI  | 0.2839, 0.2839 |
| SFP   | SFP   | 0.2166, 0.2166 |
| **DP**    | **HDMI**  | **0.1554, 0.2839** |
| **HDMI**  | **DP**    | **0.2839, 0.1554** |
| XLR3F | XLR3M | 0.3453, 0.3698 |
| `---` | XLR3M | *(only ONE locus, 0.3698)* |

Two things fall straight out:

* **The widths swap when the connectors swap.** The first locus follows the
  source, the second follows the destination. This is a **per-end** render.
* When an end's connector is unset (`---`), that end has **no locus at all** —
  the anchor exists only when there is text to draw.

Then the measurement that closes it. I created real text objects with those six
strings, classed `CC-Circuit-Connector`, measured them, and deleted them
(one named undo event, self-cleaning):

| string | rendered text width | locus width | ratio |
|---|---|---|---|
| DP    | 11.2733 | 0.1554 | 72.54 |
| SFP   | 15.7186 | 0.2166 | 72.57 |
| BNC   | 17.0506 | 0.2350 | 72.56 |
| HDMI  | 20.6014 | 0.2839 | 72.57 |
| XLR3F | 25.0584 | 0.3453 | 72.57 |
| XLR3M | 26.8358 | 0.3698 | 72.57 |

**Constant ratio 72.56 ± 0.02 across six strings of four different lengths**,
and the heights match too (9.12 / 0.1257 = 72.55). Text at 12 pt, font id 33.
That is not a coincidence — the loci *are* the rendered connector text.

This independently confirms the forum answer quoted in
`CONNECTCAD-LABELS-RESEARCH.md` (VW staff, topic 100488) and adds what the
forum did not say: **which field feeds which end.**

### 1.3 The user's own example

`<EXT>.OG DA - 01 -> DIR.SDI_IN 01` has `Src_Skt_Conn='BNC'`,
`Dst_Skt_Conn='BNC'`, and two loci of width 0.2350 each. It is drawing
**"BNC" at both ends**. That is exactly the text the user is frustrated by.

---

## 2. Plug-in regeneration is genuinely blocked — proof

Not an assumption. The decisive test:

```
prior Number=''
set Number='TEST999', no reset : text[None]='' | polyline | locus | locus
after vs.ResetObject(circuit)  : text[None]='' | polyline | locus | locus
readback Number='TEST999'
```

The field write **persisted**. The geometry did **not** change. A single
`ResetObject` is survivable (no `ConnectionResetError` — that hazard is
specific to `SetRField`+`ResetObject` in a long loop), it simply does nothing.

Consequence for this whole workstream: **no configuration can be confirmed
visually from the bridge.** Everything below is either measured from persisted
state or explicitly flagged as unconfirmed.

---

## 3. Class inventory

71 classes. Visibility encoding was determined by round-trip (`vs.SetCVis` does
**not** exist; `vs.HideClass` / `vs.ShowClass` do, and `vs.GrayClass` is
spelled with an `a`):

**`0` = visible, `-1` = hidden.**

All `CC-Circuit-*` and `CC-Socket-*` classes were `0` (visible) when I
surveyed. The only hidden classes in the document were `NonPlot-Loci` and
`CC-Equipment-CTP-Dimension`.

> The coordinator has since run `vs.HideClass('CC-Circuit-Connector')` on the
> live document, so that class is now `-1`.

### 3.1 The counting trap

`vs.Count("(C='CC-Circuit-Connector')")` returns **0.0** — and the class is in
fact populated with 440-ish loci. Criteria searches do not descend into
plug-in objects. **A zero from `Count` is not evidence of an empty class.**
Same trap that previously made `ForEachObject` report 0 sockets.

The `CC-Circuit-Signal-*` counts *are* real, because the Circuit PIO itself
carries the signal class at top level:

```
12G-SDI 80 | ??? 65 | 3GV 52 | HDMI 40 | HDMI2.0 17 | DP 11 | MIC 8 | MIC/LINE 7 | SFP 4
```

`CC-Circuit-Number` and `CC-Circuit-Preview` both exist and are visible, and
neither appears among any circuit's children — consistent with `Number` being
empty on all 220 (§5) and `Preview` being a tool-feedback class.

### 3.2 Viewports have their own class visibility

Two viewports:

| viewport | sheet | `CC-Circuit-Connector` |
|---|---|---|
| `Schematic` | TA1.1 | **visible (0)** |
| `[Drawing Title]` | TA1.3 | hidden (−1) — but so is `CC-Circuit-Signal-HDMI`, so this VP is not showing the schematic at all |

**Hiding the class on the design layer does not change what prints from sheet
TA1.1.** `vs.SetVPClassVisibility(vp,'CC-Circuit-Connector',-1)` is also needed,
and then the viewport needs an update (which the user can do with one click —
I did not force it, per the regeneration hazard).

---

## 4. The arrow formula — token syntax SOLVED, per-end resolution NOT

### 4.1 Token syntax, reconciled

The compiled plug-in contains the format string **`#%s.%s#`** — so a token is
`#<Record>.<Field>#`, hash-delimited, dotted.

The localisation file `cCADCircuitObj.vwstrings` carries a block commented
`// Arrow end circuit params`, which maps internal field names to the labels
the *Insert Field* popup shows:

```
"Src_Dev_Name"  = "Device Name";     "Src_Skt_Name"  = "Socket Name";
"Src_Dev_Tag"   = "Device Tag";      "Src_Skt_Tag"   = "Socket Tag";
"Src_Signal"    = "Socket Signal";   "Src_Skt_Conn"  = "Socket Connector";
"Src_Skt_Circs" = "Socket Circuit(s)";
"Src_Room" "Src_Rack" "Src_RackU" "Src_Slot"
"CircuitLayer"  = "Layer";
```

**This reconciles the two competing findings.** The docs agent's forum-sourced
`#Circuit.Device Tag#` and my binary-sourced `#Record.Field#` are the same
thing: the popup inserts `#Circuit.` + *the display label* + `#`. So the
correct token is `#Circuit.Socket Name#`, **not** `#Circuit.Src_Skt_Name#`.
The `#Circuit.Dst_Dev_Name#` forms set on two circuits earlier today are junk.

### 4.2 Why this is strong evidence for per-end (but not proof)

The arrow Insert Field list contains **only the `Src_*` set, plus
`CircuitLayer`** — there is no `Dst_*` entry anywhere in that block. And every
label is written unqualified: "Device Name", not "Source Device Name".

A formula vocabulary that offers exactly one end, unqualified, only makes sense
if the renderer resolves it against *the other end* at each arrow. Combined
with the help text — "the layer option is useful for arrow circuits", useless
unless it reports the far end's layer — this points hard at per-end.

The counter-case is real and I cannot dismiss it: `__ArrowFormula` is **one**
string field on **one** object. A renderer that interpolates once and stamps
the result at both ends would produce every observation above.

**Status: UNRESOLVED. Do not tell the user it works until it is seen.**

### 4.3 Arrow and bubble are for different circuit types

VW2026 help, *Customizing ConnectCAD objects*, verbatim: "edit the appearance
of **arrow circuits and/or the bubble label of other circuits**."

So on this drawing's 220 non-arrow circuits, `__CustomizeArrow` /
`__ArrowFormula` / `__ArrowStyle` are **inert**. Confirmed by the enum values
recovered from the binary and `DlgCircuitGraphics.vwstrings`:

* `__ArrowStyle`: `0`=None `1`=Arrow `2`=Pill `3`=Feather `4`=Reference `5`=Wireless
* `__BubbleStyle`: `0`=None `1`=Diamond `2`=Rounded `3`=Square

**All 220 circuits have `__ArrowStyle='0'` = None.** Even on an arrow circuit,
a custom arrow with style None would draw nothing. Any arrow experiment must
set `__ArrowStyle` to `1`–`5` as well as `__CustomizeArrow='True'`.

### 4.4 The bubble cannot do what the user wants — reasoning

The bubble is the **circuit number** label, placed by `Number Display`
(Auto/Source/Destination/Both/Mid/None). Its purpose is to stamp *one*
identifier — the circuit number — at one or both ends. Both bubbles show the
same string by design; that is what a circuit number is. Unlike the arrow, its
Insert Field list is the full Circuit record ("default Circuit parameters"),
i.e. both `Src_*` and `Dst_*`, which is only coherent if the tokens resolve
**literally**.

So: arrow = end-relative vocabulary, bubble = literal vocabulary. The bubble
is the wrong lever for "each end names the far end".

---

## 5. Corrections to statements in circulation

| Claim | Live measurement |
|---|---|
| "All 220 circuits are `CircuitType='polyline'`" | **False.** 206 are `rounded`, 14 are `polyline`. **Zero** are `arrow`. The conclusion (no arrow graphics render) still holds. |
| "A Circuit's bbox reads (0,0)-(0,0), children may be absent" | **False in this document.** bboxes are real and all 220 circuits have 4 enumerable children. |
| "`vs.SetCVis`" | Does not exist. Use `vs.HideClass` / `vs.ShowClass`; the grey one is `vs.GrayClass`. |
| "`ShowEnd` is probably inert" | Agreed, and its OIP label in the localisation file is literally the string `ShowEnd` — an unlocalised internal parameter. Setting it True on all 220 looks harmless but pointless; it should be reverted to `False` at some point. |

Other census results:

* `ShowEnd`: 220 × `True` (all set earlier today; original was `False`)
* `__CustomizeBubble`: 220 × `False`; `__BubbleFormula`: all empty
* `Number`: empty on all 220 → **no bubble is currently drawn anywhere**
* `Label`: empty on all 220
* `__SameLayer`: 220 × `True`, all on layer `Schematic` → **every circuit is
  safe to convert to Arrow type and back** (the help's irreversibility warning
  applies only to circuits spanning two layers)
* `Orientation`: 218 × `L`, 2 × `R`
* Records present on top-level objects, enumerated over `(ALL)`: `Circuit`,
  `Device`, `Device-External`, `Device Network Info Record`, `Inventory
  Record`, and four Title Block records. **No data-tag record appears**, which
  is suggestive but not conclusive.
  The direct check — `vs.Count("(PON='Data Tag')")` — was queued in the call
  that died when the bridge dropped, so **the Data Tag question (coordinator's
  item 6) is still open**. Re-run it first thing; note §3.1, a `Count` of 0
  would only rule out *top-level* tags.

### 5.1 The six `Number Display='Destination'` circuits

They are not structurally special and they do **not** demonstrate per-end
behaviour. They are one contiguous block off the same device:

```
<HDMI MATRIX>.HDMI_OUT 02 -> SR RETURNS.HDMI IN
<HDMI MATRIX>.HDMI_OUT 03 -> SL DS FACE.HDMI IN
<HDMI MATRIX>.HDMI_OUT 04 -> SL RETURNS.HDMI IN
<HDMI MATRIX>.HDMI_OUT 05 -> SPARE.HDMI IN
<HDMI MATRIX>.HDMI_OUT 07 -> SR.HDMI IN
<HDMI MATRIX>.HDMI_OUT 08 -> SL.HDMI IN
```

All `Signal=HDMI2.0`, `CircuitType=rounded`, layer `Schematic`, `Number=''`.
Since `Number` is empty, `Number Display` has nothing to place — the setting is
currently inert on all 220 circuits. Almost certainly a leftover from the user
selecting that block in the OIP and trying the popup. Nothing to learn here.

---

## 6. The three options, with honest trade-offs

### Option A — Arrow circuits (the only mechanism *designed* for this)
`CircuitType='arrow'`, `__CustomizeArrow='True'`,
`__ArrowFormula='#Circuit.Device Tag#.#Circuit.Socket Name#'`,
`__ArrowStyle='1'`.

*For:* it is the built-in feature for "name the far end", and the field
vocabulary is built for it. *Against:* an arrow circuit is drawn **instead of**
a connecting line — mass-converting 220 circuits would destroy the schematic.
And per-end is still unproven. Suitable only for the off-sheet / long runs.

### Option B — Repurpose the connector fields (proven per-end channel)
`Src_Skt_Conn := Dst_Skt_Name` and `Dst_Skt_Conn := Src_Skt_Name`.

Because §1.2 proves the first locus renders `Src_Skt_Conn` and the second
renders `Dst_Skt_Conn`, this puts the far end's socket name at each end —
`"SDI_IN 01"` at the OG DA end and `"OG DA - 01"` at the DIR end, exactly the
strings the user asked for — **on the existing rounded lines, with no change to
the drawing's look**. This is the only option whose per-end behaviour is
*measured* rather than hoped for.

Two real costs, and they are not small:
1. These are **denormalised copies of socket data**. ConnectCAD refills them
   from the sockets on reconnect / full rebuild, so the override may not
   survive. Re-runnable, but not stable.
2. They are the **connector-type** fields. Every cable schedule or worksheet
   reading `Src_Skt_Conn` will report socket names instead of `BNC`/`HDMI`.
   For a 220-circuit touring package that is a genuine data-integrity problem.

Implemented, dry-run by default, in `tools/apply_circuit_labels.py`.
**Not run across the 220 — waiting on the user's go-ahead.**

### Option C — Just remove the wrong text (already applied by the coordinator)
`vs.HideClass('CC-Circuit-Connector')`. Needs **no regeneration**, so it works
today despite §2. Reversible with `vs.ShowClass`. Also needs the TA1.1 viewport
setting (§3.2) to affect output.

Note the interaction: **Option C hides the very loci Option B writes into.** If
the user wants Option B, the class must be shown again.

---

## 7. The 30-second test that settles per-end — for a human, in the GUI

The bridge cannot answer it (§2). A human can, in under a minute, and every
circuit in this file is same-layer so it is fully reversible (§5):

1. Select one low-stakes circuit — `<HDMI MATRIX>.HDMI_OUT 05 -> SPARE.HDMI IN`
   is the one I would pick; it terminates in a SPARE.
2. Note its `Circuit Type` in the OIP (`rounded`). Change it to **Arrow**.
3. Right-click → **Edit Circuit Graphics**. Tick *Customize arrow*. Set
   **Arrow Style** to anything but None. Build the formula with *Insert Field*
   → "Device Tag", type `.`, *Insert Field* → "Socket Name".
4. **Read both ends.** Different strings ⇒ per-end, Option A is viable.
   Same string at both ⇒ literal, and Option A is dead for this purpose.
5. Undo, or set `Circuit Type` back to `rounded`.

Also worth 10 seconds: the dialog has a live **Preview** control, and the
*Insert Field* popup itself will show whether it offers one end's fields or
both — which on its own largely settles §4.2.

---

## 8. State I left in the live file — NEEDS CLEANUP

My final cleanup call **did not execute** — the bridge went away
(`ConnectionRefusedError`, and Vectorworks is no longer in the process list)
between writing the script and running it. So the following is still in the
document and someone must revert it:

1. **`<EXT>.OG DA - 01 -> DIR.SDI_IN 01`** — I primed it with Option B as a
   single-circuit trial. It now reads
   `Src_Skt_Conn='SDI_IN 01'`, `Dst_Skt_Conn='OG DA - 01'`.
   **Both were `'BNC'`.** Undo event: *"ShowCAD: prime ONE circuit with far-end
   labels (OG DA - 01 <-> DIR.SDI_IN 01)"*.
2. **Two junk arrow formulas** (set earlier today, before the token syntax was
   known) are still present and should go back to
   `__CustomizeArrow='False'`, `__ArrowFormula=''`:
   * `<HDMI MATRIX>.HDMI_OUT 02 -> SR RETURNS.HDMI IN` — `'#Circuit.Dst_Dev_Name#.#Circuit.Dst_Skt_Name#'`
   * `<HDMI MATRIX>.HDMI_OUT 03 -> SL DS FACE.HDMI IN` — `'#Dst_Dev_Name#.#Dst_Skt_Name#'`
3. `ShowEnd='True'` on all 220 (was `False`) — inert, but not original.
4. `NonPlot` class visibility: I hid it during the encoding round-trip and
   **restored it to `0` in the same session** — verified, nothing outstanding.
5. Six temporary text objects created for the metrology in §1.2 were **deleted
   in the same call**; circuit count verified still 220 afterwards.

Run `python3 tools/apply_circuit_labels.py --cleanup` once the bridge is back;
it reverts items 1 and 2 and reports item 3.

A full pre-change snapshot of all 61 fields × 220 circuits was taken and is at
the path printed by the script's `--apply` run
(`tools/circuit_labels_baseline.json`); an earlier keyed-by-endpoint snapshot
collapsed 2 duplicate src→dst pairs and so has 218 entries — the script's own
baseline is ordinal-keyed and complete.

---

## 9. Method notes for whoever picks this up

* `vs.Count` and `ForEachObject` criteria do **not** descend into PIOs. Walk
  with `FInGroup`/`NextObj`.
* `FInSymDef` gets you inside a symbol *definition*; `FInGroup` on a symbol
  *instance* returns nothing.
* **Locus bbox width is a read channel for PIO-painted text.** When
  regeneration works, this is how to verify a formula's output per end without
  a screenshot: compare the two ends' widths, and calibrate against real text
  objects at 12 pt (ratio 72.56 in this document at layer scale 48).
* `vs.GetTextLength` returns `-1` on the Circuit's `text[None]` child; treat
  that child as a container, not a readable string.
* One `ResetObject` is safe. A loop of `SetRField`+`ResetObject` over many
  objects has reset the bridge — keep batches ≤ 20 and prefer several short
  calls.
