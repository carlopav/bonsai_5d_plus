# Bonsai - OpenBIM 5D Blender Add-on based on Bonsai
# Copyright (C) 2026 Carlo Pavan <carlopav@gmail.com>
#
# This file is part of Bonsai5D+.  GNU GPL v3 or later.

import bpy
from .operator import ImportXpweCostSchedule, ExportXpweCostSchedule


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


classes = [ImportExportPanel]
