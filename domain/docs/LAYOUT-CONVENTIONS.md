# ConnectCAD schematic layout conventions

_Compiled 2026-09-02. Every number below is **measured** off the client's own
as-built, not guessed. Method and provenance in §0._

---

## 0. Provenance and method

**Primary source (house style — this is the drawing we must look like):**
`/Users/Joseph.Bradley/Downloads/Disguise GX3 FullSize As Built (1).pdf`
— Adlib Audio Ltd, DWG `-ADL-AV-STG-D-O-1200001`, Rev 2 "As Built" 31/10/2024,
drawn by MSP, "GX3 Racks / GX3 Full-Size / Schematic", sheet **A0**, scale **1:1**.

**Secondary source (title-block + revision house style):**
`/Users/Joseph.Bradley/Downloads/ADL-2360-DojaVideo_RackLayouts (1) (1).pdf`
— Adlib, DWG `-ADL-ZZ-ZZZ-D-O-2360001`, Rev `P01` "First Issue" 29/04/2026,
drawn by AJW, sheet **A3**, scale "As Labelled", Client `Doja Cat`, Project No `2360`.

**How the numbers were obtained.** The as-built PDF was parsed with `pypdf`:
the content stream was interpreted (`q/Q/cm/m/l/c/re/S/f`) with the CTM applied,
so every path is in page space; text was captured through `extract_text`'s
visitor with the text matrix, and the *effective* font size recovered as
`Tf_size x |Tm scale|` (the file has a uniform text scale of **0.24**, so a raw
`Tf 25` renders at 6.0 pt). Scratch data lives in the session scratchpad
(`asbuilt.txt`, `pos.txt`, `allpaths.txt`, `boxes.txt`) — regenerate with the
snippet in §9 if you need to re-check anything.

**The decisive finding:** the page is `3370 x 2384 pt` = **1189 x 841 mm = ISO A0
landscape**, and the title block says **1:1**. So every dimension on the page is a
literal drawing dimension. When converted to millimetres, *every* device
rectangle, socket spacing, row pitch and column offset lands on an exact
multiple of **4 mm**. The whole drawing is built on a 4 mm grid.

**And that grid is not an Adlib house preference — it is ConnectCAD's own
documented default.** From "Getting started with ConnectCAD"
(<https://help.designexpress.eu/vwhelp/2025/PL/VW2025_Guide/ConnectCAD/Getting_started_with_ConnectCAD.htm>):

> "A default snap grid setting of 4mm for metric, 1/4" for imperial, is the
> proper snap grid setting when the schematic layers are at a 1:1 scale."

> "Working in millimeters is recommended. If you are working in imperial units,
> in the Units dialog box (File > Document Settings > Units), select Show unit
> mark."

The same page gives a snap-grid table of **4 mm at 1:1 metric, 1/8" or 1/4" at
1:1 imperial**, with proportionally larger settings at reduced scales. So
measuring the as-built and reading the manual converge on the same number: the
module is 4 mm, and it is the layer snap grid.

| measured (pt) | mm | what it is |
|---|---|---|
| 11.34 | **4.0** | socket pitch (the grid unit, `G`) |
| 22.68 | 8.0 | device name band height |
| 56.7 | 20.0 | small block height / IP strip width |
| 68.0 | 24.0 | DA block height, narrow block width |
| 90.7 | 32.0 | panel-connector stub length, medium block width |
| 113.4 | 40.0 | standard block width |
| 124.7 | 44.0 | DA staggered-column x-offset |
| 170.1 | 60.0 | DA row pitch |
| 238.1 | 84.0 | Lightware 16x16 matrix block height |
| 328.8 | 116.0 | disguise GX3 block height |

Throughout this document **`G` = one grid unit**. In the house style `G = 4 mm`.
See §8 for what to do when the target document is in feet-inches.

---

## 1. Signal-flow direction, columns and bands

### 1.1 It is left-to-right, but it is *bands x columns*, not one spine

Sources left, destinations right holds — but the as-built does **not** put
everything on one horizontal line. It uses **horizontal bands by service type**,
and within the video band, **vertical columns by processing stage**. Measured
block positions (mm, block **left edge** and **bottom edge**, page origin
bottom-left):

| device | x | y | w | h | rows |
|---|---|---|---|---|---|
| PDU1 (Canford EMO E612) | 144.6 | 244 | 40 | 48 | 10 |
| UPS (Riello SD3000) | 148.6 | 316 | 32 | 44 | 9 |
| PDU2 (Canford MDU11) | 251.6 | 244 | 32 | 64 | 14 |
| DA01/03/05/07/09/11 | 336.6 | 652/592/532/472/412/351.5 | 40 | 24 | 4 |
| DA02/04/06/08/10/12 | 380.6 | 616/556/496/436/376/316 | 40 | 24 | 4 |
| SW01 / SW02 (Netgear M4350) | 444.6 | 192 / 112 | 24 | 56 | 12 |
| TCIntf01 / 02 (Rosendahl MIF4) | 476.6 | 567.5 / 430.5 | 32 | 20 | 3 |
| GX3 1.1 / GX3 1.2 (disguise) | 652.6 / 651.9 | 556 / 420 | 40 | 116 | 27 |
| MV 1/2 (Craltech 4KCRAFT-12G16) | 652.6 | 300 | 40 | 88 | 20 |
| PC01 (Dell 7010) | 690.0 | 120 | 32 | 32 | 6 |
| KVM Switch (Netgear 5-port PoE) | 714.9 | 185 | 24 | 32 | 6 |
| SPG1 (Ross SPG8260-R2) | 772.6 | 716 | 32 | 44 | 9 |
| KVM3 / KVM4 (Adder XDIP) | 800.6 | 132 / 172 | 40 | 20 | 3 |
| KVM1 / KVM2 (Adder XDIP) | 812.6 | 600 / 464 | 40 | 20 | 3 |
| RTR 1.1 (Lightware MX2-16x16) | 924.6 | 568 | 40 | 84 | 19 |
| RTR 1.2 (BMD VideoHub 12G 10x10) | 924.6 | 488 | 40 | 64 | 14 |
| OGX1 (Ross openGear frame) | 924.6 | 724 | 32 | 28 | 5 |

Read the `y` column and the bands fall straight out:

| band | y (mm) | what lives there | evidence |
|---|---|---|---|
| **R — reference / genlock / sync** | 700 – 790 | `OGX1` (724), `SPG1` (716), `Main CTP.REF In` xref (752) | top strip, spans the full width, above everything |
| **V — video spine** | 300 – 690 | DAs, servers, matrix, routers, KVM extenders | the main body |
| **M — monitoring / audio / control** | 100 – 290 | `MV 1/2` (300, at the very bottom of V), `PC01`, `KVM Switch`, `KVM3/4` | below the spine |
| **N — network** | 100 – 250 | `SW01` (192), `SW02` (112), `Network Panel` xrefs | bottom-left-of-centre, **completely off the video path** |
| **P — power** | 244 – 360 | `PDU1`, `PDU2`, `UPS` | bottom-**left corner**, its own island |

Power and network are physically segregated: the PDUs/UPS occupy `x 144–284`,
the switches `x 444–468`, and **not one video circuit is drawn through either
region.** Reference is a top band. This is the anti-spaghetti mechanism: a
service that touches every device is given its own band and reached by
cross-reference (§3), never by a line into the video spine.

### 1.2 The matrix is the hub, and the sheet is organised around it

For our rig the chain is `capture -> servers -> Lightware HDMI matrix -> SX40 ->
LED`, and the multiviewer takes matrix **outputs** and returns into matrix
**inputs**. That backward edge is the whole layout problem.

**The as-built already solves it and we copy the solution exactly.** In the
as-built, `MV 1/2` sits at `x = 652.6, y = 300` — the *same column as the
servers*, in the band *below* them — and both of its router connections are
text cross-references, not lines:

* MV inputs: `Main CTP.MV_IN13`, `.MV_IN14`, `.MV_IN15`, `.MV_IN16`
  (measured at `x = 506.7 mm`, on the MV's input side).
* MV outputs going back into the router: `Main CTP.Matrix In09`,
  `Main CTP.Matrix In10` (measured at `x = 889.9 mm`, i.e. sitting on the
  **input side of `RTR 1.2` at `x = 924.6`**).

So the return path appears twice as *text*, once at each end, and **zero lines
are drawn right-to-left across the sheet.** Same for `SDI Loop01..12` on
`Main CTP` with `<-- BNC` markers: loop-throughs are cross-references.

**Rule: the matrix goes in the horizontal middle of the video band. Everything
that feeds it is to its left. Everything it feeds is to its right. Anything that
feeds it *from* its right (multiviewer returns, loop-backs, confidence feeds)
drops into the band below and is expressed as a cross-reference.**

### 1.3 Where power, network and reference attach

* **Power** — every device carries its own `PWR_IN` / `DC_IN` sockets as the
  *last* rows of its block, and those are cross-referenced to the PDU band
  (`PDU1`, `PDU2`, `UPS`). The as-built even labels the *cable make-up* on the
  PDU outputs: `Serv01 (IEC to True1)`, `RTR02 (IEC to IEC)`,
  `PC01 (IEC to DC)`, `SW01 (IEC to IEC)`, `UPS BYPASS`. Power circuits are
  drawn only *inside* the power band; the connection to the device is a label.
* **Network** — `LAN` / `MGMT` sockets sit in the middle of each device block
  and cross-reference to `Network Panel.<way>` (`d3 Net01`, `d3 Net04`,
  `ARTNet01/02`, `MEDIA01/02`, `Trunk01..04`). Fibre trunks are labelled with the
  optic (`1310nm`, `850nm`) and the connector (`LCDUP`), never drawn across the sheet.
* **Reference / genlock** — `SPG1` sits in the top band and *does* have real
  drawn circuits down into the video band, because it is a one-to-many fan-out
  from a single column. Its input is a cross-reference (`Main CTP.REF In`).

---

## 2. Device block anatomy

### 2.1 Geometry (exact, measured on `DA01`)

```
                          <- w ->
        +---------------------------------+  ^  8 mm  name band (CC-Device-Name)
        |  DA01              <- 3.7 mm    |  |         name baseline  = top + 4.3
        |  Ross Video_SRA-8901-4  2.2 mm  |  v         model baseline = top + 1.0
  ======+=================================+ === block top
        | /24 IP |                        |  ^  4 mm  IP strip, 20 mm x 4 mm, top-LEFT
        +--------+                        |  |
   --->o 12G-SDI_IN      12G-SDI_OUT 1 o---- |  <- first socket row = top - 8 mm (2G)
        |                12G-SDI_OUT 2 o---- |  <- every 4 mm (1G) thereafter
        |                12G-SDI_OUT 3 o---- |
        |                12G-SDI_OUT 4 o---- |  <- last socket row = bottom + 4 mm (1G)
        +---------------------------------+ === block bottom
```

Verified values:

| element | value | source measurement |
|---|---|---|
| block fill+stroke rect | `40 x 24 mm` for DA01 | `f/S 954.2 1848.1 113.4x68.0 pt` |
| name band | `w x 8 mm`, sits **above** the block | `re 954.2 1916.2 113.4x22.7 pt` |
| IP strip | `20 x 4 mm`, top-left **inside** the block | `re 954.2 1904.8 56.7x11.3 pt` |
| socket pitch | **4.0 mm** | baselines 1891.6 / 1880.2 / 1868.9 / 1857.5 pt, Δ = 11.34 pt |
| first socket centre | block top − **8 mm** (2G) | 1916.1 − 1893.5 = 22.6 pt |
| last socket centre | block bottom + **4 mm** (1G) | 1859.5 − 1848.1 = 11.4 pt |
| socket arrowhead | `0.74 x 1.5 mm` filled triangle on the block edge | `f 954.2 1891.4 2.1x4.3 pt` |

**Height formula — this is the one a script needs:**

```
block_height_mm = 4 * n_socket_rows + 8          (= G*(n+2))
```

Checks against every measured block: DA 4 rows → 24 ✔ ; `SPG1` 9 rows
(`REF_IN` + `REF1_OUT A..REF4_OUT B` + `WC_OUT`) → 44 ✔ ; `SW01` 12 rows → 56 ✔ ;
`RTR 1.1` 19 rows (16 HDMI + LAN + PWR_IN 1 + PWR_IN 2) → 84 ✔ ;
`MV 1/2` 20 rows → 88 ✔ ; `GX3` 27 rows → 116 ✔ .

**Width** is one of three values, chosen by the longest socket label:

| w | used by | longest label |
|---|---|---|
| 24 mm | `SW01/02` (`LAN 1`), `KVM Switch` (`LAN 5`) | ≤ 6 chars |
| 32 mm | `SPG1` (`REF1_OUT A`), `UPS`, `PDU2`, `TCIntf`, `PC01`, `OGX1` | ≤ 10 chars |
| 40 mm | `DA` (`12G-SDI_OUT 1`), `GX3`, `MV`, `RTR`, `KVM1-4`, `PDU1` | > 10 chars |

Rule for the script: `w = 24 if maxlen <= 6 else 32 if maxlen <= 10 else 40`.

### 2.2 Inputs left, outputs right — **on the same row**

This is the single most important block fact and it is what keeps a 16x16 matrix
to 84 mm instead of 148 mm.

`RTR 1.1` (Lightware MX2-16x16-HDMI20-R): input `HDMI_2.0 1` at `x = 2626.6 pt`
and output `HDMI_2.0 1` at `x = 2696.8 pt` share the **identical baseline
`y = 1823.5`**. All sixteen pairs do. A 16-in / 16-out matrix is therefore
**16 rows, not 32**, and the device is a single block — **it is not split, not
stacked, and not pushed to a panel.**

Same on `DA01`: `12G-SDI_IN` and `12G-SDI_OUT 1` are on one row (they even
extract as one text run, `"12G-SDI_IN 12G-SDI_OUT 1"`).

```
rows = max(count_in, count_out)  per signal group, summed over groups
```

### 2.3 Text sizes (effective rendered size, mm)

| element | pt | mm | notes |
|---|---|---|---|
| Device **Name** | 10.56 | **3.7** | bold-weight position, band centre |
| `Make_Model` | 6.24 | **2.2** | underscore-joined, e.g. `Ross Video_SRA-8901-4` |
| Socket name | 6.00 | **2.1** | inside the block |
| Connector-on-cable + `-->` / `<--` | 5.04 | **1.8** | outside the block, on the stub |
| Panel cross-reference label | 6.24 | **2.2** | outside the block |
| `/24` + `IP` annotation | 5.04 / 3.84 | 1.8 / 1.35 | in the IP strip |
| Legend signal names | 9.84 | 3.5 | right-hand strip |

### 2.4 Socket ordering inside a block

**By signal-type group, then by the manufacturer's own physical port numbering
within the group. Power is always last.** Verified order on `GX3`:

```
12G/3G-SDI_IN A..L (12)  ->  MGMT, LAN A..E (6)  ->  LINE_IN L/R, ADAT_IN,
MIDI_IN (4)  ->  REF_IN  ->  USB 1..3  ->  PWR_IN
```

on `MV 1/2`: `12G-SDI_IN 1..16 -> HDMI1.4_OUT -> LTC_IN -> LAN -> DC_IN 1/2`;
on `RTR 1.1`: `HDMI_2.0 1..16 -> LAN -> PWR_IN 1/2`.

Canonical group order for the script:

```
video -> audio -> network -> reference/sync -> control (USB/serial/GPI) -> power
```

Note the labels keep the vendor's own naming (`LAN A..E`, `SDI_IN A..L`,
`VFC Slot 1..3`) — do **not** renumber to 1..n. That is what makes the drawing
usable by a tech standing behind the rack.

### 2.5 openGear frames: frame block + one block per card

The as-built draws `OGX1` (`Ross Video_Opengear Frame`, 32 x 28 mm) with only
**frame-level services**: `REF1_IN`, `REF2_IN`, `LAN`. Every card in it —
`DA01`..`DA12` (`Ross Video_SRA-8901-4`) and `SPG1` (`Ross Video_SPG8260-R2`) —
is a **separate device block** with its own signal sockets, placed away from the
frame in the band where its signal belongs.

**Rule: draw the frame as its own small block carrying reference/network/power
only; draw each card as its own device block, with `loc_rack` / `loc_rackU` /
`loc_slot` set to tie it back to the frame.** Reasons, in order:

1. Circuits terminate on **card** sockets. A circuit cannot land on a frame.
2. An OGX with 12 DAs + MV + SPG would be ~70 socket rows → a 288 mm block, more
   than half the video band, and it would have to sit in one column while its
   cards belong in four different columns.
3. The rack elevation (`ADL-2360` PDF) is where frame-and-slot is expressed;
   the schematic expresses signal. Keeping them separate is the point.

---

## 3. Patch panels as first-class devices, and the cross-reference idiom

### 3.1 What a terminal panel looks like

The as-built has five: `Main CTP`, `Audio Panel`, `KVM Panel`, `Network Panel`,
`Internal Server Patch`. They are ConnectCAD **terminal panel** objects, and
they carry rack location — `Internal Server Patch` displays `FullSize` / `8`,
`Audio Panel` displays `19`. The legend on the sheet spells out the anatomy:

```
Combined Terminal Panel        Uncombined Terminal Panel
  Term Panel ID.Way              Term Panel ID
  Rack  U                        Rack  U

Panel Connector                Uncombined Panel Connector: Input / Output
  Left Side : External           Left Side : Internal
  Right Side: Internal           Right Side: External
  Panel.Way   CNUM   -->/<--
```

Measured geometry of a panel connector (`Main CTP` on `RTR 1.1` outputs):

| element | value |
|---|---|
| stub line | `S 2734.3 1825.5 -> 2825.1 1825.5` = **32.0 mm (8G)** long, horizontal |
| way pitch | **4.0 mm (1G)** — identical to socket pitch, ways align 1:1 with rows |
| arrowheads | one at the device edge, one at the panel terminus |
| way-name text | right-aligned just inside the panel terminus, 2.1 mm |
| connector + direction text | just outside the device edge, 1.8 mm, e.g. `HDMI -->` |

Panels are placed in **their own x-column**; every stub in that column runs to
the same terminus `x`. On the DA input side the panel column is at `x = 322 mm`
and the stubs are whatever length reaches it (`DA01` 14.6 mm, `DA02` 59.6 mm) —
so **the panel column x is fixed and the stub length floats.**

### 3.2 The cross-reference label — exact idiom

Where the far end is *not* on this sheet-region, ConnectCAD prints a text
cross-reference instead of a line. The format, verbatim from the as-built:

```
<Panel Name>.<Way Name>
```

Every instance found, with its measured x (mm):

| label | x | what it stands in for |
|---|---|---|
| `Main CTP.Matrix In09` / `.Matrix In10` | 889.9 | MV outputs returning into router inputs |
| `Main CTP.MV_IN13` .. `.MV_IN16` | 506.7 | CTP feeds into the multiviewer |
| `Main CTP.REF In` | 727.5 | house reference arriving at `SPG1` |
| `Network Panel.d3 Net01` | 501.8 | server NIC to network panel |
| `Network Panel.ARTNet01`, `.MEDIA01` | 501.1 | control/media VLANs |
| `KVM Panel.UPS AUX01` / `AUX02` | 198.0 | UPS aux contacts to KVM panel |
| `KVM Panel.Ctrl PC01` .. `.Ctrl PC04` | 770.0 | control PC KVM ways |

Bare direction markers appear where the panel is already named by the adjacent
terminal-panel object: `HDMI -->`, `BNC -->`, `<-- BNC`, `<-- XLR3F`,
`<-- LCDUP`, `RJ45 -->`, `LCDUP-->`, `XLR3M -->`.

**Where the label sits — measured, and it is not next to the block.** The
cross-reference text is placed at the *far end of a short stub*, in the
panel/xref column, exactly where the terminal-panel object would have been:

* `Main CTP.Matrix In09/10` at `x = 889.9`, `RTR 1.2` left edge `x = 924.6`
  → **34.7 mm out**, i.e. one `PANEL_STUB` (32 mm) plus the arrowhead.
* `Main CTP.MV_IN13..16` at `x = 506.7`, `MV 1/2` left edge `x = 652.6`
  → **146 mm out**, because the as-built parks them in a **shared cross-reference
  column** at `x ≈ 497..527` together with `Network Panel.d3 Net01`,
  `.ARTNet01`, `.MEDIA01` (all at `x ≈ 501`) and `KVM Panel` (`x ≈ 1441 pt`).

So: **default the xref label to 32 mm out from the block edge; where several
devices in a column share the same panel, align all their labels to one shared
xref column x and let the stubs float** — the same rule as real panel columns
(§3.1). A column of aligned `Panel.Way` labels reads as a list; scattered ones
read as noise.

**Reading convention (verified against every instance):**
* `-->` on the **right** of a block = signal **leaves** here and continues at the
  named way. Text sits to the right of the output socket.
* `<--` on the **left** of a block = signal **arrives** here from the named way.
  Text sits to the left of the input socket.
* The *same* `Panel.Way` string appears at both ends. That string is the join.
* The panel object itself is drawn **once**, in its own column; every other
  appearance is text.

### 3.3 THE RULE — direct line vs cross-reference

Draw a **line** only when *all* of these hold:

1. **Direction is strictly left-to-right.** `x_dst_left > x_src_right`.
2. **Same band.** Source and destination are in the same horizontal band (§1.1).
3. **Span ≤ 250 mm.** The longest real drawn circuit measured in the as-built is
   the DA-bank → GX3 run at `1067.6 -> 1849.9 pt` = **276 mm**, using a
   17-to-36-vertex orthogonal route. 250 mm is a safe working ceiling.
4. **No device block lies in the straight corridor** between them.
5. **The pair crosses at most two column gutters.**

Otherwise use a **panel cross-reference**. Concretely, that means these are
*always* cross-references, never lines:

* **Any right-to-left edge.** Multiviewer returns, matrix loop-backs,
  confidence feeds, `SDI Loop01..12`. **No line on this drawing ever runs
  right-to-left.** This is the rule that saves the sheet.
* **Any band-crossing edge.** video↔network, video↔power, video↔audio.
  So: every `PWR_IN`, every `LAN`/`MGMT`, every Dante port.
* **Anything leaving the sheet.** FOH, stage, LED panels, house reference.
  For our rig this is specifically the **AJA FiDO TX → FOH** runs and the
  **fibre switch trunks** — both become `Network Panel.Trunk0n` /
  `Main CTP.FOH0n` at the rack end and nothing is drawn.
* **Any span > 250 mm.**

When you cross-reference, you must emit **three** things:
1. the cross-reference text at the source socket: `<Panel>.<Way> -->`
2. the cross-reference text at the destination socket: `<-- <Panel>.<Way>`
3. a real `Circuit` object for each leg (device↔panel-way), so the cable
   schedule still contains two cable records with correct `Src_*` / `Dst_*`.
   **The cross-reference is a drafting device, not a data shortcut** — the
   circuits must exist or the schedule is wrong.

---

## 4. Circuit numbering, Signal / Cable Type, and the cable schedule

### 4.1 What the as-built actually prints

**No circuit numbers are printed on the schematic.** A regex sweep for numeric
labels over all 1113 text runs returns only device names (`DA01`, `SW02`) and
socket names (`DVI-1`, `SDI-2`). The legend reserves a `CNUM` slot on the panel
connector symbols, so the field exists and is simply not displayed —
`Circuit."Number Display"` is off. What *is* printed next to every socket is the
**connector on the cable** plus a direction arrow: `BNC`, `MICROBNC`, `HDMI`,
`DVI`, `XLR3F`, `XLR3M`, `USB-A`, `USB-B`, `EC5e`, `EC6A`, `RJ45`, `LCDUP`,
`850nm`, `1310nm`, `MTP-12`, `Cu`, `IEC`, `C13`, `C14`, `C19`, `C20`,
`NAC3FX-W-TOP`.

The **Signal** vocabulary is the sheet legend, bottom-right, one colour per
signal — this is the drawing's signal table, 16 entries plus a catch-all:

```
???   12G-SDI   3G-SDI   ADAT   DP   DVI   HDMI1.4   HDMI2.0   LAN
LINE   LTC   MIDI   MMF   PWR   REF   USB
```

Circuits are classed and coloured by signal (`CC-Circuit-Signal-<SIG>`, see §5),
which is how a reader follows a path without needing numbers.

### 4.2 Where the data lives (verified live, VW 31.7.0)

From `domain/docs/records/connectcad-records-VW2026.md` — dumped from a live
document, not guessed:

* `Circuit` record, **CamelCase** fields: `Number`, `"Number Display"`, `Cable`,
  `Signal`, `"Cable Type"`, `"Cable Outside Diameter"`, `CableLength`,
  `CableCalculatedLength`, `CircuitType`, `Label`, `ShowEnd`, `Orientation`.
* **Both endpoints are denormalised onto the circuit**: `Src_Dev_Name`,
  `Src_Dev_Tag`, `Src_Skt_Name`, `Src_Skt_Tag`, `Src_Signal`, `Src_Skt_Conn`,
  `Src_Room`, `Src_Rack`, `Src_RackU`, `Src_Slot` — and the matching `Dst_*` set.
* `Socket` record, **lowercase** fields: `type` (this is the direction),
  `name`, `tag`, `signal`, `connector`, `n_circuits`, `cablenum`.
* `Device` record, **lowercase**: `name`, `make`, `model`, `width`, `height`,
  `depth`, `heightU`, `loc_room`, `loc_rack`, `loc_rackU`, `loc_slot`,
  `modular`, `nslots`, `__gridScale`, `__PanelPrefix`.

Note `Device.width` / `Device.height` are the §2.1 numbers, and `__gridScale` is
the ConnectCAD grid — the `G` of this document.

### 4.3 Numbering scheme to use

Vectorworks' `Number Cables` command "labels any non-labeled circuits in the
layer according to the cable numbering system set in the ConnectCAD settings",
applying numbering **rules** in order until one matches
(<https://app-help.vectorworks.net/2021/eng/VW2021_Guide/ConnectCAD/Numbering_circuits.htm>).
Rules match on signal/type, so the house-compatible scheme is:

```
<SIGNAL-PREFIX><nnn>        e.g.  SDI001, HDMI001, LAN001, PWR001, REF001
```

one sequence per signal prefix, numbered **per design layer** in stacking order,
left-to-right then top-to-bottom. Keep `"Number Display"` **off** on the
schematic (house style) but populate `Number` so the schedule has a key.

On the worksheet path (§6.0) stacking order is set by the order of rows in the
connection list, so sort it by `(src.col, src.row, src socket index)` and
`Number Cables` produces house order for free.

### 4.4 Cable schedule

Derive it as a worksheet report over the `Circuit` record — every column below is
a real field, no joins needed:

| schedule column | field |
|---|---|
| Cable no. | `Number` |
| Signal | `Signal` |
| Cable type | `"Cable Type"` |
| OD | `"Cable Outside Diameter"` |
| Length | `CableLength` / `CableCalculatedLength` |
| From device / socket | `Src_Dev_Name` / `Src_Skt_Name` |
| From connector | `Src_Skt_Conn` |
| From rack / U | `Src_Rack` / `Src_RackU` |
| To device / socket | `Dst_Dev_Name` / `Dst_Skt_Name` |
| To connector | `Dst_Skt_Conn` |
| To rack / U | `Dst_Rack` / `Dst_RackU` |

Because both endpoints are on the circuit, the schedule is a flat one-pass read —
no `CC_GetCircuitSource` / `CC_GetCircuitDest` calls needed.
Value lists for the three fields come from the ConnectCAD data tables and are
readable via `CC_GetSignalData(sig, col)` (1=Prefix, 2=Connector, 3=Description),
`CC_GetCableTypeData(ct, col)` (1=Description, 2=OD) and
`CC_GetConnectorData(cn, col)` (1=Description, 2=Panel symbol)
(<https://www.vectorworks.co.jp/develop/ScriptReference/Pages/ConnectCAD.html>).

---

## 5. Sheet setup, classes, layers

### 5.1 Sheet

| property | value | source |
|---|---|---|
| sheet size | **ISO A0 landscape, 1189 x 841 mm** | page mediabox `3370 x 2384 pt` |
| scale | **1:1** | title block |
| border inset | **20 mm left, 10 mm top / right / bottom** | frame path `56.6, 28.4, 3285.4 x 2327.2 pt` |
| title block | bottom-right, `x ≈ 1020..1179`, `y ≈ 10..145` | `re 3013.0 101.9 329x76 pt` |
| legend | right strip, `x ≈ 1099..1143`, `y ≈ 496..645` | `f/S 3116.2 1406.9 124.7x422.4 pt` |
| usable schematic area | **x 20 .. 1015 mm, y 15 .. 825 mm** (995 x 810) | content extent x 144.6..997, y 108..760 |

Title block fields, verbatim from the as-built: `Rev | Date | Comment | By`,
`Notes:`, `Project:`, `Client:`, `Client Series:`, `Title:`, `Drawn by:`,
`Date:`, `Scale:`, `Revision:`, `Project No:`, `DWG:`, `XREF:`, sheet-size cell
(`A0`), sheet-ID cell (`S0`), and the fixed Adlib IP/H&S paragraph. Revision
history is a table of `Rev / Date / Comment / By` rows —
`1 | 23/05/2024 | First Revision | ADB` then `2 | 31/10/2024 | As Built | MSP`.
The rack-layout PDF shows the pre-issue convention: revisions are `P01`, `P02`…
while in progress (`P01 | 29/04/2026 | First Issue | AJW`) and switch to integers
at issue. DWG numbers are `-<ORG>-<DISC>-<AREA>-D-O-<nnnnnnn>`
(`-ADL-AV-STG-D-O-1200001`, `-ADL-ZZ-ZZZ-D-O-2360001`), sheet ID `S0` / `S1`.

### 5.2 Classes

Verbatim from "Getting started with ConnectCAD"
(<https://help.designexpress.eu/vwhelp/2025/PL/VW2025_Guide/ConnectCAD/Getting_started_with_ConnectCAD.htm>):

> "ConnectCAD class names have a CC- prefix and indicate the object, its part or
> function, and type; for example, CC-Circuit-Signal-HDV."

> "You can add classes using the CC-<object>-<part or function>-<type> naming
> convention."

> "All ConnectCAD objects support the use of class text styles, which override
> default text attributes."

That last line matters for §2.3: **do not set the text sizes per object — set
them once as class text styles** on the relevant `CC-*` classes, and every device
and circuit inherits them.

**Do not invent class names.** Start from the ConnectCAD template so the shipped
`CC-*` classes exist, then add one `CC-Circuit-Signal-<SIG>` per legend entry:

```
CC-Circuit-Signal-12G-SDI    CC-Circuit-Signal-3G-SDI    CC-Circuit-Signal-ADAT
CC-Circuit-Signal-DP         CC-Circuit-Signal-DVI       CC-Circuit-Signal-HDMI1.4
CC-Circuit-Signal-HDMI2.0    CC-Circuit-Signal-LAN       CC-Circuit-Signal-LINE
CC-Circuit-Signal-LTC        CC-Circuit-Signal-MIDI      CC-Circuit-Signal-MMF
CC-Circuit-Signal-PWR        CC-Circuit-Signal-REF       CC-Circuit-Signal-USB
```

Each carries the legend colour; that is what the legend block documents. For our
rig add `CC-Circuit-Signal-10G` (SX40 → LED) and `CC-Circuit-Signal-DANTE`.

**Startup order for the script:** enumerate the classes actually present with
`ForEachObject` / the class list *before* creating anything, and only create a
class if it is missing. Log any `CC-*` class the template provides that this doc
does not list — the template is authoritative, this list is derived.

### 5.3 Layers

**Start from the ConnectCAD template.** It "comes in metric and imperial
versions with pre-configured settings" and includes "three design layers and
three sheet layers for use with schematic diagrams and rack layouts"
(<https://help.designexpress.eu/vwhelp/2025/PL/VW2025_Guide/ConnectCAD/Getting_started_with_ConnectCAD.htm>).
Take the **metric** template — that is what puts the 4 mm snap grid, the `CC-*`
classes and the 1:1 schematic layers in place for free, and it is what makes our
output match the client's package.

Beyond that: one **design layer per schematic sheet at 1:1**, plus a sheet layer
carrying the viewport, border and title block. The as-built's 1:1 title block
confirms the schematic design layer is unscaled. Cable numbering is per-layer
(`Number Cables` acts "in the layer"), which is another reason one layer = one
sheet.

---

## 6. THE PLACEMENT SPEC (numeric, executable)

All values in **mm**, on the A0 sheet, origin **bottom-left of the page**,
**y grows up** (matching the MCP bridge's coordinate convention). Every value is
a multiple of the module `G = 4 mm`, which is ConnectCAD's own documented snap
grid at 1:1 (§0). See §8 for the feet-inches variant.

### 6.0 Express the layout as ORDINALS first, coordinates second

Circuits cannot currently be bound from script: the bridge dispatches from a
modal dialog callback, where Vectorworks does not run the parametric engine, so
ConnectCAD's own bind never fires. The build therefore goes through ConnectCAD's
supported bulk path — a BoM worksheet driving **Create Devices From BoM**, and a
connection worksheet driving **Make Connections from List**. On that path
**ConnectCAD may place the devices itself**, and our x/y never gets applied.

So the spec below is written twice. The ordinals are the contract; the
coordinates are the preferred realisation of it.

Every device carries three ordinals:

```python
device.band  # 0=R reference/sync  1=V video spine  2=M monitoring/audio
             # 3=N network/fibre   4=P power            -> vertical zone
device.col   # 0..6, the signal stage                   -> left-to-right order
device.row   # 0..n within (band, col)                  -> top-to-bottom order
sort_key = (band, col, row)
```

**What we still control on the worksheet path, and how to use it:**

| lever | how to set it | what it buys |
|---|---|---|
| BoM row order | sort BoM rows by `(band, col, row)` | auto-layout consumes rows in order, so devices come out **grouped by service and ordered by signal stage** even when the coordinates are not ours |
| Connection-list row order | sort by `(src.col, src.row, src socket index)` | `Number Cables` then runs left-to-right, top-to-bottom — the house numbering order (§4.3) |
| Layer snap grid | set once to **4 mm** at 1:1 | anything ConnectCAD auto-places lands on the same module as anything we place, so a later manual nudge stays aligned |
| Device `width` / `height` | write them into the BoM (§2.1 formulae) | block proportions survive regardless of who positions the block |
| Class assignment | `CC-Circuit-Signal-<SIG>` per circuit row | signal colour survives, which is how the drawing is read (§4.1) |
| Terminal panels + `Panel.Way` strings | authored in the connection list | the cross-reference topology (§3) is data, not geometry — it cannot be destroyed by auto-layout |

**The consequence to internalise:** everything in §3 (cross-references) and §4
(signal/cable/numbering) is *data* and survives auto-layout intact. Only §6.3 /
§6.4 (absolute x/y) is at risk. That is the right split — the anti-spaghetti
mechanism is the cross-reference rule, not the coordinates.

**Column ordinals are derived from the netlist, not chosen by hand.** Take
`domain/devices/netlist.json`, build the directed graph over the 58 circuits,
drop the edges the §3.3 rule marks as cross-references (they are not spine
edges), and longest-path from the sources. That yields, for this rig:

| col | stage | instances | why |
|---|---|---|---|
| 0 | off-sheet capture | `Main CTP` ways | DA inputs are off-sheet |
| 1 | capture fan-out + feeders | `DA 1..3`, `MIF4 1..3`, `AVN-AIO8R` | `DA n -> SRV *`, `MIF4 n -> SRV *`, `AVN -> SRV *` |
| 2 | **servers** | `SRV DIR`, `SRV ACT`, `SRV UND` | fed by col 1, feeds `RTR 1` |
| 3 | **matrix (hub)** + monitoring | `RTR 1`, `MV 1` | `SRV * -> RTR 1`; `RTR 1 -> MV 1` |
| 4 | processing + conversion | `SX40 1..3`, `HA5 1..3` | `RTR 1 -> SX40 n`, `RTR 1 -> HA5 1` |
| 5 | distribution + fibre out | `XD 1..2`, `FIDO TX` | `SX40 n -> XD n`, `HA5 1 -> FIDO TX`, `MV 1 -> FIDO TX` |
| 6 | off-sheet LED / FOH | `Main CTP` LED ways | leaves the sheet |

Band 0 (R) holds `SPG 1`, `SR112`, `TR12D` and the `OGX` frames; band 3 (N)
holds `SW01`, `SW02`. Both are reached by cross-reference from the spine, so
their column ordinal only sets left-to-right order within their own band.

### 6.1 Constants

```python
G            = 4.0     # module: socket pitch, panel way pitch, layer snap grid
BLOCK_W      = {'narrow': 24.0, 'medium': 32.0, 'wide': 40.0}
NAME_BAND_H  = 8.0     # above the block
IP_STRIP     = (20.0, 4.0)   # w, h, inside top-left of the block
SOCKET_PITCH = 4.0
TOP_PAD      = 8.0     # block top -> first socket centre
BOT_PAD      = 4.0     # last socket centre -> block bottom
HEIGHT       = lambda n_rows: 4.0 * n_rows + 8.0
WIDTH        = lambda maxlen: 24.0 if maxlen <= 6 else 32.0 if maxlen <= 10 else 40.0

GUTTER       = lambda n, xr: max(72.0, 4.0*n + (32.0 if xr else 0.0))  # see 6.2
GUTTER_STUB  = 40.0    # columns that only receive panel stubs
STAGGER_DX   = 44.0    # x offset of a staggered second card column
STAGGER_DY   = 36.0    # y offset of a staggered second card column
ROW_GAP      = 20.0    # block bottom -> block top below it, in a column.
                       # MEASURED BLOCK-TO-BLOCK, not to the name band: the
                       # 8 mm name band of the lower block sits inside this gap,
                       # so 20 leaves 12 mm of visible clear space.
ROW_GAP_MIN  = 16.0    # absolute floor (measured RTR1.1 -> RTR1.2 = 16 raw,
                       # i.e. 8 mm clear after that block's name band)
COL_GAP_MIN  = 16.0    # min x clear between side-by-side blocks in a band
BAND_GAP     = 10.0    # clear between bands

PANEL_STUB   = 32.0    # device edge -> panel terminus
PANEL_COL_W  = 32.0    # width reserved for a panel terminus column
XREF_STUB    = 32.0    # device edge -> xref label; label sits at the STUB END,
                       # in the panel/xref column - never hard against the block

TEXT_NAME    = 3.7     # set these as CLASS TEXT STYLES (5.2), not per object
TEXT_MODEL   = 2.2
TEXT_SOCKET  = 2.1
TEXT_CONN    = 1.8     # connector-on-cable + --> / <--
TEXT_XREF    = 2.2
TEXT_IP      = 1.35

MAX_LINE_SPAN = 250.0  # beyond this: cross-reference, not a line
```

### 6.2 Gutter width is a circuit budget, not a constant

A gutter must hold one **4 mm vertical lane per circuit crossing it**, plus a
**32 mm strip against the receiving block** when that block also carries
cross-reference labels on that side — the labels live at the *stub end*, not
against the block (§3.2). The as-built proves the lane budget is the binding
constraint: its widest gutter is the DA-bank → GX3 run at
`1192.3 -> 1849.9 pt` = **232 mm**, carrying ~24 circuits. It is not 72 mm
because it could not be.

Counting the real `netlist.json` edges that survive the §3.3 rule as **drawn**
lines:

| gutter | drawn circuits | xref strip | width |
|---|---|---|---|
| col 0 → col 1 | 3 (`Main CTP` → `DA n` inputs, stubs) | — | 72 |
| col 1 → col 2 | **18** — `DA n -> SRV *` (9), `AVN -> SRV *` (6), `MIF4 n -> SRV *` (3) | yes | **104** |
| col 2 → col 3 | 9 — `SRV * -> RTR 1` | yes | 72 |
| col 3 → col 4 | 4 — `RTR 1 -> SX40 n` (3), `RTR 1 -> HA5 1` (1) | yes | 72 |
| col 4 → col 5 | 3 — `SX40 n -> XD n` (2), `HA5 1 -> FIDO TX` (1) | yes | 72 |
| col 5 → col 6 | 8 (`XD n` → LED ways, stubs) | — | 40 |
| within col 3 | 4 — `RTR 1 -> MV 1`, vertical inside the column | — | — |
| within band N | 2 — `SW01 -> SW02` SMF | — | 72 |
| band R fan-down | 6 — `SPG 1 -> SRV *` (3), `SPG 1 -> SX40 n` (3) | — | vertical |

Everything else in the 58 is a cross-reference: `SRV * -> SW01` (3 LAN),
`AVN -> SW01` and `TR12D -> SW01` (Dante), `MV 1 -> RTR 1` (2, right-to-left),
`MV 1 -> FIDO TX` (1 — the straight corridor from col 3 to col 5 passes through
`SX40 3`, so §3.3 rule 4 disqualifies it), and every `PWR`.

### 6.3 Column x-positions

```
col 0    24    panel terminus  - Main CTP capture ways      (terminus line 56)
                 g = 72
col 1   128    DA 1..3 / MIF4 1..3 / AVN-AIO8R    (right 168)
                 g = 104
col 2   272    *** SERVERS ***  SRV DIR/ACT/UND   (right 312)
                 g = 72
col 3   384    *** MATRIX ***  RTR 1, + MV 1      (right 424)
                 g = 72
col 4   496    SX40 1..3, HA5 1..3                (right 536)
                 g = 72
col 5   608    XD 1..2, FIDO TX                   (right 648)
                 g = 40
col 6   688    panel terminus - LED / FOH ways     (terminus line 720)
```

**Content width `24 .. 720` = 696 mm against 995 mm usable — 299 mm spare.**

This is the headline change from my first pass. I had budgeted for a 12-card DA
bank feeding three servers (36 circuits, a 176 mm gutter, a sheet that only just
fitted). The settled rig has **3 DAs, not 12**, and the dense gutter carries
**18 circuits, not 36**. The sheet is now comfortable, and the spare 299 mm is
real headroom — spend it when the LED map lands and the `XD` count grows (it is
a placeholder at 2 in the netlist).

### 6.4 Band y-ranges

```
R  reference / genlock / timecode   y 700 .. 790   (max block 90 tall)
V  video spine                      y 240 .. 690   (450 mm; servers need 436)
M  monitoring + audio               folded into V's per-column slack (see below)
N  network + fibre                  y  90 .. 230
P  power                            y  15 ..  80
```

**Bands are not uniform stripes across the sheet — they are per-column vertical
extents.** The as-built proves it: its DA column runs `y 316..676` while the
switch column two gutters away runs `y 112..248`. Each column is packed
independently, top-down, in band order, with `ROW_GAP = 20` between blocks. So
"band M" is not a reserved stripe; the multiviewer simply occupies the slack
below the matrix in col 3, and the audio I/O the slack below the DAs in col 1.

The tallest column is col 2: `3 x 132 + 2 x 20 = 436 mm`, which is what sets
band V's 450 mm.

### 6.5 Routing rules for the circuits that *are* drawn

* Orthogonal only. Segments horizontal or vertical; bends on the 4 mm grid.
* A circuit leaves an output socket horizontally right for at least `8 mm (2G)`,
  turns once vertically inside the gutter, and enters the input socket
  horizontally from the left for at least `8 mm`. The as-built's DA→GX3 routes
  use 17–36 vertices, so multi-bend is fine; keep the vertical leg inside a
  gutter, never over a block.
* Allocate vertical lanes inside a gutter on a **4 mm** pitch, one per circuit —
  the gutter was sized for exactly that count in §6.2. Assign lanes in
  destination order (topmost destination gets the leftmost lane) so lines never
  cross inside the gutter.
* Never route through band `N` or band `P`.
* **The one sanctioned exception to left-to-right:** reference/genlock
  distribution fans *downward* from band R and may run down-and-left. The
  as-built does exactly this — `SPG1` sits at `x = 772.6` in band R and feeds the
  GX3s at `x = 652`. It is legible because it is a single-source fan-out on its
  own signal class and colour. Bound it: if a reference source must reach more
  than **two** spine columns, cross-reference the further ones. `SPG 1` here
  reaches col 2 and col 4 — exactly two — so all six drops are drawn.

### 6.6 Fit check and the sheet-break rule

Content extent, verified by running every §7 coordinate through a pairwise
overlap check (29 blocks including the 8 mm name band above each):
`x 24 .. 720` (696 mm) by `y 15 .. 780` (765 mm), against a usable area of
`995 x 810`. **Zero overlaps. One A0 at 1:1, with 299 mm horizontal and 45 mm
vertical margin.** The as-built is the density precedent: 32 device blocks + 13
panel groups in `852 x 652 mm`; ours is 26 instances in `696 x 765`.

Vertical is now the tighter axis, and the driver is the **disguise server at 31
socket rows = 132 mm**, three of them stacked. Break to a second sheet when
**either** holds:

* a single column would exceed **810 mm** — i.e. a fourth server in col 2
  (`4 x 132 + 3 x 20 = 588`, still fine) is not the risk; a taller device is.
  Recheck `HEIGHT()` against the library on every run rather than assuming.
* any single gutter would need to be wider than **232 mm** (the as-built's own
  maximum, ~58 lanes) — past that a gutter stops reading as a gutter.

**How to break:** split **by band**, never by column — cutting a column cuts the
signal path. Sheet `S1` = bands R + V (the spine). Sheet `S2` = bands N + P
(network, power). The two join through the *same* terminal panels, because
band-crossing edges are already cross-references (§3.3), so **no drawn circuit is
severed by the split.** Repeat the panel objects on both sheets; the `Panel.Way`
string is the join, exactly as it is within a sheet.

---

## 7. Laying out THIS rig

Source: `domain/devices/library.json` (17 device types, 254 sockets) and
`domain/devices/netlist.json` (26 instances, 58 circuits). Block sizes below are
**computed** from the library with the §2.1 formulae — `rows` groups sockets by
signal and takes `max(n_in, n_out) + n_io` per group, per §2.2.

| instance | type | sockets | rows | w x h | band | col | row |
|---|---|---|---|---|---|---|---|
| `SRV DIR` / `ACT` / `UND` | disguise GX3 | 35 | 31 | **40 x 132** | V | 2 | 0/1/2 |
| `RTR 1` | Lightware MX2-16x16-HDMI20-R | 35 | 19 | **40 x 84** | V | 3 | 0 |
| `SX40 1` / `2` / `3` | Brompton Tessera SX40 | 23 | 20 | 40 x 88 | V | 4 | 0/1/2 |
| `MV 1` | Cobalt 9971-MV6-4H-4K | 22 | 14 | 40 x 64 | V | 3 | 1 |
| `XD 1` / `2` | Brompton Tessera XD | 17 | 14 | 40 x 64 | V | 5 | 0/1 |
| `SR112` | Brainstorm SR-112 | 17 | 16 | 32 x 72 | R | 3 | 0 |
| `TR12D` | Glensound TR-12 (TR12D) | 15 | 14 | 32 x 64 | R | 4 | 0 |
| `SW01` / `SW02` | Netgear M4350-24X4V | 30 | 30 | **32 x 128** | N | 1 | 0/1 |
| `AVN-AIO8R` | Sonifex AVN-AIO8R | 18 | 10 | 32 x 48 | V | 1 | 6 |
| `SPG 1` | Ross SPG8260-R2 | 10 | 9 | 32 x 44 | R | 2 | 0 |
| `HA5 1` / `2` / `3` | AJA OG-HA5-12G | 5 | 5 | 40 x 28 | V | 4 | 3/4/5 |
| `FIDO TX` | AJA FiDO-2T-12G | 5 | 5 | 40 x 28 | V | 5 | 2 |
| `OGX 1..3` | Ross openGear Frame | 5 | 5 | 32 x 28 | R | 1 | 0/1/2 |
| `DA 1` / `2` / `3` | Ross SRA-8901-4 | 5 | 4 | 40 x 24 | V | 1 | 0/1/2 |
| `MIF4 1` / `2` / `3` | Rosendahl MIF 4 | 6 | 4 | 32 x 24 | V | 1 | 3/4/5 |

The two blocks that set the sheet are the **disguise GX3 at 132 mm** (31 rows —
taller than the as-built's 116, because this library carries more of its rear
panel) and the **Netgear M4350-24X4V at 128 mm** (30 rows, 24 LAN + 4 SFP + 2
PSU). Note `RTR 1` at 35 sockets is only **84 mm**, because 16 in and 16 out
share rows (§2.2) — that is the single anatomy rule doing the most work here.

### Column packing (x = block left edge, y = block bottom)

**col 1, `x = 128`** — capture fan-out and feeders
```
DA 1        y 650  (40x24, top 674)
DA 2        y 606  (top 630)
DA 3        y 562  (top 586)
MIF4 1      y 498  (32x24, top 522)
MIF4 2      y 454
MIF4 3      y 410
AVN-AIO8R   y 330  (32x48, top 378)
```
Row gap 20 within a group, 32–40 between groups. Column extent `330 .. 674`.

**col 2, `x = 272`** — servers, the tallest column
```
SRV DIR     y 544  (40x132, top 676)
SRV ACT     y 392  (top 524)   -> 20 mm clear
SRV UND     y 240  (top 372)   -> 20 mm clear
```
Extent `240 .. 676` = 436 mm. This is what band V's 450 mm is sized for.

**col 3, `x = 384`** — the hub
```
RTR 1       y 592  (40x84, top 676)
MV 1        y 508  (40x64, top 572)
```
`RTR 1 -> MV 1` (4x HDMI2.0) is a **vertical** run inside the column — no
gutter needed. `MV 1 -> RTR 1` (2x) is the right-to-left return and is a
cross-reference (below).

**col 4, `x = 496`** — processing and conversion
```
SX40 1      y 588  (40x88, top 676)
SX40 2      y 480  (top 568)
SX40 3      y 372  (top 460)
HA5 1       y 300  (40x28, top 328)   -> 44 mm clear below SX40 3
```
Extent `300 .. 676`. **`HA5 2` and `HA5 3` are not in this column** — they carry
zero circuits in the netlist (only `HA5 1` is patched: `RTR 1 -> HA5 1 -> FIDO
TX`). Draw them as unpatched spares in band N at `x 224 / 272, y 90`. Stacking
all three under the SX40s does not fit: `3x88 + 2x20 + 32 + 3x28 + 2x20 = 460`
against band V's 450.

**col 5, `x = 608`** — distribution and fibre out
```
XD 1        y 612  (40x64, top 676)
XD 2        y 528  (top 592)
FIDO TX     y 300  (40x28, top 328)   -> level with HA5 1, which feeds it
```
The 200 mm gap between `XD 2` and `FIDO TX` is deliberate, not slack to be
closed: it is where the additional XDs go when the LED map lands and the
placeholder count of two grows (`netlist.json._open`).

**band R, `y 700`** — reference, sync, timecode
```
OGX 1/2/3   x 128 / 176 / 224   (32x28)   frames only: REF1/2_IN, LAN, 2x PWR
SPG 1       x 272               (32x44, top 744)
SR112       x 384               (32x72, top 772)
TR12D       x 496               (32x64, top 764)
```

**band N, `y 90`** — network
```
SW01        x 128  (32x128, top 218)
SW02        x 176  (32x128, top 218)
HA5 2       x 224  (40x28,  top 118)   unpatched spare
HA5 3       x 280  (40x28,  top 118)   unpatched spare
```
`SW01 -> SW02` (2x SMF) is a short horizontal run inside band N.

**band P, `y 15`** — power. **Not yet specified.** No PDU or UPS appears in
`library.json` or the 26 netlist instances, and the netlist carries no `PWR`
circuits. Reserve `y 15 .. 80` and place `PDU1` / `PDU2` / `UPS01` at
`x 24 / 72 / 120` once the power devices are added. Every device's `PWR_IN`
cross-references here (§1.3), so nothing in the spine changes when they arrive.

### The two right-to-left edges

These are the only backward edges in the 58, and both are cross-references —
exactly the mechanism §3.3 exists for:

1. **`MV 1 -> RTR 1`, 2x HDMI2.0.** The multiviewer sits *below* the matrix in
   col 3 and returns into it. Emit `Main CTP.Matrix In09` and
   `Main CTP.Matrix In10` at the MV's outputs and again at `x = 348` on `RTR 1`'s
   input side (one 32 mm stub out from the block edge at 384). Two real
   `Circuit` objects per leg so the schedule stays complete. **No line is drawn.**
   This is copied verbatim from the as-built, which resolves the identical
   loop-back the identical way (measured at `x = 889.9` against `RTR 1.2` at
   `x = 924.6`).
2. **`FIDO TX` → FOH.** Leaves the sheet. `FIDO TX` is fed left-to-right by
   `HA5 1` in the adjacent column (drawn) and by `MV 1` two columns back
   (cross-referenced — the corridor is blocked by `SX40 3`). Its fibre pair out
   becomes
   `Main CTP.FOH01` / `.FOH02` with the optic and connector in the
   connector-on-cable field (`1310nm`, `LCDUP`) so they still print at the
   socket — the same idiom the as-built uses for `Trunk01..04` and
   `100G A01/A02`. **Nothing is drawn.**

### Everything else that is cross-referenced, not drawn

`SRV DIR/ACT/UND -> SW01` (3x LAN), `AVN-AIO8R -> SW01` and `TR12D -> SW01`
(Dante) — all band-crossing, all `Network Panel.<way>`. `MV 1 -> FIDO TX`, by
the blocked-corridor rule. Every `PWR_IN`, once the power devices land.

Longest **drawn** span: 104 mm (col 1 → col 2), well inside the 250 mm ceiling
and under half the as-built's 276 mm worst case. **Drawn circuits: 46 of 58.
Cross-referenced: 12.**

### Two library defects the script must not silently draw

* **`sw_m4250_40g8xf` (Netgear M4250-40G8XF-PoE++) has zero sockets.** The
  library flags incompleteness rather than inventing ports — correct, and it must
  not be papered over here. `HEIGHT(0)` returns an 8 mm block with no sockets,
  which is a drafting bug, not a device. **Refuse to place any device with zero
  sockets; emit it to the BoM with a `TBC` note and report it.** It is not among
  the 26 netlist instances, so it does not affect this sheet.
* **`xd` carries `qty: 0` in the library but two instances (`XD 1`, `XD 2`) in
  the netlist**, and the netlist's own `_open` list says the XD count and the
  SX40→LED fan-out are placeholders pending the LED map. Col 5 is sized for two;
  the 299 mm of spare width (§6.3) is where more go.

Also worth carrying forward from `netlist.json._open`: **every port number in
the netlist is ours, not the user's** — paths are stated, socket assignments are
assigned. Circuit endpoints will move when the user confirms; the ordinals in
§6.0 will not, which is another reason to drive the drawing from them.

---

## 8. Units: what to do if the document is feet-inches

The house style is metric at `G = 4 mm`. The repo's live probe document
(`domain/docs/records/probe-20260901T235140.json`) reports a design layer at
**scale 48.0** (1:48 = 1/4" = 1'-0"), i.e. an imperial Spotlight document —
so do **not** assume mm.

**The script must call `get_document_units` first** (`vwx-plugin/commands.py:1307`,
returns `units_per_inch` and `name` from `vs.GetUnits()`), and pick:

| document units | `G` | sheet | consequence |
|---|---|---|---|
| **mm (recommended)** | **4 mm** | **A0 landscape, 1:1** | exact match to the client's package; every §6 number used verbatim |
| inches / feet-inches | **1/8" = 0.125"** | **ARCH E1 (30 x 42") landscape, 1:1** | scale every §6 *geometry* number by `0.125 / (4/25.4) = 0.79375` |

Under the imperial variant the derived constants are:

```
G = 0.125"        socket pitch, panel way pitch
block widths      0.75" / 1.0" / 1.25"          (24 / 32 / 40 mm)
name band         0.25"                          (8 mm)
IP strip          0.625" x 0.125"                (20 x 4 mm)
top pad / bot pad 0.25" / 0.125"
height            0.125 * n_rows + 0.25   inches
gutter            max(2.25", 0.125" * n_circuits)
row pitch         max(1.875", h + 0.625")
row clear min     0.5"
panel stub        1.0"
max line span     7.875"
content extent    21.7" x 23.9"   on a 42 x 30" sheet -> ample room for the
                  title-block/legend strip and 5.5" of vertical margin.  Fits.
```

**Text sizes do not scale with the grid** — keep the §2.3 absolute sizes, except
the socket label, which drops from 2.1 mm to **1.8 mm (0.07", ~5 pt)** to hold
the same 55–65 % fill of a 0.125" row.

`G = 1/4"` is the *primary* imperial default in the ConnectCAD help table, but
at this rig's size it gives a content extent of `43.5" x 48.9"` — taller than
ARCH E is wide. The same table also sanctions **1/8" at 1:1**, which is what
this rig needs. Use 1/8".

Recommendation: **create the ConnectCAD schematic on its own design layer set to
millimetres at 1:1**, independent of the Spotlight layer's imperial 1:48. VW
lets units be a document preference and scale a per-layer property, and matching
the client's own package is worth more than internal unit consistency. If that
is refused, take the 3/16" grid and an ARCH E sheet.

---

## 9. Reproducing the measurements

```python
from pypdf import PdfReader
from pypdf.generic import ContentStream
r  = PdfReader('Disguise GX3 FullSize As Built (1).pdf'); p = r.pages[0]
cs = ContentStream(p.get_contents(), r)
# interpret q/Q/cm to build the CTM, apply it to m/l/c/re operands, flush on S/f;
# for text, use p.extract_text(visitor_text=...) and multiply the Tf size by the
# Tm scale (0.24 in this file) to get the rendered size.
MM = 25.4 / 72          # pt -> mm ; page is 3370x2384 pt == 1189x841 mm == A0
```

---

## 10. Open items

**Resolved since the first pass:**

* ~~Whether the 4 mm grid is ConnectCAD's default or an Adlib preference.~~
  **It is ConnectCAD's own documented default snap grid at 1:1** — see the two
  quotes in §0. Measuring the as-built and reading the manual agree.

**Still open:**

* The literal `CC-*` class list shipped in the ConnectCAD template is not
  published in the online help. §5.2 has the naming convention verbatim and the
  signal-class family; the script must still **enumerate the document's classes
  at startup** rather than assume. Confirm against the metric ConnectCAD
  template file itself.
* `Circuit."Number Display"` — confirm the exact off value on a live document.
* **Auto-layout behaviour is unverified.** §6.0 asserts that *Create Devices
  From BoM* consumes rows in worksheet order. That is the load-bearing
  assumption of the whole ordinal strategy and it has not been tested on a live
  document. Test it early with a throwaway 4-device BoM before building the real
  one — if it does not hold, the ordinals still order the *connection list* and
  therefore the cable numbering, but grouping would have to be recovered by hand.
* **Band P is unpopulated.** No PDU/UPS in `library.json`, no `PWR` circuits in
  `netlist.json`. Coordinates reserved (§7), nothing to place yet.
* **`sw_m4250_40g8xf` has zero sockets** — must be refused by the placement
  script, not drawn as an 8 mm stub (§7).
* **Every port number in `netlist.json` is ours, not the user's** (its own
  `_open` says so). Endpoints will move on confirmation; the §6.0 ordinals will
  not.
* `XD` count and the SX40→LED fan-out are placeholders pending the LED map. Col
  5 is sized for two, and §6.3 has 299 mm of spare width for more.
