#!/usr/bin/env python3
"""ShowCAD domain contract suite — runs the cc_*/sl_* verbs through THIS
repo's dispatcher against tests/mock_vs.py. No Vectorworks required.

    python3 domain/tests/test_roundtrip.py        # plain, no pytest needed
    pytest domain/tests/test_roundtrip.py         # also collectable

What it proves
  A. plumbing   — the mock binds as `vs`, and the REAL vwx_pump._dispatch
                  drives commands.py against it.
  B. behavior   — the 7 legacy scaffold checks, ported.
  C. robustness — dict contract, the getters-absent capability fallback,
                  None/missing handles, and a record field that does not exist.

Verbs that do not exist yet (cc_commands.py / sl_commands.py are written by
other agents) report SKIP, never FAIL. Group A + the mock's own checks run
regardless, so this file is useful before a single verb is written.

HARD RULE honored throughout: no assertion here claims a Vectorworks record
FIELD NAME is correct. Every field name is TBV until a live document dump runs
(docs/TASKS.md T1.1-T1.3). Checks assert result SHAPE and error handling.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import harness                                             # noqa: E402
import mock_vs                                             # noqa: E402

VERBOSE = os.environ.get('SHOWCAD_TEST_VERBOSE') or '-v' in sys.argv

# ── result recording ───────────────────────────────────────────────────────

PASS, FAIL, SKIP = 'PASS', 'FAIL', 'SKIP'
RESULTS = []
NOTES = []


def record(status, name, detail=''):
    RESULTS.append((status, name, detail))
    print('%s %s%s' % (status, name, ('  — ' + detail) if detail else ''))
    return status == PASS


def check(name, cond, detail=''):
    return record(PASS if cond else FAIL, name, detail)


def skip(name, why):
    return record(SKIP, name, why)


def note(msg):
    NOTES.append(msg)


def show(title, data):
    if not VERBOSE:
        return
    print('\n--- %s ---' % title)
    try:
        print(json.dumps(data, indent=2, default=str)[:1600])
    except Exception:
        print(repr(data)[:1600])


def call(cmd, params=None):
    """dispatch_direct, converting a missing verb into a sentinel and letting
    a raise propagate (a raise is a real failure, not an error result)."""
    try:
        return harness.dispatch_direct(cmd, params)
    except KeyError:
        return MISSING


class _Missing(object):
    def __repr__(self):
        return '<verb not implemented>'


MISSING = _Missing()


def guard(cmd, params=None):
    """Call a verb, turning a raise into a FAIL-able marker instead of an
    exception that kills the run."""
    try:
        return call(cmd, params), None
    except harness.Raised as r:
        return None, r


# ── canonical verb roster (docs/ARCHITECTURE.md § Tool namespaces) ─────────

READ_VERBS = [
    ('doc_info', {}),
    ('cc_capabilities', {}),
    ('cc_dump_records', {}),
    ('cc_list_devices', {}),
    ('cc_get_device', {'device': 'E2 FRAME'}),
    ('cc_list_circuits', {}),
    ('cc_trace_signal', {'device': 'CAM 1'}),
    ('cc_audit_unconnected', {}),
    ('sl_list_fixtures', {}),
    ('sl_get_fixture', {'channel': '101'}),
    ('sl_patch_report', {}),
    ('sl_positions', {}),
]


# ═══════════════════════════════════════════════════════════════════════════
# GROUP A — plumbing (no dependency on the sibling agents' verbs)
# ═══════════════════════════════════════════════════════════════════════════

def group_a():
    print('\n===== A. plumbing =====')
    mock_vs.reset()

    check('A1 mock_vs is bound to sys.modules["vs"]',
          sys.modules.get('vs') is mock_vs)

    # commands.py does `import vs` at module scope — this is the assertion
    # that our sys.modules injection actually reached it.
    mods = harness.load_modules()
    cmds = mods.get('commands')
    check('A2 commands.py imported and sees the mock as vs',
          cmds is not None and getattr(cmds, 'vs', None) is mock_vs,
          'commands.py:20 does a hard `import vs`; there is no set_vs() hook '
          'in this repo')

    # The REAL production dispatcher, end to end.
    r = harness.dispatch_pump('get_document_info', {})
    show('vwx_pump._dispatch("get_document_info")', r)
    check('A3 real vwx_pump._dispatch drives commands.py against the mock',
          isinstance(r, dict) and r.get('name') == 'demo-show.vwx',
          str(r)[:120])

    r = harness.dispatch_pump('no_such_command_at_all', {})
    check('A4 unknown command -> {"error": ...}, no raise',
          isinstance(r, dict) and 'Unknown command' in str(r.get('error', '')))

    # A verb that blows up inside must still come back as a dict through the
    # pump — the pump's own try/except is what guarantees VW never sees a
    # traceback.
    r = harness.dispatch_pump('get_object_info', {'object_id': 'NOPE'})
    check('A5 pump converts an internal failure into a dict',
          isinstance(r, dict), str(r)[:120])

    # Capability switch itself.
    mock_vs.configure(cc_getters=True)
    present = getattr(mock_vs, 'CC_GetCircuitSource', None) is not None
    mock_vs.configure(cc_getters=False)
    absent = getattr(mock_vs, 'CC_GetCircuitSource', None) is None
    mock_vs.reset()
    check('A6 capability switch simulates BOTH worlds '
          '(CC_ getters present / absent)', present and absent,
          'vs_index.json indexes only 6 CC_* functions; the getters are not '
          'among them')

    # The mock's own error modes, so the Group C fallback checks mean something.
    mock_vs.configure(missing_field='raise')
    raised = False
    try:
        mock_vs.GetRField(mock_vs.DEVICES[0], 'Device', 'NoSuchFieldEver')
    except Exception:
        raised = True
    mock_vs.reset()
    check('A7 mock can make a missing record field RAISE', raised)

    mock_vs.configure(null_handle='raise')
    raised = False
    try:
        mock_vs.GetRField(None, 'Device', 'Name')
    except Exception:
        raised = True
    mock_vs.reset()
    check('A8 mock can make a nil handle RAISE', raised)


# ═══════════════════════════════════════════════════════════════════════════
# GROUP B — the 7 legacy scaffold checks, ported
# ═══════════════════════════════════════════════════════════════════════════

def _ported(name, cmd, params, assertion, detail=''):
    """Run one ported check; SKIP if the verb is not written yet.
    Returns the PASS/FAIL/SKIP status string."""
    res, raised = guard(cmd, params)
    if raised is not None:
        check(name, False, 'verb RAISED: %s' % raised)
        return FAIL
    if res is MISSING:
        skip(name, '%s not implemented yet' % cmd)
        return SKIP
    show('%s(%s)' % (cmd, params or ''), res)
    if harness.is_error(res):
        check(name, False, 'verb returned error: %s' % res.get('error'))
        return FAIL
    try:
        ok, extra = assertion(res)
    except Exception as e:
        check(name, False, 'assertion blew up on result shape: %r' % e)
        return FAIL
    check(name, ok, extra or detail)
    return PASS if ok else FAIL


def group_b():
    print('\n===== B. ported scaffold checks (7) =====')
    mock_vs.reset()

    def a_doc(r):
        layers = harness.rows(r) or r.get('layers') or []
        fname = harness.field(r, 'file', 'name', 'filename')
        return (fname == 'demo-show.vwx' and len(layers) == 3,
                'file=%r layers=%d' % (fname, len(layers)))

    if _ported('B1 doc_info returns demo file + 3 layers',
               'doc_info', {}, a_doc) == SKIP:
        note('B1: the doc_ namespace (docs/ARCHITECTURE.md) has no owner. '
             'commands.py has get_document_info (name/path/vw_version, no '
             'layer list) — it is NOT a drop-in for doc_info, so this check '
             'stays a SKIP rather than being pointed at the wrong verb.')

    def a_devs(r):
        n = len(harness.rows(r))
        return n == 6, '%d devices' % n

    _ported('B2 cc_list_devices -> 6 devices', 'cc_list_devices', {}, a_devs)

    def a_cirs(r):
        n = len(harness.rows(r))
        return n == 4, '%d circuits touch E2 FRAME' % n

    _ported('B3 cc_list_circuits(device="E2 FRAME") -> 4',
            'cc_list_circuits', {'device': 'E2 FRAME'}, a_cirs)

    def a_trace(r):
        # Content check by flattening: the result SCHEMA is the sibling
        # agent's choice, the reachability fact is not.
        flat = harness.flatten(r)
        hops = r.get('hops') if isinstance(r, dict) else None
        nh = len(hops) if isinstance(hops, list) else len(harness.rows(r))
        return ('XD 1' in flat and nh == 3,
                'reached XD 1=%s, hops=%d' % ('XD 1' in flat, nh))

    _ported('B4 cc_trace_signal(CAM 1) reaches XD 1 in 3 hops',
            'cc_trace_signal', {'device': 'CAM 1'}, a_trace)

    def a_audit(r):
        for row in harness.rows(r):
            f = harness.flatten(row)
            if 'SRV 1' in f and 'DP OUT 2' in f:
                return True, 'SRV 1 / DP OUT 2 flagged'
        return False, 'SRV 1 / DP OUT 2 not among %d issues' % len(harness.rows(r))

    _ported('B5 cc_audit_unconnected flags SRV 1 / DP OUT 2',
            'cc_audit_unconnected', {}, a_audit)

    def a_fx(r):
        n = len(harness.rows(r))
        return n == 6, '%d fixtures in universe 2' % n

    _ported('B6 sl_list_fixtures(universe=2) -> 6',
            'sl_list_fixtures', {'universe': '2'}, a_fx)

    def a_patch(r):
        # Wording-tolerant: the reference wrote the flag as the prose string
        # "duplicate channel with <unit>", sl_commands.py emits a structured
        # {'kind': 'duplicate_channel', ...}. Both are correct; the FACT under
        # test is that the deliberate duplicate on channel 101 is detected.
        rows = harness.rows(r)

        def flags_dup_channel(x):
            blob = ' '.join(harness.flatten(x)).lower().replace('_', ' ')
            return 'duplicate channel' in blob

        flagged = [x for x in rows if flags_dup_channel(x)]
        # a summary counter is an equally valid way to report it
        counted = r.get('conflict_count') if isinstance(r, dict) else None
        ok = bool(flagged) or bool(counted)
        return ok, '%d/%d rows flagged, conflict_count=%r' % (
            len(flagged), len(rows), counted)

    _ported('B7 sl_patch_report flags duplicate channel 101',
            'sl_patch_report', {}, a_patch)


# ═══════════════════════════════════════════════════════════════════════════
# GROUP C — new coverage
# ═══════════════════════════════════════════════════════════════════════════

def group_c_dict_contract():
    print('\n===== C1. dispatcher contract: dict in, dict out, never raise ====')
    mock_vs.reset()
    any_verb = False
    for cmd, params in READ_VERBS:
        res, raised = guard(cmd, params)
        if raised is not None:
            check('C1 %-22s returns a dict' % cmd, False,
                  'RAISED %s' % raised)
            any_verb = True
            continue
        if res is MISSING:
            skip('C1 %-22s returns a dict' % cmd, 'not implemented yet')
            continue
        any_verb = True
        check('C1 %-22s returns a dict' % cmd, isinstance(res, dict),
              'got %s' % type(res).__name__)
    if not any_verb:
        note('C1: no cc_/sl_ verb exists yet — the dict contract is unverified.')


def group_c_pump_reachability():
    print('\n===== C2. reachability through the REAL pump dispatcher =====')
    unreachable = []
    for cmd, _ in READ_VERBS:
        modname, fn = harness.resolve(cmd)
        if fn is None:
            skip('C2 %-22s reachable via getattr(commands, cmd)' % cmd,
                 'not implemented yet')
            continue
        ok = harness.pump_reachable(cmd)
        check('C2 %-22s reachable via getattr(commands, cmd)' % cmd, ok,
              'defined in %s.py%s' % (modname,
                                      '' if ok else ' — NOT re-exported from '
                                      'commands.py, so vwx_pump._dispatch '
                                      'will answer "Unknown command"'))
        if not ok:
            unreachable.append((cmd, modname))
    # Hard evidence, not just a getattr probe: run one unreachable verb
    # through the REAL production dispatcher and show what a user would get.
    if unreachable:
        cmd = unreachable[0][0]
        produced = harness.dispatch_pump(cmd, {})
        note('C2 evidence: vwx_pump._dispatch(%r) returns %r' % (cmd, produced))

    if unreachable:
        note('C2: %d verb(s) are defined but UNREACHABLE in production — '
             'vwx_pump.py:170 does getattr(commands, cmd) only. Either define '
             'them in commands.py or add `from cc_commands import *` there: %s'
             % (len(unreachable), ', '.join('%s (%s)' % u for u in unreachable)))
        note('C2: this is the re-export step already specified in '
             'domain/INTEGRATION-NOTES.md §1a — it has not landed yet. The mac '
             'transport (vwx_mcp_bridge.py) resolves verbs the same way, so '
             'this blocks BOTH platforms.')


def group_c_capability_fallback():
    print('\n===== C3. capability fallback: CC_ getters ABSENT =====')
    mock_vs.reset()
    cc_verbs = [(c, p) for c, p in READ_VERBS if c.startswith('cc_')]
    ran = 0
    with mock_vs.capability(cc_getters=False):
        for cmd, params in cc_verbs:
            res, raised = guard(cmd, params)
            if raised is not None:
                check('C3 %-22s survives getters-absent' % cmd, False,
                      'RAISED %s' % raised)
                ran += 1
                continue
            if res is MISSING:
                skip('C3 %-22s survives getters-absent' % cmd,
                     'not implemented yet')
                continue
            ran += 1
            show('%s with cc_getters=False' % cmd, res)
            ok = isinstance(res, dict)
            detail = 'error-dict' if harness.is_error(res) else \
                     '%d row(s) via record-field/container fallback' % len(
                         harness.rows(res))
            check('C3 %-22s survives getters-absent' % cmd, ok, detail)
        modeled, unmodeled = mock_vs.classify_misses()
    if modeled:
        note('C3: getters-absent world exercised — verbs probed and fell back '
             'from: %s (this is the fallback working, not a gap)'
             % ', '.join(modeled))
    check('C3 no result was shaped by a MOCK GAP', not unmodeled,
          ('unmodeled vs functions reached: %s — add them to mock_vs.py '
           'before trusting the results above' % ', '.join(unmodeled))
          if unmodeled else 'every vs function reached is modeled')
    if not ran:
        note('C3: no cc_ verb exists yet — the fallback path is unverified.')

    # Census parity: the criteria path (ForEachObject "PON='Device'") and the
    # document-walk fallback (FLayer/FInLayer/NextObj + GetParametricRecord)
    # must agree on how many objects exist. If they disagree, one of the two
    # discovery strategies is wrong and a live document will expose it.
    mock_vs.reset()
    res, raised = guard('cc_dump_records', {})
    if raised is not None:
        check('C3 census: criteria path and document walk agree', False,
              'cc_dump_records RAISED: %s' % raised)
    elif res is MISSING:
        skip('C3 census: criteria path and document walk agree',
             'cc_dump_records not implemented yet')
    else:
        show('cc_dump_records', res)
        flat = harness.flatten(res)
        seen_pons = [p for p in ('Device', 'Circuit', 'Socket',
                                 'Lighting Device') if p in flat]
        check('C3 census: document walk discriminates PIO types via '
              'GetParametricRecord', len(seen_pons) >= 3,
              'found %s' % (seen_pons or 'nothing'))

    # The same sweep with the getters PRESENT, to prove the switch is what
    # changed the code path and not something incidental.
    mock_vs.reset()
    with mock_vs.capability(cc_getters=True):
        for cmd, params in cc_verbs:
            res, raised = guard(cmd, params)
            if raised is not None:
                check('C3 %-22s survives getters-present' % cmd, False,
                      'RAISED %s' % raised)
            elif res is MISSING:
                skip('C3 %-22s survives getters-present' % cmd,
                     'not implemented yet')
            else:
                check('C3 %-22s survives getters-present' % cmd,
                      isinstance(res, dict))


def group_c_bad_handles():
    print('\n===== C4. missing / None handles =====')
    bad_params = [
        ('None device', {'device': None}),
        ('empty params', {}),
        ('None object_id', {'object_id': None}),
        ('bogus uuid', {'object_id': 'NO-SUCH-UUID-0000'}),
        ('None handle', {'handle': None}),
        ('nonexistent name', {'device': 'DEVICE THAT DOES NOT EXIST',
                              'channel': 'ZZZ', 'position': 'NOWHERE'}),
    ]
    ran = 0
    for nullmode in ('none', 'raise'):
        mock_vs.reset()
        mock_vs.configure(null_handle=nullmode)
        for cmd, _ in READ_VERBS:
            for label, params in bad_params:
                res, raised = guard(cmd, params)
                if raised is not None:
                    check('C4 %-22s %-18s null_handle=%s' % (cmd, label, nullmode),
                          False, 'RAISED %s' % raised)
                    ran += 1
                    continue
                if res is MISSING:
                    continue
                ran += 1
                ok = isinstance(res, dict)
                if not ok:
                    check('C4 %-22s %-18s null_handle=%s' % (cmd, label, nullmode),
                          False, 'returned %s, not a dict' % type(res).__name__)
    mock_vs.reset()
    if ran:
        check('C4 no verb raised on a missing/None handle (%d calls)' % ran,
              not any(s == FAIL and n.startswith('C4') for s, n, _ in RESULTS))
    else:
        skip('C4 missing/None handle sweep', 'no verb implemented yet')
        note('C4: bad-handle handling is unverified until cc_/sl_ verbs land.')


def group_c_missing_field():
    print('\n===== C5. record field that does not exist =====')
    ran = 0
    for mode in ('empty', 'raise'):
        mock_vs.reset()
        # 'raise' is the harsh case: real VW may instead return '' — we test
        # both because which one is real is TBV.
        mock_vs.configure(missing_field=mode, strict_record=(mode == 'raise'))
        for cmd, params in READ_VERBS:
            res, raised = guard(cmd, params)
            if raised is not None:
                check('C5 %-22s missing_field=%-5s' % (cmd, mode), False,
                      'RAISED %s' % raised)
                ran += 1
                continue
            if res is MISSING:
                continue
            ran += 1
            ok = isinstance(res, dict)
            detail = 'error-dict' if harness.is_error(res) else 'dict result'
            check('C5 %-22s missing_field=%-5s' % (cmd, mode), ok, detail)
    mock_vs.reset()
    if not ran:
        skip('C5 missing record field sweep', 'no verb implemented yet')
        note('C5: nonexistent-field handling is unverified until verbs land.')




def group_c_row_integrity():
    """Rows must carry data, not be structurally-empty placeholders.

    Catches the class of bug where a helper grows a second return value and a
    caller keeps doing `hs = helper(...)`: the 2-tuple is truthy, so the guard
    passes, and the verb then iterates the TUPLE and emits one all-None row per
    tuple member. Every individual contract check (dict? rows? no raise?) still
    passes — only the emptiness of the rows gives it away.
    """
    print('\n===== C6. row integrity (rows carry data) =====')
    mock_vs.reset()
    ran = 0
    for cmd, params in READ_VERBS:
        res, raised = guard(cmd, params)
        if raised is not None or res is MISSING:
            continue
        rs = [r for r in harness.rows(res) if isinstance(r, dict)]
        if not rs:
            continue
        ran += 1
        hollow = [r for r in rs
                  if r and all(v in (None, '', [], {}) for v in r.values())]
        check('C6 %-22s rows are not all-None placeholders' % cmd,
              not hollow,
              '%d/%d rows have every value empty — the verb is very likely '
              'iterating a (handles, meta) TUPLE instead of the handle list'
              % (len(hollow), len(rs)) if hollow else '%d row(s) carry data'
              % len(rs))

        # A count that does not match the rows returned is the same bug seen
        # from the other side.
        if isinstance(res, dict) and isinstance(res.get('count'), int):
            check('C6 %-22s count matches len(rows)' % cmd,
                  res['count'] == len(harness.rows(res)),
                  'count=%s rows=%d' % (res['count'], len(harness.rows(res))))

    # Cross-verb consistency: the mock has 10 fixtures and 6 devices. Any verb
    # that reports a fixture/device population must agree with its peers.
    counts = {}
    for cmd in ('sl_list_fixtures', 'sl_patch_report'):
        res, raised = guard(cmd, {})
        if raised is None and res is not MISSING and not harness.is_error(res):
            counts[cmd] = len(harness.rows(res))
    if len(counts) > 1:
        check('C6 fixture population agrees across sl_ verbs',
              len(set(counts.values())) == 1, repr(counts))

    if not ran:
        skip('C6 row integrity', 'no verb returned rows')

    # Negative case: a fixture whose Position FIELD disagrees with the truss it
    # is physically hung from. A verb that reports positions must not silently
    # agree with itself — if it cross-checks, the disagreement has to surface.
    mock_vs.reset()
    baseline, raised = guard('sl_positions', {})
    if raised is None and baseline is not MISSING and \
            not harness.is_error(baseline):
        with mock_vs.capability(hangpos_mismatch=True):
            skewed, raised2 = guard('sl_positions', {})
        if raised2 is not None:
            check('C6 sl_positions surfaces a by-field/by-parent mismatch',
                  False, 'RAISED %s' % raised2)
        else:
            def _disagrees(res):
                for row in harness.rows(res):
                    if not isinstance(row, dict):
                        continue
                    if row.get('mismatch'):
                        return True
                    bf = row.get('fixture_count_by_field')
                    bp = row.get('fixture_count_by_parent')
                    if bf is not None and bp is not None and bf != bp:
                        return True
                return False
            check('C6 sl_positions surfaces a by-field/by-parent mismatch',
                  _disagrees(skewed) and not _disagrees(baseline),
                  'clean doc disagrees=%s, skewed doc disagrees=%s'
                  % (_disagrees(baseline), _disagrees(skewed)))
    mock_vs.reset()


# ═══════════════════════════════════════════════════════════════════════════

def run():
    print('repo:    %s' % harness.REPO_ROOT)
    print('plugin:  %s' % harness.PLUGIN_DIR)
    print('modules:')
    for line in harness.module_status():
        print('  ' + line)

    group_a()
    group_b()
    group_c_dict_contract()
    group_c_pump_reachability()
    group_c_capability_fallback()
    group_c_bad_handles()
    group_c_missing_field()
    group_c_row_integrity()

    # Late re-check: the sibling agents may have landed their modules while
    # this run was in flight.
    before = set(harness.load_modules())
    after = set(harness.load_modules(force=True))
    if after - before:
        note('cc_/sl_ module(s) appeared mid-run: %s — RE-RUN the suite.'
             % ', '.join(sorted(after - before)))
    still_missing = [m for m in ('cc_commands', 'sl_commands') if m not in after]
    if still_missing:
        note('%s still absent at end of run — every cc_/sl_ verb check above '
             'is a SKIP, not a pass.' % ', '.join(still_missing))

    _, unmodeled = mock_vs.classify_misses()
    if unmodeled:
        note('MOCK GAP: these real vs functions were reached but are not '
             'implemented in mock_vs.py, so any check touching them proved '
             'nothing: %s' % ', '.join(unmodeled))

    npass = sum(1 for s, _, _ in RESULTS if s == PASS)
    nfail = sum(1 for s, _, _ in RESULTS if s == FAIL)
    nskip = sum(1 for s, _, _ in RESULTS if s == SKIP)
    print('\n' + '=' * 70)
    if NOTES:
        print('NOTES')
        for n in NOTES:
            print('  * ' + n)
        print('-' * 70)
    print('%d passed, %d failed, %d skipped' % (npass, nfail, nskip))
    if nfail:
        print('FAILED: ' + ', '.join(n for s, n, _ in RESULTS if s == FAIL))
    else:
        print('ALL %d CHECKS PASSED (%d skipped — verbs not written yet)'
              % (npass, nskip))
    print('=' * 70)
    return nfail


# ── pytest entry points ────────────────────────────────────────────────────
# One test per group so pytest reports which area broke. Each asserts that no
# check in its group FAILED; SKIPs are fine.

def _no_fails(prefix):
    bad = [n for s, n, d in RESULTS if s == FAIL and n.startswith(prefix)]
    assert not bad, 'failed: ' + '; '.join(bad)


def _once():
    if not RESULTS:
        run()


def test_a_plumbing():
    """Mock binds as `vs`; the real vwx_pump._dispatch drives commands.py."""
    _once()
    _no_fails('A')


def test_b_ported_scaffold_checks():
    """The 7 checks carried over from the standalone scaffold harness."""
    _once()
    _no_fails('B')


def test_c1_dict_contract():
    """Every verb returns a dict through getattr(module, cmd)(params)."""
    _once()
    _no_fails('C1')


def test_c2_reachable_through_production_pump():
    """vwx_pump.py:170 does getattr(commands, cmd) — a verb that lives only in
    cc_commands.py / sl_commands.py answers 'Unknown command' in production."""
    _once()
    _no_fails('C2')


def test_c3_capability_fallback():
    """Verbs survive the CC_* getters being absent (record-field / walk path)."""
    _once()
    _no_fails('C3')


def test_c4_missing_handles():
    """No verb raises on a missing/None handle."""
    _once()
    _no_fails('C4')


def test_c5_missing_record_field():
    """A record field that does not exist yields a dict, never a raise."""
    _once()
    _no_fails('C5')


def test_c6_row_integrity():
    """Rows carry data; counts match; peer verbs agree on the population."""
    _once()
    _no_fails('C6')


if __name__ == '__main__':
    sys.exit(1 if run() else 0)
