# Task Breakdown — Agent Team Plan

Structured so each task is independently assignable to an agent (Claude Code
subagent, teammate, or you). Each task lists: owner role, inputs, outputs,
done-when. Phases are sequential; tasks inside a phase can run in parallel.

## Agent roles

| Role | Charter |
|---|---|
| **Bridge Agent** | Everything between the MCP server and VW: IPC, pump, lifecycle |
| **ConnectCAD Agent** | `cc_*` tools; owns the CC_* API + Device/Circuit/Socket records |
| **Spotlight Agent** | `sl_*` tools; owns Lighting Device / position / Data Tag behavior |
| **QA Agent** | Test documents, tool contract tests, VW-version matrix |
| **Docs Agent** | README, tool reference, install guide, demo GIFs |

---

## Phase 0 — Foundations (this week)

- **T0.1 — Repo + CI skeleton** _(done — this commit)_
- **T0.2 — Dev environment doc** · Bridge Agent
  Document exact install path for the pump on Win
  (`%APPDATA%\Nemetschek\Vectorworks\2026\Plug-ins\ShowCAD-MCP\`) and Mac,
  menu-command registration, hotkey. Done when a clean machine can follow it.
- **T0.3 — License check on prior art** · Docs Agent
  Read vwx-mcp and randneto repos' LICENSE files. Decide: vendor code, or
  clean-room re-implement the pump. Record decision in `docs/DECISIONS.md`.
- **T0.4 — Function reference mirror** · ConnectCAD Agent
  Pull the CC_* pages + relevant generic functions
  (`ForEachObject`, `GetRField`, `SetRField`, `CreateCustomObjectN`,
  `ResetObject`, `NameUndoEvent`) from
  https://github.com/Vectorworks/developer-scripting into
  `docs/vs-index.json` (name, signature, min version, notes).

## Phase 1 — Discovery against a live document

- **T1.1 — Record-format dump script** · Bridge Agent → both domain agents
  One-shot VW script that enumerates every record format + field names/types
  in a document. Run it on: (a) an empty Spotlight doc, (b) a real show file
  (e.g., a tour schematic). Output → `docs/records/*.json`. **This unblocks
  every typed tool.**
- **T1.2 — ConnectCAD object census** · ConnectCAD Agent
  From the dump: field maps for Device, Socket, Circuit, Equipment Item,
  Adapter. Note which fields are writable + need `ResetObject`.
- **T1.3 — Spotlight object census** · Spotlight Agent
  Field maps for Lighting Device, Hanging Position, Data Tag (type 86),
  Cable objects. Verify the tag-association gotcha and the working
  copy/paste-pair workaround.
- **T1.4 — Test show file** · QA Agent
  Build `test-assets/demo-show.vwx`: 10 fixtures on 2 positions, small video
  rack (switcher, 2 processors, 4 panels-as-devices), ~20 circuits, 1
  deliberate unconnected socket, 1 deliberate duplicate channel.

## Phase 2 — Bridge MVP (read-only)

- **T2.1 — File-IPC pump** · Bridge Agent
  `vw-plugin/pump.py` + menu command: drain `ipc/jobs`, execute registered
  command handlers, write `ipc/results`, never raise into VW.
- **T2.2 — FastMCP server** · Bridge Agent
  `mcp-server/server.py`: job submit/await, timeout handling, VW-version
  handshake, tool registry with `min_vw` gating.
- **T2.3 — Read tools, ConnectCAD** · ConnectCAD Agent
  `cc_list_devices`, `cc_get_device` (incl. sockets), `cc_list_circuits`,
  `cc_trace_signal` (walk source→dest chains across adapters using
  `CC_GetCircuitSource/Dest` + `CC_GetDevice`), `cc_audit_unconnected`.
- **T2.4 — Read tools, Spotlight** · Spotlight Agent
  `sl_list_fixtures` (filterable by position/universe), `sl_get_fixture`,
  `sl_patch_report` (channel↔address↔universe↔position table),
  `sl_positions`.
- **T2.5 — Contract tests** · QA Agent
  Golden-output tests of every read tool against `demo-show.vwx`.

**Milestone M1:** From Claude, ask "what's patched to universe 2?" and
"trace the signal path from CAM 1 to the switcher" against the demo file.

## Phase 3 — Writes

- **T3.1 — Undo/save guardrails** · Bridge Agent (blocks all of Phase 3)
- **T3.2 — `cc_create_device` / `cc_connect`** · ConnectCAD Agent
  Create via `CC_DeviceFromShape`/`CC_CircuitFromShape` + record writes;
  `cc_connect(sourceDev, srcSocket, destDev, dstSocket, signal)`.
- **T3.3 — `cc_from_data`** · ConnectCAD Agent
  Bulk generate devices+circuits from JSON/CSV (mirrors the native
  "from worksheet" workflow — this is the killer feature for touring preps).
- **T3.4 — `sl_insert_fixture` / `sl_set_fields`** · Spotlight Agent
  Insert by symbol name at position; batch field edits w/ `ResetObject`;
  tag-pair-safe duplication.
- **T3.5 — Destructive-op review** · QA Agent
  Fuzz bad inputs; confirm one-undo-per-tool-call holds.

**Milestone M2:** Feed a CSV of a video rack → devices + circuits appear in a
schematic; renumber 20 fixtures in one call; single undo reverts each.

## Phase 4 — Polish / stretch

- **T4.1** `x_reconcile_schematic_vs_equipment` (schematic vs rack truth check)
- **T4.2** `x_export_patch_csv`, `cc_cable_schedule` (lengths via routes)
- **T4.3** Native background-write palette (vwx-mcp bridge-v13 style, C++/SDK —
  needs VW SDK + VS2022; mind VW2026 plugin credential files)
- **T4.4** macOS support pass (paths, hotkey posting differences)
- **T4.5** Publish: PulseMCP/LobeHub listings, forum announcement post in
  https://forum.vectorworks.net/topic/134256-official-model-context-protocol/

## Suggested first sprint (solo or 2 agents)

1. T0.2, T0.3, T1.1, T1.4  → you have data + a sandbox
2. T2.1 + T2.2             → bridge alive
3. T2.3 (just `cc_list_devices` + `cc_trace_signal`) → first demo
