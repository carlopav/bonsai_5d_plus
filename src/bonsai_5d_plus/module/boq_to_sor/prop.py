# Bonsai - OpenBIM 5D Blender Add-on based on Bonsai
# Copyright (C) 2026 Carlo Pavan <carlopav@gmail.com>
#
# This file is part of Bonsai5D+.  GNU GPL v3 or later.

import bpy
from .data import _sor_schedule_items


class MismatchedRateResolution(bpy.types.PropertyGroup):
    identification: bpy.props.StringProperty()
    rate_name: bpy.props.StringProperty()
    diff_fields: bpy.props.StringProperty()


classes = [MismatchedRateResolution]


def register():
    bpy.types.Scene.boq_to_sor_mode = bpy.props.EnumProperty(
        name="Mode",
        items=[
            ("NEW",    "Create New",      "Create a new Schedule of Rates"),
            ("UPDATE", "Update Existing", "Add missing items to an existing Schedule of Rates"),
        ],
        default="NEW",
    )
    bpy.types.Scene.boq_to_sor_target_schedule = bpy.props.EnumProperty(
        name="Schedule of Rates",
        items=_sor_schedule_items,
    )
    bpy.types.Scene.boq_to_sor_mismatched_rates = bpy.props.CollectionProperty(
        type=MismatchedRateResolution,
    )
    bpy.types.Scene.boq_to_sor_mismatched_index = bpy.props.IntProperty(default=0)


def unregister():
    del bpy.types.Scene.boq_to_sor_mode
    del bpy.types.Scene.boq_to_sor_target_schedule
    del bpy.types.Scene.boq_to_sor_mismatched_rates
    del bpy.types.Scene.boq_to_sor_mismatched_index
