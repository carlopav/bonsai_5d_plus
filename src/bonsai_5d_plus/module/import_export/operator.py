# Bonsai - OpenBIM 5D Blender Add-on based on Bonsai
# Copyright (C) 2026 Carlo Pavan <carlopav@gmail.com>
#
# This file is part of Bonsai5D+.  GNU GPL v3 or later.

import os

import bpy
from bpy_extras.io_utils import ImportHelper, ExportHelper

from ...core.parsers import ParserXpwe, PriceListParser
from ...core.exporters import export_cost_schedule_to_xpwe
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
    flatten_sor: bpy.props.BoolProperty(
        name="Flatten SoR",
        description="Group all EPU items under a single 'EPU' summary item instead of preserving the chapter hierarchy",
        default=True,
    )
    import_measurement_rows: bpy.props.BoolProperty(
        name="Import Measurement Rows",
        description="Import each measurement row (RGItem) as a separate IFC quantity, keeping its description and the NR x L x W x H breakdown in the IFC Formula attribute, instead of a single VCItem total",
        default=True,
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
            parser, f"{base_name} - EPU", self.report,
            flatten=self.flatten_sor,
        )
        if not success:
            return {"CANCELLED"}

        parser.parse_computo(xml_content)
        if parser.xml_computo_list:
            build_cme_schedule(
                parser, f"{base_name} - CME", ep_ifc_map, self.report,
                import_measurement_rows=self.import_measurement_rows,
            )

        epu_count = sum(1 for r in parser.xml_rate_list if not r["is_parent"])
        cme_count = sum(1 for r in parser.xml_computo_list if not r["is_parent"])
        msg = f"Imported EPU ({epu_count} voci)"
        if cme_count:
            msg += f" + CME ({cme_count} voci)"
        self.report({'INFO'}, msg)
        return {"FINISHED"}


class ExportXpweCostSchedule(bpy.types.Operator, ExportHelper):
    """Export the active IFC cost schedule (CME/BoQ) to an XPWE file.

    The active schedule drives the computo (PweVociComputo); its items' prices
    form the price list (PweElencoPrezzi), taken from the linked Schedule-of-Rates
    when present, otherwise synthesised from the items themselves.
    """

    bl_idname = "bonsai5d.export_xpwe_cost_schedule"
    bl_label = "Export XPWE"
    bl_options = {"REGISTER"}

    filename_ext = ".xpwe"
    filter_glob: bpy.props.StringProperty(
        default="*.xpwe;*.xml",
        options={"HIDDEN"},
        maxlen=255,
    )

    @classmethod
    def poll(cls, context):
        try:
            return context.scene.BIMCostProperties.active_cost_schedule_id != 0
        except Exception:
            return False

    def invoke(self, context, event):
        # Seed the filename from the active schedule's name.
        try:
            from bonsai import tool
            file = tool.Ifc.get()
            sid = context.scene.BIMCostProperties.active_cost_schedule_id
            schedule = file.by_id(sid)
            self.filepath = (schedule.Name or "cost_schedule") + ".xpwe"
        except Exception:
            self.filepath = "cost_schedule.xpwe"
        return ExportHelper.invoke(self, context, event)

    def execute(self, context):
        try:
            from bonsai import tool
        except ImportError as e:
            self.report({'ERROR'}, f"Bonsai not available: {e}")
            return {"CANCELLED"}

        file = tool.Ifc.get()
        if file is None:
            self.report({'ERROR'}, "No IFC file loaded")
            return {"CANCELLED"}

        sid = context.scene.BIMCostProperties.active_cost_schedule_id
        schedule = file.by_id(sid)
        if schedule is None:
            self.report({'ERROR'}, "No active cost schedule")
            return {"CANCELLED"}

        try:
            xml_text = export_cost_schedule_to_xpwe(
                file, schedule, filename=os.path.basename(self.filepath)
            )
        except Exception as e:
            import traceback
            self.report({'ERROR'}, f"XPWE export failed: {e}\n{traceback.format_exc()}")
            return {"CANCELLED"}

        with open(self.filepath, "w", encoding="utf-8") as f:
            f.write(xml_text)

        self.report({'INFO'}, f"Exported XPWE: {os.path.basename(self.filepath)}")
        return {"FINISHED"}


classes = [ImportXpweCostSchedule, ExportXpweCostSchedule]
