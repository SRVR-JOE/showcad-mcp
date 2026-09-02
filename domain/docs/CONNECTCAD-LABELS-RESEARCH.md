# ConnectCAD circuit-end labels — official documentation research

Research date: 2026-09-02. Target: Vectorworks 2026 (31.7.0), ConnectCAD.

Question: how do you make each end of a circuit display the **far-end** device and socket name,
so that for `OG DA - 01 -> DIR.SDI_IN 01` the destination end reads `OG DA - 01` and the source
end reads `SDI_IN 01`, replacing the cable-type / connector text currently drawn there?

Everything below is tagged **[DOC]** (the documentation says this, with a URL), **[FORUM]** (a
Vectorworks employee or MVP said this on the official community board), or **[INFER]** (my
reasoning from the above — not stated anywhere).

---

## 1. Direct answer

**The mechanism is `Edit Circuit Graphics` → Arrow Text Formula, with the unqualified tokens
`#Circuit.Device Tag#` and `#Circuit.Socket Name#`, on circuits whose Circuit Type is `Arrow`.**

The text currently at the circuit ends is the **connector-type label**, and it is a separate
thing from the arrow/bubble label. It is drawn in the class **`CC-Circuit-Connector`** and
positioned by **ConnectCAD Settings → General Settings → Circuit Label Offset → Connector Type
Offset**. Turning that class off removes it. That part is a genuine one-click answer.

The far-end-name part is **not documented**. The tokens are known only from a forum thread; the
help does not enumerate the Insert Field list at all, and never states whether the formula
resolves per end. See §4 for the verdict.

### UI click-path — do this by hand right now

**(a) Get rid of the connector text at the circuit ends** — documented, safe, reversible:

- `Tools > Organization > Classes` (or the Navigation palette), find **`CC-Circuit-Connector`**,
  and turn its visibility off (or set it invisible in the viewport's class overrides so the
  design layer is unaffected).
- Alternative, if you want it moved rather than hidden: `ConnectCAD > ConnectCAD Settings >
  General Settings > Circuit Label Offset > Connector Type Offset (Grid Spaces)`.

**(b) Put a far-end label at the circuit ends:**

- Whole drawing / default: `ConnectCAD > ConnectCAD Settings`, **General Settings** pane, click
  **Edit Default Circuit Graphics**.
- One circuit (or a selection): right-click the circuit → **Edit Circuit Graphics**.
- In the dialog: tick **Customize arrow**, then build the **Arrow Text Formula** from the
  **Insert Field** picker. The formula the forum shows for device + socket is:

  ```
  #Circuit.Device Tag# #Circuit.Socket Name#
  ```

  Watch the **Preview** pane — it renders the formula live, which is the fastest way to settle
  the per-end question empirically without any reverse engineering.
- **The arrow graphics only draw when the circuit's `Circuit Type` is `Arrow`.** With 220
  polyline circuits, nothing will appear until you change Circuit Type (OIP → `Circuit Type`, or
  Connect tool → Arrow mode). This is the single biggest gotcha and it is documented.

---

## 2. What the documentation states

### 2.1 The Edit Circuit Graphics dialog — [DOC], verbatim

Source: <https://app-help.vectorworks.net/2026/eng/VW2026_Guide/ConnectCAD/Customizing_ConnectCAD_objects.htm>
(section "Customizing circuit graphics")

> The appearance of a selected circuit, or the default appearance of all circuits, can be set from
> the Edit Circuit Graphics dialog box. **Arrow circuits are circuits created with the Arrow mode
> of the Connect tool.**
>
> To set the default appearance of all circuits, select ConnectCAD > ConnectCAD Settings. On the
> General Settings pane, click Edit Default Circuit Graphics.
>
> To set the appearance of an existing circuit, right-click on the circuit and select Edit Circuit
> Graphics from the context menu.

The full parameter table, verbatim:

| Parameter | Description |
| --- | --- |
| Customize arrow/Customize bubble | Enables the customization; to use the default, deselect the option |
| Arrow Text Formula/Bubble Text Formula | As fields are selected from Insert Field, the formula is created; the results display in the Preview. Add text to the formula if needed. **Even if the formula occupies more than one line, the resulting display is always on one line.** |
| Insert Field | Select the parameter or record value to display in the circuit; **the layer option is useful for arrow circuits** |
| Arrow Style/Bubble Style | Select the arrow or bubble style |
| Preview | Displays the results of the selected formula and style |

And:

> From the Insert Field list, select a field to display on the circuit arrow or in the bubble. The
> formula displays in the Arrow Text Formula or Bubble Text Formula, where it can be edited. Build
> up the formula by selecting items from the Insert Field list. **In addition to default Circuit
> parameters, you can select from custom record formats that are saved in the file**; if the
> custom record is attached to the circuit, its data displays.

**This confirms the dialog exists exactly as described in the brief** — Customize checkbox,
Text Formula field, Insert Field picker, live Preview, and an Arrow Style popup.

**What the documentation does NOT do:** it never enumerates the Insert Field list, never gives the
token syntax, and never says how a formula behaves at the two ends of one circuit. That is a
documented gap, not something I failed to find. I checked the 2022, 2024, 2025 and 2026 editions
of this page and the Dutch/Polish/Portuguese mirrors; the table is identical and equally thin in
all of them.

Marketing page confirming the same, and adding one detail — Vectorworks newsroom,
"Personalize Your AV Workflows with ConnectCAD"
<https://www.vectorworks.net/en-US/newsroom/personalize-your-av-workflows-with-connectcad>:

> [Edit Default Circuit Graphics] allows you to edit the default arrow shapes and bubble graphics,
> **found at the beginning and end of every connection**, as well as what information is placed
> next to these arrows.

and it states explicitly that **the circuit type must be set to Arrow for arrows to be visible.**

### 2.2 The formula token syntax — [FORUM], not [DOC]

Source: "Edit Circuit Graphics Formula?", forum.vectorworks.net topic 92229, Feb 2022
<https://forum.vectorworks.net/index.php?/topic/92229-edit-circuit-graphics-formula/>

The original poster (aheininen) asks:

> "Does Edit Circuit Graphics Arrow Text Formula support use of formulas? Like if I like to show
> different value if destination is Control panel object or device."

and shows these Arrow Text Formula strings:

```
#Circuit.Device Tag# #Circuit.Socket Name#
#Circuit.Device Tag#
```

He reports that `#Circuit.Device Tag# #Circuit.Socket Name#` "created duplicates" for his control
panels, and that `#Circuit.Device Tag#` alone "omitted source information". Conrad Preen (the
original author of ConnectCAD) answered with a working formula posted as a **screenshot**, which
is why the conditional syntax is not recoverable as text. aheininen confirmed: "That does work
like. Thanks again Conrad."

**Syntax established: `#Circuit.<Field Name>#`, hash-delimited, dotted object.field, with a space
in the field name, and literal text may be interleaved.**

Note carefully what the token names are **not**: they carry **no `Src_`/`Dst_` qualifier**. That
matters for §4.

A second thread, "Circuit Graphics Formula", topic 131675
<https://forum.vectorworks.net/index.php?/topic/131675-circuit-graphics-formula/>, has Nikolay
Zhelyazkov (Vectorworks) stating two important rules:

> "Linked text and circuit graphics in ConnectCAD are **not** using the Data Tag syntax"

> "For circuit graphics if you specify a record it will **first look for it in the circuit and then
> in the associated sockets/devices**."

That second sentence is the closest thing to an official statement of resolution order that
exists. It says circuit graphics formulas **do** reach through to the sockets and devices at the
circuit's ends — it does not say which end.

The same thread confirms Data Tag syntax such as
`#WS_OBJECTDATA('eval circuit destination socket', 'Record', 'field')#` **works in Data Tags but
fails in Circuit Graphics**. Do not try to use it in the Arrow Text Formula.

### 2.3 A separate, absolute field vocabulary exists — for cable numbering only

Source: <https://app-help.vectorworks.net/2026/eng/VW2026_Guide/ConnectCAD/Cable_numbering_rules.htm>

> Each condition allows the selection of a parameter (**including combinations of source,
> destination, socket, device, name**, and more options selected from the list) and a prefix value
> or text that you enter. ... For example, a Parameter of **`Src_Dev_Name`** and Prefix of `?DA`
> searches for source device names that begin with any character plus DA

> for a matching condition 1 (**`Src_Dev_Name`** of `?JF_`) that results in `VJF_A` and a matching
> condition 2 (**`Src_Skt_Name`** of `PORT`) ...

> `%L` means layer name

So ConnectCAD **does** have an absolute `Src_*` / `Dst_*` parameter vocabulary — but it is
documented only for the **Cable Numbering Rules** subsystem (`ConnectCAD Settings > Numbering >
Edit > Edit as text`), which produces the circuit **Number**, not the arrow label. It is a
different engine with a different syntax (`^`, `&`, `=`, `%`, `#`, `$`, `?`, `%s`, `%g`, `%u`, `%L`).

**[INFER]** Do not assume `Src_Dev_Name` works in the Arrow Text Formula. Nothing documents it
there, and the arrow tokens found in the wild are the unqualified `#Circuit.Device Tag#` form.

### 2.4 `ShowEnd` — [DOC: absent]

The complete, expanded Object Info palette parameter table for a circuit in VW2026 is:

Navigate to Other End of Circuit · Flip · Show Cable Route · Number · Cable · Signal · Circuits ·
Circuit Type · Cable Length · Calculated Cable Length · Number Display · Cable Type · Cable
Outside Diameter · Source · Destination

Source: <https://app-help.vectorworks.net/2026/eng/VW2026_Guide/ConnectCAD/Editing_circuits1.htm>

**There is no `ShowEnd` / "Show End" parameter anywhere in the Vectorworks 2026 help.** I searched
the ConnectCAD section of the 2020–2026 guides and the ConnectCAD script reference. `ShowEnd` is
an **undocumented internal plugin parameter**. Whatever it does must come from the sibling's
binary reverse-engineering, not from here.

Two documented parameters that *are* relevant:

> **Source** — Displays the source socket information
> **Destination** — Displays the destination socket information

**[INFER]** These are read-only OIP readouts of the two endpoints. They are very likely the same
values the arrow formula draws from, and are plausibly what appears in the Insert Field list.

> **Number Display** — Determines where on the circuit the number displays: Auto / Source /
> Destination / Both / Mid / None. **"The Number Display does not apply to arrow circuits."**

That last sentence is important: `Number Display` governs the **circuit number** on polyline
circuits and is *inert* on arrow circuits. The user's data (`Number Display` = 'Both' on 214,
'Destination' on 6, `Number` blank on all 220) is therefore currently doing nothing visible —
the numbers are blank. Running `ConnectCAD > Drawing > Number Cables` would populate them.

### 2.5 Show/Hide Details — [DOC], but shallow

Command: **Show or Hide Details**, at `ConnectCAD > Drawing`.

> You can determine the level of detail to display in the Schematic layer by controlling the
> visibility of certain elements. ... The Show or Hide Details dialog box opens. Select the items
> to display in the drawing, and deselect the items to hide.

Source (VW2022, the last edition where this page is publicly reachable):
<https://app-help.vectorworks.net/2022/eng/VW2022_Guide/ConnectCAD/Displaying_labeling_and_numbering_ConnectCAD_objects.htm>

**The checkbox list is never enumerated in any edition.** The 2026 equivalent topic is titled
"Labeling and numbering ConnectCAD objects" (it appears in the 2026 sidebar TOC) but every
filename I tried for it returns HTTP 403 from the help CDN, so I could not read the 2026 wording.

**[INFER]** Given that the command's stated job is "controlling the visibility of certain
elements" in the Schematic layer, and given that ConnectCAD's own stated visibility mechanism is
classes (§2.6), `DlgShowHideDetails` is most likely a convenience front-end that toggles a fixed
set of `CC-*` class visibilities. That would make it the friendly wrapper around the
`CC-Circuit-Connector` answer in §1(a). This is a guess; it is not documented.

### 2.6 ConnectCAD classes — [DOC], convention only; no class list exists

Source: <https://app-help.vectorworks.net/2026/eng/VW2026_Guide/ConnectCAD/Getting_started_with_ConnectCAD.htm>

> **ConnectCAD classes give you detailed control over the visibility and look of objects and their
> parts.**
>
> ConnectCAD class names have a **CC-** prefix and indicate **the object, its part or function, and
> type**; for example, **`CC-Circuit-Signal-HDV`**. You can add classes using the
> **`CC-<object>-<part or function>-<type>`** naming convention.
>
> All ConnectCAD objects support the use of class text styles, which override default text
> attributes. When a class text style is set, the text color is applied to the text objects in the
> class.
>
> When files created prior to Vectorworks 2023 are opened, classes are remapped automatically.

**Vectorworks publishes no enumerated list of `CC-*` classes.** The naming *convention* is the
only documentation. Confirmed against the 2026, 2025, 2024 and 2023 guides.

Two specific classes are pinned down from the forum, by Vectorworks staff and by ConnectCAD's
author:

- **`CC-Circuit-Connector`** — [FORUM] Nikolay Zhelyazkov, "Custom layout for circuit labels",
  topic 100488, Sept 2022 <https://forum.vectorworks.net/topic/100488-custom-layout-for-circuit-labels/>.
  Asked how to change the font and size of the **connector type tags on circuits**, he answers
  that from VW2023 they "are defined by the **`CC-Circuit-Connector`** class which you can modify
  and add a text style to it", and points at "Connector type offset" in ConnectCAD Settings for
  the position. **This is the class rendering the text the user wants gone.**
- **`CC-Circuit-Signal-<SIG>`** — [FORUM] Conrad Preen, "Classing and graphic style of circuit
  graphics bubble", topic 113604
  <https://forum.vectorworks.net/index.php?/topic/113604-classing-and-graphic-style-of-circuit-graphics-bubble/>:
  "The overall attributes of the circuit are controlled by the signal type class e.g.
  `CC-Circuit-Signal-HDV`. So a text style applied to this affects the text in the bubble." And
  Nikolay Zhelyazkov: "**The bubble is using the circuit object's class.**" Practical warning from
  Preen: "You have to move the bubble to get the circuit to correctly recalculate the size."

**`CC-Circuit-Number`, `CC-Socket-DisplayTag` and `CC-Device-DisplayTag` are not documented
anywhere** and are not mentioned in any forum thread I found. Their existence is plausible under
the stated `CC-<object>-<part>-<type>` convention but is unverified from any citable source.

Related and documented: sockets and devices *do* have a **Display Tag** parameter —
"Enter the name that displays on the drawing; this can be a shorter name to save space on the
drawing" (<https://app-help.vectorworks.net/2026/eng/VW2026_Guide/ConnectCAD/Editing_devices_sockets_and_adapters.htm>),
and `Renumber ConnectCAD Objects` can prefix it
(<https://app-help.vectorworks.net/2026/eng/VW2026_Guide/ConnectCAD/Renumbering_ConnectCAD_objects.htm>).
So the `#Circuit.Device Tag#` token in the arrow formula is reading the far/near device's
**Display Tag**, not its Name.

### 2.7 Cross-reference / off-page — [DOC]

There are two mechanisms, one current and one deprecated.

**Current: arrow circuits.** Source:
<https://app-help.vectorworks.net/2026/eng/VW2026_Guide/ConnectCAD/Connecting_sockets.htm>

> **Arrow** — Draws the circuit with arrows; **on the source socket, the arrow indicates the
> direction of signal flow; the destination socket displays a "reverse arrow."** This is useful
> when a polyline circuit would be too complex or would cross over too many lines, or **to connect
> devices on different layers**, including with project sharing.
>
> When a file with arrow circuits is exported to a single, multi-page PDF with the Publish command,
> **hyperlinks are automatically created to connect the sockets.** This allows you to navigate
> through the circuit by clicking on the arrow circuit.

And from Editing circuits:

> **Navigate to Other End of Circuit** (Arrow circuit required) — Allows navigation from one end of
> the circuit to the other. The view is centered upon the destination circuit, changing layers if
> necessary. ... In a single, multi-page PDF created by the Publish command from the drawing or
> from viewports, **this link becomes a hyperlink**. ... Alternatively, Ctrl-click (Windows) or
> Cmd-click (Mac) on the end of the arrow circuit to navigate to the other end.

**Deprecated: the Link tool (cross-file).** Source:
<https://app-help.vectorworks.net/2021/eng/VW2021_Guide/ConnectCAD/Connecting_devices_in_different_files.htm>

> **Important note: use of this functionality is discouraged, since it will be deprecated in the
> future.** Instead of creating multiple linked files, create a single file with multiple layers,
> and link devices on different layers using the Arrow mode of the Connect tool.

> Click on the socket that will become the target destination ... **The link label normally
> displays the device and socket names.**

> Select the socket and click OK to create a connection with a relative link. **The link label
> normally displays the destination socket's link information.**

**This is the single strongest documented statement of far-end labelling in the whole corpus:** in
the (deprecated) off-page mechanism, the label drawn at your local end shows **the destination
socket's** information. The help then explicitly names arrow circuits as the replacement for that
mechanism.

### 2.8 The script reference — [DOC: nothing useful]

<https://www.vectorworks.co.jp/develop/ScriptReference/Pages/ConnectCAD.html> exposes only:
`CC_CircuitFromShape`, `CC_DeviceFromShape`, `CC_GetCableTypeData`, `CC_GetCircuitDest`,
`CC_GetCircuitSource`, `CC_GetConnectorData`, `CC_GetDevice`, `CC_GetEquipmentItem`,
`CC_GetSignalData`, `CC_OnFindAndReplace`, `CC_ReloadData`, `CC_RoomFromShape`,
`CC_RouteFromShape`.

**Nothing for circuit graphics, arrow formulas, labels, or the Insert Field vocabulary.**
`CC_GetCircuitSource` / `CC_GetCircuitDest` return the device and socket handles for each end —
useful for a scripted workaround, useless for discovering the formula grammar.

---

## 3. Also worth knowing (documented, affects the 220-circuit file)

- **`Number Cables`** (`ConnectCAD > Drawing`) "labels any non-labeled circuits in the layer
  according to the cable numbering system set in the ConnectCAD settings", applying the numbering
  rules in order. `Clear Cable Numbers` reverses it. The help adds: "the drawing should be checked
  before numbering circuits ... **so that the labels at each end of the circuit are up to date**."
  <https://app-help.vectorworks.net/2026/eng/VW2026_Guide/ConnectCAD/Numbering_circuits.htm>
- **Circuit Label Offset** in ConnectCAD Settings > General Settings has exactly two controls:
  **Circuit Number Offset (Grid Spaces)** and **Connector Type Offset (Grid Spaces)**. So a
  polyline circuit end draws (at most) two things: the **circuit number** and the **connector
  type**. That is precisely the "cable-type / connector text at those positions" the user is
  seeing, and it is the reason `Cable Type = '---'` on all 220 is relevant.
  <https://app-help.vectorworks.net/2026/eng/VW2026_Guide/ConnectCAD/Specifying_ConnectCAD_settings.htm>
- **Circuit Type is editable in place**: "Changes the type of an existing circuit. For example,
  change an arrow type to a polyline type of circuit. (**Circuits between two layers cannot change
  their Circuit Type**, however.)" So converting the 220 polylines to arrows is a supported,
  reversible OIP edit.
- **`Data Tags` are the documented escape hatch.** Unlike circuit graphics, Data Tags **do**
  support explicit far-end addressing, e.g.
  `#WS_OBJECTDATA('eval circuit destination socket', <record>, <field>)#` (topic 131675). If the
  arrow formula turns out not to resolve per end, a pair of Data Tag styles — one keyed to the
  source socket, one to the destination socket — is the documented way to get exactly the
  `Main CTP.Matrix In09` look, and is very likely how the Adlib as-built was produced.

---

## 4. Verdict on the per-end question

**The documentation does not answer it.** No page in any edition of the Vectorworks help states
whether the Arrow Text Formula is evaluated once (identical string at both ends) or twice
(resolved relative to each end). I consider that a firm negative result, not a search failure.

**My verdict, at roughly 75% confidence: the arrow text IS resolved per end, and each end shows
the FAR end's identity.** The evidence, weakest to strongest:

1. **[DOC]** The Insert Field help note: *"the layer option is useful for arrow circuits."* A
   circuit's own layer is a constant and would be useless printed on itself. Layer is useful on an
   arrow circuit only if the arrow reports **the other end's** layer — that is the whole point of
   an off-page pointer. This is the most telling sentence in the docs.
2. **[DOC]** Arrow circuits exist specifically "to connect devices on different layers", carry a
   `Navigate to Other End of Circuit` control, and become PDF hyperlinks to the other end. Their
   entire purpose is to stand in for a connection you cannot see. A label that did not name the
   far end would defeat that purpose.
3. **[DOC]** The mechanism arrow circuits explicitly replaced — the Link tool — is documented as
   drawing, at your local end, **"the destination socket's link information."** Vectorworks
   would not have regressed that behaviour while calling arrows the successor.
4. **[FORUM]** The tokens are `#Circuit.Device Tag#` and `#Circuit.Socket Name#` — **unqualified**.
   There is no `#Circuit.Source Device Tag#` / `#Circuit.Destination Device Tag#` pair in evidence,
   even though ConnectCAD demonstrably owns an absolute `Src_*`/`Dst_*` vocabulary and uses it in
   the numbering rules. An unqualified "the device" token only makes sense in a context where the
   renderer already knows which end it is drawing.
5. **[FORUM]** In topic 92229 the poster's stated goal is a *destination-dependent* arrow label
   ("show different value if destination is Control panel object or device") and he reports that
   `#Circuit.Device Tag#` alone "omitted source information" — i.e. he observed the token resolving
   to one specific end, not both.

**The counter-case**, which is why this is 75% and not 95%: a single formula string is stored on
the object (the user's `__ArrowFormula` is one field, not two), and if the renderer interpolated it
once and stamped the result at both ends, every observation above except (5) would still hold. Only
(5) discriminates, and it comes to me second-hand through a page summariser rather than as a direct
quote, because the decisive answer in that thread was posted as a screenshot.

**How to settle it in 30 seconds without any reverse engineering:** open `Edit Circuit Graphics` on
one circuit, tick Customize arrow, set the formula to `#Circuit.Device Tag#.#Circuit.Socket Name#`,
and read the **Preview**. Then set that one circuit's `Circuit Type` to `Arrow` and look at both
ends on the drawing. If the two ends differ, the answer is per-end and the user's request is a
two-click settings change for all 220 circuits via **Edit Default Circuit Graphics**. If they are
identical, fall back to Data Tags (§3, last bullet), which are documented to address
`circuit destination socket` and `circuit source socket` explicitly.

---

## 5. Confirmed / refuted, against the brief's six questions

| # | Item | Verdict |
| --- | --- | --- |
| 1 | Edit Circuit Graphics dialog: Arrow + Bubble groups, Customize checkbox, Text Formula, Insert Field, Preview, Arrow Style | **CONFIRMED** by the official parameter table (§2.1). **Insert Field list is NOT enumerated in the docs** — refuted as a documented item. Token syntax `#Circuit.<Field>#` known only from forum topic 92229. |
| 2 | Does the arrow formula resolve per end? | **NOT DOCUMENTED.** Strong circumstantial case for per-end far-end resolution (§4), ~75% confidence. Settle it with the dialog's own Preview. |
| 3 | `ShowEnd` | **REFUTED as documented.** No such parameter in the VW2026 OIP table or anywhere in the 2020–2026 help or script reference. Undocumented internal parameter. |
| 4 | Show/Hide Details | **CONFIRMED to exist** (`ConnectCAD > Drawing > Show or Hide Details`), documented one-liner only: it "control[s] the visibility of certain elements" in the Schematic layer. **The checkbox list is never enumerated.** |
| 5 | `CC-Circuit-*` / `CC-Socket-*` classes | **Naming convention CONFIRMED** (`CC-<object>-<part or function>-<type>`), classes explicitly stated to "give you detailed control over the visibility and look of objects and their parts". **No class list is published.** `CC-Circuit-Connector` CONFIRMED via Vectorworks staff as the class of the circuit connector-type text — **this is the one-click answer for removing the current text.** `CC-Circuit-Signal-<SIG>` CONFIRMED as controlling circuit/bubble text attributes. `CC-Circuit-Number`, `CC-Socket-DisplayTag`, `CC-Device-DisplayTag`: **no source found, unverified.** |
| 6 | Cross-reference / off-page | **CONFIRMED.** Current mechanism is **arrow circuits** (Connect tool, Arrow mode) — source arrow shows signal direction, destination shows a reverse arrow; navigates across layers; becomes PDF hyperlinks. The older cross-**file** Link tool is documented as **deprecated**, and its label is documented to show **"the destination socket's link information"** at the local end. |

## 6. Sources

- <https://app-help.vectorworks.net/2026/eng/VW2026_Guide/ConnectCAD/ConnectCAD.htm>
- <https://app-help.vectorworks.net/2026/eng/VW2026_Guide/ConnectCAD/Customizing_ConnectCAD_objects.htm>
- <https://app-help.vectorworks.net/2026/eng/VW2026_Guide/ConnectCAD/Editing_circuits1.htm>
- <https://app-help.vectorworks.net/2026/eng/VW2026_Guide/ConnectCAD/Creating_circuits.htm>
- <https://app-help.vectorworks.net/2026/eng/VW2026_Guide/ConnectCAD/Connecting_sockets.htm>
- <https://app-help.vectorworks.net/2026/eng/VW2026_Guide/ConnectCAD/Specifying_ConnectCAD_settings.htm>
- <https://app-help.vectorworks.net/2026/eng/VW2026_Guide/ConnectCAD/Cable_numbering_rules.htm>
- <https://app-help.vectorworks.net/2026/eng/VW2026_Guide/ConnectCAD/Numbering_circuits.htm>
- <https://app-help.vectorworks.net/2026/eng/VW2026_Guide/ConnectCAD/Renumbering_ConnectCAD_objects.htm>
- <https://app-help.vectorworks.net/2026/eng/VW2026_Guide/ConnectCAD/Getting_started_with_ConnectCAD.htm>
- <https://app-help.vectorworks.net/2026/eng/VW2026_Guide/ConnectCAD/Editing_devices_sockets_and_adapters.htm>
- <https://app-help.vectorworks.net/2026/eng/VW2026_Guide/ConnectCAD/Placing_external_connections.htm>
- <https://app-help.vectorworks.net/2022/eng/VW2022_Guide/ConnectCAD/Displaying_labeling_and_numbering_ConnectCAD_objects.htm>
- <https://app-help.vectorworks.net/2021/eng/VW2021_Guide/ConnectCAD/Connecting_devices_in_different_files.htm>
- <https://www.vectorworks.co.jp/develop/ScriptReference/Pages/ConnectCAD.html>
- <https://www.vectorworks.net/en-US/newsroom/personalize-your-av-workflows-with-connectcad>
- Forum topic 92229, "Edit Circuit Graphics Formula?" — <https://forum.vectorworks.net/index.php?/topic/92229-edit-circuit-graphics-formula/>
- Forum topic 131675, "Circuit Graphics Formula" — <https://forum.vectorworks.net/index.php?/topic/131675-circuit-graphics-formula/>
- Forum topic 100488, "Custom layout for circuit labels" — <https://forum.vectorworks.net/topic/100488-custom-layout-for-circuit-labels/>
- Forum topic 113604, "Classing and graphic style of circuit graphics bubble" — <https://forum.vectorworks.net/index.php?/topic/113604-classing-and-graphic-style-of-circuit-graphics-bubble/>

**Access note:** `forum.vectorworks.net` returns HTTP 403 to direct fetches; forum content above
was retrieved through the r.jina.ai text proxy, and where a thread's decisive answer was posted as
a screenshot it could not be transcribed. That is specifically why the exact conditional formula
Conrad Preen gave in topic 92229 is missing. A human opening topic 92229 in a browser would
recover it in seconds, and it is the single highest-value artifact still outstanding.
