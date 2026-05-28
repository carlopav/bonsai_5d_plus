# Bonsai - OpenBIM 5D Blender Add-on based on Bonsai
# Copyright (C) 2026 Carlo Pavan <carlopav@gmail.com>
#
# This file is part of Bonsai5D+.  GNU GPL v3 or later.

import textwrap
import bpy

from .operator import (
    COMPONENT_CATEGORIES,
    _get_totals,
    _get_cost_schedule,
    _DESCRIPTION_TEXT_NAME,
)


class RATE_UL_analysis(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=False)
        if item.category and item.category != 'NONE':
            row.label(text=f"[{item.category[:3].upper()}]")
        else:
            row.label(text="     ")
        name_col = row.column()
        name_col.scale_x = 1.6
        if item.source_ifc_id:
            ref_id = item.source_identification or f"#{item.source_ifc_id}"
            name_col.label(text=f"[{ref_id}] {item.description or ''}")
        else:
            name_col.label(text=item.description or "(no description)")
        subtotal = item.qty * item.unit_price
        row.label(text=f"{item.qty:.3g} {item.unit}  ×  {item.unit_price:.2f}  =  {subtotal:.2f}")
        if item.needs_rate_update:
            op = row.operator(
                "rate_analysis.refresh_component_rate",
                text="", icon="FILE_REFRESH", emboss=False,
            )
            op.component_index = index


class CostItemEditorPanel(bpy.types.Panel):
    bl_label = "Cost Item Editor"
    bl_idname = "SCENE_PT_cost_item_editor"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Bonsai5D+"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        wm = context.window_manager
        row = layout.row(align=True)
        row.scale_y = 1.3
        row.operator("rate_analysis.load_from_ifc", text="Load Item Data", icon="FILE_REFRESH")
        row.operator("rate_analysis.load_controller", text="", icon="DRIVER")
        row.prop(wm, "rate_analysis_auto_load", text="", icon="LINKED", toggle=True)

        if wm.rate_analysis_target_ifc_id:
            sched_label = "Cost Schedule: —"
            try:
                from bonsai import tool
                file = tool.Ifc.get()
                if file:
                    cost_item = file.by_id(wm.rate_analysis_target_ifc_id)
                    schedule = _get_cost_schedule(cost_item)
                    if schedule:
                        name = schedule.Name or "—"
                        ptype = (schedule.PredefinedType or "").replace("NOTDEFINED", "").replace("USERDEFINED", "")
                        sched_label = f"Cost Schedule:  {name}  [{ptype}]" if ptype else f"Cost Schedule:  {name}"
                    else:
                        sched_label = "Cost Schedule: (not found)"
                else:
                    sched_label = "Cost Schedule: (no IFC file)"
            except Exception as e:
                sched_label = f"Cost Schedule: (error: {e})"
            layout.label(text=sched_label, icon="SPREADSHEET")


class CIE_PT_Identification(bpy.types.Panel):
    bl_label = "Identification"
    bl_idname = "SCENE_PT_cie_identification"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Bonsai5D+"
    bl_parent_id = "SCENE_PT_cost_item_editor"

    def draw(self, context):
        layout = self.layout
        wm = context.window_manager

        layout.prop(wm, "rate_analysis_item_identification", text="ID")
        layout.prop(wm, "rate_analysis_item_name", text="Name")

        desc_box = layout.box()
        if not wm.rate_analysis_editing_description:
            row = desc_box.row()
            row.label(text="Description:", icon="TEXT")
            row.operator("rate_analysis.edit_description", text="", icon="GREASEPENCIL")
            if wm.rate_analysis_item_description:
                col = desc_box.column(align=True)
                col.scale_y = 0.7
                for paragraph in wm.rate_analysis_item_description.split("\n"):
                    for line in textwrap.wrap(paragraph, 60) or [" "]:
                        col.label(text=line)
            else:
                desc_box.label(text="(empty)", icon="INFO")
        else:
            col = desc_box.column()
            col.label(text="Editing description…", icon="GREASEPENCIL")
            col.label(text=f"Edit '{_DESCRIPTION_TEXT_NAME}' in Text Editor,")
            col.label(text="then:")
            row = desc_box.row(align=True)
            row.scale_y = 1.4
            row.operator("rate_analysis.apply_description", icon="CHECKMARK")
            row.operator("rate_analysis.cancel_description", icon="X")

        layout.separator(factor=0.3)
        row = layout.row(align=True)
        row.operator("rate_analysis.sync_item_info", text="Load", icon="FILE_REFRESH")
        row.operator("rate_analysis.apply_item_info", text="Apply Description", icon="CHECKMARK")


class CIE_PT_RateAnalysis(bpy.types.Panel):
    bl_label = "Rate Analysis"
    bl_idname = "SCENE_PT_cie_rate_analysis"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Bonsai5D+"
    bl_parent_id = "SCENE_PT_cost_item_editor"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        wm = context.window_manager

        row = layout.row(align=True)
        row.operator("rate_analysis.add_component", text="", icon="ADD")
        row.operator("rate_analysis.add_from_rate", text="", icon="IMPORT")
        row.operator("rate_analysis.remove_component", text="", icon="REMOVE")
        row.operator("rate_analysis.move_up", text="", icon="TRIA_UP")
        row.operator("rate_analysis.move_down", text="", icon="TRIA_DOWN")
        row.separator()
        row.operator("rate_analysis.clear_all", text="", icon="TRASH")

        layout.template_list(
            "RATE_UL_analysis", "",
            wm, "rate_analysis_components",
            wm, "rate_analysis_active_index",
            rows=5,
        )

        comps = wm.rate_analysis_components
        idx = wm.rate_analysis_active_index
        if 0 <= idx < len(comps):
            comp = comps[idx]
            box = layout.box()
            split = box.split(factor=0.25)
            split.label(text="Category:")
            row = split.row(align=True)
            row.prop_enum(comp, "category", 'NONE',         icon="REMOVE")
            row.prop_enum(comp, "category", 'SUB_CONTRACT', icon="LINKED")
            row.prop_enum(comp, "category", 'LABOR',        icon="COMMUNITY")
            row.prop_enum(comp, "category", 'EQUIPMENT',    icon="AUTO")
            row.prop_enum(comp, "category", 'MATERIAL',     icon="MATERIAL")
            row.prop_enum(comp, "category", 'SAFETY',       icon="LOCKED")
            box.prop(comp, "description")
            row = box.row(align=True)
            row.prop(comp, "qty")
            row.prop(comp, "unit", text="UM")
            row.prop(comp, "unit_price", text="Unit Price")
            row = box.row()
            row.label(text=f"Subtotal: {comp.qty * comp.unit_price:.2f}")
            if comp.source_ifc_id:
                ref_label = comp.source_identification or f"#{comp.source_ifc_id}"
                row.label(text=f"Rate ref: {ref_label}", icon="LINKED")

        ct, sg, profit, final = _get_totals(wm)
        box = layout.box()

        cat_totals = {}
        for c in wm.rate_analysis_components:
            cat_totals[c.category] = cat_totals.get(c.category, 0.0) + c.qty * c.unit_price
        for cat_id, cat_label, _ in COMPONENT_CATEGORIES:
            total = cat_totals.get(cat_id, 0.0)
            if total:
                split = box.split(factor=0.6)
                split.label(text=f"{cat_label}:")
                split.label(text=f"{total:.2f}")

        box.separator(factor=0.3)
        split = box.split(factor=0.6)
        split.label(text="Technical Cost:")
        split.label(text=f"{ct:.2f}")
        box.separator(factor=0.3)
        split = box.split(factor=0.6)
        split.prop(wm, "rate_analysis_overhead_pct", text="Overhead %")
        split.label(text=f"{sg:.2f}")
        split = box.split(factor=0.6)
        split.prop(wm, "rate_analysis_profit_pct", text="Profit %")
        split.label(text=f"{profit:.2f}")
        split = box.split(factor=0.6)
        split.prop(wm, "rate_analysis_rounding", text="Rounding")
        split.label(text="")

        box2 = layout.box()
        split = box2.split(factor=0.6)
        split.label(text="FINAL PRICE:", icon="FUND")
        split.label(text=f"{final:.2f}")

        layout.separator(factor=0.3)
        row = layout.row(align=True)
        row.operator("rate_analysis.load_from_ifc", text="Load", icon="FILE_REFRESH")
        row.operator("rate_analysis.apply_to_ifc", text="Apply Rate Analysis", icon="EXPORT")


classes = [RATE_UL_analysis, CostItemEditorPanel, CIE_PT_Identification, CIE_PT_RateAnalysis]
