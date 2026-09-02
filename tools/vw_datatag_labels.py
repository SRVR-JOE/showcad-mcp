# ---------------------------------------------------------------------------
# vw_datatag_labels.py  -  ShowCAD circuit end labels via Data Tags
#
# WHAT THIS DOES
#   For every ConnectCAD Circuit in the active document, places TWO Data Tags:
#     - one at the SOURCE end, reading the DESTINATION's identity
#     - one at the DESTINATION end, reading the SOURCE's identity
#   i.e. each end names the FAR end, which is what was asked for.
#
#   The circuits keep their polyline/rounded geometry. Nothing about the
#   circuits themselves is modified - no Circuit Type change, no arrow stubs.
#
# HOW TO RUN
#   Resource Manager > New Resource > Script > Python.  Paste this whole file.
#   Double-click the script to run.  It is DRY_RUN by default: the first run
#   writes nothing and only tells you what it would do.
#
# PREREQUISITE - you must create two Data Tag styles by hand first.
#   The script refuses to run without them and prints the click-path.
#   See the header comment block "TAG STYLE SETUP" below.
#
# SAFETY
#   - DRY_RUN = True by default. Nothing is written.
#   - Everything is inside one vs.NameUndoEvent, so Cmd-Z reverses it.
#   - The document is never saved. Close without saving to discard entirely.
#   - REMOVE_ALL deletes only tags this script created (identified by class).
# ---------------------------------------------------------------------------
#
# ============================ TAG STYLE SETUP ==============================
#
# Do this once, by hand, before the first real run. Roughly 5 minutes.
#
# 1. Draw a small text object on any design layer. Type any placeholder.
# 2. Select it, then  Modify > ... actually: with it selected, use the
#    Data Tag tool's  "Create Data Tag Style from Shapes"  (Tools menu, or
#    right-click the text). If that route is not offered in your build:
#      a. Place one Data Tag with the Data Tag tool, clicking on any circuit.
#      b. In the Object Info palette click  "Edit Tag Layout...".
#      c. Inside the layout, select the text object.
#      d. In the OIP, tick  "Use dynamic text",  then click
#         "Define Tag Field...".
# 3. In the Define Tag Field dialog:
#      - choose the  "Advanced calculated field"  radio button
#      - Data Source:   Record Format
#      - Format Name:   Circuit
#      - Field Name:    (see table below)
#      - click  "Add to Definition",  then OK.
# 4. Exit the layout. In the OIP use  Styles > "New Plug-in Style from
#    Unstyled Object..."  and give it the style name from the table.
# 5. Repeat for the second style.
#
#   style name                     Field Name        renders, for
#                                                    OG DA - 01 -> DIR.SDI_IN 01
#   -----------------------------  ----------------  -------------------------
#   ShowCAD Far End At Source      Dst_Skt_Name      "SDI_IN 01"
#   ShowCAD Far End At Dest        Src_Dev_Name      "OG DA - 01"
#
# Want the fuller "Device.Socket" form instead? In step 3 add BOTH fields to
# one definition with a literal "." between them:
#   at source:  Dst_Dev_Name . Dst_Skt_Name   ->  "DIR.SDI_IN 01"
#   at dest:    Src_Dev_Name . Src_Skt_Name   ->  "OG DA - 01.<its socket>"
#
# The definition box will show something like  #Circuit#.#Dst_Skt_Name#.
# You do not type that - the Add to Definition button writes it.
#
# WHY THIS IS LIVE, NOT STATIC:
#   Src_*/Dst_* are denormalised fields on the Circuit record. ConnectCAD
#   rewrites them on every circuit recalculation - the calls are
#   UpdateSourceSocketDetails() and UpdateDestinationSocketDetails() inside
#   cCADCircuitObj_EventSink::Recalculate(). So repatching a circuit updates
#   the record, and the Data Tag re-reads the record. No stamped strings.
# ===========================================================================

import json
import os
import traceback

import vs

# ============================== CONFIGURATION ==============================

DRY_RUN    = True      # <- set False to actually write
REMOVE_ALL = False     # <- set True (with DRY_RUN False) to delete our tags

STYLE_AT_SOURCE = 'ShowCAD Far End At Source'
STYLE_AT_DEST   = 'ShowCAD Far End At Dest'

CLASS_AT_SOURCE = 'SHOWCAD-EndLabel-AtSource'
CLASS_AT_DEST   = 'SHOWCAD-EndLabel-AtDest'

# How far in from each end of the circuit to sit the tag, as a fraction of the
# circuit's bounding-box width. Only used by the bbox fallback anchor.
BBOX_INSET = 0.02

# Opt-in. Turns the two classes on in every sheet-layer viewport.
# Left off by default: it edits viewport state on a real project file and
# could not be tested. Do it by hand unless you want the script to try.
SET_VIEWPORT_CLASS_VIS = False

REPORT_PATH = os.path.expanduser('~/showcad_datatag_report.json')

DATA_TAG_PIO   = 'Data Tag'
CIRCUIT_RECORD = 'Circuit'
VIEWPORT_TYPE  = 122

# ===========================================================================


def _fn(name):
    """Return a vs.* function if it exists live, else None.

    DT_IsValid / DT_CreateFromShapes / DT_FixBrokenField are present in the
    running app but absent from vs_index.json, so they must be probed rather
    than called blind.
    """
    return getattr(vs, name, None)


def _pt(value):
    """Normalise whatever GetBBox/HCenter handed back into a plain (x, y)."""
    if value is None:
        return None
    try:
        x, y = value[0], value[1]
        return (float(x), float(y))
    except Exception:
        return None


class Report(object):
    def __init__(self):
        self.mode = ''
        self.circuits_found = 0
        self.circuits_processed = 0
        self.tags_planned = 0
        self.tags_created = 0
        self.tags_verified = 0
        self.tags_deleted = 0
        self.tags_rolled_back = 0
        self.anchor_methods = {}
        self.errors = []
        self.skipped = []
        self.notes = []
        self.viewports = []

    def anchor(self, method):
        self.anchor_methods[method] = self.anchor_methods.get(method, 0) + 1

    def error(self, where, detail):
        if len(self.errors) < 200:
            self.errors.append({'where': where, 'detail': str(detail)[:400]})

    def skip(self, name, why):
        if len(self.skipped) < 200:
            self.skipped.append({'circuit': name, 'why': why})

    def as_dict(self):
        return {
            'mode': self.mode,
            'circuits_found': self.circuits_found,
            'circuits_processed': self.circuits_processed,
            'tags_planned': self.tags_planned,
            'tags_created': self.tags_created,
            'tags_verified': self.tags_verified,
            'tags_deleted': self.tags_deleted,
            'tags_rolled_back': self.tags_rolled_back,
            'anchor_methods': self.anchor_methods,
            'error_count': len(self.errors),
            'errors': self.errors,
            'skipped_count': len(self.skipped),
            'skipped': self.skipped,
            'viewports': self.viewports,
            'notes': self.notes,
        }


REP = Report()


# --------------------------- document traversal ----------------------------

def parametric_name(h):
    try:
        rec = vs.GetParametricRecord(h)
        if rec is None:
            return ''
        return vs.GetName(rec) or ''
    except Exception:
        return ''


def collect(predicate):
    """Two-pass safety: gather handles first, never mutate while traversing."""
    found = []

    def cb(h):
        try:
            if predicate(h):
                found.append(h)
        except Exception as exc:
            REP.error('collect', exc)

    vs.ForEachObject(cb, "(ALL)")
    return found


def collect_circuits():
    return collect(lambda h: parametric_name(h) == CIRCUIT_RECORD)


def collect_our_tags():
    ours = (CLASS_AT_SOURCE, CLASS_AT_DEST)

    def is_ours(h):
        if parametric_name(h) != DATA_TAG_PIO:
            return False
        try:
            return (vs.GetClass(h) or '') in ours
        except Exception:
            return False

    return collect(is_ours)


# ------------------------------- anchoring ---------------------------------

def connector_points(hCircuit):
    """Positions of the CC-Circuit-Connector sub-objects inside a Circuit.

    A sibling measured that the first renders Src_Skt_Conn and the second
    Dst_Skt_Conn, so the order is (source end, destination end).
    """
    pts = []

    def walk(h, depth):
        if h is None or depth > 3 or len(pts) > 8:
            return
        cur = h
        while cur is not None:
            try:
                if (vs.GetClass(cur) or '') == 'CC-Circuit-Connector':
                    p = _pt(vs.HCenter(cur))
                    if p is not None:
                        pts.append(p)
                child = vs.FInGroup(cur)
                if child is not None:
                    walk(child, depth + 1)
            except Exception:
                pass
            try:
                cur = vs.NextObj(cur)
            except Exception:
                cur = None

    try:
        walk(vs.FInGroup(hCircuit), 0)
    except Exception as exc:
        REP.error('connector_points', exc)
    return pts


def bbox_of(h):
    try:
        p1, p2 = vs.GetBBox(h)
        a, b = _pt(p1), _pt(p2)
        if a is None or b is None:
            return None
        return (min(a[0], b[0]), min(a[1], b[1]),
                max(a[0], b[0]), max(a[1], b[1]))
    except Exception:
        return None


def anchors(hCircuit):
    """Return (source_end_pt, dest_end_pt, method) or (None, None, reason)."""
    box = bbox_of(hCircuit)

    # 1. Preferred: the two connector-text loci inside the circuit.
    pts = connector_points(hCircuit)
    if len(pts) >= 2:
        src, dst = pts[0], pts[1]
        if src != dst and _inside(box, src) and _inside(box, dst):
            return src, dst, 'connector_loci'
        # Points outside the circuit's own world bbox mean we read them in the
        # PIO's LOCAL frame. Do not trust them; fall through to the bbox.
        REP.notes.append('connector loci rejected (out of bbox or coincident) '
                         'for one or more circuits - using bbox fallback')

    # 2. Fallback: derive the ends from the bounding box plus Orientation.
    if box is None:
        return None, None, 'no_bbox'
    x0, y0, x1, y1 = box
    width = max(x1 - x0, 1e-9)
    inset = width * BBOX_INSET
    ymid = (y0 + y1) / 2.0
    left = (x0 + inset, ymid)
    right = (x1 - inset, ymid)

    orient = ''
    try:
        orient = (vs.GetRField(hCircuit, CIRCUIT_RECORD, 'Orientation') or '').strip()
    except Exception:
        pass

    if orient.upper() == 'R':
        return right, left, 'bbox_orient_R'
    return left, right, 'bbox_orient_L'


def _inside(box, p, slack=0.10):
    if box is None or p is None:
        return False
    x0, y0, x1, y1 = box
    dx = (x1 - x0) * slack + 1.0
    dy = (y1 - y0) * slack + 1.0
    return (x0 - dx) <= p[0] <= (x1 + dx) and (y0 - dy) <= p[1] <= (y1 + dy)


# ------------------------------ tag placement ------------------------------

def ensure_classes():
    active = ''
    try:
        active = vs.ActiveClass()
    except Exception:
        pass
    for cls in (CLASS_AT_SOURCE, CLASS_AT_DEST):
        try:
            vs.NameClass(cls)          # creates it if absent
            vs.ShowClass(cls)
        except Exception as exc:
            REP.error('ensure_classes:' + cls, exc)
    if active:
        try:
            vs.NameClass(active)       # restore whatever was active
        except Exception:
            pass


def place_tag(hCircuit, pt, style_name, class_name):
    """Create one Data Tag, bind it, and prove the bind. Returns True on success."""
    hTag = None
    try:
        hTag = vs.CreateCustomObjectN(DATA_TAG_PIO, pt, 0, False)
        if hTag is None:
            hTag = vs.LNewObj()
        if hTag is None:
            REP.error('place_tag', 'CreateCustomObjectN returned no handle')
            return False
        REP.tags_created += 1

        vs.SetClass(hTag, class_name)

        if not vs.SetPluginStyle(hTag, style_name):
            REP.error('place_tag', 'SetPluginStyle failed for ' + style_name)
            _rollback(hTag)
            return False

        # THE association. An unasserted bind is the failure mode that renders
        # plausibly while pointing at the wrong object - so assert on it, and
        # delete rather than leave an orphan.
        if not vs.DT_AssociateWithObj(hTag, hCircuit):
            REP.error('place_tag', 'DT_AssociateWithObj returned False')
            _rollback(hTag)
            return False

        vs.ResetObject(hTag)

        # Second, independent check where the app offers one.
        dt_is_valid = _fn('DT_IsValid')
        if dt_is_valid is not None:
            try:
                if not dt_is_valid(hTag):
                    REP.error('place_tag', 'DT_IsValid returned False after associate')
                    _rollback(hTag)
                    return False
            except Exception as exc:
                # Unindexed function, unknown arity - a raise is not a failed
                # association, so note it and keep the tag.
                REP.error('DT_IsValid', exc)
        REP.tags_verified += 1
        return True

    except Exception as exc:
        REP.error('place_tag', traceback.format_exc()[-400:])
        if hTag is not None:
            _rollback(hTag)
        return False


def _rollback(hTag):
    try:
        vs.DelObject(hTag)
        REP.tags_rolled_back += 1
    except Exception as exc:
        REP.error('rollback', exc)


# ------------------------------- operations --------------------------------

def do_remove():
    tags = collect_our_tags()
    REP.mode = 'REMOVE_ALL' + (' (dry run)' if DRY_RUN else '')
    REP.tags_planned = len(tags)
    if DRY_RUN:
        REP.notes.append('DRY RUN: would delete %d tag(s) on classes %s / %s'
                         % (len(tags), CLASS_AT_SOURCE, CLASS_AT_DEST))
        return
    for h in tags:
        try:
            vs.DelObject(h)
            REP.tags_deleted += 1
        except Exception as exc:
            REP.error('do_remove', exc)


def do_place():
    REP.mode = 'PLACE' + (' (dry run)' if DRY_RUN else '')

    circuits = collect_circuits()
    REP.circuits_found = len(circuits)
    if not circuits:
        REP.notes.append('No Circuit objects found. ForEachObject "(ALL)" does '
                         'not reach objects on hidden or greyed layers - check '
                         'layer visibility and re-run.')
        return

    existing = collect_our_tags()
    if existing:
        REP.notes.append('%d tag(s) from a previous run are already present. '
                         'Run with REMOVE_ALL first, or they will be duplicated.'
                         % len(existing))

    if not DRY_RUN:
        ensure_classes()

    # Bulk-move bracket. Exists precisely for batch placement; if it declines,
    # carry on unoptimised rather than abort.
    begin = _fn('DT_BeginMultipleMove')
    end = _fn('DT_EndMultipleMove')
    bulk = False
    if not DRY_RUN and begin is not None:
        try:
            bulk = bool(begin())
        except Exception as exc:
            REP.error('DT_BeginMultipleMove', exc)
        REP.notes.append('DT_BeginMultipleMove: %s' % ('on' if bulk else 'declined'))

    saved_layer = ''
    try:
        saved_layer = vs.GetLName(vs.ActLayer())
    except Exception:
        pass

    try:
        for i, hC in enumerate(circuits):
            if i % 20 == 0:
                try:
                    vs.Message('ShowCAD end labels: circuit %d / %d'
                               % (i + 1, len(circuits)))
                except Exception:
                    pass

            name = ''
            try:
                name = '%s.%s -> %s.%s' % (
                    vs.GetRField(hC, CIRCUIT_RECORD, 'Src_Dev_Name'),
                    vs.GetRField(hC, CIRCUIT_RECORD, 'Src_Skt_Name'),
                    vs.GetRField(hC, CIRCUIT_RECORD, 'Dst_Dev_Name'),
                    vs.GetRField(hC, CIRCUIT_RECORD, 'Dst_Skt_Name'))
            except Exception:
                name = 'circuit#%d' % i

            pSrc, pDst, method = anchors(hC)
            if pSrc is None or pDst is None:
                REP.skip(name, 'no anchor (%s)' % method)
                continue
            REP.anchor(method)
            REP.tags_planned += 2

            if DRY_RUN:
                REP.circuits_processed += 1
                continue

            # Tags must land on the circuit's own design layer.
            try:
                lname = vs.GetLName(vs.GetLayer(hC))
                if lname:
                    vs.Layer(lname)
            except Exception as exc:
                REP.error('set layer', exc)

            ok_a = place_tag(hC, pSrc, STYLE_AT_SOURCE, CLASS_AT_SOURCE)
            ok_b = place_tag(hC, pDst, STYLE_AT_DEST, CLASS_AT_DEST)
            if ok_a and ok_b:
                REP.circuits_processed += 1
            else:
                REP.skip(name, 'one or both tags failed and were rolled back')

    finally:
        if bulk and end is not None:
            try:
                end()
            except Exception as exc:
                REP.error('DT_EndMultipleMove', exc)
        if saved_layer:
            try:
                vs.Layer(saved_layer)
            except Exception:
                pass
        try:
            vs.ClrMessage()
        except Exception:
            pass

    if not DRY_RUN:
        # Documented recovery for tags rendering stale data.
        reset = _fn('DT_ResetAllDataTags')
        if reset is not None:
            try:
                reset()
                REP.notes.append('DT_ResetAllDataTags called')
            except Exception as exc:
                REP.error('DT_ResetAllDataTags', exc)
        handle_viewports()


def handle_viewports():
    """Report - and optionally set - class visibility in sheet viewports."""
    vps = collect(lambda h: vs.GetTypeN(h) == VIEWPORT_TYPE)
    for h in vps:
        entry = {'name': '', 'set': False}
        try:
            entry['name'] = vs.GetName(h) or '(unnamed)'
        except Exception:
            pass
        if SET_VIEWPORT_CLASS_VIS:
            try:
                a = vs.SetVPClassVisibility(h, CLASS_AT_SOURCE, 1)
                b = vs.SetVPClassVisibility(h, CLASS_AT_DEST, 1)
                entry['set'] = bool(a and b)
                if entry['set']:
                    vs.ResetObject(h)
            except Exception as exc:
                REP.error('viewport class vis', exc)
        REP.viewports.append(entry)
    if vps and not SET_VIEWPORT_CLASS_VIS:
        REP.notes.append(
            'Each sheet viewport carries its own class visibility. Turn on '
            '%s and %s in the TA1.1 Schematic viewport (select the viewport > '
            'Classes... > set both visible) or the tags will not print.'
            % (CLASS_AT_SOURCE, CLASS_AT_DEST))


# --------------------------------- entry -----------------------------------

def preflight():
    """Hard stops. Better to refuse than to half-build on a real project file."""
    problems = []

    try:
        if not vs.IsNewCustomObject(DATA_TAG_PIO):
            problems.append('The "%s" plug-in object is not available.' % DATA_TAG_PIO)
    except Exception as exc:
        problems.append('IsNewCustomObject failed: %s' % exc)

    for f in ('DT_AssociateWithObj', 'SetPluginStyle', 'CreateCustomObjectN'):
        if _fn(f) is None:
            problems.append('Missing required function vs.%s' % f)

    if not REMOVE_ALL:
        # Probe the styles by trying them on a throwaway tag we then delete.
        missing = []
        for style in (STYLE_AT_SOURCE, STYLE_AT_DEST):
            probe = None
            try:
                probe = vs.CreateCustomObjectN(DATA_TAG_PIO, (0, 0), 0, False)
                if probe is None:
                    probe = vs.LNewObj()
                if probe is None or not vs.SetPluginStyle(probe, style):
                    missing.append(style)
            except Exception:
                missing.append(style)
            finally:
                if probe is not None:
                    try:
                        vs.DelObject(probe)
                    except Exception:
                        pass
        if missing:
            problems.append(
                'Data Tag style(s) not found: %s\n'
                'Create them first - see TAG STYLE SETUP at the top of this '
                'script.' % ', '.join(missing))
    return problems


def run():
    # Opened first so that the throwaway style-probe object preflight creates
    # (and immediately deletes) is inside the same undoable step.
    vs.NameUndoEvent('ShowCAD circuit end labels')

    problems = preflight()
    if problems:
        REP.mode = 'ABORTED'
        for p in problems:
            REP.error('preflight', p)
        write_report()
        vs.AlrtDialog('ShowCAD end labels - nothing was changed.\n\n'
                      + '\n\n'.join(problems))
        return

    if REMOVE_ALL:
        do_remove()
    else:
        do_place()

    write_report()
    vs.AlrtDialog(summary())


def summary():
    d = REP.as_dict()
    lines = [
        'ShowCAD circuit end labels - %s' % d['mode'],
        '',
        'Circuits found:      %d' % d['circuits_found'],
        'Circuits processed:  %d' % d['circuits_processed'],
        'Tags planned:        %d' % d['tags_planned'],
    ]
    if not DRY_RUN:
        lines += [
            'Tags created:        %d' % d['tags_created'],
            'Tags VERIFIED bound: %d' % d['tags_verified'],
            'Tags rolled back:    %d' % d['tags_rolled_back'],
            'Tags deleted:        %d' % d['tags_deleted'],
        ]
    if d['anchor_methods']:
        lines += ['', 'Anchor source: ' + ', '.join(
            '%s=%d' % (k, v) for k, v in sorted(d['anchor_methods'].items()))]
    lines += ['', 'Errors:  %d' % d['error_count'],
              'Skipped: %d' % d['skipped_count'],
              '', 'Full report:', REPORT_PATH]
    if DRY_RUN:
        lines += ['', 'DRY RUN - nothing was written.',
                  'Set DRY_RUN = False to apply.']
    else:
        lines += ['', 'Not saved. Cmd-Z reverses this, or close without saving.']
    return '\n'.join(lines)


def write_report():
    try:
        with open(REPORT_PATH, 'w') as fh:
            json.dump(REP.as_dict(), fh, indent=2)
    except Exception as exc:
        try:
            vs.AlrtDialog('Could not write report to %s\n%s' % (REPORT_PATH, exc))
        except Exception:
            pass


try:
    run()
except Exception:
    try:
        REP.mode = 'CRASHED'
        REP.error('run', traceback.format_exc()[-1500:])
        write_report()
        vs.AlrtDialog('ShowCAD end labels crashed. See:\n%s' % REPORT_PATH)
    except Exception:
        pass
