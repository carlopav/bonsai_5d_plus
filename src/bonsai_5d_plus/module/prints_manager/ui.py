# Bonsai - OpenBIM 5D Blender Add-on based on Bonsai
# Copyright (C) 2026 Carlo Pavan <carlopav@gmail.com>
#
# This file is part of Bonsai5D+.  GNU GPL v3 or later.

import bpy
from .operator import _get_ifc


class PrintsManagerPanel(bpy.types.Panel):
    bl_label = "Prints Manager"
    bl_idname = "SCENE_PT_prints_manager"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Bonsai5D+"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        if _get_ifc() is None:
            layout.label(text="No IFC file loaded.", icon="ERROR")
            return

        layout.operator("bim.export_schedule_to_pdf",      icon="FILE_TEXT")
        layout.operator("bim.export_schedule_to_ods",      icon="FILE_TEXT")
        layout.separator(factor=0.5)
        layout.operator("bim.export_labor_cost_breakdown_to_pdf", icon="COMMUNITY")
        layout.separator(factor=0.5)
        row = layout.row(align=True)
        row.operator("bim.export_rate_analysis_to_pdf",     icon="SCRIPT")
        row.operator("bim.export_all_rate_analysis_to_pdf", text="", icon="DOCUMENTS")


classes = [PrintsManagerPanel]
