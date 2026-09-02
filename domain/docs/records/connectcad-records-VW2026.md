# ConnectCAD record formats — VERIFIED on live Vectorworks 31.7.0

Dumped 2026-09-01 from a live document by creating one of each PIO,
reading `GetParametricRecord` / `NumRecords` / `GetFldName` / `GetRField`,
then deleting them. These replace every TBV guess in
`domain/reference_handlers.py`.

**PIO name == record name** for all three, so `ForEachObject("PON='Device'")`
and `GetRField(h,'Device',…)` use the same string. All three are `GetTypeN` 86
(Plug-in Object) — 86 is *not* a discriminator, it is every PIO.

## Device — 35 fields, field names are LOWERCASE

    symbol  tag  description  name  make  model
    height  width  depth  power  weight
    modular  nslots
    loc_room  loc_rack  loc_rackU  loc_slot  racklocation
    user1 … user8
    __version(2500)  __gridScale  width_R  heightU
    HasEquipment  "BTU Auto Calculation"  BTU  type  __PanelPrefix

The reference handlers used `Name` / `Make` / `Model`. The real fields are
`name` / `make` / `model`. Title Case returns nothing.

## Socket — 22 fields, LOWERCASE

    type  name  tag  signal  connector  n_circuits  cablenum
    Orientation  ConnSymbol  TextSymbol
    user1 … user8
    IsTerminated  __version  __gridScale  "Connections Count"

Direction lives in **`type`**, not `Direction` as the reference guessed.

## Circuit — 61 fields, CamelCase (NOT lowercase — the cases differ per record)

    Number  Cable  Signal  Circuits
    __Src_ID  Src_Dev_Name  Src_Dev_Tag  Src_Skt_Name  Src_Skt_Tag
              Src_Signal  Src_Skt_Conn  Src_Skt_Circs
    __Dst_ID  Dst_Dev_Name  Dst_Dev_Tag  Dst_Skt_Name  Dst_Skt_Tag
              Dst_Signal  Dst_Skt_Conn  Dst_Skt_Circs
    Src_Room  Src_Rack  Src_RackU  Src_Slot
    Dst_Room  Dst_Rack  Dst_RackU  Dst_Slot
    CircuitType  ShowEnd  Label  Orientation
    CableLength  CableCalculatedLength  "Number Display"
    "Cable Type"  "Cable Outside Diameter"
    ControlPoint01X/Y … 03X/Y   plus ~20 private __ fields

**The Circuit record denormalises both endpoints.** `Src_Dev_Name`,
`Src_Skt_Name`, `Dst_Dev_Name`, `Dst_Skt_Name` and the per-end signal and
connector are all on the circuit itself. So `cc_trace_signal` can build the
whole graph from record fields in one pass, without calling
`CC_GetCircuitSource`/`Dest` per circuit at all — the "fallback" path is
actually the faster one here. The CC_* getters remain useful for resolving
adapters and equipment items, where the record carries no handle.

## Creating them from script

    vs.Rect(...);   h = vs.LNewObj();  dev = vs.CC_DeviceFromShape(h)
    vs.MoveTo/LineTo; h = vs.LNewObj();  cir = vs.CC_CircuitFromShape(h)
    vs.CreateCustomObjectN('Socket', x, y, 0, False)

`CC_DeviceFromShape` and `CC_CircuitFromShape` leave the source shape in the
document — delete it yourself or the drawing accumulates orphan geometry.
