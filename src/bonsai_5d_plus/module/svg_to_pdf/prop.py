# Bonsai - OpenBIM 5D Blender Add-on based on Bonsai
# Copyright (C) 2026 Carlo Pavan <carlopav@gmail.com>
#
# This file is part of Bonsai5D+.  GNU GPL v3 or later.

import bpy


class ComparisonScheduleItem(bpy.types.PropertyGroup):
    schedule_id:      bpy.props.IntProperty()
    name:             bpy.props.StringProperty()
    predefined_type:  bpy.props.StringProperty()
    is_base:          bpy.props.BoolProperty(default=False)
    enabled:          bpy.props.BoolProperty(default=True)


classes = [ComparisonScheduleItem]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.WindowManager.comparison_schedules = bpy.props.CollectionProperty(
        type=ComparisonScheduleItem,
    )
    bpy.types.WindowManager.comparison_active_index = bpy.props.IntProperty(default=0)


def unregister():
    del bpy.types.WindowManager.comparison_schedules
    del bpy.types.WindowManager.comparison_active_index
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
