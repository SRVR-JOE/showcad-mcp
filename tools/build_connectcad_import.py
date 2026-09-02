#!/usr/bin/env python3
"""Emit everything ConnectCAD needs to build the drawing via its own bulk path.

Three outputs:
  showcad_devices_db.txt  24-col TSV rows for devices NOT already in
                          ConnectCAD's 17k-row database. Drop into the USER
                          library so it survives a Vectorworks update.
  bom.tsv                 worksheet for  Create Devices From BoM
  connections.tsv         worksheet for  Make Connections from List

Why this route: circuits cannot be bound from the bridge (see
domain/docs/CONNECT-MECHANISM.md) — writing Src_Dev_Name is cosmetic and
leaves __Src_ID empty. ConnectCAD's own bulk commands produce REAL bindings.

Signal and connector values come from ConnectCAD's vocabulary, not ours:
12G-SDI -> 12GV, HDMI2.0 -> HDMI, fibre -> OPT. Feeding our researched names
would produce rows ConnectCAD silently cannot resolve.
"""
import csv
import io
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEV = os.path.join(ROOT, 'domain', 'devices')
APPDB = ('/Applications/Vectorworks 2026/Libraries/Defaults/ConnectCAD/'
         'ConnectCAD_Database/ConnectCAD Devices DB.txt')

# our signal vocabulary -> ConnectCAD's
SIG = {'12G-SDI': '12GV', 'HDMI2.0': 'HDMI', 'SMF': 'OPT', 'LTC': 'LTC',
       'LINE': 'LINE', 'DANTE': 'DANTE', 'LAN': 'LAN', 'USB': 'USB',
       'REF': 'REF', '10G': 'LAN', '1G': 'LAN', 'DP': 'DP', 'MIDI': 'MIDI',
       'PWR': 'PWR', 'GPIO': 'GPI', 'ADAT': 'ADAT', '3G-SDI': '3GV'}
CON = {'BNC': 'BNC', 'HDMI': 'HDMI', 'LC': 'LCDUP', 'XLR3': 'XLR3M',
       'XLR3F': 'XLR3F', 'XLR3M': 'XLR3M', 'EC6A': 'RJ45', 'EC5e': 'RJ45',
       'RJ45': 'RJ45', 'USB-A': 'USB-A', 'USB-B': 'USB-B', 'DP': 'DP',
       'OpticalCON DUO': 'LCDUP', 'DIN5': 'DIN5M', 'TOSLINK': 'TOS',
       'IEC': 'C13', 'DC': 'PSU-DC', 'NAC3FX-W-TOP': 'pCON', 'HD15': 'HD15M',
       'HDMI-C': 'HDMI', 'DB25': 'DB25M', 'TRS': 'STJ', 'RCA': 'RCA', '---': '---'}

# These five DO exist in ConnectCAD's shipped database. We still define our
# own entries, deliberately, for two reasons:
#   1. Socket NAMES differ. The DB calls the SX40 input "HDMI 2.0_IN"; our
#      verified spec and the client's own as-built use "HDMI2.0_IN". Make
#      Connections from List matches on the name, so a mismatch silently
#      fails to connect.
#   2. The DB is simplified in places. Its SR-112 has TC_OUT qty=2; the real
#      rear panel has TWELVE LTC outs (verified). Using the DB entry would
#      under-provision the timecode distribution this rig depends on.
# Recorded so the user can choose the shipped entries instead if they prefer.
ALSO_IN_SHIPPED_DB = {
    'sx40':           ('Brompton',   'SX40'),
    'xd':             ('Brompton',   'XD'),
    'lightware_mx2':  ('Lightware',  'MX2-16x16-HDMI20'),
    'sr112':          ('Brainstorm', 'SR-112'),
    'mif4':           ('Rosendahl',  'MIF 4 MIDI Timecode Interface'),
}
IN_DB = {}   # define everything ourselves - exactness beats reuse here

lib = json.load(open(os.path.join(DEV, 'library.json')))
DEVS = lib if isinstance(lib, list) else lib.get('devices', list(lib.values()))
BYKEY = {d['key']: d for d in DEVS if isinstance(d, dict) and 'key' in d}
net = json.load(open(os.path.join(DEV, 'netlist.json')))
INSTANCES = net['instances']

# ── 1. DB rows for the devices ConnectCAD does not know ─────────────────────
CAT = {
    'disguise_server': ('Video', 'Server'), 'mv_9971': ('Video', 'Multiviewer'),
    'og_ha5_12g': ('Video', 'Converter'), 'ogx': ('Video', 'Frame'),
    'sra_8901_4': ('Video', 'Distribution'), 'spg8260': ('Video', 'Sync Generator'),
    'tr12d': ('Audio', 'Clock/Timecode'), 'avn_aio8r': ('Audio', 'Interface'),
    'sw_m4350_24x4v': ('Control', 'Network'), 'sw_m4250_40g8xf': ('Control', 'Network'),
    'fido_2t_12g': ('Video', 'Converter'), 'xdip': ('Control', 'KVM'),
}
rows = []
created = []
for key, dev in BYKEY.items():
    if key in IN_DB or not dev.get('sockets'):
        continue
    cat, sub = CAT.get(key, ('Video', 'Other'))
    hdr = [''] * 24
    hdr[0], hdr[1] = dev.get('make', ''), dev.get('model', '')
    hdr[2], hdr[3], hdr[4] = '482.6', '44.45', '300'      # rack default, mm
    hdr[6] = str(dev.get('power', '') or '0')
    hdr[7], hdr[8] = 'FALSE', '1'
    hdr[21], hdr[22] = cat, sub
    # first socket rides the header row, per the DB's own continuation format
    sk = dev['sockets']
    def srow(r, s):
        r[14] = CON.get(s.get('connector', ''), s.get('connector', '') or '---')
        r[15] = '1'
        r[16] = 'L' if s.get('dir') == 'in' else 'R'
        r[17] = s['name']
        r[18] = SIG.get(s.get('signal', ''), s.get('signal', '') or 'VID')
        r[19] = {'in': 'IN', 'out': 'OUT', 'io': 'IO'}.get(s.get('dir'), 'IO')
        return r
    rows.append(srow(hdr, sk[0]))
    for s in sk[1:]:
        rows.append(srow([''] * 24, s))
    created.append('%s %s (%d sockets)' % (dev.get('make'), dev.get('model'), len(sk)))

out_db = os.path.join(DEV, 'showcad_devices_db.txt')
with open(out_db, 'w', encoding='utf-8-sig', newline='') as f:
    csv.writer(f, delimiter='\t', lineterminator='\r\n').writerows(rows)

# ── 2. BoM worksheet -> Create Devices From BoM ─────────────────────────────
bom = [['Name', 'Make', 'Model', 'Qty']]
for inst, key in sorted(INSTANCES.items()):
    dev = BYKEY.get(key, {})
    mk, mo = (IN_DB[key] if key in IN_DB
              else (dev.get('make', ''), dev.get('model', '')))
    bom.append([inst, mk, mo, '1'])
with open(os.path.join(DEV, 'bom.tsv'), 'w', encoding='utf-8-sig', newline='') as f:
    csv.writer(f, delimiter='\t', lineterminator='\r\n').writerows(bom)

# ── 3. Connection list -> Make Connections from List ────────────────────────
con = [['Circuit', 'Src Device', 'Src Socket', 'Dst Device', 'Dst Socket',
        'Signal', 'Cable']]
for c in net['circuits']:
    con.append([str(c['n']), c['src'][0], c['src'][1], c['dst'][0], c['dst'][1],
                SIG.get(c['signal'], c['signal']),
                CON.get(c.get('cable', ''), c.get('cable', ''))])
with open(os.path.join(DEV, 'connections.tsv'), 'w', encoding='utf-8-sig', newline='') as f:
    csv.writer(f, delimiter='\t', lineterminator='\r\n').writerows(con)

print('also present in the shipped DB, but we define our own (%d):' % len(ALSO_IN_SHIPPED_DB))
for k, v in ALSO_IN_SHIPPED_DB.items():
    print('   %-16s shipped as %s %s' % (k, v[0], v[1]))
print('\nDB entries written (%d):' % len(created))
for c in created:
    print('   ' + c)
print('\nshowcad_devices_db.txt : %d TSV rows' % len(rows))
print('bom.tsv                : %d devices' % (len(bom) - 1))
print('connections.tsv        : %d circuits' % (len(con) - 1))


# ── 4. cross-validate: every socket in the connection list must exist ───────
defined = {}
cur = None
for r in rows:
    if r[0] and r[1]:
        cur = '%s|%s' % (r[0], r[1])
        defined.setdefault(cur, set())
    if cur and r[17]:
        defined[cur].add(r[17])

bad = []
for c in net['circuits']:
    for inst, sock in ((c['src'][0], c['src'][1]), (c['dst'][0], c['dst'][1])):
        key = INSTANCES.get(inst)
        dev = BYKEY.get(key, {})
        dk = '%s|%s' % (dev.get('make', ''), dev.get('model', ''))
        if dk not in defined:
            bad.append('circuit %s: %s -> no DB entry for %s' % (c['n'], inst, dk))
        elif sock not in defined[dk]:
            bad.append('circuit %s: %s.%s not in %s' % (c['n'], inst, sock, dk))

if bad:
    print('\nCONSISTENCY FAILURES (%d):' % len(bad))
    for b in sorted(set(bad))[:20]:
        print('   ' + b)
    raise SystemExit(1)
print('\nconsistency: all %d circuits reference sockets that exist' % len(net['circuits']))
