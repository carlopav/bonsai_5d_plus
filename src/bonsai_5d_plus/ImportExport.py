# Bonsai - OpenBIM 5D Blender Add-on based on Bonsai
# Copyright (C) 2026 Carlo Pavan <carlopav@gmail.com>
#
# This file is part of Bonsai5D+.
#
# Bonsai5D+ is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Bonsai5D+ is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Bonsai5D+.  If not, see <http://www.gnu.org/licenses/>.
#
# This file was modified with the assistance of an AI coding tool.

import os

import bpy
from bpy.types import Operator, Panel
from bpy_extras.io_utils import ImportHelper

from .RateListImporter import ParserXpwe, PriceListParser


# ---------------------------------------------------------------------------
# XPWE import helpers
# ---------------------------------------------------------------------------

def _ifc_str(s):
    """Strip whitespace; return None if the result is empty (IfcLabel must be non-empty)."""
    s = (s or "").strip()
    return s or None


def _build_schedule_from_xpwe(parser, schedule_name, report=None):
    """Create a new IfcCostSchedule (EPU) from parser.xml_rate_list.

    Returns (True, ep_ifc_map) on success where ep_ifc_map maps
    {xml_ep_id: IfcCostItem} for use by the CME builder.
    Returns (False, {}) on failure.
    """
    try:
        from bonsai import tool
        import bonsai.bim.module.cost.data
    except ImportError as e:
        if report:
            report({'ERROR'}, f"Bonsai not available: {e}")
        return False, {}

    file = tool.Ifc.get()
    if file is None:
        if report:
            report({'ERROR'}, "No IFC file loaded")
        return False, {}

    try:
        schedule = tool.Ifc.run(
            "cost.add_cost_schedule",
            name=schedule_name,
            predefined_type="SCHEDULEOFRATES",
        )

        index_to_ifc = {}

        for rate in parser.xml_rate_list:
            parent_indices = [int(p) for p in rate["parents"].split(",") if p.strip()]

            if not parent_indices:
                cost_item = tool.Ifc.run("cost.add_cost_item", cost_schedule=schedule)
            else:
                parent_ifc = index_to_ifc[parent_indices[-1]]
                cost_item = tool.Ifc.run("cost.add_cost_item", cost_item=parent_ifc)

            tool.Ifc.run("cost.edit_cost_item", cost_item=cost_item, attributes={
                "Identification": _ifc_str(rate["id"]),
                "Name": _ifc_str(rate["name"]),
                "Description": _ifc_str(rate["desc"]),
            })

            if not rate["is_parent"]:
                value = float(rate["value"])
                labor = float(rate["labor"])
                equipment = float(rate["equipment"])
                materials = float(rate["materials"])
                safety = float(rate["safety"])

                components = [
                    ("Labor", labor),
                    ("Equipment", equipment),
                    ("Materials", materials),
                    ("Safety", safety),
                ]
                has_components = any(v != 0.0 for _, v in components)

                if not has_components:
                    if value != 0.0:
                        cv = tool.Ifc.run("cost.add_cost_value", parent=cost_item)
                        tool.Ifc.run("cost.edit_cost_value", cost_value=cv,
                                     attributes={"AppliedValue": round(value, 2)})
                else:
                    remaining = round(value - sum(v for _, v in components), 2)
                    if remaining != 0.0:
                        cv = tool.Ifc.run("cost.add_cost_value", parent=cost_item)
                        tool.Ifc.run("cost.edit_cost_value", cost_value=cv,
                                     attributes={"AppliedValue": remaining})
                    for category, amount in components:
                        if amount != 0.0:
                            cv = tool.Ifc.run("cost.add_cost_value", parent=cost_item)
                            tool.Ifc.run("cost.edit_cost_value", cost_value=cv, attributes={
                                "Category": category,
                                "AppliedValue": round(amount, 2),
                            })

            index_to_ifc[rate["index"]] = cost_item

        # build xml_ep_id → IfcCostItem for the CME linker
        ep_ifc_map = {
            xml_id: index_to_ifc[ep["index"]]
            for xml_id, ep in parser._ep_by_xml_id.items()
            if ep["index"] in index_to_ifc
        }

        bonsai.bim.module.cost.data.refresh()
        import bpy as _bpy
        if _bpy.context.scene.BIMCostProperties.active_cost_schedule_id != 0:
            tool.Cost.load_cost_schedule_tree()

    except Exception as e:
        if report:
            import traceback
            report({'ERROR'}, f"IFC import failed: {e}\n{traceback.format_exc()}")
        return False, {}

    return True, ep_ifc_map


def _build_cme_schedule(parser, schedule_name, ep_ifc_map, report=None):
    """Create an IfcCostSchedule (CME/BoQ) from parser.xml_computo_list.

    ep_ifc_map: {xml_ep_id: IfcCostItem} returned by _build_schedule_from_xpwe.
    Each leaf item's rate is linked to the EPU IfcCostItem via assign_cost_value
    so that price changes in the EPU propagate automatically.
    """
    try:
        from bonsai import tool
        from bonsai.core import cost as cost_core
        import bonsai.bim.module.cost.data
    except ImportError as e:
        if report:
            report({'ERROR'}, f"Bonsai not available: {e}")
        return False

    file = tool.Ifc.get()
    if file is None:
        if report:
            report({'ERROR'}, "No IFC file loaded")
        return False

    try:
        schedule = tool.Ifc.run(
            "cost.add_cost_schedule",
            name=schedule_name,
            predefined_type="PRICEDBILLOFQUANTITIES",
        )

        index_to_ifc = {}

        for rate in parser.xml_computo_list:
            parent_indices = [int(p) for p in rate["parents"].split(",") if p.strip()]

            if not parent_indices:
                cost_item = tool.Ifc.run("cost.add_cost_item", cost_schedule=schedule)
            else:
                cost_item = tool.Ifc.run("cost.add_cost_item",
                                         cost_item=index_to_ifc[parent_indices[-1]])

            tool.Ifc.run("cost.edit_cost_item", cost_item=cost_item, attributes={
                "Identification": _ifc_str(rate["id"]),
                "Name": _ifc_str(rate["name"]),
                "Description": _ifc_str(rate["desc"]),
            })

            if not rate["is_parent"]:
                ep_xml_id = rate.get("ep_xml_id", "")
                cost_rate = ep_ifc_map.get(ep_xml_id)
                quantity = float(rate.get("quantity", 0.0))

                if cost_rate is not None:
                    # link to EPU item: price changes in the SoR propagate automatically
                    cost_core.assign_cost_value(
                        tool.Ifc, tool.Cost,
                        cost_item=cost_item,
                        cost_rate=cost_rate,
                    )
                elif float(rate["value"]) != 0.0:
                    # fallback: copy value directly (no EPU item found)
                    cv = tool.Ifc.run("cost.add_cost_value", parent=cost_item)
                    tool.Ifc.run("cost.edit_cost_value", cost_value=cv,
                                 attributes={"AppliedValue": round(float(rate["value"]), 2)})

                if quantity != 0.0:
                    cv = tool.Ifc.run("cost.add_cost_value", parent=cost_item)
                    tool.Ifc.run("cost.edit_cost_value", cost_value=cv, attributes={
                        "Category": "Quantity",
                        "AppliedValue": round(quantity, 4),
                    })

            index_to_ifc[rate["index"]] = cost_item

        bonsai.bim.module.cost.data.refresh()
        import bpy as _bpy
        if _bpy.context.scene.BIMCostProperties.active_cost_schedule_id != 0:
            tool.Cost.load_cost_schedule_tree()

    except Exception as e:
        if report:
            import traceback
            report({'ERROR'}, f"CME import failed: {e}\n{traceback.format_exc()}")
        return False

    return True


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------

class ImportXpweCostSchedule(bpy.types.Operator, ImportHelper):
    """Import an XPWE file as a new IFC cost schedule (Elenco Prezzi → IfcCostSchedule)."""

    bl_idname = "bonsai5d.import_xpwe_cost_schedule"
    bl_label = "Import XPWE"
    bl_options = {"REGISTER", "UNDO"}

    filename_ext = ".xpwe"
    filter_glob: bpy.props.StringProperty(
        default="*.xpwe;*.xml",
        options={"HIDDEN"},
        maxlen=255,
    )

    @classmethod
    def poll(cls, context):
        try:
            from bonsai import tool
            return tool.Ifc.get() is not None
        except Exception:
            return False

    def execute(self, context):
        xml_content = PriceListParser.get_xml_content(self.filepath)
        parser = ParserXpwe()
        parser.parse_items(xml_content)

        if not parser.xml_rate_list:
            self.report({'ERROR'}, "No items found in XPWE file")
            return {"CANCELLED"}

        base_name = os.path.splitext(os.path.basename(self.filepath))[0]

        success, ep_ifc_map = _build_schedule_from_xpwe(
            parser, f"{base_name} - EPU", self.report
        )
        if not success:
            return {"CANCELLED"}

        parser.parse_computo(xml_content)
        if parser.xml_computo_list:
            _build_cme_schedule(parser, f"{base_name} - CME", ep_ifc_map, self.report)

        epu_count = sum(1 for r in parser.xml_rate_list if not r["is_parent"])
        cme_count = sum(1 for r in parser.xml_computo_list if not r["is_parent"])
        msg = f"Imported EPU ({epu_count} voci)"
        if cme_count:
            msg += f" + CME ({cme_count} voci)"
        self.report({'INFO'}, msg)
        return {"FINISHED"}


class ExportXpweCostSchedule(bpy.types.Operator):
    """Export the active IFC cost schedule to XPWE format."""

    bl_idname = "bonsai5d.export_xpwe_cost_schedule"
    bl_label = "Export XPWE"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        try:
            return context.scene.BIMCostProperties.active_cost_schedule_id != 0
        except Exception:
            return False

    def execute(self, context):
        self.report({'WARNING'}, "XPWE export not yet implemented")
        return {"CANCELLED"}


# ---------------------------------------------------------------------------
# Panel
# ---------------------------------------------------------------------------

class ImportExportPanel(bpy.types.Panel):
    bl_label = "Import / Export"
    bl_idname = "SCENE_PT_import_export"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Bonsai5D+"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout

        layout.label(text="XPWE (Primus / Computi)")
        col = layout.column(align=True)
        col.operator(ImportXpweCostSchedule.bl_idname, icon="IMPORT")
        col.operator(ExportXpweCostSchedule.bl_idname, icon="EXPORT")


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

classes = [
    ImportXpweCostSchedule,
    ExportXpweCostSchedule,
    ImportExportPanel,
]

class_register, class_unregister = bpy.utils.register_classes_factory(classes)


def register():
    class_register()


def unregister():
    class_unregister()
