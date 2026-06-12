# Bonsai - OpenBIM 5D Blender Add-on based on Bonsai
# Copyright (C) 2026 Carlo Pavan <carlopav@gmail.com>
#
# This file is part of Bonsai5D+.  GNU GPL v3 or later.

import bpy
from .data import (
    _get_recent_items, _on_recent_select,
    _get_ifc_schedules, _on_ifc_schedule_select,
    _on_source_mode_change, _on_rate_selection_change,
    _on_search_query_change, _on_search_result_select,
    _on_llm_result_select,
    _refresh_recent_cache, _refresh_ifc_schedules_cache,
)


class RateListPropGroup(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty()
    level: bpy.props.IntProperty()
    is_parent: bpy.props.BoolProperty()
    parents: bpy.props.StringProperty()
    attributes: bpy.props.StringProperty()
    is_expanded: bpy.props.BoolProperty(default=True)


class SearchResultPropGroup(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty()
    rate_index: bpy.props.IntProperty()
    score: bpy.props.FloatProperty()


class LLMResultPropGroup(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty()    # display: "ID – Nome"
    rate_index: bpy.props.IntProperty()
    item_id: bpy.props.StringProperty()
    motivo: bpy.props.StringProperty()


classes = [RateListPropGroup, SearchResultPropGroup, LLMResultPropGroup]


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
    bpy.types.Scene.xml_rate_search_query = bpy.props.StringProperty(
        name="Search",
        description="Descrizione libera da cercare nel prezzario caricato",
        default="",
        update=_on_search_query_change,
    )
    bpy.types.Scene.xml_rate_search_results = bpy.props.CollectionProperty(
        type=SearchResultPropGroup,
    )
    bpy.types.Scene.xml_rate_search_active_index = bpy.props.IntProperty(
        update=_on_search_result_select,
    )
    bpy.types.Scene.xml_llm_query = bpy.props.StringProperty(
        name="AI Query",
        description="Descrivi la lavorazione — l'AI suggerisce le voci più pertinenti",
        default="",
    )
    bpy.types.Scene.xml_llm_results = bpy.props.CollectionProperty(type=LLMResultPropGroup)
    bpy.types.Scene.xml_llm_active_index = bpy.props.IntProperty(update=_on_llm_result_select)
    bpy.types.Scene.xml_llm_status = bpy.props.StringProperty(default="")
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
    del bpy.types.Scene.xml_rate_search_query
    del bpy.types.Scene.xml_rate_search_results
    del bpy.types.Scene.xml_rate_search_active_index
    del bpy.types.Scene.xml_llm_query
    del bpy.types.Scene.xml_llm_results
    del bpy.types.Scene.xml_llm_active_index
    del bpy.types.Scene.xml_llm_status
