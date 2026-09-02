# Spotlight Domain Design

Owner: Spotlight Agent. Covers `sl_*` verbs in `vwx-plugin/sl_commands.py`.
Companion to `RESEARCH.md` §3 and `TASKS.md` T1.3 / T2.4 / T3.4.

Status as of this pass: **T1.1 (Spotlight scope) + T2.4 implemented, read-only.
T3.4 (`sl_insert_fixture`) is DESIGN ONLY — deliberately not implemented and
deliberately not even defined as a function**, because `vwx_pump._dispatch`
resolves commands with `getattr(commands, cmd)`, so any function that exists is
callable. A design that exists as a `def` is a write path that shipped by
accident.

---

## 0. Two corrections to RESEARCH.md §3

Both were found by grepping `vwx-plugin/vs_index.json` (3071 signatures) rather
than by trusting the standing research, and both change the design.

### 0.1 There *is* a Spotlight API family

RESEARCH.md §3 states "No `SL_*` family; ... manipulated with generic `vs.*`
calls." That is wrong. Vectorworks 2026 ships:

| Family | Count | What matters |
|---|---|---|
| `LDevice_*` | 24 | `Get/SetParam{Str,Long,Real,Bool}(h, cellIndex, accIndex, universalName)` — field access **by universal (worksheet) name**, plus `LDevice_GetCellCount`, `LDevice_GetAccCount`, `LDevice_Reset`, `LDevice_ResetVisual`, accessory add/delete/position |
| `DT_*` | 5 | `DT_AssociateWithObj`, `DT_UpdateTaggedTags`, `DT_ResetAllDataTags`, `DT_Begin/EndMultipleMove` |
| `SL_*` | 4 | `SL_Export`, `SL_Import`, `SL_UpdateSAcc`, `SL_UpdateUID` (XML data exchange) |
| misc | — | `GetLoadParent`, `IsLDSchematicViewObj`, `ApplyLightInfoRecord`, `Get/SetVisionMapping` |
| Braceworks (`Truss Analysis`) | — | `OLDGetHangingPos(h, loadIndex) -> HANDLE`, `OLDFindAttachHangPos`, `HP_AutoAttachLoads`, `UpdatePositionParam` |

The consequence for design: **`LDevice_GetParamStr(h, cell, -1, universalName)`
is the primary read path, not `GetRField`** — the inverse of
`domain/reference_handlers.py`, which uses `GetRField` exclusively. Universal names are the worksheet
names — they are stable across Vectorworks localizations and across versions,
whereas the record field name displayed in the OIP is not. `sl_commands.py`
tries the universal name first and falls back to `GetRField` on the parametric
record name, and reports which one won in `resolved_field_spellings`.

`cellIndex=0` is the first cell; `accIndex=-1` addresses the lighting device
itself rather than an attached accessory. Note both indices are required on
every `Get/SetParam*` call.

`GetRField` cannot substitute for cells 1..N. A record holds **one value per
field**, so asking it for cell 3's address silently returns cell 0's. The
fallback therefore applies only to cell 0; for cell > 0 a miss stays a miss and
is reported as such in `resolved_field_spellings`.

### 0.2 "Data Tag = type 86" is not a discriminator

RESEARCH.md §3 and TASKS.md T1.3 both say "Data Tag = type 86". Type 86 is
**Plug-in Object**. Evidence: `commands.py:3977` uses `vs.GetTypeN(ch) == 86`
to find Marionette node PIOs. So the Lighting Device is type 86, the Hanging
Position is type 86, the Data Tag is type 86, and every Marionette node is
type 86. (Separately, `commands.py` `OBJ_TYPES[86] = 'space'` is wrong and
should be corrected by that module's owner to `'plugin_obj'`; `OBJ_TYPES[68]`
currently holds `'plugin_obj'`.)

**The discriminator is the parametric record name**:

```python
vs.GetName(vs.GetParametricRecord(h))   # -> 'Lighting Device' | 'Data Tag' | ...
```

Every verb in `sl_commands.py` identifies PIO families this way. This matters
most in the insert design (§4): an implementation that gathers "type-86 objects
near the fixture" in order to re-tag them will pick up the fixture itself.

---

## 1. Implemented verbs (read-only)

| Verb | Purpose |
|---|---|
| `sl_dump_records` | T1.1/T1.3 discovery: Spotlight record formats + field names/types, PIO census by parametric record, one full sample of each Spotlight PIO family, and the **live universal-name probe** that closes the TBV list |
| `sl_list_fixtures` | Lighting devices, filterable by `position`, `universe`, `layer` |
| `sl_get_fixture` | One fixture by `object_id` / `channel` / `unit`, with all parametric fields |
| `sl_patch_report` | channel ↔ address ↔ universe ↔ position table with conflict flags, **one row per cell** |
| `sl_positions` | Hanging positions with fixture counts, by field *and* by geometric parent |

All five are read-only: no `SetRField`, no `ResetObject`, no `DoMenuTextByName`,
no selection change. All five are wrapped so nothing can raise into Vectorworks
(verified against three hostile `vs` stubs: absent, `None`, and one where every
call raises).

Scope boundary with the ConnectCAD agent: `sl_dump_records` dumps *fields* only
for formats matching Spotlight hints (`lighting device`, `hanging position`,
`data tag`, `light info`, `instrument`, `lighting`). `Device`, `Socket`,
`Circuit`, `Equipment Item` belong to `cc_dump_records`. `all_format_names`
returns the bare *names* of every format in the document so neither agent is
blind to what the other owns, without either dumping the other's fields.

### 1.1 Design choices worth knowing

**`sl_patch_report` blank handling.** The reference implementation
(`domain/reference_handlers.py`) seeds `ch_seen` / `ad_seen` with blank values,
so on an unpatched rig every fixture flags as a duplicate of every other one.
Blank channels and blank addresses are now skipped, and counted separately as
`unpatched_count`. The duplicate logic itself — duplicate channel and duplicate
`(universe, address)` tracked independently — is carried over unchanged,
because it is correct: two fixtures on one channel is usually intentional (a
pair), two on one DMX address is a patch collision. Flags now also carry the
other fixture's `object_id`, since unit numbers are frequently blank in
practice and `with_unit: None` is not actionable.

**`sl_patch_report` emits one row per CELL, not per fixture.** See §1.2 — this
is the correctness fix, not a cosmetic one.

**`sl_positions` counts fixtures twice, on purpose.** `fixture_count_by_field`
groups on the `Position` text field (what the LD sees in the OIP and in
reports); `fixture_count_by_parent` groups on `OLDGetHangingPos(fixture, 0)`
(what the fixture is geometrically attached to). Where they disagree,
`mismatch: true`, and that disagreement is the point — it is the classic stale-
`Position`-field bug after a truss is moved or renamed, and it is invisible in
any single-source report. Braceworks' `UpdatePositionParam(positionHandle)` is
the native fix; it is a write, so no read-only verb calls it.

### 1.2 Multi-cell fixtures — a correctness bug in the reference

`LDevice_GetCellCount` exists because a Lighting Device can carry several
cells. An LED bar, a moving-head array, a multi-cell wash: **each cell patches
to its own channel and DMX address.** A "fixture" is therefore not one patch
row.

`domain/reference_handlers.py` reads only the record — one value per field — so
it reports a 12-cell bar as a single address. Cells 2..N are invisible to its
duplicate-address detection, which is the one thing a patch report exists to
catch. That is a correctness bug, not a gap: the report returns a clean bill of
health on a rig that has a real DMX collision.

`sl_patch_report` expands every fixture to one row per cell
(`row_granularity: "one row per cell"`), and reports `fixture_count` and
`count` separately. Single-cell fixtures produce exactly one row, so the common
case is unchanged in shape and size — `sl_list_fixtures` only itemises `cells`
when `cell_count > 1`, since repeating cell 0 for every ordinary fixture would
double the size of every report for no information.

Filters and lookups match on **any** cell: `sl_list_fixtures(universe=2)` must
return a bar whose cells span universes 1 and 2, and
`sl_get_fixture(channel='22')` finds the bar when 22 is a cell channel. Matching
only the fixture-level value would silently hide half the rig.

Regression-tested against a fake 4-cell bar whose cell 2 collides with another
fixture's address — the exact collision a per-fixture report cannot see.

### 1.3 Nothing trusts a single API or a single root

Three defences, all regression-tested by stubbing the relevant call out:

**Runtime chokepoint.** No uncertain `vs.*` call is made directly. Everything
goes through `_vcall(name, args)`, which resolves with `getattr` at runtime and
records `ok` / `blank` / `absent` / `raised` into `_meta.vs_probe` on every
verb result. `vs_index.json` mirrors the SDK stub, not a given build — the
first live run reports what is actually there rather than returning empty.

**Multi-root document walk.** `_walk_document` unions a layer walk
(`FLayer`/`NextLayer`/`FInLayer`), `FObject()`, and both PIO criteria
spellings, dedupes by `GetObjectUuid`, and descends containers via
`FInGroup`/`FIn3D` to depth 6. Each root's contribution is reported in
`walk.roots` — a root that contributes 0 on a non-empty document is itself a
finding. **An empty `ForEachObject` result is never accepted as the answer**:
a wrong criteria keyword returns zero rows silently rather than erroring, so
`_pios_named` pays for the full walk before reporting zero. Verified: with
`ForEachObject` stubbed dead the census is still complete, and with the layer
walk *also* dead `FObject` recovers every object.

**Union'd format harvest.** Record formats come from three independent sources
— criteria `T=RECDEF`, records attached to walked objects
(`NumRecords`→`GetRecord`), and `GetParametricRecord` — with `format_sources`
reporting what each contributed. Format discovery is deliberately **not** gated
on finding PIO buckets first: on a document where `GetParametricRecord` returns
nothing, a PIO-gated harvest reports almost no formats and wastes the one run
against the user's real file.

---

## 2. Field names: what is verified, what is TBV

`Position` is the only field name with independent corroboration — the
`vs_index.json` doc string for `UpdatePositionParam` reads *"changes the
'Position' parameter for all loads."*

Everything else is **TBV** and is stored as an ordered *candidate list*
(`_FIELD_CANDIDATES` in `sl_commands.py`), never as a hardcoded constant.
Nothing breaks if a spelling is wrong; the verb reports `via: None` for that
field and `sl_dump_records` shows the real spellings.

TBV list:

- Record format names: `Lighting Device`, `Hanging Position`, `Data Tag`
- Field names: `Channel`, `Unit Number`, `Address`, `Universe`, `Purpose`,
  `Symbol Name`, `Instrument Type`, `Wattage`, `Color`, `Fixture Mode`
- Universal/worksheet names used by `LDevice_GetParam*`
- `GetFldType` integer → type-name mapping (raw int is always returned too)
- `'T=PLUGINOBJ'` vs `'T=PLUGINOBJECT'` — `commands.py` uses **both**, at
  lines 2212 and 4290. `sl_commands` tries each and reports which returned
  objects, in `pio_criteria_used`.
- `GetLoadParent(h)` semantics. Its `vs_index` doc string is a verbatim
  copy-paste of `LDevice_GetCellCount`'s, so only its name and `HANDLE` return
  type are trustworthy. `sl_dump_records` reports it alongside
  `OLDGetHangingPos(h, 0)` so one live run settles which is correct.
- Whether `Universe` is a separate field or is encoded inside `Address` as
  `u/a` (Vectorworks supports both patch styles).

**One run of `sl_dump_records` against a real show file collapses this entire
list to fact.** The key output is `universal_names.resolved`: the dump probes
37 candidate universal names against a live fixture via
`LDevice_GetParamStr` and returns the ones that answer, with their values.
That list is the authoritative field map — pin `_FIELD_CANDIDATES` to it and
the TBV problem is closed. (A blank result is ambiguous: unknown name, or known
name with no value on that fixture. `blank_or_unknown` is reported separately
for that reason.)

Run it with:

```
python3 tools/sl_dump.py --out domain/docs/records/spotlight.json
```

`tools/sl_dump.py` loads `sl_commands.py` inside Vectorworks over the bridge's
`execute_script` and calls `sl_dump_records`. It requires the bridge dialog
open (Tools > Plug-ins > Run Script... > `START_BRIDGE_MAC.py`). **Not yet run
— the bridge was not listening on 127.0.0.1:9878 during this pass**, so every
TBV above is still open.

The dump also returns `GetVisionMapping()`, which yields the Lighting
Device field names mapped to a visualizer in `SetVisionMapping` order — `color,
universe, gobo, name, channel, fixtureid` — giving independent confirmation of
the `Universe` and `Channel` spellings for free.

---

## 3. Deliberately not used

- **`PON='Lighting Device'` criteria.** If the actual PIO name differs by case,
  a space, or localization, `ForEachObject` silently returns zero objects and
  the caller reads that as "this rig has no fixtures". `sl_commands` collects
  all PIOs and filters in Python on the parametric record name, so a miss shows
  up as a populated `pio_census` with no `Lighting Device` row — visibly wrong
  instead of quietly empty.
- **`vs.Layer(name)`.** Quarantined per `commands.py:set_active_layer` — on
  VW2026 it parks the enclosing script frame in a nested message loop and has
  been observed to kill the file pump. Any future insert path must place onto a
  layer without it.
- **`vs.GetPluginType(h)`.** Used by `commands.py:2217` but **absent from
  `vs_index.json`**. `GetName(GetParametricRecord(h))` is indexed and does the
  same job.

---

## 4. `sl_insert_fixture` — design (T3.4, NOT IMPLEMENTED)

### 4.1 The hazard, stated precisely

RESEARCH.md §3 records the forum finding: duplicating a Lighting Device and its
Data Tag separately via `HDuplicate` **breaks the tag association**; copy/paste
as a pair preserves it. Two things to add.

**(a) The naive fix is unsafe.** "Find the type-86 objects near the fixture and
re-tag them" picks up the fixture itself, the hanging position, and any
Marionette node in the vicinity — all type 86 (§0.2). The tag must be located
by parametric record name.

**(b) The breakage is repairable in script.** The Data Tag Interface Library
was not found by the original research:

```
DT_AssociateWithObj(hDataTag, hObject) -> BOOLEAN    # verified signature
DT_UpdateTaggedTags(hObject)           -> BOOLEAN    # verified signature
```

So the rule is **not** "avoid `HDuplicate`". It is:

> `HDuplicate` the fixture and the tag separately, then **explicitly
> re-associate** with `DT_AssociateWithObj`, and **assert on the boolean it
> returns.**

Copy/paste via `DoMenuTextByName` is the *fallback*, not the primary path,
because it depends on selection state and on localized menu item names, neither
of which can be verified from `vs_index.json`.

**The failure mode to design against:** a duplicated tag that silently stays
associated with the *template* fixture. It renders plausibly — it shows a
channel, in the right place, next to the new fixture — and it is wrong. On a
plot with 400 fixtures nobody catches it until the tags are read on site. An
orphaned tag is worse than no tag, so if `DT_AssociateWithObj` returns false,
**delete the duplicated tag and fail the call**.

### 4.2 Call plan

Verified = signature and arity checked against `vs_index.json`.

| Call | Status | Note |
|---|---|---|
| `NameUndoEvent(eventName)` | verified | exactly one per tool call, first |
| `CreateCustomObjectN(objectName, p, rotationAngle, showPref) -> HANDLE` | verified sig | **unverified** that Spotlight accepts a bare create for a Lighting Device |
| `HDuplicate(h, x, y) -> HANDLE` | verified | duplicate-from-template path |
| `LDevice_SetParamStr(h, cell, -1, universalName, newValue)` | verified | preferred field write — localization-safe; **must be called per cell** |
| `LDevice_AddAccessory(h, cellIndex, accessorySymbol) -> LONGINT` | verified | **mutates**; accessory indices shift after a delete, so re-read `LDevice_GetAccCount` rather than caching one |
| `LDevice_DeleteAcc(h, cellIndex, accessoryIndex)` | verified | **mutates** |
| `SetRField(h, record, field, str(value))` | verified | fallback field write only |
| `LDevice_Reset(h)` | verified | use **instead of** generic `ResetObject` for a lighting device |
| `LDevice_ResetVisual(h)` | verified | clears the draw cache if the symbol changed |
| `ResetObject(h)` | verified | generic; for the Data Tag and the position |
| `DT_AssociateWithObj(hTag, hFixture) -> BOOLEAN` | verified | **the tag-pairing fix** |
| `DT_UpdateTaggedTags(hFixture) -> BOOLEAN` | verified | redraw tags on an object |
| `DT_Begin/EndMultipleMove()` | verified | bracket a bulk insert so tags reflow once |
| `OLDGetHangingPos(h, loadIndex) -> HANDLE` | verified sig, **semantics TBV** | |
| `GetLoadParent(h) -> HANDLE` | verified sig, **semantics TBV** | doc string is a copy-paste |
| `UpdatePositionParam(positionHandle)` | verified | **call LAST** — it rewrites the `Position` param of every load on the position and can overwrite a value just written |
| `DelObject(h)` | verified | rollback of a failed tag duplicate |

Unverified and blocking, to settle before writing code:

1. The PIO name string `CreateCustomObjectN` wants for a lighting device.
2. Every universal name in `_FIELD_CANDIDATES`.
3. Whether a fixture created by `CreateCustomObjectN` gets a Data Tag at all —
   tags are normally placed by the user or a tool, not by object creation. If
   not, the duplicate-from-template path is the *only* one that has a tag to
   preserve, which makes it the primary path and `CreateCustomObjectN` the
   secondary.
4. Whether attaching to a hanging position requires geometry (dropping the
   fixture inside the position's bounds so Braceworks picks it up), or only the
   `Position` field, or both. `sl_positions`' `by_field` vs `by_parent` split
   is what answers this.

### 4.3 Implementation shape

```
sl_insert_fixture(p):
  1. Validate. Symbol/PIO name resolves; position exists; refuse to patch onto
     an occupied (universe, address) unless allow_conflict — reuse
     sl_patch_report's index, do not run a second scan.
  2. NameUndoEvent('MCP: insert fixture')            # once, first
  3. Create:
       preferred: h = CreateCustomObjectN(<LD pio name>, (x,y), rot, False)
       fallback:  h = HDuplicate(<template fixture>, dx, dy)
                  -- the fixture ONLY, never fixture+tag as two blind
                     HDuplicate calls
  4. Fields: LDevice_SetParamStr(h, cell, -1, uname, value), universal names
     only, FOR EVERY CELL. Writing cell 0 on a 12-cell bar patches one cell
     and leaves eleven wrong — which looks like success in the OIP.
  5. LDevice_Reset(h)
  6. TAG PAIRING (only when duplicating a template that HAS a tag):
       a. locate the template's tag by parametric record name, NOT type 86
       b. hTagNew = HDuplicate(hTagOld, dx, dy)
       c. ok = DT_AssociateWithObj(hTagNew, h)
       d. if not ok: DelObject(hTagNew); return {'error': 'tag association
          failed'}    # never leave a tag pointing at the template
       e. DT_UpdateTaggedTags(h)
  7. If a position was named: UpdatePositionParam(hPosition) LAST, after every
     field write. Then RE-READ the fixture and return the values actually
     stored, not the values requested.
  8. return {'status':'ok', 'object_id':…, 'tag_object_id':…,
             'tag_associated':bool, 'fields':<read back>}
```

Step 7's read-back is not cosmetic: `UpdatePositionParam` and `LDevice_Reset`
can both change a field after it is written, so returning the requested values
would report a success the document does not contain.

For bulk insert, bracket the loop in `DT_BeginMultipleMove()` /
`DT_EndMultipleMove()` so tags reflow once rather than per fixture.

### 4.4 Pre-flight for whoever implements T3.4

- **T3.1 (undo/save guardrails) must land first** — it blocks all of Phase 3.
- Run `sl_dump_records` on a real show file and pin every TBV name in §2.
- Prove the tag round-trip on a scratch document: duplicate a tagged fixture,
  re-associate, **save, close, reopen**, and confirm the new tag reads the
  *new* fixture's channel and not the template's. The reopen is the test — an
  in-session tag can look correct and still be mis-associated on disk.
- Fuzz `DT_AssociateWithObj` returning false and confirm the rollback leaves no
  orphaned tag (T3.5).

---

## 5. Wiring

`vwx_pump._dispatch` resolves commands with `getattr(commands, cmd)`, so
`commands.py` needs one line for these verbs to be reachable:

```python
from sl_commands import *      # noqa: F401,F403
```

That edit belongs to `commands.py`'s owner; `sl_commands.py` touches neither
`commands.py` nor `cc_commands.py`, and imports neither (it re-declares `_oid`,
`_h`, `_safe`, `_collect` locally so `commands.py` can `import *` without a
cycle).

`sl_commands.SL_HANDLERS` maps name → function and `SL_READONLY` lists all five
verbs. **All five are read-only but none matches the pump's read-only name
prefixes** (`get_`, `list_`, `count_`, `find_`), so `vwx_pump` will
conservatively classify them as mutations and hold them for genuine dispatch.
That is safe, just slower — the MCP server should merge `SL_READONLY` into
`ipc/readonly.json` so they drain in the background.

---

## 6. Known gaps

- **Accessories.** `LDevice_GetAccCount(h, cell)` is reported; accessory fields
  (`accIndex >= 0`) are not read. Gobo/scroller accessories carry their own
  patch data, and ignoring them undercounts DMX footprint the same way ignoring
  cells did. This is the next read-side feature.
  `LDevice_AddAccessory` / `LDevice_DeleteAcc` **mutate** and are never called
  by any verb here — they belong to the T3.4 write path only.
- **Cell channel vs fixture channel.** A multi-cell fixture has both. The
  per-cell rows carry the cell's; `sl_list_fixtures` also reports the
  fixture-level value. Which one a lighting designer means by "channel 22"
  depends on the console, and the dump's live output should settle whether
  they even differ in practice.
- **`Universe` may be encoded in `Address`.** If the dump shows no separate
  `Universe` field, `sl_patch_report`'s `(universe, address)` key needs a
  parser for `u/a` notation before its duplicate detection is trustworthy.
- **Traversal depth.** `ForEachObject` does not descend into symbols, groups or
  viewport annotations without `INSYMBOL` / `INOBJECT` / `INVIEWPORT`
  modifiers. Fixtures nested in a group will be missed. Whether real plots nest
  them is TBV — `sl_dump_records`' census against a real file answers it.
