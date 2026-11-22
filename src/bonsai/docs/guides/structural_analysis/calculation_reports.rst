.. This file was generated with the assistance of an AI coding tool.

Calculation reports
===================

Bonsai can write the calculations for the point forces in an analysis model as a report: a
diagram of the forces at each point, a table of them, and the steps that add them up, set out
as a statics textbook would, and the moments about each load case's moment centre.

Exporting a report
------------------

1. Make the analysis model current in the **Structural Analysis Models** panel.
2. In the **Show Loads** panel, choose how the forces are drawn. The report's diagrams use
   the same settings as the viewport: components, parallelogram or tip to tail, angles,
   slopes, decimal places, **Label Size**, **Arrow Thickness** and **Moment Detail**.
3. Turn on **Detailed Steps** to include the working between the main steps, in grey.
4. Click **Export Calculations** and choose a folder. Tick **Selected Items Only** to report
   only the structural items selected. Bonsai writes a ``<model>_calcs`` folder there, opens
   its ``index.html`` in your browser, and also writes ``report.md`` with the same content,
   for Git forges such as GitHub and Forgejo.

The HTML page renders its math with a copy of KaTeX that is bundled in the folder, so the
report reads offline and can be printed to PDF from the browser. Diagrams are SVG files in
``diagrams/``, drawn on white so that they read on dark pages too.

What a report contains
----------------------

For each load case, each point with forces gets:

- A **diagram** of the forces, drawn from the viewport's own drawing, with each force and
  component named as in the steps. A couple at the point is drawn as a curved arrow turning
  its way.
- A **table** of the forces, any couples, and their resultant: magnitude, and direction as an
  angle from the axis of the eighth (Q1 to Q8) the force points into, or as a slope. A couple's
  direction is clockwise or counter-clockwise.
- The **steps**: each force's components, their sums along X and Z, and the resultant's
  magnitude and angle. Forces entered as a slope are resolved by the ratios of the slope's
  sides. If the point carries a couple, the resultant is stated with it, as **R = 90.00 kN …
  with a couple M = −27450.00 kN.mm (clockwise)**.

Values that were unknown and found with **Edit Resultant** are solved first, as the problem
was posed, and shown in bold with 🔓. Linked magnitudes are stated, as **magnitude = 0.25 ×
F₂**. A point whose axes are tilted, as along an incline, also gets its forces resolved along
those axes, with a second diagram.

Notes under a table explain what it uses:

- A push added to other forces is added as a pull along its line of action, by the principle
  of transmissibility.
- A moved load, marked **←** and drawn with a dashed shaft, is the equivalent of the named
  load case's loads moved there.
- A shared load, tagged ① to ⑳, is one load definition acting at several points.

Moments
-------

A load case with a moment centre also gets a moments section:

- A **diagram** of the moments about the centre, with the members along the points, each
  point's name, and each force at its point to scale, drawn as **Moment Detail** sets.
- A **table** of each force: where it acts, its magnitude, its Δx and Δz from the centre, its
  moment arm d and its moment. Couples are listed as applied moments.
- The **steps**: each force's arm, found from Δx and Δz or by the right triangle, its moment
  as F d, and again by Varignon's theorem as F\ :sub:`z` Δx − F\ :sub:`x` Δz, then the sum
  ΣM. A sum kept with **Edit Resultant Moment** is followed by the steps that find its unknown.

Example
-------

:download:`two-forces-on-slopes.ifc <files/two-forces-on-slopes.ifc>` has two forces on one
point: 500 lbf down and to the left on a 3:4 slope, and 300 lbf down and to the right on a
2:3 slope. Their resultant is found from their components.

.. figure:: images/two-forces-report.png
   :alt: Calculation report for two forces on slopes, with a diagram, a table and the steps

   The report as exported

.. figure:: images/two-forces-report-detailed.png
   :alt: The same report with Detailed Steps turned on

   With **Detailed Steps** on, each step's working is shown beneath it in grey
