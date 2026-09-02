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
**y grows up** (matching the MCP bridge's coordinate convention). All values are
multiples of `G = 4 mm`. See §8 for the feet-inches variant.

### 6.1 Constants

```python
G            = 4.0     # grid unit == socket pitch == panel way pitch
BLOCK_W      = {'narrow': 24.0, 'medium': 32.0, 'wide': 40.0}
NAME_BAND_H  = 8.0     # above the block
IP_STRIP     = (20.0, 4.0)   # w, h, inside top-left of the block
SOCKET_PITCH = 4.0
TOP_PAD      = 8.0     # block top -> first socket centre
BOT_PAD      = 4.0     # last socket centre -> block bottom
HEIGHT       = lambda n_rows: 4.0 * n_rows + 8.0

GUTTER_MIN   = 72.0    # floor for any gutter that carries circuits
GUTTER       = lambda n, xr: max(72.0, 4.0*n + (32.0 if xr else 0.0))  # see 6.2
GUTTER_STUB  = 32.0    # columns that only receive panel stubs
STAGGER_DX   = 44.0    # x offset of a staggered second card column
STAGGER_DY   = 36.0    # y offset of a staggered second card column
ROW_PITCH    = lambda h: max(60.0, h + 20.0)   # min 60; 20 mm clear between blocks
ROW_CLEAR_MIN= 16.0    # absolute floor (measured RTR1.1 -> RTR1.2)

PANEL_STUB   = 32.0    # device edge -> panel terminus
PANEL_COL_W  = 32.0    # width reserved for a panel terminus column
XREF_STUB    = 32.0    # device edge -> xref label; the label sits at the STUB
                       # END, in the panel/xref column - never hard against the
                       # block.  Widen to reach a shared xref column (see 3.2).

TEXT_NAME    = 3.7     # device name
TEXT_MODEL   = 2.2     # make_model
TEXT_SOCKET  = 2.1     # socket name
TEXT_CONN    = 1.8     # connector-on-cable + --> / <--
TEXT_XREF    = 2.2     # Panel.Way cross-reference
TEXT_IP      = 1.35

MAX_LINE_SPAN = 250.0  # beyond this: cross-reference, not a line
```

### 6.2 Gutter width is a circuit budget, not a constant

A gutter must hold one **4 mm vertical lane per circuit crossing it**, plus a
**32 mm strip against the receiving block** when that block also carries
cross-reference labels on that side — because the labels live at the *stub end*,
not against the block (§3.2). The as-built proves the lane budget is the binding
constraint: its widest gutter is the DA-bank → GX3 run at
`1192.3 -> 1849.9 pt` = **232 mm**, carrying ~24 circuits (two GX3s x 12 SDI
inputs). It is not 72 mm because it could not be.

```python
GUTTER = lambda n, has_xref: max(72.0, 4.0*n + (32.0 if has_xref else 0.0))
```

### 6.3 Column x-positions — and the one hard constraint

Working the budget left to right for this rig:

| gutter | circuits drawn | xref strip | width | resulting column (left edge) |
|---|---|---|---|---|
| CTP terminus (x 56) → C1 | 12 | no | 72 | **C1 = 128** FiDO RX / capture (right 168) |
| C1 → C2 | 12 | no | 72 | **C2 = 240** openGear card col A (right 280) |
| C2 ↔ C3 | — | — | 44 (stagger, not a gutter) | **C3 = 284** card col B (right 324) |
| C3 → C4 | **12** — see below | yes | 80 | **C4 = 404** SERVERS x3 (right 444) |
| C4 → C5 | 24 (panel stubs only) | — | 32 | **C5 = 476** Internal Server Patch |
| C5 → C6 | 24 | yes | 128 | **C6 = 644** *** MATRIX *** + VideoHub (right 684) |
| C6 → C7 | 12 | yes | 80 | **C7 = 764** SX40 x3 (right 804) |
| C7 → C8 | 12 | yes | 80 | **C8 = 884** Tessera XD (right 924) |
| C8 → C9 | 8 (panel stubs only) | — | 40 | **C9 = 964** LED/FOH panel (terminus 996) |

**Content width `24 .. 996` = 972 mm against 995 mm usable — fits, 23 mm spare.**

The matrix lands at **C6 = 644**, the horizontal middle of the drawing area
(20 .. 1015): four columns of sources to its left, three of sinks to its right.
That is exactly what §1.2 requires of a hub.

**The hard constraint, stated plainly.** The `C3 → C4` gutter decides whether
this rig fits on one A0. Drawing **all** 12 DAs into **all three** servers is 36
circuits → `4*36 + 32 = 176 mm`, which pushes C9's terminus to **1020 mm** and
the sheet **does not fit**. So the budget above assumes **12 drawn circuits: the
DA bank feeds `SRV01` with real lines, and its feeds to `SRV02` / `SRV03` go
through `Main CTP` as cross-references.** That is not a fudge — it is the same
decision the as-built makes everywhere else, and it is what keeps the dense
gutter readable. If all 36 must be drawn, the answer is a two-sheet split
(§6.6), not a smaller grid.

### 6.4 Band y-ranges (block **bottom** edge lives inside these)

```
R  reference / genlock / timecode      y 700 .. 800
V  video spine                          y 300 .. 690
M  monitoring + Dante audio + KVM       y 190 .. 290
N  network + fibre trunks               y 100 .. 180
P  power                                y  20 ..  90
```

Minimum clear between bands: 10 mm. Nothing from one band is drawn through
another; band-to-band always cross-references (§3.3).

### 6.5 Routing rules for the circuits that *are* drawn

* Orthogonal only. Segments are horizontal or vertical; bends on the 4 mm grid.
* A circuit leaves an output socket horizontally right for at least `8 mm (2G)`,
  turns once vertically inside the gutter, and enters the input socket
  horizontally from the left for at least `8 mm`. The as-built's DA→GX3 routes
  use 17–36 vertices, so multi-bend is fine; keep the vertical leg inside a
  gutter, never over a block.
* Allocate vertical "lanes" inside a gutter on a **4 mm** pitch, one per circuit;
  the gutter was sized for exactly that count in §6.2. Assign lanes in destination
  order (topmost destination gets the leftmost lane) so lines never cross inside
  the gutter.
* Never route through band `P` or band `N`.

### 6.6 Fit check and the sheet-break rule

Content extent under this spec: `x 24 .. 996` (972 mm) by `y 20 .. 800`
(780 mm), against a usable area of `995 x 810`. **It fits on one A0 at 1:1**,
with 23 mm of horizontal and 30 mm of vertical margin, and with the as-built's
own density as the precedent (that sheet carries 32 device blocks + 13 panel groups
in `852 x 652 mm`).

Break to a second sheet when **either** holds:
* content would exceed `995 x 810 mm` — in practice the moment the `C3 → C4`
  gutter must carry more than ~16 drawn circuits (§6.3), or
* any single gutter would need to be wider than 232 mm (the as-built's own
  maximum, ~58 lanes) — past that a gutter stops reading as a gutter.

**How to break:** split **by band**, never by column — cutting a column cuts the
signal path. Sheet `S1` = bands R + V (the video spine). Sheet `S2` = bands
M + N + P (monitoring, network, power). The two sheets join through the *same*
terminal panels, since band-crossing edges are already cross-references (§3.3) —
so no drawn circuit is ever severed by the split. Repeat the panel objects on
both sheets; the `Panel.Way` string is the join, exactly as it is within a sheet.

---

## 7. Laying out THIS rig

~25 devices: 3 servers, ~12 DAs, 2 routers (Lightware matrix + BMD VideoHub),
2 switches, a multiviewer (openGear card), timecode/sync (Brainstorm SR-112),
FiDO fibre TX/RX pairs, 3 Brompton Tessera SX40, Tessera XD, Dante I/O,
patch panels, PDUs/UPS.

### Band R — reference, genlock, timecode (`y 700 .. 800`)

| device | col | x | y | w x h | rows |
|---|---|---|---|---|---|
| `Main CTP` (REF ways) | C0 | 24 | 740 | panel | 4 ways |
| `OGX1` openGear frame (REF1/2_IN, LAN) | C2 | 240 | 724 | 32 x 28 | 5 |
| `SPG1` sync generator (openGear card) | C4 | 404 | 716 | 32 x 44 | 9 |
| `TC01` Brainstorm SR-112 | C6 | 644 | 704 | 40 x 56 | 12 |

`SPG1` fans out downward into band V — the one band-crossing that is drawn,
because it is a single-column one-to-many. `TC01`'s LTC out to the servers is
drawn; its house-clock in is `Main CTP.REF In`.

### Band V — video spine (`y 300 .. 690`)

| device | col | x | y (bottom) | w x h |
|---|---|---|---|---|
| `Main CTP` SDI In01..12 | C0 | 24 | 400 | panel, 12 ways = 48 mm |
| `FIDO-RX01..04` (AJA) | C1 | 128 | 620 / 560 / 500 / 440 | 40 x 24 |
| `DA01,03,05,07,09,11` | C2 | 240 | 650 / 590 / 530 / 470 / 410 / 350 | 40 x 24 |
| `DA02,04,06,08,10,12` | C3 | 284 | 614 / 554 / 494 / 434 / 374 / 314 | 40 x 24 |
| `SRV01` disguise | C4 | 404 | 572 | 40 x 116 (top 688) |
| `SRV02` disguise | C4 | 404 | 436 | 40 x 116 (top 552, 20 mm clear) |
| `SRV03` disguise | C4 | 404 | 300 | 40 x 116 (top 416, 20 mm clear) |
| `Internal Server Patch 1..3` | C5 | 476 | 572 / 436 / 300 | panel, 12 ways |
| **`RTR01` Lightware MX2-16x16** | **C6** | **644** | **520** | **40 x 84** |
| `RTR02` BMD VideoHub 12G 10x10 | C6 | 644 | 420 | 40 x 64 |
| `SX40-1` Brompton Tessera | C7 | 764 | 610 | 40 x 56 |
| `SX40-2` Brompton Tessera | C7 | 764 | 534 | 40 x 56 |
| `SX40-3` Brompton Tessera | C7 | 764 | 458 | 40 x 56 |
| `XD01 / XD02` Tessera XD | C8 | 884 | 610 / 550 | 40 x 40 |
| `Main CTP` LED Out / FOH ways | C9 | 964 | 440 | panel |

DA row pitch 60 mm, columns staggered `+44 x / −36 y` — 12 cards in 44 mm of
width. Server column: three 116 mm blocks need `3x116 + 2x20 = 388`, and band V
is 390 mm — exact, with the 2 mm slack at the top. If a fourth server appears,
drop `SRV03` into band M or split sheets (§6.6).

### Band M — monitoring, Dante, KVM (`y 190 .. 290`)

| device | col | x | y | w x h |
|---|---|---|---|---|
| `AVN-AIO8` Sonifex Dante | C1 | 128 | 200 | 40 x 56 |
| `AVN-AIO4` Sonifex Dante | C2 | 240 | 200 | 40 x 40 |
| `Audio Panel` | C0 | 24 | 210 | panel |
| **`MV01` multiviewer (openGear card)** | **C6** | **644** | **200** | **40 x 88** |
| `KVM1..3` Adder XDIP | C8 | 884 | 270 / 230 / 190 | 40 x 20 (40 mm pitch) |
| `KVM Panel` | C9 | 964 | 200 | panel |

**`MV01` sits directly below the matrix, in its own band.** Every one of its
connections is a cross-reference — this is the whole point:
* matrix out → MV in: `Main CTP.MV_IN01..16` printed at the MV's input side.
* MV out → matrix in: `Main CTP.Matrix In09`, `Main CTP.Matrix In10` printed at
  `x = 608` (on `RTR01`'s **input** side, one 32 mm stub out from the block edge).
* Not one line runs right-to-left. Exactly as the as-built does it.

### Band N — network and fibre (`y 100 .. 180`)

| device | col | x | y | w x h |
|---|---|---|---|---|
| `SW01` Netgear M4350 | C2 | 240 | 120 | 24 x 56 |
| `SW02` Netgear M4350 | C3 | 284 | 120 | 24 x 56 |
| `FIDO-TX01`, `FIDO-TX03` → FOH | C4 | 404 | 160 / 120 | 40 x 24 |
| `FIDO-TX02`, `FIDO-TX04` → FOH | C4+44 | 448 | 140 / 100 | 40 x 24 (staggered pair) |
| `Network Panel` | C0 / C9 | 24 / 964 | 120 | panel |

**FiDO TX → FOH and the switch fibre trunks leave the sheet.** They are
cross-references at both ends and nothing is drawn:
`Network Panel.Trunk01..04` for the inter-switch fibre,
`Main CTP.FOH01..04` (or `Network Panel.FOH0n`) for the FiDO runs.
The optic and connector go in the connector-on-cable field so they still print
next to the socket: `1310nm`, `850nm`, `LCDUP`, `MTP-12` — same idiom the
as-built uses for `Trunk01..04` and `100G A01/A02`, `100G B01/B02`.

### Band P — power (`y 20 .. 90`)

| device | col | x | y | w x h |
|---|---|---|---|---|
| `PDU1` Canford EMO E612 | C0 | 24 | 30 | 40 x 48 |
| `PDU2` Canford MDU11 | C1 | 128 | 24 | 32 x 64 |
| `UPS01` Riello SD3000 | C2 | 240 | 30 | 32 x 44 |

Every device's `PWR_IN` cross-references here. Annotate each PDU way with the
cable make-up in the way name, house style: `SRV01 (IEC to True1)`,
`RTR01 (IEC to IEC)`, `SX40-1 (IEC to IEC)`, `SW01 (IEC to IEC)`.

### Circuits actually drawn on this sheet

Only these, and every one runs left-to-right within a band:

```
                                        span   circuits  gutter
Main CTP SDI In  -> FIDO-RX             72 mm     12        72
FIDO-RX          -> DA in               72 mm     12        72
DA out           -> SRV01 in            80 mm     12        80   <- the dense one
   DA -> SRV02 / SRV03 are Main CTP cross-references (see 6.3)
SRV out          -> Internal Patch      32 mm     24        stub
Internal Patch   -> RTR01 in           128 mm     24       128
RTR01 out        -> SX40 in             80 mm     12        80
SX40 out         -> XD                  80 mm     12        80
XD out           -> Main CTP LED Out    40 mm      8        stub
SPG1             -> genlock inputs      band R -> V, single-column fan-out
PDU/UPS internal                        inside band P only
```

Everything else — MV returns, all `LAN`/`MGMT`, all `PWR_IN`, all Dante, all
fibre trunks, all FOH — is a cross-reference. Longest drawn span: 128 mm, well
inside the 250 mm ceiling and under half the as-built's 276 mm worst case.

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
content extent    30.4" x 24.4"   on a 42 x 30" sheet -> 11.6" left for the
                  title-block/legend strip, 5.6" of vertical margin.  Fits.
```

**Text sizes do not scale with the grid** — keep the §2.3 absolute sizes, except
the socket label, which drops from 2.1 mm to **1.8 mm (0.07", ~5 pt)** to hold
the same 55–65 % fill of a 0.125" row.

`G = 3/16"` was also evaluated (it is the nicer imperial grid): it gives a
content extent of `45.6" x 36.6"`, which overruns ARCH E (36 x 48") vertically
by 0.6" and needs a custom sheet. Not worth it — use 1/8".

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

* The literal `CC-*` class list shipped in the ConnectCAD template is not
  published in the online help; §5.2 gives the naming convention and the
  signal-class family, but the script must **enumerate the document's classes at
  startup** rather than assume. Confirm against a real ConnectCAD template file.
* `Circuit."Number Display"` — confirm the exact off value on a live document.
* Whether the 4 mm grid is ConnectCAD's default (`Device.__gridScale`) or an
  Adlib preference. Read `__gridScale` off a template device to settle it.
