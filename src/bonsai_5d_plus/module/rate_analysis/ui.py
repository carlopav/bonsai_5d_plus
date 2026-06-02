# Bonsai - OpenBIM 5D Blender Add-on based on Bonsai
# Copyright (C) 2026 Carlo Pavan <carlopav@gmail.com>
#
# This file is part of Bonsai5D+.  GNU GPL v3 or later.

import bpy

from .operator import (
    COMPONENT_CATEGORIES,
    _get_totals,
    _get_cost_schedule,
    _DESCRIPTION_TEXT_NAME,
    _QTY_UNIT_ABBR,
    _compute_partial_qty,
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
    def draw(self, context):
        layout = self.layout
        wm = context.window_manager

        row = layout.row(align=True)
        row.operator("rate_analysis.add_summary_cost", icon="ADD")
        row.separator()
        op = row.operator("rate_analysis.add_cost_item", text="", icon="TRIA_UP")
        op.position = 'BEFORE'
        op = row.operator("rate_analysis.add_cost_item", text="", icon="TRIA_DOWN")
        op.position = 'AFTER'
        op = row.operator("rate_analysis.add_cost_item", text="", icon="TRIA_RIGHT")
        op.position = 'CHILD'

        layout.separator(factor=0.5)
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

        if not wm.rate_analysis_editing_description:
            row = layout.row(align=True)
            row.prop(wm, "rate_analysis_item_description", text="Description")
            row.operator("rate_analysis.edit_description", text="", icon="GREASEPENCIL")
        else:
            box = layout.box()
            col = box.column()
            col.label(text="Editing description…", icon="GREASEPENCIL")
            col.label(text=f"Edit '{_DESCRIPTION_TEXT_NAME}' in Text Editor,")
            col.label(text="then:")
            row = box.row(align=True)
            row.scale_y = 1.4
            row.operator("rate_analysis.cancel_description", icon="X")
            row.operator("rate_analysis.apply_description", icon="CHECKMARK")

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
                r = split.row()
                r.alignment = 'RIGHT'
                r.label(text=f"{total:.2f}")

        box.separator(factor=0.3)
        split = box.split(factor=0.6)
        split.label(text="Technical Cost:")
        r = split.row(); r.alignment = 'RIGHT'; r.label(text=f"{ct:.2f}")
        box.separator(factor=0.3)
        split = box.split(factor=0.6)
        split.prop(wm, "rate_analysis_overhead_pct", text="Overhead %")
        r = split.row(); r.alignment = 'RIGHT'; r.label(text=f"{sg:.2f}")
        split = box.split(factor=0.6)
        split.prop(wm, "rate_analysis_profit_pct", text="Profit %")
        r = split.row(); r.alignment = 'RIGHT'; r.label(text=f"{profit:.2f}")
        split = box.split(factor=0.6)
        split.prop(wm, "rate_analysis_rounding", text="Rounding")
        split.label(text="")

        box2 = layout.box()
        split = box2.split(factor=0.6)
        row_label = split.row(align=True)
        row_label.label(text="FINAL PRICE:", icon="DISC")
        row_label.prop(wm, "rate_analysis_unit", text="")
        r = split.row(); r.alignment = 'RIGHT'; r.label(text=f"{final:.2f}")

        layout.separator(factor=0.3)
        row = layout.row(align=True)
        row.operator("rate_analysis.load_from_ifc", text="Load", icon="FILE_REFRESH")
        row.operator("rate_analysis.apply_to_ifc", text="Apply Rate Analysis", icon="EXPORT")


class MEAS_UL_rows(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)

        # Selection zone: clicking here selects the row without triggering text edit
        col = row.column()
        col.scale_x = 0.12
        col.label(text="")

        col = row.column()
        col.scale_x = 2.0
        col.prop(item, "qty_desc", text="", emboss=True)

        for field in ("qty_nr", "qty_l", "qty_b", "qty_h"):
            col = row.column()
            col.scale_x = 0.6
            col.prop(item, field, text="")

        partial = _compute_partial_qty(item.qty_nr, item.qty_l, item.qty_b, item.qty_h)
        col = row.column()
        col.scale_x = 0.7
        col.label(text=f"{partial:g}")

        op = row.operator("cost_quantities.insert_row_after", text="", icon="ADD", emboss=False)
        op.index = index


class CIE_PT_Quantities(bpy.types.Panel):
    bl_label = "Quantities"
    bl_idname = "SCENE_PT_cie_quantities"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Bonsai5D+"
    bl_parent_id = "SCENE_PT_cost_item_editor"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        wm = context.window_manager

        row = layout.row(align=True)
        row.prop(wm, "cost_quantities_type", text="")
        row.separator()
        row.operator("cost_quantities.add_row",       text="", icon="ADD")
        row.operator("cost_quantities.remove_row",    text="", icon="REMOVE")
        row.operator("cost_quantities.move_row_up",   text="", icon="TRIA_UP")
        row.operator("cost_quantities.move_row_down", text="", icon="TRIA_DOWN")
        row.separator()
        row.operator("rate_analysis.add_zero_quantity", text="", icon="RADIOBUT_OFF")

        # Column headers — mirrors UIList column proportions
        hdr = layout.row(align=True)
        hdr.scale_y = 0.6
        col = hdr.column(); col.scale_x = 0.12; col.label(text="")
        col = hdr.column(); col.scale_x = 2.0;  col.label(text="Descrizione")
        for lbl in ("NR", "L", "B", "H"):
            col = hdr.column(); col.scale_x = 0.6; col.label(text=lbl)
        col = hdr.column(); col.scale_x = 0.7;  col.label(text="Parziale")
        col = hdr.column(); col.scale_x = 0.25; col.label(text="")

        layout.template_list(
            "MEAS_UL_rows", "",
            wm, "cost_quantities",
            wm, "cost_quantities_active_index",
            rows=5,
        )

        # Total row — "Totale:" centred, value aligned with "Parziale" column
        # Split factor ≈ (spacer+desc+4cols) / total_scale_units: 0.12+2.0+2.4 / 5.47 ≈ 0.83
        total = sum(
            _compute_partial_qty(r.qty_nr, r.qty_l, r.qty_b, r.qty_h)
            for r in wm.cost_quantities
        )
        unit = _QTY_UNIT_ABBR.get(wm.cost_quantities_type, "")
        total_row = layout.split(factor=0.83)
        lbl_col = total_row.row()
        lbl_col.alignment = 'CENTER'
        lbl_col.label(text="Totale:", icon="PROPERTIES")
        val_col = total_row.row()
        val_col.label(text=f"{total:g} {unit}".strip())

        layout.separator(factor=0.3)
        row = layout.row(align=True)
        row.operator("cost_quantities.load",  text="Load",             icon="FILE_REFRESH")
        row.operator("cost_quantities.apply", text="Apply Quantities", icon="EXPORT")


classes = [RATE_UL_analysis, MEAS_UL_rows, CostItemEditorPanel, CIE_PT_Identification, CIE_PT_RateAnalysis, CIE_PT_Quantities]
