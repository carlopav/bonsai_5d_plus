# Bonsai - OpenBIM 5D Blender Add-on based on Bonsai
# Copyright (C) 2026 Carlo Pavan <carlopav@gmail.com>
#
# This file is part of Bonsai5D+.  GNU GPL v3 or later.

import json
import bpy

from . import data as _data
from .data import _invalidate_filter_cache
from .operator import (
    ImportRateList,
    UpdateActiveCostItem,
    ImportRateToActiveCostSchedule,
    AssignRateValue,
    CUSTOM_OT_collapse_to_level_0,
    CUSTOM_OT_collapse_to_level_1,
    CUSTOM_OT_expand_all,
    IFC_OT_rate_source_refresh,
    BuildSearchIndex,
    LLMSuggestRates,
    LLMConfirmChoice,
)


_filter_cache: dict = {}  # {(gen, filter_name, sort_reverse): (flt_flags, flt_neworder)}


class RATE_UL_xml_list(bpy.types.UIList):
    def draw_filter(self, context, layout):
        layout.prop(self, "filter_name", text="", icon="VIEWZOOM")

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        rate_attrib = json.loads(item.attributes)
        layout.alignment = "LEFT"
        if rate_attrib["is_parent"]:
            icon_expand = "DOWNARROW_HLT" if item.is_expanded else "RIGHTARROW"
            row = layout.row()
            row.alignment = "RIGHT"
            if item.level != 0:
                row.label(text="  " * item.level)
            op = row.operator("xml_rate_list_ui.toggle", text="", icon=icon_expand, emboss=False)
            row.label(text=item.name)
            op.index = index
        else:
            layout.label(text="          " * item.level + item.name)

    def filter_items(self, context, data, propname):
        cache_key = (_data._filter_gen, self.filter_name, self.use_filter_sort_reverse)
        if cache_key in _filter_cache:
            return _filter_cache[cache_key]

        items = getattr(data, propname)
        flt_flags = []
        flt_neworder = []

        if self.filter_name:
            flt_flags = bpy.types.UI_UL_list.filter_items_by_name(
                self.filter_name,
                self.bitflag_filter_item,
                items,
                "name",
                reverse=self.use_filter_sort_reverse,
            )
            search_filtered_flags = flt_flags[:]
            for i, item in enumerate(items):
                if flt_flags[i] & self.bitflag_filter_item:
                    for parent_idx in [int(p) for p in item.parents.split(",") if p.strip()]:
                        search_filtered_flags[parent_idx] = self.bitflag_filter_item
            flt_flags = search_filtered_flags

            final_flags = []
            hide_next = False
            hide_level = 10
            for i, item in enumerate(items):
                show_item = (flt_flags[i] & self.bitflag_filter_item) != 0
                if show_item:
                    if hide_next:
                        if item.level <= hide_level:
                            show_item = True
                            hide_next = not item.is_expanded
                            if hide_next:
                                hide_level = item.level
                        else:
                            show_item = False
                    else:
                        show_item = True
                        if not item.is_expanded:
                            hide_next = True
                            hide_level = item.level
                final_flags.append(self.bitflag_filter_item if show_item else 0)
            flt_flags = final_flags
        else:
            hide_next = False
            hide_level = 10
            for item in items:
                show_item = True
                if hide_next:
                    if item.level <= hide_level:
                        show_item = True
                        hide_next = not item.is_expanded
                        if hide_next:
                            hide_level = item.level
                    else:
                        show_item = False
                else:
                    show_item = True
                    if not item.is_expanded:
                        hide_next = True
                        hide_level = item.level
                flt_flags.append(self.bitflag_filter_item if show_item else 0)

        _filter_cache.clear()
        _filter_cache[cache_key] = (flt_flags, flt_neworder)
        return flt_flags, flt_neworder


class RateListPanel(bpy.types.Panel):
    bl_label = "Rate List Importer"
    bl_idname = "SCENE_PT_xml_rate_list"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Bonsai5D+"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        row = layout.row(align=True)
        row.prop(context.scene, "rate_source_mode", expand=True)
        row = layout.row(align=True)
        if context.scene.rate_source_mode == 'FILE':
            row.prop(context.scene, "xml_rate_recent_path", text="")
            row.operator(ImportRateList.bl_idname, text="", icon="ADD")
        else:
            row.prop(context.scene, "ifc_rate_source_schedule", text="")
            row.operator(IFC_OT_rate_source_refresh.bl_idname, text="", icon="FILE_REFRESH")
        row = layout.row()
        row.operator(CUSTOM_OT_collapse_to_level_0.bl_idname, text="Collapse")
        row.operator(CUSTOM_OT_collapse_to_level_1.bl_idname, text="To Level 1")
        row.operator(CUSTOM_OT_expand_all.bl_idname, text="Expand All")
        layout.template_list(
            "RATE_UL_xml_list", "",
            context.scene, "xml_rate_list",
            context.scene, "xml_rate_list_active_index",
            rows=8,
        )

        from ...core import semantic_search as _ss
        if len(context.scene.xml_rate_list) > 0:
            if _ss.is_ready():
                layout.prop(context.scene, "xml_rate_search_query", text="Semantic search:", icon="VIEWZOOM")
                results = context.scene.xml_rate_search_results
                if len(results) > 0:
                    layout.template_list(
                        "RATE_UL_search_results", "",
                        context.scene, "xml_rate_search_results",
                        context.scene, "xml_rate_search_active_index",
                        rows=5,
                    )
            else:
                layout.operator(BuildSearchIndex.bl_idname, icon="SORTTIME")

        box = layout.box()
        row = box.row()
        rate_info = _data.active_item_info.split("\n")
        if len(rate_info) > 5:
            row.label(text=rate_info[0])
            btn_row = row.row(align=True)
            btn_row.alignment = "RIGHT"
            btn_row.prop(context.scene, "xml_rate_combine_desc", text="", icon="OUTLINER", toggle=True)
            btn_row.separator(factor=2.0)
            btn_row.operator(ImportRateToActiveCostSchedule.bl_idname, text="", icon="ADD")
            btn_row.operator(UpdateActiveCostItem.bl_idname, text="", icon="FILE_REFRESH")
            btn_row.operator(AssignRateValue.bl_idname, text="", icon="COPYDOWN")
            row = box.row()
            box.label(text=rate_info[1])
            row = box.row()
            row.label(text="unit: " + rate_info[2])
            row.label(text="value: " + rate_info[3])
            box = layout.box()
            box.label(text="Cost Value Components:")
            row = box.row()
            row.label(text="labor: " + rate_info[4])
            row.label(text="equipment: " + rate_info[5])
            row = box.row()
            row.label(text="materials: " + rate_info[6])
            row.label(text="safety: " + rate_info[7])
            box = layout.box()
            for row in rate_info[8:]:
                box.label(text=row)


class RATE_UL_search_results(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout.label(text=item.name)


class RATE_UL_llm_results(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        col = layout.column()
        col.label(text=item.name)
        if item.motivo:
            sub = col.row()
            sub.enabled = False
            sub.label(text=item.motivo)


class AISearchSubPanel(bpy.types.Panel):
    bl_label = "AI Rate Search"
    bl_idname = "SCENE_PT_ai_rate_search"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Bonsai5D+"
    bl_parent_id = "SCENE_PT_xml_rate_list"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        from ...core import llm_search as _llm
        layout = self.layout

        if not len(context.scene.xml_rate_list):
            layout.label(text="Carica un prezzario per usare l'AI", icon="INFO")
            return

        row = layout.row(align=True)
        row.prop(context.scene, "xml_llm_query", text="", icon="OUTLINER_DATA_FONT")
        row.operator(LLMSuggestRates.bl_idname, text="", icon="SHADERFX")

        status = context.scene.xml_llm_status
        if status:
            layout.label(text=status, icon="INFO")

        results = context.scene.xml_llm_results
        if len(results) > 0:
            layout.template_list(
                "RATE_UL_llm_results", "",
                context.scene, "xml_llm_results",
                context.scene, "xml_llm_active_index",
                rows=3,
            )
            row = layout.row()
            row.operator(LLMConfirmChoice.bl_idname, icon="CHECKMARK")


classes = [RATE_UL_xml_list, RateListPanel, RATE_UL_search_results,
           RATE_UL_llm_results, AISearchSubPanel]
