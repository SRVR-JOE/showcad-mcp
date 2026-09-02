"""Mock `vs` module — stands in for Vectorworks' Python API out of process.

Installed into ``sys.modules['vs']`` by ``harness.py`` BEFORE any plugin module
is imported, because this repo's ``vwx-plugin/commands.py`` does a hard
``import vs`` at module top level (the old standalone pump had a ``set_vs()``
injection hook instead — that hook does not exist here).

Dataset mirrors docs/TASKS.md T1.4: small video rack + 10 fixtures, one
deliberately unconnected socket, one deliberate duplicate channel. The original
scaffold fixture values are preserved verbatim so the 7 legacy checks port
over unchanged.

────────────────────────────────────────────────────────────────────────────
CAPABILITY SWITCH — the point of this file
────────────────────────────────────────────────────────────────────────────
``vwx-plugin/vs_index.json`` indexes only SIX ConnectCAD functions:

    CC_CircuitFromShape  CC_DeviceFromShape  CC_RouteFromShape
    CC_RoomFromShape     CC_OnFindAndReplace CC_ReloadData

``CC_GetCircuitSource``, ``CC_GetCircuitDest``, ``CC_GetDevice`` and
``CC_DeviceSockets`` are NOT in that index. We do not yet know whether they
exist on a live VW2026 install (the index may lag the SDK stub it was built
from) — so this mock simulates BOTH worlds:

    configure(cc_getters=True)   getters present  → direct-API path
    configure(cc_getters=False)  getters absent   → AttributeError on access,
                                                    forcing the record-field /
                                                    container-walk fallback

Everything a caller reaches for that this mock does not define is recorded in
``MISSES`` and then raises AttributeError, exactly as a real ``vs`` would. That
list is the diagnostic: it names every VW function the plugin code assumes.

NOTHING here asserts that a record FIELD NAME is correct. All ConnectCAD /
Spotlight field names below are TBV until a live document dump runs
(docs/TASKS.md T1.1-T1.3). The circuit records deliberately carry the same
value under many plausible aliases so a fallback implementation can find it
whichever spelling it guessed; tests assert result SHAPE, never field names.
"""

# ── configuration ───────────────────────────────────────────────────────────

DEFAULTS = {
    # Are CC_GetCircuitSource / CC_GetCircuitDest / CC_GetDevice /
    # CC_DeviceSockets reachable on the vs module?
    'cc_getters': True,
    # GetRField() for a field that does not exist on the record.
    #   'none'  -> return None      'empty' -> return ''   (real VW's likely behavior)
    #   'raise' -> raise RuntimeError (worst case; proves the verb still returns a dict)
    'missing_field': 'none',
    # GetRField()/GetLayer() etc. handed a None handle.
    #   'none' -> return None       'raise' -> raise RuntimeError
    'null_handle': 'none',
    # Enforce that the `record` argument of GetRField matches the object's
    # record name. Off by default: record names are TBV too.
    'strict_record': False,
    # Detach one fixture from the position its Position FIELD names, so
    # by-field and by-parent counts disagree. Off by default (the base fixture
    # document is consistent); switch it on to test the disagreement report.
    'hangpos_mismatch': False,
}
CONFIG = dict(DEFAULTS)

# Diagnostics, reset by reset().
MISSES = []          # vs.<name> attribute lookups this mock does not implement
CRITERIA = []        # every ForEachObject criteria string seen
FIELD_READS = []     # (record, field, hit?) for every GetRField call


def configure(**kw):
    """Flip a capability switch. Unknown keys raise (typo protection)."""
    for k, v in kw.items():
        if k not in DEFAULTS:
            raise KeyError('unknown mock_vs config key: %r (known: %s)'
                           % (k, ', '.join(sorted(DEFAULTS))))
        CONFIG[k] = v
    return dict(CONFIG)


def reset():
    """Restore defaults and clear diagnostics. Call between test cases."""
    CONFIG.clear()
    CONFIG.update(DEFAULTS)
    del MISSES[:], CRITERIA[:], FIELD_READS[:]


class capability(object):
    """Context manager: ``with mock_vs.capability(cc_getters=False): ...``"""

    def __init__(self, **kw):
        self._kw = kw
        self._prev = None

    def __enter__(self):
        self._prev = dict(CONFIG)
        configure(**self._kw)
        return self

    def __exit__(self, *exc):
        CONFIG.clear()
        CONFIG.update(self._prev)
        return False


# ── fixture data ────────────────────────────────────────────────────────────

_uuid_seq = [0]


class H(dict):
    """A "handle" is a dict with a _record tag. Hashable by identity so it can
    live in sets the way a real opaque VW handle does."""

    def __init__(self, *a, **kw):
        dict.__init__(self, *a, **kw)
        _uuid_seq[0] += 1
        self['_uuid'] = 'MOCK-%04d' % _uuid_seq[0]
        _BY_UUID[self['_uuid']] = self

    def __hash__(self):
        return id(self)

    def __eq__(self, other):
        return self is other

    def __ne__(self, other):
        return self is not other


_BY_UUID = {}


def _dev(name, make, model, layer, sockets):
    d = H(_record="Device", name=name, make=make, model=model, _layer=layer)
    d["_sockets"] = [H(_record="Socket", name=n, type=dr, _parent=d)
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
         [("DP OUT 1", "out"), ("DP OUT 2", "out")]),  # DP OUT 2 unconnected on purpose
]
_D = {d["name"]: d for d in DEVICES}


def _skt(dev, name):
    return next(s for s in _D[dev]["_sockets"] if s["name"] == name)


# The circuit endpoint field names are no longer guesses. A live dump against
# Vectorworks 31.7.0 (domain/docs/records/connectcad-records-VW2026.md) settled
# them: the Circuit record denormalises BOTH endpoints under these exact names.
# The mock deliberately populates ONLY these — populating speculative aliases as
# well would let a handler reading the wrong field still pass.
SRC_DEV_ALIASES = ("Src_Dev_Name",)
SRC_SKT_ALIASES = ("Src_Skt_Name",)
DST_DEV_ALIASES = ("Dst_Dev_Name",)
DST_SKT_ALIASES = ("Dst_Skt_Name",)


def _cir(num, sig, ct, sd, ss, dd, ds):
    c = H(_record="Circuit", _layer="VIDEO SCHEM", Number=num, Signal=sig,
          **{"Cable Type": ct})
    c["_src"] = (_D[sd], _skt(sd, ss)) if sd else (None, None)
    c["_dst"] = (_D[dd], _skt(dd, ds)) if dd else (None, None)
    # Record-field mirror of the same wiring, for the getters-absent fallback.
    for a in SRC_DEV_ALIASES:
        c[a] = sd or ""
    for a in SRC_SKT_ALIASES:
        c[a] = ss or ""
    for a in DST_DEV_ALIASES:
        c[a] = dd or ""
    for a in DST_SKT_ALIASES:
        c[a] = ds or ""
    return c


CIRCUITS = [
    _cir("V001", "12G-SDI", "Belden 4794R", "CAM 1", "SDI OUT 1", "E2 FRAME", "IN 1"),
    _cir("V002", "12G-SDI", "Belden 4794R", "CAM 2", "SDI OUT 1", "E2 FRAME", "IN 2"),
    _cir("V003", "HDMI", "HDMI 2.0", "E2 FRAME", "OUT 1", "SX40 A", "HDMI IN"),
    _cir("V004", "10GbE", "OpticalCON DUO", "SX40 A", "10G OUT 1", "XD 1", "10G IN"),
    _cir("V005", "DP1.2", "DisplayPort", "SRV 1", "DP OUT 1", "E2 FRAME", "IN 3"),
]


def _fx(ch, unit, addr, uni, pos, purpose, sym):
    return H(_record="Lighting Device", _layer="LX PLOT", Channel=ch,
             **{"Unit Number": unit},
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
    _fx("101", "10", "221", "2", "US TRUSS", "Specials",   "BMFL Blade"),  # dup channel 101
]

# Hanging Position PIOs. Fixtures carry a Position STRING field; the real
# association is the truss object the fixture hangs from, reachable via
# vs.OLDGetHangingPos (cat "Truss Analysis" in vs_index.json). Modeling both
# lets sl_positions cross-check by-field against by-parent — which is the whole
# point of that verb's disagreement report.
POSITIONS = [
    H(_record="Hanging Position", _layer="LX PLOT", Name="FOH TRUSS"),
    H(_record="Hanging Position", _layer="LX PLOT", Name="US TRUSS"),
]
_P = {p["Name"]: p for p in POSITIONS}

for _f in FIXTURES:
    _f["_hangpos"] = _P.get(_f.get("Position"))

_LAYERS = ["VIDEO SCHEM", "LX PLOT", "RACK LAYOUT"]

# Plug-in object name -> pool, used by ForEachObject / criteria matching.
_POOLS = {
    "Device": DEVICES,
    "Circuit": CIRCUITS,
    "Socket": [s for d in DEVICES for s in d["_sockets"]],
    "Lighting Device": FIXTURES,
    "Hanging Position": POSITIONS,
}

# type codes, mirroring commands.OBJ_TYPES
_TYPE_PLUGIN_OBJ = 68


# ── error helpers ───────────────────────────────────────────────────────────

class MockVSError(RuntimeError):
    """Raised by the mock when a switch says the real API would fail."""


def _null(what):
    if CONFIG['null_handle'] == 'raise':
        raise MockVSError('%s called with a nil handle' % what)
    return None


# ── document / layer API ────────────────────────────────────────────────────

def FLayer():
    return ("L", 0)


def NextLayer(h):
    if not isinstance(h, tuple):
        return _null('NextLayer')
    i = h[1] + 1
    return ("L", i) if i < len(_LAYERS) else None


def GetLName(h):
    if h is None:
        return _null('GetLName')
    return _LAYERS[h[1]] if isinstance(h, tuple) else h


def GetLayer(h):
    if h is None:
        return _null('GetLayer')
    return ("L", _LAYERS.index(h.get("_layer", _LAYERS[0])))


def GetVersionEx():
    return (31, 0, 1, 1, 800000)          # 31 = VW2026


def GetFName():
    return "demo-show.vwx"


def GetFPathName():
    return "C:/shows/demo-show.vwx"


def GetFileDirty():
    return False


# ── object identity ─────────────────────────────────────────────────────────

def GetObjectUuid(h):
    if h is None:
        return _null('GetObjectUuid')
    return h.get('_uuid')


def GetObjectByUuid(u):
    return _BY_UUID.get(str(u))


def GetName(h):
    """Object name — and, for a parametric record handle, the plug-in
    object name, which is what makes GetParametricRecord+GetName the PIO
    discriminator cc_commands relies on."""
    if h is None:
        return _null('GetName')
    return h.get('Name') or ''


def GetClass(h):
    if h is None:
        return _null('GetClass')
    return h.get('_class', 'None')


def GetTypeN(h):
    if h is None:
        return _null('GetTypeN')
    return h.get('_type', _TYPE_PLUGIN_OBJ)


def GetBBox(h):
    if h is None:
        return _null('GetBBox')
    return ((0.0, 0.0), (10.0, 10.0))


# ── criteria search ─────────────────────────────────────────────────────────

def _criteria_pon(criteria):
    """Extract the quoted plug-in-object name from a criteria string.

    Tolerates the shapes this repo's code uses:  PON='Device',
    (PON='Device'),  R IN ['Device'],  PON = 'Device'
    """
    s = str(criteria)
    for q in ("'", '"'):
        if q in s:
            parts = s.split(q)
            if len(parts) >= 2:
                return parts[1]
    return s.strip()


def _criteria_matches(criteria):
    """Objects matching a VW criteria string.

    Both discovery strategies in this repo must work:
      * cc_commands.py uses  PON='Device'      (index-assisted, name-dependent)
      * sl_commands.py uses  T=PLUGINOBJ       (type-based, name-independent)
        and                  T=RECDEF          (record-format definitions)
    A mock that only understood PON= made every sl_* verb return zero rows,
    which reads exactly like a plugin bug. It is not — do not "fix" that in
    sl_commands.py.
    """
    s = str(criteria).upper().replace(' ', '')
    if 'T=RECDEF' in s:
        return list(_PARAM_RECS.values())
    if 'T=PLUGINOBJ' in s:                       # covers T=PLUGINOBJECT too
        return (DEVICES + CIRCUITS + FIXTURES + POSITIONS
                + _POOLS['Socket'])
    return _POOLS.get(_criteria_pon(criteria), [])


def ForEachObject(callback, criteria):
    CRITERIA.append(str(criteria))
    for h in _criteria_matches(criteria):
        callback(h)


def ForEachObjectInLayer(callback, criteria, *a):
    return ForEachObject(callback, criteria)


# ── record access ───────────────────────────────────────────────────────────

def _field_exists(h, field):
    return field in h and not str(field).startswith('_')


def GetRField(h, record, field):
    """Read a record field.

    ``record`` is only enforced when CONFIG['strict_record'] is on: record
    names are TBV alongside field names.
    """
    if h is None:
        FIELD_READS.append((record, field, False))
        return _null('GetRField')
    if CONFIG['strict_record'] and h.get('_record') != record:
        FIELD_READS.append((record, field, False))
        raise MockVSError('object is not a %r record (it is %r)'
                          % (record, h.get('_record')))
    if _field_exists(h, field):
        FIELD_READS.append((record, field, True))
        return h[field]
    FIELD_READS.append((record, field, False))
    mode = CONFIG['missing_field']
    if mode == 'raise':
        raise MockVSError('no field %r on record %r' % (field, record))
    return '' if mode == 'empty' else None


def SetRField(h, record, field, value):
    if h is None:
        return _null('SetRField')
    h[field] = value
    return True


def ResetObject(h):
    return None if h is None else True


def GetRecord(h, index):
    if h is None:
        return _null('GetRecord')
    return h if index == 1 else None


def NumRecords(h):
    return 0 if h is None else 1


def GetName_Record(h):
    return None if h is None else h.get('_record')


def NumFields(rec):
    if rec is None:
        return _null('NumFields')
    return len([k for k in rec if not str(k).startswith('_')])


def GetFldName(rec, i):
    if rec is None:
        return _null('GetFldName')
    names = [k for k in rec if not str(k).startswith('_')]
    return names[i - 1] if 1 <= i <= len(names) else ''


# ── record-format field introspection ───────────────────────────────────────
# Used by the *_dump_records discovery verbs. Field TYPES here are mock values;
# nothing asserts them.

_FLD_TYPE_TEXT = 4          # VW's field-type code for a text field


def GetFldType(rec, i):
    if rec is None:
        return _null('GetFldType')
    return _FLD_TYPE_TEXT


def GetFldFlag(rec, i):
    if rec is None:
        return _null('GetFldFlag')
    return 0


def GetPluginStyle(h):
    """Style/unstyled state of a plug-in object. Mock objects are unstyled."""
    if h is None:
        return _null('GetPluginStyle')
    return 0


# ── document order / container walk ─────────────────────────────────────────
# The getters-absent fallback in cc_commands.py does NOT use ForEachObject
# alone — it unions a layer walk (FLayer/FInLayer/FInGroup/NextObj/NextLayer)
# with a document walk (FObject/NextObj) and discriminates objects by
# GetParametricRecord(h) -> GetName(rec). All four of those ARE in
# vs_index.json, so the mock must model them or the fallback path is only
# being tested against a hole in the mock.

def _link(chain):
    """Give a list of handles VW-style `_next` sibling pointers."""
    for a, b in zip(chain, chain[1:]):
        a['_next'] = b
    if chain:
        chain[-1]['_next'] = None
    return chain[0] if chain else None


# Top-level document objects, chained per layer (VW's NextObj stops at the
# end of the layer's list).
_LAYER_HEAD = {}
for _lname in _LAYERS:
    _members = [o for o in (DEVICES + CIRCUITS + FIXTURES + POSITIONS)
                if o.get('_layer') == _lname]
    _LAYER_HEAD[_lname] = _link(_members)

# Sockets are children of their device, chained among themselves.
for _d in DEVICES:
    _link(_d['_sockets'])


def FInLayer(layerH):
    if layerH is None:
        return _null('FInLayer')
    return _LAYER_HEAD.get(GetLName(layerH))


def FObject():
    """First object in the document. Overlaps the layer walk on purpose —
    cc_commands dedupes by UUID, and a mock that made the two roots disjoint
    would hide a dedupe bug."""
    return _LAYER_HEAD.get(_LAYERS[0])


def FInGroup(h):
    """First member of a container. For a Device that is its first socket —
    this is the walk a real implementation must use when CC_DeviceSockets does
    not exist."""
    if h is None:
        return _null('FInGroup')
    kids = h.get('_sockets') or []
    return kids[0] if kids else None


FIn3D = FInGroup


def NextObj(h):
    if h is None:
        return _null('NextObj')
    return h.get('_next')


def ParentShape(h):
    if h is None:
        return _null('ParentShape')
    return h.get('_parent')


# ── parametric record (the authoritative PIO discriminator) ─────────────────
# vs.GetParametricRecord(h) -> record handle; vs.GetName(rec) -> plug-in name.
# Both indexed in vs_index.json. This is how cc_commands identifies a Device /
# Circuit / Socket / Lighting Device without trusting a PON= criteria string.

_PARAM_RECS = {}
for _pon in ('Device', 'Circuit', 'Socket', 'Lighting Device',
             'Hanging Position'):
    _r = H(Name=_pon, _is_param_record=True)
    _PARAM_RECS[_pon] = _r


def GetParametricRecord(h):
    if h is None:
        return _null('GetParametricRecord')
    if h.get('_is_param_record'):
        return None
    return _PARAM_RECS.get(h.get('_record'))


# ── Spotlight LDevice_* family (vs_index.json cat "Spotlight") ─────────────
# LDevice_GetParamStr(h, cell, acc, universalName) addresses a Lighting Device
# field by its UNIVERSAL name, which is version- and localization-stable — a
# better primitive than GetRField for Spotlight. Universal names are TBV like
# everything else, so lookup here is spelling-tolerant: leading underscores,
# spaces and case are normalized away, plus an explicit alias table for the
# spellings that do not normalize onto the record field name.

def _norm_param(name):
    return str(name or '').replace('_', '').replace(' ', '').strip().lower()


# TBV. Maps a normalized universal name onto the fixture record field.
_UNIVERSAL_ALIASES = {
    'symname': 'Symbol Name',
    'symbolname': 'Symbol Name',
    'unitnum': 'Unit Number',
    'unitnumber': 'Unit Number',
    'dmxaddress': 'Address',
    'absoluteaddress': 'Address',
    'universenumber': 'Universe',
    'instrumenttype': 'Symbol Name',
    'userfield1': 'Purpose',
}


def _ldevice_field(h, universalName):
    """Resolve a universal parameter name to a value on a fixture handle."""
    want = _norm_param(universalName)
    target = _UNIVERSAL_ALIASES.get(want)
    if target is None:
        for k in h:
            if not str(k).startswith('_') and _norm_param(k) == want:
                target = k
                break
    if target is not None and target in h:
        FIELD_READS.append(('LDevice', universalName, True))
        return h[target]
    FIELD_READS.append(('LDevice', universalName, False))
    mode = CONFIG['missing_field']
    if mode == 'raise':
        raise MockVSError('no LDevice parameter %r' % (universalName,))
    return '' if mode == 'empty' else None


def LDevice_GetCellCount(h):
    if h is None:
        return _null('LDevice_GetCellCount')
    return 1 if h.get('_record') == 'Lighting Device' else 0


def LDevice_GetAccCount(h, cellIndex=0):
    if h is None:
        return _null('LDevice_GetAccCount')
    return 0


def LDevice_GetParamStr(h, cellIndex, accessoryIndex, universalName):
    if h is None:
        return _null('LDevice_GetParamStr')
    v = _ldevice_field(h, universalName)
    return '' if v is None and CONFIG['missing_field'] == 'empty' else v


def LDevice_GetParamLong(h, cellIndex, accessoryIndex, universalName):
    v = LDevice_GetParamStr(h, cellIndex, accessoryIndex, universalName)
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def LDevice_GetParamReal(h, cellIndex, accessoryIndex, universalName):
    v = LDevice_GetParamStr(h, cellIndex, accessoryIndex, universalName)
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def LDevice_GetParamBool(h, cellIndex, accessoryIndex, universalName):
    v = LDevice_GetParamStr(h, cellIndex, accessoryIndex, universalName)
    return bool(v) and str(v).strip().lower() not in ('0', 'false', '')


def LDevice_SetParamStr(h, cellIndex, accessoryIndex, universalName, newValue):
    if h is None:
        return _null('LDevice_SetParamStr')
    h[_UNIVERSAL_ALIASES.get(_norm_param(universalName), universalName)] = newValue
    return True


def LDevice_Reset(h):
    return None if h is None else True


def LDevice_ResetVisual(h):
    return None if h is None else True


# ── Truss Analysis: fixture -> hanging position ────────────────────────────

def OLDGetHangingPos(h, loadIndex=0):
    """Handle of the Hanging Position the given load is attached to.

    With CONFIG['hangpos_mismatch'] on, the first fixture is physically hung
    from a position OTHER than the one its Position field names — the real
    fault sl_positions' by_field/by_parent comparison exists to catch.
    """
    if h is None:
        return _null('OLDGetHangingPos')
    if CONFIG['hangpos_mismatch'] and h is FIXTURES[0]:
        return _P.get('US TRUSS')          # field says FOH TRUSS
    return h.get('_hangpos')


def OLDFindAttachHangPos(h, loadIndex=0):
    if h is None:
        return _null('OLDFindAttachHangPos')
    return h.get('_hangpos')


# ── switchable ConnectCAD getters ───────────────────────────────────────────
# NOT defined as module globals on purpose — module __getattr__ (PEP 562) gates
# them so `configure(cc_getters=False)` makes them genuinely absent, the way
# they are absent from vs_index.json.

def _CC_GetCircuitSource(h):
    if h is None:
        return _null('CC_GetCircuitSource')
    dev, skt = h["_src"]
    return (dev, skt, None, skt)


def _CC_GetCircuitDest(h):
    if h is None:
        return _null('CC_GetCircuitDest')
    dev, skt = h["_dst"]
    return (dev, skt, None, skt)


def _CC_GetDevice(hSocket, skip_adapters=True):
    if hSocket is None:
        return _null('CC_GetDevice')
    return hSocket.get("_parent")


def _CC_DeviceSockets(hDevice):
    # NOTE: this is NOT a documented vs function. The old scaffold pump called
    # vs.CC_DeviceSockets() and the old mock provided it, so the check passed
    # against an API that does not exist. Kept here ONLY behind the switch so
    # the legacy path still runs; the container walk above is the real fallback.
    if hDevice is None:
        return _null('CC_DeviceSockets')
    return hDevice["_sockets"]


_SWITCHED = {
    'CC_GetCircuitSource': _CC_GetCircuitSource,
    'CC_GetCircuitDest': _CC_GetCircuitDest,
    'CC_GetDevice': _CC_GetDevice,
    'CC_DeviceSockets': _CC_DeviceSockets,
    'CC_GetEquipmentItem': lambda h: None if h is None else h.get('_equip'),
}

# The six CC_* functions vs_index.json actually indexes. Always present.
def CC_CircuitFromShape(hObj):
    return _cir("VNEW", "TBD", "TBD", None, None, None, None)


def CC_DeviceFromShape(hObj):
    return _dev("NEW DEVICE", "", "", _LAYERS[0], [])


def CC_RouteFromShape(hObj):
    return H(_record="Cable Path", Name="NEW ROUTE")


def CC_RoomFromShape(hObj):
    return H(_record="Layout Room", Name="NEW ROOM")


def CC_OnFindAndReplace(hObject, fieldName, fieldValue):
    if hObject is not None:
        hObject[fieldName] = fieldValue
    return None


def CC_ReloadData():
    return None


# ConnectCAD data-table getters. Not in vs_index.json, not in any public doc,
# and per docs/ARCHITECTURE.md the table getters need VW2025.2+. The capability
# layer is SUPPOSED to probe these and get nothing — their absence is modeled
# behavior, not a hole in this mock, so they are reported separately.
KNOWN_ABSENT = frozenset({
    'CC_GetCableTypeData', 'CC_GetConnectorData', 'CC_GetSignalData',
    'CC_GetJackFieldData', 'CC_GetDeviceData',
})


def __getattr__(name):
    """PEP 562 module hook — reached only when a normal global lookup fails.

    Serves the switchable CC_* getters when they are configured present, and
    otherwise records the miss and raises AttributeError exactly like a real
    `vs` module missing that function.
    """
    if name in _SWITCHED and CONFIG['cc_getters']:
        return _SWITCHED[name]
    MISSES.append(name)
    raise AttributeError(
        "mock_vs has no attribute %r "
        "(cc_getters=%s; if this is a real vs function the mock needs it added)"
        % (name, CONFIG['cc_getters']))


def classify_misses():
    """Split MISSES into (modeled_absent, unmodeled).

    `modeled_absent` = the mock is deliberately withholding it (the capability
    switch, or a getter that does not exist in any known VW). Those are the
    fallback path working as designed.
    `unmodeled` = a real vs function this mock has not implemented. Every name
    here means a test result is being shaped by a MOCK GAP, not by the
    plugin's behavior — add it to mock_vs before trusting that result.
    """
    modeled, unmodeled = set(), set()
    for n in MISSES:
        if n in KNOWN_ABSENT or n in _SWITCHED:
            modeled.add(n)
        else:
            unmodeled.add(n)
    return sorted(modeled), sorted(unmodeled)


def implemented():
    """Names this mock currently exposes — for the harness's capability report."""
    names = sorted(k for k, v in globals().items()
                   if callable(v) and not k.startswith('_') and k[0].isupper())
    if CONFIG['cc_getters']:
        names += sorted(_SWITCHED)
    return sorted(set(names))
