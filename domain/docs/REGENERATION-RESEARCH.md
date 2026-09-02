# Scripted plug-in-object regeneration in Vectorworks 2026 (macOS)

**Research document. Nothing here has been run live.** Every claim carries a source.
Read §2 before you read anything else.

---

## 0. Verdict

**Yes. Scripted PIO regeneration is possible from Python, `vs.ResetObject` is the
correct call, and the sequence is:**

```python
vs.SetRField(h, '<PIO name>', '<Field>', value)   # write the parametric record
vs.ResetObject(h)                                  # flags the object for regeneration
# ---- let the script RETURN. Regeneration runs after the script has fully completed. ----
# ---- read the result in a SEPARATE, LATER script execution ----
```

**And: our evidence that regeneration is broken is almost certainly a measurement
artefact.** Vectorworks documents, in the official `ResetObject` remarks, that
`ResetObject` *sets a flag* and that the object does not regenerate until the current
script has finished — and it names our exact test as the thing you must not do:

> "…there are some things that you cannot do, **like reset another object and then
> check its bounding box for differences. Bounding boxes only get changed when the
> geometry of an object changes, and this won't happen until the object has
> regenerated**, and if you're still within the script of another object, this hasn't
> happened yet."
> — [VS:ResetObject, Remarks](https://github.com/Vectorworks/developer-scripting/blob/main/Function%20Reference/Functions/ResetObject.md)

Every measurement in `CONNECT-MECHANISM.md` §3.3 and `MACOS-EXECUTOR.md` §2 —
`GetBBox` before/after `ResetObject`, and `GetBBox` on a freshly
`CreateCustomObjectN`'d PIO — was taken **inside the same script execution as the
reset**. By the documented model those measurements are guaranteed to return the
stale/zero box whether regeneration works or not. They cannot distinguish "the
engine is dead" from "the engine is working exactly as designed."

Run the 12-line falsification script in §2.3 before doing any more engineering.

**One thing that could still be genuinely broken**, and which this research does not
settle: whether the `RunLayoutDialog` timer-callback context ever reaches "script
fully completed" while the dialog is open. The Plug-in Manager Python **menu command**
context definitely does. That is a reason to prefer the menu-command executor — but it
is a *different* reason from the one `MACOS-EXECUTOR.md` §2 currently gives, and it is
testable in five minutes.

### Primary source note

`developer.vectorworks.net` (the old MediaWiki) now **403s all fetches**. The entire
wiki has been migrated to public GitHub repositories and that is where the
authoritative text now lives:

- <https://github.com/Vectorworks/developer-scripting> — VectorScript/Python function
  reference, appendices, object-event docs. Every `Function Reference/Functions/<Name>.md`
  file is the former `VS:<Name>` wiki page verbatim, including community remarks.
- <https://github.com/Vectorworks/developer-sdk> — the C++ SDK docs.

Clone them. They are 69 MB and 36 MB and they are greppable, which the wiki is not.

---

## 1. The documented semantics, call by call

Sources are the migrated wiki pages; the local `vwx-plugin/vs_index.json` doc strings
match them (abridged) and are quoted where they differ.

### `ResetObject(h)` — **THE correct call**

> "Update the specified object using the current settings and parameter values. This
> will reset the bounding box of the object. If the object is in a wall, then the wall
> is reset also.
>
> An object of any type may be passed to this function to have its boundary reset. The
> following object types will be reset in a way that is appropriate for each type:
> **Plug-in Object**, Symbol Definition, Wall, Roof Container, Bitmap, Picture,
> Dimension, Extrude, Multiple Extrude, Sweep, Polygon, Polyline, Worksheet."
> — [ResetObject.md](https://github.com/Vectorworks/developer-scripting/blob/main/Function%20Reference/Functions/ResetObject.md)

Available since VectorWorks 10.0. And, decisively, from the same page's Remarks:

> "VectorScript doesn't do multi-tasking — it is only capable of running one script at
> a time. If one object is regenerating, and this object calls ResetObject on another
> object, **the other object will not regenerate until the first script has fully
> completed.**"

> "In order to improve performance of object regeneration, the VectorScript interpreter
> **looks for all of the PIOs of a certain type that have been flagged for regeneration
> (ResetObject sets this flag)**, and it will regenerate all of them before unloading
> that PIO code and loading the PIO code for the next PIO type."

Three things follow, all load-bearing:

1. **`ResetObject` is asynchronous by design.** It marks; it does not draw. Returning
   without error and leaving the bbox unchanged *within the same script* is correct
   behaviour, not a failure.
2. **Regeneration is batched by PIO type, in one pass, in an arbitrary type order.**
   The doc's own worked example is a **jack → cable → splitter** chain — i.e. exactly
   ConnectCAD's Device → Circuit → Socket topology. It states plainly that the chain
   breaks at the second hop back: "the splitter will fail to regenerate the second
   cable, and the last jack will not get regenerated either… then the interpreter
   thinks it's done."
3. Therefore **a single dispatch may legitimately regenerate only part of a
   cross-type graph.** The cheap fix for an external script is to reset *again* in a
   *new* script execution, repeatedly, until the state stops changing. Our batch bridge
   can do that for free; a human clicking a menu cannot.

### `ResetBBox(h)` — bounding box only, not a regeneration

> "Procedure ResetBBox forces the bounding box information for the specified object to
> be recomputed **based on the objects' current geometry**. Call this procedure after
> modifying an object to force a redraw of the object."
> Remarks: "Forces the bounding box information for object h to be recomputed based on
> current geometry. This doesn't seem to work on symdefs."
> — [ResetBBox.md](https://github.com/Vectorworks/developer-scripting/blob/main/Function%20Reference/Functions/ResetBBox.md)

"Based on current geometry" is the whole point: `ResetBBox` recomputes the box from
geometry that *already exists*. It does not run a PIO's recalculate. It cannot create
the geometry. For a PIO whose parameters changed, `ResetBBox` is a no-op with extra
steps. `ResetObject` already resets the bbox anyway (per its own description).

### `GetBBox(h)` — and the caching question

> "Procedure GetBBox returns the bounding box of the projection of the referenced
> object on the screen plane."
> Remarks (community, 2017): "GetBBox fails unpredictably on Roof faces when in
> top-plan: it returns a bounding box dependent on the axis widget and the page
> position of the face. Avoid the axis widget setting the view to Top…"
> — [GetBBox.md](https://github.com/Vectorworks/developer-scripting/blob/main/Function%20Reference/Functions/GetBBox.md)

**`GetBBox` is not documented as returning a cached value.** But the existence of
`ResetBBox` ("forces the bounding box information … to be **recomputed**") proves the
bbox *is* stored, not derived on demand — otherwise there would be nothing to force.
And `ResetObject`'s own remarks state the box only changes once the object has
regenerated. So the correct model is:

> the bbox is a stored property of the object, refreshed as a side effect of
> regeneration; `GetBBox` reads that stored property.

Two independent consequences, both matching what we observed:

- `GetBBox` immediately after `ResetObject`, same script → **stale value, guaranteed.**
- `GetBBox` on a PIO created moments ago by `CreateCustomObjectN`, same script →
  **`((0,0),(0,0))`, guaranteed**, because the object has never regenerated and so has
  never had a box computed. `FInGroup(h)` being empty in the same script is the same
  fact seen from the other end: the PIO's contents are produced *by* the recalculate.

Note also the second-order caution: `GetBBox` is *"the projection … on the screen
plane"*, so it is view-dependent. Any before/after comparison must be taken in the
same view, and in Top/Plan for 2D work. That is a second way our measurement could
mislead.

### `ReDraw` / `ReDrawAll` / `RedrawSelection` — screen only, and a direct hit

> `ReDraw`: "invokes a screen redraw of newly created objects…"
> `ReDrawAll`: "invokes a full screen redraw of the active Vectorworks document."
> `RedrawSelection`: "This will update selection indication without redrawing the drawing."

None of these regenerates a PIO. But `ReDraw`'s community remarks contain the single
most on-the-nose sentence in the entire reference for our situation:

> "**If you use a .vsm or .vst to create a .vso, the object will not regen, even if you
> use redraw or redrawall.** Try this at the very end of the vso script (assuming you
> have the vso set to regen on move):
> `HMove(parmHand,0,0);`"
> — [ReDraw.md, Remarks](https://github.com/Vectorworks/developer-scripting/blob/main/Function%20Reference/Functions/ReDraw.md)

A `.vsm` is a plug-in menu command. A `.vso` is a plug-in object. That is *precisely*
"a Python menu command creates a PIO and it doesn't draw." The suggested lever is a
zero-distance `HMove`, which fires the reset-on-move trigger — see §5.

The same page carries Julian Carr's document-wide sledgehammer:

```pascal
Procedure RegenGeometry;
VAR CurrentPref : INTEGER;
BEGIN
  CurrentPref := GetPrefInt(56);        { 3D Conversion Resolution }
  SetPrefInt(56, CurrentPref / 2);
  Layer(GetLName(ActLayer));            { re-activate the layer }
  SetPrefInt(56, CurrentPref);
END;
```

Pref 56 is *3D Conversion Resolution*
([Appendix F](https://github.com/Vectorworks/developer-scripting/blob/main/Function%20Reference/Appendix/pages/Appendix%20F%20-%20Preference%20Selectors.md)).
Changing it invalidates every object's 3D geometry; re-activating the layer forces the
sweep. This is the *documented* equivalent of the `SetLayerScale` trick we tried — and
it is document-wide and expensive, exactly the class of operation that killed
Vectorworks in `CONNECT-MECHANISM.md` §3.4. **Do not run this until §2 has been
falsified.**

### `UpdatePIOFromStyle` — **do not call this. The Python binding is broken.**

> "Updates the given plugin object from its style, if it has any."
> ```pascal
> PROCEDURE UpdatePIOFromStyle(VAR pioHandle : HANDLE);
> ```
> ```python
> def vs.UpdatePIOFromStyle():
>     return pioHandle
> ```
> Availability: from Vectorworks 2021.
> — [UpdatePIOFromStyle.md](https://github.com/Vectorworks/developer-scripting/blob/main/Function%20Reference/Functions/UpdatePIOFromStyle.md)

Look at the two signatures. Pascal takes a `VAR HANDLE` **in**. The Python binding
takes **no arguments** and *returns* a handle — the `VAR` parameter was mis-bound as
an out-parameter only. `vwx-plugin/vs_index.json` agrees: `"arity": 0`. So
`vs.UpdatePIOFromStyle()` passes an **uninitialised handle** into a function that
dereferences it.

This is the strongest single candidate for the VW 2026 crash recorded in
`CONNECT-MECHANISM.md` §3.4, and it is a crash you would expect on any platform, in
any context. **`UpdatePIOFromStyle` is permanently off the table.** It is also the
wrong tool regardless — it pushes *style* values onto an instance; ConnectCAD circuits
are not being driven from a plug-in style.

### `SetObjectVariableBoolean(h, 1167, True)` — "Immediate Reset", the one real dirty flag

The Object Selectors appendix, **Plug-in Objects** section:

| Object Setting | Selector | Setting Value |
|---|---|---|
| Parametric Internal ID | 1165 | INTEGER (read-only) |
| Parametric Localized Name | 1166 | STRING (read-only) |
| **Immediate Reset** | **1167** | **Write Only (Use on SDK parametric objects only!)** |
| Hide Style Parameter check | 1168 | Read Only |

— [Appendix G — Object Selectors](https://github.com/Vectorworks/developer-scripting/blob/main/Function%20Reference/Appendix/pages/Appendix%20G%20-%20Object%20Selectors.md)

This is the only documented lever that claims to make a reset *immediate* rather than
flagged. And its restriction — "SDK parametric objects only" — is *satisfied* here:
ConnectCAD is a compiled C++ plug-in, so Device / Socket / Circuit are SDK parametrics,
not VectorScript `.vso`s. It is untested by us and it is write-only, so there is no way
to read back whether it took; the test is behavioural.

There is **no** `Needs Update`-style dirty flag for PIOs. Selector 1004 ("Needs Update")
lives in the **Viewports** table, not the plug-in table — do not repurpose it.

### `ResetAllPluginObjects` — **does not exist**

There is no such VectorScript/Python function. Confirmed three ways: absent from the
3078-entry `vwx-plugin/vs_index.json`; absent from the 185 live-but-unindexed names in
`domain/docs/records/vs_index_drift.json`; and the string "Reset All Plug" does not
appear anywhere in the entire migrated developer-scripting repository, including
[Appendix H — DoMenuTextByName Constants](https://github.com/Vectorworks/developer-scripting/blob/main/Function%20Reference/Appendix/pages/Appendix%20H%20-%20DoMenuTextByName%20Constants.md).

It exists **only as a menu command**, Tools ▸ Utilities ▸ Reset All Plug-ins, and its
documented purpose is *version migration*, not "I changed a field":

> "Select the Reset All Plug-ins command to execute a refresh" of plug-in objects when
> migrating from previous versions … so the Object Info palette displays only relevant
> parameters and affected drawing objects are refreshed.
> — [Vectorworks Help: Resetting plug-in objects from previous versions](http://app-help.vectorworks.net/2024/eng/VW2024_Guide/Start/Resetting_plug-in_objects_from_previous_versions.htm)

**The exact universal name, verified locally**, not guessed. In
`/Applications/Vectorworks 2026/Workspaces/ConnectCAD.vww`:

```xml
<UniversalName>Reset_x20All_x20Plug_x2dIns</UniversalName>
```

`_x20` = space, `_x2d` = hyphen, so the string is **`Reset All Plug-Ins`** — capital
`I` in `Ins`. It is present in both the ConnectCAD and Spotlight workspaces, so the
"not present in the workspace" failure mode below does not apply to us. The call is
therefore `vs.DoMenuTextByName('Reset All Plug-Ins', 0)`, which carries two documented
hazards:

> "This call will fail if the specified item is not present in the workspace."
> "(2016.02.17): This is not operational when used from the regen event
> (kParametricRecalculate) or set up event (kObjOnInitXProperties) of plug-in objects.
> But can be used outside. To be noted that other view routines behave the same. **The
> Plug-in regeneration environment is isolated.**"
> — [DoMenuTextByName.md](https://github.com/Vectorworks/developer-scripting/blob/main/Function%20Reference/Functions/DoMenuTextByName.md)

Neither hazard is a crash on its own, and `CONNECT-MECHANISM.md` §3.2/§3.4 records it
completing safely once. Treat it as a heavyweight last resort, not a per-object call.

### `UpdateStyledObjects(styleName)` — bulk, but style-scoped

> "Update all objects of the specified style." — Vectorworks 2017.
> — [UpdateStyledObjects.md](https://github.com/Vectorworks/developer-scripting/blob/main/Function%20Reference/Functions/UpdateStyledObjects.md)

The nearest thing to a documented bulk regeneration that is an actual `vs.` function.
Only useful if the objects are instances of a named plug-in style. ConnectCAD circuits
are not being driven from a style, so this is almost certainly inapplicable — but it is
the *safe* member of the `UpdatePIOFromStyle` family and worth knowing exists.

### Regeneration pause prefs — read-only, so this door is shut

[Appendix F](https://github.com/Vectorworks/developer-scripting/blob/main/Function%20Reference/Appendix/pages/Appendix%20F%20-%20Preference%20Selectors.md)
carries three prefs that look like regeneration control. Two of the three are read-only,
which forecloses the obvious "pause regen, batch, resume" strategy:

| Pref | Selector | Value |
|---|---|---|
| Resetting Plugin-ins During File Read | 129 | TRUE or FALSE |
| Parametric Enable State Eventing | 590 | 0 NoStateEvents / 1 ResetStatesEvent / 2 InternalStatesEvent |
| Parametric Regen Paused Plan Rotation | 591 | **read-only** |
| Parametric Regen Paused Plan Rotation Angle | 592 | **read-only** |

Pref 590 turns on the *state-notification* feed described in §4; it does not gate
regeneration itself, and it only matters to a PIO that has opted in with
`kObjXPropAcceptStates`. Nothing here lets an external script suspend or force the
parametric engine.

### `RefreshObject`, `ForceRedraw` — **do not exist**

No such VectorScript/Python functions in 2026. Nothing by those names in the index, the
drift list, or the reference. `RefreshItem` / `RefreshLB` are *dialog* functions.
`DT_ResetAllDataTags` and `LDevice_Reset` / `LDevice_ResetVisual` are domain-specific
(Data Tags, Spotlight lighting devices) and do not apply to ConnectCAD objects.

Likewise absent from both the scripting and SDK repositories: `ResetPIO`, `ForcePIOReset`,
`SetPluginObjectNeedsReset`, `RedrawObject`, and any `ovResetBBox`-style selector. On the
SDK side the only reset material is `ISDK::ResetObject` (used in the SDK samples exactly
as we use it) and the terse note *"The reset function regenerates the Parametric Object's
visual appearance"*
([SDK: Parametric General Info](https://github.com/Vectorworks/developer-sdk/blob/main/Info/Parametric%20General%20Info.md)),
plus the `ResetOnMove` / `ResetOnRotate` flags in the extension-definition struct — which
is what makes §7 row 5 (`HMove(h,0,0)`) conditional on a flag we cannot inspect from
outside.

---

## 2. The "our measurement is wrong" hypothesis

**This is the hypothesis to test first, and the documentation strongly supports it.**

### 2.1 What we actually measured

Both surviving proofs are single-script-execution measurements:

```python
# CONNECT-MECHANISM.md §3.3 / MACOS-EXECUTOR.md §2
for nm in ('Angle', 'Ball Bearing', 'Base Cabinet'):
    h = vs.CreateCustomObjectN(nm, 5.0, 5.0, 0, False)
    vs.GetBBox(h)        # -> ((0,0),(0,0)), FInGroup(h) empty
```

```python
vs.SetRField(cir, 'Circuit', 'Src_Dev_Name', 'CAM-1')
vs.ResetObject(cir)
vs.GetBBox(cir)          # byte-identical to before
```

A third, smaller doubt about the first snippet: the Python binding is
`vs.CreateCustomObjectN(objectName, p, rotationAngle, showPref)` — **four** arguments,
with `p` a *point tuple*
([CreateCustomObjectN.md](https://github.com/Vectorworks/developer-scripting/blob/main/Function%20Reference/Functions/CreateCustomObjectN.md);
`vs_index.json` arity 4). As transcribed in §3.3 it was called with **five** flattened
arguments. Vectorworks' Python layer is often forgiving about flattened points, and a
handle did come back, so this is probably benign — but it costs nothing to write the
probe in the documented form and remove the doubt.

### 2.2 Why both are invalid

Per the `ResetObject` remarks quoted in §0 and §1, a reset flagged during a script
does not execute until that script has fully completed, and the bounding box does not
move until the object has regenerated. Both scripts read the box **before** the reset
could possibly have run. A working engine and a dead engine produce identical output
here. The measurement has no discriminating power.

Corroborating precedent from the same reference, on a different subsystem:

> "If you're hiding a class for the purpose of printing with that class turned off, you
> have to do a ReDrawAll before calling the DoMenuTextByName('Print',0) call, or else
> **the class doesn't get hidden until after the script completes execution.**"
> — [HideClass.md](https://github.com/Vectorworks/developer-scripting/blob/main/Function%20Reference/Functions/HideClass.md)

"Nothing takes effect until the script ends" is a general property of the VectorScript
runtime, not a quirk of PIOs.

### 2.3 The falsification script

Two dispatches. Do **not** merge them — the split is the whole experiment. Run from the
Plug-in Manager Python menu command (a real dispatch context), not the dialog bridge,
for the first run; then repeat through the bridge to compare the two contexts.

**Dispatch 1 — create and mark, then RETURN:**

```python
import vs
# Control: does GetBBox work at all in this context, on an ordinary object?
vs.Rect((0.0, 0.0), (100.0, 50.0))   # Python binding takes two POINTS, not four reals
r = vs.LNewObj()                      # "handle to the last object created ... during the current script execution"
print('CONTROL rect  type=%s bbox=%s' % (vs.GetTypeN(r), vs.GetBBox(r)))

# Subject: a stock PIO, measured in-script (expected: zero box)
h = vs.CreateCustomObjectN('Ball Bearing', (5.0, 5.0), 0, False)
vs.SetName(h, 'PROBE_PIO')
vs.ResetObject(h)
print('SUBJECT same-script  type=%s bbox=%s child=%s'
      % (vs.GetTypeN(h), vs.GetBBox(h), vs.FInGroup(h)))
```

**Dispatch 2 — a completely separate execution, nothing else in between:**

```python
import vs
h = vs.GetObject('PROBE_PIO')
print('SUBJECT next-dispatch  bbox=%s child=%s' % (vs.GetBBox(h), vs.FInGroup(h)))
```

**How to read it:**

| Dispatch 1 control rect | Dispatch 2 PIO bbox | Conclusion |
|---|---|---|
| sane, non-zero | **non-zero, has children** | **Regeneration works.** §3.3 and `MACOS-EXECUTOR.md` §2 are void. Our measurement was the bug. |
| sane, non-zero | still `((0,0),(0,0))`, no children | Regeneration really is not running in this context. Then, and only then, proceed down §4. |
| zero / nonsense | — | `GetBBox` itself is unreliable in this context. Stop using it as the oracle; switch to `FInGroup`/`NumObj` and `CC_GetCircuitSource`. |

Add a third arm if you can: run the identical dispatch-1/dispatch-2 pair from **both**
the `RunLayoutDialog` bridge and the Plug-in Manager menu command. If they differ, the
dialog-timer diagnosis in `MACOS-EXECUTOR.md` §2 is confirmed on the right grounds; if
they agree, the whole macOS-executor rebuild is not needed for *this* reason (it may
still be needed to avoid the documented dialog-in-non-dispatch-context crash).

### 2.4 Independent practitioner confirmation

This is not just a doc-page reading. Josh Benghiat — one of the most-cited third-party
Vectorworks plug-in developers, 2.2k posts on the official board — states it flatly in
a thread about resetting a *"data circuit"* PIO and a dependent *"data note"* PIO from a
menu command, which is very nearly our exact scenario:

> "**Script-based plug-ins run linearly, so the resets actually happen after the script
> completes.** You should look at your Create scripts."
> — JBenghiat, 2021-04-20,
> [Reset Object & Active Layer](https://forum.vectorworks.net/topic/82571-reset-object-active-layer/),
> Vectorworks Community Board ▸ Python Scripting

In the same thread he gives the canonical Python idiom for a bulk reset of one PIO type
— which is materially better than `Reset All Plug-Ins` for our purposes:

> "your reset script … should basically be
> `vs.ForEachObject( vs.ResetObject, "PON='{plug-in_name}'" )`"

`PON` is the Plug-in Object Name criterion. This is targeted, cheap, and stays inside
the documented `ResetObject` path — no menu commands, no document-wide sledgehammer.
For us: `vs.ForEachObject(vs.ResetObject, "PON='Circuit'")`, then the same for
`'Socket'` and `'Device'`, each in its own dispatch (see §1's per-type batching gotcha).

The thread also, incidentally, answers the "active layer" incantation: the OP's problem
was that *his own PIO scripts* changed the active layer, and Benghiat's advice was the
opposite of an incantation — "There's no reason to switch the active layer — you can
send any object to any layer without making it active."

Note: `forum.vectorworks.net` 403s direct fetches. It is readable through the text proxy
`https://r.jina.ai/<forum-url>`, which is how the above was retrieved.

### 2.5 What this hypothesis does *not* explain

`CONNECT-MECHANISM.md` §3.2 records one cross-execution retest: geometry placed on the
socket, `CC_CircuitFromShape`, then re-checked "in a separate script execution after
`ReDrawAll()`" — `CC_GetCircuitSource` still nil, `__ISNEW` still `True`. That test
*did* span dispatches, so it is not invalidated by this hypothesis.

So the honest position is: the **general** claim ("plug-in objects never regenerate
here") is unproven and probably false, while the **specific** ConnectCAD circuit-bind
failure may be real and independent. §1's batching gotcha offers a plausible mechanism
for the latter even when the engine is healthy — see §6.

---

## 3. Are record fields the right input? (Yes.)

`SetRField` on the parametric record **is** the documented mechanism, and it is the
same store the Object Info palette writes:

> "This can be used to update values in data records attached to objects, **as well as
> to set PIO parameter values (parameter records). When setting values in parameter
> records, the record name is the PIO object name.** Also, for the field name, use the
> field name as it appears in the plug-in editor's parameter dialog (such as
> "Draw3D"), not the internal parameter name (such as "pDraw3D")."
> — [SetRField.md, Remarks](https://github.com/Vectorworks/developer-scripting/blob/main/Function%20Reference/Functions/SetRField.md)

`GetParametricRecord(h)` returns a handle to that same hidden record:

> "Parametric record is a hidden record format containing the parameter values of the
> parametric object. Only parametric objects have parametric records."
> — [GetParametricRecord.md](https://github.com/Vectorworks/developer-scripting/blob/main/Function%20Reference/Functions/GetParametricRecord.md)

There is **no separate OIP write path.** The OIP does exactly two things: it writes the
parameter record, and it triggers a reset. The reset-trigger list treats the two
sources as peers:

> **Existing Object Reset** is triggered when:
> - **Parameters** were changed in the Object Info palette.
> - The **object's script** was edited…
> - Attributes of the object's **class**… were changed.
> - **Another script (object or menu command) called `ResetObject`** to trigger a
>   regeneration of the object.
> - Object was **rotated**, and Reset on Rotate was set…
> - Object was **moved**… and Reset on Move was set…
> — [VectorScript ▸ Object Events](https://github.com/Vectorworks/developer-scripting/blob/main/VectorScript/pages/Object%20Events.md)

So "`SetRField` + `ResetObject` from a menu command" is a **documented, first-class,
supported** equivalent of a user typing in the OIP. There is no privileged path we are
missing.

Two caveats worth carrying:

- **Case matters in pop-up fields.** `SetRField.md` records a real bug where writing
  `'Condoc F - Horizontal'` instead of `'ConDoc F - Horizontal'` left an orphan value
  that the OIP *displayed* as correct while the object drew the default. Our
  `Circuit` writes go into text fields, but any enum-ish ConnectCAD field is exposed
  to this.
- `SetRField` already does a limited redraw of its own: "The object 'h' is redrawn
  afterward to support the symbol 'link text to record' feature." That is a *redraw*,
  not a regeneration — do not mistake a visual flicker for a recalculate.

---

## 4. The Recalculate lifecycle, and what a script can trigger

The PIO event is `kParametricRecalculate`, numeric event **3**. (The Parametric State
Notifications page opens by calling it `kParametricRecalculate(5)` — that is a typo in
the official doc; every code sample on that page and in all seven `vsoStateGet*` pages
uses `3: {kParametricRecalculate}`, and the Object Events article defines
`kResetEventID = 3`. Use 3.) The neighbouring event IDs, from the article's own CONST
blocks: `kOnObjPrefEventID = 4`, `kObjOnInitXProperties = 5`,
`kObjOnObjectUIButtonHit = 35`, `kObjOnAddState = 44`. There is no
`kObjOnObjectXProperties`.

Triggers are exactly the six listed in §3 above. **A script can trigger it**, via
`ResetObject`, and that is an explicitly enumerated trigger — not a side effect.

What a script **cannot** do:

- Call the recalculate directly. There is no `vs.` entry point for it. The only handles
  on the event live *inside* the PIO's own code (`vsoGetEventInfo`,
  `GetCustomObjectInfo`, `IsNewCustomObject`, `vsoStateGet*`, `vsoStateClear`), and
  those are drop-in functions valid only during the PIO's own event dispatch.
- Observe it. `vsoStateGetParamChng` etc. report *to the object*, not to us.
- Escape its isolation. "The Plug-in regeneration environment is isolated"
  (`DoMenuTextByName.md`), and geometry created outside the reset event is not a member
  of the PIO at all:
  > "any primitives that you intend to be a member of the PIO can only be created
  > within the reset case of the event loop." — Object Events

That last point independently explains why every attempt in `CONNECT-MECHANISM.md`
§2.4 to *build* a PIO's contents from outside failed, and why `HDuplicate` of an
already-regenerated object was the only thing that worked.

The state-notification machinery (`SetPrefInt(590, 1)` +
`SetObjPropVS(18 /*kObjXPropAcceptStates*/, True)` + `vsoStateAddCurrent` +
`vsoStateClear`) is described in
[Parametric State Notifications](https://github.com/Vectorworks/developer-scripting/blob/main/Common/Tasks/Parametrics/Parametric%20State%20Notifications.md)
by Vladislav Stanev. It is entirely an *inside-the-PIO* facility. `kParameterChangedReset (3)`
is the state ConnectCAD's Circuit would receive when we `SetRField` + `ResetObject` —
which is further evidence our input is the right input. We cannot set these properties
on someone else's compiled plug-in.

Two details from that page are worth carrying anyway, because they describe what
ConnectCAD's own code is doing on the other side of the wall:

- The six **pre-reset states** — `kCreatedReset (0)`, `kMovedReset (1)` (only if reset
  on move is on), `kRotatedReset (2)` (only if reset on rotate is on),
  `kParameterChangedReset (3)`, `kObjectChangedReset (4)`, `kLayerChangedReset (5)` —
  are exactly the six triggers in §3, seen from inside. A `SetRField` + `ResetObject`
  from us arrives as `kParameterChangedReset`.
- Two states **do not** cause an automatic reset: `kExitFromEditGroup (6)` and
  `kObjectNameChanged (7)`. The doc is explicit — *"'Exit Group' doesn't send a reset
  event. This means that you have to explicitly reset the object upon receiving the
  state event"*. So **renaming a PIO does not reset it.** Our socket/device workflow
  does a lot of `SetName` with GUIDs (`CONNECT-MECHANISM.md` §2.2); none of that
  triggers anything on its own. Corroborated independently: *"actions that modify an
  object's name don't trigger a regen event, so `vsoStateGetNameChng` won't detect name
  changes until next regen"*
  ([vsoStateGetNameChng.md](https://github.com/Vectorworks/developer-scripting/blob/main/Function%20Reference/Functions/vsoStateGetNameChng.md)).

---

## 5. Document state, selection, and the practitioner "incantations"

Which are real, per the documentation:

| Incantation | Verdict | Source |
|---|---|---|
| **Let the script end, then read** | **Real, and the only one that is documented as necessary.** | `ResetObject.md` remarks |
| `HMove(h, 0, 0)` after creating a PIO from a menu command | **Real, documented, and specific to our exact scenario** — but only fires if that PIO has *Reset on Move* set in its plug-in properties, which we cannot check or change for ConnectCAD. Cheap and harmless to try. | `ReDraw.md` remarks: "If you use a .vsm or .vst to create a .vso, the object will not regen, even if you use redraw or redrawall. Try … `HMove(parmHand,0,0)`" |
| `ReDrawAll()` before reading | Harmless. Documented to matter for *screen* state (`HideClass.md`), not for regeneration. Worth including in a probe purely to remove doubt. | `ReDrawAll.md`, `HideClass.md` |
| `vs.ForEachObject(vs.ResetObject, "PON='<name>'")` | **Real, and the practitioner standard.** Not an incantation — it is just `ResetObject` applied by criteria, so it inherits the same deferred semantics. Its value is that it resets one whole PIO *type* per pass, matching how the interpreter batches. | JBenghiat, [forum topic 82571](https://forum.vectorworks.net/topic/82571-reset-object-active-layer/) |
| **"Select the object, then reset"** | **No documentation supports this.** Selection is not in the reset-trigger list. `SetSelect` + `DoMenuTextByName` is a different mechanism (it makes a *menu command* act on the object) and should not be confused with making `ResetObject` work. | Object Events trigger list |
| `DSelectAll()` first | No documented effect on regeneration. It is real hygiene for anything that then uses a selection-based menu command. | — |
| Active layer must contain the object | Not documented as a reset requirement. `GetLayer.md` does warn that a freshly pasted/inserted PIO "has to regenerate before it is actually in a layer" — i.e. layer membership is downstream of regeneration, not upstream. | `GetLayer.md` remarks |
| Toggling screen redraw (`SetPref(6799, …)`) | Pref 6799 is "Turns screen redraws on/off". Screen-level only; no documented relationship to the parametric engine. | Appendix F |
| Julian Carr's `GetPrefInt(56)` / `SetPrefInt(56, …)` + re-activate layer | Real, documented, and a **document-wide** sledgehammer of the same class as `SetLayerScale`. High crash risk in a non-dispatch context. Last resort only. | `ReDraw.md` remarks |
| `BeginContext` / `EndContext` | **Not a regeneration tool.** It is undo-list suppression for temporary geometry. It also carries a documented AppleScript/undo bug and must begin and end in the same procedure block. Do not add it hoping it flushes anything. | `BeginContext.md` remarks |

One further documented gotcha that bit us already, worth recording here because it is
in the same family:

> "This function will fail if obj is being moved from a non-regenerable list of a
> plug-in to a regenerable list of a plug-in." … "Starting with 12.5, `SetParent` no
> longer works within plug-in objects if you're trying to move something from outside
> of the PIO group into the PIO group. … To accomplish the same purpose, do this:
> `dupeHandle := CreateDuplicateObject(somethingInsideSymbol, pioHandle);`"
> — [SetParent.md, Remarks](https://github.com/Vectorworks/developer-scripting/blob/main/Function%20Reference/Functions/SetParent.md)

That is the exact failure in `CONNECT-MECHANISM.md` §2.4 (`SetParent(socket, device)`
→ `False`), and `vs.CreateDuplicateObject(src, hDevice)` is the documented replacement
for our `HDuplicate` + `SetParent` dance. Worth trying in the socket-attach path.

---

## 6. macOS versus Windows

**No macOS-specific difference in scripted PIO regeneration is documented anywhere.**
A full-text sweep of the migrated developer-scripting repository for Macintosh/Windows
divergences turns up only: `SetTextStyle` (Outline/Shadow styles Mac-only),
`GetFolderPath` / `ConvertPosix2HSFPath` (path separators), `KeyDown` (hangs, Windows
only), and one OIP quirk:

> "Multiple selections behave differently on Mac and windows. Select 2 objects. Object
> A has a Dim Parm, Object B has an Int Parm. Change the parm. On windows, it will
> change to 11" and 11 respectively. On the Mac, with A active it will change to 11"
> and no change to B. (26635)"
> — [SetParameterVisibility.md](https://github.com/Vectorworks/developer-scripting/blob/main/Function%20Reference/Functions/SetParameterVisibility.md)

That is an OIP multi-select bug, not a regeneration difference. The Vectorworks 2026
release notes list no platform-divergent scripting behaviour
([Vectorworks 2026](https://github.com/Vectorworks/developer-scripting/blob/main/Common/Versions/Vectorworks%202026.md);
Python 3.9.2, same as 2025).

**Our real macOS difference is not the engine — it is the trigger.** Windows has a
native palette that presses the hotkey; macOS does not, which is what
`MACOS-EXECUTOR.md` is about. That difference is about *how a dispatch gets started*,
not about what regeneration does once a dispatch runs. Keep those two claims separate.

---

## 7. Ranked list of things to try — cheapest and safest first

Stop at the first one that works. Do not batch these into a single script; that is how
we crashed Vectorworks last time, and it destroys the ability to attribute the result.

| # | Try | Why | Risk | Source |
|---|---|---|---|---|
| **1** | **Split the measurement across two dispatches** (§2.3). Write + `ResetObject` in dispatch A; read `GetBBox` / `FInGroup` in dispatch B. | The documented model says this is the *only* valid way to observe a reset. Everything else in this list is moot until this is run. | **None.** Two reads and a create. | `ResetObject.md` remarks |
| **2** | Add an **ordinary-object control** (a `Rect`) to every probe, and pin the view to Top/Plan. | Establishes whether `GetBBox` is trustworthy in the context at all, and removes the documented view-dependence. | None | `GetBBox.md` |
| **3** | Repeat the **same `ResetObject` in N successive dispatches** and watch for change between them. | Regeneration is batched one pass per PIO type; a Device→Circuit→Socket chain is documented to stall on the second hop back. Successive dispatches walk the chain. Free for a batch bridge. | None | `ResetObject.md` remarks (jack/cable/splitter) |
| **4** | Stop using `GetBBox` as the oracle. Use `vs.FInGroup(h)` / child count, and `CC_GetCircuitSource`. | Child contents are produced *by* the recalculate; they are a more direct witness than a projected box. `CC_*` getters are already our established ground truth. | None | Object Events; `CONNECT-MECHANISM.md` §1 |
| **4b** | `vs.ForEachObject(vs.ResetObject, "PON='Circuit'")` — one PIO type per dispatch. | The practitioner-standard bulk reset, from Josh Benghiat. Targeted, no menu command, no document-wide cost, and it aligns with the documented per-type batching so each dispatch does one clean pass. | Very low | [forum.vectorworks.net/topic/82571](https://forum.vectorworks.net/topic/82571-reset-object-active-layer/) |
| **5** | `vs.HMove(h, 0.0, 0.0)` immediately after creating/writing, before `ResetObject`. | Documented workaround for the exact "a .vsm created a .vso and it won't regen" case. Only effective if that PIO has Reset on Move. | Very low — a zero-distance move. | `ReDraw.md` remarks |
| **6** | `vs.SetObjectVariableBoolean(h, 1167, True)` — **Immediate Reset** — then `ResetObject(h)`. | The only documented lever for a synchronous rather than flagged reset. Its "SDK parametric objects only" restriction is satisfied: ConnectCAD is compiled C++. | Low-moderate. Write-only, undocumented beyond one table row, and it changes reset *timing* — try it on a scratch stock PIO first, never first on a real circuit. | Appendix G, Plug-in Objects |
| **7** | `vs.CreateDuplicateObject(src, hDevice)` in place of `HDuplicate` + `SetParent` for socket attach. | Documented replacement for exactly the `SetParent`-into-a-PIO failure we hit. | Low | `SetParent.md`, `CreateDuplicateObject.md` |
| **8** | `vs.DoMenuTextByName('Reset All Plug-Ins', 0)` — **once, alone, in its own dispatch**, then read in the next. Note the capital `I`. | Document-wide reset. Completed safely once in our own session. Present in the ConnectCAD workspace (verified in `ConnectCAD.vww`), so it will not silently no-op. | Moderate. Document-wide; slow on a large file; not a per-object call. | `DoMenuTextByName.md`; VW Help; `ConnectCAD.vww` |
| **9** | Julian Carr's `GetPrefInt(56)` / `SetPrefInt(56, half)` / re-activate layer / restore. | Documented document-wide geometry invalidation. | **High.** Same class as `SetLayerScale`, which is a prime suspect for the §3.4 crash. Only after 1–8, only from a genuine menu-command dispatch, only on a scratch document. | `ReDraw.md` remarks |
| — | ~~`vs.UpdatePIOFromStyle()`~~ | — | **NEVER.** Python binding takes no argument for a `VAR HANDLE` in-parameter — it dereferences an uninitialised handle. Prime suspect for the §3.4 crash. | `UpdatePIOFromStyle.md`; `vs_index.json` arity 0 |
| — | ~~`vs.SetLayerScale(...)`~~ | — | **NEVER** from a non-dispatch context. Document-wide PIO reset; co-suspect for the §3.4 crash. | `CONNECT-MECHANISM.md` §3.4 |
| — | ~~`vs.ResetBBox(h)`~~ as a regeneration attempt | — | Not dangerous, just useless: it recomputes the box from geometry that already exists, and `ResetObject` resets the box anyway. | `ResetBBox.md` |

---

## 8. What this means for the two documents that depend on the old conclusion

**`domain/docs/CONNECT-MECHANISM.md` §3.3** — the claim "Stock Vectorworks plug-in
objects … also generate zero geometry from this bridge" rests on a same-script
`GetBBox` and is **not supported by that evidence**. The observation is exactly what a
*healthy* engine produces. §3.3 should be marked provisional pending §2.3. §3.1 and
§3.2 (record fields written, `CC_GetCircuitSource` nil) are unaffected, and §3.2's
cross-execution retest remains a genuine unexplained result.

**`domain/docs/MACOS-EXECUTOR.md` §2** — "While that dialog owns the event loop
Vectorworks does not run the parametric engine" is an inference from the same invalid
measurement. It may well be true; it is not yet demonstrated. The executor rebuild has
an *independent* justification that this research does not touch — `vwx_pump.py`'s
documented context map, in which opening a dialog from a non-dispatch context crashes
Vectorworks. Keep that justification; retire this one until §2.3 confirms it.

If §2.3 comes back green in both contexts, a day of executor work is unnecessary and
the real ConnectCAD blocker is narrower than we thought: not "regeneration is dead",
but "the Circuit PIO's bind does not fire from a record-field change alone", for which
§7 rows 3, 4 and 6 are the live hypotheses and `Make Connections from List`
(`CONNECT-MECHANISM.md` §4) remains the supported fallback.

---

## 9. Sources

- [Vectorworks/developer-scripting](https://github.com/Vectorworks/developer-scripting)
  — the migrated developer wiki. `developer.vectorworks.net` 403s; this repo is the
  live text. Pages cited: `ResetObject`, `ResetBBox`, `GetBBox`, `SetBBox`, `ReDraw`,
  `ReDrawAll`, `RedrawSelection`, `UpdatePIOFromStyle`, `SetRField`,
  `GetParametricRecord`, `CreateCustomObject(N)`, `IsNewCustomObject`,
  `GetCustomObjectInfo`, `SetParent`, `CreateDuplicateObject`, `SetObjectVariableBoolean`,
  `DoMenuTextByName`, `HideClass`, `GetLayer`, `SetParameterVisibility`,
  `BeginContext`/`EndContext`, `vsoStateClear`.
- [VectorScript ▸ Object Events](https://github.com/Vectorworks/developer-scripting/blob/main/VectorScript/pages/Object%20Events.md)
  — Charles Chandler; the reset-trigger list and the inside/outside-the-PIO geometry rule.
- [Parametric State Notifications](https://github.com/Vectorworks/developer-scripting/blob/main/Common/Tasks/Parametrics/Parametric%20State%20Notifications.md)
  — Vladislav Stanev; `kParametricRecalculate`, `kParameterChangedReset`.
- [Appendix F — Preference Selectors](https://github.com/Vectorworks/developer-scripting/blob/main/Function%20Reference/Appendix/pages/Appendix%20F%20-%20Preference%20Selectors.md)
  and [Appendix G — Object Selectors](https://github.com/Vectorworks/developer-scripting/blob/main/Function%20Reference/Appendix/pages/Appendix%20G%20-%20Object%20Selectors.md).
- [Vectorworks/developer-sdk](https://github.com/Vectorworks/developer-sdk) — `ISDK::ResetObject`.
- [Vectorworks Help: Resetting plug-in objects from previous versions](http://app-help.vectorworks.net/2024/eng/VW2024_Guide/Start/Resetting_plug-in_objects_from_previous_versions.htm).
- [forum.vectorworks.net topic 82571 — "Reset Object & Active Layer"](https://forum.vectorworks.net/topic/82571-reset-object-active-layer/)
  (Martin Crawford / JBenghiat, April 2021). The forum 403s direct fetches; read it via
  `https://r.jina.ai/<url>`.
- `/Applications/Vectorworks 2026/Workspaces/ConnectCAD.vww` — the verified universal
  menu name `Reset_x20All_x20Plug_x2dIns`.
- Local: `vwx-plugin/vs_index.json` (3078 functions),
  `domain/docs/records/vs_index_drift.json` (185 live-only, 18 index-only),
  `domain/docs/CONNECT-MECHANISM.md`, `domain/docs/MACOS-EXECUTOR.md`,
  `vwx-plugin/vwx_mcp_bridge.py`, `vwx-plugin/vwx_pump.py`.
