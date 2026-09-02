# Research Findings — Spotlight/ConnectCAD MCP

_Compiled 2026-09-01. Every claim carries its source link._

## 1. Landscape: what exists, what doesn't

| Project | Scope | Platform | Link |
|---|---|---|---|
| **Official Vectorworks MCP** | Does not exist; open forum request, no first-party reply | — | https://forum.vectorworks.net/topic/134256-official-model-context-protocol/ |
| **vicquick/vwx-mcp** | VW 2026, 248 tools, 3071-signature `vs.*` knowledge index, background writes via native C++ palette + file IPC | Windows | https://github.com/vicquick/vwx-mcp |
| — its roadmap | Explicitly skips Spotlight/Truss/ConnectCAD ("out of domain") | | https://github.com/vicquick/vwx-mcp/blob/main/docs/ROADMAP.md |
| **mako-357/vectorworks-mcp** | Rust server + C++ SDK plugin over Unix socket; VW 2025+; requires building SDK plugin | macOS | https://github.com/mako-357/vectorworks-mcp |
| **randneto-lab/vwx-mpc-server-plugin** | Codex packaging of the file-IPC workflow, VW 2026; documents modeling limits | Windows | https://github.com/randneto-lab/vwx-mpc-server-plugin |

**Conclusion:** the entertainment domain (Spotlight + ConnectCAD) is unclaimed.
The transport problem is already solved twice over — we should reuse the
file-IPC pattern and spend our effort on the domain toolset.

## 2. ConnectCAD scripting surface

Dedicated `vs.CC_*` functions (introduced VW 2022, expanded through 2025.2).
Full reference: https://www.vectorworks.co.jp/develop/ScriptReference/Pages/ConnectCAD.html

| Function | Since | What it does |
|---|---|---|
| `CC_CircuitFromShape(h)` | 2022 | Line/poly → circuit; returns circuit handle |
| `CC_DeviceFromShape(h)` | 2022 | Rect/poly → device; returns device handle |
| `CC_RouteFromShape(h)` | 2022 | Poly/3D poly → cable path |
| `CC_RoomFromShape(h)` | 2022.3 | Shape → layout room |
| `CC_GetCircuitSource(h)` | 2025 | → (device, devSocket, adapter, socket) handles |
| `CC_GetCircuitDest(h)` | 2025 | → (device, devSocket, adapter, socket) handles |
| `CC_GetDevice(hSocket, skipAdapters)` | 2025 | Socket → parent device |
| `CC_GetEquipmentItem(hDevice)` | 2025 | Device → associated equipment item |
| `CC_GetSignalData(sig, col)` | 2025.2 | Signal table: 1=Prefix 2=Connector 3=Description |
| `CC_GetCableTypeData(ct, col)` | 2025.2 | Cable table: 1=Description 2=OD |
| `CC_GetConnectorData(cn, col)` | 2025.2 | Connector table: 1=Description 2=Panel symbol |
| `CC_ReloadData()` | 2023.4 | Reload device DB, signal/connector/cable tables |
| `CC_OnFindAndReplace(h, field, val)` | 2023.6 | Find/replace on ConnectCAD objects |

Everything else (device name, socket names, circuit number, cable type on a
specific circuit, etc.) is **record-format access on the PIOs** — read/write via
`GetRField`/`SetRField` + `ResetObject`, enumerate via `ForEachObject` criteria.

ConnectCAD data model (per official docs):
- Circuits have exactly one **source** (output/IO socket) and one
  **destination** (input/IO socket); direction mirrors signal flow.
  https://app-help.vectorworks.net/2024/eng/VW2024_Guide/ConnectCAD/Creating_circuits.htm
- Devices = groups of sockets w/ label + graphics; device definition record can
  attach to Spotlight 3D symbols so they act as ConnectCAD devices.
  https://app-help.vectorworks.net/2026/eng/VW2026_Guide/ConnectCAD/Concept_ConnectCAD_devices.htm
- Circuit params editable from Object Info palette (= record fields).
  https://app-help.vectorworks.net/2024/eng/VW2024_Guide/ConnectCAD/Editing_circuits1.htm
- "Create circuits/devices from worksheet" exists natively → confirms
  data-driven generation is a sanctioned workflow we can mirror via MCP.
- Spotlight **cable objects can associate with ConnectCAD circuits**; Spotlight
  and ConnectCAD are integrated by design.
  https://app-help.vectorworks.net/2025/eng/VW2025_Guide/ConnectCAD/ConnectCAD.htm

## 3. Spotlight scripting surface

- No `SL_*` family; Lighting Device is a PIO with a rich record
  ("Lighting Device" format: Channel, Unit Number, Dimmer/Address, Universe,
  Position, Purpose, Color, Fixture Mode, etc.). Manipulated with generic
  `vs.*` calls. Official scripting home:
  https://github.com/Vectorworks/developer-scripting
  (Python + VectorScript; function reference lives in
  `Function Reference/` in that repo).
- Community-proven patterns exist for inserting/duplicating Lighting Devices
  from data via Python:
  https://forum.vectorworks.net/index.php?%2Ftopic%2F106507-spotlight-insert-a-lighting-device%2F=
- Known gotcha from the forum: duplicating a Lighting Device and its Data Tag
  separately via `HDuplicate` **breaks the tag association** (Data Tag = type 86;
  association is not preserved). Copy/paste as a pair preserves it. Must handle
  in our duplicate/insert tools.
  https://forum.vectorworks.net/forum/45-python-scripting/

## 4. Platform constraints

- VW 2026: encrypted script plugins + SDK plugins need a **credentials file**
  identifying the developer; plain script plugins are exempt.
  https://github.com/Vectorworks/developer-scripting and
  https://github.com/VectorworksDeveloper/SDKExamples
- Document mutation is only safe from VW's own script-runner context — the
  reason every working bridge routes writes through a menu-command pump
  (vwx-mcp ARCHITECTURE, randneto README).
- randneto documents modeling limits worth inheriting as warnings in tool
  descriptions (e.g., scripted wall joins ≠ manual tool behavior — analogous
  risks likely exist for scripted circuit routing vs. Connect tool).

## 5. Design implications

1. **Reuse, don't reinvent, the bridge.** File-IPC + in-VW Python pump.
   Verify vwx-mcp license before copying code (Task 0.3); otherwise re-implement
   the pattern cleanly (it's small).
2. **Two tool layers:**
   - typed domain tools (`cc_list_devices`, `sl_patch_report`, …) built on
     `CC_*` + record access;
   - a guarded `run_vs` escape hatch for anything unmapped.
3. **Record-format discovery is Phase 1's real work.** The exact field names of
   "Lighting Device", "Device", "Socket", "Circuit", "Equipment Item" records
   must be dumped from a live document (script: enumerate record formats +
   fields) — they are versioned and not fully documented publicly.
4. **Read-only first.** Query/trace/report tools ship before any mutation tools;
   mutation tools always run against a saved document and name their undo event.
