# Bonsai - OpenBIM 5D Blender Add-on based on Bonsai
# Copyright (C) 2026 Carlo Pavan <carlopav@gmail.com>
#
# This file is part of Bonsai5D+.  GNU GPL v3 or later.

import bpy
from .operator import _get_ifc


class SvgToPdfPanel(bpy.types.Panel):
    bl_label = "Prints Manager"
    bl_idname = "SCENE_PT_svg_to_pdf"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Bonsai5D+"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        if _get_ifc() is None:
            layout.label(text="No IFC file loaded.", icon="ERROR")
            return

        layout.operator("bim.export_sheets_to_pdf",        icon="FILE_BLANK")
        layout.separator(factor=0.5)
        layout.operator("bim.export_schedule_to_pdf",      icon="FILE_TEXT")
        layout.separator(factor=0.5)
        row = layout.row(align=True)
        row.operator("bim.export_rate_analysis_to_pdf",     icon="SCRIPT")
        row.operator("bim.export_all_rate_analysis_to_pdf", text="", icon="DOCUMENTS")


class ComparisonPanel(bpy.types.Panel):
    bl_label = "Confronto Prezzi"
    bl_idname = "SCENE_PT_comparison"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Bonsai5D+"
    bl_parent_id = "SCENE_PT_svg_to_pdf"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        wm = context.window_manager

        row = layout.row()
        row.operator("comparison.refresh_schedules", text="Refresh", icon="FILE_REFRESH")

        schedules = wm.comparison_schedules
        if not schedules:
            layout.label(text="Click Refresh to load schedules.", icon="INFO")
        else:
            for item in schedules:
                row = layout.row(align=True)

                # BASE toggle (radio-button style)
                base_op = row.operator(
                    "comparison.set_base",
                    text="",
                    icon="RADIOBUT_ON" if item.is_base else "RADIOBUT_OFF",
                    emboss=False,
                )
                base_op.schedule_id = item.schedule_id

                # Enabled checkbox
                row.prop(item, "enabled", text="")

                # Name + type label
                ptype = item.predefined_type.replace("NOTDEFINED", "").replace("USERDEFINED", "")
                label = item.name
                if ptype:
                    label += f"  [{ptype[:3]}]"
                row.label(text=label)

        layout.separator(factor=0.5)
        layout.operator("comparison.export_price_comparison", icon="NLA")


classes = [SvgToPdfPanel, ComparisonPanel]
