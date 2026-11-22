# Bonsai - OpenBIM Blender Add-on
# Copyright (C) 2026
#
# This file is part of Bonsai.
#
# Bonsai is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Bonsai is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Bonsai.  If not, see <http://www.gnu.org/licenses/>.
#
# This file was generated with the assistance of an AI coding tool.

import math
import re
from unittest import mock

import bpy
import ifcopenshell
import ifcopenshell.api.group
import ifcopenshell.api.root
import ifcopenshell.api.structural
import ifcopenshell.guid

import bonsai.tool as tool
from bonsai.bim.module.structural.decorator import LoadsDecorator
from bonsai.bim.module.structural.load_decoration_data import ShaderInfo
from bonsai.bim.module.structural.shader import DecorationShader
from test.bim.bootstrap import NewFile


class TestLinearLoadsForMemberWithoutMesh(NewFile):
    def _shader_info(self, ifc):
        member = ifc.createIfcStructuralCurveMember(
            GlobalId=ifcopenshell.guid.new(), PredefinedType="RIGID_JOINED_MEMBER"
        )
        action = ifc.createIfcStructuralLinearAction(GlobalId=ifcopenshell.guid.new(), PredefinedType="CONST")
        info = ShaderInfo()
        info.curve_members = {"1": {"member": member, "activities": [(action, 1.0)]}}
        return info, member

    def test_member_without_object(self):
        ifc = ifcopenshell.file()
        tool.Ifc.set(ifc)
        info, _ = self._shader_info(ifc)
        info.get_linear_loads()
        assert info.info == []

    def test_member_with_empty_mesh(self):
        ifc = ifcopenshell.file()
        tool.Ifc.set(ifc)
        info, member = self._shader_info(ifc)
        tool.Ifc.link(member, bpy.data.objects.new("Member", bpy.data.meshes.new("Member")))
        info.get_linear_loads()
        assert info.info == []


class TestMomentDetail(NewFile):
    """Moments about A at the origin: two inclined forces at P (4, 3), a level one at Q (0, 2), whose arm is its Δz,
    and a plumb one at Q, whose line of action passes through A"""

    def add_point(self, ifc, name, x, z):
        point = ifcopenshell.api.root.create_entity(ifc, ifc_class="IfcStructuralPointConnection", name=name)
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata([(0.0, 0.0, 0.0)], [], [])
        obj = bpy.data.objects.new(name, mesh)
        obj.location = (x, 0.0, z)
        bpy.context.scene.collection.objects.link(obj)
        tool.Ifc.link(point, obj)
        return point

    def setup_case(self):
        ifc = ifcopenshell.file(schema="IFC4")
        tool.Ifc.set(ifc)
        ifcopenshell.api.root.create_entity(ifc, ifc_class="IfcProject")
        points = {name: self.add_point(ifc, name, x, z) for name, x, z in (("A", 0, 0), ("P", 4, 3), ("Q", 0, 2))}
        bpy.context.view_layer.update()
        case = ifcopenshell.api.structural.add_structural_load_case(ifc, name="About A")
        tool.Structural.set_moment_centre(case, points["A"])
        self.activities = {}
        for name, point, x, z in (
            ("F1", "P", 3.0, 4.0),
            ("F2", "P", 1.0, -1.0),
            ("F3", "Q", 5.0, 0.0),
            ("F4", "Q", 0.0, -1.0),
        ):
            load = ifcopenshell.api.structural.add_structural_load(
                ifc, name=name, ifc_class="IfcStructuralLoadSingleForce"
            )
            ifcopenshell.api.structural.edit_structural_load(
                ifc, structural_load=load, attributes={"ForceX": x, "ForceZ": z}
            )
            activity = ifcopenshell.api.structural.add_structural_activity(
                ifc, applied_load=load, structural_member=points[point], ifc_class="IfcStructuralPointAction"
            )
            ifcopenshell.api.group.assign_group(ifc, products=[activity], group=case)
            self.activities[name] = activity.id()
        return case

    def draw(self, case, detail):
        """The moment diagram drawn for a report at a Moment Detail, as its entries and its labels' texts"""
        tool.Structural.get_structural_props().moment_detail = detail
        with mock.patch.object(DecorationShader, "new", return_value=None):
            drawing = ShaderInfo(case)
            drawing.update()
        moments = [e for e in drawing.info + drawing.text_info if str(e.get("object", "")).endswith(" moments")]
        return moments, [t["text"] for t in drawing.text_info if any(t is m for m in moments)]

    def test_full_draws_r_once_per_point_and_no_triangle_for_level_or_plumb_forces(self):
        moments, texts = self.draw(self.setup_case(), "FULL")
        # r to P, shared by F1 and F2, once; none to Q, whose level and plumb forces need no triangle.
        assert len([t for t in texts if re.match(r"r. = ", t)]) == 1
        assert len([t for t in texts if t.startswith("α")]) == 2  # Each inclined force's own angles.
        assert any(re.match(r"d. = Δz. = 2\.00", t) for t in texts)  # F3's arm.

    def test_a_force_through_the_centre_says_its_moment_is_zero(self):
        moments, texts = self.draw(self.setup_case(), "MINIMAL")
        assert any(re.fullmatch(r"M. = 0", t) for t in texts)

    def test_arms_leaves_out_the_triangles_and_minimal_the_arms(self):
        case = self.setup_case()
        moments, texts = self.draw(case, "ARMS")
        assert not any(re.match(r"[rs]. = ", t) or t.startswith(("α", "φ")) for t in texts)
        assert len([t for t in texts if re.match(r"d. = \d", t)]) == 2  # The inclined forces' arms.
        assert any(re.match(r"d. = Δz. = ", t) for t in texts)
        moments, texts = self.draw(case, "MINIMAL")
        assert not any(t.startswith(("d", "Δ")) for t in texts)
        # No construction, which is dashed: a report draws the members along the points too, solid.
        assert not any(e.get("primitive", {}).get("dashed") for e in moments)
        assert len([t for t in texts if re.match(r"M. = ", t)]) == 4
        assert any(t.startswith("ΣM") for t in texts)

    def test_a_sum_of_zero_is_drawn_as_a_full_circle_round_the_centre(self):
        case = self.setup_case()
        for activity in tool.Ifc.get().by_type("IfcStructuralActivity"):
            if activity.id() != self.activities["F4"]:  # Only the plumb force through A is left.
                ifcopenshell.api.group.unassign_group(tool.Ifc.get(), products=[activity], group=case)
        moments, texts = self.draw(case, "MINIMAL")
        assert any(re.fullmatch(r"M. = 0", t) for t in texts)
        lines = [e["primitive"] for e in moments if e.get("primitive", {}).get("type") == "LINE"]
        radii = {round(float(math.dist(line["start"], (0, 0, 0))), 6) for line in lines}
        assert len(lines) == 36 and len(radii) == 1  # A closed circle round A: an arc with a head has 26.

    def test_hovering_a_force_shows_all_of_its_own_detail(self):
        self.setup_case()
        props = tool.Structural.get_structural_props()
        props.moment_detail = "ARMS"
        entry = {"detail": 2, "detail_of": [self.activities["F1"]]}
        try:
            LoadsDecorator.hovered = None
            assert not LoadsDecorator.is_visible(entry)
            LoadsDecorator.hovered = {"moment_activity": self.activities["F2"]}
            assert not LoadsDecorator.is_visible(entry)
            LoadsDecorator.hovered = {"activity": self.activities["F1"]}
            assert LoadsDecorator.is_visible(entry)
            assert LoadsDecorator.is_visible({"detail": 1, "detail_of": [self.activities["F2"]]})
        finally:
            LoadsDecorator.hovered = None


class TestAppliedMomentArcInReports(NewFile):
    def test_a_couple_at_a_point_gets_an_arc_turning_its_way_in_reports_only(self):
        ifc = ifcopenshell.file(schema="IFC4")
        tool.Ifc.set(ifc)
        ifcopenshell.api.root.create_entity(ifc, ifc_class="IfcProject")
        point = ifcopenshell.api.root.create_entity(ifc, ifc_class="IfcStructuralPointConnection", name="A")
        mesh = bpy.data.meshes.new("A")
        mesh.from_pydata([(0.0, 0.0, 0.0)], [], [])
        obj = bpy.data.objects.new("A", mesh)
        bpy.context.scene.collection.objects.link(obj)
        tool.Ifc.link(point, obj)
        bpy.context.view_layer.update()
        case = ifcopenshell.api.structural.add_structural_load_case(ifc, name="Force and couple")
        load = ifcopenshell.api.structural.add_structural_load(ifc, name="F", ifc_class="IfcStructuralLoadSingleForce")
        # 90 down with a clockwise couple, as statics texts see the X-Z plane: IFC's MomentY turns Z to X.
        ifcopenshell.api.structural.edit_structural_load(
            ifc, structural_load=load, attributes={"ForceZ": -90.0, "MomentY": 27.45}
        )
        activity = ifcopenshell.api.structural.add_structural_activity(
            ifc, applied_load=load, structural_member=point, ifc_class="IfcStructuralPointAction"
        )
        ifcopenshell.api.group.assign_group(ifc, products=[activity], group=case)
        with mock.patch.object(DecorationShader, "new", return_value=None):
            drawing = ShaderInfo(case)
            drawing.update()
        arc = [e for e in drawing.info if e.get("report_only")]
        assert arc and all(e.get("object") == "A" for e in arc)
        (head,) = [e["primitive"] for e in arc if e["primitive"]["type"] == "ARROW"]
        # Turning clockwise from below right, it ends above right, at 45 degrees.
        assert head["tip"][0] > 0 and head["tip"][2] > 0
        assert not LoadsDecorator.is_visible(arc[0])
