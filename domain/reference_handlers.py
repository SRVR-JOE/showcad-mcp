"""ShowCAD Bridge pump — runs INSIDE Vectorworks (Python menu command).

Drains ipc/jobs/*.json, executes handlers with the `vs` module, writes
ipc/results/<cid>.json. Exceptions never escape into VW.

Field names marked TBV (to be verified) come from public docs/forum patterns
and must be confirmed against a real document dump (docs/TASKS.md T1.1-T1.3).
Outside VW, tests inject tests/mock_vs.py in place of `vs`.
"""
import json
import traceback
from pathlib import Path

try:
    import vs  # only exists inside Vectorworks
except ImportError:
    vs = None  # tests inject a mock via set_vs()

IPC_ROOT = Path.home() / "showcad-ipc"
JOBS = IPC_ROOT / "jobs"
RESULTS = IPC_ROOT / "results"

HANDLERS = {}


def set_vs(module):
    """Test hook: inject a mock vs module."""
    global vs
    vs = module


def handler(name):
    def deco(fn):
        HANDLERS[name] = fn
        return fn
    return deco


# ── shared record helpers ───────────────────────────────────────────────────
def _collect(pon):
    """All objects whose plug-in object name is `pon`."""
    out = []
    vs.ForEachObject(out.append, f"PON='{pon}'")
    return out


def _rf(h, record, field):
    return vs.GetRField(h, record, field)


# ── document ────────────────────────────────────────────────────────────────
@handler("doc_info")
def doc_info(args):
    layers = []
    h = vs.FLayer()
    while h:
        layers.append(vs.GetLName(h))
        h = vs.NextLayer(h)
    ver = vs.GetVersionEx()
    return {"file": vs.GetFName(), "path": vs.GetFPathName(),
            "vw_version_internal": ver[0], "layers": layers}


# ── ConnectCAD read tools ───────────────────────────────────────────────────
DEV_REC, CIR_REC, SKT_REC = "Device", "Circuit", "Socket"  # record names TBV (T1.2)


def _device_summary(h):
    return {
        "name": _rf(h, DEV_REC, "Name"),            # TBV
        "make": _rf(h, DEV_REC, "Make"),            # TBV
        "model": _rf(h, DEV_REC, "Model"),          # TBV
        "layer": vs.GetLName(vs.GetLayer(h)),
        "sockets": [{"name": _rf(s, SKT_REC, "Name"),        # TBV
                     "dir": _rf(s, SKT_REC, "Direction")}    # TBV
                    for s in vs.CC_DeviceSockets(h)],  # helper: real impl walks container (T2.3)
    }


@handler("cc_list_devices")
def cc_list_devices(args):
    devs = _collect(DEV_REC)
    if args.get("layer"):
        devs = [h for h in devs if vs.GetLName(vs.GetLayer(h)) == args["layer"]]
    return [_device_summary(h) for h in devs]


def _circuit_summary(h):
    s_dev, s_dskt, s_ad, s_skt = vs.CC_GetCircuitSource(h)
    d_dev, d_dskt, d_ad, d_skt = vs.CC_GetCircuitDest(h)
    return {
        "number": _rf(h, CIR_REC, "Number"),        # TBV
        "signal": _rf(h, CIR_REC, "Signal"),        # TBV
        "cable_type": _rf(h, CIR_REC, "Cable Type"),  # TBV
        "src_device": _rf(s_dev, DEV_REC, "Name") if s_dev else None,
        "src_socket": _rf(s_skt, SKT_REC, "Name") if s_skt else None,
        "dst_device": _rf(d_dev, DEV_REC, "Name") if d_dev else None,
        "dst_socket": _rf(d_skt, SKT_REC, "Name") if d_skt else None,
    }


@handler("cc_list_circuits")
def cc_list_circuits(args):
    rows = [_circuit_summary(h) for h in _collect(CIR_REC)]
    dev = args.get("device")
    if dev:
        rows = [r for r in rows if dev in (r["src_device"], r["dst_device"])]
    return rows


@handler("cc_trace_signal")
def cc_trace_signal(args):
    """Walk circuits downstream from a device (optionally one socket)."""
    start, only_skt = args["device"], args.get("socket")
    circuits = [_circuit_summary(h) for h in _collect(CIR_REC)]
    hops, seen, frontier = [], set(), {start}
    for _ in range(32):  # depth guard
        nxt = set()
        for c in circuits:
            if c["src_device"] in frontier and c["dst_device"]:
                if c["src_device"] == start and only_skt and c["src_socket"] != only_skt:
                    continue
                key = (c["src_device"], c["src_socket"], c["dst_device"], c["dst_socket"])
                if key in seen:
                    continue
                seen.add(key)
                hops.append(c)
                nxt.add(c["dst_device"])
        if not nxt:
            break
        frontier = nxt
    return {"start": start, "hops": hops,
            "devices_reached": sorted({h["dst_device"] for h in hops})}


@handler("cc_audit_unconnected")
def cc_audit_unconnected(args):
    issues = []
    connected = set()
    for h in _collect(CIR_REC):
        c = _circuit_summary(h)
        if not c["src_device"] or not c["dst_device"]:
            issues.append({"kind": "dangling_circuit", **c})
        connected.add((c["src_device"], c["src_socket"]))
        connected.add((c["dst_device"], c["dst_socket"]))
    for d in _collect(DEV_REC):
        ds = _device_summary(d)
        for s in ds["sockets"]:
            if (ds["name"], s["name"]) not in connected:
                issues.append({"kind": "unconnected_socket",
                               "device": ds["name"], "socket": s["name"],
                               "dir": s["dir"]})
    return issues


# ── Spotlight read tools ────────────────────────────────────────────────────
LD_REC = "Lighting Device"  # field names TBV (T1.3)


def _fixture_summary(h):
    f = lambda fld: _rf(h, LD_REC, fld)
    return {"channel": f("Channel"), "unit": f("Unit Number"),
            "address": f("Address"), "universe": f("Universe"),
            "position": f("Position"), "purpose": f("Purpose"),
            "symbol": f("Symbol Name")}


@handler("sl_list_fixtures")
def sl_list_fixtures(args):
    rows = [_fixture_summary(h) for h in _collect(LD_REC)]
    if args.get("position"):
        rows = [r for r in rows if r["position"] == args["position"]]
    if args.get("universe"):
        rows = [r for r in rows if str(r["universe"]) == str(args["universe"])]
    return rows


@handler("sl_patch_report")
def sl_patch_report(args):
    rows = [_fixture_summary(h) for h in _collect(LD_REC)]
    ch_seen, ad_seen = {}, {}
    for r in rows:
        r["flags"] = []
        if r["channel"] in ch_seen:
            r["flags"].append(f"duplicate channel with {ch_seen[r['channel']]}")
        ch_seen.setdefault(r["channel"], r["unit"])
        key = (r["universe"], r["address"])
        if key in ad_seen:
            r["flags"].append(f"duplicate address with {ad_seen[key]}")
        ad_seen.setdefault(key, r["unit"])
    return rows


@handler("vs_run")
def vs_run(args):
    scope = {"vs": vs, "result": None}
    exec(args["src"], scope)
    return {"result": scope.get("result")}


# ── pump loop ───────────────────────────────────────────────────────────────
def pump_all():
    JOBS.mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(parents=True, exist_ok=True)
    n = 0
    for job_file in sorted(JOBS.glob("*.json")):
        try:
            job = json.loads(job_file.read_text())
        except Exception:
            job_file.unlink(missing_ok=True)
            continue
        cid = job.get("cid", job_file.stem)
        out = RESULTS / f"{cid}.json"
        try:
            fn = HANDLERS.get(job["cmd"])
            if fn is None:
                payload = {"cid": cid, "ok": False,
                           "error": f"unknown cmd {job['cmd']!r}"}
            else:
                payload = {"cid": cid, "ok": True,
                           "data": fn(job.get("args") or {})}
        except Exception as e:
            payload = {"cid": cid, "ok": False, "error": str(e),
                       "trace": traceback.format_exc()}
        tmp = out.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload))
        tmp.rename(out)
        job_file.unlink(missing_ok=True)
        n += 1
    return n


if __name__ == "__main__" and vs is not None:
    pump_all()
