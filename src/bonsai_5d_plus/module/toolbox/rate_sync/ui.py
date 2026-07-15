# Bonsai - OpenBIM 5D Blender Add-on based on Bonsai
# Copyright (C) 2026 Carlo Pavan <carlopav@gmail.com>
#
# This file is part of Bonsai5D+.  GNU GPL v3 or later.

import bpy


class RateSyncPanel(bpy.types.Panel):
    bl_label = "Rate Sync"
    bl_idname = "SCENE_PT_bonsai5d_rate_sync"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Bonsai5D+"
    bl_parent_id = "SCENE_PT_bonsai5d_toolbox"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        row = layout.row(align=True)
        row.operator("bonsai5d.audit_schedule", text="Audit schedule", icon="VIEWZOOM")
        row.operator("bonsai5d.resync_schedule", text="Resync all", icon="FILE_REFRESH")


classes = [RateSyncPanel]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
