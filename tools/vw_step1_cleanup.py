# ═══════════════════════════════════════════════════════════════════════════
#  ShowCAD STEP 1 — cleanup + kill the connector text
#  PASTE INTO: Resource Manager > New Resource > Script > LANGUAGE = PYTHON
#
#  Runs in a script-resource context, which HAS a live parametric engine -
#  unlike the bridge, whose modal dialog is why nothing we set ever rendered.
#
#  1. Reports whether the engine really is running here
#  2. Collapses double spaces in socket names  (SDI_IN  01 -> SDI_IN 01)
#  3. Hides the connector-type text ("BNC") on the design layer AND in every
#     sheet viewport - viewports carry their own class visibility, so hiding
#     the class alone would look right on screen and still print wrong
#
#  Reversible: Cmd+Z, or set UNDO_CONNECTOR_HIDE = True and re-run.
# ═══════════════════════════════════════════════════════════════════════════
import vs, json, os, io, re

UNDO_CONNECTOR_HIDE = False        # True = show the connector text again
CONN_CLASS = 'CC-Circuit-Connector'
REPORT = os.path.expanduser('~/showcad_step1_report.json')

rep = {'engine_runs': None, 'sockets_scanned': 0, 'sockets_renamed': 0,
       'viewports_updated': [], 'errors': [], 'samples': []}

def norm(s):
    return re.sub(r'  +', ' ', s).strip() if s else s

vs.NameUndoEvent('ShowCAD step 1: cleanup + connector text')

# ── 1. is the parametric engine alive in THIS context? ────────────────────
try:
    try:
        vs.CreateCustomObjectN('Angle', 5.0, 5.0, 0, False)
    except TypeError:
        vs.CreateCustomObjectN('Angle', (5.0, 5.0), 0, False)
    p = vs.LNewObj()
    if p:
        bb = vs.GetBBox(p)
        flat = []
        for part in bb:
            flat.extend(part) if isinstance(part, (tuple, list)) else flat.append(part)
        rep['probe_bbox'] = [round(float(v), 4) for v in flat]
        rep['engine_runs'] = any(abs(float(v)) > 1e-9 for v in flat)
        vs.DelObject(p)
except Exception as e:
    rep['errors'].append('engine probe: %s' % str(e)[:140])

# ── 2. socket names ───────────────────────────────────────────────────────
devices = []
def collect(h):
    pr = vs.GetParametricRecord(h)
    if pr and vs.GetName(pr) in ('Device', 'Device-External'):
        devices.append(h)
vs.ForEachObject(collect, "(ALL)")
rep['devices'] = len(devices)

def walk(h, depth=0):
    # sockets live INSIDE device PIOs; a top-level sweep sees none of them
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
                rep['sockets_scanned'] += 1
                nm = vs.GetRField(c, 'Socket', 'name')
                if nm and '  ' in nm:
                    new = norm(nm)
                    vs.SetRField(c, 'Socket', 'name', new)
                    vs.ResetObject(c)
                    rep['sockets_renamed'] += 1
                    if len(rep['samples']) < 8:
                        rep['samples'].append([nm, new])
            walk(c, depth + 1)
        except Exception:
            pass
        try:
            c = vs.NextObj(c)
        except Exception:
            break

if not UNDO_CONNECTOR_HIDE:
    for d in devices:
        walk(d)

# circuits keep denormalised copies of the socket names - keep them in step
circuits = []
def collect_c(h):
    pr = vs.GetParametricRecord(h)
    if pr and vs.GetName(pr) == 'Circuit':
        circuits.append(h)
vs.ForEachObject(collect_c, "(ALL)")
rep['circuits'] = len(circuits)
fixed = 0
if not UNDO_CONNECTOR_HIDE:
    for h in circuits:
        for f in ('Src_Skt_Name', 'Dst_Skt_Name'):
            try:
                v = vs.GetRField(h, 'Circuit', f)
                if v and '  ' in v:
                    vs.SetRField(h, 'Circuit', f, norm(v))
                    fixed += 1
            except Exception:
                pass
rep['circuit_fields_fixed'] = fixed

# ── 3. connector text: design layer + EVERY sheet viewport ────────────────
try:
    if UNDO_CONNECTOR_HIDE:
        vs.ShowClass(CONN_CLASS)
    else:
        vs.HideClass(CONN_CLASS)
    rep['class_visibility'] = vs.GetCVis(CONN_CLASS)
except Exception as e:
    rep['errors'].append('class vis: %s' % str(e)[:140])

# 0 = invisible, 1 = visible, 2 = grey  (SetVPClassVisibility)
want = 1 if UNDO_CONNECTOR_HIDE else 0
vps = []
def collect_vp(h):
    try:
        if vs.GetTypeN(h) == 122:      # viewport
            vps.append(h)
    except Exception:
        pass
vs.ForEachObjectInLayer(collect_vp, 0, 2, 0)   # all layers, all objects
if not vps:
    # fall back to a whole-document sweep if the layer-scoped call finds none
    def collect_vp2(h):
        try:
            if vs.GetTypeN(h) == 122:
                vps.append(h)
        except Exception:
            pass
    vs.ForEachObject(collect_vp2, "(ALL)")

for vp in vps:
    try:
        before = vs.GetVPClassVisibility(vp, CONN_CLASS)
        vs.SetVPClassVisibility(vp, CONN_CLASS, want)
        after = vs.GetVPClassVisibility(vp, CONN_CLASS)
        rep['viewports_updated'].append(
            {'name': vs.GetName(vp) or '(unnamed)', 'before': before, 'after': after})
        vs.ResetObject(vp)
    except Exception as e:
        rep['errors'].append('vp: %s' % str(e)[:120])

vs.ReDrawAll()
with io.open(REPORT, 'w', encoding='utf-8') as f:
    f.write(json.dumps(rep, indent=2))

vs.AlrtDialog(
    'ShowCAD step 1 done.\n\n'
    'Parametric engine running here: %s\n'
    'Sockets renamed: %d of %d scanned\n'
    'Circuit fields fixed: %d\n'
    'Viewports updated: %d\n\n'
    'Report: %s'
    % (rep['engine_runs'], rep['sockets_renamed'], rep['sockets_scanned'],
       fixed, len(rep['viewports_updated']), REPORT))
