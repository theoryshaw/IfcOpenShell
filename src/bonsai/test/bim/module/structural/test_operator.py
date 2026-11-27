# This file was generated with the assistance of an AI coding tool.

import math
from types import SimpleNamespace
from unittest import mock

import bpy
import ifcopenshell
import ifcopenshell.api.group
import ifcopenshell.api.root
import ifcopenshell.api.structural
import ifcopenshell.api.unit
import ifcopenshell.guid
import ifcopenshell.util.element
import ifcopenshell.util.structural
import pytest
from mathutils import Vector

import bonsai.tool as tool
from bonsai.bim.module.structural.data import LoadGroupDecorationData
from bonsai.bim.module.structural.decorator import LoadsDecorator
from bonsai.bim.module.structural.operator import PickStructuralLoads, get_load_unit_symbol
from test.bim.bootstrap import NewFile


class TestLoadBoundaryConditions(NewFile):
    def test_filtering_duplicate_names(self):
        ifc = ifcopenshell.file(schema="IFC4")
        tool.Ifc.set(ifc)
        ifc.createIfcBoundaryNodeCondition(Name="Fixed")
        ifc.createIfcBoundaryNodeCondition(Name="Fixed")
        ifc.createIfcBoundaryNodeCondition(Name="Pinned")
        props = tool.Structural.get_structural_props()
        props.filtered_boundary_conditions = True
        bpy.ops.bim.load_boundary_conditions()
        assert sorted(c.name for c in props.boundary_conditions) == ["Pinned"]


class TestEnableEditingStructuralItemAxis(NewFile):
    def test_starting_square_to_a_member_stood_up_along_its_axis(self):
        bpy.ops.bim.create_project()
        props = tool.Root.get_root_props()
        props.ifc_product, props.ifc_class, props.representation_template = (
            "IfcStructuralItem",
            "IfcStructuralCurveMember",
            "EDGE",
        )
        bpy.ops.bim.add_element(skip_dialog=True)
        member = tool.Ifc.get().by_type("IfcStructuralCurveMember")[0]
        obj = tool.Ifc.get_object(member)
        bpy.context.view_layer.objects.active = obj
        obj.data.vertices[1].co = obj.data.vertices[0].co + Vector((0.0, 0.0, 3.0))
        assert member.Axis.DirectionRatios == (0.0, 0.0, 1.0)  # Now parallel to the member.

        bpy.ops.bim.enable_editing_structural_item_axis()
        empty = tool.Structural.get_object_structural_props(obj).axis_empty
        x, y, z = (empty.matrix_world.col[i].to_3d() for i in range(3))
        assert abs(x.dot(Vector((0.0, 0.0, 1.0)))) == pytest.approx(1.0)
        assert y.length == pytest.approx(1.0)
        assert abs(z.dot(x)) < 1e-6

        bpy.ops.bim.edit_structural_item_axis()
        assert abs(Vector(member.Axis.DirectionRatios).normalized().z) < 1e-6

    def add_member(self) -> tuple:
        props = tool.Root.get_root_props()
        props.ifc_product, props.ifc_class, props.representation_template = (
            "IfcStructuralItem",
            "IfcStructuralCurveMember",
            "EDGE",
        )
        bpy.ops.bim.add_element(skip_dialog=True)
        member = tool.Ifc.get().by_type("IfcStructuralCurveMember")[-1]
        obj = tool.Ifc.get_object(member)
        bpy.context.view_layer.objects.active = obj
        return member, obj

    def test_keeping_the_axis_of_a_member_rotated_as_a_whole(self):
        # Axis is relative to the member's placement, as its edge is, so it turns with the member.
        bpy.ops.bim.create_project()
        member, obj = self.add_member()
        obj.rotation_euler = (0.0, math.radians(90), 0.0)
        obj.location = (2.0, 3.0, 4.0)
        bpy.context.view_layer.update()
        bpy.ops.bim.enable_editing_structural_item_axis()
        empty = tool.Structural.get_object_structural_props(obj).axis_empty
        assert tool.Structural.get_object_structural_props(obj).axis_angle == pytest.approx(0.0)
        # At the edge's start, wherever the member is.
        assert (empty.matrix_world.translation - obj.matrix_world @ obj.data.vertices[0].co).length < 1e-6
        bpy.ops.bim.edit_structural_item_axis()
        assert tuple(Vector(member.Axis.DirectionRatios)) == pytest.approx((0.0, 0.0, 1.0), abs=1e-6)

    def test_projecting_an_axis_nearly_along_the_member(self):
        bpy.ops.bim.create_project()
        member, obj = self.add_member()
        angle = math.radians(1)
        ifcopenshell.api.structural.edit_structural_item_axis(
            tool.Ifc.get(), structural_item=member, axis=(math.cos(angle), 0.0, math.sin(angle))
        )
        bpy.ops.bim.enable_editing_structural_item_axis()
        bpy.ops.bim.edit_structural_item_axis()
        assert tuple(Vector(member.Axis.DirectionRatios)) == pytest.approx((0.0, 0.0, 1.0), abs=1e-6)

    def test_rolling_the_axis_about_the_member(self):
        bpy.ops.bim.create_project()
        member, obj = self.add_member()
        obj.rotation_euler = (0.0, 0.0, math.radians(90))  # Along world Y; the roll is about the member itself.
        bpy.context.view_layer.update()
        bpy.ops.bim.enable_editing_structural_item_axis()
        tool.Structural.get_object_structural_props(obj).axis_angle = 90.0
        bpy.ops.bim.edit_structural_item_axis()
        assert tuple(Vector(member.Axis.DirectionRatios)) == pytest.approx((0.0, -1.0, 0.0), abs=1e-6)


class TestAddCurveItem(NewFile):
    def test_adding_a_curve_member_in_ifc2x3_which_has_no_axis(self):
        tool.Project.get_project_props().export_schema = "IFC2X3"
        bpy.ops.bim.create_project()
        props = tool.Root.get_root_props()
        props.ifc_product, props.ifc_class, props.representation_template = (
            "IfcStructuralItem",
            "IfcStructuralCurveMember",
            "EDGE",
        )
        bpy.ops.bim.add_element(skip_dialog=True)
        assert tool.Ifc.get().by_type("IfcStructuralCurveMember")


class TestLoadStructuralLoads(NewFile):
    def test_unused_only(self):
        ifc = ifcopenshell.file(schema="IFC4")
        tool.Ifc.set(ifc)
        point = ifcopenshell.api.root.create_entity(ifc, ifc_class="IfcStructuralPointConnection")
        used = ifcopenshell.api.structural.add_structural_load(
            ifc, name="Used", ifc_class="IfcStructuralLoadSingleForce"
        )
        ifcopenshell.api.structural.add_structural_load(ifc, name="Unused", ifc_class="IfcStructuralLoadSingleForce")
        activity = ifcopenshell.api.structural.add_structural_activity(
            ifc, applied_load=used, structural_member=point, ifc_class="IfcStructuralPointAction"
        )
        case = ifcopenshell.api.structural.add_structural_load_case(ifc, name="Case")
        ifcopenshell.api.group.assign_group(ifc, products=[activity], group=case)
        props = tool.Structural.get_structural_props()
        props.show_unused_loads_only = True  # Which lists the loads again.
        assert [load.name for load in props.structural_loads] == ["Unused"]
        props.show_unused_loads_only = False
        assert sorted(load.name for load in props.structural_loads) == ["Unused", "Used"]

    def test_clicking_a_load_selects_the_items_it_is_applied_to(self):
        ifc = ifcopenshell.file(schema="IFC4")
        tool.Ifc.set(ifc)
        shared = ifcopenshell.api.structural.add_structural_load(
            ifc, name="Shared", ifc_class="IfcStructuralLoadSingleForce"
        )
        ifcopenshell.api.structural.add_structural_load(ifc, name="Unused", ifc_class="IfcStructuralLoadSingleForce")
        objects = {}
        for name in ("A", "B", "C"):
            element = ifcopenshell.api.root.create_entity(ifc, ifc_class="IfcStructuralPointConnection", name=name)
            obj = bpy.data.objects.new(name, None)
            bpy.context.scene.collection.objects.link(obj)
            tool.Ifc.link(element, obj)
            objects[name] = obj
        for name in ("A", "B"):
            ifcopenshell.api.structural.add_structural_activity(
                ifc,
                applied_load=shared,
                structural_member=tool.Ifc.get_entity(objects[name]),
                ifc_class="IfcStructuralPointAction",
            )
        objects["C"].select_set(True)
        bpy.ops.bim.load_structural_loads()
        props = tool.Structural.get_structural_props()
        names = [load.name for load in props.structural_loads]
        props.active_structural_load_index = names.index("Shared")
        assert sorted(obj.name for obj in bpy.context.selected_objects) == ["A", "B"]
        assert bpy.context.view_layer.objects.active in (objects["A"], objects["B"])
        props.active_structural_load_index = names.index("Unused")
        assert not bpy.context.selected_objects
        bpy.ops.bim.click_structural_load(index=names.index("Shared"))
        assert sorted(obj.name for obj in bpy.context.selected_objects) == ["A", "B"]


class TestSoloingALoad(NewFile):
    """Problem 2.24's 10 k square to the chord at P, 14 out and 8 down from A, level with B: one load definition in
    "About A" and "About B", with 4 k down at Q, 14 out and 16 down, in "About A" only"""

    def add_point(self, ifc, name, x, z):
        point = ifcopenshell.api.root.create_entity(ifc, ifc_class="IfcStructuralPointConnection", name=name)
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata([(0.0, 0.0, 0.0)], [], [])
        obj = bpy.data.objects.new(name, mesh)
        obj.location = (x, 0.0, z)
        bpy.context.scene.collection.objects.link(obj)
        tool.Ifc.link(point, obj)
        return point

    def apply(self, ifc, load, point, case):
        activity = ifcopenshell.api.structural.add_structural_activity(
            ifc, applied_load=load, structural_member=point, ifc_class="IfcStructuralPointAction"
        )
        ifcopenshell.api.group.assign_group(ifc, products=[activity], group=case)

    def setup_cases(self):
        ifc = ifcopenshell.file(schema="IFC4")
        tool.Ifc.set(ifc)
        ifcopenshell.api.root.create_entity(ifc, ifc_class="IfcProject")
        points = {
            "A": self.add_point(ifc, "A", 0.0, 0.0),
            "B": self.add_point(ifc, "B", 0.0, -8.0),
            "P": self.add_point(ifc, "P", 14.0, -8.0),
            "Q": self.add_point(ifc, "Q", 14.0, -16.0),
        }
        bpy.context.view_layer.update()
        about_a = ifcopenshell.api.structural.add_structural_load_case(ifc, name="About A")
        about_b = ifcopenshell.api.structural.add_structural_load_case(ifc, name="About B")
        tool.Structural.set_moment_centre(about_a, points["A"])
        tool.Structural.set_moment_centre(about_b, points["B"])
        ten = ifcopenshell.api.structural.add_structural_load(
            ifc, name="10 k", ifc_class="IfcStructuralLoadSingleForce"
        )
        c = 10.0 / math.sqrt(2)
        ifcopenshell.api.structural.edit_structural_load(
            ifc, structural_load=ten, attributes={"ForceX": c, "ForceZ": c}
        )
        four = ifcopenshell.api.structural.add_structural_load(
            ifc, name="4 k", ifc_class="IfcStructuralLoadSingleForce"
        )
        ifcopenshell.api.structural.edit_structural_load(ifc, structural_load=four, attributes={"ForceZ": -4.0})
        for case in (about_a, about_b):
            self.apply(ifc, ten, points["P"], case)
        self.apply(ifc, four, points["Q"], about_a)
        LoadGroupDecorationData.is_loaded = False
        bpy.ops.bim.load_structural_loads()
        props = tool.Structural.get_structural_props()
        index = [load.name for load in props.structural_loads].index("10 k")
        return ifc, about_a, about_b, ten, four, index

    def test_shift_click_solos_and_again_brings_back_what_was_shown(self):
        ifc, about_a, about_b, ten, four, index = self.setup_cases()
        props = tool.Structural.get_structural_props()
        assert not props.show_loads
        with mock.patch.object(LoadsDecorator, "update"):
            bpy.ops.bim.click_structural_load(index=index, solo=True)
            assert tool.Structural.get_solo_load() == ten
            assert props.show_loads
            assert [obj.name for obj in bpy.context.selected_objects] == ["P"]  # Its item selected and active.
            assert bpy.context.view_layer.objects.active.name == "P"
            bpy.ops.bim.click_structural_load(index=index, solo=True)
            assert tool.Structural.get_solo_load() is None
            assert not props.show_loads

    def test_an_applied_loads_button_selects_its_item_and_with_shift_solos_its_load(self):
        ifc, about_a, about_b, ten, four, index = self.setup_cases()
        activity = next(a for a in ifc.by_type("IfcStructuralActivity") if a.AppliedLoad == four)
        with mock.patch.object(LoadsDecorator, "update"):
            bpy.ops.bim.click_structural_activity(activity=activity.id())
            assert [obj.name for obj in bpy.context.selected_objects] == ["Q"]
            assert bpy.context.view_layer.objects.active.name == "Q"
            assert tool.Structural.get_solo_load() is None
            bpy.ops.bim.click_structural_activity(activity=activity.id(), solo=True)
            assert tool.Structural.get_solo_load() == four
            bpy.ops.bim.click_structural_activity(activity=activity.id(), solo=True)
            assert tool.Structural.get_solo_load() is None

    def test_showing_a_load_case_ends_the_solo(self):
        ifc, about_a, about_b, ten, four, index = self.setup_cases()
        with mock.patch.object(LoadsDecorator, "update"):
            bpy.ops.bim.click_structural_load(index=index, solo=True)
            bpy.ops.bim.show_structural_load_case(load_case=about_b.id())
            assert tool.Structural.get_solo_load() is None
            props = tool.Structural.get_structural_props()
            assert props.show_loads and props.load_group_to_show == str(about_b.id())
            bpy.ops.bim.click_structural_load(index=index, solo=True)
            bpy.ops.bim.end_structural_load_solo()
            assert props.show_loads and props.load_group_to_show == str(about_b.id())  # As it was before.

    def test_the_soloed_load_is_drawn_alone_and_once_naming_its_load_cases(self):
        from bonsai.bim.module.structural.shader import DecorationShader

        ifc, about_a, about_b, ten, four, index = self.setup_cases()
        with mock.patch.object(DecorationShader, "new", return_value=None):
            LoadsDecorator.update_solo(ten)
        values = [t["text"] for t in LoadsDecorator.text_info if t.get("force_of")]
        assert len(values) == 1 and values[0].startswith("About A, About B: ")
        assert any(e.get("primitive", {}).get("type") == "ARROW" for e in LoadsDecorator.shader_info)
        # Only the 10 k at P: not the 4 k at Q, nor either load case's moments, which are drawn about A and B.
        drawn = LoadsDecorator.shader_info + LoadsDecorator.text_info
        assert {e.get("object") for e in drawn} == {"P"}
        LoadsDecorator.shader_info, LoadsDecorator.text_info, LoadsDecorator.pickables = [], [], []


class TestShowingSeveralLoadCases(NewFile):
    """Eyes show several load cases at once, one of them active, whose moments are drawn"""

    def setup_cases(self):
        ifc = ifcopenshell.file(schema="IFC4")
        tool.Ifc.set(ifc)
        model = ifcopenshell.api.structural.add_structural_analysis_model(ifc)
        cases = [ifcopenshell.api.structural.add_structural_load_case(ifc, name=n) for n in ("A", "B", "C")]
        model.LoadedBy = cases
        LoadGroupDecorationData.is_loaded = False
        props = tool.Structural.get_structural_props()
        props.activity_type = "Action"
        props.show_loads = False
        tool.Structural.set_also_shown_ids([])
        return cases, props

    def click(self, case, mode="CLICK"):
        bpy.ops.bim.show_structural_load_case(load_case=case.id(), mode=mode)

    def state(self, props):
        active = props.load_group_to_show if props.show_loads else None
        return active, tool.Structural.get_also_shown_ids() if props.show_loads else []

    def test_clicking_eyes_shows_several_with_the_last_active(self):
        (a, b, c), props = self.setup_cases()
        self.click(a)
        assert self.state(props) == (str(a.id()), [])
        self.click(b)  # Shown with A, as the active one.
        assert self.state(props) == (str(b.id()), [a.id()])
        self.click(a)  # Shown already: made active again.
        assert self.state(props) == (str(a.id()), [b.id()])
        self.click(a)  # The active one hidden: B takes its place.
        assert self.state(props) == (str(b.id()), [])

    def test_shift_shows_or_hides_without_changing_the_active_one(self):
        (a, b, c), props = self.setup_cases()
        self.click(a)
        self.click(b, "TOGGLE")
        self.click(c, "TOGGLE")
        assert self.state(props) == (str(a.id()), [b.id(), c.id()])
        self.click(b, "TOGGLE")
        assert self.state(props) == (str(a.id()), [c.id()])

    def test_ctrl_shows_only_one_and_hide_all_hides_all(self):
        (a, b, c), props = self.setup_cases()
        self.click(a)
        self.click(b)
        self.click(c, "ONLY")
        assert self.state(props) == (str(c.id()), [])
        self.click(a, "TOGGLE")
        bpy.ops.bim.hide_structural_load_cases()
        assert not props.show_loads and tool.Structural.get_also_shown_ids() == []

    def test_a_removed_load_case_is_no_longer_shown(self):
        (a, b, c), props = self.setup_cases()
        self.click(a)
        self.click(b, "TOGGLE")
        ifcopenshell.api.structural.remove_structural_load_case(tool.Ifc.get(), load_case=b)
        assert tool.Structural.get_also_shown_load_groups() == []


class TestShowStructuralLoadCase(NewFile):
    def test_showing_and_hiding_a_load_case(self):
        ifc = ifcopenshell.file(schema="IFC4")
        tool.Ifc.set(ifc)
        model = ifcopenshell.api.structural.add_structural_analysis_model(ifc)
        case = ifcopenshell.api.structural.add_structural_load_case(ifc, name="Case")
        model.LoadedBy = [case]
        LoadGroupDecorationData.is_loaded = False
        props = tool.Structural.get_structural_props()
        props.activity_type = "Action"
        bpy.ops.bim.show_structural_load_case(load_case=case.id())
        assert props.show_loads and props.load_group_to_show == str(case.id())
        # Clicking the open eye of the case shown hides the loads.
        bpy.ops.bim.show_structural_load_case(load_case=case.id())
        assert not props.show_loads

    def test_apply_load_offers_the_load_case_shown_first(self):
        from bonsai.bim.module.structural.operator import get_shown_apply_load_group

        ifc = ifcopenshell.file(schema="IFC4")
        tool.Ifc.set(ifc)
        model = ifcopenshell.api.structural.add_structural_analysis_model(ifc)
        first = ifcopenshell.api.structural.add_structural_load_case(ifc, name="About B")
        second = ifcopenshell.api.structural.add_structural_load_case(ifc, name="Pair at B")
        model.LoadedBy = [first, second]
        LoadGroupDecorationData.is_loaded = False
        props = tool.Structural.get_structural_props()
        props.activity_type = "Action"
        assert get_shown_apply_load_group(None, bpy.context) is None  # No eye open.
        bpy.ops.bim.show_structural_load_case(load_case=second.id())
        assert get_shown_apply_load_group(None, bpy.context) == str(second.id())
        bpy.ops.bim.show_structural_load_case(load_case=second.id())  # Hidden again.
        assert get_shown_apply_load_group(None, bpy.context) is None


def region(type, x, y, width, height, data=None):
    return SimpleNamespace(type=type, x=x, y=y, width=width, height=height, data=data)


class TestGetViewUnderMouse:
    def get(self, regions, x, y):
        area = SimpleNamespace(type="VIEW_3D", regions=regions)
        context = SimpleNamespace(window=SimpleNamespace(screen=SimpleNamespace(areas=[area])))
        return PickStructuralLoads.get_view_under_mouse(None, context, SimpleNamespace(mouse_x=x, mouse_y=y))

    def test_the_view_of_the_quarter_of_a_quad_view_under_the_mouse(self):
        left, right = region("WINDOW", 0, 0, 100, 100, "left"), region("WINDOW", 100, 0, 100, 100, "right")
        assert self.get([left, right], 150, 50)[1:] == (right, "right")

    def test_not_under_a_sidebar_lying_over_the_view(self):
        view = region("WINDOW", 0, 0, 200, 100, "view")
        sidebar = region("UI", 150, 0, 50, 100)
        assert self.get([view, sidebar], 175, 50) is None
        assert self.get([view, sidebar], 75, 50)[1] is view

    def test_a_hidden_sidebar_takes_nothing(self):
        view = region("WINDOW", 0, 0, 200, 100, "view")
        assert self.get([view, region("UI", 199, 0, 1, 100)], 199, 50)[1] is view


class TestPickLoads:
    def pick(self, x, y):
        LoadsDecorator.shader_info = [{}]
        LoadsDecorator.pickables = [{"tail": (0.0, 0.0, 0.0), "tip": (100.0, 0.0, 0.0), "activity": 7, "info": 0}]
        # Viewed from the front, as if X and Z were the region's x and y.
        project = lambda region, rv3d, point: Vector((point.x, point.z))
        with mock.patch("bonsai.bim.module.structural.decorator.location_3d_to_region_2d", project):
            try:
                # A region with no labels drawn in it, so that only arrows are picked.
                return LoadsDecorator.pick(mock.Mock(as_pointer=lambda: 0), None, x, y)
            finally:
                LoadsDecorator.pickables, LoadsDecorator.shader_info = [], []

    def test_an_arrow_within_a_few_pixels(self):
        assert self.pick(60, 5)["activity"] == 7
        assert self.pick(60, 15) is None

    def test_not_at_its_tail_where_its_point_is_selected(self):
        assert self.pick(5, 0) is None


class TestLoadCaseSelfWeight(NewFile):
    def test_edit_and_clear_self_weight(self):
        ifc = ifcopenshell.file(schema="IFC4")
        tool.Ifc.set(ifc)
        load_case = ifc.createIfcStructuralLoadCase(
            GlobalId=ifcopenshell.guid.new(),
            Name="Dead Load",
            PredefinedType="LOAD_CASE",
            ActionType="PERMANENT_G",
            ActionSource="DEAD_LOAD_G",
        )
        props = tool.Structural.get_structural_props()

        bpy.ops.bim.enable_editing_structural_load_case(load_case=load_case.id())
        assert props.load_case_has_self_weight is False
        assert tuple(props.load_case_self_weight) == (0.0, 0.0, -1.0)

        props.load_case_has_self_weight = True
        props.load_case_self_weight = (0.5, 0.0, -1.0)
        bpy.ops.bim.edit_structural_load_case()
        assert list(load_case.SelfWeightCoefficients) == [0.5, 0.0, -1.0]

        bpy.ops.bim.enable_editing_structural_load_case(load_case=load_case.id())
        assert props.load_case_has_self_weight is True
        assert tuple(props.load_case_self_weight) == (0.5, 0.0, -1.0)

        props.load_case_has_self_weight = False
        bpy.ops.bim.edit_structural_load_case()
        assert load_case.SelfWeightCoefficients is None


class TestGetLoadUnitSymbol(NewFile):
    def make_file(self) -> ifcopenshell.file:
        ifc = ifcopenshell.file(schema="IFC4")
        tool.Ifc.set(ifc)
        ifcopenshell.api.root.create_entity(ifc, ifc_class="IfcProject")
        ifcopenshell.api.unit.assign_unit(ifc)  # millimetres
        return ifc

    def test_composing_force_over_length_when_no_load_units_are_declared(self):
        self.make_file()
        assert get_load_unit_symbol("IfcStructuralPointConnection") == "N"
        assert get_load_unit_symbol("IfcStructuralCurveMember") == "N/mm"
        assert get_load_unit_symbol("IfcStructuralSurfaceMember") == "N/mm2"

    def test_using_the_declared_load_units(self):
        ifc = self.make_file()
        bpy.context.scene.unit_settings.system = "METRIC"
        ifcopenshell.api.unit.assign_unit(ifc, units=tool.Unit.add_structural_units())
        assert get_load_unit_symbol("IfcStructuralPointConnection") == "kN"
        assert get_load_unit_symbol("IfcStructuralCurveMember") == "kN/m"
        assert get_load_unit_symbol("IfcStructuralSurfaceMember") == "kN/m2"


class TestSolveFactoredResultant(NewFile):
    def setup_case(self):
        """A load case with a Coefficient of 1.5. One force is in it directly; the other through a load group
        assigned to it by a factor of 2, so it is drawn at 1.5 x 2 = 3 times its value."""
        ifc = ifcopenshell.file(schema="IFC4")
        tool.Ifc.set(ifc)
        point = ifcopenshell.api.root.create_entity(ifc, ifc_class="IfcStructuralPointConnection")
        case = ifcopenshell.api.structural.add_structural_load_case(ifc, name="Case")
        case.Coefficient = 1.5
        group = ifcopenshell.api.structural.add_structural_load_group(ifc, name="Group")
        ifcopenshell.api.group.assign_group(ifc, products=[group], group=case)
        activities = []
        for name, force in (("Known", (10.0, 0.0, 0.0)), ("Unknown", (0.0, 0.0, 1.0))):
            load = ifcopenshell.api.structural.add_structural_load(
                ifc, name=name, ifc_class="IfcStructuralLoadSingleForce"
            )
            load.ForceX, load.ForceY, load.ForceZ = force
            activities.append(
                ifcopenshell.api.structural.add_structural_activity(
                    ifc, applied_load=load, structural_member=point, ifc_class="IfcStructuralPointAction"
                )
            )
        ifcopenshell.api.group.assign_group(ifc, products=[activities[0]], group=case)
        ifc.createIfcRelAssignsToGroupByFactor(
            ifcopenshell.guid.new(), RelatedObjects=[activities[1]], RelatingGroup=group, Factor=2.0
        )
        return case, activities

    def test_factor_of_each_activity_in_its_load_case(self):
        case, (known, unknown) = self.setup_case()
        assert tool.Structural.get_activity_factor(known, case) == pytest.approx(1.5)
        assert tool.Structural.get_activity_factor(unknown, case) == pytest.approx(3.0)

    def test_solving_in_the_forces_drawn(self):
        from bonsai.bim.module.structural.operator import solve_factored

        case, activities = self.setup_case()
        # Drawn, the known force is 15 along X; for a resultant at 45 deg the unknown must be drawn 15 along Z,
        # which is 5 of its own value, times 3.
        solved, resultant, error = solve_factored(
            activities,
            [(10.0, 0.0, 0.0), (0.0, 0.0, 1.0)],
            [(True, True), (False, True)],
            (1.0, 0.0, 1.0),
            (False, True),
        )
        assert not error
        assert solved[0] == pytest.approx((10.0, 0.0, 0.0))
        assert solved[1] == pytest.approx((0.0, 0.0, 5.0))
        assert resultant == pytest.approx((15.0, 0.0, 15.0))

    def test_refusing_an_unknown_with_a_factor_of_zero(self):
        from bonsai.bim.module.structural.operator import solve_factored

        case, activities = self.setup_case()
        case.Coefficient = 0.0
        _, _, error = solve_factored(
            activities,
            [(10.0, 0.0, 0.0), (0.0, 0.0, 1.0)],
            [(True, True), (False, True)],
            (1.0, 0.0, 1.0),
            (False, True),
        )
        assert "factor of 0" in error


class TestSolvingAtOneItemOnly(NewFile):
    def setup_shared_load(self):
        """Point A has a known force along X and an unknown force up; the unknown's load is also applied at B."""
        ifc = ifcopenshell.file(schema="IFC4")
        tool.Ifc.set(ifc)
        ifcopenshell.api.root.create_entity(ifc, ifc_class="IfcProject")
        case = ifcopenshell.api.structural.add_structural_load_case(ifc, name="Case")
        a, b = (ifcopenshell.api.root.create_entity(ifc, ifc_class="IfcStructuralPointConnection") for _ in range(2))
        loads = {}
        for name, force in (("Known", (10.0, 0.0, 0.0)), ("Shared", (0.0, 0.0, 1.0))):
            load = ifcopenshell.api.structural.add_structural_load(
                ifc, name=name, ifc_class="IfcStructuralLoadSingleForce"
            )
            load.ForceX, load.ForceY, load.ForceZ = force
            loads[name] = load
        add = lambda load, point: ifcopenshell.api.structural.add_structural_activity(
            ifc, applied_load=load, structural_member=point, ifc_class="IfcStructuralPointAction"
        )
        known_at_a, shared_at_a, shared_at_b = add(loads["Known"], a), add(loads["Shared"], a), add(loads["Shared"], b)
        ifcopenshell.api.group.assign_group(ifc, products=[known_at_a, shared_at_a, shared_at_b], group=case)
        tool.Structural.set_locks(shared_at_a, False, True)  # Its magnitude is to be found.
        tool.Structural.set_resultant(a, case, False, True, (1.0, 0.0, 1.0))  # At 45 degrees.
        return loads["Shared"], shared_at_a, shared_at_b

    def test_a_load_shared_with_another_item_is_copied_before_it_changes(self):
        from bonsai.bim.module.structural.operator import get_resolved_forces, write_activity_forces

        shared, shared_at_a, shared_at_b = self.setup_shared_load()
        forces, error = get_resolved_forces(shared_at_a)
        assert not error and forces[shared_at_a] == pytest.approx((0.0, 0.0, 10.0))
        write_activity_forces(forces)
        assert shared_at_a.AppliedLoad != shared
        assert tool.Structural.get_force(shared_at_a.AppliedLoad) == pytest.approx((0.0, 0.0, 10.0))
        # B keeps the load, unchanged.
        assert shared_at_b.AppliedLoad == shared
        assert tool.Structural.get_force(shared) == pytest.approx((0.0, 0.0, 1.0))

    def test_a_load_used_once_is_changed_in_place(self):
        from bonsai.bim.module.structural.operator import get_resolved_forces, write_activity_forces

        shared, shared_at_a, shared_at_b = self.setup_shared_load()
        ifcopenshell.api.root.remove_product(tool.Ifc.get(), product=shared_at_b)
        forces, _ = get_resolved_forces(shared_at_a)
        write_activity_forces(forces)
        assert shared_at_a.AppliedLoad == shared
        assert tool.Structural.get_force(shared) == pytest.approx((0.0, 0.0, 10.0))


class TestKeepingTheDirectionOfAForceOfNone(NewFile):
    def setup_point(self):
        ifc = ifcopenshell.file(schema="IFC4")
        tool.Ifc.set(ifc)
        ifcopenshell.api.root.create_entity(ifc, ifc_class="IfcProject")
        case = ifcopenshell.api.structural.add_structural_load_case(ifc, name="Case")
        point = ifcopenshell.api.root.create_entity(ifc, ifc_class="IfcStructuralPointConnection")
        return ifc, case, point

    def add_force(self, ifc, case, point, name, force):
        load = ifcopenshell.api.structural.add_structural_load(ifc, name=name, ifc_class="IfcStructuralLoadSingleForce")
        load.ForceX, load.ForceY, load.ForceZ = force
        activity = ifcopenshell.api.structural.add_structural_activity(
            ifc, applied_load=load, structural_member=point, ifc_class="IfcStructuralPointAction"
        )
        ifcopenshell.api.group.assign_group(ifc, products=[activity], group=case)
        return load, activity

    def test_naming_a_force_of_none_in_the_direction_it_had(self):
        from bonsai.bim.module.structural.operator import get_named_force_direction, write_forces

        ifc, case, point = self.setup_point()
        c, s = math.cos(math.radians(30)), math.sin(math.radians(30))
        load, _ = self.add_force(ifc, case, point, "10 N at 30 deg Q8", (10 * c, 0.0, -10 * s))
        write_forces({load: (1e-15, 0.0, 0.0)})  # Found to be none, as a solve finds it, give or take rounding.
        assert load.Name == "0 N at 30 deg Q8"
        assert tool.Structural.get_force(load) == (0.0, 0.0, 0.0)
        assert get_named_force_direction(load) == pytest.approx((c, 0.0, -s))

    def test_solving_a_force_of_none_along_its_named_direction(self):
        from bonsai.bim.module.structural.operator import get_resolved_forces

        ifc, case, point = self.setup_point()
        _, along_x = self.add_force(ifc, case, point, "X 1 N", (1.0, 0.0, 0.0))
        _, none = self.add_force(ifc, case, point, "0 N at 30 deg Q8", (0.0, 0.0, 0.0))
        for activity in (along_x, none):
            tool.Structural.set_locks(activity, False, True)  # Both magnitudes to be found.
        tool.Structural.set_resultant(point, case, True, True, (20.0, 0.0, -5.0))
        forces, error = get_resolved_forces(none)
        assert not error
        # Down 5 at 30 deg below +X is 10 along that line: 8.66 along X, the other force the rest of 20.
        # By load here; by applied load once solving at one item only is in.
        assert forces.get(none, forces.get(none.AppliedLoad)) == pytest.approx(
            (10 * math.cos(math.radians(30)), 0.0, -5.0)
        )


class TestNamingTheMomentCentre(NewFile):
    def test_the_centre_is_written_by_its_points_name(self):
        from bonsai.bim.module.structural.report import get_centre_symbols

        ifc = ifcopenshell.file(schema="IFC4")
        tool.Ifc.set(ifc)
        case = ifcopenshell.api.structural.add_structural_load_case(ifc, name="Case")
        assert tool.Structural.get_centre_symbol(case) == "A"  # No centre: the textbook's A.
        point = ifcopenshell.api.root.create_entity(ifc, ifc_class="IfcStructuralPointConnection", name="B")
        tool.Structural.set_moment_centre(case, point)
        assert tool.Structural.get_centre_symbol(case) == "B"
        assert get_centre_symbols(case) == ("B", "B")
        point.Name = "Joint 1"  # Too long for a subscript of letters: set as text.
        assert get_centre_symbols(case) == (r"\text{Joint 1}", "Joint 1")
        point.Name = None  # Unnamed: A, as statics texts write a moment centre.
        assert tool.Structural.get_centre_symbol(case) == "A"


class TestApplyingAChosenLoad(NewFile):
    def setup_points(self):
        """D carries a single force in a load case; B and C carry nothing; a curve member M can't take a single force."""
        ifc = ifcopenshell.file(schema="IFC4")
        tool.Ifc.set(ifc)
        ifcopenshell.api.root.create_entity(ifc, ifc_class="IfcProject")
        case = ifcopenshell.api.structural.add_structural_load_case(ifc, name="Case")
        load = ifcopenshell.api.structural.add_structural_load(
            ifc, name="1300 lbf", ifc_class="IfcStructuralLoadSingleForce"
        )
        objects = {}
        for name, ifc_class in (
            ("B", "IfcStructuralPointConnection"),
            ("C", "IfcStructuralPointConnection"),
            ("D", "IfcStructuralPointConnection"),
            ("M", "IfcStructuralCurveMember"),
        ):
            element = ifcopenshell.api.root.create_entity(ifc, ifc_class=ifc_class, name=name)
            obj = bpy.data.objects.new(name, None)
            bpy.context.scene.collection.objects.link(obj)
            tool.Ifc.link(element, obj)
            objects[name] = obj
        activity = ifcopenshell.api.structural.add_structural_activity(
            ifc,
            applied_load=load,
            structural_member=tool.Ifc.get_entity(objects["D"]),
            ifc_class="IfcStructuralPointAction",
        )
        ifcopenshell.api.group.assign_group(ifc, products=[activity], group=case)
        return ifc, case, load, objects

    def select(self, objects, names, active):
        for obj in bpy.context.scene.objects:
            obj.select_set(obj.name in names)
        bpy.context.view_layer.objects.active = objects[active]

    def test_targets_are_items_that_can_take_the_load_and_lack_it(self):
        ifc, case, load, objects = self.setup_points()
        targets = tool.Structural.get_load_targets(list(objects.values()), load, case)
        assert sorted(t.Name for t in targets) == ["B", "C"]  # Not D, which has it; not M, a curve member.

    def test_applying_skips_an_item_that_has_the_load_already(self):
        ifc, case, load, objects = self.setup_points()
        props = tool.Structural.get_structural_props()
        self.select(objects, {"B", "D"}, "D")
        props.applicable_structural_load_types = "IfcStructuralLoadSingleForce"
        props.applicable_structural_loads = str(load.id())
        bpy.ops.bim.add_structural_activity(load_group=case.id())
        users = [i for i in ifc.get_inverse(load) if i.is_a("IfcStructuralActivity")]
        assert sorted(u.AssignedToStructuralItem[0].RelatingElement.Name for u in users) == ["B", "D"]

    def test_the_picker_follows_the_active_items_load(self):
        ifc, case, load, objects = self.setup_points()
        other = ifcopenshell.api.structural.add_structural_load(
            ifc, name="Other", ifc_class="IfcStructuralLoadSingleForce"
        )
        props = tool.Structural.get_structural_props()
        props.active_load_case_id = case.id()
        self.select(objects, {"D"}, "D")
        props.applicable_structural_load_types = "IfcStructuralLoadSingleForce"
        props.applicable_structural_loads = str(other.id())
        tool.Structural.follow_active_item_load()
        assert props.applicable_structural_loads == str(load.id())
        # An item with no load here leaves the picker alone.
        self.select(objects, {"B"}, "B")
        props.applicable_structural_loads = str(other.id())
        tool.Structural.follow_active_item_load()
        assert props.applicable_structural_loads == str(other.id())

    def test_picking_a_loads_arrow_sets_the_picker_to_its_load(self):
        from bonsai.bim.module.structural.operator import pick_load_to_apply

        ifc, case, load, objects = self.setup_points()
        other = ifcopenshell.api.structural.add_structural_load(
            ifc, name="Other", ifc_class="IfcStructuralLoadSingleForce"
        )
        activity = next(i for i in ifc.get_inverse(load) if i.is_a("IfcStructuralActivity"))
        props = tool.Structural.get_structural_props()
        self.select(objects, {"B"}, "B")
        props.applicable_structural_load_types = "IfcStructuralLoadSingleForce"
        props.applicable_structural_loads = str(other.id())
        assert pick_load_to_apply({"activity": activity.id()}) == (True, f"Picked {load.Name}")
        assert props.applicable_structural_loads == str(load.id())

    def test_picking_a_load_with_nothing_selected(self):
        # A load can be picked first, and where it goes chosen after.
        from bonsai.bim.module.structural.operator import pick_load_to_apply

        ifc, case, load, objects = self.setup_points()
        activity = next(i for i in ifc.get_inverse(load) if i.is_a("IfcStructuralActivity"))
        for obj in bpy.context.scene.objects:
            obj.select_set(False)
        assert pick_load_to_apply({"activity": activity.id()})[0]
        props = tool.Structural.get_structural_props()
        assert props.applicable_structural_loads == str(load.id())

    def test_picking_what_is_not_a_load_or_cannot_be_applied_leaves_the_picker(self):
        from bonsai.bim.module.structural.operator import pick_load_to_apply

        ifc, case, load, objects = self.setup_points()
        other = ifcopenshell.api.structural.add_structural_load(
            ifc, name="Other", ifc_class="IfcStructuralLoadSingleForce"
        )
        activity = next(i for i in ifc.get_inverse(load) if i.is_a("IfcStructuralActivity"))
        props = tool.Structural.get_structural_props()
        self.select(objects, {"B"}, "B")
        props.applicable_structural_load_types = "IfcStructuralLoadSingleForce"
        props.applicable_structural_loads = str(other.id())
        # A resultant's arrow, which stands for several loads.
        assert not pick_load_to_apply({"activity": 0, "activities": [activity.id()]})[0]
        # A point load, with only a curve member selected, which cannot take it.
        self.select(objects, {"M"}, "M")
        assert not pick_load_to_apply({"activity": activity.id()})[0]
        self.select(objects, {"B"}, "B")
        assert props.applicable_structural_loads == str(other.id())


class TestKeepingMomentsAfterMoves(NewFile):
    """A kept sum of moments about A, with B's downward force to find: moving B along X changes its arm, so the
    force solves again to keep the sum, written once a move through IFC Move is confirmed"""

    def add_point(self, ifc, name, x):
        point = ifcopenshell.api.root.create_entity(ifc, ifc_class="IfcStructuralPointConnection", name=name)
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata([(0.0, 0.0, 0.0)], [], [])
        obj = bpy.data.objects.new(name, mesh)
        obj.location = (x, 0.0, 0.0)
        bpy.context.scene.collection.objects.link(obj)
        tool.Ifc.link(point, obj)
        return point, obj

    def setup_case(self):
        ifc = ifcopenshell.file(schema="IFC4")
        tool.Ifc.set(ifc)
        ifcopenshell.api.root.create_entity(ifc, ifc_class="IfcProject")
        case = ifcopenshell.api.structural.add_structural_load_case(ifc, name="Case")
        centre, _ = self.add_point(ifc, "A", 0.0)
        point, obj = self.add_point(ifc, "B", 2.0)
        bpy.context.view_layer.update()
        load = ifcopenshell.api.structural.add_structural_load(
            ifc, name="Z -10 N", ifc_class="IfcStructuralLoadSingleForce"
        )
        load.ForceX, load.ForceY, load.ForceZ = 0.0, 0.0, -10.0
        activity = ifcopenshell.api.structural.add_structural_activity(
            ifc, applied_load=load, structural_member=point, ifc_class="IfcStructuralPointAction"
        )
        ifcopenshell.api.group.assign_group(ifc, products=[activity], group=case)
        tool.Structural.set_locks(activity, False, True)  # Its magnitude is the unknown.
        tool.Structural.set_moment_centre(case, centre)
        from bonsai.bim.module.structural.operator import get_case_moment_forces

        _, arms, forces = get_case_moment_forces(case)
        tool.Structural.set_resultant_moment(case, float(arms[0][0] * forces[0][2] - arms[0][2] * forces[0][0]))
        return point, obj, load

    def move(self, obj, x):
        obj.location.x = x
        bpy.context.view_layer.update()

    def report_move(self, obj):
        """As the depsgraph reports a move while loads are shown"""
        from bonsai.bim.module.structural.decorator import update_loads_after_moves

        update = SimpleNamespace(is_updated_transform=True, id=obj)
        with mock.patch.object(LoadsDecorator, "update"):
            update_loads_after_moves(bpy.context.scene, SimpleNamespace(updates=[update]))

    def test_the_kept_moment_is_written_after_a_move_is_confirmed(self):
        from bonsai.bim.module.geometry.operator import OverrideMoveFinish
        from bonsai.bim.module.structural.operator import keep_moments_after_move

        assert keep_moments_after_move in OverrideMoveFinish.callbacks
        point, obj, load = self.setup_case()
        self.move(obj, 4.0)
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.ops.bim.override_move_finish()  # The step IFC Move runs once a move is confirmed.
        assert tool.Structural.get_force(load) == pytest.approx((0.0, 0.0, -5.0))  # Twice the arm, half the force.

    def test_a_move_by_other_means_is_kept_on_request(self):
        from bonsai.bim.module.structural.decorator import UNKEPT_ITEMS
        from bonsai.bim.module.structural.load_decoration_data import ShaderInfo

        point, obj, load = self.setup_case()
        self.move(obj, 4.0)  # As the gizmo or a typed location moves it: no IFC Move to confirm.
        self.report_move(obj)
        assert UNKEPT_ITEMS == {point.id()}
        assert tool.Structural.get_force(load) == pytest.approx((0.0, 0.0, -10.0))  # Not written yet,
        assert ShaderInfo.preview[load.id()]["ForceZ"] == pytest.approx(-5.0)  # but drawn as it solves.
        bpy.ops.bim.keep_structural_moments(items=str(point.id()))
        assert tool.Structural.get_force(load) == pytest.approx((0.0, 0.0, -5.0))
        assert not UNKEPT_ITEMS

    def test_moving_back_is_kept_without_writing(self):
        from bonsai.bim.module.structural.decorator import UNKEPT_ITEMS
        from bonsai.bim.module.structural.load_decoration_data import ShaderInfo

        point, obj, load = self.setup_case()
        self.move(obj, 4.0)
        self.report_move(obj)
        self.move(obj, 2.0)  # As an undo or a cancelled move puts it back.
        self.report_move(obj)
        assert not UNKEPT_ITEMS
        assert not ShaderInfo.preview
        assert tool.Structural.get_force(load) == pytest.approx((0.0, 0.0, -10.0))


class TestApplyStructuralLoadAxes(NewFile):
    def make_item(self, ifc_class, z_down=False):
        ifc = ifcopenshell.file(schema="IFC4")
        tool.Ifc.set(ifc)
        ifcopenshell.api.root.create_entity(ifc, ifc_class="IfcProject")
        model = ifcopenshell.api.structural.add_structural_analysis_model(ifc)
        if z_down:
            # As RFEM places its models: Z down.
            model.SharedPlacement = ifc.createIfcLocalPlacement(
                None,
                ifc.createIfcAxis2Placement3D(
                    ifc.createIfcCartesianPoint((0.0, 0.0, 0.0)),
                    ifc.createIfcDirection((0.0, 0.0, -1.0)),
                    ifc.createIfcDirection((1.0, 0.0, 0.0)),
                ),
            )
        item = ifcopenshell.api.root.create_entity(ifc, ifc_class=ifc_class)
        ifcopenshell.api.structural.assign_structural_analysis_model(
            ifc, products=[item], structural_analysis_model=model
        )
        obj = bpy.data.objects.new("Item", None)
        bpy.context.scene.collection.objects.link(obj)
        tool.Ifc.link(item, obj)
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        return ifc, item

    def get_activity(self, item):
        return ifcopenshell.util.structural.get_item_activities(item)[0]

    def test_a_force_normal_to_a_surface(self):
        ifc, surface = self.make_item("IfcStructuralSurfaceMember")
        bpy.ops.bim.apply_structural_load(load_group="0", axes="LOCAL_COORDS", z=-2.0)
        activity = self.get_activity(surface)
        assert activity.GlobalOrLocal == "LOCAL_COORDS"
        assert activity.AppliedLoad.PlanarForceZ == -2.0
        assert activity.AppliedLoad.Name.endswith(" local")

    def test_global_by_default(self):
        ifc, surface = self.make_item("IfcStructuralSurfaceMember")
        bpy.ops.bim.apply_structural_load(load_group="0", z=-2.0)
        assert self.get_activity(surface).GlobalOrLocal == "GLOBAL_COORDS"

    def test_local_values_are_not_turned_into_the_model_axes(self):
        ifc, surface = self.make_item("IfcStructuralSurfaceMember", z_down=True)
        bpy.ops.bim.apply_structural_load(load_group="0", axes="LOCAL_COORDS", z=-2.0)
        assert self.get_activity(surface).AppliedLoad.PlanarForceZ == -2.0

    def test_global_values_are_turned_into_the_model_axes(self):
        ifc, surface = self.make_item("IfcStructuralSurfaceMember", z_down=True)
        bpy.ops.bim.apply_structural_load(load_group="0", axes="GLOBAL_COORDS", z=-2.0)
        assert self.get_activity(surface).AppliedLoad.PlanarForceZ == 2.0

    def test_a_point_connection_takes_global_axes(self):
        ifc, point = self.make_item("IfcStructuralPointConnection")
        bpy.ops.bim.apply_structural_load(load_group="0", axes="LOCAL_COORDS", z=-2.0)
        activity = self.get_activity(point)
        assert activity.GlobalOrLocal == "GLOBAL_COORDS"
        assert not activity.AppliedLoad.Name.endswith(" local")

    def test_editing_a_load_changes_its_axes(self):
        ifc, surface = self.make_item("IfcStructuralSurfaceMember")
        bpy.ops.bim.apply_structural_load(load_group="0", axes="LOCAL_COORDS", z=-2.0)
        activity = self.get_activity(surface)
        case = str(ifcopenshell.util.structural.get_activity_load_cases(activity)[0].id())
        bpy.ops.bim.edit_structural_load_values(
            activity=activity.id(), load_group=case, initial_load_group=case, axes="GLOBAL_COORDS", z=-3.0
        )
        assert activity.GlobalOrLocal == "GLOBAL_COORDS"
        assert activity.AppliedLoad.PlanarForceZ == -3.0
        assert not activity.AppliedLoad.Name.endswith(" local")

    def test_an_angle_in_local_axes(self):
        # The calculator's angle and slope inputs give a force in a member's own axes as well as in global ones.
        ifc, surface = self.make_item("IfcStructuralSurfaceMember", z_down=True)
        bpy.ops.bim.apply_structural_load(
            load_group="0", axes="LOCAL_COORDS", input_mode="ANGLE", magnitude=2.0, angle=30.0
        )
        activity = self.get_activity(surface)
        assert activity.GlobalOrLocal == "LOCAL_COORDS"
        # 30 degrees from +X towards +Z, in the member's axes, so not turned into the model's.
        assert activity.AppliedLoad.PlanarForceX == pytest.approx(2.0 * math.cos(math.radians(30)))
        assert activity.AppliedLoad.PlanarForceZ == pytest.approx(1.0)
        assert activity.AppliedLoad.Name == "2 N/m2 at 30 deg local"


class TestPlacingAPoint(NewFile):
    """Place Point moves a structural point to a distance and direction from another, as the book dimensions one:
    C, 200 mm at 60 degrees from B"""

    def add_point(self, ifc, name, x, z=0.0):
        point = ifcopenshell.api.root.create_entity(ifc, ifc_class="IfcStructuralPointConnection", name=name)
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata([(0.0, 0.0, 0.0)], [], [])
        obj = bpy.data.objects.new(name, mesh)
        obj.location = (x, 0.0, z)
        bpy.context.scene.collection.objects.link(obj)
        tool.Ifc.link(point, obj)
        return point, obj

    def setup_points(self):
        ifc = ifcopenshell.file(schema="IFC4")
        tool.Ifc.set(ifc)
        ifcopenshell.api.root.create_entity(ifc, ifc_class="IfcProject")
        b, b_obj = self.add_point(ifc, "B", 1.0, 0.5)
        c, c_obj = self.add_point(ifc, "C", 3.0)
        bpy.context.view_layer.update()
        bpy.context.view_layer.objects.active = c_obj
        return ifc, b, c, c_obj

    def test_placing_by_distance_and_angle(self):
        _, b, c, c_obj = self.setup_points()
        bpy.ops.bim.place_structural_point(
            point_id=c.id(), from_point=str(b.id()), input_mode="ANGLE", distance=0.2, direction="Q1", angle=60.0
        )
        at = c_obj.matrix_world @ c_obj.data.vertices[0].co
        assert (at.x, at.y, at.z) == pytest.approx(
            (1.0 + 0.2 * math.cos(math.radians(60)), 0.0, 0.5 + 0.2 * math.sin(math.radians(60)))
        )
        # Written to the IFC, not only moved in Blender.
        assert c.ObjectPlacement.RelativePlacement.Location.Coordinates == pytest.approx((at.x, 0.0, at.z))

    def test_placing_by_components(self):
        _, b, c, c_obj = self.setup_points()
        bpy.ops.bim.place_structural_point(
            point_id=c.id(), from_point=str(b.id()), input_mode="COMPONENTS", dx=-0.3, dz=0.4
        )
        at = c_obj.matrix_world @ c_obj.data.vertices[0].co
        assert (at.x, at.z) == pytest.approx((0.7, 0.9))

    def test_a_kept_moment_follows_the_point_placed(self):
        ifc, b, c, c_obj = self.setup_points()
        centre, _ = self.add_point(ifc, "A", 0.0)
        bpy.context.view_layer.update()
        case = ifcopenshell.api.structural.add_structural_load_case(ifc, name="Case")
        load = ifcopenshell.api.structural.add_structural_load(
            ifc, name="Z -10 N", ifc_class="IfcStructuralLoadSingleForce"
        )
        load.ForceX, load.ForceY, load.ForceZ = 0.0, 0.0, -10.0
        activity = ifcopenshell.api.structural.add_structural_activity(
            ifc, applied_load=load, structural_member=c, ifc_class="IfcStructuralPointAction"
        )
        ifcopenshell.api.group.assign_group(ifc, products=[activity], group=case)
        tool.Structural.set_locks(activity, False, True)
        tool.Structural.set_moment_centre(case, centre)
        tool.Structural.set_resultant_moment(case, -30.0)  # C at x = 3: 3 x -10, clockwise.
        # C to x = 1 + 0.5 = 1.5, from B: half the arm, so twice the force.
        bpy.ops.bim.place_structural_point(
            point_id=c.id(), from_point=str(b.id()), input_mode="COMPONENTS", dx=0.5, dz=0.0
        )
        assert tool.Structural.get_force(load) == pytest.approx((0.0, 0.0, -20.0))

    def test_placing_from_the_origin(self):
        _, _, c, c_obj = self.setup_points()
        bpy.ops.bim.place_structural_point(
            point_id=c.id(), from_point="ORIGIN", input_mode="ANGLE", distance=0.2, direction="Q4", angle=30.0
        )
        at = c_obj.matrix_world @ c_obj.data.vertices[0].co
        # 30 degrees up from -X: 150 degrees from +X.
        assert (at.x, at.z) == pytest.approx((0.2 * math.cos(math.radians(150)), 0.2 * math.sin(math.radians(150))))

    def test_placing_from_the_3d_cursor(self):
        _, _, c, c_obj = self.setup_points()
        bpy.context.scene.cursor.location = (-1.0, 0.0, 2.0)
        bpy.ops.bim.place_structural_point(
            point_id=c.id(), from_point="CURSOR", input_mode="COMPONENTS", dx=0.5, dz=-0.5
        )
        at = c_obj.matrix_world @ c_obj.data.vertices[0].co
        assert (at.x, at.z) == pytest.approx((-0.5, 1.5))

    def test_placing_from_a_picked_object(self):
        _, _, c, c_obj = self.setup_points()
        empty = bpy.data.objects.new("Corner", None)  # Any object: its origin.
        empty.location = (2.0, 0.0, 1.0)
        bpy.context.scene.collection.objects.link(empty)
        bpy.context.view_layer.update()
        tool.Structural.get_structural_props().place_from_object = empty
        bpy.ops.bim.place_structural_point(
            point_id=c.id(), from_point="OBJECT", input_mode="COMPONENTS", dx=0.0, dz=0.25
        )
        at = c_obj.matrix_world @ c_obj.data.vertices[0].co
        assert (at.x, at.z) == pytest.approx((2.0, 1.25))

    def test_placing_by_components_with_dz_from_another_point(self):
        # As Example 2.19 dimensions a joint: Δx from B, but 4' above A.
        ifc, b, c, c_obj = self.setup_points()
        a, _ = self.add_point(ifc, "A", 0.0, 2.0)
        bpy.context.view_layer.update()
        bpy.ops.bim.place_structural_point(
            point_id=c.id(), from_point=str(b.id()), input_mode="COMPONENTS", dx=-0.3, dz=0.4, length_from=str(a.id())
        )
        at = c_obj.matrix_world @ c_obj.data.vertices[0].co
        assert (at.x, at.z) == pytest.approx((0.7, 2.4))

    def test_level_with_another_point(self):
        ifc, b, c, c_obj = self.setup_points()
        a, _ = self.add_point(ifc, "A", 0.0, 2.0)
        bpy.context.view_layer.update()
        bpy.ops.bim.place_structural_point(
            point_id=c.id(), from_point=str(b.id()), input_mode="COMPONENTS", dx=0.5, dz=0.0, length_from=str(a.id())
        )
        at = c_obj.matrix_world @ c_obj.data.vertices[0].co
        assert (at.x, at.z) == pytest.approx((1.5, 2.0))

    def test_the_inputs_read_dz_from_the_point_it_is_measured_from(self):
        from bonsai.bim.module.structural.operator import fill_place_inputs

        ifc, b, c, c_obj = self.setup_points()
        a, _ = self.add_point(ifc, "A", 0.0, 2.0)
        bpy.context.view_layer.update()
        props = SimpleNamespace(
            point_id=c.id(), from_point=str(b.id()), input_mode="COMPONENTS", length_from=str(a.id()), dx=0.0, dz=0.0
        )
        props.distance = props.direction = props.angle = props.rise = props.run = None
        props.known = "DISTANCE"
        fill_place_inputs(props)
        # C at (3, 0): 2 right of B, 2 below A.
        assert (props.dx, props.dz) == pytest.approx((2.0, -2.0))

    def test_placing_along_a_slope_until_a_dz(self):
        # As Example 2.19's D: along the member from B, rising 4 in 3 to the left, until it is a height above B.
        _, b, c, c_obj = self.setup_points()
        bpy.ops.bim.place_structural_point(
            point_id=c.id(),
            from_point=str(b.id()),
            input_mode="SLOPE",
            direction="Q4",
            rise=4.0,
            run=3.0,
            known="DZ",
            dz=1.0,
        )
        at = c_obj.matrix_world @ c_obj.data.vertices[0].co
        assert (at.x, at.z) == pytest.approx((1.0 - 0.75, 1.5))

    def test_placing_along_a_slope_until_a_height_above_another_point(self):
        ifc, b, c, c_obj = self.setup_points()
        a, _ = self.add_point(ifc, "A", 0.0, 2.0)
        bpy.context.view_layer.update()
        bpy.ops.bim.place_structural_point(
            point_id=c.id(),
            from_point=str(b.id()),
            input_mode="SLOPE",
            direction="Q4",
            rise=4.0,
            run=3.0,
            known="DZ",
            dz=0.4,
            length_from=str(a.id()),
        )
        at = c_obj.matrix_world @ c_obj.data.vertices[0].co
        # Up 2.4 - 0.5 = 1.9 from B, so 1.9 x 3/4 to the left.
        assert (at.x, at.z) == pytest.approx((1.0 - 1.425, 2.4))

    def test_placing_at_an_angle_until_a_dx(self):
        _, b, c, c_obj = self.setup_points()
        bpy.ops.bim.place_structural_point(
            point_id=c.id(), from_point=str(b.id()), input_mode="ANGLE", direction="Q1", angle=45.0, known="DX", dx=0.5
        )
        at = c_obj.matrix_world @ c_obj.data.vertices[0].co
        assert (at.x, at.z) == pytest.approx((1.5, 1.0))

    def test_a_direction_that_never_reaches_the_length_leaves_the_point(self):
        _, b, c, c_obj = self.setup_points()
        with pytest.raises(RuntimeError, match="never reaches"):
            bpy.ops.bim.place_structural_point(
                point_id=c.id(),
                from_point=str(b.id()),
                input_mode="ANGLE",
                direction="Q1",
                angle=0.0,
                known="DZ",
                dz=0.3,
            )
        at = c_obj.matrix_world @ c_obj.data.vertices[0].co
        assert (at.x, at.z) == pytest.approx((3.0, 0.0))


class TestDuplicateStructuralLoadCase(NewFile):
    def test_duplicating_a_load_case_and_telling_the_callbacks(self):
        from bonsai.bim.module.structural.operator import DuplicateStructuralLoadCase

        ifc = ifcopenshell.file(schema="IFC4")
        tool.Ifc.set(ifc)
        ifcopenshell.api.root.create_entity(ifc, ifc_class="IfcProject")
        load_case = ifcopenshell.api.structural.add_structural_load_case(ifc, name="About A")
        calls = []
        callback = lambda original, copy: calls.append((original, copy))
        DuplicateStructuralLoadCase.callbacks.append(callback)
        try:
            bpy.ops.bim.duplicate_structural_load_case(load_case=load_case.id())
        finally:
            DuplicateStructuralLoadCase.callbacks.remove(callback)
        copy = next(c for c in ifc.by_type("IfcStructuralLoadCase") if c != load_case)
        assert copy.Name == "About A (copy)"
        assert calls == [(load_case, copy)]


class TestDuplicatingALoadCaseKeepsTheCalculatorsState(NewFile):
    """A load case about A with a load group, a force on B linked to twice a force on C in the group, a locked
    resultant at B and a kept moment, duplicated to take moments about another point"""

    def test_the_copy_keeps_the_calculators_state_as_its_own(self):
        ifc = ifcopenshell.file(schema="IFC4")
        tool.Ifc.set(ifc)
        ifcopenshell.api.root.create_entity(ifc, ifc_class="IfcProject")
        case = ifcopenshell.api.structural.add_structural_load_case(ifc, name="About A")
        group = ifcopenshell.api.structural.add_structural_load_group(ifc, name="Wind")
        ifcopenshell.api.group.assign_group(ifc, products=[group], group=case)
        load = ifcopenshell.api.structural.add_structural_load(
            ifc, name="100 lbf", ifc_class="IfcStructuralLoadSingleForce"
        )
        points = {
            name: ifcopenshell.api.root.create_entity(ifc, ifc_class="IfcStructuralPointConnection", name=name)
            for name in ("A", "B", "C")
        }
        activities = {}
        for name, target in (("B", case), ("C", group)):
            activity = ifcopenshell.api.structural.add_structural_activity(
                ifc, applied_load=load, structural_member=points[name], ifc_class="IfcStructuralPointAction"
            )
            ifcopenshell.api.group.assign_group(ifc, products=[activity], group=target)
            activities[name] = activity
        tool.Structural.set_magnitude_link(activities["B"], activities["C"], 2.0)
        tool.Structural.edit_bbim_structural(activities["B"], {"DirectionLocked": True})
        tool.Structural.edit_bbim_structural(case, {"MomentCentre": points["A"].GlobalId, "ResultantMoment": 0.0})
        tool.Structural.set_resultant(points["B"], case, True, False, (0.0, 0.0, -100.0))
        tool.Structural.set_resultant_eighth(points["B"], case, "Q4")

        bpy.ops.bim.duplicate_structural_load_case(load_case=case.id())
        copy = next(c for c in ifc.by_type("IfcStructuralLoadCase") if c != case)
        pset = ifcopenshell.util.element.get_pset(copy, "BBIM_Structural")
        assert pset["MomentCentre"] == points["A"].GlobalId and pset["ResultantMoment"] == 0.0
        assert tool.Structural.get_resultant(points["B"], copy) == tool.Structural.get_resultant(points["B"], case)
        assert tool.Structural.get_resultant_eighth(points["B"], copy) == "Q4"
        copied = tool.Structural.get_copied_activities(case, copy)
        on_b, on_c = copied[activities["B"]], copied[activities["C"]]
        assert ifcopenshell.util.element.get_pset(on_b, "BBIM_Structural", "DirectionLocked") is True
        # Linked to the copy's force on C, not the original's, which stays linked as it was.
        assert tool.Structural.get_magnitude_link(on_b) == on_c.GlobalId
        assert tool.Structural.get_magnitude_ratio(on_b) == 2.0
        assert tool.Structural.get_magnitude_link(activities["B"]) == activities["C"].GlobalId


class TestChoosingTheMomentCentreOfALoadCase(NewFile):
    """Choosing the point a load case's moments are taken about from the load case being edited, not only the one
    shown"""

    def setup_case(self):
        ifc = ifcopenshell.file(schema="IFC4")
        tool.Ifc.set(ifc)
        ifcopenshell.api.root.create_entity(ifc, ifc_class="IfcProject")
        case = ifcopenshell.api.structural.add_structural_load_case(ifc, name="About B")
        points = {
            name: ifcopenshell.api.root.create_entity(ifc, ifc_class="IfcStructuralPointConnection", name=name)
            for name in ("A", "B")
        }
        return ifc, case, points

    def test_choosing_a_point_for_a_load_case(self):
        ifc, case, points = self.setup_case()
        bpy.ops.bim.set_structural_moment_centre(load_case=case.id(), point=str(points["B"].id()))
        assert tool.Structural.get_moment_centre(case) == points["B"]

    def test_choosing_none(self):
        ifc, case, points = self.setup_case()
        tool.Structural.set_moment_centre(case, points["A"])
        bpy.ops.bim.set_structural_moment_centre(load_case=case.id(), point="NONE")
        assert tool.Structural.get_moment_centre(case) is None

    def test_the_selected_point_by_default(self):
        ifc, case, points = self.setup_case()
        obj = bpy.data.objects.new("A", None)
        bpy.context.scene.collection.objects.link(obj)
        tool.Ifc.link(points["A"], obj)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.bim.set_structural_moment_centre(load_case=case.id())
        assert tool.Structural.get_moment_centre(case) == points["A"]

    def test_picking_the_point_nearest_the_click(self):
        from bonsai.bim.module.structural import operator as structural_operator

        ifc, case, points = self.setup_case()
        for name, x in (("A", 0.0), ("B", 1.0)):
            mesh = bpy.data.meshes.new(name)
            mesh.from_pydata([(0.0, 0.0, 0.0)], [], [])
            obj = bpy.data.objects.new(name, mesh)
            obj.location = (x, 0.0, 0.0)
            bpy.context.scene.collection.objects.link(obj)
            tool.Ifc.link(points[name], obj)
        bpy.context.view_layer.update()

        # A view drawing X at 100 pixels a metre.
        def project(region, rv3d, co):
            return Vector((co.x * 100.0, co.z * 100.0))

        with mock.patch.object(structural_operator, "location_3d_to_region_2d", project):
            assert structural_operator.pick_point_connection(None, None, 95.0, 6.0) == points["B"]
            assert structural_operator.pick_point_connection(None, None, 50.0, 0.0) is None  # A miss.


class TestAppliedMoments(NewFile):
    """Example 2.20's force moved to B with its couple: 10 down at B and a moment of -50 applied at B, the same about
    B, about C below it and about A, 5 to its right, as 10 down at A alone is"""

    def add_point(self, ifc, name, x, z=0.0):
        point = ifcopenshell.api.root.create_entity(ifc, ifc_class="IfcStructuralPointConnection", name=name)
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata([(0.0, 0.0, 0.0)], [], [])
        obj = bpy.data.objects.new(name, mesh)
        obj.location = (x, 0.0, z)
        bpy.context.scene.collection.objects.link(obj)
        tool.Ifc.link(point, obj)
        return point

    def setup_case(self, moment_y=50.0):
        ifc = ifcopenshell.file(schema="IFC4")
        tool.Ifc.set(ifc)
        ifcopenshell.api.root.create_entity(ifc, ifc_class="IfcProject")
        case = ifcopenshell.api.structural.add_structural_load_case(ifc, name="Force and couple at B")
        points = {"A": self.add_point(ifc, "A", 0.0), "B": self.add_point(ifc, "B", -5.0)}
        points["C"] = self.add_point(ifc, "C", -5.0, -15.0)
        bpy.context.view_layer.update()
        load = ifcopenshell.api.structural.add_structural_load(
            ifc, name="Z -10 N", ifc_class="IfcStructuralLoadSingleForce"
        )
        load.ForceZ = -10.0
        load.MomentY = moment_y  # By the right-hand rule about +Y: clockwise as the X-Z plane is seen from -Y.
        activity = ifcopenshell.api.structural.add_structural_activity(
            ifc, applied_load=load, structural_member=points["B"], ifc_class="IfcStructuralPointAction"
        )
        ifcopenshell.api.group.assign_group(ifc, products=[activity], group=case)
        return ifc, case, points, load, activity

    def test_an_applied_moment_is_counter_clockwise_positive(self):
        _, _, _, load, _ = self.setup_case()
        assert tool.Structural.get_applied_moment(load) == pytest.approx(-50.0)

    def test_an_applied_moment_counts_the_same_about_any_point(self):
        _, case, points, _, _ = self.setup_case()
        assert tool.Structural.get_moment_about(case, points["B"]) == pytest.approx(-50.0)
        assert tool.Structural.get_moment_about(case, points["C"]) == pytest.approx(-50.0)
        # The force's +50 about A, and the couple's -50.
        assert tool.Structural.get_moment_about(case, points["A"]) == pytest.approx(0.0)

    def test_a_kept_moment_solves_with_the_applied_moment_known(self):
        from bonsai.bim.module.structural.operator import solve_case_moment

        _, case, points, load, activity = self.setup_case(moment_y=20.0)  # -20 applied.
        tool.Structural.set_locks(activity, False, True)  # The force's magnitude is the unknown.
        tool.Structural.set_moment_centre(case, points["A"])
        # About A: the force at B, 5 to the left, makes the other -30, so 6 up.
        changed, error = solve_case_moment(case, -50.0)
        assert not error
        assert changed[load] == pytest.approx((0.0, 0.0, 6.0))

    def test_edit_load_keeps_the_moment_in_every_input_mode(self):
        from bonsai.bim.module.structural.operator import get_load_attributes

        _, _, _, load, _ = self.setup_case()
        props = SimpleNamespace(
            input_mode="ANGLE",
            magnitude=10.0,
            angle=0.0,
            rise=1.0,
            run=1.0,
            direction="Q7",
            x=0.0,
            y=0.0,
            z=0.0,
            moment_x=0.0,
            moment_y=0.0,
            moment_z=0.0,
            moment=-50.0,
            given="MAGNITUDE",
            given_value=0.0,
            on_axes=False,
            has_axes=False,
            axes_tilt=0.0,
        )
        attributes = get_load_attributes(props, "IfcStructuralPointConnection", load)
        assert attributes["MomentY"] == pytest.approx(50.0)
        assert attributes["ForceZ"] == pytest.approx(-10.0)

    def test_the_resultant_at_the_point_names_its_couple(self):
        from bonsai.bim.module.structural.data import StructuralItemLoadsData
        from bonsai.bim.module.structural.report import get_resultant_calculation

        _, _, _, _, activity = self.setup_case()
        calculation = get_resultant_calculation([activity], "N")
        summary = calculation["summary"]
        assert summary.startswith("R = 10.00 N")
        assert summary.endswith(", with a couple M = -50.00 N.m (clockwise)")
        # Listed with the force, before the resultant, as the diagram draws it.
        assert [row["symbol"] for row in calculation["forces"]] == ["F_{1}", "M_{1}", "R"]
        couple = calculation["forces"][1]
        assert couple["magnitude"] == "50.00 N.m" and couple["direction"] == "clockwise"
        label = StructuralItemLoadsData.get_resultant_label([(0.0, 0.0, -10.0)], -50.0)
        assert "M = -50" in label and label.startswith("R = 10")


class TestMovingLoadsToAPoint(NewFile):
    """Example 2.21's roof: 12 down 1 left of the column's axis and 10 down 1 right of it, moved to the axis: 22
    down with a couple of +12 - 10 = +2"""

    def add_point(self, ifc, name, x, z=0.0):
        point = ifcopenshell.api.root.create_entity(ifc, ifc_class="IfcStructuralPointConnection", name=name)
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata([(0.0, 0.0, 0.0)], [], [])
        obj = bpy.data.objects.new(name, mesh)
        obj.location = (x, 0.0, z)
        bpy.context.scene.collection.objects.link(obj)
        tool.Ifc.link(point, obj)
        return point

    def setup_roof(self):
        ifc = ifcopenshell.file(schema="IFC4")
        tool.Ifc.set(ifc)
        ifcopenshell.api.root.create_entity(ifc, ifc_class="IfcProject")
        model = ifcopenshell.api.structural.add_structural_analysis_model(ifc)
        case = ifcopenshell.api.structural.add_structural_load_case(ifc, name="At Roof")
        model.LoadedBy = [case]
        points = {name: self.add_point(ifc, name, x, 26.0) for name, x in (("ROOF", 0.0), ("L", -1.0), ("R", 1.0))}
        bpy.context.view_layer.update()
        loads = {}
        for name, value in (("L", -12.0), ("R", -10.0)):
            load = ifcopenshell.api.structural.add_structural_load(
                ifc, name=f"{value} kip", ifc_class="IfcStructuralLoadSingleForce"
            )
            load.ForceZ = value
            activity = ifcopenshell.api.structural.add_structural_activity(
                ifc, applied_load=load, structural_member=points[name], ifc_class="IfcStructuralPointAction"
            )
            ifcopenshell.api.group.assign_group(ifc, products=[activity], group=case)
            loads[name] = load
        return ifc, model, case, points, loads

    def get_moved(self, ifc, source):
        target = next(c for c in ifc.by_type("IfcStructuralLoadCase") if c != source)
        (activity,) = [o for r in target.IsGroupedBy for o in r.RelatedObjects]
        return target, activity

    def test_moving_loads_to_a_point_makes_a_force_and_a_couple(self):
        ifc, model, case, points, _ = self.setup_roof()
        bpy.ops.bim.move_structural_loads_to_point(
            load_case=case.id(), point=str(points["ROOF"].id()), target="NEW", new_load_case_name="On the column axis"
        )
        target, activity = self.get_moved(ifc, case)
        assert target.Name == "On the column axis" and target in model.LoadedBy
        assert activity.AssignedToStructuralItem[0].RelatingElement == points["ROOF"]
        assert tool.Structural.get_force(activity.AppliedLoad) == pytest.approx((0.0, 0.0, -22.0))
        assert tool.Structural.get_applied_moment(activity.AppliedLoad) == pytest.approx(2.0)
        assert tool.Structural.get_moved_from(activity) == case

    def test_lists_name_where_a_moved_load_came_from(self):
        from bonsai.bim.module.structural.data import StructuralLoadCasesData, StructuralLoadsData

        ifc, model, case, points, loads = self.setup_roof()
        bpy.ops.bim.move_structural_loads_to_point(load_case=case.id(), point=str(points["ROOF"].id()), target="NEW")
        target, activity = self.get_moved(ifc, case)
        rows = {a["id"]: a for c in StructuralLoadCasesData.load_cases() for a in c["activities"]}
        assert rows[activity.id()]["name"].endswith(" ← At Roof") and rows[activity.id()]["moved"]
        source_rows = [a for c in StructuralLoadCasesData.load_cases() if c["id"] == case.id() for a in c["activities"]]
        assert source_rows and not any(a["moved"] or "←" in a["name"] for a in source_rows)
        assert StructuralLoadsData.moved_from() == {activity.AppliedLoad.id(): "At Roof"}

    def test_a_moved_load_follows_its_loads_after_any_ifc_operator(self):
        ifc, model, case, points, loads = self.setup_roof()
        bpy.ops.bim.move_structural_loads_to_point(load_case=case.id(), point=str(points["ROOF"].id()), target="NEW")
        _, activity = self.get_moved(ifc, case)
        loads["L"].ForceZ = -16.0  # As any edit might, then an IFC operator ends.
        bpy.ops.bim.set_structural_moment_centre(load_case=case.id(), point=str(points["ROOF"].id()))
        assert tool.Structural.get_force(activity.AppliedLoad) == pytest.approx((0.0, 0.0, -26.0))
        assert tool.Structural.get_applied_moment(activity.AppliedLoad) == pytest.approx(6.0)

    def test_a_moved_load_removed_is_forgotten(self):
        ifc, model, case, points, _ = self.setup_roof()
        bpy.ops.bim.move_structural_loads_to_point(load_case=case.id(), point=str(points["ROOF"].id()), target="NEW")
        target, activity = self.get_moved(ifc, case)
        ifcopenshell.api.structural.remove_structural_activity(ifc, activity=activity)
        tool.Structural.refresh_moved_loads()
        assert tool.Structural.get_moved_loads(target) == []

    def test_a_moved_load_case_removed_takes_its_load_definition(self):
        ifc, model, case, points, loads = self.setup_roof()
        bpy.ops.bim.move_structural_loads_to_point(load_case=case.id(), point=str(points["ROOF"].id()), target="NEW")
        target, activity = self.get_moved(ifc, case)
        load_id = activity.AppliedLoad.id()
        bpy.ops.bim.remove_structural_load_case(load_case=target.id())
        assert load_id not in {l.id() for l in ifc.by_type("IfcStructuralLoad")}
        assert set(ifc.by_type("IfcStructuralLoad")) == set(loads.values())

    def test_a_moved_load_removed_takes_its_load_definition(self):
        ifc, model, case, points, _ = self.setup_roof()
        bpy.ops.bim.move_structural_loads_to_point(load_case=case.id(), point=str(points["ROOF"].id()), target="NEW")
        _, activity = self.get_moved(ifc, case)
        load_id = activity.AppliedLoad.id()
        bpy.ops.bim.remove_structural_activity(activity=activity.id())
        assert load_id not in {l.id() for l in ifc.by_type("IfcStructuralLoad")}

    def test_a_moved_load_definition_applied_elsewhere_is_kept(self):
        ifc, model, case, points, _ = self.setup_roof()
        bpy.ops.bim.move_structural_loads_to_point(load_case=case.id(), point=str(points["ROOF"].id()), target="NEW")
        target, activity = self.get_moved(ifc, case)
        load = activity.AppliedLoad
        ifcopenshell.api.structural.add_structural_activity(
            ifc, applied_load=load, structural_member=points["L"], ifc_class="IfcStructuralPointAction"
        )
        bpy.ops.bim.remove_structural_load_case(load_case=target.id())
        assert load in ifc.by_type("IfcStructuralLoad")

    def test_an_unused_load_definition_not_from_a_move_is_kept(self):
        ifc, model, case, points, _ = self.setup_roof()
        bpy.ops.bim.move_structural_loads_to_point(load_case=case.id(), point=str(points["ROOF"].id()), target="NEW")
        target, _ = self.get_moved(ifc, case)
        spare = ifcopenshell.api.structural.add_structural_load(
            ifc, name="Spare", ifc_class="IfcStructuralLoadSingleForce"
        )
        bpy.ops.bim.remove_structural_load_case(load_case=target.id())
        assert spare in ifc.by_type("IfcStructuralLoad")

    def test_undoing_a_removed_moved_load_case_brings_back_its_load_definition(self):
        ifc, model, case, points, _ = self.setup_roof()
        bpy.ops.bim.move_structural_loads_to_point(load_case=case.id(), point=str(points["ROOF"].id()), target="NEW")
        target, activity = self.get_moved(ifc, case)
        load_id = activity.AppliedLoad.id()
        bpy.ops.bim.remove_structural_load_case(load_case=target.id())
        assert load_id not in {l.id() for l in ifc.by_type("IfcStructuralLoad")}
        ifc.undo()
        assert ifc.by_id(load_id).is_a("IfcStructuralLoadSingleForce")

    def test_moving_more_loads_into_the_same_load_case(self):
        ifc, model, case, points, _ = self.setup_roof()
        floor = ifcopenshell.api.structural.add_structural_load_case(ifc, name="On the column axis")
        bpy.ops.bim.move_structural_loads_to_point(
            load_case=case.id(), point=str(points["ROOF"].id()), target=str(floor.id())
        )
        bpy.ops.bim.move_structural_loads_to_point(
            load_case=case.id(), point=str(points["L"].id()), target=str(floor.id())
        )
        assert len(tool.Structural.get_moved_loads(floor)) == 2
        # About L itself: 10 down 2 to its right, clockwise.
        at_l = next(
            a
            for r in floor.IsGroupedBy
            for a in r.RelatedObjects
            if a.AssignedToStructuralItem[0].RelatingElement == points["L"]
        )
        assert tool.Structural.get_applied_moment(at_l.AppliedLoad) == pytest.approx(-20.0)

    def test_moved_and_shared_loads_are_marked(self):
        from bonsai.bim.module.structural.load_decoration_data import ShaderInfo

        ifc, model, case, points, loads = self.setup_roof()
        bpy.ops.bim.move_structural_loads_to_point(load_case=case.id(), point=str(points["ROOF"].id()), target="NEW")
        target, moved = self.get_moved(ifc, case)
        # The 12 at L also applied at R, by sharing its definition, in another load case.
        shared = ifcopenshell.api.structural.add_structural_activity(
            ifc, applied_load=loads["L"], structural_member=points["R"], ifc_class="IfcStructuralPointAction"
        )
        ifcopenshell.api.group.assign_group(ifc, products=[shared], group=target)
        marks = ShaderInfo(target).get_load_marks()
        assert marks[moved.id()] == ("At Roof", None)
        # At L and at R: both uses tagged alike. The 10 at R, at one point, is not.
        original = next(a for a in ifc.get_inverse(loads["L"]) if a.is_a("IfcStructuralActivity") and a != shared)
        assert marks[shared.id()] == marks[original.id()] == (None, "①")
        assert marks[next(a for a in ifc.get_inverse(loads["R"]) if a.is_a("IfcStructuralActivity")).id()] == (
            None,
            None,
        )
        # Reports mark them as the drawing does, and say what the marks mean.
        from bonsai.bim.module.structural.report import get_marked_name, get_marks_note

        assert get_marked_name("12 kip", shared.id(), marks) == "12 kip ①"
        assert get_marked_name("Moved", moved.id(), marks) == "Moved ← At Roof"
        note = get_marks_note([moved.id(), shared.id()], marks)
        assert "moved load" in note and "circled number" in note
        assert get_marks_note([], marks) == ""
