"""showcad-mcp — FastMCP server for Vectorworks Spotlight + ConnectCAD.

Runs OUTSIDE Vectorworks. Serializes tool calls into file-IPC jobs consumed
by the in-VW pump (vw-plugin/pump.py). See docs/ARCHITECTURE.md.

Status: Phase 2 skeleton (T2.2). Transport works end-to-end once the pump
exists; tools below are the read-only MVP surface with stub wiring.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path

from fastmcp import FastMCP

IPC_ROOT = Path(os.environ.get("SHOWCAD_IPC", Path.home() / "showcad-ipc"))
JOBS = IPC_ROOT / "jobs"
RESULTS = IPC_ROOT / "results"
TIMEOUT_S = float(os.environ.get("SHOWCAD_TIMEOUT", "30"))
ALLOW_RAW = os.environ.get("SHOWCAD_ALLOW_RAW") == "1"

mcp = FastMCP("showcad-mcp")


def _dispatch(cmd: str, args: dict | None = None) -> dict:
    """Write a job file, await the matching result file from the VW pump."""
    JOBS.mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(parents=True, exist_ok=True)
    cid = uuid.uuid4().hex
    job = JOBS / f"{cid}.json"
    tmp = job.with_suffix(".tmp")
    tmp.write_text(json.dumps({"cid": cid, "cmd": cmd, "args": args or {}}))
    tmp.rename(job)  # atomic hand-off

    result = RESULTS / f"{cid}.json"
    deadline = time.monotonic() + TIMEOUT_S
    while time.monotonic() < deadline:
        if result.exists():
            payload = json.loads(result.read_text())
            result.unlink(missing_ok=True)
            if not payload.get("ok"):
                raise RuntimeError(payload.get("error", "VW-side error"))
            return payload["data"]
        time.sleep(0.1)
    raise TimeoutError(
        f"No response from Vectorworks in {TIMEOUT_S}s. Is the "
        "'ShowCAD Bridge Start' menu command running inside VW?"
    )


# ── document ────────────────────────────────────────────────────────────────
@mcp.tool()
def doc_info() -> dict:
    """Active document name, path, VW version, dirty state, layer list.
    Read-only. min_vw: 2025."""
    return _dispatch("doc_info")


# ── ConnectCAD (read) ───────────────────────────────────────────────────────
@mcp.tool()
def cc_list_devices(layer: str | None = None) -> list[dict]:
    """List ConnectCAD devices (name, make/model, layer, socket count).
    Read-only. min_vw: 2025."""
    return _dispatch("cc_list_devices", {"layer": layer})


@mcp.tool()
def cc_list_circuits(device: str | None = None) -> list[dict]:
    """List circuits (number, signal, cable type, source dev/socket,
    dest dev/socket). Optional filter to circuits touching `device`.
    Read-only. min_vw: 2025 (uses CC_GetCircuitSource/Dest)."""
    return _dispatch("cc_list_circuits", {"device": device})


@mcp.tool()
def cc_trace_signal(device: str, socket: str | None = None) -> dict:
    """Trace signal flow downstream from a device (optionally one socket),
    walking circuits source→destination across adapters.
    Read-only. min_vw: 2025."""
    return _dispatch("cc_trace_signal", {"device": device, "socket": socket})


@mcp.tool()
def cc_audit_unconnected() -> list[dict]:
    """Report sockets with no circuit and circuits with a missing endpoint.
    Read-only. min_vw: 2025."""
    return _dispatch("cc_audit_unconnected")


# ── Spotlight (read) ────────────────────────────────────────────────────────
@mcp.tool()
def sl_list_fixtures(position: str | None = None,
                     universe: str | None = None) -> list[dict]:
    """List Lighting Devices (channel, unit, address, universe, position,
    purpose, symbol). Filterable by position or universe.
    Read-only. min_vw: 2025."""
    return _dispatch("sl_list_fixtures",
                     {"position": position, "universe": universe})


@mcp.tool()
def sl_patch_report() -> list[dict]:
    """Full patch table: channel ↔ address ↔ universe ↔ position ↔ fixture.
    Flags duplicate channels/addresses. Read-only. min_vw: 2025."""
    return _dispatch("sl_patch_report")


# ── escape hatch ────────────────────────────────────────────────────────────
@mcp.tool()
def vs_run(python_source: str) -> dict:
    """Run raw Python (vs.* available) inside Vectorworks. DISABLED unless
    SHOWCAD_ALLOW_RAW=1. Mutations must be wrapped in vs.NameUndoEvent by
    the caller. Use only for operations no typed tool covers."""
    if not ALLOW_RAW:
        raise PermissionError("vs_run disabled; set SHOWCAD_ALLOW_RAW=1")
    return _dispatch("vs_run", {"src": python_source})


if __name__ == "__main__":
    mcp.run()
