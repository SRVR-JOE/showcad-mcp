"""
cc_commands.py — ConnectCAD READ-ONLY verbs for the VW MCP Bridge.

Owned by the ConnectCAD agent. `commands.py` is owned by the bridge agent and
is NOT edited from here; a bridge-side registry imports this module and merges
the verbs in COMMANDS below.

────────────────────────────────────────────────────────────────────────────
WHY THIS MODULE HAS A CAPABILITY LAYER
────────────────────────────────────────────────────────────────────────────
docs/RESEARCH.md §2 claims a family of ConnectCAD getters exists since
VW2025/2025.2:  CC_GetCircuitSource, CC_GetCircuitDest, CC_GetDevice,
CC_GetEquipmentItem, CC_GetSignalData, CC_GetCableTypeData, CC_GetConnectorData.

vs_index.json (3071 entries, built by tools/build_vs_index.py from the SDK
vs.py stub) contains exactly SIX CC_* functions and NONE of those getters:

    CC_CircuitFromShape(hObj)                       -> HANDLE
    CC_DeviceFromShape(hObj)                        -> HANDLE
    CC_RouteFromShape(hObj)                         -> HANDLE
    CC_RoomFromShape(hObj)                          -> HANDLE
    CC_OnFindAndReplace(hObject, fieldName, fieldValue)
    CC_ReloadData()

Either the index is stale or the research is wrong; that is UNRESOLVED and will
be settled empirically against live VW2026. Additionally
`domain/reference_handlers.py` calls `vs.CC_DeviceSockets(h)`, which appears in
NO source at all — it is a placeholder the reference file itself flags.

Therefore every ConnectCAD API call in this module goes through `_cc(name)`,
which resolves the function at RUNTIME via getattr. Each consumer has a
documented fallback that uses only APIs verified present in vs_index.json.
Verbs report which path they took in `_meta.mode` so the live run tells us
which world we are in.

────────────────────────────────────────────────────────────────────────────
TWO NAMESPACES, KEPT SEPARATE ON PURPOSE
────────────────────────────────────────────────────────────────────────────
`domain/reference_handlers.py` uses the same literals ("Device", "Circuit",
"Socket") as BOTH a `PON=` criteria value in `_collect()` AND a record-format
name in `GetRField()`. Those are different namespaces in Vectorworks:

    PON_*  = plug-in-object name   (ForEachObject "PON='...'" criteria)
    REC_*  = record-format name    (GetRField(h, record, field))

They are declared separately below so `cc_dump_records` can correct either one
independently once it runs against a real document.

────────────────────────────────────────────────────────────────────────────
TBV
────────────────────────────────────────────────────────────────────────────
Anything marked `# TBV` (to be verified) is an unverified name — a PIO name, a
record-format name, or a record field name. None of them are confirmed until
`cc_dump_records` runs on a live ConnectCAD document (docs/TASKS.md T1.2).
No vs.* SIGNATURE in this file is guessed: every one was checked against
vs_index.json (see VS_USED at the bottom).

READ-ONLY. This module contains no mutation verbs. Writes are Phase 3.
Nothing here raises into Vectorworks: every verb is wrapped by `_guard`.
"""

import traceback

try:
    import vs  # only exists inside Vectorworks
except ImportError:  # pragma: no cover - exercised by tests
    vs = None


def set_vs(module):
    """Test hook: inject a mock `vs` (domain/tests/mock_vs.py) outside VW."""
    global vs
    vs = module


# ── namespace constants ─────────────────────────────────────────────────────
# Plug-in-object names — the ForEachObject "PON='...'" criteria namespace.
PON_DEVICE = 'Device'            # TBV
PON_CIRCUIT = 'Circuit'          # TBV
PON_SOCKET = 'Socket'            # TBV
PON_EQUIPMENT = 'Equipment Item'  # TBV
PON_ADAPTER = 'Adapter'          # TBV

# Record-format names — the GetRField(h, record, field) namespace.
# For a PIO, the parametric record name is normally the same string as the PIO
# name, but that is an assumption; cc_dump_records reports both so the two can
# diverge without breaking anything.
REC_DEVICE = 'Device'            # TBV
REC_CIRCUIT = 'Circuit'          # TBV
REC_SOCKET = 'Socket'            # TBV
REC_EQUIPMENT = 'Equipment Item'  # TBV
REC_ADAPTER = 'Adapter'          # TBV

# The five PIO types T1.2 must census, in (pon, rec) pairs.
CC_TYPES = (
    (PON_DEVICE, REC_DEVICE),
    (PON_CIRCUIT, REC_CIRCUIT),
    (PON_SOCKET, REC_SOCKET),
    (PON_EQUIPMENT, REC_EQUIPMENT),
    (PON_ADAPTER, REC_ADAPTER),
)

# Record field names. ALL TBV — corrected by cc_dump_records (T1.2).
F_DEV_NAME = 'Name'              # TBV
F_DEV_MAKE = 'Make'              # TBV
F_DEV_MODEL = 'Model'            # TBV
F_SKT_NAME = 'Name'              # TBV
F_SKT_DIR = 'Direction'          # TBV
F_CIR_NUMBER = 'Number'          # TBV
F_CIR_SIGNAL = 'Signal'          # TBV
F_CIR_CABLE = 'Cable Type'       # TBV

# Circuit endpoint fields used ONLY by the record-join fallback (when the
# CC_GetCircuit* getters are absent). Several plausible spellings are tried in
# order and the first non-empty one wins; the winner is reported in
# `_meta.join_fields` so the live run tells us the real names. ALL TBV.
F_CIR_SRC_DEV = ('Source Device', 'From Device', 'Src Device')      # TBV
F_CIR_SRC_SKT = ('Source Socket', 'From Socket', 'Src Socket')      # TBV
F_CIR_DST_DEV = ('Destination Device', 'To Device', 'Dest Device')  # TBV
F_CIR_DST_SKT = ('Destination Socket', 'To Socket', 'Dest Socket')  # TBV

# vs.GetTypeN() index for a plug-in object (per commands.py OBJ_TYPES).
TYPE_PLUGIN_OBJ = 68

# GetFldType() integer -> name. TBV: vs_index.json documents the call but not
# the constant table, so the raw int is always emitted alongside this guess.
FLD_TYPE_NAMES_TBV = {
    1: 'integer', 2: 'boolean', 3: 'real', 4: 'text',
    5: 'number', 6: 'date', 7: 'popup', 8: 'radio', 9: 'checkbox',
}

MAX_OBJECTS = 20000   # whole-document walk guard
MAX_DEPTH = 12        # container recursion guard
MAX_VALUE_LEN = 400   # truncate dumped field values
TRACE_DEPTH = 32      # signal-trace depth guard (from reference impl)


# ── infrastructure ──────────────────────────────────────────────────────────
def _safe(fn, default=None):
    """Call fn(), swallowing anything. Mirrors commands.py `_safe`."""
    try:
        return fn()
    except Exception:
        return default


def _oid(h):
    """Object UUID string, or None. Mirrors commands.py `_oid`."""
    if not h:
        return None
    return _safe(lambda: vs.GetObjectUuid(h)) or None


def _s(v):
    """Normalise a VW return to a stripped str, or None if empty."""
    if v is None:
        return None
    if isinstance(v, (tuple, list)):
        v = v[0] if v else None
        if v is None:
            return None
    try:
        t = str(v).strip()
    except Exception:
        return None
    return t or None


def _clip(v):
    t = _s(v)
    if t is not None and len(t) > MAX_VALUE_LEN:
        return t[:MAX_VALUE_LEN] + '…'
    return t


def _guard(fn):
    """Wrap a verb so it returns {'error': ...} instead of raising into VW."""
    def wrapper(p=None):
        if vs is None:
            return {'error': 'vs module unavailable (not running inside Vectorworks)'}
        try:
            return fn(p or {})
        except Exception as e:
            return {'error': '%s: %s: %s' % (fn.__name__, e.__class__.__name__, e),
                    'trace': traceback.format_exc()[-1500:]}
    wrapper.__name__ = fn.__name__
    wrapper.__doc__ = fn.__doc__
    return wrapper


# ── capability layer ────────────────────────────────────────────────────────
# The ONLY place ConnectCAD-specific APIs are resolved. Nothing else in this
# module may touch vs.CC_* directly.

CC_API_NAMES = (
    # verified present in vs_index.json (all six are creators/mutators, so this
    # module resolves them for reporting only and calls none of them)
    'CC_CircuitFromShape', 'CC_DeviceFromShape', 'CC_RouteFromShape',
    'CC_RoomFromShape', 'CC_OnFindAndReplace', 'CC_ReloadData',
    # claimed by RESEARCH.md §2, ABSENT from vs_index.json — probed at runtime
    'CC_GetCircuitSource', 'CC_GetCircuitDest', 'CC_GetDevice',
    'CC_GetEquipmentItem', 'CC_GetSignalData', 'CC_GetCableTypeData',
    'CC_GetConnectorData',
    # in no source at all; reference_handlers.py placeholder, probed anyway
    'CC_DeviceSockets',
)


def _cc(name):
    """Resolve vs.<name> at runtime, or None if this VW does not expose it."""
    if vs is None:
        return None
    fn = getattr(vs, name, None)
    return fn if callable(fn) else None


def _cc_available(name):
    """True if the running Vectorworks exposes vs.<name>."""
    return _cc(name) is not None


def _capabilities():
    """Availability map for every ConnectCAD API this module might use."""
    return dict((n, _cc_available(n)) for n in CC_API_NAMES)


# ── object walking (verified APIs only) ─────────────────────────────────────
def _pio_name(h):
    """Plug-in-object name of `h` via its parametric record, or None.

    vs.GetParametricRecord(h) -> HANDLE  and  vs.GetName(rec) -> STRING are
    both verified. For a PIO the parametric record's name IS the plug-in name,
    which is what makes this the authoritative discriminator — it needs no
    criteria-string guessing.
    """
    rec = _safe(lambda: vs.GetParametricRecord(h))
    if not rec:
        return None
    return _s(_safe(lambda: vs.GetName(rec)))


def _key(h):
    """Dedupe key for a handle: its UUID, else its Python identity."""
    return _oid(h) or ('id:%d' % id(h))


def _all_objects(limit=MAX_OBJECTS, seeds=()):
    """Deduped list of document objects, gathered from independent roots.

    `cc_dump_records` is the first verb that will ever run against a live
    document, so enumeration must not hinge on a single call succeeding. Three
    independent, individually-verified roots are unioned and deduped by UUID:

      1. layer walk   FLayer -> FInLayer -> NextObj, then NextLayer
      2. document walk FObject -> NextObj   ("first object in the active
         document" — independent of the layer list)
      3. caller seeds  handles already collected some other way (e.g. by
         ForEachObject criteria), so a walk that returns nothing still yields
         a useful census

    Each root recurses into containers with FInGroup, depth-guarded.
    Read-only: nothing is created, deleted or re-layered, and the walk only
    appends inside the ForEachObject callback (per commands.py's rule).

    Returns (handles, sources_that_produced_something).
    """
    out, seen, sources = [], set(), []

    def add(h):
        if h is None or len(out) >= limit:
            return False
        k = _key(h)
        if k in seen:
            return False
        seen.add(k)
        out.append(h)
        return True

    def descend(h, depth):
        while h and len(out) < limit:
            fresh = add(h)
            if fresh and depth < MAX_DEPTH:
                child = _safe(lambda h=h: vs.FInGroup(h))
                if child:
                    descend(child, depth + 1)
            h = _safe(lambda h=h: vs.NextObj(h))

    before = len(out)
    layer = _safe(lambda: vs.FLayer())
    guard = 0
    while layer and len(out) < limit and guard < 5000:
        guard += 1
        descend(_safe(lambda l=layer: vs.FInLayer(l)), 0)
        layer = _safe(lambda l=layer: vs.NextLayer(l))
    if len(out) > before:
        sources.append('layers')

    before = len(out)
    descend(_safe(lambda: vs.FObject()), 0)
    if len(out) > before:
        sources.append('document')

    before = len(out)
    for h in seeds:
        descend(h, 0)
    if len(out) > before:
        sources.append('seeds')

    return out, sources


def _walk_document(visit, limit=MAX_OBJECTS, seeds=()):
    """Call `visit(h)` once per document object. Returns the number visited."""
    handles, _ = _all_objects(limit, seeds)
    for h in handles:
        try:
            visit(h)
        except Exception:
            pass  # one bad object must not abort the walk
    return len(handles)


def _census():
    """One document walk -> {pio_name: [handles]} plus a total count.

    This is the fallback that makes the module independent of whether the
    "PON='...'" criteria strings are right: it discovers the real PIO names
    instead of asserting them.
    """
    buckets = {}
    total = [0]

    def visit(h):
        total[0] += 1
        name = _pio_name(h)
        if name:
            buckets.setdefault(name, []).append(h)

    _walk_document(visit)
    return buckets, total[0]


def _collect(pon, limit=MAX_OBJECTS):
    """Handles of every object whose plug-in-object name is `pon`.

    Primary: vs.ForEachObject(cb, "PON='<pon>'") — cheap, index-assisted.
    Fallback: if the criteria yields nothing, walk the document and match on
    the parametric record name. A `PON=` criteria with a wrong/renamed plug-in
    name returns zero rows silently, so an empty result is never trusted.

    Returns (handles, mode).
    """
    out = []

    def cb(h):
        if len(out) < limit:
            out.append(h)

    _safe(lambda: vs.ForEachObject(cb, "PON='%s'" % pon))
    if out:
        return out, 'criteria'

    buckets, _ = _census()
    return buckets.get(pon, [])[:limit], 'walk'


def _rf(h, record, field):
    """GetRField(h, record, field) -> str|None. Never raises."""
    if not h or not record or not field:
        return None
    return _s(_safe(lambda: vs.GetRField(h, record, field)))


def _rf_first(h, record, fields):
    """First non-empty value among `fields`. Returns (value, winning_field)."""
    for f in fields:
        v = _rf(h, record, f)
        if v is not None:
            return v, f
    return None, None


# ── sockets ─────────────────────────────────────────────────────────────────
def _device_sockets(h):
    """Socket handles belonging to device `h`. Returns (handles, mode).

    Primary: vs.CC_DeviceSockets(h) if this VW has it. NOTE: that name appears
    in no Vectorworks source — reference_handlers.py flags it as a placeholder
    and domain/tests/mock_vs.py provides it — so it is probed, never assumed.

    Fallback (T2.3 "real impl walks container"): a ConnectCAD device is a
    container of socket PIOs, so walk it with FInGroup/NextObj and keep the
    children whose parametric record name is PON_SOCKET.
    """
    fn = _cc('CC_DeviceSockets')
    if fn:
        res = _safe(lambda: fn(h))
        if res:
            return list(res), 'cc_api'

    kids = _children(h)
    by_pon = [c for c in kids if _pio_name(c) == PON_SOCKET]
    if by_pon:
        return by_pon, 'walk_pon'

    # Tier 3. GetParametricRecord is the authoritative discriminator, but it can
    # come back empty (older VW, a non-parametric container, or a socket that is
    # not itself a PIO). Fall back to a shape test: a child that yields a socket
    # name field is treated as a socket. Heuristic, and it depends on TBV field
    # names, so the mode is reported and the caller can see which path ran.
    by_field = [c for c in kids if _rf(c, REC_SOCKET, F_SKT_NAME) is not None]
    if by_field:
        return by_field, 'walk_field'  # TBV
    return [], 'walk_empty'


def _children(h, max_depth=MAX_DEPTH):
    """Every descendant of container `h` (FInGroup/NextObj), depth-guarded."""
    out = []

    def descend(c, depth):
        while c and len(out) < MAX_OBJECTS:
            out.append(c)
            if depth < max_depth:
                g = _safe(lambda c=c: vs.FInGroup(c))
                if g:
                    descend(g, depth + 1)
            c = _safe(lambda c=c: vs.NextObj(c))

    descend(_safe(lambda: vs.FInGroup(h)), 0)
    return out


def _socket_row(s):
    return {
        'object_id': _oid(s),
        'name': _rf(s, REC_SOCKET, F_SKT_NAME),   # TBV
        'dir': _rf(s, REC_SOCKET, F_SKT_DIR),     # TBV
    }


def _device_summary(h, with_sockets=True):
    row = {
        'object_id': _oid(h),
        'name': _rf(h, REC_DEVICE, F_DEV_NAME),    # TBV
        'make': _rf(h, REC_DEVICE, F_DEV_MAKE),    # TBV
        'model': _rf(h, REC_DEVICE, F_DEV_MODEL),  # TBV
        'layer': _s(_safe(lambda: vs.GetLName(vs.GetLayer(h)))),
    }
    if with_sockets:
        sockets, mode = _device_sockets(h)
        row['sockets'] = [_socket_row(s) for s in sockets]
        row['socket_mode'] = mode
    return row


# ── circuit edges: the two-world core ───────────────────────────────────────
def _endpoint_names(dev_h, skt_h):
    return (_rf(dev_h, REC_DEVICE, F_DEV_NAME),
            _rf(skt_h, REC_SOCKET, F_SKT_NAME))


def _unpack_endpoint(res):
    """CC_GetCircuitSource/Dest is documented as returning
    (device, devSocket, adapter, socket). Unpack defensively: the arity is
    unverified because the function is absent from vs_index.json.
    Returns (device_handle, socket_handle).
    """
    if not res:
        return None, None
    if not isinstance(res, (tuple, list)):
        return res, None
    dev = res[0] if len(res) > 0 else None
    # prefer the 4th element (the socket proper), fall back to the 2nd
    skt = res[3] if len(res) > 3 else (res[1] if len(res) > 1 else None)
    return dev, skt


def _circuit_row(h, join_fields):
    """Name-level view of one circuit, endpoint source depending on capability.

    World A (getters present): CC_GetCircuitSource/Dest give handles, which are
    resolved to names with GetRField. If CC_GetDevice is present it repairs a
    missing device handle from the socket handle (this is what walks through
    adapters).

    World B (getters absent): the endpoints are read straight off the circuit's
    own record as strings — a record-field join. Field spellings are TBV, so
    several are tried and the winner is recorded in `join_fields`.

    Downstream (trace, audit) consumes only names, so both worlds converge here
    and the graph logic is identical.
    """
    row = {
        'object_id': _oid(h),
        'number': _rf(h, REC_CIRCUIT, F_CIR_NUMBER),   # TBV
        'signal': _rf(h, REC_CIRCUIT, F_CIR_SIGNAL),   # TBV
        'cable_type': _rf(h, REC_CIRCUIT, F_CIR_CABLE),  # TBV
    }

    get_src, get_dst = _cc('CC_GetCircuitSource'), _cc('CC_GetCircuitDest')
    if get_src and get_dst:
        get_dev = _cc('CC_GetDevice')
        s_dev, s_skt = _unpack_endpoint(_safe(lambda: get_src(h)))
        d_dev, d_skt = _unpack_endpoint(_safe(lambda: get_dst(h)))
        if get_dev:
            # skipAdapters=True -> the device behind any adapter chain
            if not s_dev and s_skt:
                s_dev = _safe(lambda: get_dev(s_skt, True))
            if not d_dev and d_skt:
                d_dev = _safe(lambda: get_dev(d_skt, True))
        row['src_device'], row['src_socket'] = _endpoint_names(s_dev, s_skt)
        row['dst_device'], row['dst_socket'] = _endpoint_names(d_dev, d_skt)
        row['edge_mode'] = 'cc_api'
        return row

    sd, f1 = _rf_first(h, REC_CIRCUIT, F_CIR_SRC_DEV)   # TBV
    ss, f2 = _rf_first(h, REC_CIRCUIT, F_CIR_SRC_SKT)   # TBV
    dd, f3 = _rf_first(h, REC_CIRCUIT, F_CIR_DST_DEV)   # TBV
    ds, f4 = _rf_first(h, REC_CIRCUIT, F_CIR_DST_SKT)   # TBV
    for k, v in (('src_device', f1), ('src_socket', f2),
                 ('dst_device', f3), ('dst_socket', f4)):
        if v:
            join_fields[k] = v
    row['src_device'], row['src_socket'] = sd, ss
    row['dst_device'], row['dst_socket'] = dd, ds
    row['edge_mode'] = 'record_join'
    return row


def _circuit_rows(limit=MAX_OBJECTS):
    """All circuits as name-level rows. Returns (rows, meta)."""
    handles, mode = _collect(PON_CIRCUIT, limit)
    join_fields = {}
    rows = [_circuit_row(h, join_fields) for h in handles]
    meta = {
        'collect_mode': mode,
        'edge_mode': rows[0]['edge_mode'] if rows else (
            'cc_api' if _cc_available('CC_GetCircuitSource') else 'record_join'),
        'count': len(rows),
    }
    if join_fields:
        meta['join_fields'] = join_fields
    if meta['edge_mode'] == 'record_join':
        meta['warning'] = ('CC_GetCircuitSource/Dest absent; endpoints read as '
                           'record fields. Field names are TBV until '
                           'cc_dump_records confirms them.')
    return rows, meta


# ══ VERBS ═══════════════════════════════════════════════════════════════════

@_guard
def cc_capabilities(p):
    """Which ConnectCAD APIs this Vectorworks actually exposes.

    Diagnostic verb — the fastest way to settle the vs_index.json vs
    RESEARCH.md §2 contradiction. Read-only.
    """
    caps = _capabilities()
    getters = ('CC_GetCircuitSource', 'CC_GetCircuitDest', 'CC_GetDevice',
               'CC_GetEquipmentItem', 'CC_GetSignalData',
               'CC_GetCableTypeData', 'CC_GetConnectorData')
    present = [n for n in getters if caps.get(n)]
    return {
        'status': 'ok',
        'capabilities': caps,
        'getters_present': present,
        'edge_mode': 'cc_api' if caps.get('CC_GetCircuitSource') else 'record_join',
        'verdict': ('RESEARCH.md §2 confirmed; vs_index.json is stale'
                    if present else
                    'vs_index.json confirmed; RESEARCH.md §2 getters do NOT exist'),
    }


@_guard
def cc_dump_records(p):
    """T1.2 — read-only census of record formats and ConnectCAD PIOs.

    This is the FIRST verb to run against a live document, so it asserts
    nothing: it walks the document, discovers real plug-in-object names via
    GetParametricRecord/GetName, and dumps every attached record format with
    its field names and types. It also dumps a full field/value sample for each
    of the five PIO types in CC_TYPES, matching by exact name and, when that
    misses, by case-insensitive/substring near-match so a wrong constant shows
    up as a suggestion instead of an empty result.

    Mutates nothing — only NumRecords/GetRecord/NumFields/GetFldName/
    GetFldType/GetFldFlag/GetRField/GetName, all read calls.

    Params (all optional):
      limit               int  max objects to walk (default 20000)
      samples_per_type    int  sample objects dumped per PIO type (default 1)
      include_values      bool dump field VALUES as well as names (default True)
      probe_resource_types list[int] BuildResourceList type constants to probe.
                          Off by default: vs_index.json documents
                          BuildResourceList(type, folderIndex, subFolderName)
                          but carries no resource-type constant table, and this
                          module does not guess constants. Caller may pass ints
                          explicitly once the table is known.
    """
    limit = int(p.get('limit') or MAX_OBJECTS)
    n_samples = int(p.get('samples_per_type') or 1)
    with_values = p.get('include_values', True)

    formats = {}   # record-format name -> field schema + usage count
    pios = {}      # pio name -> census row
    samples_by_pio = {}
    samples_by_format = {}
    notes = []

    def note_fields(rec_h, rec_name):
        """Record the field schema for `rec_name` once."""
        if rec_name in formats:
            formats[rec_name]['seen_on'] += 1
            return formats[rec_name]
        nf = int(_safe(lambda: vs.NumFields(rec_h)) or 0)
        fields = []
        for i in range(1, nf + 1):
            fname = _s(_safe(lambda i=i: vs.GetFldName(rec_h, i)))
            ftype = _safe(lambda i=i: vs.GetFldType(rec_h, i))
            fields.append({
                'index': i,
                'name': fname,
                'type': ftype,
                'type_name_tbv': FLD_TYPE_NAMES_TBV.get(ftype),
                'flag': _safe(lambda i=i: vs.GetFldFlag(rec_h, i)),
            })
        entry = {'name': rec_name, 'field_count': nf,
                 'fields': fields, 'seen_on': 1, 'parametric': False}
        formats[rec_name] = entry
        return entry

    def attached_records(h):
        """(record_handle, record_name, is_parametric) for records on `h`.

        The parametric record is listed FIRST and separately from the
        NumRecords/GetRecord sweep. For a plug-in object it is the parameter
        record — the authoritative link between the PON namespace and the REC
        namespace — and reaching it directly does not depend on it also showing
        up in the attached-record list. Deduped by name.
        """
        out, seen_names = [], set()
        prec = _safe(lambda: vs.GetParametricRecord(h))
        if prec:
            pname = _s(_safe(lambda: vs.GetName(prec)))
            if pname:
                out.append((prec, pname, True))
                seen_names.add(pname)
        n = int(_safe(lambda: vs.NumRecords(h)) or 0)
        for i in range(1, n + 1):
            rec_h = _safe(lambda i=i: vs.GetRecord(h, i))
            if not rec_h:
                continue
            rec_name = _s(_safe(lambda: vs.GetName(rec_h)))
            if rec_name and rec_name not in seen_names:
                seen_names.add(rec_name)
                out.append((rec_h, rec_name, False))
        return out

    def harvest(h):
        """Register the schema of every record on `h`. Called for EVERY object.

        Kept separate from dump_object on purpose: the record-format census must
        NOT depend on plug-in-object names being discoverable, or a document
        where GetParametricRecord comes back empty would report almost no
        formats — the exact failure that makes a first live run useless.
        note_fields short-circuits after a format's first sighting, so this is
        cheap to run document-wide.
        """
        names = []
        for rec_h, rec_name, is_param in attached_records(h):
            entry = note_fields(rec_h, rec_name)
            entry['parametric'] = entry.get('parametric') or is_param
            names.append(rec_name)
            # one full-value sample per record format, independent of PIO names
            if rec_name not in samples_by_format:
                samples_by_format[rec_name] = {
                    'object_id': _oid(h),
                    'layer': _s(_safe(lambda: vs.GetLName(vs.GetLayer(h)))),
                    'values': dict(
                        (f['name'], _clip(_rf(h, rec_name, f['name'])))
                        for f in formats[rec_name]['fields'] if f['name']),
                }
        return names

    def dump_object(h, rec_names):
        """Full field/value dump of every record attached to `h`."""
        recs = []
        for rec_name in rec_names:
            schema = formats.get(rec_name)
            if not schema:
                continue
            entry = {'record': rec_name, 'field_count': schema['field_count']}
            if with_values:
                entry['values'] = dict(
                    (f['name'], _clip(_rf(h, rec_name, f['name'])))
                    for f in schema['fields'] if f['name'])
            else:
                entry['fields'] = [f['name'] for f in schema['fields']]
            recs.append(entry)
        return recs

    def visit(h):
        rec_names = harvest(h)
        pio = _pio_name(h)
        key = pio or '(no parametric record)'
        row = pios.setdefault(key, {
            'pio_name': pio,
            'count': 0,
            'object_type': _safe(lambda: vs.GetTypeN(h)),
            'sample_uuid': _oid(h),
            'sample_layer': _s(_safe(lambda: vs.GetLName(vs.GetLayer(h)))),
            'record_names': [],
        })
        row['count'] += 1
        for rn in rec_names:
            if rn not in row['record_names']:
                row['record_names'].append(rn)
        if pio and len(samples_by_pio.get(pio, ())) < max(n_samples, 1):
            samples_by_pio.setdefault(pio, []).append({
                'object_id': _oid(h),
                'layer': row['sample_layer'],
                'object_type': _safe(lambda: vs.GetTypeN(h)),
                'plugin_style': _s(_safe(lambda: vs.GetPluginStyle(h))),
                'records': dump_object(h, rec_names),
            })

    # Seed the walk with whatever the PON criteria can find, so the census is
    # still useful on a document where the layer/document walk comes back empty.
    seeds, seed_modes = [], {}
    for pon, _rec in CC_TYPES:
        got = []
        _safe(lambda pon=pon, got=got: vs.ForEachObject(
            lambda h, got=got: got.append(h) if len(got) < limit else None,
            "PON='%s'" % pon))
        if got:
            seed_modes[pon] = len(got)
            seeds.extend(got)

    handles, sources = _all_objects(limit, seeds)
    for h in handles:
        try:
            visit(h)
        except Exception:
            pass
    walked = len(handles)

    # Match the five wanted PIO types against what was actually found.
    found_names = list(pios.keys())
    lower = dict((n.lower(), n) for n in found_names if n)
    wanted = {}
    for pon, rec in CC_TYPES:
        exact = pon if pon in pios else None
        near = []
        if not exact:
            hit = lower.get(pon.lower())
            if hit:
                near.append(hit)
            near.extend(n for n in found_names
                        if n and n not in near
                        and (pon.lower() in n.lower() or n.lower() in pon.lower()))
        entry = {
            'pon_constant': pon,
            'rec_constant': rec,
            'found': bool(exact),
            'count': pios.get(exact, {}).get('count', 0) if exact else 0,
            'samples': samples_by_pio.get(exact, []) if exact else [],
        }
        if not exact:
            entry['near_matches'] = near[:5]
            entry['note'] = ('PON constant did not match any plug-in-object '
                             'name in this document — correct PON_* above.')
            # The PON namespace may be undiscoverable (no parametric record)
            # while the REC namespace still is. Report the record-format side
            # independently, which is the whole reason the two are separate.
            entry['rec_constant_found'] = rec in formats
            if rec in formats:
                entry['rec_sample'] = samples_by_format.get(rec)
                entry['note'] += (' Record format %r DOES exist in this '
                                  'document, so REC_* is likely correct.' % rec)
        else:
            # Does the record-format namespace agree with the PIO namespace?
            rec_names = set()
            for s in entry['samples']:
                for r in s['records']:
                    rec_names.add(r['record'])
            entry['record_names_on_samples'] = sorted(rec_names)
            entry['rec_constant_valid'] = rec in rec_names
            if not entry['rec_constant_valid']:
                entry['note'] = ('REC constant %r not among the records '
                                 'attached to sampled objects — correct REC_* '
                                 'independently of PON_*.' % rec)
        wanted[pon] = entry

    if walked >= limit:
        notes.append('object walk hit the limit of %d; results are partial' % limit)
    if not any(r['pio_name'] for r in pios.values()):
        notes.append('vs.GetParametricRecord returned nothing for any object — '
                     'plug-in-object names could not be discovered, so the '
                     'PON_* namespace cannot be verified from this run')
    missing = [k for k, v in wanted.items() if not v['found']]
    if missing:
        notes.append('PIO names not found: %s — see near_matches' % ', '.join(missing))

    out = {
        'status': 'ok',
        'document': {
            'file': _s(_safe(lambda: vs.GetFName())),
            'vw_version': _safe(lambda: vs.GetVersionEx()),
        },
        'capabilities': _capabilities(),
        'objects_walked': walked,
        'walk_sources': sources,
        'criteria_seeds': seed_modes,
        'record_formats': sorted(formats.values(), key=lambda r: r['name'] or ''),
        'record_format_count': len(formats),
        'record_format_samples': samples_by_format,
        'pio_census': sorted(pios.values(),
                             key=lambda r: -r['count']),
        'connectcad_types': wanted,
        'notes': notes,
        '_meta': {'read_only': True, 'task': 'T1.2'},
    }

    probe = p.get('probe_resource_types')
    if probe:
        out['resource_lists'] = _probe_resource_lists(probe)
    return out


def _probe_resource_lists(type_ids):
    """Opt-in probe of BuildResourceList for caller-supplied type constants.

    vs_index.json has BuildResourceList(type, folderIndex, subFolderName) with
    an empty `ret`, which in this index means a VAR/tuple return (GetBBox is
    encoded the same way) — so the (listID, count) shape is handled defensively.
    No constant is hardcoded here because the index carries no resource-type
    table and this module does not guess constants. Read-only.
    """
    res = {}
    for t in type_ids:
        try:
            t = int(t)
        except Exception:
            continue
        raw = _safe(lambda t=t: vs.BuildResourceList(t, 0, ''))
        list_id, count = None, 0
        if isinstance(raw, (tuple, list)):
            if len(raw) > 0:
                list_id = raw[0]
            if len(raw) > 1:
                count = raw[1]
        else:
            list_id = raw
        names = []
        try:
            count = int(count or 0)
        except Exception:
            count = 0
        for i in range(1, min(count, 200) + 1):
            nm = _s(_safe(lambda i=i: vs.GetActualNameFromResourceList(list_id, i)))
            if nm is None:
                nm = _s(_safe(lambda i=i: vs.GetNameFromResourceList(list_id, i)))
            if nm:
                names.append(nm)
        res[str(t)] = {'list_id': list_id, 'count': count, 'names': names}
    return res


@_guard
def cc_list_devices(p):
    """List ConnectCAD devices, optionally filtered by layer.

    Params: layer (str), with_sockets (bool, default True), limit (int).
    """
    limit = int(p.get('limit') or MAX_OBJECTS)
    with_sockets = p.get('with_sockets', True)
    handles, mode = _collect(PON_DEVICE, limit)
    rows = [_device_summary(h, with_sockets) for h in handles]
    if p.get('layer'):
        rows = [r for r in rows if r['layer'] == p['layer']]
    return {'status': 'ok', 'count': len(rows), 'devices': rows,
            '_meta': {'collect_mode': mode, 'pon': PON_DEVICE,
                      'rec': REC_DEVICE, 'fields_tbv': True}}


@_guard
def cc_get_device(p):
    """One device with its sockets, by name or object_id.

    Params: name (str) or object_id (str/uuid). One is required.
    """
    name, oid = p.get('name'), p.get('object_id')
    if not name and not oid:
        return {'error': "cc_get_device requires 'name' or 'object_id'"}

    if oid:
        h = _safe(lambda: vs.GetObjectByUuid(str(oid)))
        if not h:
            return {'error': 'no object with object_id %r' % oid}
        pio = _pio_name(h)
        if pio != PON_DEVICE:
            return {'error': 'object %r is %r, not a %r' % (oid, pio, PON_DEVICE)}
        return {'status': 'ok', 'device': _device_summary(h),
                '_meta': {'collect_mode': 'uuid', 'fields_tbv': True}}

    handles, mode = _collect(PON_DEVICE)
    matches = [h for h in handles
               if _rf(h, REC_DEVICE, F_DEV_NAME) == name]
    if not matches:
        return {'error': 'no device named %r' % name,
                '_meta': {'collect_mode': mode, 'candidates': len(handles)}}
    out = {'status': 'ok', 'device': _device_summary(matches[0]),
           '_meta': {'collect_mode': mode, 'fields_tbv': True}}
    if len(matches) > 1:
        out['_meta']['warning'] = ('%d devices share the name %r; returned the '
                                   'first' % (len(matches), name))
    return out


@_guard
def cc_list_circuits(p):
    """List circuits, optionally filtered to those touching one device.

    Params: device (str, matches either endpoint), limit (int).
    """
    rows, meta = _circuit_rows(int(p.get('limit') or MAX_OBJECTS))
    dev = p.get('device')
    if dev:
        rows = [r for r in rows if dev in (r['src_device'], r['dst_device'])]
    meta['returned'] = len(rows)
    return {'status': 'ok', 'count': len(rows), 'circuits': rows, '_meta': meta}


@_guard
def cc_trace_signal(p):
    """Walk circuits downstream from a device, optionally from one socket.

    Breadth-first over the name-level circuit graph with a depth guard of 32
    and dedupe on (src_device, src_socket, dst_device, dst_socket) — the graph
    logic is the reference implementation's, unchanged. Only how the edges are
    obtained differs between the two worlds (see `_circuit_row`).

    Params: device (str, required), socket (str, optional — restricts only the
    first hop, matching the reference behaviour).
    """
    start = p.get('device')
    if not start:
        return {'error': "cc_trace_signal requires 'device'"}
    only_skt = p.get('socket')

    circuits, meta = _circuit_rows()
    hops, seen, frontier = [], set(), {start}
    depth = 0
    for _ in range(TRACE_DEPTH):
        nxt = set()
        for c in circuits:
            if c['src_device'] in frontier and c['dst_device']:
                if (c['src_device'] == start and only_skt
                        and c['src_socket'] != only_skt):
                    continue
                key = (c['src_device'], c['src_socket'],
                       c['dst_device'], c['dst_socket'])
                if key in seen:
                    continue
                seen.add(key)
                hops.append(c)
                nxt.add(c['dst_device'])
        if not nxt:
            break
        frontier = nxt
        depth += 1
    if depth >= TRACE_DEPTH:
        meta['warning'] = ('trace hit the depth guard of %d; the path may be '
                           'truncated or cyclic' % TRACE_DEPTH)

    reached = sorted(h['dst_device'] for h in hops if h['dst_device'])
    if not hops:
        known = sorted({c['src_device'] for c in circuits if c['src_device']})
        meta['note'] = ('no circuit sources matched %r; known sources: %s'
                        % (start, ', '.join(known[:20]) or 'none'))
    return {'status': 'ok', 'start': start, 'socket': only_skt,
            'hops': hops, 'hop_count': len(hops), 'depth': depth,
            'devices_reached': sorted(set(reached)), '_meta': meta}


@_guard
def cc_audit_unconnected(p):
    """Report dangling circuits and sockets with nothing patched to them.

    Params: layer (str, restricts the device sweep), limit (int).
    """
    issues = []
    connected = set()

    circuits, meta = _circuit_rows()
    for c in circuits:
        if not c['src_device'] or not c['dst_device']:
            issue = {'kind': 'dangling_circuit'}
            issue.update(c)
            issues.append(issue)
        connected.add((c['src_device'], c['src_socket']))
        connected.add((c['dst_device'], c['dst_socket']))

    handles, dmode = _collect(PON_DEVICE, int(p.get('limit') or MAX_OBJECTS))
    devices = 0
    for h in handles:
        ds = _device_summary(h)
        if p.get('layer') and ds['layer'] != p['layer']:
            continue
        devices += 1
        for s in ds['sockets']:
            if (ds['name'], s['name']) not in connected:
                issues.append({'kind': 'unconnected_socket',
                               'device': ds['name'], 'socket': s['name'],
                               'dir': s['dir'], 'layer': ds['layer']})

    meta['device_collect_mode'] = dmode
    meta['devices_checked'] = devices
    meta['fields_tbv'] = True
    counts = {}
    for i in issues:
        counts[i['kind']] = counts.get(i['kind'], 0) + 1
    return {'status': 'ok', 'count': len(issues), 'by_kind': counts,
            'issues': issues, '_meta': meta}


# ── registry ────────────────────────────────────────────────────────────────
# The bridge agent merges this into commands.py's dispatch table.
# READ-ONLY verbs only. No cc_connect / cc_create_device — Phase 3.
# Star-import surface. Without this, `from cc_commands import *` in commands.py
# would also inject `set_vs`, `traceback` and `COMMANDS` into that module's
# namespace — and `COMMANDS` in particular would be clobbered by whichever
# domain module is star-imported last, silently. Only the verbs cross over;
# the pump reaches them via getattr(commands, name).
__all__ = [
    'cc_capabilities',
    'cc_dump_records',
    'cc_list_devices',
    'cc_get_device',
    'cc_list_circuits',
    'cc_trace_signal',
    'cc_audit_unconnected',
]

COMMANDS = {
    'cc_capabilities': cc_capabilities,
    'cc_dump_records': cc_dump_records,
    'cc_list_devices': cc_list_devices,
    'cc_get_device': cc_get_device,
    'cc_list_circuits': cc_list_circuits,
    'cc_trace_signal': cc_trace_signal,
    'cc_audit_unconnected': cc_audit_unconnected,
}

# ── vs.* functions used, with signatures verified against vs_index.json ──────
# Every one of these was checked before use; none is guessed.
#   ForEachObject(callback, c)                    -> (void)
#   FLayer()                                      -> HANDLE
#   NextLayer(h)                                  -> HANDLE
#   FInLayer(h)                                   -> HANDLE
#   FInGroup(ObjectHd)                            -> HANDLE
#   NextObj(h)                                    -> HANDLE
#   GetParametricRecord(h)                        -> HANDLE
#   GetName(h)                                    -> STRING
#   GetTypeN(h)                                   -> INTEGER
#   GetLayer(h)                                   -> HANDLE
#   GetLName(h)                                   -> STRING
#   GetPluginStyle(hObject)                       -> STRING
#   GetObjectUuid(h)                              -> STRING
#   GetObjectByUuid(UUID)                         -> HANDLE
#   NumRecords(h)                                 -> INTEGER   (records ON h)
#   GetRecord(h, cnt)                             -> HANDLE
#   NumFields(h)                                  -> INTEGER
#   GetFldName(h, index)                          -> STRING
#   GetFldType(h, t)                              -> INTEGER
#   GetFldFlag(h, t)                              -> INTEGER
#   GetRField(h, record, field)                   -> DYNARRAY[] of CHAR
#   GetFName()                                    -> STRING
#   GetVersionEx()                                -> (tuple)
#   BuildResourceList(type, folderIndex, subFolderName)  -> (tuple)  [opt-in]
#   GetNameFromResourceList(listID, index)        -> DYNARRAY[] of CHAR
#   GetActualNameFromResourceList(listID, index)  -> DYNARRAY[] of CHAR
#
# NOT USED, and why:
#   GetRecordName / NumRecordsInDocument — DO NOT EXIST in vs_index.json.
#     The brief suggested them; NumRecords(h) counts records attached to an
#     OBJECT, not record formats in the document. cc_dump_records therefore
#     harvests formats from attached records during the object walk.
#   All six real CC_* functions are creators/mutators (FromShape,
#     OnFindAndReplace, ReloadData) — this module is read-only and calls none.
VS_USED = True
