# Bonsai - OpenBIM 5D Blender Add-on based on Bonsai
# Copyright (C) 2026 Carlo Pavan <carlopav@gmail.com>
#
# This file is part of Bonsai5D+.  GNU GPL v3 or later.

import bpy
from .data import (
    _get_recent_items, _on_recent_select,
    _get_ifc_schedules, _on_ifc_schedule_select,
    _on_source_mode_change, _on_rate_selection_change,
    _refresh_recent_cache, _refresh_ifc_schedules_cache,
)


class RateListPropGroup(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty()
    level: bpy.props.IntProperty()
    is_parent: bpy.props.BoolProperty()
    parents: bpy.props.StringProperty()
    attributes: bpy.props.StringProperty()
    is_expanded: bpy.props.BoolProperty(default=True)


classes = [RateListPropGroup]


def register():
    bpy.types.Scene.xml_rate_list = bpy.props.CollectionProperty(type=RateListPropGroup)
    bpy.types.Scene.xml_rate_list_active_index = bpy.props.IntProperty(
        update=_on_rate_selection_change
    )
    bpy.types.Scene.xml_rate_title = bpy.props.StringProperty(name="Rate Title", default="")
    bpy.types.Scene.xml_rate_year = bpy.props.StringProperty(name="Rate Year", default="")
    bpy.types.Scene.xml_rate_combine_desc = bpy.props.BoolProperty(
        name="Combine Description with Parent",
        description="Prepend the parent item description to the selected item description",
        default=False,
    )
    bpy.types.Scene.xml_rate_recent_path = bpy.props.EnumProperty(
        name="Recent Price Lists",
        description="Recently opened price lists — select to load",
        items=_get_recent_items,
        update=_on_recent_select,
    )
    bpy.types.Scene.rate_source_mode = bpy.props.EnumProperty(
        name="Source",
        items=[
            ('FILE', "External Rate List", "Load from XML or XPWE file"),
            ('IFC_SCHEDULE', "Current Project Rate List", "Load from a cost schedule in the current IFC project"),
        ],
        default='FILE',
        update=_on_source_mode_change,
    )
    bpy.types.Scene.ifc_rate_source_schedule = bpy.props.EnumProperty(
        name="IFC Rate Schedule",
        description="Select a cost schedule from the current IFC project as rate source",
        items=_get_ifc_schedules,
        update=_on_ifc_schedule_select,
    )
    _refresh_recent_cache()
    _refresh_ifc_schedules_cache()


def unregister():
    del bpy.types.Scene.xml_rate_list
    del bpy.types.Scene.xml_rate_list_active_index
    del bpy.types.Scene.xml_rate_title
    del bpy.types.Scene.xml_rate_year
    del bpy.types.Scene.xml_rate_combine_desc
    del bpy.types.Scene.xml_rate_recent_path
    del bpy.types.Scene.rate_source_mode
    del bpy.types.Scene.ifc_rate_source_schedule
