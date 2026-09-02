# domain/tests — ShowCAD domain contract suite

Exercises the `cc_*` / `sl_*` verbs through **this repo's dispatcher** against a
mock Vectorworks. No VW, no bridge, no socket, no document required.

## Run it

```bash
# from the repo root — plain, no pytest needed
~/showcad-mcp/.venv/bin/python domain/tests/test_roundtrip.py

# verbose (prints every verb's JSON result)
~/showcad-mcp/.venv/bin/python domain/tests/test_roundtrip.py -v

# same checks under pytest, one test per group
~/showcad-mcp/.venv/bin/python -m pytest domain/tests/test_roundtrip.py -q
```

Exit code is `0` only when nothing FAILed. SKIPs (a verb not written yet) do not
fail the run — but they are counted and named, and a SKIP is **not** a pass.

## Files

| File | What it is |
|---|---|
| `mock_vs.py` | Stand-in for the `vs` module: fixture document + the vs.\* API surface, with capability switches |
| `harness.py` | Binds the mock as `vs`, loads the plugin modules, resolves and dispatches verbs |
| `test_roundtrip.py` | The checks (groups A/B/C) and both entry points |

## What the groups cover

- **A — plumbing.** The mock is bound to `sys.modules['vs']`; `commands.py` sees
  it; the *real* `vwx_pump._dispatch` runs against it; an unknown command and an
  internal failure both come back as `{'error': ...}` instead of raising.
- **B — behavior.** The 7 checks ported from the original standalone scaffold
  harness (device count, circuit filter, signal trace, unconnected-socket audit,
  universe filter, duplicate-channel detection, doc info).
- **C — contract and robustness.**
  - `C1` every verb returns a **dict**
  - `C2` every verb is **reachable through the production dispatcher**
  - `C3` verbs survive the **CC_\* getters being absent** (see below), and the
    document-walk census discriminates PIO types
  - `C4` verbs never raise on a **missing/None handle**
  - `C5` verbs never raise on a **record field that does not exist**
  - `C6` **row integrity** — rows carry data (not all-`None` placeholders),
    `count` matches `len(rows)`, peer verbs agree on the population, and
    `sl_positions` surfaces a deliberate by-field/by-parent mismatch

## The capability switch (the point of `mock_vs.py`)

`vwx-plugin/vs_index.json` indexes only **six** ConnectCAD functions:
`CC_CircuitFromShape`, `CC_DeviceFromShape`, `CC_RouteFromShape`,
`CC_RoomFromShape`, `CC_OnFindAndReplace`, `CC_ReloadData`.

`CC_GetCircuitSource`, `CC_GetCircuitDest`, `CC_GetDevice` and
`CC_DeviceSockets` are **not** among them. We do not yet know whether they exist
on a live VW2026 install, so the mock simulates both worlds:

```python
mock_vs.configure(cc_getters=True)    # getters present  -> direct-API path
mock_vs.configure(cc_getters=False)   # getters absent   -> AttributeError,
                                      #   forcing the record-field / walk fallback

with mock_vs.capability(cc_getters=False):   # scoped form
    ...
```

Other switches:

| Switch | Values | Simulates |
|---|---|---|
| `cc_getters` | `True` / `False` | the CC_\* getters existing or not |
| `missing_field` | `'none'` / `'empty'` / `'raise'` | how `GetRField` answers for a field that is not on the record |
| `null_handle` | `'none'` / `'raise'` | how the API answers a nil handle |
| `strict_record` | `False` / `True` | enforcing that `GetRField`'s `record` argument matches the object |
| `hangpos_mismatch` | `False` / `True` | a fixture hung from a truss other than the one its `Position` field names |

`mock_vs.reset()` restores defaults and clears diagnostics.

`mock_vs.classify_misses()` splits every `vs.<name>` the plugin reached but the
mock does not provide into **modeled absent** (the capability layer probing, as
designed) and **unmodeled** (a real vs function missing from the mock — any
check touching it proved nothing). Check `C3 no result was shaped by a MOCK GAP`
enforces that the unmodeled list is empty.

## Rules this suite follows

1. **The mock is the only source of truth.** Nothing here asserts that a
   Vectorworks **record field name** is correct — every ConnectCAD/Spotlight
   field name is TBV until the live document dump runs (`docs/TASKS.md` T1.1–T1.3).
   Checks assert result **shape** and **error handling**.
2. **Result-schema tolerant.** Content checks flatten the result and look for the
   fact (`'XD 1'` is reachable, channel `101` is flagged) rather than pinning the
   sibling agents' key names or wording.
3. **Missing verb = SKIP, never FAIL.** `cc_commands.py` / `sl_commands.py` are
   written by other agents; the suite is useful before either exists.

## Adding a vs function to the mock

If a verb reaches for a `vs.*` the mock lacks, the run reports it under
`MOCK GAP`. Add it to `mock_vs.py` as a plain module-level function — but only
if it is in `vwx-plugin/vs_index.json`. If it is **not** indexed, it belongs in
`KNOWN_ABSENT` or in the `_SWITCHED` capability group instead: modeling a
function that may not exist as if it always does is how the old harness ended up
passing against `vs.CC_DeviceSockets`, which is not a documented VW API at all.

## Fixture document

Mirrors `docs/TASKS.md` T1.4 and is byte-identical to the original scaffold's
data, so the ported checks mean the same thing:

- 6 devices on `VIDEO SCHEM` (CAM 1, CAM 2, E2 FRAME, SX40 A, XD 1, SRV 1)
- 5 circuits, chain `CAM 1 → E2 FRAME → SX40 A → XD 1`
- `SRV 1 / DP OUT 2` deliberately **unconnected**
- 10 fixtures on `LX PLOT`, 4 in universe 1 and 6 in universe 2
- channel `101` deliberately **duplicated** (units 1 and 10)
- 2 Hanging Position PIOs (`FOH TRUSS`, `US TRUSS`) reachable from a fixture via
  `vs.OLDGetHangingPos`, so by-field and by-parent position counts can be
  cross-checked (they agree by default; `hangpos_mismatch` breaks one on purpose)

Beyond `GetRField`, the mock models the walk APIs (`FLayer`/`FInLayer`/`FObject`/
`FInGroup`/`NextObj`), the PIO discriminator (`GetParametricRecord` + `GetName`),
criteria by type (`T=PLUGINOBJ`, `T=PLUGINOBJECT`, `T=RECDEF`) as well as
`PON='...'`, and the Spotlight `LDevice_*` universal-name parameter family —
because the plugin modules use all of those, and a mock that only understood
`PON=` made every `sl_*` verb look broken when it was not.
