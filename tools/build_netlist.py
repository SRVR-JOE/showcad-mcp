#!/usr/bin/env python3
"""Emit domain/devices/netlist.json from the user's stated topology.

Every endpoint is validated against domain/devices/library.json before it is
written, so a socket name that does not exist fails HERE rather than silently
producing a dangling circuit in Vectorworks.

Confidence is two axes, because they differ sharply:
  path_confidence  - did the user say A connects to B?
  port_confidence  - are the specific socket numbers theirs, or ours?
The user stated paths. Every port number is ours until they say otherwise.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = os.path.join(ROOT, 'domain', 'devices', 'library.json')
OUT = os.path.join(ROOT, 'domain', 'devices', 'netlist.json')

lib = json.load(open(LIB))
DEVS = lib if isinstance(lib, list) else lib.get('devices', list(lib.values()))
BYKEY = {d['key']: d for d in DEVS if isinstance(d, dict) and 'key' in d}

# instance name -> library key
INSTANCES = {
    'SRV DIR': 'disguise_server', 'SRV ACT': 'disguise_server', 'SRV UND': 'disguise_server',
    'RTR 1': 'lightware_mx2',
    'SX40 1': 'sx40', 'SX40 2': 'sx40', 'SX40 3': 'sx40',
    'MV 1': 'mv_9971',
    'HA5 1': 'og_ha5_12g', 'HA5 2': 'og_ha5_12g', 'HA5 3': 'og_ha5_12g',
    'DA 1': 'sra_8901_4', 'DA 2': 'sra_8901_4', 'DA 3': 'sra_8901_4',
    'SPG 1': 'spg8260',
    'SR112': 'sr112', 'TR12D': 'tr12d', 'AVN-AIO8R': 'avn_aio8r',
    'MIF4 1': 'mif4', 'MIF4 2': 'mif4', 'MIF4 3': 'mif4',
    'SW01': 'sw_m4350_24x4v', 'SW02': 'sw_m4350_24x4v',
    'FIDO TX': 'fido_2t_12g',
    'XD 1': 'xd', 'XD 2': 'xd',
}

ERRORS = []


def skt(inst, name, want_dir=None):
    """Assert the socket exists on that instance's device type."""
    key = INSTANCES.get(inst)
    if not key:
        ERRORS.append('unknown instance %r' % inst); return name
    dev = BYKEY.get(key)
    if not dev:
        ERRORS.append('instance %r -> unknown library key %r' % (inst, key)); return name
    matches = [s for s in dev['sockets'] if s['name'] == name]
    if not matches:
        ERRORS.append('%s (%s): no socket %r' % (inst, key, name)); return name
    if want_dir and not any(s['dir'] in (want_dir, 'io') for s in matches):
        ERRORS.append('%s.%s: no %r direction (has %s)'
                      % (inst, name, want_dir, [s['dir'] for s in matches]))
    return name


C = []


def wire(n, sd, ss, dd, ds, signal, cable, note=None, port='assigned_by_us'):
    skt(sd, ss, 'out'); skt(dd, ds, 'in')
    row = {'n': n, 'src': [sd, ss], 'dst': [dd, ds], 'signal': signal,
           'cable': cable, 'path_confidence': 'stated', 'port_confidence': port}
    if note:
        row['note'] = note
    C.append(row)


n = 0
def nxt():
    global n
    n += 10
    return n

# ── capture: 3x 12G-SDI, distributed to all three servers via DAs ────────────
# The user said "3 12G SDI OF CAPTURE". Three servers running DIR/ACT/UND all
# need the same feeds, so each capture goes through a DA. The DA is inferred,
# not stated - without it one capture could only reach one server.
CAP_IN = ['12G-SDI_IN A', '12G-SDI_IN E', '12G-SDI_IN I']
for i, (da, cap_socket) in enumerate(zip(['DA 1', 'DA 2', 'DA 3'], CAP_IN), start=1):
    for j, srv in enumerate(['SRV DIR', 'SRV ACT', 'SRV UND'], start=1):
        wire(nxt(), da, '12G-SDI_OUT %d' % j, srv, cap_socket, '12G-SDI', 'BNC',
             note='capture %d to %s (DA fan-out inferred, not stated)' % (i, srv))

# ── servers -> matrix over HDMI (user stated) ───────────────────────────────
mi = 0
for srv in ['SRV DIR', 'SRV ACT', 'SRV UND']:
    for slot in [1, 2, 3]:
        mi += 1
        wire(nxt(), srv, 'VFC Slot %d' % slot, 'RTR 1', 'HDMI_2.0 %d' % mi,
             'HDMI2.0', 'HDMI')

# ── matrix -> SX40 (user stated; SX40 has exactly one HDMI input) ───────────
for i, sx in enumerate(['SX40 1', 'SX40 2', 'SX40 3'], start=1):
    wire(nxt(), 'RTR 1', 'HDMI_2.0 %d' % i, sx, 'HDMI2.0_IN', 'HDMI2.0', 'HDMI')

# ── matrix <-> MV, both directions (user stated) ────────────────────────────
for i in range(1, 5):
    wire(nxt(), 'RTR 1', 'HDMI_2.0 %d' % (12 + i), 'MV 1', 'HDMI2.0_IN %d' % i,
         'HDMI2.0', 'HDMI')
for i in (1, 2):
    wire(nxt(), 'MV 1', 'HDMI2.0_OUT %d' % i, 'RTR 1', 'HDMI_2.0 %d' % (14 + i),
         'HDMI2.0', 'HDMI',
         note='MV RETURN - right-to-left edge, render as panel cross-reference')

# ── timecode: Dante TC -> TR12D -> SR112 -> MIF4 -> server USB ──────────────
# The GX3 has NO LTC input - verified from the as-built socket list. Timecode
# reaches it through the Rosendahl MIF 4 over USB, exactly as the as-built
# draws (TCIntf01/02). This is why "DANTE IS WIRED FOR SERVERS VIA SR112"
# cannot be a direct Dante-to-SR112 link: the SR-112 has no Dante port.
wire(nxt(), 'TR12D', 'LTC_OUT 1', 'SR112', 'LTC_IN', 'LTC', 'XLR3',
     note='Dante timecode lands on TR12D, converted to LTC - NEEDS USER CONFIRMATION')
for i, mif in enumerate(['MIF4 1', 'MIF4 2', 'MIF4 3'], start=1):
    wire(nxt(), 'SR112', 'LTC_OUT %d' % i, mif, 'LTC_IN', 'LTC', 'XLR3')
for mif, srv in zip(['MIF4 1', 'MIF4 2', 'MIF4 3'], ['SRV DIR', 'SRV ACT', 'SRV UND']):
    wire(nxt(), mif, 'USB2_IO', srv, 'USB 1', 'USB', 'USB',
         note='timecode into the server over USB - the GX3 has no LTC input')

# ── Dante audio -> servers, via the Sonifex (NOT via the SR-112) ───────────
for i, srv in enumerate(['SRV DIR', 'SRV ACT', 'SRV UND'], start=1):
    for ch, side in ((2 * i - 1, 'L'), (2 * i, 'R')):
        wire(nxt(), 'AVN-AIO8R', 'LINE_OUT %d' % ch, srv, 'LINE_IN %s' % side,
             'LINE', 'XLR3', note='Dante audio breakout - inferred path')

# ── reference / genlock ─────────────────────────────────────────────────────
# The SPG8260-R2 has four reference groups, each with an A and B output.
# Servers take group 1, processors group 2 - keeping the two domains on
# separate distribution groups is normal practice and survives a group fault.
SPG_OUTS = ['REF1_OUT A', 'REF1_OUT B', 'REF2_OUT A']
for srv, so in zip(['SRV DIR', 'SRV ACT', 'SRV UND'], SPG_OUTS):
    wire(nxt(), 'SPG 1', so, srv, 'REF_IN', 'REF', 'BNC')
for sx, so in zip(['SX40 1', 'SX40 2', 'SX40 3'],
                  ['REF3_OUT A', 'REF3_OUT B', 'REF4_OUT A']):
    wire(nxt(), 'SPG 1', so, sx, 'REF_IN', 'REF', 'BNC')

# ── FOH over fibre: matrix -> HDMI/SDI convert -> FiDO TX ──────────────────
wire(nxt(), 'RTR 1', 'HDMI_2.0 10', 'HA5 1', 'HDMI2.0_IN', 'HDMI2.0', 'HDMI')
wire(nxt(), 'HA5 1', '12G-SDI_OUT 1', 'FIDO TX', '12G-SDI_IN 1', '12G-SDI', 'BNC')
wire(nxt(), 'MV 1', '12G-SDI_OUT 1', 'FIDO TX', '12G-SDI_IN 2', '12G-SDI', 'BNC',
     note='multiview to FOH')

# ── network: switch trunk over fibre (user stated) ─────────────────────────
wire(nxt(), 'SW01', 'SFP28 1', 'SW02', 'SFP28 1', 'SMF', 'LC',
     note='switch-to-switch fibre trunk')
wire(nxt(), 'SW01', 'SFP28 2', 'SW02', 'SFP28 2', 'SMF', 'LC',
     note='redundant trunk - inferred, not stated')
wire(nxt(), 'AVN-AIO8R', 'DANTE PRI', 'SW01', 'LAN 1', 'DANTE', 'EC6A')
wire(nxt(), 'TR12D', 'DANTE', 'SW01', 'LAN 2', 'DANTE', 'EC6A',
     note='Dante timecode onto the network')
for i, srv in enumerate(['SRV DIR', 'SRV ACT', 'SRV UND'], start=3):
    wire(nxt(), srv, 'LAN A', 'SW01', 'LAN %d' % i, 'LAN', 'EC6A')

# ── SX40 -> LED distribution ────────────────────────────────────────────────
for i, (sx, xd) in enumerate(zip(['SX40 1', 'SX40 2'], ['XD 1', 'XD 2']), start=1):
    wire(nxt(), sx, '10G_OUT 1 Fib', xd, '10G_IN Fib', '10G', 'OpticalCON DUO',
         note='XD count depends on the LED map - NOT yet known')

out = {
    '_comment': __doc__,
    '_open': [
        'EVERY port number here is ours, not the user\'s. Paths are theirs.',
        'DA fan-out for capture is inferred - the user said 3x 12G-SDI capture '
        'but not how one feed reaches three servers.',
        'Third SX40: device team reads it as a backup processor (2 carry the two '
        '4K surfaces). Still consumes a matrix output either way.',
        'SR-112 has NO Dante port (verified rear panel). Dante timecode is '
        'assumed to arrive via the Glensound TR-12D. Needs user yes/no.',
        'XD count and the SX40->LED fan-out depend on the LED map, which we do '
        'not have. Two XDs shown as a placeholder.',
        'Server model assumed GX3 from the pull sheet and as-built; the user '
        'said only "disguise servers", and 3 are needed where the sheet has 2.',
    ],
    'instances': INSTANCES,
    'circuits': C,
}
json.dump(out, open(OUT, 'w'), indent=2)

print('circuits: %d' % len(C))
if ERRORS:
    print('\nVALIDATION FAILURES (%d):' % len(ERRORS))
    for e in sorted(set(ERRORS)):
        print('  ' + e)
    sys.exit(1)
print('all endpoints validated against library.json')
