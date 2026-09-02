# ═══════════════════════════════════════════════════════════════════════════
#  ShowCAD — one-shot repair + labelling for DOJA26_SRVR_V1
#  PASTE INTO: Resource Manager > New Resource > Script > LANGUAGE = PYTHON
#  Then double-click to run. No bridge, no dialog: a script resource runs with
#  a LIVE parametric engine, which is why changes here actually render.
#
#  Does four things, all inside ONE named undo event:
#    1. Collapses double spaces in socket names (SDI_IN  01 -> SDI_IN 01)
#    2. Backs up every circuit's original connector values to disk
#    3. Writes the FAR-END name into each end's connector field, so each end
#       names where the cable goes / comes from
#    4. Reports whether the parametric engine is actually running
#
#  REVERSIBLE two ways: Cmd+Z, or re-run with RESTORE = True below.
# ═══════════════════════════════════════════════════════════════════════════
import vs, json, os, io, re

RESTORE = False          # set True to put the original connector values back
BACKUP  = os.path.expanduser('~/showcad_connector_backup.json')
REPORT  = os.path.expanduser('~/showcad_fix_report.json')

rep = {'engine_runs': None, 'sockets_renamed': 0, 'circuits': 0,
       'labels_written': 0, 'restored': 0, 'errors': []}

def norm(s):
    return re.sub(r'  +', ' ', s).strip() if s else s

# ── collect ────────────────────────────────────────────────────────────────
devices, circuits = [], []
def collect(h):
    pr = vs.GetParametricRecord(h)
    if not pr:
        return
    n = vs.GetName(pr)
    if n in ('Device', 'Device-External'):
        devices.append(h)
    elif n == 'Circuit':
        circuits.append(h)
vs.ForEachObject(collect, "(ALL)")
rep['devices'] = len(devices)
rep['circuits'] = len(circuits)

vs.NameUndoEvent('ShowCAD: repair + far-end labels')

# ── 1. engine check, WITHOUT creating anything ────────────────────────────
# Earlier this probed CreateCustomObjectN('Angle', 5.0, 5.0, 0, False). That is
# wrong twice over: the signature is (objectName, p, rotationAngle, showPref)
# where p is a POINT TUPLE, so the extra argument shifted 5.0 into the angle
# slot and VW reported "incorrect angle format". Creating a throwaway PIO in
# the user's real drawing was also needless risk. Toggling a field on a circuit
# that already exists answers the same question and touches nothing new.
try:
    probe_h = circuits[0] if circuits else None
    if probe_h is not None:
        def _flat_bbox(h):
            bb = vs.GetBBox(h)
            out = []
            for part in bb:
                out.extend(part) if isinstance(part, (tuple, list)) else out.append(part)
            return [round(float(v), 6) for v in out]

        before_bb = _flat_bbox(probe_h)
        keep = vs.GetRField(probe_h, 'Circuit', 'Number')
        vs.SetRField(probe_h, 'Circuit', 'Number', 'ENGINEPROBE')
        vs.ResetObject(probe_h)
        after_bb = _flat_bbox(probe_h)
        vs.SetRField(probe_h, 'Circuit', 'Number', keep)   # restore
        vs.ResetObject(probe_h)
        rep['probe_bbox_before'] = before_bb
        rep['probe_bbox_after'] = after_bb
        # A circuit that regenerates redraws its number text, changing the bbox.
        rep['engine_runs'] = (before_bb != after_bb)
    else:
        rep['errors'].append('engine probe: no circuits found')
except Exception as e:
    rep['errors'].append('engine probe: %s' % str(e)[:140])

# ── 2. socket names: collapse double spaces (descend INTO device PIOs) ─────
def walk_sockets(h, depth=0):
    if depth > 4:
        return
    try:
        c = vs.FInGroup(h)
    except Exception:
        return
    while c:
        try:
            pr = vs.GetParametricRecord(c)
            if pr and vs.GetName(pr) == 'Socket':
                nm = vs.GetRField(c, 'Socket', 'name')
                if nm and '  ' in nm:
                    vs.SetRField(c, 'Socket', 'name', norm(nm))
                    vs.ResetObject(c)
                    rep['sockets_renamed'] += 1
            walk_sockets(c, depth + 1)
        except Exception:
            pass
        try:
            c = vs.NextObj(c)
        except Exception:
            break

if not RESTORE:
    for d in devices:
        walk_sockets(d)

# ── 3. connector fields <- far-end names ───────────────────────────────────
# The two CC-Circuit-Connector loci inside a Circuit render Src_Skt_Conn and
# Dst_Skt_Conn. Putting the FAR end's name in each is what makes an end say
# where the cable is going. Originals are saved first so this is reversible
# even after the undo stack is gone.
if RESTORE:
    try:
        saved = json.load(io.open(BACKUP, encoding='utf-8'))
    except Exception as e:
        saved = {}
        rep['errors'].append('no backup to restore: %s' % str(e)[:120])
    for h in circuits:
        uid = vs.GetObjectUuid(h)
        row = saved.get(uid)
        if not row:
            continue
        try:
            vs.SetRField(h, 'Circuit', 'Src_Skt_Conn', row['src'])
            vs.SetRField(h, 'Circuit', 'Dst_Skt_Conn', row['dst'])
            vs.ResetObject(h)
            rep['restored'] += 1
        except Exception:
            pass
else:
    backup = {}
    for h in circuits:
        try:
            uid = vs.GetObjectUuid(h)
            src_conn = vs.GetRField(h, 'Circuit', 'Src_Skt_Conn')
            dst_conn = vs.GetRField(h, 'Circuit', 'Dst_Skt_Conn')
            backup[uid] = {'src': src_conn, 'dst': dst_conn}

            src_dev = norm(vs.GetRField(h, 'Circuit', 'Src_Dev_Name'))
            src_skt = norm(vs.GetRField(h, 'Circuit', 'Src_Skt_Name'))
            dst_dev = norm(vs.GetRField(h, 'Circuit', 'Dst_Dev_Name'))
            dst_skt = norm(vs.GetRField(h, 'Circuit', 'Dst_Skt_Name'))

            # each end names the FAR end
            near = ('%s %s' % (dst_dev or '', dst_skt or '')).strip()
            far  = ('%s %s' % (src_dev or '', src_skt or '')).strip()
            if near:
                vs.SetRField(h, 'Circuit', 'Src_Skt_Conn', near)
            if far:
                vs.SetRField(h, 'Circuit', 'Dst_Skt_Conn', far)
            vs.ResetObject(h)
            rep['labels_written'] += 1
        except Exception as e:
            rep['errors'].append('circuit: %s' % str(e)[:100])
    try:
        with io.open(BACKUP, 'w', encoding='utf-8') as f:
            f.write(json.dumps(backup, indent=1))
        rep['backup_written'] = BACKUP
    except Exception as e:
        rep['errors'].append('backup write: %s' % str(e)[:120])

vs.ReDrawAll()
with io.open(REPORT, 'w', encoding='utf-8') as f:
    f.write(json.dumps(rep, indent=2))

vs.AlrtDialog(
    'ShowCAD done.\n\n'
    'Parametric engine running here: %s\n'
    'Sockets renamed: %d\n'
    'Circuits labelled: %d   restored: %d\n\n'
    'Report: %s\nBackup: %s'
    % (rep['engine_runs'], rep['sockets_renamed'],
       rep['labels_written'], rep['restored'], REPORT, BACKUP))
