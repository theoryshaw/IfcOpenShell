.. This file was generated with the assistance of an AI coding tool.

Showing loads
=============

Bonsai draws loads in the viewport as a statics textbook draws them: arrows to scale, labelled with
their values, with their angles, slopes and components, and the resultant of the forces at each point.

Turning loads on
----------------

Tick **Show Loads** in the **Show Loads** panel of the scene properties' structural tab. The same
toggle is in the viewport's **Overlays** menu.

Loads hide with their structural items: hiding a point hides its loads.

Choosing load cases
-------------------

Each load case in the **Structural Load Cases** panel has an **eye**:

- **Click** an eye to show that load case, making it the **active** one. Others already shown stay
  shown. Clicking the active one's eye hides it.
- **Shift+click** to show or hide a load case without changing the active one.
- **Ctrl+click** to show only that load case.
- **Hide All**, beside **Add Load Case**, hides them all.

When several load cases are shown, the active one's eye is drawn pressed. Only the active one draws its
moments; the others draw their loads, each labelled with its load case's name. The tools that work on
one load case, such as **Apply Structural Load**, start on the active one.

The **Load Case** menu in **Show Loads** chooses the active one too.

Soloing a load
--------------

To see one load on its own, **Shift+click** it in the **Load Definitions** list, or Shift+click the
select button to the left of an applied load in a load case. Its items are selected, and:

- That load is drawn wherever it is applied, in any load case, and nothing else is.
- Where two load cases put it on the same point, it is drawn once, labelled with both their names, as
  **About A, About B: 10.00 kip**.
- A red **Solo** line, with an **✕**, shows in the **Structural Load Cases** and **Load Definitions**
  panels, and the soloed load's rows show a solo icon.

The load cases that were shown are set aside, not changed. The solo ends, and they come back, when you:

- click **✕**, or Shift+click the soloed load again,
- click a load case's eye, which shows that load case,
- click **Hide All**, or turn **Show Loads** off.

How loads are drawn
-------------------

The **Show Loads** panel sets how forces are drawn, in the viewport and in reports alike:

Reference Frame
   **Global**, along X, Y and Z, or **Local**, along each point's own axes.

Force Display
   - **Both**: each point's resultant with its components.
   - **Resultant**: the resultant only.
   - **Components**: the X, Y and Z components only.
   - **Parallelogram**: each force from its point, added into the resultant by the parallelogram law.
   - **Tip-to-Tail**: the forces chained tip to tail, in the order set in the **Applied Loads**
     lists, closed by the resultant.

Force Scale
   Force per unit length. Zero fits the arrows to the model automatically.

Angles, Slopes
   Mark each force's angle with an arc, and its slope with a rise and run triangle. **Angle From**
   measures angles from the axis of the eighth the force points into (**Load Direction**), from the
   **Nearest Horizontal**, as textbooks draw them, or from **+X**.

Point Axes Components
   Also resolve forces along a tilted point's own x′ and z′ axes.

Moment Detail
   How much of each moment's working is drawn. See :doc:`moments`.

Force Decimals, Angle Decimals
   Decimal places of the values shown.

Label Size, Arrow Thickness
   Scale the labels, and the arrows' shafts and heads together.

Arrows are drawn over the dashed axis and construction lines, so that they stay readable where they
cross.

Marks on loads
--------------

Two kinds of load are marked, in the viewport and in reports:

- A **moved** load, made by **Move Loads to Point** (see :doc:`moments`), is drawn with a **dashed
  shaft** and labelled with the load case it came from, as **← LC_1**. Its couple's label names it
  too.
- A **shared** load, one definition applied at several points, is tagged with a circled number, ①
  to ⑳, the same at every point it acts. Editing it at one point changes it at all of them.

Picking loads in the viewport
-----------------------------

With loads shown, hover over an arrow or its value to highlight it, and click to edit it:

- An **arrow** opens its dialog: **Edit Structural Load** for a load, **Edit Resultant** for a
  resultant, **Edit Axes** for a point's axes.
- A **value**, such as a magnitude, angle or slope, opens the dialog with that value ready to type.
- A **moment's** lines or value open **Edit Moment Centre**, and the sum at the centre opens **Edit
  Resultant Moment**.

The tail of an arrow is left free, so that clicking a point still selects it.
