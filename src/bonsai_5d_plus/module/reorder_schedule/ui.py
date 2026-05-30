# Bonsai - OpenBIM 5D Blender Add-on based on Bonsai
# Copyright (C) 2026 Carlo Pavan <carlopav@gmail.com>
#
# This file is part of Bonsai5D+.  GNU GPL v3 or later.

import bpy


class ReorderSchedulePanel(bpy.types.Panel):
    bl_label = "Reorder Cost Schedule"
    bl_idname = "SCENE_PT_reorder_cost_schedule"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Bonsai5D+"
    bl_parent_id = "SCENE_PT_bonsai5d_sandbox"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        row = layout.row(align=True)
        row.operator("reorder_schedule.reorder_identifications",        text="Reorder All",          icon="SORTALPHA")
        row.operator("reorder_schedule.reorder_keep_root_summary",      text="Keep Root Summaries",  icon="OUTLINER")


classes = [ReorderSchedulePanel]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
