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
from ...tool.cost import (
    get_rate_controller,
    get_rate_dependents,
    group_dependents_by_schedule,
    rate_dependent_diffs,
    is_item_in_sync,
    get_cost_item_schedule,
)


def _target_item(context):
    """The IfcCostItem currently loaded in the Cost Item Editor, or None."""
    try:
        from bonsai import tool
        file = tool.Ifc.get()
        tid = getattr(context.window_manager, "rate_analysis_target_ifc_id", 0)
        if file and tid:
            return file.by_id(int(tid))
    except Exception:
        pass
    return None


def _draw_rate_link_header(layout, context):
    """One-line rate-link status for the active cost item (header).

    Returns the row used for the 'Rate: ...' line (controller case), so the
    caller can append more controls to it — None otherwise.
    """
    item = _target_item(context)
    if item is None:
        return None
    ctrl = get_rate_controller(item)
    if ctrl is not None:
        synced = is_item_in_sync(item)
        sor = get_cost_item_schedule(ctrl)
        sor_name = (sor.Name if sor is not None else "") or "rate"
        ident = ctrl.Identification or ""
        label = f"Rate: {sor_name}" + (f"  [{ident}]" if ident else "")
        row = layout.row(align=True)
        row.label(text=label, icon="CHECKMARK" if synced else "ERROR")
        return row
    deps = get_rate_dependents(item)
    if deps:
        groups = group_dependents_by_schedule(item)
        in_sync = not rate_dependent_diffs(item)
        layout.label(
            text=f"Controls {len(deps)} item(s) in {len(groups)} schedule(s)",
            icon="CHECKMARK" if in_sync else "ERROR",
        )
    return None


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

        box = layout.box()

        row = box.row(align=True)
        row.label(text="Summary Cost Item:")
        sub = row.row(align=True)
        op = sub.operator("rate_analysis.add_cost_item", text="", icon="TRIA_UP")
        op.position, op.summary = 'BEFORE', True
        op = sub.operator("rate_analysis.add_cost_item", text="", icon="TRIA_DOWN")
        op.position, op.summary = 'AFTER', True
        op = sub.operator("rate_analysis.add_cost_item", text="", icon="TRIA_RIGHT")
        op.position, op.summary = 'CHILD', True

        row.separator()
        row.label(text="Cost Item:")
        sub = row.row(align=True)
        op = sub.operator("rate_analysis.add_cost_item", text="", icon="TRIA_UP")
        op.position, op.summary = 'BEFORE', False
        op = sub.operator("rate_analysis.add_cost_item", text="", icon="TRIA_DOWN")
        op.position, op.summary = 'AFTER', False
        op = sub.operator("rate_analysis.add_cost_item", text="", icon="TRIA_RIGHT")
        op.position, op.summary = 'CHILD', False

        layout.separator(factor=0.5)
        row = layout.row(align=True)
        row.scale_y = 1.3
        row.operator("rate_analysis.load_from_ifc", text="Load Item Data", icon="FILE_REFRESH")
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
            rate_row = _draw_rate_link_header(layout, context)
            if rate_row is not None:
                rate_row.operator("rate_analysis.load_controller", text="", icon="DRIVER")
                rate_row.operator("rate_analysis.unlink_from_rate", text="", icon="UNLINKED")
                rate_row.operator("rate_analysis.make_unique", text="", icon="DUPLICATE")
                rate_row.operator("rate_analysis.duplicate_rate", text="", icon="COPYDOWN")

        box2 = layout.box()

        header, panel = box2.panel("cie_identification", default_closed=False)
        header.label(text="Identification")
        if panel:
            _draw_identification(panel, context)

        header, panel = box2.panel("cie_rate_analysis", default_closed=True)
        header.label(text="Cost Value")
        if panel:
            _draw_cost_value(panel, context)

        header, panel = box2.panel("cie_quantities", default_closed=True)
        header.label(text="Cost Quantities")
        if panel:
            _draw_quantities(panel, context)

        header, panel = box2.panel("cie_rate_sync", default_closed=True)
        header.label(text="Rate Sync")
        if panel:
            _draw_rate_sync(panel, context)


def _draw_identification(layout, context):
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


def _draw_cost_value(layout, context):
    wm = context.window_manager

    row = layout.row(align=True)
    row.prop_enum(wm, "cost_value_mode", 'SUM')
    row.prop_enum(wm, "cost_value_mode", 'FIXED')
    row.prop_enum(wm, "cost_value_mode", 'RATE_ANALYSIS')
    layout.separator(factor=0.3)

    item = _target_item(context)
    deps = get_rate_dependents(item) if item is not None else []
    if deps:
        layout.label(text=f"Cost value controls {len(deps)} other value(s)", icon="INFO")

    if wm.cost_value_mode == 'SUM':
        _draw_cost_value_sum(layout, context)
    elif wm.cost_value_mode == 'FIXED':
        _draw_cost_value_fixed(layout, context)
    else:
        _draw_rate_analysis(layout, context)


def _draw_cost_value_sum(layout, context):
    layout.label(text="This item sums its children's costs.", icon="INFO")
    layout.separator(factor=0.3)
    row = layout.row(align=True)
    row.operator("rate_analysis.load_from_ifc", text="Load", icon="FILE_REFRESH")
    row.operator("cost_value.apply_sum", text="Apply Sum", icon="EXPORT")


def _draw_cost_value_fixed(layout, context):
    wm = context.window_manager
    item = _target_item(context)
    ctrl = get_rate_controller(item) if item is not None else None

    box = layout.box()
    if ctrl is not None:
        ident = ctrl.Identification or ctrl.Name or f"#{ctrl.id()}"
        box.label(text=f"Cost value controlled by item {ident}", icon="ERROR")
    col = box.column()
    col.enabled = ctrl is None
    col.prop(wm, "cost_value_fixed_amount")
    row = col.row(align=True)
    row.prop(wm, "cost_value_fixed_qty")
    row.prop(wm, "cost_value_fixed_unit", text="Unit")
    row.prop(wm, "cost_value_fixed_unit_enum", text="")

    layout.separator(factor=0.3)
    row = layout.row(align=True)
    row.operator("rate_analysis.load_from_ifc", text="Load", icon="FILE_REFRESH")
    row.operator("cost_value.apply_fixed", text="Apply Fixed Price", icon="EXPORT")


def _draw_rate_analysis(layout, context):
    wm = context.window_manager
    item = _target_item(context)
    ctrl = get_rate_controller(item) if item is not None else None
    if ctrl is not None:
        ident = ctrl.Identification or ctrl.Name or f"#{ctrl.id()}"
        layout.label(text=f"Cost value controlled by item {ident}", icon="ERROR")

    body = layout.column()
    body.enabled = ctrl is None

    row = body.row(align=True)
    row.operator("rate_analysis.add_component", text="", icon="ADD")
    row.operator("rate_analysis.add_from_rate", text="", icon="IMPORT")
    row.operator("rate_analysis.remove_component", text="", icon="REMOVE")
    row.operator("rate_analysis.move_up", text="", icon="TRIA_UP")
    row.operator("rate_analysis.move_down", text="", icon="TRIA_DOWN")
    row.separator()
    row.operator("rate_analysis.clear_all", text="", icon="TRASH")

    body.template_list(
        "RATE_UL_analysis", "",
        wm, "rate_analysis_components",
        wm, "rate_analysis_active_index",
        rows=5,
    )

    comps = wm.rate_analysis_components
    idx = wm.rate_analysis_active_index
    if 0 <= idx < len(comps):
        comp = comps[idx]
        box = body.box()
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
    box = body.box()

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

    box2 = body.box()
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

        col = row.column()
        col.scale_x = 0.9
        sel_icon = 'CHECKBOX_HLT' if item.is_selected else 'CHECKBOX_DEHLT'
        col.prop(item, "is_selected", text="", icon=sel_icon, emboss=False)

        col = row.column()
        col.scale_x = 2.0
        col.prop(item, "qty_desc", text="", emboss=True)

        for field in ("qty_nr", "qty_l", "qty_b", "qty_h"):
            col = row.column()
            col.scale_x = 1.4
            col.prop(item, field, text="", emboss=False)

        partial = _compute_partial_qty(item.qty_nr, item.qty_l, item.qty_b, item.qty_h)
        col = row.column()
        col.scale_x = 1.4
        col.label(text=f"{partial:.2f}")


def _draw_quantities(layout, context):
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
    row.separator()
    row.operator("cost_quantities.select_all",  text="", icon="CHECKBOX_HLT")
    row.operator("cost_quantities.select_none", text="", icon="CHECKBOX_DEHLT")
    row.separator()
    row.operator("cost_quantities.copy_rows",  text="", icon="COPYDOWN")
    row.operator("cost_quantities.paste_rows", text="", icon="PASTEDOWN")

    # Column headers — mirrors UIList column proportions
    hdr = layout.row(align=True)
    hdr.scale_y = 0.6
    col = hdr.column(); col.scale_x = 0.9; col.label(text="")
    col = hdr.column(); col.scale_x = 2.0;  col.label(text="Descrizione")
    for lbl in ("NR", "L", "B", "H"):
        col = hdr.column(); col.scale_x = 1.4; col.label(text=lbl)
    col = hdr.column(); col.scale_x = 1.4;  col.label(text="Parziale")

    layout.template_list(
        "MEAS_UL_rows", "",
        wm, "cost_quantities",
        wm, "cost_quantities_active_index",
        rows=5,
    )

    # Total row — "Totale:" centred, value aligned with "Parziale" column
    # Split factor ≈ (spacer+desc+4cols) / total_scale_units: 0.9+2.0+5.6 / 9.9 ≈ 0.86
    total = sum(
        _compute_partial_qty(r.qty_nr, r.qty_l, r.qty_b, r.qty_h)
        for r in wm.cost_quantities
    )
    unit = _QTY_UNIT_ABBR.get(wm.cost_quantities_type, "")
    total_row = layout.split(factor=0.86)
    lbl_col = total_row.row()
    lbl_col.alignment = 'CENTER'
    lbl_col.label(text="Totale:", icon="PROPERTIES")
    val_col = total_row.row()
    val_col.label(text=f"{total:.2f} {unit}".strip())

    layout.separator(factor=0.3)
    row = layout.row(align=True)
    row.operator("cost_quantities.load",  text="Load",             icon="FILE_REFRESH")
    row.operator("cost_quantities.apply", text="Apply Quantities", icon="EXPORT")


def _draw_rate_sync(layout, context):
    item = _target_item(context)

    if item is not None:
        ctrl = get_rate_controller(item)
        if ctrl is not None:
            # This item borrows its price from a rate.
            synced = is_item_in_sync(item)
            sor = get_cost_item_schedule(ctrl)
            sor_name = (sor.Name if sor is not None else "") or "rate"
            ident = ctrl.Identification or ""
            box = layout.box()
            box.label(
                text=f"Linked rate: {sor_name}" + (f"  [{ident}]" if ident else ""),
                icon="CHECKMARK" if synced else "ERROR",
            )
            if synced is False:
                op = box.operator("bonsai5d.resync_from_rate",
                                  text="Resync from rate", icon="FILE_REFRESH")
                op.item_id = item.id()

        deps = get_rate_dependents(item)
        if deps:
            # This item is a rate controlling other (CME) items.
            groups = group_dependents_by_schedule(item)
            diffs = rate_dependent_diffs(item)
            box = layout.box()
            hrow = box.row()
            hrow.label(text=f"Controls {len(deps)} item(s):")
            if diffs:
                hrow.label(text="out of sync", icon="ERROR")
            else:
                hrow.label(text="in sync", icon="CHECKMARK")
            for schedule, items in groups:
                name = (schedule.Name if schedule is not None else None) or "(no schedule)"
                n = len(items)
                box.label(text=f"   • {name}:  {n} item{'s' if n != 1 else ''}")
            row = box.row(align=True)
            op = row.operator("bonsai5d.propagate_rate",
                              text="Propagate now…", icon="EXPORT")
            op.rate_id = item.id()
            op = row.operator("bonsai5d.resync_rate_values",
                              text="Resync values", icon="FILE_REFRESH")
            op.rate_id = item.id()

        if get_rate_controller(item) is None and not get_rate_dependents(item):
            layout.label(text="No rate link on this item", icon="UNLINKED")
    else:
        layout.label(text="No active cost item")

    layout.separator(factor=0.5)
    row = layout.row(align=True)
    row.operator("bonsai5d.audit_schedule", text="Audit schedule", icon="VIEWZOOM")
    row.operator("bonsai5d.resync_schedule", text="Resync all", icon="FILE_REFRESH")


classes = [RATE_UL_analysis, MEAS_UL_rows, CostItemEditorPanel]
