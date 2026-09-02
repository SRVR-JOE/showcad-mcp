#!/usr/bin/env python3
"""sl_dump.py — run sl_dump_records against the LIVE Vectorworks document.

STRICTLY READ-ONLY. It loads vwx-plugin/sl_commands.py inside Vectorworks via
the bridge's execute_script and calls sl_dump_records, which performs only
getters and traversals: no SetRField, no ResetObject, no selection change, no
menu command, no dialog. Nothing it calls can raise into Vectorworks —
every verb is wrapped.

This is the one run that collapses every TBV field name in
domain/docs/SPOTLIGHT-DESIGN.md §2 into fact.

  Prereq: in Vectorworks, Tools > Plug-ins > Run Script... > START_BRIDGE_MAC.py
          and leave the "Active on :9878" dialog open. Open the show file first.

  python3 tools/sl_dump.py                       # summary to stdout
  python3 tools/sl_dump.py --json out.json       # full dump to a file
  python3 tools/sl_dump.py --out domain/docs/records/spotlight.json

Exit: 0 ok · 2 bridge unreachable · 3 the dump reported an error.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from vwx_cli import call  # same newline-JSON protocol, one implementation

PLUGIN_DIR = os.path.join(os.path.dirname(HERE), 'vwx-plugin')

# Loaded by path so the repo copy is used even if an older sl_commands.py is
# already deployed into the Vectorworks Plug-ins folder.
SCRIPT = '''
import json, sys, importlib.util
spec = importlib.util.spec_from_file_location("sl_commands_live", %(path)r)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
__result__ = json.dumps(mod.sl_dump_records(%(params)s), default=str)
'''


def main(argv):
    out_path = None
    for flag in ('--json', '--out'):
        if flag in argv:
            out_path = argv[argv.index(flag) + 1]

    script = SCRIPT % {'path': os.path.join(PLUGIN_DIR, 'sl_commands.py'),
                       'params': repr({'all_format_names': True,
                                       'sample_fields': True})}
    try:
        resp = call('execute_script', {'code': script})
    except (ConnectionRefusedError, OSError) as e:
        print(json.dumps({'error': 'bridge unreachable on 127.0.0.1:9878 (%s)' % e,
                          'fix': 'In Vectorworks: Tools > Plug-ins > Run Script... '
                                 '> START_BRIDGE_MAC.py, leave the dialog open.'},
                         indent=2))
        return 2

    body = resp.get('result') or resp
    if isinstance(body, dict) and body.get('error'):
        print(json.dumps(body, indent=2))
        return 3
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except Exception:
            print(body)
            return 3
    if not isinstance(body, dict):
        print(json.dumps(resp, indent=2))
        return 3

    if out_path:
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(body, f, indent=2, default=str)
        print('wrote %s' % out_path)

    print('document          : %s' % (body.get('document') or {}).get('name'))
    print('PIO criteria used : %s' % body.get('pio_criteria_used'))
    print('formats matched   : %s' % body.get('record_formats_matched'))
    for row in body.get('pio_census') or []:
        print('  census  %-34s %5s  type_n=%s'
              % (row['parametric_record'], row['count'], row['type_n']))
    for name, fmt in (body.get('record_formats') or {}).items():
        print('\n%s — %s fields' % (name, fmt['field_count']))
        for fl in fmt['fields']:
            print('    %3s  %-34s type=%s (%s)'
                  % (fl['index'], fl['name'], fl['type'], fl['type_name_tbv']))
    for name, s in (body.get('samples') or {}).items():
        print('\nsample: %s  (resolved field spellings)' % name)
        for k, t in sorted((s.get('resolved_field_spellings') or {}).items()):
            print('    %-16s %s' % (k, t))
        print('    ldevice: %s' % s.get('ldevice'))
    print('\nvision mapping    : %r' % body.get('vision_mapping'))
    for n in body.get('notes') or []:
        print('\nNOTE: %s' % n)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
