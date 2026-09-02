# Rig spec — as stated by the user (Solotech video engineer)

Verbatim, in the order given. Anything not quoted here is inference and must
be marked as such wherever it is used.

> "its a 2 OUTPUT SHOW 4K. WITH 3 SX40. ITS 3 12G SDI OF CAPTURE AND DANTE IS
>  WIRED FOR SERVERS VIA SR112. CONNECT NETWORK SWITCHES VIA FIBER AND FIDO TX
>  SENDS TO FOH. CREATE OR LOOK UP ALL DEVICES, AND MAKE IT EXACT"

> "SX4O PLUGS INTO LIGHTWARE OUTPUTS PLEASE"

> "DISGUISE SERVERS PLUG INTO MATRIX VIA HDMI. THE MV IS A OG ONE ANS IT
>  PLUGS INTO MATRIX INS AND OUTS TOO"

> "DO YOUR BEST WE WILL HONE IN."

## Settled

| Item | Value |
|---|---|
| Show outputs | 2 × 4K |
| Processors | 3 × Brompton Tessera **SX40** (LED processor — NOT disguise; disguise has no SX40) |
| SX40 feed | From the **Lightware** matrix outputs — `RTR 1.1/2.1`, `Lightware_MX2-16x16-HDMI20-R`, HDMI 2.0 |
| Capture | 3 × 12G-SDI, into the **servers** — not into the SX40s |
| Switch interconnect | Fiber trunks |
| FOH feed | AJA **FiDO TX** |
| Timecode / sync | Brainstorm **SR-112** |
| Servers | **disguise** — feed the matrix over **HDMI** (pull sheet: 3 × VFCHDMI20 per server = 3 × HDMI 2.0 out each) |
| Multiviewer | an **openGear** card (pull sheet `9971MV64K`, Cobalt 9971-MV family, in a Ross OGX frame) — **not** the as-built's Craltech |
| MV wiring | Bidirectional with the matrix: takes matrix **outputs**, returns to matrix **inputs** |

## Signal spine

    capture (3× 12G-SDI) → disguise servers ──HDMI──┐
                                                    ▼
                          openGear MV ⇄ Lightware MX2-16x16-HDMI20-R ──▶ 3× SX40 ──▶ LED

The matrix is the HUB, not a stage in a line. Three claimants on its 16×16
ports: disguise server HDMI outs (in), MV (both directions), SX40s (out).
The MV return is a right-to-left edge — it must be drawn as a panel
cross-reference, never as a line doubling back across the sheet.

with reference/genlock, Dante/audio, network and power as separate bands.

## Open questions — do not silently resolve these

1. **"DANTE IS WIRED FOR SERVERS VIA SR112."** The SR-112 is a timecode
   distripalyzer; it distributes LTC/sync, not Dante. Their own pull sheet
   carries a Sonifex AVN-AIO8 for Dante. Best reading: timecode/sync to the
   servers via SR-112, Dante arriving separately. Needs user confirmation —
   do not invent Dante ports on an SR-112.
2. ~~Server model.~~ **RESOLVED** — the user confirmed disguise, feeding the
   matrix over HDMI. Exact model (GX3 per pull sheet and as-built) still
   assumed rather than stated.
3. **Third SX40.** With 2 × 4K outputs and 3 processors, is the third a spare,
   a redundant pair member, or a third surface?
4. **Lightware port budget.** How many matrix outputs each SX40 consumes.

## Reference drawings on this machine

- `~/Downloads/Disguise GX3 FullSize As Built (1).pdf` — a real ConnectCAD
  as-built for this client. THE house-style reference for block anatomy,
  socket naming and the panel cross-reference idiom.
- `~/Downloads/ADL-2360-DojaVideo_RackLayouts (1) (1).pdf` — rack elevations.
- `~/Library/CloudStorage/OneDrive-Solotech.com/01 Shows & Tours/DOJA/
  DOJACAT_SERVER PULLSHEET.pdf` — gear list (GX3-era; convention, not spec).
