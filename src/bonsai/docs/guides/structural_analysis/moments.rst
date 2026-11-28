.. This file was generated with the assistance of an AI coding tool.

Moments
=======

Bonsai takes the moments of a load case's point forces about a point, its **moment centre**, written A
in the drawing unless the point has a name. Each force's moment is drawn with its line of action and
moment arm, and their sum as a curved arrow round the centre.

Moments are counter-clockwise positive, as the X-Z plane is seen from −Y, as statics texts take them.
They are in the force unit times the project's length unit, unless the project declares a torque unit.

Choosing the moment centre
--------------------------

Each load case has its own moment centre. Set it:

- While editing the load case, under **Moments About**: choose a point from the menu, or click the
  **eyedropper** and click the point in the viewport.
- In **Show Loads**, for the load case shown: select a point and click **Take Moments About Selected
  Point**. The **✕** beside it stops taking moments.

To take moments about several points, duplicate the load case and give each copy its own centre. The
copies share their load definitions, so the loads stay the same in all of them.

A point's **Applied Loads** panel lists, under **Moments About This Point**, each load case taking
moments about it, with its sum.

The moment drawing
------------------

For each force, as the **Moment Detail** setting in **Show Loads** allows:

- Its **moment**, M₁, M₂…, beside the force's value.
- Its **line of action**, dashed, and its **moment arm** d from the centre, square to it, with a right
  angle mark.
- For a level or plumb force, the arm is its Δz or Δx, dimensioned as **d = Δz** or **d = Δx**.
- For an inclined force, the right triangle that finds its arm, as a textbook draws it: **r** from
  the centre to the force's point, **s** along the line of action to the arm's foot, and the angles **φ**
  at the point and **α** at the centre, with r's run and rise, Δx and Δz.

At the centre, a curved arrow turning the way the sum does, labelled **ΣM_A**. A sum of zero is drawn as
a full circle without an arrowhead. A force whose line of action passes through the centre is labelled
**M = 0**.

Moment Detail
~~~~~~~~~~~~~

**Moment Detail** chooses how much is drawn:

=========== ===============================================================================
Minimal     Each moment and their sum
Arms        Also each line of action and moment arm, with d, as statics texts draw them
Full        Also the triangle that finds an inclined force's arm, r, s, φ and α, and the
            dimension of r along the other axis
=========== ===============================================================================

**Arms** is the default. Hover a force's arrow, its moment lines or its moment's value to see all of
that force's working, whatever the setting.

A level or plumb force never gets the triangle, as its arm is simply its Δz or Δx. Forces at the same
point share one r, drawn once.

Moving the moment centre
------------------------

Click a moment's lines or its value to open **Edit Moment Centre**. It moves the centre, previewing the
moments:

- **From** a loaded point, by **Components** (Δx and Δz), **Angle** or **Slope**, as a force is
  entered.
- Or by a force's moment arm: **d**, the arm, sliding the centre along the line of action; **s**,
  along the line of action; **φ** or **α**, swinging the centre round the force's point.

For a point with tilted axes, Δx′ and Δz′ along them can be entered too. Click a dimension in the
drawing, such as Δx or s, to open the dialog with that value ready to type.

Kept moments
------------

Click the sum at the centre, or **Edit Resultant Moment** (the vortex button in **Moments About This
Point**), to set the sum of the moments, as a problem gives it, such as ΣM = 0 for a body that does
not turn. One value is then found to make it:

- A force's **magnitude** or **direction**, unlocked as in :doc:`resultants`.
- Where a force acts: its point's **X Position** or **Z Position**, which moves the point.
- Where the centre is: its moment arm **d**, its distance **r**, or the angle of r (**φ**, **α**),
  unlocked in **Edit Moment Centre**.

The sum is kept, marked 🔒, and solved again as the model changes:

- Editing a load re-solves it, previewed in **Edit Structural Load** as you type.
- Moving a structural point with Bonsai's move tool re-solves it once the move is confirmed.
- Moving one by other means, as by typing its location, shows **Keep Moments\*** in **Show Loads**.
  Click it to re-solve; until then the drawing shows the moments as they would be kept.

Placing a point
---------------

Statics problems often give a point's place by a distance and a direction from another, rather than by
coordinates. Select the point and click **Place Point** in its **Applied Loads** panel:

- **From**: the point it is placed from.
- **Input**: **Components** (Δx and Δz), **Angle** or **Slope**, by eighth, as a force's direction
  is entered.
- **Length**, with **Angle** or **Slope**: the **Distance** along the direction, or follow the
  direction until a **Δx** or **Δz**, as along a member's slope up to a given height. **Measured From**
  sets the point the Δx or Δz is measured from, which need not be the point placed from.

The point and its moments are previewed as you edit, and kept moments follow it.

Couples
-------

A couple, a moment applied as a load, is entered with **Moment** in the force dialog, with a force or
on its own. It is the same about any point, so it is counted as it is in every moment taken:

- In the viewport, it is labelled at its point and marked **(applied)** in the moment drawing.
- It is a term of ΣM in the drawing and in reports.
- A point's resultant names it, as **R = 10.00 kip … with a couple M = −50.00 kip.ft (clockwise)**.

Moving loads to a point
-----------------------

A force can be replaced by the same force at another point with the couple that moving it adds, as an
**equivalent force-couple system**. Bonsai does this for a whole load case: click **Move Loads to
Point** on a load case's row and choose:

- **To Point**: where the loads go. It starts on the load case's moment centre.
- **Into**: a new load case, named in **New Load Case**, or an existing one.

The load case's point loads are added up into one force at that point, with the couple their moments
about it make. The result is a **moved load**:

- It is kept in step with the loads it came from: after any change, to a load or a point, it is
  rewritten. It is meant for design, where loads change, not only for a one-off answer.
- It is drawn with a dashed shaft and labelled **← LC_1**, after the load case it came from.
- In the load lists it is dimmed and names its source. It is not meant to be edited by hand.
- Removing it, or the load case it is in, removes it from the record of moved loads too, and removes
  the load definition the move made, unless you have applied that definition somewhere else.

Where the resultant acts
~~~~~~~~~~~~~~~~~~~~~~~~

Loads at several points, such as two columns on a combined footing, can also be replaced by one
force with no couple, acting where its moment about any point is theirs. Tick **Where the Couple Is
Zero** in **Move Loads to Point**: the dialog shows where that is, as Δx and Δz from **To Point**,
and the loads are moved to a new point there, named in **New Point**, on their resultant's line of
action: where it crosses the line through the loads' points, if they lie on one, as along a footing
or a beam, even a sloping one; or else at its nearest to To Point. The dialog says which.

For a plumb resultant that is Δx = M/R\ :sub:`z` along the level through To Point, as for 20 k and
60 k down 12 ft apart: M = −720 k-ft about the first, R = −80 k, so Δx = 9 ft. A level resultant is
found up or down from it, and a sloping one square to its line of action.

With its load case shown, a string of dimensions along the line square to the resultant gives where
it is from each of the loads' points, with their overall length beyond, as 9.00 and 3.00 ft between
the two columns, 12.00 ft apart.

The new point follows: when a load changes or a point moves, it is moved back onto the resultant's
line of action, measured again from To Point, so that the couple stays zero. Loads that add to no
force, a couple, have no single resultant, and the dialog says so; if they come to that later, the
point stays where it was.
