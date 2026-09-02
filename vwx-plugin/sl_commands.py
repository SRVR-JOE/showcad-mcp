"""
sl_commands.py — Spotlight (`sl_*`) verbs for the VW MCP Bridge.

Owned by the Spotlight Agent. Do NOT put ConnectCAD or generic verbs here.
Sibling modules: commands.py (generic, other owner), cc_commands.py
(ConnectCAD, other owner). This module imports NEITHER of them — it
re-declares the four house helpers locally so that commands.py can do
`from sl_commands import *` without an import cycle.

House style (matches commands.py):
    def verb(p) -> dict      # p is the params dict from the job file
    returns {'status': 'ok', ...}   on success
            {'error': '...'}        on failure
    NOTHING raises into Vectorworks. Ever.

═══════════════════════════════════════════════════════════════════════════
WHAT IS AND IS NOT VERIFIED
═══════════════════════════════════════════════════════════════════════════

VERIFIED — every vs.* call below was checked against vwx-plugin/vs_index.json
(3071 signatures) for existence and arity before it was written:

    Generic / record access
      ForEachObject(callback, c)                     Criteria
      GetRField(h, record, field) -> str             Database / Record
      NumFields(h) -> int                            Database / Record
      NumRecords(h) -> int                           Database / Record
      GetRecord(h, cnt) -> HANDLE                    Database / Record
      GetFldName(h, index) -> str                    Database / Record
      GetFldType(h, t) -> int                        Database / Record
      GetParametricRecord(h) -> HANDLE               Database / Record
      GetName(h) -> str                              Object Names
      GetTypeN(h) -> int                             Object Info
      GetLayer(h) -> HANDLE / GetLName(h) -> str     Layers
      GetClass(h) -> str                             Object Attributes
      GetObjectUuid(h) / GetObjectByUuid(uuid)       Object Info
      GetSymLoc(symHd) / GetSymLoc3D(objectHandle)   Object Info / Symbols
      GetBBox(h)                                     Object Info

    Spotlight family — THE BRIEF SAID THIS DID NOT EXIST. IT DOES.
      LDevice_GetParamStr (h, cell, acc, universalName) -> STRING
      LDevice_GetParamLong(h, cell, acc, universalName) -> LONGINT
      LDevice_GetParamReal(h, cell, acc, universalName) -> REAL
      LDevice_GetParamBool(h, cell, acc, universalName) -> BOOLEAN
      LDevice_GetCellCount(h) -> LONGINT
      LDevice_GetAccCount(h, cellIndex) -> LONGINT
      LDevice_Reset(h) / LDevice_ResetVisual(h)
      GetLoadParent(h) -> HANDLE
      IsLDSchematicViewObj(h) -> BOOLEAN
      GetVisionMapping() -> str
      OLDGetHangingPos(h, loadIndex) -> HANDLE       (Truss Analysis)
      UpdatePositionParam(positionHandle)            (Truss Analysis)

    Data Tag family (used by the sl_insert_fixture DESIGN only)
      DT_AssociateWithObj(hDataTag, hObject) -> BOOLEAN
      DT_UpdateTaggedTags(h) -> BOOLEAN
      DT_ResetAllDataTags()

CORRECTIONS TO THE STANDING RESEARCH — both matter:

  (1) RESEARCH.md §3 says "no SL_* family". False. Vectorworks 2026 ships a
      24-function `LDevice_*` family plus SL_Export / SL_Import. The important
      one is LDevice_Get/SetParam*, which addresses fields by their UNIVERSAL
      (worksheet) name rather than the localized record field name. That is
      the localization- and version-stable read path and this module prefers
      it, falling back to GetRField only when it returns nothing.

  (2) RESEARCH.md §3 and TASKS.md T1.3 say "Data Tag = type 86". Type 86 is
      **Plug-in Object**, not "Data Tag" — commands.py:3977 relies on
      GetTypeN(h) == 86 to find Marionette node PIOs, and commands.py's own
      OBJ_TYPES dict mislabels 86 as 'space'. So 86 does NOT discriminate a
      Data Tag from a Lighting Device from a Hanging Position: all three are
      type 86. The discriminator is the PARAMETRIC RECORD NAME,
      vs.GetName(vs.GetParametricRecord(h)). Every verb here uses that.

RESILIENCE — three things this module does NOT assume:

  * No uncertain vs.* call is made directly. Everything goes through the
    `_vcall(name, args)` chokepoint, which resolves via getattr at runtime and
    records the outcome ('ok' / 'blank' / 'absent' / 'raised') into
    `_meta.vs_probe` on every verb result. vs_index.json is a mirror of the
    SDK stub, not proof of what a given build exposes, so the first live run
    tells us what is actually available instead of quietly returning nothing.

  * No single enumeration root is trusted. `_walk_document` unions a layer
    walk (FLayer/NextLayer/FInLayer), FObject(), and both PIO criteria
    spellings, deduping by GetObjectUuid, with a depth-capped descent through
    FInGroup/FIn3D. An empty ForEachObject result is indistinguishable from a
    wrong criteria keyword — VW returns zero rows silently rather than
    erroring — so an empty criteria result is never accepted as the answer.
    (Verified: with ForEachObject stubbed to return nothing, and again with
    the layer walk ALSO dead, the census is still complete.)

  * Record-format discovery is not gated on finding PIOs first. Formats come
    from a union of three independent sources — criteria T=RECDEF, records
    attached to walked objects (NumRecords/GetRecord), and parametric records
    — and `format_sources` reports what each contributed. A document where
    GetParametricRecord returns nothing would otherwise report almost no
    formats and waste the one run against the user's real file.

MULTI-CELL — a Lighting Device is NOT necessarily one patch row.
LDevice_GetCellCount exists because an LED bar / moving-head array carries
several cells, each with its own channel and DMX address. sl_patch_report
therefore emits ONE ROW PER CELL. domain/reference_handlers.py reads only the
record (one value per field) and so reports a 12-cell bar as a single address:
cells 2..N are invisible to its duplicate-address detection, which is the one
thing a patch report exists to catch. That is a correctness bug in the
reference, not just a gap.

WRITES — none. LDevice_AddAccessory, LDevice_DeleteAcc, LDevice_Set*,
SetRField, ResetObject, UpdatePositionParam and DT_AssociateWithObj all mutate
and are referenced ONLY in the sl_insert_fixture design block at the end of
this file. No verb here calls any of them.

TBV — NOT verified against a live document; nothing here is hardcoded as
truth, every one is a *candidate* that sl_dump_records resolves and reports:
      - record format names: 'Lighting Device', 'Hanging Position', 'Data Tag'
      - field names: Channel, Unit Number, Address, Universe, Position,
        Purpose, Symbol Name  (only 'Position' has independent corroboration:
        vs_index doc for UpdatePositionParam reads "changes the 'Position'
        parameter for all loads")
      - universal/worksheet names used by LDevice_GetParam*
      - GetFldType integer -> type-name mapping
      - whether 'T=PLUGINOBJ' or 'T=PLUGINOBJECT' is the correct criteria
        keyword (commands.py uses BOTH, in different places) — the dump
        reports a row count for each in `pio_criteria_probe`, and does not
        depend on either being right
      - the semantics of GetLoadParent (its vs_index doc string is a
        copy-paste of GetCellCount's, so only its name and HANDLE return
        type are trustworthy)

Run sl_dump_records once on a real show file and every TBV above collapses to
a fact — in particular `universal_names.resolved`, which probes 37 candidate
universal names against a live fixture and returns the ones that answer. That
list is the authoritative field map: pin _FIELD_CANDIDATES to it and the TBV
problem is closed. Until then no sl_* verb depends on any single spelling.

  python3 tools/sl_dump.py --out domain/docs/records/spotlight.json
"""

try:
    import vs                     # only exists inside Vectorworks
except ImportError:               # out-of-VW tests inject a mock
    vs = None


def set_vs(module):
    """Test hook: inject domain/tests/mock_vs.py in place of `vs`."""
    global vs
    vs = module


# ── house helpers (local copies — see module docstring on the import cycle) ──

def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _oid(h):
    """Object UUID string. VW2026 uses UUIDs; InternalIndex APIs were removed."""
    if not h:
        return None
    return _vcall('GetObjectUuid', (h,)) or None


def _h(oid):
    """Resolve object_id (UUID string) -> handle."""
    if oid is None:
        return None
    return _vcall('GetObjectByUuid', (str(oid),)) or None


def _collect(criteria, limit=2000):
    """Handles matching a criteria string. Never creates/deletes in the
    callback — VW forbids mutating the traversal set from inside it."""
    out = []

    def cb(h):
        if len(out) < limit:
            out.append(h)

    _vcall('ForEachObject', (cb, criteria))
    return out


def _guard(fn):
    """Wrap a verb so no exception can ever reach Vectorworks."""
    def wrapped(p):
        try:
            return fn(p or {})
        except Exception as e:
            return {'error': '%s: %s' % (fn.__name__, e)}
    wrapped.__name__ = fn.__name__
    wrapped.__doc__ = fn.__doc__
    return wrapped


# ── runtime chokepoint for every uncertain vs.* call ────────────────────────
# Nothing Spotlight-side is called directly. `_vcall` resolves the function by
# name at runtime and records the outcome, so the FIRST live run tells us what
# this build actually exposes instead of just returning empty. The record is
# emitted as `_meta.vs_probe` on every verb result.
#
# 'ok'      the call ran and returned something non-blank
# 'blank'   the call ran and returned None/'' (function exists, no data)
# 'absent'  vs has no such attribute on this build
# 'raised'  the call exists but threw (wrong arity, wrong object, VW refused)

_VS_PROBE = {}


def _vsfn(name):
    """Resolve vs.<name> or None. Never raises, even when vs itself is None."""
    try:
        return getattr(vs, name, None)
    except Exception:
        return None


def _vcall(name, args=(), default=None):
    """Call vs.<name>(*args) through the chokepoint, recording the outcome."""
    fn = _vsfn(name)
    if fn is None:
        _VS_PROBE[name] = 'absent'
        return default
    try:
        v = fn(*args)
    except Exception as e:
        prev = _VS_PROBE.get(name)
        if prev not in ('ok', 'blank'):
            _VS_PROBE[name] = 'raised: %s' % (str(e)[:80],)
        return default
    if _blank_v(v):
        _VS_PROBE.setdefault(name, 'blank')
    else:
        _VS_PROBE[name] = 'ok'
    return v if v is not None else default


def _blank_v(v):
    return v is None or (isinstance(v, str) and v.strip() == '')


def _vs_meta(extra=None):
    m = {'vs_probe': dict(sorted(_VS_PROBE.items()))}
    if extra:
        m.update(extra)
    return m


# ── criteria: both spellings appear in commands.py; try each (TBV) ──────────
_PIO_CRITERIA = ('T=PLUGINOBJ', 'T=PLUGINOBJECT')

MAX_OBJECTS = 20000
_MAX_DEPTH = 6      # descend into groups/symbols this far


def _walk_document(limit=MAX_OBJECTS):
    """Every object in the document, from a UNION of independent roots,
    deduped by UUID.

    No single enumeration root is trusted. A layer walk that fails (FInLayer
    returning nothing on one layer, or FLayer itself being unavailable) would
    otherwise zero the entire dump and read as "this document is empty". Roots:

      1. layer walk   FLayer -> NextLayer, FInLayer on each
      2. FObject()    first object of the active document
      3. criteria     both PIO criteria spellings

    plus a depth-capped descent into containers via FInGroup / FIn3D, because
    ForEachObject does not enter symbols, groups or viewport annotations
    without INSYMBOL / INOBJECT / INVIEWPORT modifiers.

    Returns (handles, meta) where meta records what each root contributed —
    a root that contributes 0 on a non-empty document is itself a finding.
    """
    seen = {}
    meta = {'roots': {}, 'limit': limit, 'truncated': False}

    def _key(h):
        return _oid(h) or ('addr#%d' % id(h))

    def _add_chain(h, depth):
        added = 0
        while h is not None and h:
            if len(seen) >= limit:
                meta['truncated'] = True
                return added
            k = _key(h)
            if k not in seen:
                seen[k] = h
                added += 1
                if depth < _MAX_DEPTH:
                    for child_root in ('FInGroup', 'FIn3D'):
                        c = _vcall(child_root, (h,))
                        if c:
                            added += _add_chain(c, depth + 1)
            h = _vcall('NextObj', (h,))
        return added

    # root 1 — layer walk
    n = 0
    lh = _vcall('FLayer')
    guard = 0
    while lh and guard < 512:
        guard += 1
        n += _add_chain(_vcall('FInLayer', (lh,)), 0)
        lh = _vcall('NextLayer', (lh,))
    meta['roots']['layer_walk'] = n

    # root 2 — first object of the active document
    before = len(seen)
    _add_chain(_vcall('FObject'), 0)
    meta['roots']['FObject'] = len(seen) - before

    # root 3 — criteria seeds
    for crit in _PIO_CRITERIA:
        before = len(seen)
        for h in _collect(crit, limit):
            if _key(h) not in seen:
                seen[_key(h)] = h
        meta['roots']['criteria:' + crit] = len(seen) - before

    meta['total'] = len(seen)
    return list(seen.values()), meta


def _pio_record_name(h):
    """The PIO's parametric record name — 'Lighting Device', 'Data Tag', etc.

    This, NOT GetTypeN, is what identifies a PIO family (see module docstring
    §2). For a plug-in object the parametric record's name IS the plug-in
    name, which makes it the authoritative PON <-> record-name bridge and does
    not depend on the record also appearing in the object's attached list.
    """
    rh = _vcall('GetParametricRecord', (h,))
    if not rh:
        return None
    return _vcall('GetName', (rh,)) or None


def _all_pios(limit=MAX_OBJECTS, force_walk=False):
    """(handles, meta). Criteria first (cheap); multi-root walk as fallback.

    An empty ForEachObject result is indistinguishable from a wrong criteria
    keyword — VW returns zero rows silently rather than erroring — so an empty
    criteria result is NEVER accepted as the answer. The read verbs take the
    cheap path when it produces rows; the dump passes force_walk=True and
    always pays for the full walk.
    """
    meta = {'criteria_tried': [], 'criteria_used': None, 'walk_used': False}
    if not force_walk:
        for crit in _PIO_CRITERIA:
            hs = _collect(crit, limit)
            meta['criteria_tried'].append({'criteria': crit,
                                           'count': len(hs)})
            if hs:
                meta['criteria_used'] = crit
                return hs, meta

    objs, wmeta = _walk_document(limit)
    meta['walk_used'] = True
    meta['walk'] = wmeta
    hs = [h for h in objs if _vcall('GetParametricRecord', (h,))]
    meta['walk_object_count'] = len(objs)
    meta['walk_pio_count'] = len(hs)
    for crit in _PIO_CRITERIA:
        c = _collect(crit, limit)
        meta['criteria_tried'].append({'criteria': crit, 'count': len(c)})
        if c and not meta['criteria_used']:
            meta['criteria_used'] = crit
    return hs, meta


def _pios_named(name, limit=MAX_OBJECTS):
    """All PIOs whose parametric record name matches `name` (case-insensitive).

    Deliberately NOT `PON='<name>'` criteria: if the localized/actual PIO name
    differs by a space or case the criteria silently returns zero objects,
    which reads as "this document has no fixtures". Filtering in Python on the
    parametric record name fails visibly instead (the census in
    sl_dump_records shows what is actually there).
    """
    want = (name or '').strip().lower()
    hs, meta = _all_pios(limit)
    out = [h for h in hs
           if (_pio_record_name(h) or '').strip().lower() == want]
    if not out and not meta.get('walk_used'):
        # criteria produced PIOs but none matched — the criteria may still be
        # missing nested fixtures. Pay for the walk before reporting zero.
        hs, meta = _all_pios(limit, force_walk=True)
        out = [h for h in hs
               if (_pio_record_name(h) or '').strip().lower() == want]
    return out, meta


# ── record-format name candidates (all TBV until the dump runs) ─────────────
LD_REC_CANDIDATES = ('Lighting Device', 'LightingDevice', 'Light Device')
HP_REC_CANDIDATES = ('Hanging Position', 'HangingPosition', 'Lighting Position')
DT_REC_CANDIDATES = ('Data Tag', 'DataTag')

# Substrings used to pull Spotlight-relevant formats out of the full T=RECDEF
# list. Scope is deliberately narrow: the ConnectCAD agent's cc_dump_records
# owns Device / Socket / Circuit / Equipment Item and this must not overlap.
_SPOTLIGHT_FORMAT_HINTS = (
    'lighting device', 'hanging position', 'lighting position',
    'data tag', 'light info', 'instrument', 'lighting',
)

# GetFldType -> name. TBV: the dump always returns the raw int alongside.
_FLD_TYPES_TBV = {1: 'integer', 2: 'boolean', 3: 'real', 4: 'text',
                  5: 'text_static', 6: 'popup', 7: 'radio', 8: 'checkbox'}


# ── logical field -> candidate names, tried in order ────────────────────────
# `universal` = LDevice_GetParam* worksheet name (preferred: localization- and
# version-stable). `record` = GetRField field name (fallback).
# EVERY entry is TBV. _read_field records which candidate actually resolved so
# one live run pins them all.
_FIELD_CANDIDATES = {
    'channel':  {'universal': ('Channel',),
                 'record':    ('Channel',)},
    'unit':     {'universal': ('UnitNumber', 'Unit Number'),
                 'record':    ('Unit Number', 'UnitNumber', 'Unit')},
    'address':  {'universal': ('Address', 'Dimmer'),
                 'record':    ('Address', 'Dimmer/Address', 'Dimmer')},
    'universe': {'universe_note': 'often embedded in Address as "u/a"',
                 'universal': ('Universe',),
                 'record':    ('Universe',)},
    'position': {'universal': ('Position',),
                 'record':    ('Position',)},   # corroborated by UpdatePositionParam doc
    'purpose':  {'universal': ('Purpose',),
                 'record':    ('Purpose',)},
    'symbol':   {'universal': ('SymbolName', 'Symbol Name'),
                 'record':    ('Symbol Name', 'SymbolName')},
    'instrument_type': {'universal': ('InstrumentType', 'Instrument Type'),
                        'record':    ('Instrument Type', 'InstrumentType')},
    'wattage':  {'universal': ('Wattage',),
                 'record':    ('Wattage',)},
    'color':    {'universal': ('Color',),
                 'record':    ('Color',)},
    'mode':     {'universal': ('FixtureMode', 'Fixture Mode'),
                 'record':    ('Fixture Mode', 'FixtureMode')},
}

_LD_CELL = 0        # first cell
_LD_ACC = -1        # -1 = the lighting device itself, not an accessory

# Universal names worth probing on a live fixture. sl_dump_records tries every
# one and reports which resolve — that resolved list is what makes every other
# verb reliable, so it is deliberately wider than _FIELD_CANDIDATES.
_UNIVERSAL_PROBE = (
    'Channel', 'UnitNumber', 'Unit Number', 'Address', 'Dimmer', 'Universe',
    'Position', 'Purpose', 'SymbolName', 'Symbol Name', 'InstrumentType',
    'Instrument Type', 'Wattage', 'Color', 'FixtureMode', 'Fixture Mode',
    'FixtureID', 'Fixture ID', 'UID', 'Frame', 'Gobo1', 'Gobo 1',
    'DeviceType', 'Device Type', 'NumChannels', 'DMXFootprint', 'Circuit',
    'CircuitName', 'CircuitNumber', 'Load', 'Weight', 'FocusPoint', 'Focus',
    'UserField1', 'Mark', 'Cell', 'Layer',
)


def _blank(v):
    return v is None or (isinstance(v, str) and v.strip() == '')


def _read_field(h, rec_name, key, cell=_LD_CELL, trace=None):
    """Read one logical field of one CELL of a lighting device.

    Order is deliberately the INVERSE of domain/reference_handlers.py:

      1. LDevice_GetParamStr(h, cell, -1, universalName)  — PRIMARY.
         Universal (worksheet) names are stable across Vectorworks
         localizations and versions. GetRField's field names are not: they are
         exactly the strings that break on a non-English install or a version
         bump, and the reference handlers depend on them.
      2. GetRField(h, <parametric record name>, field)    — FALLBACK, and only
         for cell 0. A record holds ONE value per field, so it cannot express
         cells 1..N; asking it for cell 3's address would silently return
         cell 0's. For cell > 0 there is no fallback and a miss stays a miss.

    Every call goes through _vcall, so a build that lacks LDevice_GetParamStr
    records 'absent' in _meta.vs_probe rather than failing invisibly.
    """
    spec = _FIELD_CANDIDATES.get(key) or {}
    for un in spec.get('universal', ()):
        v = _vcall('LDevice_GetParamStr', (h, cell, _LD_ACC, un))
        if not _blank(v):
            if trace is not None:
                trace[key] = {'via': 'LDevice_GetParamStr', 'name': un,
                              'cell': cell}
            return v
    if rec_name and cell == _LD_CELL:
        for fn in spec.get('record', ()):
            v = _vcall('GetRField', (h, rec_name, fn))
            if not _blank(v):
                if trace is not None:
                    trace[key] = {'via': 'GetRField', 'record': rec_name,
                                  'name': fn, 'cell': cell}
                return v
    if trace is not None:
        trace[key] = {'via': None, 'cell': cell,
                      'note': 'no candidate resolved (TBV)' if cell == _LD_CELL
                              else 'no universal name resolved; GetRField '
                                   'cannot address cell > 0'}
    return None


def _cell_count(h):
    n = _vcall('LDevice_GetCellCount', (h,))
    try:
        n = int(n)
    except (TypeError, ValueError):
        return 1
    return n if n and n > 0 else 1


def _cell_rows(h, rec_name, count=None):
    """One patch row per CELL.

    A Lighting Device is not necessarily one channel/address row.
    LDevice_GetCellCount exists precisely because a multi-cell fixture (an LED
    bar, a moving-head array, a multi-cell wash) carries several cells, and
    each cell patches to its own channel and DMX address.
    domain/reference_handlers.py reads only the record — one value per field —
    so it reports a 12-cell bar as a single address. That is not merely a gap,
    it is a correctness bug: cells 2..N are invisible to its duplicate-address
    detection, which is the exact thing a patch report exists to catch.
    """
    n = count if count is not None else _cell_count(h)
    rows = []
    for c in range(n):
        rows.append({
            'cell': c,
            'channel':  _read_field(h, rec_name, 'channel', c),
            'address':  _read_field(h, rec_name, 'address', c),
            'universe': _read_field(h, rec_name, 'universe', c),
        })
    return rows


def _loc(h):
    p = _vcall('GetSymLoc', (h,))
    if p and len(p) >= 2:
        return {'x': p[0], 'y': p[1]}
    return None


# ═══════════════════════════════════════════════════════════════════════════
# 1. sl_dump_records — T1.1 / T1.3 discovery. READ-ONLY.
# ═══════════════════════════════════════════════════════════════════════════

@_guard
def sl_dump_records(p):
    """Dump the Spotlight record formats + one fully-populated sample object
    of each, from the OPEN document. This is the verb that turns every TBV
    field name in this module into a fact.

    Scope is Spotlight only — Lighting Device, Hanging Position, Data Tag and
    anything whose format name matches _SPOTLIGHT_FORMAT_HINTS. ConnectCAD's
    Device / Socket / Circuit / Equipment Item formats belong to
    cc_dump_records and are deliberately NOT dumped here; pass
    all_format_names=True to get the bare *names* of every format in the doc
    (names only, no fields) when you need to see what else is present.

    params:
      all_format_names  bool  also list every T=RECDEF name (default True)
      max_objects       int   PIO traversal cap (default 2000)
      sample_fields     bool  dump full field values of a sample of each PIO
                              family (default True)

    Read-only: no SetRField, no ResetObject, no menu commands, no selection
    change. Runs against the user's live document.
    """
    all_names = p.get('all_format_names', True)
    max_objects = int(p.get('max_objects', MAX_OBJECTS) or MAX_OBJECTS)
    want_samples = p.get('sample_fields', True)

    out = {
        'status': 'ok',
        'scope': 'spotlight-only (ConnectCAD formats are cc_dump_records)',
        'document': {
            'name': _vcall('GetFName'),
            'path': _vcall('GetFPathName'),
            'vw_version': _vcall('GetVersion'),
        },
        'notes': [],
    }

    def _dump_format(fh, name, sources):
        nf = _vcall('NumFields', (fh,), 0) or 0
        try:
            nf = int(nf)
        except (TypeError, ValueError):
            nf = 0
        fields = []
        for k in range(1, nf + 1):
            fname = _vcall('GetFldName', (fh, k))
            ftype = _vcall('GetFldType', (fh, k))
            fields.append({'index': k, 'name': fname, 'type': ftype,
                           'type_name_tbv': _FLD_TYPES_TBV.get(ftype)})
        return {'name': name, 'object_id': _oid(fh), 'field_count': nf,
                'fields': fields, 'discovered_via': sorted(sources)}

    # ── the document walk, done ONCE and shared ────────────────────────────
    # The dump always pays for the full multi-root walk (force_walk=True). It
    # must not depend on a criteria string being right, and it must not gate
    # format discovery on finding PIO buckets first: on a document where
    # GetParametricRecord returns nothing, a PIO-gated harvest reports almost
    # no formats and the one run against the user's real file is wasted.
    walk_objs, walk_meta = _walk_document(max_objects)
    out['walk'] = walk_meta
    if not walk_objs:
        out['notes'].append(
            'Document walk returned ZERO objects from every root '
            '(layer walk, FObject, criteria). Either the document is empty or '
            'every enumeration root is unavailable on this build — check '
            '_meta.vs_probe before believing any other field here.')

    # ── record formats: UNION of three independent sources ─────────────────
    # No single source is trusted. T=RECDEF is a criteria call and returns
    # zero rows silently if the keyword is wrong; the attached-record harvest
    # only sees formats that are actually in use; the parametric harvest only
    # sees PIOs. Together they cover each other's blind spots.
    fmt = {}          # name -> (handle, {sources})

    def _note_fmt(name, handle, source):
        if not name:
            return
        cur = fmt.get(name)
        if cur is None:
            fmt[name] = [handle, {source}]
        else:
            cur[1].add(source)
            if cur[0] is None:
                cur[0] = handle

    for fh in _collect('T=RECDEF', 4000):
        _note_fmt(_vcall('GetName', (fh,)), fh, 'criteria:T=RECDEF')

    for h in walk_objs:
        n = _vcall('NumRecords', (h,), 0) or 0
        try:
            n = int(n)
        except (TypeError, ValueError):
            n = 0
        for k in range(1, n + 1):
            rh = _vcall('GetRecord', (h, k))
            if rh:
                _note_fmt(_vcall('GetName', (rh,)), rh, 'attached_record')
        prec = _vcall('GetParametricRecord', (h,))
        if prec:
            _note_fmt(_vcall('GetName', (prec,)), prec, 'parametric_record')

    out['format_count'] = len(fmt)
    out['format_sources'] = {
        'criteria:T=RECDEF': sum(1 for v in fmt.values()
                                 if 'criteria:T=RECDEF' in v[1]),
        'attached_record': sum(1 for v in fmt.values()
                               if 'attached_record' in v[1]),
        'parametric_record': sum(1 for v in fmt.values()
                                 if 'parametric_record' in v[1]),
    }
    if all_names:
        out['all_format_names'] = sorted(fmt)

    formats = {}
    explicit = {c.strip().lower() for c in
                LD_REC_CANDIDATES + HP_REC_CANDIDATES + DT_REC_CANDIDATES}
    for n, (fh, sources) in fmt.items():
        low = n.strip().lower()
        if low in explicit or any(hint in low
                                  for hint in _SPOTLIGHT_FORMAT_HINTS):
            formats[n] = _dump_format(fh, n, sources)
    out['record_formats'] = formats
    out['record_formats_matched'] = sorted(formats)
    if not formats:
        out['notes'].append(
            'No Spotlight record format matched. Either the document has no '
            'Spotlight content, or the format names differ from every TBV '
            'candidate — check all_format_names for the real spellings.')

    # ── census of plug-in objects by parametric record name ────────────────
    pios = [h for h in walk_objs if _vcall('GetParametricRecord', (h,))]
    crit_counts = []
    for crit in _PIO_CRITERIA:
        crit_counts.append({'criteria': crit,
                            'count': len(_collect(crit, max_objects))})
    out['pio_criteria_probe'] = crit_counts
    out['pio_criteria_used'] = next(
        (c['criteria'] for c in crit_counts if c['count']), None)
    out['notes'].append(
        "PIO criteria: commands.py uses BOTH 'T=PLUGINOBJ' (line 2212) and "
        "'T=PLUGINOBJECT' (line 4290). pio_criteria_probe gives the row count "
        'for each; the census itself comes from the walk and does not depend '
        'on either being right. Standardise on whichever is non-zero.')

    census, first = {}, {}
    for h in pios:
        rn = _pio_record_name(h) or '(no parametric record)'
        census[rn] = census.get(rn, 0) + 1
        first.setdefault(rn, h)
    out['pio_census'] = [{'parametric_record': k, 'count': v,
                          'type_n': _vcall('GetTypeN', (first[k],))}
                         for k, v in sorted(census.items(),
                                            key=lambda kv: -kv[1])]
    out['notes'].append(
        'type_n above is expected to be 86 for EVERY row: 86 is Plug-in '
        'Object, not "Data Tag" and not "space". RESEARCH.md §3 / TASKS.md '
        'T1.3 ("Data Tag = type 86") and commands.py OBJ_TYPES[86]="space" '
        'are both wrong. Identify a PIO family by parametric_record, never '
        'by type_n.')

    # ── one full sample of each Spotlight PIO family ───────────────────────
    if want_samples:
        samples = {}
        for rn, h in first.items():
            low = rn.strip().lower()
            if low not in explicit and not any(hint in low for hint
                                               in _SPOTLIGHT_FORMAT_HINTS):
                continue
            samples[rn] = _dump_sample(h, rn)
        out['samples'] = samples
        if not samples:
            out['notes'].append(
                'No Spotlight PIO found to sample. pio_census lists what the '
                'document actually contains.')

    # ── THE list that makes everything else reliable: which universal names
    #    actually resolve on a live fixture. Read-only: LDevice_GetParamStr
    #    is a getter. LDevice_AddAccessory / LDevice_DeleteAcc MUTATE and are
    #    never called by any verb in this module.
    ld_sample = None
    for rn, h in first.items():
        if rn.strip().lower() in {c.strip().lower()
                                  for c in LD_REC_CANDIDATES}:
            ld_sample = h
            break
    if ld_sample is not None:
        resolved, empty = {}, []
        for un in _UNIVERSAL_PROBE:
            v = _vcall('LDevice_GetParamStr', (ld_sample, _LD_CELL,
                                               _LD_ACC, un))
            if not _blank(v):
                resolved[un] = v
            else:
                empty.append(un)
        out['universal_names'] = {
            'sample_object_id': _oid(ld_sample),
            'cell_count': _cell_count(ld_sample),
            'resolved': resolved,
            'blank_or_unknown': empty,
            'probe_size': len(_UNIVERSAL_PROBE),
        }
        if _cell_count(ld_sample) > 1:
            out['universal_names']['per_cell'] = _cell_rows(ld_sample, None)
        out['notes'].append(
            'universal_names.resolved is the authoritative field list. A name '
            'here works through LDevice_GetParamStr(h, cell, -1, name), which '
            'is localization- and version-stable — unlike the GetRField field '
            'names, which break on a non-English install. Pin '
            '_FIELD_CANDIDATES to these and the TBV problem is closed. Note a '
            'blank result is ambiguous: unknown name, or known name with no '
            'value on this fixture.')
    else:
        out['universal_names'] = None
        out['notes'].append(
            'No Lighting Device sampled, so the universal-name probe did not '
            'run. Open a document with at least one fixture.')

    # ── free field-name intel from the Vision mapping ──────────────────────
    out['vision_mapping'] = _vcall('GetVisionMapping')
    out['vision_mapping_note'] = (
        'GetVisionMapping() returns the Lighting Device field names mapped to '
        'a visualizer, in SetVisionMapping order: color, universe, gobo, '
        'name, channel, fixtureid. Independent confirmation of the Universe '
        'and Channel field spellings if it is non-empty.')

    out['_meta'] = _vs_meta({'walk': walk_meta})
    return out


def _dump_sample(h, rec_name):
    """Every field of one object, by three independent routes."""
    s = {
        'object_id': _oid(h),
        'type_n': _vcall('GetTypeN', (h,)),
        'name': _vcall('GetName', (h,)),
        'class': _vcall('GetClass', (h,)),
        'layer': _vcall('GetLName', (_vcall('GetLayer', (h,)),)),
        'location': _loc(h),
        'parametric_record': rec_name,
    }

    # route 1 — parametric record, every field
    prec = _vcall('GetParametricRecord', (h,))
    pf = {}
    if prec:
        nf = int(_vcall('NumFields', (prec,), 0) or 0)
        for i in range(1, nf + 1):
            fn = _vcall('GetFldName', (prec, i))
            if not fn:
                continue
            pf[fn] = _vcall('GetRField', (h, rec_name, fn))
    s['parametric_fields'] = pf
    s['parametric_field_count'] = len(pf)

    # route 2 — every ATTACHED record (a Lighting Device commonly carries
    # extra formats, e.g. Light Info Record, beyond its parametric one)
    attached = {}
    n = int(_vcall('NumRecords', (h,), 0) or 0)
    for i in range(1, n + 1):
        rh = _vcall('GetRecord', (h, i))
        if not rh:
            continue
        rn = _vcall('GetName', (rh,))
        if not rn or rn == rec_name:
            continue
        flds = {}
        nf = int(_vcall('NumFields', (rh,), 0) or 0)
        for j in range(1, nf + 1):
            fn = _vcall('GetFldName', (rh, j))
            if fn:
                flds[fn] = _vcall('GetRField', (h, rn, fn))
        attached[rn] = flds
    s['attached_records'] = attached

    # route 3 — LDevice_* universal names, and the resolved-candidate trace
    trace = {}
    logical = {k: _read_field(h, rec_name, k, trace)
               for k in _FIELD_CANDIDATES}
    s['logical_fields'] = logical
    s['resolved_field_spellings'] = trace
    s['cells'] = _cell_rows(h, rec_name)
    s['ldevice'] = {
        'cell_count': _cell_count(h),
        'accessory_count_cell0': _vcall('LDevice_GetAccCount', (h, 0)),
        'is_schematic_view_obj': _vcall('IsLDSchematicViewObj', (h,)),
        'load_parent': _oid(_vcall('GetLoadParent', (h,))),
        'hanging_pos_load0': _oid(_vcall('OLDGetHangingPos', (h, 0))),
    }
    s['ldevice_note'] = (
        'load_parent / hanging_pos_load0 are the two candidate ways to get a '
        "fixture's hanging position without reading the Position text field. "
        "GetLoadParent's vs_index doc string is a copy-paste of "
        "GetCellCount's, so only its name and HANDLE return are trustworthy "
        '— this dump is what decides which of the two is correct.')
    return s


# ═══════════════════════════════════════════════════════════════════════════
# 2. sl_list_fixtures / sl_get_fixture — READ-ONLY
# ═══════════════════════════════════════════════════════════════════════════

def _fixture_summary(h, rec_name=None, trace=None, with_cells=True):
    rn = rec_name or _pio_record_name(h)
    f = lambda k: _read_field(h, rn, k, _LD_CELL, trace)
    row = {
        'object_id': _oid(h),
        'channel':  f('channel'),
        'unit':     f('unit'),
        'address':  f('address'),
        'universe': f('universe'),
        'position': f('position'),
        'purpose':  f('purpose'),
        'symbol':   f('symbol'),
        'layer':    _vcall('GetLName', (_vcall('GetLayer', (h,)),)),
        'class':    _vcall('GetClass', (h,)),
    }
    if with_cells:
        n = _cell_count(h)
        row['cell_count'] = n
        # cells are only itemised when there is more than one — a single-cell
        # fixture's cell 0 IS the row above, and repeating it would double the
        # size of every patch report for no information.
        row['cells'] = _cell_rows(h, rn, n) if n > 1 else None
    return row


def _lighting_devices(limit=MAX_OBJECTS):
    """(handles, record_name_that_matched, meta). Tries each LD candidate."""
    last_meta = {}
    for cand in LD_REC_CANDIDATES:
        hs, meta = _pios_named(cand, limit)
        last_meta = meta
        if hs:
            return hs, cand, meta
    return [], None, last_meta


@_guard
def sl_list_fixtures(p):
    """Lighting devices in the open document, optionally filtered.

    params:
      position  str   exact hanging-position name (case-insensitive)
      universe  str   universe, compared as a string
      layer     str   design layer name
      cells     bool  itemise per-cell patch data (default True)
      limit     int   traversal cap

    Filters match on cell 0 for a single-cell fixture and on ANY cell for a
    multi-cell one — a 12-cell bar whose cells span universes 1 and 2 must
    appear in both universe filters, or filtering silently hides half the rig.

    Returns {'status':'ok','count':n,'record':<matched record name>,
             'fixtures':[...], '_meta':{...}} — or a warning naming every
    candidate that was tried, so a miss is never a silently empty list.
    """
    limit = int(p.get('limit', MAX_OBJECTS) or MAX_OBJECTS)
    with_cells = p.get('cells', True)
    hs, rec, meta = _lighting_devices(limit)
    if not hs:
        return {'status': 'ok', 'count': 0, 'fixtures': [], 'record': None,
                'warning': 'No Lighting Device PIOs found. Tried parametric '
                           'record names %s. Run sl_dump_records to see the '
                           "document's actual PIO census."
                           % (list(LD_REC_CANDIDATES),),
                '_meta': _vs_meta({'lookup': meta})}

    rows = [_fixture_summary(h, rec, None, with_cells) for h in hs]

    def _any_cell(r, key, want):
        vals = [str(r.get(key) or '').strip()]
        for c in (r.get('cells') or []):
            vals.append(str(c.get(key) or '').strip())
        return want in vals

    if p.get('position'):
        want = str(p['position']).strip().lower()
        rows = [r for r in rows
                if (r['position'] or '').strip().lower() == want]
    if p.get('universe') not in (None, ''):
        want = str(p['universe']).strip()
        rows = [r for r in rows if _any_cell(r, 'universe', want)]
    if p.get('layer'):
        want = str(p['layer'])
        rows = [r for r in rows if r['layer'] == want]

    return {'status': 'ok', 'record': rec, 'count': len(rows),
            'multicell_count': sum(1 for r in rows
                                   if (r.get('cell_count') or 1) > 1),
            'fixtures': rows,
            '_meta': _vs_meta({'lookup': meta})}


@_guard
def sl_get_fixture(p):
    """One fixture, in full.

    params (one of):
      object_id  str  UUID
      channel    str  match on the Channel field
      unit       str  match on the Unit Number field

    Returns every parametric field, every cell, and the resolved field
    spellings, so this doubles as a per-object probe while names are TBV.
    """
    h = None
    rec = None
    meta = {}
    if p.get('object_id'):
        h = _h(p['object_id'])
        if not h:
            return {'error': 'Object not found: %s' % p['object_id'],
                    '_meta': _vs_meta()}
        rec = _pio_record_name(h)
    else:
        key = 'channel' if p.get('channel') not in (None, '') else (
            'unit' if p.get('unit') not in (None, '') else None)
        if key is None:
            return {'error': 'sl_get_fixture needs object_id, channel or unit',
                    '_meta': _vs_meta()}
        want = str(p[key]).strip()
        hs, rec, meta = _lighting_devices(
            int(p.get('limit', MAX_OBJECTS) or MAX_OBJECTS))
        matches = []
        for x in hs:
            vals = [str(_read_field(x, rec, key) or '').strip()]
            if key == 'channel':
                for c in _cell_rows(x, rec):
                    vals.append(str(c.get('channel') or '').strip())
            if want in vals:
                matches.append(x)
        if not matches:
            return {'error': 'No fixture with %s=%r' % (key, want),
                    '_meta': _vs_meta({'lookup': meta})}
        if len(matches) > 1:
            return {'error': 'Ambiguous: %d fixtures have %s=%r. Use '
                             'object_id (see sl_patch_report duplicate flags).'
                             % (len(matches), key, want),
                    'object_ids': [_oid(x) for x in matches],
                    '_meta': _vs_meta({'lookup': meta})}
        h = matches[0]

    trace = {}
    summary = _fixture_summary(h, rec, trace)
    summary['status'] = 'ok'
    summary['resolved_field_spellings'] = trace
    summary['location'] = _loc(h)
    summary['all_cells'] = _cell_rows(h, rec)
    summary['accessory_count_cell0'] = _vcall('LDevice_GetAccCount', (h, 0))
    summary['hanging_position_object_id'] = _oid(
        _vcall('OLDGetHangingPos', (h, 0)))
    summary['load_parent_object_id'] = _oid(_vcall('GetLoadParent', (h,)))

    prec = _vcall('GetParametricRecord', (h,))
    if prec and rec:
        fields = {}
        nf = _vcall('NumFields', (prec,), 0) or 0
        for k in range(1, int(nf) + 1):
            fn = _vcall('GetFldName', (prec, k))
            if fn:
                fields[fn] = _vcall('GetRField', (h, rec, fn))
        summary['all_fields'] = fields
    summary['_meta'] = _vs_meta({'lookup': meta})
    return summary


# ═══════════════════════════════════════════════════════════════════════════
# 3. sl_patch_report — READ-ONLY
# ═══════════════════════════════════════════════════════════════════════════

@_guard
def sl_patch_report(p):
    """The channel <-> address <-> universe <-> position table, with conflicts.

    ONE ROW PER CELL, not per fixture. A multi-cell fixture (LED bar, moving-
    head array) patches as several addresses, so collapsing it to one row
    hides real collisions on cells 2..N — see _cell_rows. Single-cell
    fixtures produce exactly one row, so the common case is unchanged.

    Duplicate detection is carried over from domain/reference_handlers.py
    (7/7 green on the mock): duplicate CHANNEL and duplicate
    (UNIVERSE, ADDRESS) are flagged independently, because they are different
    production faults — two fixtures on one channel is usually intentional (a
    pair), two on one DMX address is a patch collision.

    Three deliberate changes from the reference:
      - per-cell rows (above);
      - blank channels/addresses are not duplicates of each other, or an
        unpatched rig flags every fixture against every other one — they are
        counted as unpatched_count instead;
      - flags carry the other row's object_id and cell as well as its unit,
        since unit numbers are frequently blank and 'with_unit: None' is not
        actionable.

    params:
      position / universe / layer / limit — same filters as sl_list_fixtures
      only_conflicts  bool  return only flagged rows (default False)
    """
    listed = sl_list_fixtures(dict(p, cells=True))
    if 'error' in listed:
        return listed
    fixtures = listed.get('fixtures', [])

    rows = []
    for fxt in fixtures:
        cells = fxt.get('cells')
        if not cells:
            cells = [{'cell': 0, 'channel': fxt['channel'],
                      'address': fxt['address'], 'universe': fxt['universe']}]
        for c in cells:
            rows.append({
                'object_id': fxt['object_id'],
                'cell': c['cell'],
                'cell_count': fxt.get('cell_count', 1),
                'channel': c['channel'],
                'address': c['address'],
                'universe': c['universe'],
                'unit': fxt['unit'],
                'position': fxt['position'],
                'purpose': fxt['purpose'],
                'symbol': fxt['symbol'],
                'layer': fxt['layer'],
                'flags': [],
            })

    def _ref(r):
        return {'with_unit': r['unit'], 'with_object_id': r['object_id'],
                'with_cell': r['cell']}

    ch_seen, ad_seen = {}, {}
    for r in rows:
        if not _blank(r['channel']):
            key = str(r['channel']).strip()
            if key in ch_seen:
                r['flags'].append(dict(kind='duplicate_channel', channel=key,
                                       **_ref(ch_seen[key])))
            else:
                ch_seen[key] = r
        if not _blank(r['address']):
            key = (str(r['universe'] or '').strip(), str(r['address']).strip())
            if key in ad_seen:
                r['flags'].append(dict(kind='duplicate_address',
                                       universe=key[0], address=key[1],
                                       **_ref(ad_seen[key])))
            else:
                ad_seen[key] = r

    conflicts = [r for r in rows if r['flags']]
    unpatched = [r for r in rows if _blank(r['address'])]

    return {
        'status': 'ok',
        'record': listed.get('record'),
        'row_granularity': 'one row per cell',
        'fixture_count': len(fixtures),
        'count': len(rows),
        'multicell_fixture_count': listed.get('multicell_count', 0),
        'conflict_count': len(conflicts),
        'unpatched_count': len(unpatched),
        'universes': sorted({str(r['universe']) for r in rows
                             if not _blank(r['universe'])}),
        'positions': sorted({str(r['position']) for r in rows
                             if not _blank(r['position'])}),
        'fixtures': conflicts if p.get('only_conflicts') else rows,
        '_meta': listed.get('_meta'),
    }


# ═══════════════════════════════════════════════════════════════════════════
# 4. sl_positions — READ-ONLY
# ═══════════════════════════════════════════════════════════════════════════

@_guard
def sl_positions(p):
    """Hanging positions with fixture counts.

    Counts come from two independent sources and both are reported, because
    they disagree in real files and the disagreement is the useful signal:

      by_field   — grouping fixtures on their Position text field. This is
                   what a lighting designer sees in the OIP and in reports.
      by_parent  — grouping on OLDGetHangingPos(fixture, 0), i.e. what the
                   fixture is geometrically attached to.

    A position where by_field > by_parent means fixtures are labelled onto a
    position they are not actually hung on — the classic stale-Position-field
    bug after a truss gets moved or renamed. Braceworks' UpdatePositionParam()
    is the native fix, but it is a WRITE and so is not called here.

    params:
      limit  int  traversal cap (default 2000)
    """
    limit = int(p.get('limit', 2000) or 2000)

    # hanging-position PIOs actually present
    hp_objs, hp_rec, hp_meta = [], None, {}
    for cand in HP_REC_CANDIDATES:
        hp_objs, hp_meta = _pios_named(cand, limit)
        if hp_objs:
            hp_rec = cand
            break

    positions = {}

    def _slot(name):
        return positions.setdefault(str(name), {
            'name': str(name), 'object_id': None,
            'fixture_count_by_field': 0, 'fixture_count_by_parent': 0,
            'universes': set(), 'channels': [], 'layer': None,
            'exists_as_object': False})

    for h in hp_objs:
        nm = (_vcall('GetName', (h,))
              or _read_field(h, hp_rec, 'position')
              or '(unnamed)')
        s = _slot(nm)
        s['object_id'] = _oid(h)
        s['layer'] = _vcall('GetLName', (_vcall('GetLayer', (h,)),))
        s['exists_as_object'] = True

    fx, ld_rec, ld_meta = _lighting_devices(limit)
    hp_by_oid = {_oid(h): h for h in hp_objs}

    orphans = 0
    for h in fx:
        name = _read_field(h, ld_rec, 'position')
        s = _slot(name if not _blank(name) else '(no position)')
        s['fixture_count_by_field'] += 1
        u = _read_field(h, ld_rec, 'universe')
        if not _blank(u):
            s['universes'].add(str(u))
        c = _read_field(h, ld_rec, 'channel')
        if not _blank(c):
            s['channels'].append(str(c))

        parent = _vcall('OLDGetHangingPos', (h, 0))
        poid = _oid(parent)
        if poid and poid in hp_by_oid:
            pname = (_vcall('GetName', (hp_by_oid[poid],))
                     or '(unnamed)')
            _slot(pname)['fixture_count_by_parent'] += 1
        else:
            orphans += 1

    rows = []
    for s in positions.values():
        s['universes'] = sorted(s['universes'])
        s['channels'] = sorted(s['channels'])
        s['mismatch'] = (s['fixture_count_by_field']
                         != s['fixture_count_by_parent'])
        rows.append(s)
    rows.sort(key=lambda r: (-r['fixture_count_by_field'], r['name']))

    return {
        'status': 'ok',
        'position_record': hp_rec,
        'fixture_record': ld_rec,
        'count': len(rows),
        'fixtures_with_no_hanging_parent': orphans,
        'positions': rows,
        'note': 'by_field vs by_parent disagreement = fixtures labelled onto '
                'a position they are not attached to. Braceworks '
                'UpdatePositionParam(positionHandle) is the native fix; it is '
                'a write and is not called by any read-only verb.',
        '_meta': _vs_meta({'fixture_lookup': ld_meta,
                           'position_lookup': hp_meta}),
    }


# ═══════════════════════════════════════════════════════════════════════════
# 5. sl_insert_fixture — DESIGN ONLY. NOT IMPLEMENTED THIS PASS (T3.4).
# ═══════════════════════════════════════════════════════════════════════════
#
# Deliberately NOT defined as a function: the pump dispatches by getattr on
# the module, so defining sl_insert_fixture at all would make it callable.
# See domain/docs/SPOTLIGHT-DESIGN.md for the long form.
#
# ---------------------------------------------------------------------------
# THE HAZARD: Data-Tag pairing
# ---------------------------------------------------------------------------
# RESEARCH.md §3: duplicating a Lighting Device and its Data Tag separately
# via HDuplicate BREAKS the tag association; copy/paste as a pair preserves
# it. Two things about this the research got wrong or left out:
#
#   a) "Data Tag = type 86" is not a discriminator. 86 is Plug-in Object —
#      the Lighting Device is ALSO type 86, so is the Hanging Position, so is
#      every Marionette node (commands.py:3977). A naive implementation that
#      collects "the type-86 objects near the fixture" to re-tag them will
#      grab the fixture itself and any neighbouring PIO. Discriminate on
#      vs.GetName(vs.GetParametricRecord(h)) == '<Data Tag record>'.
#
#   b) The breakage is REPAIRABLE in script. VW2026 exposes a Data Tag
#      Interface Library that the research did not find:
#          DT_AssociateWithObj(hDataTag, hObject) -> BOOLEAN   [verified sig]
#          DT_UpdateTaggedTags(hObject)           -> BOOLEAN   [verified sig]
#      So the fix is not "avoid HDuplicate" — it is "HDuplicate, then
#      re-associate explicitly and check the BOOLEAN". Copy/paste via
#      DoMenuTextByName is the fallback, not the primary, because it depends
#      on selection state and localized menu names and cannot be verified.
#
# ---------------------------------------------------------------------------
# CALL PLAN (verified vs. unverified, per call)
# ---------------------------------------------------------------------------
#   vs.NameUndoEvent(name)                       VERIFIED sig. One per call.
#   vs.CreateCustomObjectN(objectName, p,        VERIFIED sig (4 args:
#       rotationAngle, showPref) -> HANDLE       objectName, p, rotationAngle,
#                                                showPref). objectName is the
#                                                PIO name ('Lighting Device');
#                                                UNVERIFIED that Spotlight
#                                                accepts a bare create without
#                                                its own insertion machinery.
#   vs.LDevice_SetParamStr(h, 0, -1, uname, v)   VERIFIED sig. Preferred over
#                                                SetRField: universal name, so
#                                                localization-safe.
#   vs.SetRField(h, rec, field, str(v))          VERIFIED sig. Fallback only.
#   vs.LDevice_Reset(h)                          VERIFIED sig. Use INSTEAD of
#                                                the generic ResetObject for a
#                                                lighting device.
#   vs.ResetObject(h)                            VERIFIED sig. Generic; for
#                                                the Data Tag and the position.
#   vs.DT_AssociateWithObj(hTag, hFixture)       VERIFIED sig -> BOOLEAN.
#   vs.DT_UpdateTaggedTags(hFixture)             VERIFIED sig -> BOOLEAN.
#   vs.HDuplicate(h, dx, dy) -> HANDLE           VERIFIED sig.
#   vs.OLDGetHangingPos(h, 0) -> HANDLE          VERIFIED sig; semantics TBV.
#   vs.UpdatePositionParam(hPosition)            VERIFIED sig. Rewrites the
#                                                'Position' param of every load
#                                                on a position — call it LAST,
#                                                it can overwrite a Position
#                                                value just written.
#   vs.GetLoadParent(h) -> HANDLE                VERIFIED sig; doc string is a
#                                                copy-paste of GetCellCount's,
#                                                so semantics are TBV.
#
# UNVERIFIED / must be settled by sl_dump_records + one sandbox file first:
#   - the PIO name string CreateCustomObjectN wants for a lighting device
#   - every universal name in _FIELD_CANDIDATES
#   - whether a fixture created by CreateCustomObjectN gets a Data Tag at all
#     (tags are usually placed by the user or by a tool, not by creation)
#   - whether attaching to a hanging position needs geometry (drop the fixture
#     inside the position's bounds) or only the Position field, or both
#   - vs.Layer(name) is QUARANTINED (commands.py:set_active_layer — it parks
#     the script frame on VW2026). Any insert must place onto a layer WITHOUT
#     it.
#
# ---------------------------------------------------------------------------
# SAFE IMPLEMENTATION SHAPE
# ---------------------------------------------------------------------------
#   def sl_insert_fixture(p):
#       1. Validate: symbol/PIO name resolves; position exists; refuse to
#          patch onto an occupied (universe,address) unless allow_conflict —
#          reuse sl_patch_report's index rather than a second scan.
#       2. vs.NameUndoEvent('MCP: insert fixture') — exactly once, first.
#       3. Create:
#            preferred  h = vs.CreateCustomObjectN(<LD pio name>, (x,y), rot,
#                                                   False)
#            fallback   h = vs.HDuplicate(<template fixture>, dx, dy)
#                       -- ONLY the fixture, never the fixture+tag as two
#                          separate HDuplicate calls.
#       4. Fields via vs.LDevice_SetParamStr(h, 0, -1, uname, value), one per
#          logical field, universal names only.
#       5. vs.LDevice_Reset(h).
#       6. TAG PAIRING — the whole point:
#            if duplicating from a template that HAS a tag:
#              a. find the template's tag by parametric record name, NOT by
#                 type 86;
#              b. hTagNew = vs.HDuplicate(hTagOld, dx, dy);
#              c. ok = vs.DT_AssociateWithObj(hTagNew, h)
#              d. if not ok: vs.DelObject(hTagNew) and return
#                 {'error': 'tag association failed'} — leaving an
#                 orphaned tag pointing at the TEMPLATE fixture is the exact
#                 silent-corruption failure the forum thread describes, and
#                 is worse than no tag.
#              e. vs.DT_UpdateTaggedTags(h) to redraw.
#            Never call HDuplicate on fixture and tag and assume the pair
#            survived. Always assert on the DT_AssociateWithObj boolean.
#       7. If a position was named: vs.UpdatePositionParam(hPosition) LAST,
#          after all field writes, then re-read the fixture and return the
#          ACTUAL stored values, not the requested ones.
#       8. Return {'status':'ok','object_id':_oid(h),'tag_object_id':...,
#                  'tag_associated':bool,'fields':<read back>}.
#
# MULTI-CELL AND ACCESSORIES ON THE WRITE PATH
# ---------------------------------------------------------------------------
#   - Field writes must specify the cell: LDevice_SetParamStr(h, cell, -1,
#     uname, v). Writing cell 0 on a 12-cell bar patches one cell and leaves
#     eleven wrong, which looks like success in the OIP.
#   - LDevice_AddAccessory(h, cellIndex, accessorySymbol) -> LONGINT and
#     LDevice_DeleteAcc(h, cellIndex, accessoryIndex) MUTATE. They are the
#     right calls for gobo/scroller accessories, and they are the reason the
#     read verbs only ever touch LDevice_GetParam*. Accessory indices shift
#     after a delete — re-read LDevice_GetAccCount rather than caching one.
#   - Accessories carry their own patch data (accIndex >= 0). A patch report
#     that ignores them undercounts DMX footprint the same way ignoring cells
#     does.
#
# PRE-FLIGHT for whoever implements this (T3.4):
#   - T3.1 undo/save guardrails must land first (it blocks all of Phase 3).
#   - Run sl_dump_records on a real show file and pin every TBV name.
#   - Prove the tag round-trip on a scratch document: duplicate a tagged
#     fixture, re-associate, save, reopen, confirm the new tag reads the NEW
#     fixture's channel and not the template's. That reopen is the test —
#     an in-session tag can look right and still be mis-associated on disk.
# ═══════════════════════════════════════════════════════════════════════════


# ── registry ────────────────────────────────────────────────────────────────
# The pump dispatches with getattr(commands, cmd), so commands.py needs a
# single line — `from sl_commands import *` — for these to be reachable.
# That edit belongs to commands.py's owner; nothing here touches it.

SL_HANDLERS = {
    'sl_dump_records':  sl_dump_records,
    'sl_list_fixtures': sl_list_fixtures,
    'sl_get_fixture':   sl_get_fixture,
    'sl_patch_report':  sl_patch_report,
    'sl_positions':     sl_positions,
}

# Every verb here is read-only, but none matches the pump's read-only name
# prefixes ('get_', 'list_', 'count_', 'find_'), so vwx_pump will conservatively
# treat them as mutations and hold them for genuine dispatch. That is safe,
# just slower. The MCP server should merge this set into ipc/readonly.json so
# they drain in the background instead.
SL_READONLY = frozenset(SL_HANDLERS)

# `set_vs` is deliberately NOT exported. commands.py does
# `from cc_commands import *` and `from sl_commands import *`; both modules
# define set_vs, so exporting it would bind commands.set_vs to whichever
# module imported last and silently inject the mock into only one of them.
# cc_commands' __all__ omits it for the same reason. Tests import the module
# directly (`import sl_commands; sl_commands.set_vs(mock)`).
__all__ = list(SL_HANDLERS) + ['SL_HANDLERS', 'SL_READONLY']
