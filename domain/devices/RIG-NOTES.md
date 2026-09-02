# RIG-NOTES — touring media-server / LED package

Companion to `library.json`. Everything below separates **what a source says**
from **what I read into it**. Nothing here is a substitute for the user's
confirmation on the flagged items.

Sources, in the order I trusted them:

| Ref | What it is |
|---|---|
| **AS-BUILT** | `Disguise GX3 FullSize As Built (1).pdf` — the client's own ConnectCAD as-built for the previous package (Adlib, rev 2, 31/10/2024). Socket naming authority. |
| **RACK** | `ADL-2360-DojaVideo_RackLayouts (1) (1).pdf` — rack elevations, 29/04/2026. |
| **PULL** | `DOJACAT_SERVER PULLSHEET.pdf` — gear list, ENAS002229, 12-08-2026. Convention/context, not the device list. |
| datasheets | Brompton, AJA, Brainstorm, Glensound, Sonifex, Netgear, Cobalt — cited per socket in `library.json`. |

---

## 1. My reading of the rig

The user's spec, verbatim:

> "its a 2 OUTPUT SHOW 4K. WITH 3 SX40. ITS 3 12G SDI OF CAPTURE AND DANTE IS
> WIRED FOR SERVERS VIA SR112. CONNECT NETWORK SWITCHES VIA FIBER AND FIDO TX
> SENDS TO FOH."

plus, later: *"SX4O PLUGS INTO LIGHTWARE OUTPUTS"* and *"DISGUISE SERVERS PLUG
INTO MATRIX VIA HDMI. THE MV IS A OG ONE ANS IT PLUGS INTO MATRIX INS AND
OUTS TOO"*.

**The Lightware 16×16 HDMI 2.0 matrix is the hub of the drawing.** Everything in
the video path meets there:

```
  3x 12G-SDI capture ──▶ 3x 1:4 DA ──▶ SRV 1/2/3  (12G-SDI_IN A, E, I)
                                          │
                                          │ 3x HDMI 2.0 per server (VFC Slot 1/2/3)
                                          ▼
                              ┌───────────────────────────┐
        MV HDMI out ─────────▶│  RTR — Lightware MX2      │──────▶ 3x SX40  (HDMI2.0_IN)
                              │  16x16 HDMI 2.0           │            │
        (MV picture back      │                           │──────▶ MV HDMI2.0_IN 1..4
         into the matrix)     └───────────────────────────┘            │
                                          │                           ▼
                                          └──▶ 3x OG-HA5-12G ──▶ 12G-SDI ──▶ FiDO TX ──▶ FOH
                                                (HDMI 2.0 → 12G-SDI)
  SX40 10G ──▶ Tessera XD ──▶ 1G ──▶ LED fixtures
```

Audio / sync / control run alongside:

```
  Dante network ──▶ Sonifex AVN-AIO8R ──▶ analogue LINE ──▶ SRV LINE_IN / LINE_OUT
  Dante network ──▶ Glensound TR-12D  ──▶ LTC ──▶ Brainstorm SR-112 ──▶ 12x LTC
                                                     └─▶ Rosendahl MIF 4 ──USB──▶ SRV
  SPG ──▶ REF ──▶ SRV REF_IN, SX40 REF_IN, OGX REF1/2_IN
  SW01 ◀──25G SFP28 fibre trunk──▶ SW02
```

Two readings I want to make explicit, because they change the cable schedule:

- **The "3× 12G-SDI of capture" goes into the SERVERS, not the processors.** The
  AS-BUILT disguise block has exactly three 12G-SDI capture inputs — `12G-SDI_IN A`,
  `12G-SDI_IN E`, `12G-SDI_IN I` — with 3G inputs B/C/D, F/G/H, J/K/L between them.
  Three 12G captures is exactly what one disguise machine takes. The SX40 also has a
  12G-SDI input, but the show feed reaches it on HDMI 2.0 from the Lightware, so I have
  left every SX40 `12G-SDI_IN` unconnected in my reading.
- **Servers and processors are different devices.** "3 SX40" = three Brompton
  Tessera SX40 LED processors. "SERVERS" is separate and plural. The server model is
  an open question (§4.1).

---

## 2. Device list with quantities

| Qty | Device | Key | Confidence in the socket list |
|---:|---|---|---|
| 3 | Brompton **Tessera SX40** LED processor | `sx40` | verified — Brompton Feb-2025 datasheet + QSG |
| ? | Brompton **Tessera XD** distribution unit | `xd` | verified spec, **quantity unknown** (§4.3) |
| 3 | **disguise GX3** media server (DIR / ACT / UND) | `disguise_server` | verified from AS-BUILT; **model unconfirmed** (§4.1) |
| 1 | **Lightware MX2-16x16-HDMI20-R** HDMI 2.0 matrix | `lightware_mx2` | verified from AS-BUILT, verbatim |
| 1 | **Cobalt 9971-MV6-4H-4K** openGear multiviewer | `mv_9971` | verified spec; **variant unconfirmed** (§4.5) |
| 3 | **AJA OG-HA5-12G** openGear HDMI 2.0 → 12G-SDI | `og_ha5_12g` | verified (AJA) |
| 3 | **Ross openGear OGX** frames | `ogx` | verified from AS-BUILT |
| 3 | **Ross SRA-8901-4** 1:4 12G DA | `sra_8901_4` | verified from AS-BUILT; **PULL lists a different DA** (§4.6) |
| 1 | **Ross SPG8260-R2** sync generator | `spg8260` | verified from AS-BUILT; **PULL lists a Brainstorm DXD-8** (§4.6) |
| 1 | **Brainstorm SR-112** timecode distripalyzer | `sr112` | verified (Brainstorm) |
| 1 | **Glensound TR-12 + TR12D** Dante timecode reader | `tr12d` | verified (Glensound manual) |
| 1 | **Sonifex AVN-AIO8R** 8×8 dual-Dante interface | `avn_aio8r` | verified (Sonifex) |
| 2 | **Netgear M4350-24X4V** (XSM4328CV) switch | `sw_m4350_24x4v` | verified (Netgear) |
| 1 | **Netgear M4250-40G8XF-PoE++** switch | `sw_m4250_40g8xf` | **placeholder, no sockets researched** |
| 1+ | **AJA FiDO-2T-12G** fibre transmitter | `fido_2t_12g` | verified (AJA); **qty depends on FOH channel count** (§4.4) |
| 3 | **Rosendahl MIF 4** timecode interface | `mif4` | verified from AS-BUILT; count is my inference (§4.2) |
| 4 | **Adder XDIP** KVM extender | `xdip` | verified from AS-BUILT; **PULL specifies Adder Infinity instead** (§4.6) |

254 sockets total: 244 `verified`, 10 `inferred`, 0 fabricated.

---

## 3. The three questions you asked me to settle

### 3.1 "DANTE IS WIRED FOR SERVERS VIA SR112" — the SR-112 has no Dante.

**Verified fact.** The Brainstorm SR-112's complete rear panel is:
1× LTC in (XLR female) · 12× LTC out (outputs 1–8 on one DB-25 Tascam/Avid pinout,
9–10 on XLR male, 11–12 on ¼" TRS) · 1× video ref BNC · 1× Ethernet RJ45 ·
2× 4-pin circular 12 VDC inputs. **No Dante port, no audio I/O, no AES67.**
It is a timecode reader/reshaper/distributor and nothing else.
Source: <https://brainstormtime.com/products/sr-112/>

**My conclusion — two separate paths are being collapsed into one sentence:**

1. **Timecode/sync to the servers** — this is the SR-112's job, and there IS a real
   Dante link in that chain, just not on the SR-112. The PULL sheet carries a
   **Glensound TR-12 with the TR12D Dante option card** ("Timecode Viewer and
   Distribution with Dante Option Card"). Its manual is explicit: with the Dante card
   fitted, the rear blanking plate becomes an etherCON RJ45 to a Dante/AES67 network,
   and **two Dante channels are selectable as the timecode source**. So timecode
   arrives from the audio world **on Dante**, the TR-12D turns it into analogue LTC,
   and the SR-112 fans that out to 12 destinations — the servers via their
   **Rosendahl MIF 4** interfaces (`LTC_IN` → `USB2_IO` to the disguise machine), which
   is exactly what the AS-BUILT shows (`TCIntf01/02 · Rosendahl_MIF 4`) and what the
   RACK layout confirms (`MIF4 #1`, `MIF4 #2`).
   → **"Dante … via SR112" = timecode that originated on Dante, distributed by the SR-112.**

2. **Dante audio to/from the servers** — this is a different box. The PULL sheet has a
   **Sonifex AVN-AIO8R**, an 8×8 dual-Dante ↔ analogue interface on Neutrik XLRs with
   PoE. That is what feeds the disguise `LINE_IN L/R` and takes back `LINE_OUT L/R`.
   (There is also an AVN-AIO4 in the RACK layout, presumably at FOH.)

**❓ CONFIRM:** is the intent (a) timecode-on-Dante → TR-12D → SR-112 → MIF 4 → servers,
with audio-on-Dante → AVN-AIO8R → server LINE I/O as a parallel path? Or (b) something
else? **I have not put a Dante socket on the SR-112 and will not.**

### 3.2 Which FiDO — `FiDO-2T-12G`.

**Verified constraint:** AJA makes **no 4-channel 12G FiDO**. The 4-channel FiDO-4T is
3G-SDI only. At 12G the range is FiDO-T-12G (1 ch) and **FiDO-2T-12G (2 ch)**.

**Choice: FiDO-2T-12G.** The show is 2× 4K, which is 12G-SDI single-link, so 3G parts
are out; and two channels matches the two show outputs exactly, on one duplex LC —
i.e. one opticalCON DUO tail on the fibre panel, which is how this package's FOH snake
is built (PULL: `UCP4OFN` / `UCP2OFN` opticalCON plates, `OFNS2XQ152` OS2 quad SM fibre).
Its I/O is 2× 12G-SDI BNC in, LC fibre out ("2 simplex or 1 duplex"), 5–20 VDC power.
**No SDI loop/thru** — if you need the same feed locally, it has to be split before
the FiDO. Source: <https://www.aja.com/products/fido-2t-12g>

**❓ CONFIRM:** how many 12G channels actually go to FOH? 2 → one FiDO-2T-12G.
3–4 → two of them. Note the Doja package as pulled did this with **Ross openGear
`SFC6901R3F` quad 12G fibre cards** in an OGX frame, not with FiDOs at all — so if
you want FiDOs this is a change from the pull sheet, and I should know it.

### 3.3 SX40 vs XD — do the XDs belong in the chain?

**Yes, if the LED map needs more than 4 fixture trunks per processor.** Verified from
Brompton: the SX40's only fixture output is **4× 10G Tessera ports** (each with a copper
etherCON Cat6A *and* a fibre opticalCON DUO connector, auto-switching — one logical port,
two physical sockets, only one used at a time). The SX40 has **no 1G fixture ports at
all**. To get 1G runs to panels you need the **Tessera XD**: 10G in (Cu or fibre) →
**10× 1G etherCON outputs**, up to 5 XDs daisy-chained per 10G trunk.

Three SX40s alone can absolutely carry a 2×4K show (each SX40 does ~9 M px, and a
4096×2160 canvas is ~8.8 M px, so **one SX40 ≈ one 4K surface at 60 Hz**). What they
cannot do alone is *cable* it — you get 12 trunks total and no per-panel-string ports.

**❓ CONFIRM:** the XD count is a pure function of the LED map (fixture count, string
lengths, bit depth, frame rate) and I have none of that. `library.json` carries `xd`
with `"qty": null` deliberately.

---

## 4. Open questions — answer these before this is "exact"

### 4.1 What are the servers? ⚠️ blocking
You said "servers", plural, and confirmed they are **disguise** and connect to the
matrix over HDMI. Both reference documents say **GX3** — AS-BUILT draws two
`disguise_GX3` blocks, PULL lists `D3GX3 × 2`. But PULL also annotates
`3 - 4k OUTPUTS : DIR/ACT/UND` and `MID LEVEL SERVER - *STRATOS*`, and this rig needs
three machines (Director / Actor / Understudy). I have modelled **3× GX3** from the
as-built socket list.
**→ Confirm: GX3? Or has the fleet moved to the disguise EX range (EX 2 / EX 3+) for
this tour?** If it has changed, the whole server block's socket list changes and I
should redo it — the as-built naming would carry over but the port counts would not.

### 4.2 The third SX40 — spare, or a third surface? ⚠️ my best guess, needs your call
**My reading: 2 SX40s carry the two 4K surfaces and the 3rd is a backup processor.**
Reasoning: the show is 2× 4K outputs; one SX40 handles one 4K canvas at capacity; and
Brompton **Processor Redundancy** exists precisely for this — "if a problem occurs with
the video input or output on a primary processor, a back-up processor takes over in a
few seconds". A backup processor still needs its own video feed, so it still consumes a
matrix output either way.
**The alternative** is that the LED wall is bigger than 2× 4K worth of pixels and all
three SX40s are live, each taking a copy or a region of the two feeds through the matrix.
**→ Which is it?** Either way the Lightware port count is the same (3 outputs); what
changes is the LED-side drawing and the XD count.

### 4.3 Lightware 16×16 port budget — all three claimants
Each SX40 has **exactly one** HDMI 2.0b input, so **each SX40 consumes exactly one
matrix output.** Full budget as I read it:

**Inputs (16 available)**
| Source | Ports |
|---|---:|
| SRV 1 — VFC Slot 1/2/3 (HDMI 2.0) | 3 |
| SRV 2 — VFC Slot 1/2/3 | 3 |
| SRV 3 — VFC Slot 1/2/3 | 3 |
| MV return — `HDMI2.0_OUT 1..2` back into the matrix | 1–2 |
| **Used** | **10–11** |
| **Spare** | **5–6** |

**Outputs (16 available)**
| Destination | Ports |
|---|---:|
| SX40 1/2/3 — `HDMI2.0_IN` (one each) | 3 |
| MV — `HDMI2.0_IN 1..4` | up to 4 |
| OG-HA5-12G × 3 (HDMI → 12G-SDI, for FOH/FiDO and the SDI plant) | 3 |
| Local monitoring (drawer monitor, 27" reference monitors) | 1–3 |
| **Used** | **~11–13** |
| **Spare** | **~3–5** |

It fits, with real headroom on the input side and tighter headroom on outputs.
**→ Confirm** how many MV tiles you actually want (4 HDMI feeds is the -4H card's limit,
more sources have to arrive on its SDI side), and how many local monitor feeds.

### 4.4 The multiviewer variant ⚠️
PULL code `9971MV64K`, described "6-In / 4 in HDMI Expandable UHD Multiviewer openGear
Card". That description matches Cobalt's **9971-MV6-4H-4K** — 6× SDI in, 8× SDI out,
**4× HDMI 2.0 in (type C mini)**, 2× HDMI 2.0 out (type A), GbE, GPIO on HD-15.
The plain **9971-MV6-4K has no HDMI inputs at all.**
**→ Confirm the variant.** If it is the plain MV6-4K, then every matrix output feeding
the MV must first pass through an OG-HA5-12G HDMI→12G-SDI converter — which is very
likely *why* PULL carries 3 of them in the same OGX frame as the MV, and it changes
the drawing materially.

### 4.5 Does the MV also feed / take from the SDI plant?
You said the MV plugs into matrix ins **and** outs. It also has 6 SDI in and 8 SDI out.
**→ Are the SDI ports used** (e.g. the 3 captures mirrored into the MV, or MV output to
an SDI monitor at FOH), or is the MV purely HDMI-side on this rig?

### 4.6 Pull-sheet vs as-built conflicts — which drawing wins?
Three devices differ between the client's own as-built and this tour's pull sheet. I
kept the **as-built** socket lists (they are house-verified) and flagged each:

| As-built | Pull sheet | Effect |
|---|---|---|
| Ross **SRA-8901-4** 1:4 12G DA | Ross **DRA-8902-10** 2-ch 2:10 12G DA (`R2_DRA890210R3` ×4) | different socket list entirely |
| Ross **SPG8260-R2** sync generator | **Brainstorm DXD-8** reference generator w/ PTP | different socket list |
| Adder **XDIP** KVM | Adder **Infinity ALIF4001T/R + AIM24V2** | different socket list |
| BMD **VideoHub 12G 10×10** SDI router | **AJA KUMO 3232-12G** 32×32 + KUMO CP | not yet modelled either way |
| Craltech **4KCRAFT-12G16** MV | Cobalt **9971-MV** openGear (you confirmed openGear) | ✅ resolved — using Cobalt |

**→ For each row, which one is in this rig?** I will re-spec whichever you pick.
Note there is **no 12G SDI router in `library.json` yet** — I did not want to guess
between the BMD VideoHub and the AJA KUMO. Tell me which and I will add it.

### 4.7 Smaller ones
- **MIF 4 count** — as-built and rack layout both show 2; three servers implies 3. Confirm.
- **Second switch PSU** — the M4350-24X4V's second PSU is optional (it also raises the
  PoE budget to 720 W). `PWR_IN 2` is marked `inferred`. Fitted or not?
- **Netgear M4250-40G8XF-PoE++** — in PULL, not in your spec. In this rig? It is a
  sockets-empty placeholder right now.
- **openGear rear-module connectors** — every openGear card's SDI connector type (BNC vs
  DIN 1.0/2.3 micro-BNC) depends on the rear module fitted. The as-built shows both
  `BNC` and `MICROBNC` on Ross cards. I defaulted to `BNC` and noted it per socket.
  Confirm against the actual rear modules before the cable schedule is cut.
- **SX40 mains inlet** — datasheet says "switched autoranging mains input" without naming
  the IEC type. C14 or C20? Marked `inferred`.
- **XD 10G thru connectors** — the datasheet says the thru auto-switches between fibre and
  copper but does not enumerate its connectors. I modelled `10G_THRU Cu` + `10G_THRU Fib`
  as `inferred`. Confirm on the unit.

---

## 5. Drawing conventions used

- Devices label as **Name over Make_Model**, per the as-built.
- Socket names copy the as-built grammar exactly: `12G-SDI_IN A`, `12G-SDI_OUT 1`,
  `HDMI_2.0 1`, `LAN A`, `MGMT`, `REF_IN`, `LINE_IN L`, `PWR_IN`, `USB 1`.
- **The Lightware block reuses the same socket names on both sides** (`HDMI_2.0 1..16`
  in *and* out) because that is literally what the as-built draws. Direction
  disambiguates them. Flagging it in case your ConnectCAD import needs unique names.
- **Brompton 10G ports are modelled as two sockets each** — `10G_OUT 1 Cu` (etherCON
  Cat6A) and `10G_OUT 1 Fib` (opticalCON DUO). They are **one logical port**; only one is
  patched at a time. Same for the XD's `10G_IN Cu` / `10G_IN Fib`.
- Signal types beyond the as-built legend: `10G`, `1G`, `SMF`, `DANTE`, `DMX`, `GPIO`.
  `SMF` is new because the as-built legend only has `MMF` — every fibre link in this rig
  (1310 nm 25G trunks, FiDO, Tessera fibre) is single-mode.
