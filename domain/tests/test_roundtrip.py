"""End-to-end round trip: server _dispatch -> ipc/jobs -> pump -> ipc/results.
Run: python tests/test_roundtrip.py  (no VW needed; uses tests/mock_vs.py)"""
import json, sys, threading, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "vw-plugin"), str(ROOT / "tests"), str(ROOT / "mcp-server")]

import mock_vs
import pump
pump.set_vs(mock_vs)

import server  # uses same ~/showcad-ipc dirs as pump

STOP = False
def pump_loop():
    while not STOP:
        pump.pump_all()
        time.sleep(0.05)

t = threading.Thread(target=pump_loop, daemon=True); t.start()

def show(title, data):
    print(f"\n=== {title} ===")
    print(json.dumps(data, indent=2)[:1600])

checks = []
def check(name, cond):
    checks.append((name, cond))
    print(("PASS " if cond else "FAIL ") + name)

d = server._dispatch("doc_info")
show("doc_info", d)
check("doc_info returns demo file + 3 layers", d["file"] == "demo-show.vwx" and len(d["layers"]) == 3)

devs = server._dispatch("cc_list_devices")
check(f"cc_list_devices -> {len(devs)} devices", len(devs) == 6)

cirs = server._dispatch("cc_list_circuits", {"device": "E2 FRAME"})
show("cc_list_circuits(device='E2 FRAME')", cirs)
check("E2 FRAME touches 4 circuits", len(cirs) == 4)

trace = server._dispatch("cc_trace_signal", {"device": "CAM 1"})
show("cc_trace_signal(CAM 1)", trace)
check("CAM 1 reaches XD 1 through E2 + SX40",
      "XD 1" in trace["devices_reached"] and len(trace["hops"]) == 3)

audit = server._dispatch("cc_audit_unconnected")
show("cc_audit_unconnected", audit)
unconn = [i for i in audit if i["kind"] == "unconnected_socket"]
check("audit flags SRV 1 / DP OUT 2 among unconnected",
      any(i["device"] == "SRV 1" and i["socket"] == "DP OUT 2" for i in unconn))

fx = server._dispatch("sl_list_fixtures", {"universe": "2"})
check(f"sl_list_fixtures(universe=2) -> {len(fx)} fixtures", len(fx) == 6)

patch = server._dispatch("sl_patch_report")
dups = [r for r in patch if r["flags"]]
show("sl_patch_report — flagged rows", dups)
check("patch report flags duplicate channel 101",
      any("duplicate channel" in f for r in dups for f in r["flags"]))

STOP = True
fails = [n for n, ok in checks if not ok]
print(f"\n{'ALL ' + str(len(checks)) + ' CHECKS PASSED' if not fails else 'FAILED: ' + ', '.join(fails)}")
sys.exit(1 if fails else 0)
