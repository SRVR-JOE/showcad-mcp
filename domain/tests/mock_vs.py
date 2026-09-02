"""Mock `vs` module — simulates a Vectorworks doc for out-of-VW testing.
Dataset mirrors docs/TASKS.md T1.4: small video rack + 10 fixtures,
one deliberately unconnected socket, one duplicate channel."""


class H(dict):  # a "handle" is just a dict with a _record tag
    pass


def _dev(name, make, model, layer, sockets):
    d = H(_record="Device", Name=name, Make=make, Model=model, _layer=layer)
    d["_sockets"] = [H(_record="Socket", Name=n, Direction=dr, _parent=d)
                     for n, dr in sockets]
    return d

DEVICES = [
    _dev("CAM 1", "Sony", "HDC-3500", "VIDEO SCHEM", [("SDI OUT 1", "out")]),
    _dev("CAM 2", "Sony", "HDC-3500", "VIDEO SCHEM", [("SDI OUT 1", "out")]),
    _dev("E2 FRAME", "Barco", "E2 Gen2", "VIDEO SCHEM",
         [("IN 1", "in"), ("IN 2", "in"), ("IN 3", "in"),
          ("OUT 1", "out"), ("OUT 2", "out")]),
    _dev("SX40 A", "Brompton", "Tessera SX40", "VIDEO SCHEM",
         [("HDMI IN", "in"), ("10G OUT 1", "out"), ("10G OUT 2", "out")]),
    _dev("XD 1", "Brompton", "Tessera XD", "VIDEO SCHEM",
         [("10G IN", "in"), ("PORT 1", "out")]),
    _dev("SRV 1", "disguise", "GX3", "VIDEO SCHEM",
         [("DP OUT 1", "out"), ("DP OUT 2", "out")]),  # DP OUT 2 left unconnected on purpose
]
_D = {d["Name"]: d for d in DEVICES}
def _skt(dev, name):
    return next(s for s in _D[dev]["_sockets"] if s["Name"] == name)

def _cir(num, sig, ct, sd, ss, dd, ds):
    return H(_record="Circuit", Number=num, Signal=sig, **{"Cable Type": ct},
             _src=(_D[sd], _skt(sd, ss)) if sd else (None, None),
             _dst=(_D[dd], _skt(dd, ds)) if dd else (None, None))

CIRCUITS = [
    _cir("V001", "12G-SDI", "Belden 4794R", "CAM 1", "SDI OUT 1", "E2 FRAME", "IN 1"),
    _cir("V002", "12G-SDI", "Belden 4794R", "CAM 2", "SDI OUT 1", "E2 FRAME", "IN 2"),
    _cir("V003", "HDMI", "HDMI 2.0", "E2 FRAME", "OUT 1", "SX40 A", "HDMI IN"),
    _cir("V004", "10GbE", "OpticalCON DUO", "SX40 A", "10G OUT 1", "XD 1", "10G IN"),
    _cir("V005", "DP1.2", "DisplayPort", "SRV 1", "DP OUT 1", "E2 FRAME", "IN 3"),
]

def _fx(ch, unit, addr, uni, pos, purpose, sym):
    return H(_record="Lighting Device", Channel=ch, **{"Unit Number": unit},
             Address=addr, Universe=uni, Position=pos, Purpose=purpose,
             **{"Symbol Name": sym})

FIXTURES = [
    _fx("101", "1", "1",   "1", "FOH TRUSS", "Front Wash", "MAC Aura XB"),
    _fx("102", "2", "17",  "1", "FOH TRUSS", "Front Wash", "MAC Aura XB"),
    _fx("103", "3", "33",  "1", "FOH TRUSS", "Front Wash", "MAC Aura XB"),
    _fx("104", "4", "49",  "1", "FOH TRUSS", "Key",        "BMFL Blade"),
    _fx("201", "5", "1",   "2", "US TRUSS",  "Back Light", "MAC Ultra"),
    _fx("202", "6", "45",  "2", "US TRUSS",  "Back Light", "MAC Ultra"),
    _fx("203", "7", "89",  "2", "US TRUSS",  "Back Light", "MAC Ultra"),
    _fx("204", "8", "133", "2", "US TRUSS",  "Eye Candy",  "Strobe X"),
    _fx("205", "9", "177", "2", "US TRUSS",  "Eye Candy",  "Strobe X"),
    _fx("101", "10", "221","2", "US TRUSS",  "Specials",   "BMFL Blade"),  # duplicate channel 101 on purpose
]

_LAYERS = ["VIDEO SCHEM", "LX PLOT", "RACK LAYOUT"]

# ── vs.* API surface used by the pump ───────────────────────────────────────
def FLayer():            return ("L", 0)
def NextLayer(h):        i = h[1] + 1; return ("L", i) if i < len(_LAYERS) else None
def GetLName(h):         return _LAYERS[h[1]] if isinstance(h, tuple) else h
def GetLayer(h):         return ("L", _LAYERS.index(h.get("_layer", _LAYERS[0])))
def GetVersionEx():      return (31, 0, 1, 1, 800000)   # 31 ≙ VW2026
def GetFName():          return "demo-show.vwx"
def GetFPathName():      return "C:/shows/demo-show.vwx"

def ForEachObject(cb, criteria):
    pon = criteria.split("'")[1]
    pool = {"Device": DEVICES, "Circuit": CIRCUITS,
            "Lighting Device": FIXTURES}.get(pon, [])
    for h in pool:
        cb(h)

def GetRField(h, record, field):
    if h is None: return None
    return h.get(field)

def CC_GetCircuitSource(h):
    dev, skt = h["_src"]; return (dev, skt, None, skt)
def CC_GetCircuitDest(h):
    dev, skt = h["_dst"]; return (dev, skt, None, skt)
def CC_GetDevice(hSocket, skip_adapters=True):
    return hSocket.get("_parent")
def CC_DeviceSockets(hDevice):          # pump helper; real impl walks container
    return hDevice["_sockets"]
