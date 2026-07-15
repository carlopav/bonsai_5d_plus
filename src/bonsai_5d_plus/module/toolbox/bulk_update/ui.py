# Bonsai - OpenBIM 5D Blender Add-on based on Bonsai
# Copyright (C) 2026 Carlo Pavan <carlopav@gmail.com>
#
# This file is part of Bonsai5D+.  GNU GPL v3 or later.

import bpy
from .operator import BulkUpdateCostSchedule


class BulkUpdatePanel(bpy.types.Panel):
    bl_label = "Bulk Update from Rate List"
    bl_idname = "SCENE_PT_bulk_update_cost_schedule"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Bonsai5D+"
    bl_parent_id = "SCENE_PT_bonsai5d_toolbox"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        self.layout.operator(BulkUpdateCostSchedule.bl_idname, icon="FILE_REFRESH")


classes = [BulkUpdatePanel]
