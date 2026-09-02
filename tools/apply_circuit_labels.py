#!/usr/bin/env python3
"""Put the FAR end's socket name at each end of every ConnectCAD circuit.

WHAT THIS DOES AND WHY IT WORKS
-------------------------------
Established live against DOJA26_SRVR_V1.vwx (see domain/docs/LABEL-EXPERIMENTS.md):
the text drawn at each end of a Circuit plug-in object is painted at the two
`CC-Circuit-Connector` loci inside the PIO. The first locus renders
`Circuit.Src_Skt_Conn`; the second renders `Circuit.Dst_Skt_Conn`. Proven by
measuring the loci bounding boxes against real 12 pt text of the same strings:
the ratio was 72.56 +/- 0.02 across six different connector names, and the two
widths swap when the two connectors differ.

So writing the FAR end's socket name into those two fields makes each end name
the far end:

    Src_Skt_Conn := Dst_Skt_Name     # drawn at the SOURCE end
    Dst_Skt_Conn := Src_Skt_Name     # drawn at the DESTINATION end

For `<EXT>.OG DA - 01 -> DIR.SDI_IN 01` that puts "SDI_IN 01" at the OG DA end
and "OG DA - 01" at the DIR end, which is exactly the requested behaviour.

READ THIS BEFORE YOU RUN IT
---------------------------
1. `Src_Skt_Conn` / `Dst_Skt_Conn` are DENORMALISED COPIES of socket data.
   ConnectCAD refills them from the sockets whenever it reconnects or fully
   rebuilds a circuit. This override may not survive a Reconnect / Update
   Circuits operation. Re-run this script if that happens.
2. They are the CONNECTOR TYPE fields. Any cable schedule, worksheet or report
   that reads Src_Skt_Conn / Dst_Skt_Conn will show socket names instead of
   "BNC"/"HDMI" after this runs. Check your reports before committing.
3. Nothing renders until the Circuit PIO regenerates, which does NOT happen from
   the bridge. Field writes persist; the drawing updates when Vectorworks next
   rebuilds the object (nudge it with the Reshape tool, or run a ConnectCAD
   command that touches circuits).

Every mutating batch is wrapped in vs.NameUndoEvent. Nothing is ever saved --
the user saves.

USAGE
-----
    python3 tools/apply_circuit_labels.py                  # dry run (default)
    python3 tools/apply_circuit_labels.py --apply
    python3 tools/apply_circuit_labels.py --restore
    python3 tools/apply_circuit_labels.py --hide-connector-class
    python3 tools/apply_circuit_labels.py --show-connector-class

Options:
    --batch N     circuits per bridge call (default 20; keep it small, a long
                  SetRField+ResetObject loop has reset the bridge before)
    --limit N     only touch the first N circuits (good for a 1-circuit trial)
    --baseline P  path to the baseline JSON (default alongside this script)
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vwx_cli import call  # noqa: E402

BASELINE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        'circuit_labels_baseline.json')

# Fields this script touches. Recorded before every write so --restore is exact.
FIELDS = ('Src_Skt_Conn', 'Dst_Skt_Conn')


def run(code, timeout=180.0):
    r = call('execute_script', {'code': code}, timeout=timeout)
    if isinstance(r, dict) and r.get('error'):
        raise SystemExit('bridge error:\n' + r['error'])
    return r.get('result') if isinstance(r, dict) else r


ENUMERATE = r'''
import vs, json
circs = []
vs.ForEachObject(lambda h: circs.append(h), "(R IN ['Circuit'])")
rows = []
for i, h in enumerate(circs):
    g = lambda f: vs.GetRField(h, 'Circuit', f)
    rows.append({
        'i': i,
        'src_dev': g('Src_Dev_Name'), 'src_skt': g('Src_Skt_Name'),
        'dst_dev': g('Dst_Dev_Name'), 'dst_skt': g('Dst_Skt_Name'),
        'Src_Skt_Conn': g('Src_Skt_Conn'), 'Dst_Skt_Conn': g('Dst_Skt_Conn'),
    })
__result__ = json.dumps(rows)
'''


def enumerate_circuits():
    return json.loads(run(ENUMERATE))


def _batch_script(pairs, undo_label):
    """pairs: list of (ordinal, src_skt_conn_value, dst_skt_conn_value)."""
    return (
        'import vs\n'
        'circs = []\n'
        "vs.ForEachObject(lambda h: circs.append(h), \"(R IN ['Circuit'])\")\n"
        'plan = %r\n'
        'vs.NameUndoEvent(%r)\n'
        'done = 0\n'
        'for idx, sv, dv in plan:\n'
        '    h = circs[idx]\n'
        "    vs.SetRField(h, 'Circuit', 'Src_Skt_Conn', sv)\n"
        "    vs.SetRField(h, 'Circuit', 'Dst_Skt_Conn', dv)\n"
        '    done += 1\n'
        '__result__ = done\n'
    ) % (pairs, undo_label)


def plan_apply(rows, limit=None):
    """Each end takes the FAR end's socket name."""
    plan = []
    for r in rows:
        if limit is not None and len(plan) >= limit:
            break
        new_src, new_dst = r['dst_skt'], r['src_skt']
        if (r['Src_Skt_Conn'], r['Dst_Skt_Conn']) == (new_src, new_dst):
            continue                       # already applied, skip
        plan.append((r['i'], new_src, new_dst))
    return plan


def plan_restore(rows, baseline, limit=None):
    by_i = {b['i']: b for b in baseline}
    plan = []
    for r in rows:
        if limit is not None and len(plan) >= limit:
            break
        b = by_i.get(r['i'])
        if b is None:
            continue
        sig = (b['src_dev'], b['src_skt'], b['dst_dev'], b['dst_skt'])
        if sig != (r['src_dev'], r['src_skt'], r['dst_dev'], r['dst_skt']):
            raise SystemExit(
                'circuit ordering changed since the baseline was taken '
                '(index %d is now %s, baseline says %s). Refusing to restore.'
                % (r['i'], (r['src_dev'], r['src_skt']), (b['src_dev'], b['src_skt'])))
        if (r['Src_Skt_Conn'], r['Dst_Skt_Conn']) == (b['Src_Skt_Conn'], b['Dst_Skt_Conn']):
            continue
        plan.append((r['i'], b['Src_Skt_Conn'], b['Dst_Skt_Conn']))
    return plan


def execute(plan, rows, batch, label):
    by_i = {r['i']: r for r in rows}
    total = 0
    for k in range(0, len(plan), batch):
        chunk = plan[k:k + batch]
        n = run(_batch_script(chunk, '%s (%d-%d)' % (label, k + 1, k + len(chunk))))
        total += int(n or 0)
        first, last = by_i[chunk[0][0]], by_i[chunk[-1][0]]
        print('  batch %3d-%-3d ok (%s.%s ... %s.%s)'
              % (k + 1, k + len(chunk), first['src_dev'], first['src_skt'],
                 last['dst_dev'], last['dst_skt']))
    return total


def show_plan(plan, rows):
    by_i = {r['i']: r for r in rows}
    for idx, sv, dv in plan[:12]:
        r = by_i[idx]
        print('  [%3d] %s.%s -> %s.%s' % (idx, r['src_dev'], r['src_skt'],
                                          r['dst_dev'], r['dst_skt']))
        print('        source end: %-14r -> %r' % (r['Src_Skt_Conn'], sv))
        print('        dest   end: %-14r -> %r' % (r['Dst_Skt_Conn'], dv))
    if len(plan) > 12:
        print('  ... and %d more' % (len(plan) - 12))


def class_vis(hide):
    verb = 'HideClass' if hide else 'ShowClass'
    code = ("import vs\n"
            "prior = vs.GetCVis('CC-Circuit-Connector')\n"
            "vs.NameUndoEvent('ShowCAD: %s CC-Circuit-Connector')\n"
            "vs.%s('CC-Circuit-Connector')\n"
            "__result__ = 'prior=%%r now=%%r' %% (prior, vs.GetCVis('CC-Circuit-Connector'))\n"
            % (verb, verb))
    print(run(code))
    print('NOTE: this is the DESIGN LAYER only. Sheet TA1.1 viewport "Schematic"')
    print('      has its own class visibility; set it there too for output.')


CLEANUP = r'''
import vs
out = []
circs = []
vs.ForEachObject(lambda h: circs.append(h), "(R IN ['Circuit'])")
vs.NameUndoEvent('ShowCAD: revert probe priming and junk arrow formulas')
for h in circs:
    g = lambda f: vs.GetRField(h, 'Circuit', f)
    if g('Src_Skt_Name') == 'OG DA - 01' and g('Dst_Dev_Name') == 'DIR':
        was = (g('Src_Skt_Conn'), g('Dst_Skt_Conn'))
        if was != ('BNC', 'BNC'):
            vs.SetRField(h, 'Circuit', 'Src_Skt_Conn', 'BNC')
            vs.SetRField(h, 'Circuit', 'Dst_Skt_Conn', 'BNC')
            out.append('reverted OG DA - 01 -> DIR.SDI_IN 01 connector fields %r -> (BNC, BNC)' % (was,))
    if g('__CustomizeArrow') == 'True':
        old = g('__ArrowFormula')
        vs.SetRField(h, 'Circuit', '__CustomizeArrow', 'False')
        vs.SetRField(h, 'Circuit', '__ArrowFormula', '')
        out.append('cleared junk arrow formula %r on %s.%s -> %s.%s'
                   % (old, g('Src_Dev_Name'), g('Src_Skt_Name'),
                      g('Dst_Dev_Name'), g('Dst_Skt_Name')))
se = sum(1 for h in circs if vs.GetRField(h, 'Circuit', 'ShowEnd') == 'True')
out.append("NOT reverted (ask the user first): ShowEnd='True' on %d circuits, original was 'False'" % se)
out.append("CC-Circuit-Connector visibility = %r  (0 visible, -1 hidden)" % vs.GetCVis('CC-Circuit-Connector'))
__result__ = '\n'.join(out) if out else 'nothing to clean up'
'''

# Prime ONE circuit for the per-end arrow test. Every circuit in this document
# is __SameLayer='True', so the Circuit Type change is reversible (the help's
# irreversibility warning applies only to circuits spanning two layers).
ARROW_TEST = r'''
import vs
circs = []
vs.ForEachObject(lambda h: circs.append(h), "(R IN ['Circuit'])")
tgt = None
for h in circs:
    if (vs.GetRField(h, 'Circuit', 'Src_Skt_Name') == 'HDMI_OUT 05'
            and vs.GetRField(h, 'Circuit', 'Dst_Dev_Name') == 'SPARE'):
        tgt = h
        break
if tgt is None:
    __result__ = 'target circuit not found'
else:
    g = lambda f: vs.GetRField(tgt, 'Circuit', f)
    prior = {f: g(f) for f in ('CircuitType', '__CustomizeArrow',
                               '__ArrowFormula', '__ArrowStyle', '__SameLayer')}
    vs.NameUndoEvent('ShowCAD: arrow per-end test on ONE circuit (HDMI_OUT 05 -> SPARE)')
    vs.SetRField(tgt, 'Circuit', 'CircuitType', 'arrow')
    vs.SetRField(tgt, 'Circuit', '__CustomizeArrow', 'True')
    vs.SetRField(tgt, 'Circuit', '__ArrowFormula', '#Circuit.Device Tag#.#Circuit.Socket Name#')
    vs.SetRField(tgt, 'Circuit', '__ArrowStyle', '1')
    vs.ResetObject(tgt)
    now = {f: g(f) for f in prior}
    kids = []
    c = vs.FInGroup(tgt)
    while c:
        t = vs.GetTypeN(c)
        (x1, y1), (x2, y2) = vs.GetBBox(c)
        kids.append('%s[%s] w=%.4f' % (t, vs.GetClass(c), abs(x2 - x1)))
        c = vs.NextObj(c)
    __result__ = ('PRIOR: %r\nNOW  : %r\nchildren: %s\n'
                  '(children unchanged => still not regenerating; finish the test in the GUI)'
                  % (prior, now, ' | '.join(kids)))
'''


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    g.add_argument('--apply', action='store_true', help='write the far-end labels')
    g.add_argument('--restore', action='store_true', help='put the baseline values back')
    g.add_argument('--hide-connector-class', action='store_true')
    g.add_argument('--show-connector-class', action='store_true')
    g.add_argument('--cleanup', action='store_true',
                   help='revert the leftover probe state (see LABEL-EXPERIMENTS.md §8)')
    g.add_argument('--arrow-test', action='store_true',
                   help='prime ONE low-stakes circuit for the per-end arrow test')
    ap.add_argument('--batch', type=int, default=20)
    ap.add_argument('--limit', type=int, default=None)
    ap.add_argument('--baseline', default=BASELINE)
    a = ap.parse_args()

    if a.hide_connector_class or a.show_connector_class:
        class_vis(a.hide_connector_class)
        return

    if a.cleanup:
        print(run(CLEANUP))
        return

    if a.arrow_test:
        print(run(ARROW_TEST))
        print('\nNow finish it in Vectorworks: select that circuit, nudge it so the')
        print('PIO rebuilds, and READ BOTH ENDS. Different strings => per-end.')
        print('Then set Circuit Type back to "rounded" (or undo).')
        return

    rows = enumerate_circuits()
    print('%d circuits found.' % len(rows))

    if a.restore:
        if not os.path.exists(a.baseline):
            raise SystemExit('no baseline at %s -- nothing to restore from' % a.baseline)
        baseline = json.load(open(a.baseline))
        plan = plan_restore(rows, baseline, a.limit)
        print('%d circuits to restore.' % len(plan))
        show_plan(plan, rows)
        if plan:
            print('applying...')
            print('restored %d circuits.' % execute(plan, rows, a.batch,
                                                    'ShowCAD: restore connector fields'))
        return

    plan = plan_apply(rows, a.limit)
    print('%d circuits would change (%d already correct or skipped).'
          % (len(plan), len(rows) - len(plan)))
    show_plan(plan, rows)

    if not a.apply:
        print('\nDRY RUN -- nothing written. Re-run with --apply to commit.')
        print('Read the caveats at the top of this file first.')
        return

    if not os.path.exists(a.baseline):
        json.dump(rows, open(a.baseline, 'w'), indent=1)
        print('baseline written to %s' % a.baseline)
    else:
        print('baseline already exists at %s (kept)' % a.baseline)

    print('applying in batches of %d...' % a.batch)
    print('changed %d circuits.' % execute(plan, rows, a.batch,
                                           'ShowCAD: far-end circuit labels'))
    print('\nNothing was saved. The drawing will not repaint until the Circuit')
    print('objects regenerate -- see the header of this file.')


if __name__ == '__main__':
    main()
