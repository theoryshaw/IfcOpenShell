# Bonsai - OpenBIM Blender Add-on
# Copyright (C) 2020, 2021 Dion Moult <dion@thinkmoult.com>
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

import ntpath
import os
import re
import shutil
import urllib.parse
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Union
from xml.dom import minidom

import ifcopenshell.util.geolocation
import pystache
from mathutils import Vector

import bonsai.tool as tool

os.environ.setdefault("GIT_PYTHON_REFRESH", "quiet")

VIEW_TITLE_OFFSET_Y = 5
DRAWING_PADDING = 10
DEFAULT_POSITION = Vector((30, 30))
SVG = "{http://www.w3.org/2000/svg}"
XLINK = "{http://www.w3.org/1999/xlink}"
# Presentation attributes whose value may be a `url(#target)` reference. They are
# equivalent to the same named CSS properties, so a document is free to use either
# these or `style`, and both have to be rewritten when ids are prefixed.
URL_ATTRIBUTES = (
    "clip-path",
    "color-profile",
    "cursor",
    "fill",
    "filter",
    "marker",
    "marker-end",
    "marker-mid",
    "marker-start",
    "mask",
    "stroke",
)


def as_template_data(value):
    """A value as a sheet template sees it, in a form that survives JSON.

    pystache renders a variable with str(), so everything becomes text - an unset
    attribute is "None" - except what templates test and iterate: booleans, and
    lists of rows such as the titleblock's revisions.
    """
    if isinstance(value, dict):
        return {k: as_template_data(v) for k, v in value.items()}
    if isinstance(value, bool):
        return value
    if isinstance(value, list) and all(isinstance(v, dict) for v in value):
        return [as_template_data(v) for v in value]
    return str(value)


class SheetBuilder:
    def __init__(self):
        self.scale = "NTS"

    def create(self, layout_path: str, titleblock_name: str) -> None:
        root = ET.Element("svg")
        root.attrib["xmlns"] = "http://www.w3.org/2000/svg"
        root.attrib["xmlns:xlink"] = "http://www.w3.org/1999/xlink"
        root.attrib["xmlns:sodipodi"] = "http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd"
        root.attrib["id"] = "root"
        root.attrib["version"] = "1.1"

        sheet_dir = os.path.dirname(layout_path)
        ootb_titleblock_path = tool.Blender.get_data_dir_path(
            Path("templates") / "titleblocks" / (titleblock_name + ".svg")
        )
        titleblock_path = tool.Ifc.resolve_uri(tool.Drawing.get_default_titleblock_path(titleblock_name))

        os.makedirs(sheet_dir, exist_ok=True)
        os.makedirs(os.path.dirname(titleblock_path), exist_ok=True)
        if not os.path.exists(titleblock_path):
            shutil.copy(ootb_titleblock_path, titleblock_path)

        view_root = ET.parse(titleblock_path).getroot()
        view_width = self.convert_to_mm(view_root.attrib["width"])
        view_height = self.convert_to_mm(view_root.attrib["height"])
        view = ET.SubElement(root, "g")
        view.attrib["data-type"] = "titleblock"
        view.attrib["sodipodi:insensitive"] = "true"
        titleblock = ET.SubElement(view, "image")
        titleblock.attrib["xlink:href"] = Path(os.path.relpath(titleblock_path, sheet_dir)).as_posix()
        titleblock.attrib["x"] = "0"
        titleblock.attrib["y"] = "0"
        titleblock.attrib["width"] = str(view_width)
        titleblock.attrib["height"] = str(view_height)

        root.attrib["width"] = "{}mm".format(view_width)
        root.attrib["height"] = "{}mm".format(view_height)
        root.attrib["viewBox"] = "0 0 {} {}".format(view_width, view_height)

        with open(layout_path, "w") as f:
            f.write(minidom.parseString(ET.tostring(root)).toprettyxml(indent="    "))

    def add_drawing(
        self,
        reference: ifcopenshell.entity_instance,
        drawing: ifcopenshell.entity_instance,
        sheet: ifcopenshell.entity_instance,
    ) -> None:
        filename = drawing.Name
        layout_path = tool.Drawing.get_document_uri(sheet, "LAYOUT")
        assert layout_path
        layout_dir = os.path.dirname(layout_path)

        drawing_path = tool.Drawing.get_document_uri(tool.Drawing.get_drawing_reference(drawing))

        if not os.path.exists(layout_path) or not os.path.exists(drawing_path):
            raise FileNotFoundError

        ET.register_namespace("", "http://www.w3.org/2000/svg")
        ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")

        layout_tree = ET.parse(layout_path)
        layout_root = layout_tree.getroot()

        view_tree = ET.parse(drawing_path)
        view_root = view_tree.getroot()

        # The view is placed into a group with a background image element.
        # Although the foreground SVG already has a background, it is duplicated
        # here to accommodate browsers which do not nest images.
        view = ET.SubElement(layout_root, "g")
        view.attrib["data-type"] = "drawing"
        view.attrib["data-id"] = str(reference.id())
        view.attrib["data-drawing"] = drawing.GlobalId
        view_width = self.convert_to_mm(view_root.attrib["width"])
        view_height = self.convert_to_mm(view_root.attrib["height"])

        x, y = self.next_drawing_location(layout_root, view_width)

        # add foreground
        if os.path.isfile(drawing_path):
            foreground = ET.SubElement(view, "image")
            foreground.attrib["data-type"] = "foreground"
            foreground.attrib["xlink:href"] = os.path.relpath(drawing_path, layout_dir)
            foreground.attrib["x"] = str(x)
            foreground.attrib["y"] = str(y)
            foreground.attrib["width"] = str(view_width)
            foreground.attrib["height"] = str(view_height)

        self.add_view_title(x, view_height + y + VIEW_TITLE_OFFSET_Y, view, layout_dir)
        layout_tree.write(layout_path)

    def next_drawing_location(self, layout_root: ET.Element, next_width: float) -> list:
        titleblocks = layout_root.findall(f'{SVG}g[@data-type="titleblock"]')
        drawings = layout_root.findall(f'{SVG}g[@data-type="drawing"]')

        # how wide is the title block frame
        try:
            titleblock_width = self.convert_to_mm(titleblocks[0][0].attrib["width"])
        except (IndexError, AttributeError):
            titleblock_width = 840.0

        # where does the last drawing finish
        try:
            last = drawings[-1][0]
            last_width = self.convert_to_mm(last.attrib["width"])
            last_x = self.convert_to_mm(last.attrib["x"])
            last_y = self.convert_to_mm(last.attrib["y"])
        except (IndexError, AttributeError):
            return [DEFAULT_POSITION.x, DEFAULT_POSITION.y]

        # check if the new drawing fits in the current row
        if last_x + last_width + DRAWING_PADDING + next_width + DEFAULT_POSITION.x < titleblock_width:
            return [last_x + last_width + DRAWING_PADDING, last_y]

        # start a new row, find the y
        for drawing in drawings:
            for image in drawing:
                try:
                    image_y = self.convert_to_mm(image.attrib["y"])
                    image_height = self.convert_to_mm(image.attrib["height"])
                except AttributeError:
                    return [DEFAULT_POSITION.x, DEFAULT_POSITION.y]
                if image_y + image_height + DRAWING_PADDING > last_y:
                    last_y = image_y + image_height + DRAWING_PADDING
        return [DEFAULT_POSITION.x, last_y]

    def update_sheet_drawing_sizes(self, sheet: ifcopenshell.entity_instance) -> None:
        ET.register_namespace("", "http://www.w3.org/2000/svg")

        layout_path = tool.Drawing.get_document_uri(sheet, "LAYOUT")
        assert layout_path
        layout_tree = ET.parse(layout_path)
        layout_root = layout_tree.getroot()
        ifc_file = tool.Ifc.get()

        # iterate over all drawings in the sheet
        drawings_views = layout_root.findall(f'{SVG}g[@data-type="drawing"]')

        for drawing_view in drawings_views:
            # find drawing in ifc file to get the drawing dimensions
            drawing = ifc_file.by_guid(drawing_view.attrib.get("data-drawing"))
            drawing_path = tool.Drawing.get_document_uri(tool.Drawing.get_drawing_reference(drawing))
            drawing_tree = ET.parse(drawing_path)
            drawing_root = drawing_tree.getroot()
            view_width = round(self.convert_to_mm(drawing_root.attrib.get("width")), 2)
            view_height = round(self.convert_to_mm(drawing_root.attrib.get("height")), 2)

            foreground = drawing_view.find(f'.//{SVG}image[@data-type="foreground"]')
            current_width = round(float(foreground.attrib["width"]), 2)
            current_height = round(float(foreground.attrib["height"]), 2)

            # Check if the dimensions have changed
            if current_width != view_width or current_height != view_height:
                height_delta = view_height - current_height

                for image in drawing_view.findall(f"{SVG}image"):
                    if image.attrib["data-type"] == "view-title":
                        # title sits below the drawing, so it tracks the bottom edge
                        image.attrib["y"] = str(float(image.attrib["y"]) + height_delta)
                    else:
                        image.attrib["width"] = str(view_width)
                        image.attrib["height"] = str(view_height)

        layout_tree.write(layout_path)

    def update_sheet_schedule_sizes(self, sheet: ifcopenshell.entity_instance) -> None:
        ET.register_namespace("", "http://www.w3.org/2000/svg")

        layout_path = tool.Drawing.get_document_uri(sheet, "LAYOUT")
        assert layout_path
        layout_tree = ET.parse(layout_path)
        layout_root = layout_tree.getroot()
        ifc_file = tool.Ifc.get()

        for document_view in layout_root.findall(f"{SVG}g[@data-document]"):
            document = ifc_file.by_id(int(document_view.attrib["data-document"]))
            document_path = tool.Drawing.get_path_with_ext(tool.Drawing.get_document_uri(document), "svg")
            if not os.path.exists(document_path):
                continue
            document_tree = ET.parse(document_path)
            document_root = document_tree.getroot()
            view_width = round(self.convert_to_mm(document_root.attrib.get("width")), 2)
            view_height = round(self.convert_to_mm(document_root.attrib.get("height")), 2)

            content = document_view.find(f'.//{SVG}image[@data-type="content"]')
            if content is None:
                continue
            current_width = round(float(content.attrib["width"]), 2)
            current_height = round(float(content.attrib["height"]), 2)

            if current_width != view_width or current_height != view_height:
                height_delta = view_height - current_height

                for image in document_view.findall(f"{SVG}image"):
                    if image.attrib["data-type"] == "view-title":
                        # view-title sits below the content, so track height changes
                        image.attrib["y"] = str(float(image.attrib["y"]) + height_delta)
                    else:
                        # upper-left corner stays fixed; only size changes
                        image.attrib["width"] = str(view_width)
                        image.attrib["height"] = str(view_height)

        layout_tree.write(layout_path)

    def find_drawing_group(
        self,
        layout_root: ET.Element,
        layout_path: str,
        reference: ifcopenshell.entity_instance,
    ) -> Union[ET.Element, None]:
        """Find the <g> a drawing reference was placed into.

        `data-id` is the reference's STEP id, which is only meaningful while the
        file keeps the numbering it had when the drawing was added. Merging a
        project - or any round trip through a tool that renumbers entities -
        leaves every `data-id` in every layout pointing at nothing, and matching
        on it alone then finds no group at all.

        The drawing's own file is stable across that, so it is used as a
        fallback. Layout hrefs are relative to the layout and URL-encoded, hence
        the unquote and the join.
        """
        for g in layout_root.findall(f"{SVG}g"):
            if g.attrib.get("data-id") == str(reference.id()):
                return g

        drawing_path = tool.Drawing.get_document_uri(reference)
        if not drawing_path:
            return None
        wanted = os.path.normcase(os.path.normpath(drawing_path))
        layout_dir = os.path.dirname(layout_path)

        for g in layout_root.findall(f'{SVG}g[@data-type="drawing"]'):
            foreground = g.find(f'.//{SVG}image[@data-type="foreground"]')
            if foreground is None:
                continue
            href = foreground.attrib.get(f"{XLINK}href") or foreground.attrib.get("href")
            if not href:
                continue
            candidate = os.path.normpath(os.path.join(layout_dir, urllib.parse.unquote(href)))
            if os.path.normcase(candidate) == wanted:
                return g
        return None

    def remove_drawing(self, reference: ifcopenshell.entity_instance, sheet: ifcopenshell.entity_instance) -> None:
        ET.register_namespace("", "http://www.w3.org/2000/svg")

        layout_path = tool.Drawing.get_document_uri(sheet, "LAYOUT")
        assert layout_path
        if not os.path.exists(layout_path):
            return
        layout_tree = ET.parse(layout_path)
        layout_root = layout_tree.getroot()

        group = self.find_drawing_group(layout_root, layout_path, reference)
        if group is None:
            # Nothing to remove, so nothing to write. Rewriting the layout here
            # would reserialise it - a changed mtime and a whole-file diff for a
            # removal that did not happen, which is what made this hard to spot.
            print(
                f"WARNING. Could not find drawing #{reference.id()} in layout '{layout_path}'. "
                "It has been removed from the sheet in the IFC, but the layout is unchanged."
            )
            return

        layout_root.remove(group)
        layout_tree.write(layout_path)

    def add_document(
        self,
        reference: ifcopenshell.entity_instance,
        document: ifcopenshell.entity_instance,
        sheet: ifcopenshell.entity_instance,
    ) -> None:
        view_path = tool.Drawing.get_path_with_ext(tool.Drawing.get_document_uri(document), "svg")
        if not os.path.exists(view_path):
            tool.Drawing.create_svg_document(document)
        document_name = os.path.splitext(os.path.basename(view_path))[0]
        layout_path = tool.Drawing.get_document_uri(sheet, "LAYOUT")
        assert layout_path
        layout_dir = os.path.dirname(layout_path)

        ET.register_namespace("", "http://www.w3.org/2000/svg")
        ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")

        layout_tree = ET.parse(layout_path)
        layout_root = layout_tree.getroot()

        view_tree = ET.parse(view_path)
        view_root = view_tree.getroot()
        view_width = self.convert_to_mm(view_root.attrib.get("width"))
        view_height = self.convert_to_mm(view_root.attrib.get("height"))

        x, y = self.next_drawing_location(layout_root, view_width)

        view = ET.SubElement(layout_root, "g")
        view.attrib["data-id"] = str(reference.id())
        view.attrib["data-type"] = document.Scope.lower()
        view.attrib["data-document"] = str(document.id())

        foreground = ET.SubElement(view, "image")
        foreground.attrib["data-type"] = "content"
        foreground.attrib["xlink:href"] = os.path.relpath(view_path, layout_dir)
        foreground.attrib["x"] = str(x)
        foreground.attrib["y"] = str(y)
        foreground.attrib["width"] = str(view_width)
        foreground.attrib["height"] = str(view_height)

        self.add_view_title(x, view_height + y + VIEW_TITLE_OFFSET_Y, view, layout_dir)
        layout_tree.write(layout_path)

    def add_view_title(self, x: float, y: float, parent: ET.Element, layout_dir: str) -> None:
        title_path = os.path.join(layout_dir, "assets", "view-title.svg")
        os.makedirs(os.path.dirname(title_path), exist_ok=True)
        if not os.path.exists(title_path):
            ootb_title = tool.Blender.get_data_dir_path(Path("assets") / "view-title.svg")
            shutil.copy(ootb_title, title_path)

        title_tree = ET.parse(title_path)
        title_root = title_tree.getroot()
        title = ET.SubElement(parent, "image")
        title.attrib["data-type"] = "view-title"
        title.attrib["xlink:href"] = os.path.relpath(title_path, layout_dir)
        title.attrib["x"] = str(x)
        title.attrib["y"] = str(y)
        title.attrib["width"] = str(self.convert_to_mm(title_root.attrib["width"]))
        title.attrib["height"] = str(self.convert_to_mm(title_root.attrib["height"]))

    def build(self, sheet: ifcopenshell.entity_instance) -> dict[str, str]:
        layout_path = tool.Drawing.get_document_uri(sheet, "LAYOUT")
        assert layout_path
        self.layout_dir = os.path.dirname(layout_path)

        sheet_path = tool.Ifc.resolve_uri(tool.Drawing.get_default_sheet_path(sheet[0], sheet.Name))
        self.sheets_dir = os.path.dirname(sheet_path)

        os.makedirs(self.sheets_dir, exist_ok=True)

        ET.register_namespace("", "http://www.w3.org/2000/svg")
        ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")

        tree = ET.parse(layout_path)
        root = tree.getroot()

        self.defs = ET.Element("defs")
        root.append(self.defs)

        self.build_titleblock(root, sheet)
        self.build_drawings(root, sheet)
        self.build_documents(root, sheet)

        with open(sheet_path, "wb") as output:
            tree.write(output)

        return {"SHEET": sheet_path}

    def get_titleblock_data(self, sheet: ifcopenshell.entity_instance) -> dict:
        data = sheet.get_info()
        revisions = self._get_git_revisions()
        data["revisions"] = revisions
        data["has_revisions"] = bool(revisions)
        return data

    def _get_git_revisions(self) -> list[dict]:
        try:
            import git
        except ImportError:
            return []

        ifc_path = tool.Ifc.get_path()
        if not ifc_path:
            return []
        try:
            repo = git.Repo(ifc_path, search_parent_directories=True)
        except Exception:
            return []

        # Oldest-first so the SVG template can anchor at the bottom: oldest
        # tag sits at y=0 (the anchor point) and newer tags stack upward.
        # Always sort and date by the tagged commit, not when the tag was applied.
        tags = sorted(repo.tags, key=lambda t: t.commit.committed_date)

        def initials(actor) -> str:
            if not actor or not actor.name:
                return ""
            return "".join(w[0].upper() for w in actor.name.split() if w)

        rows = []
        for i, tag_ref in enumerate(tags):
            date = datetime.fromtimestamp(tag_ref.commit.committed_date).date().isoformat()
            if tag_ref.tag:
                description = (tag_ref.tag.message or "").strip().splitlines()[0]
                author = initials(tag_ref.tag.tagger)
            else:
                description = ""
                author = initials(tag_ref.commit.author)
            # y is a negative offset from the group anchor (5 mm row height to
            # match the A3 titleblock grid). Oldest tag sits at y=0 (the anchor);
            # newer tags stack upward so the oldest stays at a fixed position.
            rows.append(
                {
                    "rev": tag_ref.name,
                    "date": date,
                    "description": description,
                    "author": author,
                    "issued": "",
                    "y": -i * 5,
                }
            )
        return rows

    def build_titleblock(self, root: ET.Element, sheet: ifcopenshell.entity_instance) -> None:
        titleblock = root.findall(f'{SVG}g[@data-type="titleblock"]')[0]
        image = titleblock.findall(f"{SVG}image")[0]
        g = self.parse_embedded_svg(image, self.get_titleblock_data(sheet))
        # the titleblock shares the sheet with the drawings and references, so its
        # ids need the same namespacing. `sheet.id()` cannot collide with the
        # document ids used for the other views, they all come from the same file.
        g = self.ensure_unique_ids(g, sheet.id())
        grid_north = ifcopenshell.util.geolocation.get_grid_north(tool.Ifc.get()) * -1
        true_north = ifcopenshell.util.geolocation.get_true_north(tool.Ifc.get()) * -1
        for north in g.iterfind(f'.//{SVG}g[@data-type="grid-north"]'):
            north.attrib["transform"] = f"rotate({grid_north})"
        for north in g.iterfind(f'.//{SVG}g[@data-type="true-north"]'):
            north.attrib["transform"] = f"rotate({true_north})"
        titleblock.append(g)
        titleblock.remove(image)

    def ensure_unique_ids(self, svg: ET.Element, view_id: int) -> ET.Element:
        """ensures all view's classes and ids will be unique for the whole sheet
        by adding `view_id` based prefix.

        Applies to both drawings and referenced documents. Referenced documents
        (for example markdown converted to SVG) commonly define glyph symbols with
        generic ids like `glyph-0-0` and reference them via `<use>`. Without a per
        view prefix these ids collide across embedded views, so every `<use>`
        resolves to the first matching id and the text is garbled.
        """
        prefix = f"d{view_id}"  # just number doesn't work

        def replace_urls(text: str) -> str:
            """replace urls `url(#marker)` with `url(#prefix-marker)`
            since `url(#marker.prefix)` doesn't seem to work
            """
            return re.sub(r"url\(#([^\)]+)\)", rf"url(#{prefix}-\1)", text)

        # add .prefix class to all css selectors
        style = svg.find(f"{SVG}defs/{SVG}style")
        if style is not None and style.text is not None:
            style_data = style.text
            text = ""
            brackets_level = 0

            for l in style_data:
                if l == "{":
                    if brackets_level == 0:
                        # Get all accumulated selector text (may span multiple lines)
                        # Find where the last rule ended (after last }) or start of text
                        last_close = text.rfind("}")
                        if last_close == -1:
                            selector_text = text
                            text = ""
                        else:
                            selector_text = text[last_close + 1 :]
                            text = text[: last_close + 1]

                        # Process all selectors (split by comma)
                        css_selectors = []
                        for css_selector in selector_text.split(","):
                            css_selector = css_selector.strip()
                            if css_selector:  # Only process non-empty selectors
                                css_selector = f"{css_selector}.{prefix}"
                                css_selectors.append(css_selector)

                        text += ", ".join(css_selectors) + " "
                    brackets_level += 1
                elif l == "}":
                    brackets_level -= 1
                text += l

            style.text = replace_urls(text)

        for svg_element in svg.findall(f".//*"):
            if svg_element.tag in (f"{SVG}style", f"{SVG}svg"):
                continue
            attrib = svg_element.attrib
            # add "prefix-" to all ids
            if "id" in attrib:
                attrib["id"] = f"{prefix}-{attrib['id']}"
            # add class "prefix" to all classes
            if "class" in attrib:
                attrib["class"] += f" {prefix}"
            # rewrite `url(#target)` wherever it can appear: the `style` property
            # and every presentation attribute. Inkscape authored references rely on
            # the latter, e.g. `<g clip-path="url(#clipPath1)">`, which is left
            # dangling if only the ids are prefixed.
            for url_attrib in ("style",) + URL_ATTRIBUTES:
                value = attrib.get(url_attrib)
                if value is not None:
                    attrib[url_attrib] = replace_urls(value)
            # local fragment hrefs: `<use>` glyphs, `<textPath>`, `<mpath>` and
            # gradients or patterns inheriting from another via `xlink:href`
            for href_attrib in (f"{XLINK}href", "href"):
                href = attrib.get(href_attrib)
                if href is not None and href.startswith("#"):
                    attrib[href_attrib] = f"#{prefix}-{href[1:]}"

        return svg

    def build_drawings(self, root: ET.Element, sheet: ifcopenshell.entity_instance):
        for view in root.findall(f'{SVG}g[@data-type="drawing"]'):
            drawing_id = int(view.attrib["data-id"])
            try:
                reference = tool.Ifc.get().by_id(int(view.attrib["data-id"]))
                drawing = tool.Ifc.get().by_guid(view.attrib["data-drawing"])
            except RuntimeError:
                # Perhaps the SVG has outdated content or is edited externally which we cannot control.
                continue

            images = view.findall(f"{SVG}image")

            foreground = None
            view_title = None

            for image in images:
                if image.attrib["data-type"] == "foreground":
                    foreground = image
                elif image.attrib["data-type"] == "view-title":
                    view_title = image

            if foreground is not None:
                svg = self.parse_embedded_svg(foreground, {})
                svg = self.ensure_unique_ids(svg, drawing_id)
                view.append(svg)

            if view_title is not None:
                assert foreground is not None
                foreground_path = self.get_href(foreground)
                data = self.get_drawing_view_title_data(reference, sheet, drawing, foreground_path)
                view.append(self.parse_embedded_svg(view_title, data))

            for image in images:
                view.remove(image)

    def get_drawing_view_title_data(
        self,
        reference: ifcopenshell.entity_instance,
        sheet: ifcopenshell.entity_instance,
        drawing: ifcopenshell.entity_instance,
        foreground_path: str,
    ) -> dict:
        """Template data for a drawing's view-title.

        Shared by `build_drawings` and `get_template_values`, so a tool showing a
        sheet without building it fills the title exactly as a build would.
        """
        data = reference.get_info()
        data.update({"Sheet" + k: v for k, v in sheet.get_info().items()})
        if not data["Name"]:
            data["Name"] = drawing.Name or ntpath.basename(foreground_path)[0:-4]

        # If a perspective drawing, don't add scale to view title
        try:
            is_perspective = (
                drawing.Representation.Representations[0]
                .Items[0]
                .TreeRootExpression.FirstOperand.is_a("IfcRectangularPyramid")
            )
        except AttributeError:
            is_perspective = False

        if not is_perspective:
            data["Scale"] = tool.Drawing.get_drawing_human_scale(drawing)
        return data

    def build_documents(self, root: ET.Element, sheet: ifcopenshell.entity_instance) -> None:
        schedules = root.findall(f'{SVG}g[@data-type="schedule"]')
        references = root.findall(f'{SVG}g[@data-type="reference"]')
        documents = schedules + references
        for view in documents:
            try:
                reference = tool.Ifc.get().by_id(int(view.attrib["data-id"]))
                document = tool.Ifc.get().by_id(int(view.attrib["data-document"]))
            except:
                # Perhaps the SVG has outdated content or is edited externally which we cannot control.
                continue

            images = view.findall(f"{SVG}image")

            table = None
            view_title = None

            for image in images:
                if image.attrib["data-type"] == "content":
                    table = image
                elif image.attrib["data-type"] == "view-title":
                    view_title = image

            if table is not None:
                svg = self.parse_embedded_svg(table, {})
                svg = self.ensure_unique_ids(svg, int(view.attrib["data-id"]))
                view.append(svg)

            if view_title is not None:
                path = self.get_href(table)
                data = self.get_document_view_title_data(
                    reference,
                    sheet,
                    document,
                    os.path.join(self.layout_dir, path),
                    is_reference=view.attrib.get("data-type") == "reference",
                )
                view.append(self.parse_embedded_svg(view_title, data))

            for image in images:
                view.remove(image)

    def get_document_view_title_data(
        self,
        reference: ifcopenshell.entity_instance,
        sheet: ifcopenshell.entity_instance,
        document: ifcopenshell.entity_instance,
        content_path: str,
        is_reference: bool,
    ) -> dict:
        """Template data for a schedule's or reference's view-title.

        Shared by `build_documents` and `get_template_values`.
        """
        data = reference.get_info()
        data.update({"Sheet" + k: v for k, v in sheet.get_info().items()})
        if not data["Name"]:
            data["Name"] = document.Name or "Unnamed"
        if is_reference:
            human_scale = self.get_scale_from_svg(content_path)
            if human_scale:
                data["Scale"] = human_scale
        return data

    def get_template_values(self) -> dict:
        """The data every sheet's templates are filled with, without building.

        For tools that display sheets from their layouts - SketchSpace renders
        them live - so view-titles and titleblocks read as a build would. The
        data comes from the same methods `build` uses, and from the model in
        memory, unsaved edits included.

        Sheets are keyed by their layout's path and placements by the path of the
        file they place: a layout's ``data-id`` is a STEP id, which does not
        survive a re-serialised model. Values are text, as pystache renders them,
        except the booleans and lists of rows that templates test and iterate.

        ::

            {
                "ifc": "<absolute path, or empty if unsaved>",
                "sheets": [
                    {
                        "identification": "A01",
                        "layout": "<absolute path>",
                        "values": {...titleblock data...},
                        "placements": {"<absolute path>": {...view-title data...}},
                        "drawings": {"<drawing GlobalId>": {...the same, for drawings...}},
                    }
                ],
                "north": {"grid": "rotate(...)", "true": "rotate(...)"},
            }
        """
        ifc_file = tool.Ifc.get()
        ifc_path = tool.Ifc.get_path()
        result = {
            "ifc": os.path.abspath(ifc_path) if ifc_path else "",
            "sheets": [],
            "north": {"grid": "rotate(0)", "true": "rotate(0)"},
        }
        if not ifc_file:
            return result

        key = self._path_key
        drawings = self._drawings_by_uri()
        documents = self._documents_by_uri()

        for sheet in ifc_file.by_type("IfcDocumentInformation"):
            if sheet.Scope != "SHEET":
                continue
            layout = tool.Drawing.get_document_uri(sheet, "LAYOUT")
            if not layout:
                continue

            placements = {}
            by_drawing = {}
            for reference in tool.Drawing.get_document_references(sheet):
                kind = tool.Drawing.get_reference_description(reference)
                if kind in ("LAYOUT", "TITLEBLOCK", "SHEET"):
                    continue
                uri = tool.Drawing.get_document_uri(reference)
                if not uri:
                    continue
                if kind == "DRAWING":
                    if (drawing := drawings.get(key(uri))) is None:
                        continue
                    data = self.get_drawing_view_title_data(reference, sheet, drawing, uri)
                    by_drawing[drawing.GlobalId] = as_template_data(data)
                else:
                    if (document := documents.get(key(uri))) is None:
                        continue
                    data = self.get_document_view_title_data(
                        reference, sheet, document, uri, is_reference=kind == "REFERENCE"
                    )
                placements[os.path.abspath(uri)] = as_template_data(data)

            result["sheets"].append(
                {
                    "identification": str(tool.Drawing.get_sheet_identification(sheet)),
                    "layout": os.path.abspath(layout),
                    "values": as_template_data(self.get_titleblock_data(sheet)),
                    "placements": placements,
                    "drawings": by_drawing,
                }
            )

        grid_north = ifcopenshell.util.geolocation.get_grid_north(ifc_file) * -1
        true_north = ifcopenshell.util.geolocation.get_true_north(ifc_file) * -1
        result["north"] = {"grid": f"rotate({grid_north})", "true": f"rotate({true_north})"}
        return result

    def find_sheet(self, layout: str) -> Union[ifcopenshell.entity_instance, None]:
        """The sheet whose layout is at `layout`, or None.

        By path, as `get_template_values` keys its sheets: a layout's STEP id
        does not survive a re-serialised model, and the same file can be spelled
        several ways on Windows.
        """
        ifc_file = tool.Ifc.get()
        if not ifc_file:
            return None
        target = self._path_key(layout)
        for sheet in ifc_file.by_type("IfcDocumentInformation"):
            if sheet.Scope != "SHEET":
                continue
            uri = tool.Drawing.get_document_uri(sheet, "LAYOUT")
            if uri and self._path_key(uri) == target:
                return sheet
        return None

    def get_editable_fields(self, layout: str, target: dict, fields: list[str]) -> dict:
        """Which of `fields` can be written back on this view, and what they hold.

        `fields` are the placeholders a template actually uses, so a tool can
        offer what is on the sheet rather than every attribute of the entity
        behind it. Whether a field is writable is answered here, beside the
        operations that would apply it: a tool deciding for itself would drift
        from what `set_template_values` accepts.

        ::

            {"fields": [{"name": "Name", "value": "SITE PLAN", "editable": True},
                        {"name": "Scale", "value": "1:100", "editable": False,
                         "reason": "..."}]}
        """
        sheet = self._require_sheet(layout)
        kind, reference, entity = self._find_target(sheet, target)
        data = self._view_data(sheet, kind, reference, entity)
        writable = self.WRITABLE_FIELDS[kind]

        answer = []
        for name in fields:
            # Unset reads as empty here, not as the "None" a build prints: this
            # value goes into a box someone types in, and saving it back would
            # otherwise set the attribute to the word.
            value = data.get(name)
            field = {"name": name, "value": "" if value is None else as_template_data(value)}
            if name in writable:
                field["editable"] = True
            else:
                field["editable"] = False
                field["reason"] = self._read_only_reason(kind, name)
            answer.append(field)
        return {"fields": answer, "kind": kind}

    def set_template_values(self, layout: str, target: dict, values: dict) -> dict:
        """Apply template values to the model in memory, through Bonsai.

        Every field goes through the operation Bonsai itself uses, because
        several of them are not just an attribute: renaming a sheet moves its
        layout and its built sheet, renaming a drawing moves its SVG and relinks
        every layout that places it. Writing the attribute alone would leave the
        model naming files that are not there.

        Raises ValueError with a reason a person can read - the caller is a
        remote tool, and the message is what it shows.
        """
        import bonsai.core.drawing as core

        sheet = self._require_sheet(layout)
        kind, reference, entity = self._find_target(sheet, target)
        writable = self.WRITABLE_FIELDS[kind]

        for name in values:
            if name not in writable:
                raise ValueError(f"{name} cannot be edited: {self._read_only_reason(kind, name)}")
        values = {name: ("" if value is None else str(value)) for name, value in values.items()}
        if not values:
            return {"changed": []}

        ifc_file = tool.Ifc.get()
        if kind == "sheet":
            # Identification and Name name the layout and sheet files together,
            # so they are renamed together, keeping whichever is not being set.
            if "Identification" in values or "Name" in values:
                core.rename_sheet(
                    tool.Ifc,
                    tool.Drawing,
                    sheet=sheet,
                    identification=values.get("Identification", str(tool.Drawing.get_sheet_identification(sheet))),
                    name=values.get("Name", sheet.Name or ""),
                )
            attributes = {k: v for k, v in values.items() if k not in ("Identification", "Name")}
            if attributes:
                tool.Ifc.run("document.edit_information", information=sheet, attributes=attributes)
            tool.Drawing.import_sheets()
        else:
            if "Identification" in values:
                core.rename_reference(tool.Ifc, tool.Drawing, reference=reference, identification=values["Identification"])
            if "Name" in values:
                # A view-title shows the reference's own name when it has one and
                # falls back to the drawing's, so the edit goes wherever the
                # displayed value came from (`get_drawing_view_title_data`).
                if reference.Name:
                    tool.Ifc.run("document.edit_reference", reference=reference, attributes={"Name": values["Name"]})
                elif kind == "drawing":
                    core.update_drawing_name(tool.Ifc, tool.Drawing, drawing=entity, name=values["Name"])
                else:
                    tool.Ifc.run("document.edit_information", information=entity, attributes={"Name": values["Name"]})
            attributes = {k: v for k, v in values.items() if k not in ("Identification", "Name")}
            if attributes:
                tool.Ifc.run("document.edit_reference", reference=reference, attributes=attributes)
            tool.Drawing.import_sheets()
            if kind == "drawing":
                tool.Drawing.import_drawings()

        # Where the sheet is now: renaming one moves its layout, so the path the
        # caller asked about no longer exists. Saying so is what lets a tool ask
        # again straight away rather than wait to notice the file move.
        moved = tool.Drawing.get_document_uri(sheet, "LAYOUT")
        return {"changed": sorted(values), "layout": os.path.abspath(moved) if moved else ""}

    #: What each kind of view can write back. An allow-list, because the rest of
    #: a document's attributes are either maintained by Bonsai alongside files on
    #: disk, or are entities rather than text.
    WRITABLE_FIELDS = {
        "sheet": (
            "Identification",
            "Name",
            "Description",
            "Purpose",
            "IntendedUse",
            "Revision",
            "Status",
            "Confidentiality",
            "ElectronicFormat",
            "CreationTime",
            "LastRevisionTime",
            "ValidFrom",
            "ValidUntil",
        ),
        "drawing": ("Identification", "Name", "Description"),
        "document": ("Identification", "Name", "Description"),
    }

    #: Why a field a template uses cannot be written, where there is more to say
    #: than that Bonsai has no operation for it.
    READ_ONLY_REASONS = {
        "Scale": "The scale comes from the drawing's camera.",
        "Scope": "Scope is what makes this document a sheet.",
        "Location": "This is a file path, which Bonsai maintains as things are renamed.",
        "revisions": "Revisions are read from the project repository's tags, not the model.",
        "has_revisions": "Revisions are read from the project repository's tags, not the model.",
        "DocumentOwner": "An owner is a person or organisation in the model, not text.",
        "Editors": "Editors are people or organisations in the model, not text.",
        "ReferencedDocument": "This points at another document in the model, not text.",
        "id": "A STEP id belongs to the file, not the sheet.",
        "type": "This is the IFC class of the entity behind the view.",
        "GlobalId": "A GlobalId identifies the drawing; changing it would unlink it.",
        "OwnerHistory": "Ownership is recorded by IFC, not typed in.",
    }

    def _read_only_reason(self, kind: str, name: str) -> str:
        if kind != "sheet" and name.startswith("Sheet"):
            return "This is the sheet's own field - edit it on the titleblock."
        return self.READ_ONLY_REASONS.get(name, "Bonsai has no operation for this field.")

    @staticmethod
    def _path_key(path: str) -> str:
        return os.path.normcase(os.path.abspath(path))

    def _require_sheet(self, layout: str) -> ifcopenshell.entity_instance:
        sheet = self.find_sheet(layout)
        if sheet is None:
            raise ValueError(f"no sheet in this model uses the layout {os.path.basename(layout)}")
        return sheet

    def _drawings_by_uri(self) -> dict:
        """Every drawing in the model, by the path of the SVG it is drawn into."""
        drawings = {}
        for drawing in tool.Ifc.get().by_type("IfcAnnotation"):
            if drawing.ObjectType != "DRAWING":
                continue
            document = tool.Drawing.get_drawing_document(drawing)
            if document and (uri := tool.Drawing.get_document_uri(document)):
                drawings[self._path_key(uri)] = drawing
        return drawings

    def _documents_by_uri(self) -> dict:
        """Every schedule and reference, by the path of the file it is kept in."""
        documents = {}
        for information in tool.Ifc.get().by_type("IfcDocumentInformation"):
            if information.Scope not in ("SCHEDULE", "REFERENCE"):
                continue
            for reference in tool.Drawing.get_document_references(information):
                if uri := tool.Drawing.get_document_uri(reference):
                    documents.setdefault(self._path_key(uri), information)
        return documents

    def _find_target(self, sheet: ifcopenshell.entity_instance, target: dict) -> tuple:
        """The view a request names, as (kind, reference, entity).

        A view is named by the GlobalId of its drawing or by the path of the file
        it places - the same two handles `get_template_values` answers with, and
        the only two that survive a re-serialised model.
        """
        kind = target.get("kind", "sheet")
        if kind in ("sheet", "titleblock"):
            return "sheet", None, sheet

        wanted_guid = target.get("globalId")
        wanted_path = self._path_key(target["path"]) if target.get("path") else None
        if not wanted_guid and not wanted_path:
            raise ValueError("a view has to be named by its drawing's GlobalId or by its file")

        drawings = self._drawings_by_uri()
        documents = self._documents_by_uri()
        for reference in tool.Drawing.get_document_references(sheet):
            description = tool.Drawing.get_reference_description(reference)
            if description in ("LAYOUT", "TITLEBLOCK", "SHEET"):
                continue
            uri = tool.Drawing.get_document_uri(reference)
            if not uri:
                continue
            uri_key = self._path_key(uri)
            drawing = drawings.get(uri_key)
            if wanted_guid and drawing is not None and drawing.GlobalId == wanted_guid:
                return "drawing", reference, drawing
            if wanted_path and uri_key == wanted_path:
                if drawing is not None:
                    return "drawing", reference, drawing
                document = documents.get(uri_key)
                if document is not None:
                    return "document", reference, document
        raise ValueError(f"{sheet.Name or 'this sheet'} has no such view - it may have been moved or removed")

    def _view_data(
        self,
        sheet: ifcopenshell.entity_instance,
        kind: str,
        reference: Union[ifcopenshell.entity_instance, None],
        entity: ifcopenshell.entity_instance,
    ) -> dict:
        """What this view's template is filled with - the same data a build uses."""
        if kind == "sheet":
            return self.get_titleblock_data(sheet)
        uri = tool.Drawing.get_document_uri(reference) or ""
        if kind == "drawing":
            return self.get_drawing_view_title_data(reference, sheet, entity, uri)
        return self.get_document_view_title_data(
            reference,
            sheet,
            entity,
            uri,
            is_reference=entity.Scope == "REFERENCE",
        )

    def get_scale_from_svg(self, svg_path: str) -> str:
        try:
            tree = ET.parse(svg_path)
            root = tree.getroot()
            for g in root.iter(f"{SVG}g"):
                for cls in g.attrib.get("class", "").split():
                    if cls.startswith("scale-"):
                        denominator = cls[6:]
                        if denominator.isdigit():
                            return tool.Drawing.get_human_scale_from_scale_denominator(denominator)
        except Exception:
            pass
        return ""

    def get_href(self, element: ET.Element) -> str:
        return urllib.parse.unquote(element.attrib[f"{XLINK}href"]).replace("\\", "/")

    def parse_embedded_svg(self, image: ET.Element, data: dict) -> ET.Element:
        group = ET.Element("g")
        x, y = self.convert_to_mm(image.attrib["x"]), self.convert_to_mm(image.attrib["y"])
        group.attrib["transform"] = f"translate({x},{y})"

        # Convert viewBox into a clip path
        clip_id = str(uuid.uuid4())
        group.attrib["clip-path"] = f"url(#{clip_id})"
        clip_path = ET.Element("clipPath")
        clip_path.attrib["id"] = clip_id
        rect = ET.Element("rect")
        rect.attrib["x"] = "0"
        rect.attrib["y"] = "0"
        rect.attrib["width"] = str(self.convert_to_mm(image.attrib["width"]))
        rect.attrib["height"] = str(self.convert_to_mm(image.attrib["height"]))
        clip_path.append(rect)
        self.defs.append(clip_path)

        svg_path = self.get_href(image)
        with open(os.path.join(self.layout_dir, svg_path), "r") as template:
            embedded = ET.fromstring(pystache.render(template.read(), data))
            # viewBox should not be nested
            embedded.attrib["viewBox"] = ""
            # TODO: This should not be in this function
            self.scale = embedded.attrib.get("data-scale")
            images = embedded.findall(f"{SVG}image")
            for image in images:
                old_href = Path(image.attrib[f"{XLINK}href"])
                if not os.path.isabs(old_href):
                    template_dir = Path(os.path.join(self.layout_dir, svg_path)).resolve().parent
                    old_href = Path(os.path.join(template_dir, old_href))
                old_href = old_href.absolute().resolve().as_posix()
                new_href = Path(os.path.join(self.sheets_dir, Path(old_href).name)).absolute().resolve().as_posix()
                shutil.copy(old_href, new_href)
                image.attrib[f"{XLINK}href"] = Path(old_href).name
        for child in embedded:
            if "namedview" in child.tag:
                continue
            group.append(child)
        return group

    def change_titleblock(self, sheet: ifcopenshell.entity_instance, titleblock_name: str) -> None:
        ootb_titleblock_path = tool.Blender.get_data_dir_path(
            Path("templates") / "titleblocks" / (titleblock_name + ".svg")
        )
        titleblock_path = tool.Ifc.resolve_uri(tool.Drawing.get_default_titleblock_path(titleblock_name))
        sheet_path = tool.Drawing.get_document_uri(sheet, "LAYOUT")
        assert sheet_path is not None
        sheet_dir = os.path.dirname(sheet_path)

        os.makedirs(sheet_dir, exist_ok=True)
        os.makedirs(os.path.dirname(titleblock_path), exist_ok=True)
        if not os.path.exists(titleblock_path):
            shutil.copy(ootb_titleblock_path, titleblock_path)

        ET.register_namespace("", "http://www.w3.org/2000/svg")
        ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")

        view_root = ET.parse(titleblock_path).getroot()
        view_width = self.convert_to_mm(view_root.attrib["width"])
        view_height = self.convert_to_mm(view_root.attrib["height"])

        sheet_tree = ET.parse(sheet_path)
        root = sheet_tree.getroot()

        titleblock = sheet_tree.findall(f'{SVG}g[@data-type="titleblock"]')[0]
        image = titleblock.findall(f"{SVG}image[@{XLINK}href]")[0]
        image.attrib[f"{XLINK}href"] = os.path.relpath(titleblock_path, sheet_dir)
        image.attrib["width"] = str(view_width)
        image.attrib["height"] = str(view_height)

        root.attrib["width"] = "{}mm".format(view_width)
        root.attrib["height"] = "{}mm".format(view_height)
        root.attrib["viewBox"] = "0 0 {} {}".format(view_width, view_height)

        sheet_tree.write(sheet_path)

    def convert_to_mm(self, value: str) -> float:
        # CSS is what defines these possibilities
        # https://www.w3.org/TR/SVG/refs.html#ref-css-values-3
        # https://www.w3.org/TR/css-values-3/#absolute-lengths
        # The relative units are not implemented. Go fish.
        if "cm" in value:
            return float(value[0:-2]) * 10
        elif "mm" in value:
            return float(value[0:-2])
        elif "Q" in value:
            return float(value[0:-1]) * (1 / 40) * 10
        elif "in" in value:
            return float(value[0:-2]) * 2.54 * 10
        elif "pc" in value:
            return float(value[0:-2]) * (1 / 6) * 2.54 * 10
        elif "pt" in value:
            return float(value[0:-2]) * (1 / 72) * 2.54 * 10
        elif "px" in value:
            return float(value[0:-2]) * (1 / 96) * 2.54 * 10
        return float(value)

    def mm_to_px(self, value: float) -> float:
        return (value / 25.4) * 96
