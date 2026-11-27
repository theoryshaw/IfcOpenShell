.. This file was generated with the assistance of an AI coding tool.

Loads and load cases
====================

Loads in Bonsai follow IFC's structure:

- An **analysis model** groups the structural items analysed together and the load cases they carry.
- A **load case** groups the loads acting at once, such as dead load or wind. It can hold **load
  groups** for parts of it.
- An **applied load** is one load on one structural item, a point, member or surface, in a load case.
- A **load definition** holds the load's values: its force components and moments. Several applied
  loads can share one definition, so that editing it once changes all of them.

Analysis models
---------------

The **Structural Analysis Models** panel, in the scene properties' structural tab, lists the models.
The one marked current is the one new loads go into, the one shown, and the one reports are written
for. Click the circle beside another model to make it current.

A structural item's own **Analysis Models** panel, in its object properties, lists every model with a
checkbox. Ticking one assigns all the selected items to that model.

While a load case is being edited, its **Analysis Models** box sets which models it loads.

Load cases
----------

The **Structural Load Cases** panel lists the load cases. Each row has:

- An **eye**, to show its loads in the viewport. See :doc:`showing_loads`.
- **Duplicate**, which copies the load case with its load groups and applied loads. The copies share
  their load definitions with the originals, so a value edited once changes in both. This suits
  problems worked several ways, such as the same loads with moments about different points.
- **Move Loads to Point**, which adds the load case's loads, moved to a point, to another load case.
  See :doc:`moments`.
- **Edit** and **Remove**. Removing a load case also removes its applied loads and load groups.

Editing a load case shows its attributes (collapsed by default, with self-weight), its moment centre
(see :doc:`moments`), the analysis models it loads, and its **Applied Loads**.

Applying a load
---------------

Select one or more structural items and click **Apply Structural Load**: the **+** in the header of
an item's **Applied Loads** panel, or the structural tool. The dialog asks for:

Load Case
   The load case to add the load to, or a new one. It starts on the load case shown in the viewport.

Axes
   For a force on a curve or surface member, the axes it is given in: **Global**, the project's, with Z
   vertical, or **Local**, the member's own. A surface member's local Z is normal to its surface, as wind
   or pressure acts; a curve member's local X runs along it and its Z follows the member's Axis. A force
   given in local axes is named with "local". Point connections take forces in global axes, or in their
   own point axes (below).

Input
   How the force is entered:

   - **Components**: X, Y and Z.
   - **Angle**: a magnitude and an angle in the X-Z plane.
   - **Slope**: a magnitude and a rise over run, as a 3:4 slope.

Direction
   With **Angle** or **Slope**, the eighth of a circle the force points into, **Q1** to **Q8**. The
   angle or slope is measured from that eighth's axis:

   ===== =========================
   Q1    from +X, turning up
   Q2    from +Z, turning right
   Q3    from +Z, turning left
   Q4    from −X, turning up
   Q5    from −X, turning down
   Q6    from −Z, turning left
   Q7    from −Z, turning right
   Q8    from +X, turning down
   ===== =========================

   A force straight down is 0° in Q7 (or Q6).

Given
   What is known: the **Magnitude**, or only its **X** or **Z** component, as a horizontal or vertical
   capacity. With a component given, the magnitude follows from it and the direction.

Acts As
   **Pull**, drawn leaving its point as a cable pulls, or **Push**, drawn arriving at its point as a
   strut pushes. The force is the same either way; only the drawing differs.

Moment
   A couple about Y, applied with the force or on its own, counter-clockwise positive as statics texts
   take it. It counts in every moment taken, the same about any point.

Point Axes
   For a point whose axes are tilted (see below), enter the force along its own x′ and z′ axes rather
   than X and Z.

Magnitude Known, Direction Known
   Whether each value is known or to be found. See :doc:`resultants`.

Magnitude As
   Tie this force's magnitude to another's at the same point, equal or by a **Ratio**, as two equal
   cable tensions are. See :doc:`resultants`.

The dialog previews the load in the viewport while you edit it. The load's name is made from its
values, unless you type one.

Applying an existing load definition
------------------------------------

While editing a load case, the bottom of its **Applied Loads** box applies an existing definition:

1. Choose the kind of load, then the definition. Only definitions that the selected items can take
   are offered. With nothing structural selected, every kind is offered.
2. Or click the **eyedropper** and click a load's arrow in the viewport to pick its definition.
3. Click the button below them. It names the items it will apply to, as **Apply to B, C**, and skips
   items that already carry that load in the load case.

The picked definition is shared, not copied: the new applied load and the one picked edit together.

Editing loads
-------------

- Click a load's arrow in the viewport to open **Edit Structural Load**. Click its value to open the
  dialog with the magnitude ready to type over. The dialog opens beside the loads, not over them.
- Or click the pencil beside it in an **Applied Loads** list.

The dialog reopens the force the way it was entered, by components, angle or slope. Edits are
previewed in the viewport until you confirm them. Editing a load definition shared by several applied
loads changes all of them; the drawing tags shared loads so that this is no surprise (see
:doc:`showing_loads`).

Loads move with their items. Moving a point redraws its loads at once.

The Applied Loads panels
------------------------

A structural item's **Applied Loads** panel, in its object properties, lists its loads by load case,
with each load case's resultant at the item, an **Edit Resultant** pencil and the load case's eye.
A point also gets **Place Point** (see :doc:`moments`) and, for each load case taking moments about
it, a **Moments About This Point** row.

A load case's own **Applied Loads** box lists its loads by item. Each row has:

- A **select** button on the left. Click it to select the load's item and make it active.
  **Shift+click** to also solo the load, drawing it alone. See :doc:`showing_loads`.
- Up and down arrows that set the order the item's forces are chained in, tip to tail. A reverse button
  flips the whole chain.
- **Edit** and **Remove**.

A moved load is dimmed and names the load case it came from, as **LC_1 at P on P ← LC_1**. It is
rewritten from that load case after every change, so it is not meant to be edited by hand.

Load definitions
----------------

The **Load Definitions** panel lists every load definition, with the number of applied loads using
it in brackets. Click the pencil in its header to list them.

- **Click** a definition to select the structural items it is applied to.
- **Shift+click** to also solo it. See :doc:`showing_loads`.
- **Unused Only** lists only definitions applied in no load case or load group, to tidy up.
- **Filter** hides unused duplicates of a name.

A moved load's definition is dimmed and names where it came from, as in the load case.

Point axes
----------

A point's **Structural Connection** panel shows its axes: global, or tilted in the X-Z plane, as along
an incline. Click the pencil to open **Edit Axes** and set x′ at an angle or a slope, by eighth as a
force is entered, or turn the axes in 3D.

Forces at a tilted point can be entered along its axes (**Point Axes** in the force dialog). With
**Point Axes Components** on in **Show Loads**, forces are also drawn resolved along x′ and z′.
Choosing the **Local** reference frame draws them in the point's axes instead of the global ones.
