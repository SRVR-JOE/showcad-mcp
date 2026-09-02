# Architecture

## Transport chain

```
┌──────────────────────────────┐
│ MCP client                   │  Claude Code / Claude Desktop / claude.ai
└──────────────┬───────────────┘
               │ streamable-http :8083  (stdio also supported)
┌──────────────▼───────────────┐
│ mcp-server/ (Python FastMCP) │  runs OUTSIDE Vectorworks
│  - tool registry             │
│  - job serializer            │
└──────────────┬───────────────┘
               │ file IPC
               │   ipc/jobs/<cid>.json      (request)
               │   ipc/results/<cid>.json   (response)
┌──────────────▼───────────────┐
│ vw-plugin/ pump              │  Python menu command INSIDE Vectorworks
│  "ShowCAD Bridge Start"      │  drains job queue, executes vs.* calls,
│  (hotkey e.g. Ctrl+Shift+M)  │  writes results
└──────────────┬───────────────┘
               │ vs.* API
┌──────────────▼───────────────┐
│ Vectorworks 2025/2026        │  Spotlight + ConnectCAD document
└──────────────────────────────┘
```

Why file IPC and not a socket: mutation is only safe inside VW's script runner;
the file queue decouples the server's lifetime from VW's, survives VW crashes,
needs no SDK build for v1, and is the pattern proven by vwx-mcp and
randneto-lab (links in RESEARCH.md). A native C++ palette for true background
writes (vwx-mcp bridge v13 style) is a Phase 4 upgrade, not a prerequisite.

## Tool namespaces

| Prefix | Domain | Examples |
|---|---|---|
| `doc_`  | document | `doc_info`, `doc_layers`, `doc_record_formats`, `doc_save` |
| `cc_`   | ConnectCAD | `cc_list_devices`, `cc_get_device`, `cc_list_circuits`, `cc_trace_signal`, `cc_create_device`, `cc_connect`, `cc_audit_unconnected`, `cc_cable_schedule` |
| `sl_`   | Spotlight | `sl_list_fixtures`, `sl_get_fixture`, `sl_patch_report`, `sl_insert_fixture`, `sl_set_fields`, `sl_positions` |
| `x_`    | cross-domain | `x_reconcile_schematic_vs_equipment`, `x_export_patch_csv` |
| `vs_`   | escape hatch | `vs_run` (guarded raw script), `vs_lookup` (function index) |

## Safety model

1. **Read tools** run freely.
2. **Write tools** require the document to be saved first (pump checks
   `vs.GetFName` + dirty state) and wrap work in a named undo event
   (`vs.NameUndoEvent`) so every MCP mutation is one Cmd+Z.
3. `vs_run` is off by default; enabled with `SHOWCAD_ALLOW_RAW=1`.
4. Data Tag rule: fixture duplication tools must move device+tag as a pair
   (see RESEARCH.md §3 gotcha).

## Record access pattern (core primitive)

```python
# enumerate all Lighting Devices
vs.ForEachObject(cb, "PON='Lighting Device'")
# read/write a field
vs.GetRField(h, 'Lighting Device', 'Channel')
vs.SetRField(h, 'Lighting Device', 'Channel', '101'); vs.ResetObject(h)
```

Same pattern with `'Device'`, `'Circuit'`, `'Socket'`, `'Equipment Item'` for
ConnectCAD, layered under typed tools. Exact field names come from the
Phase 1 record dump (docs/TASKS.md → T1.1).

## Versioning targets

- Primary: **Vectorworks 2026** (Windows), where the CC_* set is complete.
- `CC_GetCircuitSource/Dest`, `CC_GetDevice`, `CC_GetEquipmentItem` need
  **2025+**; table getters need **2025.2+**. Tools declare a `min_vw` and the
  pump reports VW version at startup so the server can hide unsupported tools.
