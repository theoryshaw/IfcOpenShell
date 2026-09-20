# Bonsai - OpenBIM Blender Add-on
# Copyright (C) 2025 Bruno Postle <bruno@postle.net>
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

import os
import re
import time
import xml.etree.ElementTree as ET

import ifcopenshell
import pytest

try:
    import git
    import git.exc

    HAS_GIT = True
except ImportError:
    HAS_GIT = False

requires_git = pytest.mark.skipif(not HAS_GIT, reason="GitPython not available")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_repo(tmpdir: str) -> "git.Repo":
    repo = git.Repo.init(tmpdir)
    with repo.config_writer() as cfg:
        cfg.set_value("user", "name", "Test User")
        cfg.set_value("user", "email", "test@example.com")
    return repo


def _commit(repo: "git.Repo", tmpdir: str, content: str = "data") -> "git.Commit":
    path = os.path.join(tmpdir, "model.ifc")
    with open(path, "w") as f:
        f.write(content)
    repo.index.add([os.path.normpath(path)])
    return repo.index.commit(content)


@pytest.fixture
def builder():
    """Return a SheetBuilder with bonsai.bim loaded lazily."""
    from bonsai.bim.module.drawing import sheeter

    return sheeter.SheetBuilder()


@pytest.fixture
def builder_at(monkeypatch):
    """Factory: builder_at(ifc_path) patches tool.Ifc.get_path and returns a SheetBuilder."""
    import bonsai.tool as tool
    from bonsai.bim.module.drawing import sheeter

    def factory(ifc_path):
        monkeypatch.setattr(tool.Ifc, "get_path", classmethod(lambda cls: ifc_path))
        return sheeter.SheetBuilder()

    return factory


# ---------------------------------------------------------------------------
# Unit conversions (pure, no add-on registration required)
# ---------------------------------------------------------------------------


class TestConvertToMm:
    def test_mm(self, builder):
        assert builder.convert_to_mm("297mm") == pytest.approx(297.0)

    def test_cm(self, builder):
        assert builder.convert_to_mm("29.7cm") == pytest.approx(297.0)

    def test_in(self, builder):
        assert builder.convert_to_mm("1in") == pytest.approx(25.4)

    def test_px(self, builder):
        # 96 dpi: 96 px = 25.4 mm
        assert builder.convert_to_mm("96px") == pytest.approx(25.4, rel=1e-3)

    def test_pt(self, builder):
        # 72 pt = 25.4 mm
        assert builder.convert_to_mm("72pt") == pytest.approx(25.4, rel=1e-3)


class TestMmToPx:
    def test_round_trip(self, builder):
        assert builder.mm_to_px(builder.convert_to_mm("96px")) == pytest.approx(96.0, rel=1e-3)

    def test_zero(self, builder):
        assert builder.mm_to_px(0.0) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# parse_embedded_svg — Pystache template rendering
# ---------------------------------------------------------------------------


class TestParseEmbeddedSvg:
    def _image_element(self, filename="titleblock.svg"):
        image = ET.Element("image")
        image.attrib["x"] = "0mm"
        image.attrib["y"] = "0mm"
        image.attrib["width"] = "420mm"
        image.attrib["height"] = "297mm"
        image.attrib["{http://www.w3.org/1999/xlink}href"] = filename
        return image

    def _make_builder(self, tmp_path):
        from bonsai.bim.module.drawing import sheeter

        b = sheeter.SheetBuilder()
        b.layout_dir = str(tmp_path)
        b.sheets_dir = str(tmp_path)
        b.defs = ET.Element("defs")
        return b

    def test_variable_substitution(self, tmp_path):
        svg = '<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg"><text>{{Name}}</text></svg>'
        (tmp_path / "titleblock.svg").write_text(svg)

        group = self._make_builder(tmp_path).parse_embedded_svg(self._image_element(), {"Name": "My Sheet"})
        texts = group.findall(".//{http://www.w3.org/2000/svg}text")
        assert any(t.text == "My Sheet" for t in texts)

    def test_revision_rows_rendered(self, tmp_path):
        svg = (
            '<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg"><g>'
            '{{#revisions}}<text x="11" y="{{y}}">{{rev}}</text>{{/revisions}}'
            "</g></svg>"
        )
        (tmp_path / "titleblock.svg").write_text(svg)

        revisions = [
            {"rev": "v1.0", "date": "2024-01-01", "description": "First", "author": "TU", "issued": "", "y": 0},
            {"rev": "v2.0", "date": "2025-01-01", "description": "Second", "author": "TU", "issued": "", "y": -5},
        ]
        group = self._make_builder(tmp_path).parse_embedded_svg(self._image_element(), {"revisions": revisions})
        labels = [t.text for t in group.findall(".//{http://www.w3.org/2000/svg}text")]
        assert "v1.0" in labels
        assert "v2.0" in labels

    def test_has_revisions_section_hidden_when_false(self, tmp_path):
        svg = (
            '<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg">'
            "{{#has_revisions}}<text>HEADERS</text>{{/has_revisions}}"
            "</svg>"
        )
        (tmp_path / "titleblock.svg").write_text(svg)

        group = self._make_builder(tmp_path).parse_embedded_svg(
            self._image_element(), {"has_revisions": False, "revisions": []}
        )
        texts = group.findall(".//{http://www.w3.org/2000/svg}text")
        assert not any(t.text == "HEADERS" for t in texts)

    def test_has_revisions_section_shown_when_true(self, tmp_path):
        svg = (
            '<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg">'
            "{{#has_revisions}}<text>HEADERS</text>{{/has_revisions}}"
            "</svg>"
        )
        (tmp_path / "titleblock.svg").write_text(svg)

        group = self._make_builder(tmp_path).parse_embedded_svg(
            self._image_element(), {"has_revisions": True, "revisions": []}
        )
        texts = group.findall(".//{http://www.w3.org/2000/svg}text")
        assert any(t.text == "HEADERS" for t in texts)


# ---------------------------------------------------------------------------
# _get_git_revisions
# ---------------------------------------------------------------------------


class TestGetGitRevisions:
    def test_no_ifc_path_returns_empty(self, builder_at):
        assert builder_at(None)._get_git_revisions() == []

    @requires_git
    def test_not_a_git_repo_returns_empty(self, builder_at, tmp_path):
        assert builder_at(str(tmp_path / "model.ifc"))._get_git_revisions() == []

    @requires_git
    def test_no_tags_returns_empty(self, builder_at, tmp_path):
        repo = _make_repo(str(tmp_path))
        _commit(repo, str(tmp_path))
        assert builder_at(str(tmp_path / "model.ifc"))._get_git_revisions() == []

    @requires_git
    def test_lightweight_tag_fields(self, builder_at, tmp_path):
        repo = _make_repo(str(tmp_path))
        _commit(repo, str(tmp_path))
        repo.create_tag("v1.0")

        rows = builder_at(str(tmp_path / "model.ifc"))._get_git_revisions()

        assert len(rows) == 1
        assert rows[0]["rev"] == "v1.0"
        assert rows[0]["description"] == ""
        assert rows[0]["author"] == "TU"  # initials of "Test User"
        assert rows[0]["issued"] == ""
        assert rows[0]["y"] == 0

    @requires_git
    def test_annotated_tag_uses_message_first_line(self, builder_at, tmp_path):
        repo = _make_repo(str(tmp_path))
        _commit(repo, str(tmp_path))
        repo.create_tag("v1.0", message="First release\nExtra detail ignored")

        rows = builder_at(str(tmp_path / "model.ifc"))._get_git_revisions()

        assert rows[0]["description"] == "First release"

    @requires_git
    def test_annotated_tag_author_is_tagger_initials(self, builder_at, tmp_path):
        repo = _make_repo(str(tmp_path))
        _commit(repo, str(tmp_path))
        repo.create_tag("v1.0", message="Release")

        rows = builder_at(str(tmp_path / "model.ifc"))._get_git_revisions()

        assert rows[0]["author"] == "TU"

    @requires_git
    def test_date_is_iso_format(self, builder_at, tmp_path):
        repo = _make_repo(str(tmp_path))
        _commit(repo, str(tmp_path))
        repo.create_tag("v1.0", message="Release")

        rows = builder_at(str(tmp_path / "model.ifc"))._get_git_revisions()

        assert re.match(r"\d{4}-\d{2}-\d{2}$", rows[0]["date"])

    @requires_git
    def test_multiple_tags_sorted_oldest_first(self, builder_at, tmp_path):
        repo = _make_repo(str(tmp_path))
        _commit(repo, str(tmp_path), "first")
        repo.create_tag("v1.0", message="First")
        time.sleep(1.1)  # ensure distinct second-level timestamps
        _commit(repo, str(tmp_path), "second")
        repo.create_tag("v2.0", message="Second")

        rows = builder_at(str(tmp_path / "model.ifc"))._get_git_revisions()

        assert len(rows) == 2
        assert rows[0]["rev"] == "v1.0"  # oldest at index 0 (bottom of table)
        assert rows[1]["rev"] == "v2.0"  # newest at index 1 (stacks upward)

    @requires_git
    def test_y_offsets_are_negative_multiples_of_5(self, builder_at, tmp_path):
        repo = _make_repo(str(tmp_path))
        for i in range(3):
            _commit(repo, str(tmp_path), f"rev{i}")
            repo.create_tag(f"v{i}.0", message=f"Release {i}")
            time.sleep(1.1)

        rows = builder_at(str(tmp_path / "model.ifc"))._get_git_revisions()

        assert rows[0]["y"] == 0
        assert rows[1]["y"] == -5
        assert rows[2]["y"] == -10


# ---------------------------------------------------------------------------
# get_titleblock_data
# ---------------------------------------------------------------------------


class TestGetTitleblockData:
    @requires_git
    def test_has_revisions_false_when_no_tags(self, builder_at, tmp_path):
        repo = _make_repo(str(tmp_path))
        _commit(repo, str(tmp_path))

        ifc = ifcopenshell.file()
        sheet = ifc.createIfcDocumentInformation(Identification="DR-01", Name="Site Plan")
        data = builder_at(str(tmp_path / "model.ifc")).get_titleblock_data(sheet)

        assert data["has_revisions"] is False
        assert data["revisions"] == []

    @requires_git
    def test_has_revisions_true_when_tags_present(self, builder_at, tmp_path):
        repo = _make_repo(str(tmp_path))
        _commit(repo, str(tmp_path))
        repo.create_tag("v1.0", message="Issued for review")

        ifc = ifcopenshell.file()
        sheet = ifc.createIfcDocumentInformation(Identification="DR-01", Name="Site Plan")
        data = builder_at(str(tmp_path / "model.ifc")).get_titleblock_data(sheet)

        assert data["has_revisions"] is True
        assert len(data["revisions"]) == 1

    @requires_git
    def test_sheet_ifc_attributes_are_included(self, builder_at, tmp_path):
        repo = _make_repo(str(tmp_path))
        _commit(repo, str(tmp_path))

        ifc = ifcopenshell.file()
        sheet = ifc.createIfcDocumentInformation(Identification="DR-01", Name="Site Plan")
        data = builder_at(str(tmp_path / "model.ifc")).get_titleblock_data(sheet)

        assert data["Identification"] == "DR-01"
        assert data["Name"] == "Site Plan"


# ---------------------------------------------------------------------------
# find_drawing_group — locating a placed drawing in a layout
# ---------------------------------------------------------------------------


class _FakeReference:
    def __init__(self, step_id: int):
        self._id = step_id

    def id(self) -> int:
        return self._id


class TestFindDrawingGroup:
    LAYOUT = (
        '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">'
        '  <g data-type="drawing" data-id="{first}" data-drawing="0aaa">'
        '    <image data-type="foreground"'
        '           xlink:href="..%5Cdrawings%5CPLAN%20-%20LEVEL%201.svg" />'
        "  </g>"
        '  <g data-type="drawing" data-id="{second}" data-drawing="0bbb">'
        '    <image data-type="foreground"'
        '           xlink:href="..%5Cdrawings%5CSECTION%20A.svg" />'
        "  </g>"
        "</svg>"
    )

    def _setup(self, tmp_path, monkeypatch, first="101", second="102", drawing="PLAN - LEVEL 1.svg"):
        import bonsai.tool as tool
        from bonsai.bim.module.drawing import sheeter

        layouts = tmp_path / "layouts"
        layouts.mkdir()
        layout_path = layouts / "A101 - PLANS.svg"
        layout_path.write_text(self.LAYOUT.format(first=first, second=second))

        drawing_path = str(tmp_path / "drawings" / drawing)
        monkeypatch.setattr(tool.Drawing, "get_document_uri", lambda *a, **k: drawing_path)

        root = ET.parse(str(layout_path)).getroot()
        return sheeter.SheetBuilder(), root, str(layout_path)

    def test_matches_on_data_id_when_ids_are_current(self, tmp_path, monkeypatch):
        builder, root, layout_path = self._setup(tmp_path, monkeypatch)
        group = builder.find_drawing_group(root, layout_path, _FakeReference(102))
        assert group is not None
        assert group.attrib["data-drawing"] == "0bbb"

    def test_falls_back_to_the_drawing_path_when_data_id_is_stale(self, tmp_path, monkeypatch):
        """STEP ids do not survive a re-serialisation of the IFC.

        Merging a project renumbers entities, so every data-id in every layout
        points at nothing. Matching on it alone found no group, and the drawing
        was left on the sheet while leaving the model - silently.
        """
        builder, root, layout_path = self._setup(tmp_path, monkeypatch, first="3729889", second="3729890")
        group = builder.find_drawing_group(root, layout_path, _FakeReference(101))
        assert group is not None
        assert group.attrib["data-drawing"] == "0aaa"

    def test_returns_none_when_the_drawing_is_not_on_the_sheet(self, tmp_path, monkeypatch):
        builder, root, layout_path = self._setup(
            tmp_path, monkeypatch, first="3729889", second="3729890", drawing="ELEVATION - NORTH.svg"
        )
        assert builder.find_drawing_group(root, layout_path, _FakeReference(101)) is None


# ---------------------------------------------------------------------------
# as_template_data - values for tools that render sheet templates themselves
# ---------------------------------------------------------------------------


class TestAsTemplateData:
    """Values must render as pystache would render them, and survive JSON."""

    def _convert(self, value):
        from bonsai.bim.module.drawing import sheeter

        return sheeter.as_template_data(value)

    def test_scalars_become_text_as_pystache_prints_them(self):
        assert self._convert({"Name": None, "Scale": 1.0, "id": 5}) == {"Name": "None", "Scale": "1.0", "id": "5"}

    def test_booleans_stay_booleans_for_sections(self):
        assert self._convert({"has_revisions": False}) == {"has_revisions": False}

    def test_rows_stay_a_list_even_when_empty(self):
        # An empty list turned into the text "[]" would be truthy, and a
        # {{#revisions}} section would render once for nothing.
        assert self._convert({"revisions": []}) == {"revisions": []}
        assert self._convert({"revisions": [{"rev": "v1", "y": 0}]}) == {"revisions": [{"rev": "v1", "y": "0"}]}

    def test_other_sequences_are_text(self):
        assert self._convert({"Editors": ()}) == {"Editors": "()"}


# ---------------------------------------------------------------------------
# Editing template values - the write half, for tools that show sheets
# ---------------------------------------------------------------------------


@pytest.fixture
def sheet_model(tmp_path, monkeypatch):
    """A model with one sheet, one drawing placed on it, and tool.Drawing stubbed.

    The methods stubbed are the ones that reach into Blender or resolve URIs
    against the project; everything the code under test decides - which sheet a
    layout belongs to, which view a request names, what may be written - is real.
    """
    import ifcopenshell.api

    import bonsai.tool as tool
    from bonsai.bim.module.drawing import sheeter

    layout_path = str(tmp_path / "layouts" / "A01 - PLANS.svg")
    drawing_path = str(tmp_path / "drawings" / "MY STOREY PLAN.svg")

    ifc = ifcopenshell.file()
    sheet = ifc.createIfcDocumentInformation(Identification="A01", Name="PLANS", Scope="SHEET")
    layout_ref = ifc.createIfcDocumentReference(Location=layout_path, Description="LAYOUT")
    drawing_ref = ifc.createIfcDocumentReference(Location=drawing_path, Description="DRAWING", Identification="1")
    annotation = ifc.createIfcAnnotation(GlobalId="0abcdefghijklmnopqrstu", ObjectType="DRAWING", Name="MY STOREY PLAN")

    references = {sheet.id(): [layout_ref, drawing_ref]}
    uris = {layout_ref.id(): layout_path, drawing_ref.id(): drawing_path}

    def get_document_uri(document, description=None):
        if document.is_a("IfcDocumentInformation"):
            for reference in references.get(document.id(), []):
                if reference.Description == description:
                    return uris[reference.id()]
            return None
        return uris.get(document.id())

    monkeypatch.setattr(tool.Ifc, "get", classmethod(lambda cls: ifc))
    monkeypatch.setattr(tool.Ifc, "get_path", classmethod(lambda cls: str(tmp_path / "model.ifc")))
    # tool.Ifc.run reaches for the file Blender has open, not the one patched in.
    monkeypatch.setattr(
        tool.Ifc, "run", classmethod(lambda cls, command, **kwargs: ifcopenshell.api.run(command, ifc, **kwargs))
    )
    monkeypatch.setattr(tool.Drawing, "get_document_uri", staticmethod(get_document_uri))
    monkeypatch.setattr(
        tool.Drawing, "get_document_references", staticmethod(lambda info: references.get(info.id(), []))
    )
    monkeypatch.setattr(tool.Drawing, "get_reference_description", staticmethod(lambda ref: ref.Description))
    monkeypatch.setattr(tool.Drawing, "get_drawing_document", staticmethod(lambda drawing: drawing_ref))
    monkeypatch.setattr(tool.Drawing, "get_sheet_identification", staticmethod(lambda s: s.Identification))
    monkeypatch.setattr(tool.Drawing, "get_drawing_human_scale", staticmethod(lambda drawing: '1/4"=1\'-0"'))
    monkeypatch.setattr(tool.Drawing, "import_sheets", staticmethod(lambda: None))
    monkeypatch.setattr(tool.Drawing, "import_drawings", staticmethod(lambda: None))

    class Model:
        pass

    model = Model()
    model.builder = sheeter.SheetBuilder()
    model.ifc = ifc
    model.sheet = sheet
    model.drawing = annotation
    model.reference = drawing_ref
    model.layout = layout_path
    model.drawing_path = drawing_path
    # So a test can move the layout the way rename_sheet would.
    model.uris = uris
    model.layout_ref = layout_ref
    return model


@pytest.fixture
def calls(monkeypatch):
    """Record what would be asked of bonsai.core.drawing, without doing it."""
    import bonsai.core.drawing as core

    recorded = []
    for name in ("rename_sheet", "rename_reference", "update_drawing_name"):
        monkeypatch.setattr(
            core,
            name,
            lambda *a, _name=name, **kw: recorded.append((_name, kw)),
        )
    return recorded


class TestFindSheet:
    def test_matches_a_layout_by_path(self, sheet_model):
        assert sheet_model.builder.find_sheet(sheet_model.layout) == sheet_model.sheet

    def test_matches_however_the_path_is_spelled(self, sheet_model, tmp_path):
        # The caller is another tool: it may have the path from a layout link,
        # with a different case or a relative step in it.
        spelled = os.path.join(str(tmp_path), "layouts", "..", "layouts", "A01 - PLANS.svg").upper()
        assert sheet_model.builder.find_sheet(spelled) == sheet_model.sheet

    def test_none_when_no_sheet_uses_it(self, sheet_model, tmp_path):
        assert sheet_model.builder.find_sheet(str(tmp_path / "layouts" / "A99.svg")) is None


class TestGetEditableFields:
    def test_a_titleblock_field_reports_its_value(self, sheet_model):
        fields = sheet_model.builder.get_editable_fields(sheet_model.layout, {"kind": "sheet"}, ["Name"])["fields"]
        assert fields == [{"name": "Name", "value": "PLANS", "editable": True}]

    def test_an_unset_field_is_empty_not_the_word_None(self, sheet_model):
        # A build prints "None" for an unset attribute, but this value goes into
        # a box someone types in - and saving it back would set that word.
        fields = sheet_model.builder.get_editable_fields(sheet_model.layout, {"kind": "sheet"}, ["Revision"])["fields"]
        assert fields[0]["value"] == ""

    def test_scale_is_read_only_with_a_reason(self, sheet_model):
        fields = sheet_model.builder.get_editable_fields(
            sheet_model.layout, {"kind": "drawing", "globalId": "0abcdefghijklmnopqrstu"}, ["Scale"]
        )["fields"]
        assert fields[0]["editable"] is False
        assert "camera" in fields[0]["reason"]

    def test_a_sheet_field_on_a_view_title_says_where_to_edit_it(self, sheet_model):
        fields = sheet_model.builder.get_editable_fields(
            sheet_model.layout, {"kind": "drawing", "globalId": "0abcdefghijklmnopqrstu"}, ["SheetName"]
        )["fields"]
        assert fields[0]["editable"] is False
        assert "titleblock" in fields[0]["reason"]

    def test_a_drawing_is_found_by_the_file_it_places(self, sheet_model):
        answer = sheet_model.builder.get_editable_fields(
            sheet_model.layout, {"kind": "placement", "path": sheet_model.drawing_path}, ["Name"]
        )
        assert answer["kind"] == "drawing"
        # The reference has no name of its own, so the title shows the drawing's.
        assert answer["fields"][0]["value"] == "MY STOREY PLAN"

    def test_an_unknown_view_is_refused_by_name(self, sheet_model, tmp_path):
        with pytest.raises(ValueError, match="no such view"):
            sheet_model.builder.get_editable_fields(
                sheet_model.layout, {"kind": "placement", "path": str(tmp_path / "drawings" / "GONE.svg")}, ["Name"]
            )

    def test_an_unknown_layout_is_refused_by_name(self, sheet_model, tmp_path):
        with pytest.raises(ValueError, match="A99"):
            sheet_model.builder.get_editable_fields(str(tmp_path / "layouts" / "A99.svg"), {"kind": "sheet"}, ["Name"])


class TestSetTemplateValues:
    def test_renaming_a_sheet_keeps_the_field_not_being_set(self, sheet_model, calls):
        # Identification and Name together name the layout and sheet files, so
        # Bonsai renames on both at once - setting one must not blank the other.
        sheet_model.builder.set_template_values(sheet_model.layout, {"kind": "sheet"}, {"Name": "PLANS AND SECTIONS"})
        assert calls == [("rename_sheet", {"sheet": sheet_model.sheet, "identification": "A01", "name": "PLANS AND SECTIONS"})]

    def test_renaming_a_sheet_sets_both_when_both_are_given(self, sheet_model, calls):
        sheet_model.builder.set_template_values(
            sheet_model.layout, {"kind": "sheet"}, {"Identification": "A02", "Name": "SECTIONS"}
        )
        assert calls[0][1]["identification"] == "A02"
        assert calls[0][1]["name"] == "SECTIONS"

    def test_a_plain_titleblock_field_is_written_as_an_attribute(self, sheet_model, calls):
        sheet_model.builder.set_template_values(sheet_model.layout, {"kind": "sheet"}, {"Revision": "C"})
        assert calls == []
        assert sheet_model.sheet.Revision == "C"

    def test_renaming_a_drawing_goes_through_bonsai(self, sheet_model, calls):
        # Renaming a drawing moves its SVG and relinks every layout placing it,
        # which is the whole reason an edit comes here rather than to the file.
        sheet_model.builder.set_template_values(
            sheet_model.layout, {"kind": "drawing", "globalId": "0abcdefghijklmnopqrstu"}, {"Name": "LEVEL 1 PLAN"}
        )
        assert calls == [("update_drawing_name", {"drawing": sheet_model.drawing, "name": "LEVEL 1 PLAN"})]

    def test_a_named_reference_is_renamed_in_place(self, sheet_model, calls):
        # A view-title shows the reference's own name when it has one, so that
        # is where the edit goes - the drawing keeps its name and its file.
        sheet_model.reference.Name = "PLAN AS PLACED"
        sheet_model.builder.set_template_values(
            sheet_model.layout, {"kind": "drawing", "globalId": "0abcdefghijklmnopqrstu"}, {"Name": "PLAN, AS PLACED"}
        )
        assert calls == []
        assert sheet_model.reference.Name == "PLAN, AS PLACED"

    def test_a_view_number_goes_through_bonsai(self, sheet_model, calls):
        sheet_model.builder.set_template_values(
            sheet_model.layout, {"kind": "drawing", "globalId": "0abcdefghijklmnopqrstu"}, {"Identification": "3"}
        )
        assert calls == [("rename_reference", {"reference": sheet_model.reference, "identification": "3"})]

    def test_a_read_only_field_is_refused_with_its_reason(self, sheet_model, calls):
        with pytest.raises(ValueError, match="camera"):
            sheet_model.builder.set_template_values(
                sheet_model.layout, {"kind": "drawing", "globalId": "0abcdefghijklmnopqrstu"}, {"Scale": "1:50"}
            )
        assert calls == []

    def test_nothing_is_written_when_one_field_is_refused(self, sheet_model, calls):
        # All or nothing: a half-applied edit would leave the sheet showing a
        # mixture of what was asked for and what was there.
        with pytest.raises(ValueError):
            sheet_model.builder.set_template_values(
                sheet_model.layout, {"kind": "sheet"}, {"Name": "SECTIONS", "Scope": "DRAWING"}
            )
        assert calls == []
        assert sheet_model.sheet.Name == "PLANS"

    def test_it_answers_with_where_the_layout_is_now(self, sheet_model, monkeypatch, tmp_path):
        # Renaming a sheet moves its layout, so the path the caller asked about
        # is gone by the time it is answered. Without being told the new one it
        # would have to wait to notice the file move before it could ask again.
        import bonsai.core.drawing as core

        moved = str(tmp_path / "layouts" / "A02 - PLANS.svg")
        monkeypatch.setattr(
            core,
            "rename_sheet",
            lambda *a, **kw: sheet_model.uris.update({sheet_model.layout_ref.id(): moved}),
        )
        answer = sheet_model.builder.set_template_values(
            sheet_model.layout, {"kind": "sheet"}, {"Identification": "A02"}
        )
        assert answer["layout"] == os.path.abspath(moved)
        assert answer["changed"] == ["Identification"]

    def test_an_empty_edit_changes_nothing(self, sheet_model, calls):
        assert sheet_model.builder.set_template_values(sheet_model.layout, {"kind": "sheet"}, {}) == {"changed": []}
        assert calls == []
