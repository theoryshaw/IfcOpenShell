Structural analysis
===================

This section covers the structural analysis capabilities in Bonsai.

.. include:: /_incomplete_message.rst

Overview
--------

Bonsai can build a structural analysis model alongside the building model: points, members and their
supports, the loads on them grouped into load cases, and the forces and moments those loads make. The
loads are drawn in the viewport as a statics textbook draws them, to scale, with their angles, slopes,
components and resultants, and moments about a chosen point with their moment arms. They can be solved
for unknown values and written out as a calculation report.

Everything is stored in the IFC file: analysis models, load cases, applied loads and load definitions
are IFC entities, so the loads travel with the model to other software.

Key features
------------

- Analysis models, load cases and load groups, with structural items assigned to them
- Point forces entered by components, angle or slope, along global axes or a point's own tilted axes
- Couples, applied moments, as loads
- Loads drawn to scale in the viewport, picked there to edit, and moved with their points
- Several load cases shown at once, and a single load shown on its own
- Resultants of the forces at a point, with unknown magnitudes and directions solved for
- Moments about a point, with their arms, kept at a set value as the model changes
- A load case's loads moved to a point as a force and a couple, kept in step with them
- Calculation reports in HTML and Markdown, with diagrams and the steps of each calculation

Getting started
---------------

1. Create structural points and members, or open a model that has them.
2. Select a point and click **Apply Structural Load** (the **+** in the **Applied Loads** panel of its
   object properties). If there is no analysis model or load case yet, one is made for you.
3. Turn on **Show Loads** in the **Show Loads** panel to see the loads in the viewport.
4. Click a load's arrow to edit it, or its value to type over it.
5. To take moments, choose a point under **Moments About** while editing the load case.
6. Click **Export Calculations** to write the report.

.. toctree::
   :maxdepth: 1

   loads
   showing_loads
   resultants
   moments
   calculation_reports

.. seealso::
   - :doc:`/guides/authoring/index`
   - :doc:`/guides/authoring/advanced_modeling/index`
