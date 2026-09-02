# ═══════════════════════════════════════════════════════════════════════════
#  ShowCAD — fix duplicate / placeholder device names
#  Resource Manager > New Resource > Script > LANGUAGE = PYTHON > paste > run
#
#  WHY: circuits reference their endpoints BY NAME. Six devices called
#  '<DEVICE>' are indistinguishable to any schedule, worksheet or bulk import.
#  48 of the 220 circuits currently land on an ambiguous name.
#
#  Devices are matched by INDEX in drawing order (the order ForEachObject
#  returns them), because name cannot disambiguate them - that is the bug.
#  DRY_RUN prints the mapping against what it actually found, so you can
#  confirm every row before writing anything.
#
#  EDIT THE NAMES BELOW if you disagree - they are inferences from model and
#  connectivity, not gospel.
# ═══════════════════════════════════════════════════════════════════════════
import vs, json, os, io

DRY_RUN = True          # set False to actually write

# index in drawing order -> (expected current name, expected model, new name)
RENAMES = {
    27: ('<ACT_3 - KVM>', 'ALIF4000T',      '<UND_1 - KVM>'),
    32: ('<DEVICE>',      'SFC-6901',       '12G TX/RX_3'),
    33: ('<DEVICE>',      'SFC-6901',       '12G TX/RX_4'),
    36: ('12G TX/RX_1',   'SFC-6901',       '12G TX/RX_2'),
    34: ('<DEVICE>',      '9971-MV6-4K',    '<SHOW MV 2>'),
    40: ('<DEVICE>',      'ALIF4000T',      '<FOH KVM 1>'),
    41: ('<DEVICE>',      'ALIF4000T',      '<FOH KVM 2>'),
    42: ('<DEVICE>',      'AIO8R',          '<DANTE AUDIO>'),
    43: ('UDC-4K',        'UDC-4K',         'UDC-4K 1'),
    44: ('UDC-4K',        'UDC-4K',         'UDC-4K 2'),
    45: ('UDC-4K',        'UDC-4K',         'UDC-4K 3'),
    46: ('UDC-4K',        'UDC-4K',         'UDC-4K 4'),
}

rep = {'dry_run': DRY_RUN, 'matched': [], 'MISMATCHED': [], 'renamed': 0}

devices = []
def collect(h):
    pr = vs.GetParametricRecord(h)
    if pr and vs.GetName(pr) in ('Device', 'Device-External'):
        devices.append(h)
vs.ForEachObject(collect, "(ALL)")
rep['devices_found'] = len(devices)

if not DRY_RUN:
    vs.NameUndoEvent('ShowCAD: fix duplicate device names')

for idx in sorted(RENAMES):
    want_name, want_model, new_name = RENAMES[idx]
    if idx >= len(devices):
        rep['MISMATCHED'].append({'index': idx, 'why': 'index beyond %d devices' % len(devices)})
        continue
    h = devices[idx]
    cur = vs.GetRField(h, 'Device', 'name')
    mdl = vs.GetRField(h, 'Device', 'model') or ''
    # Refuse to rename anything that is not what we expect at that index.
    # Drawing order could differ from the read this mapping was built from,
    # and renaming the wrong device would be worse than renaming none.
    if cur != want_name or want_model not in mdl:
        rep['MISMATCHED'].append({'index': idx, 'found_name': cur, 'found_model': mdl,
                                  'expected_name': want_name, 'expected_model': want_model})
        continue
    rep['matched'].append({'index': idx, 'from': cur, 'model': mdl, 'to': new_name})
    if not DRY_RUN:
        vs.SetRField(h, 'Device', 'name', new_name)
        vs.ResetObject(h)
        rep['renamed'] += 1

# circuits carry denormalised copies of the endpoint device names
if not DRY_RUN and rep['renamed']:
    remap = {}
    for m in rep['matched']:
        remap.setdefault(m['from'], []).append(m['to'])
    # only safe where the old name was unique; ambiguous ones need the
    # circuit's own handle-based endpoints, which ConnectCAD rebuilds itself
    rep['note'] = ('Circuit Src_Dev_Name / Dst_Dev_Name are DERIVED - ConnectCAD '
                   'rewrites them from the socket on every recalculation, so they '
                   'will pick up the new names by themselves. Not touched here.')

out = os.path.expanduser('~/showcad_names_report.json')
with io.open(out, 'w', encoding='utf-8') as f:
    f.write(json.dumps(rep, indent=2))

lines = ['%-3s %-18s -> %s' % (m['index'], m['from'], m['to']) for m in rep['matched']]
bad = ['%-3s FOUND %r / %r' % (m['index'], m.get('found_name'), m.get('found_model'))
       for m in rep['MISMATCHED']]
vs.AlrtDialog(
    ('DRY RUN - nothing written\n\n' if DRY_RUN else 'RENAMED %d devices\n\n' % rep['renamed'])
    + 'WILL RENAME:\n' + '\n'.join(lines)
    + ('\n\nMISMATCHED (skipped):\n' + '\n'.join(bad) if bad else '\n\nNo mismatches.')
    + '\n\nReport: ' + out)
