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
