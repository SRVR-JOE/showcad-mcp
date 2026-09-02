"""
cc_build.py — ConnectCAD BUILD primitives for the VW MCP Bridge.

NEW module. Does not touch `cc_commands.py`, `sl_commands.py` or `commands.py`;
those are owned elsewhere. Import it and merge `COMMANDS` the same way the
bridge merges `cc_commands.COMMANDS`.

────────────────────────────────────────────────────────────────────────────
WHAT IS AND IS NOT POSSIBLE — read this before trusting any output
────────────────────────────────────────────────────────────────────────────
Established live on VW 31.7.0.1; the long form is `domain/docs/CONNECT-
MECHANISM.md`.

DEVICES + SOCKETS: real, and provable.
    A Socket binds to a Device by being a DIRECT CHILD of the Device PIO.
    `vs.SetParent(socket, device)` returns False and `vs.BeginGroupN(device)`
    is ignored, so the ONLY way to put one there is `vs.HDuplicate` of a socket
    that is already inside that device. Hence the seed-and-clone design below.
    `vs.CC_GetDevice(socket, False) == device` proves it, and every device this
    module returns has been checked that way.

CIRCUITS: NOT bindable from this bridge. Not a missing API — a missing engine.
    ConnectCAD makes the circuit↔socket bind inside the Circuit PIO's
    recalculate. Plug-in-object regeneration does not run in the bridge's
    execution context (`vwx_mcp_bridge.py` dispatches from a
    `vs.RunLayoutDialog` timer callback). Stock VW PIOs — `Angle`,
    `Ball Bearing`, `Base Cabinet` — also come out with a zero bounding box
    here, so this is not ConnectCAD's doing.

    Writing `Src_Dev_Name` / `Src_Skt_Name` therefore produces a LABEL, not a
    connection: `__Src_ID` stays empty and `CC_GetCircuitSource` returns
    (nil,nil,nil,nil). `cc_make_circuit` still writes those fields — they are
    what the supported "Make Connections from List" command consumes — but it
    reports `verified: False`, always, until the oracle says otherwise.

    NEVER report a circuit as connected on the strength of its record fields.

DO NOT try to force regeneration from here. `vs.SetLayerScale`,
`vs.UpdatePIOFromStyle()` and friends, invoked from the bridge context, took
Vectorworks down mid-script during this investigation.

────────────────────────────────────────────────────────────────────────────
Record namespaces (verified live — the cases genuinely differ per record)
────────────────────────────────────────────────────────────────────────────
    Device : lowercase   name make model tag type loc_rack loc_rackU user1..8
    Socket : lowercase   type name tag signal connector n_circuits Orientation
                         ConnSymbol TextSymbol IsTerminated cablenum
    Circuit: CamelCase   Number Cable Signal 'Cable Type'
                         Src_Dev_Name Src_Skt_Name Src_Signal Src_Skt_Conn
                         Dst_Dev_Name Dst_Skt_Name Dst_Signal Dst_Skt_Conn
                         __Src_ID __Dst_ID __ISNEW __RECONNECT

Socket direction lives in `type` ('IN' / 'OUT' / 'IO'), not in a Direction
field. `ConnSymbol` and `TextSymbol` are PREFIXES: ConnSymbol + type and
TextSymbol + Orientation must name symbols present in the document.

Every vs.* signature used here was checked against `vwx-plugin/vs_index.json`;
see VS_USED at the bottom.

────────────────────────────────────────────────────────────────────────────
VERIFICATION STATUS — be precise about this
────────────────────────────────────────────────────────────────────────────
The MECHANISM in `cc_make_device` was verified live, step by step: seed
HDuplicate → SetParent to layer → field writes → socket HDuplicate → field
writes → `CC_GetDevice(socket) == device` returning True for every socket.

This MODULE, as assembled, has NOT been executed end to end against
Vectorworks. VW terminated during the investigation (see
CONNECT-MECHANISM.md §3.4) and the bridge can only be restarted by hand
from inside the application. Run it against a scratch document first and
check that `cc_make_device(...)['verified']` is True before trusting it.
"""

import traceback

try:
    import vs
except ImportError:                    # importable outside Vectorworks
    vs = None


# ── constants ───────────────────────────────────────────────────────────────

PON_DEVICE  = 'Device'
PON_SOCKET  = 'Socket'
PON_CIRCUIT = 'Circuit'

REC_DEVICE  = 'Device'
REC_SOCKET  = 'Socket'
REC_CIRCUIT = 'Circuit'

TYPE_PLUGIN = 86                       # GetTypeN for every PIO
TYPE_LAYER  = 31
RSRC_SYMBOL = 16                       # BuildResourceListN resource type

_LIB = '/Applications/Vectorworks 2026/Libraries/'

# Seeds, in preference order. Only these two shipped symbols contain a Device
# PIO that already holds a Socket; `Basic Device`, `Basic Distributor`,
# `Basic Lighting Device` and `DAdevice` all hold zero and cannot seed.
SEED_SYMBOLS = (
    ('VidJack2', _LIB + 'ConnectCAD/Samples/Sample Worksheets.vwx'),
    ('VidTP',    _LIB + 'Defaults/ConnectCAD/Panels/Panels.vwx'),
)

# Socket connector/text symbols. Prefix + type / prefix + Orientation.
SOCKET_SYMBOL_SOURCES = (
    _LIB + 'ConnectCAD/Samples/Sample Worksheets.vwx',   # skt_con_IN/OUT/IO, skt_txt_L/R
    _LIB + 'Defaults/ConnectCAD/External/External.vwx',  # skt_txt_L/R
)
CONN_SYMBOL_PREFIX = 'skt_con_'
TEXT_SYMBOL_PREFIX = 'skt_txt_'
_WANTED_SYMBOLS = ('skt_con_IN', 'skt_con_OUT', 'skt_con_IO',
                   'skt_txt_L', 'skt_txt_R', 'dev_label_generic')

DEVICE_NAME_PREFIX = '<DEV>'           # ConnectCAD's own convention


# ── plumbing ────────────────────────────────────────────────────────────────

def _guard(fn):
    """Never raise into Vectorworks; a traceback beats a dead bridge."""
    def wrapped(*a, **kw):
        try:
            return fn(*a, **kw)
        except Exception as exc:
            return {'status': 'error', 'error': '%s: %s' % (type(exc).__name__, exc),
                    'traceback': traceback.format_exc()[-2000:]}
    wrapped.__name__ = getattr(fn, '__name__', 'wrapped')
    wrapped.__doc__ = fn.__doc__
    return wrapped


def _pon(h):
    """Plug-in-object name of h, or '' — PIO name == record name for CC objects."""
    if not h:
        return ''
    try:
        rec = vs.GetParametricRecord(h)
        return vs.GetName(rec) if rec else ''
    except Exception:
        return ''


def _children(h):
    out = []
    try:
        c = vs.FInGroup(h)
    except Exception:
        return out
    while c:
        out.append(c)
        c = vs.NextObj(c)
    return out


def device_sockets(hdev):
    """Direct Socket children of a Device PIO.

    Replaces the non-existent `vs.CC_DeviceSockets`. Direct children only —
    the Top/Plan component group holds a duplicate set that must not be
    counted or edited.
    """
    return [c for c in _children(hdev) if _pon(c) == PON_SOCKET]


def _layer_objects(pon_filter=None):
    out = []
    h = vs.FActLayer()
    while h:
        if pon_filter is None or _pon(h) == pon_filter:
            out.append(h)
        h = vs.NextObj(h)
    return out


def _world_offset(hdev):
    """Children of a PIO are in its local frame; this is local → world.

    Confirmed equal to the translation of `vs.GetEntityMatrix(hdev)`.
    """
    return vs.GetSymLoc(hdev)


# ── resource import ─────────────────────────────────────────────────────────

def _import_symbol(name, path):
    """Import one symbol definition from a file without opening it."""
    existing = vs.GetObject(name)
    if existing:
        return existing
    res = vs.BuildResourceListN(RSRC_SYMBOL, path)
    list_id, count = res[0], res[1]
    for i in range(1, count + 1):
        if vs.GetNameFromResourceList(list_id, i) == name:
            return vs.ImportResourceToCurrentFile(list_id, i)
    return None


def ensure_socket_symbols():
    """Make sure skt_con_* / skt_txt_* exist. A socket without them draws nothing."""
    got = {}
    for name in _WANTED_SYMBOLS:
        if vs.GetObject(name):
            got[name] = 'present'
            continue
        for path in SOCKET_SYMBOL_SOURCES:
            if _import_symbol(name, path):
                got[name] = 'imported'
                break
        else:
            got[name] = 'MISSING'
    return got


def _seed_device():
    """A Device PIO that already contains ≥1 Socket, to clone from.

    Prefers one already on the layer (cheaper, and keeps the document tidy);
    otherwise imports a shipped symbol and reads the device out of its
    definition. The definition is never modified — HDuplicate reads it only.
    """
    for hdev in _layer_objects(PON_DEVICE):
        if device_sockets(hdev):
            return hdev, 'layer'
    for name, path in SEED_SYMBOLS:
        sym = _import_symbol(name, path)
        if not sym:
            continue
        for child in _children(sym):
            if _pon(child) == PON_DEVICE and device_sockets(child):
                return child, 'symbol:' + name
    return None, None


# ── device + sockets ────────────────────────────────────────────────────────

@_guard
def cc_make_device(name, make='', model='', x=0.0, y=0.0, sockets=None,
                   tag=None, dev_type='Generic', label_symbol='dev_label_generic',
                   socket_pitch=None):
    """Create a ConnectCAD Device with sockets genuinely attached to it.

    sockets: list of dicts. Recognised keys — every one optional:
        name, tag, type ('IN'|'OUT'|'IO'), signal, connector,
        n_circuits, Orientation ('L'|'R'), user1..user8
    At least one socket must be requested; a device with none needs no seed and
    would be better made with `vs.CC_DeviceFromShape`.

    Returns {'status','verified','device','sockets',...}. `verified` is True
    only when `CC_GetDevice` returns this device for EVERY socket created.
    """
    sockets = list(sockets or [])
    if not sockets:
        return {'status': 'error', 'verified': False,
                'error': 'cc_make_device needs at least one socket; use '
                         'CC_DeviceFromShape for a bare device'}

    vs.NameUndoEvent('MCP: create ConnectCAD device %s' % name)
    syms = ensure_socket_symbols()

    seed, seed_from = _seed_device()
    if not seed:
        return {'status': 'error', 'verified': False,
                'error': 'no seed device available — every shipped Device symbol '
                         'with sockets was unreachable',
                'searched': [s[1] for s in SEED_SYMBOLS], 'symbols': syms}

    hdev = vs.HDuplicate(seed, 0, 0)            # lands in the seed's container
    if not hdev:
        return {'status': 'error', 'verified': False,
                'error': 'HDuplicate of the seed device returned nil'}
    # device → layer is the direction of SetParent that works
    if vs.GetTypeN(vs.GetParent(hdev)) != TYPE_LAYER:
        if not vs.SetParent(hdev, vs.ActLayer()):
            vs.DelObject(hdev)
            return {'status': 'error', 'verified': False,
                    'error': 'SetParent(device, layer) failed; device left nowhere'}

    vs.SetName(hdev, DEVICE_NAME_PREFIX + vs.CreateUUID())
    for field, value in (('name', name), ('tag', tag if tag is not None else name),
                         ('make', make), ('model', model), ('type', dev_type),
                         ('symbol', label_symbol)):
        vs.SetRField(hdev, REC_DEVICE, field, value)

    # Grow / shrink the inherited socket set to the requested count.
    live = device_sockets(hdev)
    if not live:
        vs.DelObject(hdev)
        return {'status': 'error', 'verified': False,
                'error': 'cloned device arrived with no sockets (seed=%s)' % seed_from}
    pitch = socket_pitch if socket_pitch is not None else 0.0
    while len(live) < len(sockets):
        dup = vs.HDuplicate(live[0], 0.0, -pitch * len(live))
        if not dup:
            break
        live.append(dup)
    for extra in live[len(sockets):]:
        vs.DelObject(extra)
    live = live[:len(sockets)]

    if len(live) != len(sockets):
        vs.DelObject(hdev)
        return {'status': 'error', 'verified': False,
                'error': 'could not reach %d sockets (got %d)' % (len(sockets), len(live))}

    for hskt, spec in zip(live, sockets):
        vs.SetName(hskt, vs.CreateUUID())
        for field in ('name', 'tag', 'type', 'signal', 'connector', 'n_circuits',
                      'Orientation', 'cablenum',
                      'user1', 'user2', 'user3', 'user4',
                      'user5', 'user6', 'user7', 'user8'):
            if field in spec:
                vs.SetRField(hskt, REC_SOCKET, field, str(spec[field]))
        vs.SetRField(hskt, REC_SOCKET, 'ConnSymbol', CONN_SYMBOL_PREFIX)
        vs.SetRField(hskt, REC_SOCKET, 'TextSymbol', TEXT_SYMBOL_PREFIX)
        vs.ResetObject(hskt)
    vs.ResetObject(hdev)

    # Position by the device's top-left corner, so callers can lay out a grid.
    lo, _hi = vs.GetBBox(hdev)
    vs.HMove(hdev, x - lo[0], y - lo[1])

    # ── verify against the oracle ──────────────────────────────────────────
    checks = []
    for hskt in device_sockets(hdev):
        owner = vs.CC_GetDevice(hskt, False)
        checks.append({'name': vs.GetRField(hskt, REC_SOCKET, 'name'),
                       'id': vs.GetName(hskt),
                       'type': vs.GetRField(hskt, REC_SOCKET, 'type'),
                       'signal': vs.GetRField(hskt, REC_SOCKET, 'signal'),
                       'bound': bool(owner) and str(owner) == str(hdev)})
    verified = bool(checks) and all(c['bound'] for c in checks)

    return {'status': 'ok', 'verified': verified,
            'device': {'handle': str(hdev), 'id': vs.GetName(hdev), 'name': name,
                       'make': make, 'model': model, 'bbox': vs.GetBBox(hdev)},
            'sockets': checks,
            'seed': seed_from, 'symbols': syms,
            'oracle': 'CC_GetDevice(socket, False) == device'}


# ── circuits ────────────────────────────────────────────────────────────────

def _find_device(dev_name):
    for hdev in _layer_objects(PON_DEVICE):
        if vs.GetRField(hdev, REC_DEVICE, 'name') == dev_name:
            return hdev
    return None


def _find_socket(hdev, skt_name):
    for hskt in device_sockets(hdev):
        if vs.GetRField(hskt, REC_SOCKET, 'name') == skt_name:
            return hskt
    return None


def _socket_world_bbox(hdev, hskt):
    ox, oy = _world_offset(hdev)
    lo, hi = vs.GetBBox(hskt)
    return (lo[0] + ox, lo[1] + oy, hi[0] + ox, hi[1] + oy)


@_guard
def cc_make_circuit(src_dev, src_skt, dst_dev, dst_skt, signal='', number='',
                    cable_type=None):
    """Create a Circuit between two named device sockets.

    HONEST CONTRACT: this returns `verified: False` on this bridge, every time.
    The circuit object is real, its endpoints sit on the two sockets and its
    Src_*/Dst_* fields are filled — but `CC_GetCircuitSource` reports no
    binding, because ConnectCAD makes the binding inside the Circuit PIO's
    recalculate and plug-in-object regeneration does not run in the bridge's
    execution context (see the module docstring and
    `domain/docs/CONNECT-MECHANISM.md` §3).

    So treat the result as DRAFT GEOMETRY plus a row for the circuit list.
    To obtain real bindings, feed the same rows to ConnectCAD's
    "Make Connections from List" and have an operator run it once.

    `verified` flips to True on its own the day regeneration works — the check
    below is a live `CC_GetCircuitSource` call, not a constant.
    """
    vs.NameUndoEvent('MCP: create ConnectCAD circuit %s' % (number or ''))

    hsrc_dev = _find_device(src_dev)
    hdst_dev = _find_device(dst_dev)
    if not hsrc_dev or not hdst_dev:
        return {'status': 'error', 'verified': False,
                'error': 'device not found: %s' % (
                    src_dev if not hsrc_dev else dst_dev)}
    hsrc = _find_socket(hsrc_dev, src_skt)
    hdst = _find_socket(hdst_dev, dst_skt)
    if not hsrc or not hdst:
        return {'status': 'error', 'verified': False,
                'error': 'socket not found: %s' % (
                    ('%s/%s' % (src_dev, src_skt)) if not hsrc
                    else ('%s/%s' % (dst_dev, dst_skt)))}

    ax1, ay1, ax2, ay2 = _socket_world_bbox(hsrc_dev, hsrc)
    bx1, by1, bx2, by2 = _socket_world_bbox(hdst_dev, hdst)
    # Leave from the side facing the destination, arrive on the facing side.
    a_left = (ax1 + ax2) / 2.0 <= (bx1 + bx2) / 2.0
    ax = ax2 if a_left else ax1
    bx = bx1 if a_left else bx2
    ay = (ay1 + ay2) / 2.0
    by = (by1 + by2) / 2.0

    vs.MoveTo(ax, ay)
    vs.LineTo(bx, by)
    hline = vs.LNewObj()
    hcir = vs.CC_CircuitFromShape(hline)
    # CC_CircuitFromShape COPIES the line into the circuit (GetCustomObjectPath
    # returns a different handle), so removing the original is safe and stops
    # the drawing accumulating orphan geometry.
    vs.DelObject(hline)
    if not hcir:
        return {'status': 'error', 'verified': False,
                'error': 'CC_CircuitFromShape returned nil'}

    vs.SetName(hcir, vs.CreateUUID())
    pairs = [('Src_Dev_Name', src_dev), ('Src_Skt_Name', src_skt),
             ('Src_Dev_Tag', vs.GetRField(hsrc_dev, REC_DEVICE, 'tag')),
             ('Src_Skt_Tag', vs.GetRField(hsrc, REC_SOCKET, 'tag')),
             ('Src_Signal', vs.GetRField(hsrc, REC_SOCKET, 'signal')),
             ('Src_Skt_Conn', vs.GetRField(hsrc, REC_SOCKET, 'connector')),
             ('Dst_Dev_Name', dst_dev), ('Dst_Skt_Name', dst_skt),
             ('Dst_Dev_Tag', vs.GetRField(hdst_dev, REC_DEVICE, 'tag')),
             ('Dst_Skt_Tag', vs.GetRField(hdst, REC_SOCKET, 'tag')),
             ('Dst_Signal', vs.GetRField(hdst, REC_SOCKET, 'signal')),
             ('Dst_Skt_Conn', vs.GetRField(hdst, REC_SOCKET, 'connector')),
             ('Signal', signal or vs.GetRField(hsrc, REC_SOCKET, 'signal')),
             ('Number', str(number))]
    if cable_type is not None:
        pairs.append(('Cable Type', cable_type))
    for field, value in pairs:
        vs.SetRField(hcir, REC_CIRCUIT, field, value)
    vs.ResetObject(hcir)

    src = vs.CC_GetCircuitSource(hcir) or (None, None, None, None)
    dst = vs.CC_GetCircuitDest(hcir) or (None, None, None, None)
    src_ok = bool(src[0]) and str(src[0]) == str(hsrc_dev) and \
        bool(src[1]) and str(src[1]) == str(hsrc)
    dst_ok = bool(dst[0]) and str(dst[0]) == str(hdst_dev) and \
        bool(dst[1]) and str(dst[1]) == str(hdst)
    verified = src_ok and dst_ok

    out = {'status': 'ok', 'verified': verified,
           'circuit': {'handle': str(hcir), 'id': vs.GetName(hcir),
                       'number': str(number), 'signal': signal},
           'endpoints': {'src': [src_dev, src_skt, [ax, ay]],
                         'dst': [dst_dev, dst_skt, [bx, by]]},
           'oracle': {'CC_GetCircuitSource_device': bool(src[0]),
                      'CC_GetCircuitSource_socket': bool(src[1]),
                      'CC_GetCircuitDest_device': bool(dst[0]),
                      'CC_GetCircuitDest_socket': bool(dst[1]),
                      '__Src_ID': vs.GetRField(hcir, REC_CIRCUIT, '__Src_ID'),
                      '__Dst_ID': vs.GetRField(hcir, REC_CIRCUIT, '__Dst_ID'),
                      '__ISNEW': vs.GetRField(hcir, REC_CIRCUIT, '__ISNEW')}}
    if not verified:
        out['warning'] = (
            'NOT CONNECTED. The record fields are set and the line is drawn, '
            'but CC_GetCircuitSource reports no binding and __Src_ID is empty. '
            'Do not present this as wired. Cause: plug-in-object regeneration '
            'does not run in the bridge context — see '
            'domain/docs/CONNECT-MECHANISM.md §3.')
        out['bulk_path'] = (
            'Export these rows to a worksheet and run ConnectCAD > '
            'Make Connections from List once, by hand.')
    return out


@_guard
def cc_verify_document():
    """Re-check every device, socket and circuit on the active layer.

    Cheap enough to run after a build and after any human step (such as
    "Make Connections from List"), and the only honest way to learn that a
    circuit became connected.
    """
    devices, circuits = [], []
    for hdev in _layer_objects(PON_DEVICE):
        skts = []
        for hskt in device_sockets(hdev):
            owner = vs.CC_GetDevice(hskt, False)
            skts.append({'name': vs.GetRField(hskt, REC_SOCKET, 'name'),
                         'type': vs.GetRField(hskt, REC_SOCKET, 'type'),
                         'bound': bool(owner) and str(owner) == str(hdev)})
        devices.append({'name': vs.GetRField(hdev, REC_DEVICE, 'name'),
                        'handle': str(hdev), 'sockets': skts,
                        'all_bound': bool(skts) and all(s['bound'] for s in skts)})
    for hcir in _layer_objects(PON_CIRCUIT):
        src = vs.CC_GetCircuitSource(hcir) or (None, None, None, None)
        dst = vs.CC_GetCircuitDest(hcir) or (None, None, None, None)
        circuits.append({'number': vs.GetRField(hcir, REC_CIRCUIT, 'Number'),
                         'label_src': '%s/%s' % (
                             vs.GetRField(hcir, REC_CIRCUIT, 'Src_Dev_Name'),
                             vs.GetRField(hcir, REC_CIRCUIT, 'Src_Skt_Name')),
                         'label_dst': '%s/%s' % (
                             vs.GetRField(hcir, REC_CIRCUIT, 'Dst_Dev_Name'),
                             vs.GetRField(hcir, REC_CIRCUIT, 'Dst_Skt_Name')),
                         'connected': bool(src[0] and src[1] and dst[0] and dst[1])})
    return {'status': 'ok',
            'devices': devices, 'circuits': circuits,
            'sockets_verified': all(d['all_bound'] for d in devices) if devices else None,
            'circuits_verified': all(c['connected'] for c in circuits) if circuits else None}


@_guard
def cc_clear_document():
    """Delete every top-level object on the active layer. Scratch files only."""
    vs.NameUndoEvent('MCP: clear layer')
    doomed = []
    h = vs.FActLayer()
    while h:
        doomed.append(h)
        h = vs.NextObj(h)
    for h in doomed:
        vs.DelObject(h)
    return {'status': 'ok', 'deleted': len(doomed)}


COMMANDS = {
    'cc_make_device':     cc_make_device,
    'cc_make_circuit':    cc_make_circuit,
    'cc_verify_document': cc_verify_document,
    'cc_clear_document':  cc_clear_document,
}


# Every vs.* used above, with the signature from vwx-plugin/vs_index.json.
VS_USED = """
ActLayer()                                  -> HANDLE
BuildResourceListN(type, fullPath)
CC_CircuitFromShape(hObj)                   -> HANDLE
CC_GetCircuitDest(h)                        -> (device, devSocket, adapter, socket)
CC_GetCircuitSource(h)                      -> (device, devSocket, adapter, socket)
CC_GetDevice(hSocket, skipAdapters)         -> HANDLE
CreateUUID()                                -> STRING      '{GUID}' form
DelObject(h)
FActLayer()                                 -> HANDLE
FInGroup(ObjectHd)                          -> HANDLE
GetBBox(h)                                  -> (lo, hi)
GetName(h)                                  -> STRING
GetNameFromResourceList(listID, index)      -> STRING
GetObject(name)                             -> HANDLE
GetParametricRecord(h)                      -> HANDLE
GetParent(h)                                -> HANDLE
GetRField(h, record, field)                 -> STRING
GetSymLoc(symHd)                            -> (x, y)      PIO local->world offset
GetTypeN(h)                                 -> INTEGER     86 = any PIO
HDuplicate(objectHandle, x, y)              -> HANDLE      the ONLY way into a PIO
HMove(h, xOffset, yOffset)
ImportResourceToCurrentFile(listID, index)  -> HANDLE
LNewObj()                                   -> HANDLE
LineTo(p) / MoveTo(p)
NameUndoEvent(eventName)
NextObj(h)                                  -> HANDLE
ResetObject(objectHandle)
SetName(h, name)
SetParent(obj, container)                   -> BOOLEAN     PIO->layer only
SetRField(h, record, field, value)
"""
