# Bonsai - OpenBIM 5D Blender Add-on based on Bonsai
# Copyright (C) 2026 Carlo Pavan <carlopav@gmail.com>
#
# This file is part of Bonsai5D+.  GNU GPL v3 or later.

import os

import bpy
from bpy_extras.io_utils import ImportHelper

from ...core.parsers import ParserXpwe, PriceListParser
from ...tool.cost import build_schedule_from_xpwe, build_cme_schedule


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

        success, ep_ifc_map = build_schedule_from_xpwe(
            parser, f"{base_name} - EPU", self.report
        )
        if not success:
            return {"CANCELLED"}

        parser.parse_computo(xml_content)
        if parser.xml_computo_list:
            build_cme_schedule(parser, f"{base_name} - CME", ep_ifc_map, self.report)

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


classes = [ImportXpweCostSchedule, ExportXpweCostSchedule]
