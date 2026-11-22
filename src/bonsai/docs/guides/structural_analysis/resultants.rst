.. This file was generated with the assistance of an AI coding tool.

Resultants and unknowns
=======================

The forces at a point add up to their **resultant**, drawn in white from the point. Bonsai can also
work the other way, as statics problems often do: given what is known of the forces and the resultant,
find what is not.

Known and unknown values
------------------------

Each force has two values that can be known or unknown: its **magnitude** and its **direction**. Set
them with **Magnitude Known** and **Direction Known** in the force dialog, or with the padlocks in
**Edit Resultant**.

An unknown value is marked in the drawing, and in reports, with an open padlock 🔓 once it has been
found.

Edit Resultant
--------------

Click a point's resultant arrow, or the pencil beside a load case's resultant in the point's **Applied
Loads** panel, to open **Edit Resultant**. The pencil also works when the forces are in equilibrium and
there is no arrow to click.

The dialog shows:

- The resultant, entered as a force is: by components, angle or slope, with its own **Magnitude
  Known** and **Direction Known**.
- Each force at the point, numbered F₁, F₂… tip to tail as reports number them, with a padlock for its
  magnitude and one for its direction.
- What solving gives: each changed force, old value to new, and the resultant found.

Two values can be found in all, as two equations, ΣFx and ΣFz, find two unknowns. For example:

- The resultant known in full, and two force magnitudes unknown.
- The resultant's direction known, its magnitude unknown, and one force's magnitude unknown.
- One force entirely unknown, magnitude and direction, found from the resultant.

If the values cannot be solved, as when there are too many unknowns, or two on parallel lines, the
dialog says which values are unknown and why.

Solving changes only the loads at this point. A load definition shared with applied loads elsewhere
gets its own copy first, and the dialog says so. A force that solves negative is reversed, and the
dialog warns that a pull becomes a push.

Loads that carry a factor in their load case, from a load group's coefficient or a factored
assignment, are solved as drawn, times their factor, and their own values written back.

The resultant's angle
---------------------

A resultant's angle is measured from the axis of the eighth it points into, as forces are. Clicking an
angle in the other eighth of the same quarter, as 30° from −X rather than 60° from −Z, keeps that
choice: the drawing, the dialog and reports measure the resultant from it from then on.

Kept resultants
---------------

The resultant set in **Edit Resultant** is kept. When a force at the point changes later, or one is
added, the unknowns are solved again so that the resultant stays as set. **Edit Structural Load**'s
preview shows them moving as you type.

A force found to be zero keeps the direction it was named with, so that solving again can bring it
back the same way.

Linked magnitudes
-----------------

**Magnitude As**, in the force dialog, ties one force's magnitude to another's at the same point:
equal, as the two tensions of one cable over a pulley, or by a **Ratio**, as 0.25 for a quarter of
it. Linked magnitudes count as one unknown: solving finds one value for both, and a force linked to a
known one simply follows it.

Reports state the link, as **magnitude = 0.25 × F₂**.

Known components
----------------

**Given** in the force dialog can be a component instead of the magnitude: the **X** or **Z** of the
force, as a horizontal or vertical capacity. The magnitude follows from it and the direction, and
reports show it found from the component.
