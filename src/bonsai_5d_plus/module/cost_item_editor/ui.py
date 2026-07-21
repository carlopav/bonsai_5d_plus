# Bonsai - OpenBIM 5D Blender Add-on based on Bonsai
# Copyright (C) 2026 Carlo Pavan <carlopav@gmail.com>
#
# This file is part of Bonsai5D+.  GNU GPL v3 or later.

import bpy

from .operator import (
    COMPONENT_CATEGORIES,
    _get_totals,
    _get_cost_schedule,
    _get_rate_value_and_unit,
    _DESCRIPTION_TEXT_NAME,
    _compute_partial_qty,
    _unit_display_label,
)
from ...tool.cost import (
    get_rate_controller,
    get_rate_dependents,
    group_dependents_by_schedule,
    rate_dependent_diffs,
    is_item_in_sync,
    get_cost_item_schedule,
    is_summary_cost_item,
    get_cost_item_children,
)


def _target_item(context):
    """The IfcCostItem currently loaded in the Cost Item Editor, or None."""
    try:
        from bonsai import tool
        file = tool.Ifc.get()
        tid = getattr(context.scene.bonsai5d_cost_editor, "rate_analysis_target_ifc_id", 0)
        if file and tid:
            return file.by_id(int(tid))
    except Exception:
        pass
    return None


def _draw_rate_link_header(layout, context):
    """One-line rate-link status for the active cost item (header), with the
    relevant link/sync operators attached."""
    item = _target_item(context)
    if item is None:
        return
    ctrl = get_rate_controller(item)
    if ctrl is not None:
        synced = is_item_in_sync(item)
        sor = get_cost_item_schedule(ctrl)
        sor_name = (sor.Name if sor is not None else "") or "rate"
        ident = ctrl.Identification or ""
        label = f"Rate: {sor_name}" + (f"  [{ident}]" if ident else "")
        row = layout.row(align=True)
        row.label(text=label, icon="CHECKMARK" if synced else "ERROR")
        row.operator("rate_analysis.load_controller", text="", icon="DRIVER")
        if not synced:
            op = row.operator("bonsai5d.resync_from_rate", text="", icon="FILE_REFRESH")
            op.item_id = item.id()
        row.operator("rate_analysis.unlink_from_rate", text="", icon="UNLINKED")
        row.operator("rate_analysis.make_unique", text="", icon="DUPLICATE")
        row.operator("rate_analysis.duplicate_rate", text="", icon="COPYDOWN")
        return
    deps = get_rate_dependents(item)
    if deps:
        groups = group_dependents_by_schedule(item)
        in_sync = not rate_dependent_diffs(item)
        row = layout.row(align=True)
        row.label(
            text=f"Controls {len(deps)} item(s) in {len(groups)} schedule(s)",
            icon="CHECKMARK" if in_sync else "ERROR",
        )
        op = row.operator("bonsai5d.propagate_rate", text="", icon="EXPORT")
        op.rate_id = item.id()
        op = row.operator("bonsai5d.resync_rate_values", text="", icon="FILE_REFRESH")
        op.rate_id = item.id()


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
        unit_label = _unit_display_label(item.unit, item.unit_custom)
        row.label(text=f"{item.qty:.3g} {unit_label}  ×  {item.unit_price:.2f}  =  {subtotal:.2f}")
        row.prop(
            item, "apply_markup", text="", emboss=False,
            icon='CHECKBOX_HLT' if item.apply_markup else 'CHECKBOX_DEHLT',
        )
        if item.needs_rate_update:
            op = row.operator(
                "rate_analysis.refresh_component_rate",
                text="", icon="FILE_REFRESH", emboss=False,
            )
            op.component_index = index


class FIXED_UL_values(bpy.types.UIList):
    """Editable list of flat cost values: category, name, value — all inline."""
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "category", text="", emboss=False)
        name_col = row.column()
        name_col.scale_x = 2.0
        name_col.prop(item, "description", text="", emboss=False)
        row.prop(item, "unit_price", text="", emboss=False)


class CostItemEditorPanel(bpy.types.Panel):
    bl_label = "Cost Item Editor"
    bl_idname = "SCENE_PT_cost_item_editor"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Bonsai5D+"
    def draw(self, context):
        layout = self.layout
        ed = context.scene.bonsai5d_cost_editor

        box = layout.box()

        row = box.row(align=True)
        row.label(text="Add Summary Cost Item:")
        sub = row.row(align=True)
        op = sub.operator("rate_analysis.add_cost_item", text="", icon="TRIA_UP")
        op.position, op.summary = 'BEFORE', True
        op = sub.operator("rate_analysis.add_cost_item", text="", icon="TRIA_DOWN")
        op.position, op.summary = 'AFTER', True
        op = sub.operator("rate_analysis.add_cost_item", text="", icon="TRIA_RIGHT")
        op.position, op.summary = 'CHILD', True

        row.separator()
        row.label(text="Add Cost Item:")
        sub = row.row(align=True)
        op = sub.operator("rate_analysis.add_cost_item", text="", icon="TRIA_UP")
        op.position, op.summary = 'BEFORE', False
        op = sub.operator("rate_analysis.add_cost_item", text="", icon="TRIA_DOWN")
        op.position, op.summary = 'AFTER', False
        op = sub.operator("rate_analysis.add_cost_item", text="", icon="TRIA_RIGHT")
        op.position, op.summary = 'CHILD', False

        row.separator()
        row.label(text="Reorder:")
        sub = row.row(align=True)
        op = sub.operator("rate_analysis.move_cost_item", text="", icon="TRIA_UP")
        op.direction = 'UP'
        op = sub.operator("rate_analysis.move_cost_item", text="", icon="TRIA_DOWN")
        op.direction = 'DOWN'

        layout.separator(factor=0.5)
        row = layout.row(align=True)
        row.scale_y = 1.3
        row.operator("rate_analysis.load_from_ifc", text="Load Item Data", icon="FILE_REFRESH")
        row.prop(ed, "rate_analysis_auto_load", text="", icon="LINKED", toggle=True)

        if ed.rate_analysis_target_ifc_id:
            sched_label = "Cost Schedule: —"
            try:
                from bonsai import tool
                file = tool.Ifc.get()
                if file:
                    cost_item = file.by_id(ed.rate_analysis_target_ifc_id)
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
            _draw_rate_link_header(layout, context)

        box2 = layout.box()

        header, panel = box2.panel("cie_identification", default_closed=False)
        header.label(text="Identification")
        if panel:
            _draw_identification(panel, context)

        header, panel = box2.panel("cie_rate_analysis", default_closed=True)
        header.label(text="Cost Values")
        if panel:
            _draw_cost_value(panel, context)

        header, panel = box2.panel("cie_quantities", default_closed=True)
        header.label(text="Cost Quantities")
        if panel:
            _draw_quantities(panel, context)


def _draw_identification(layout, context):
    ed = context.scene.bonsai5d_cost_editor

    layout.prop(ed, "rate_analysis_item_identification", text="ID")
    layout.prop(ed, "rate_analysis_item_name", text="Name")

    if not ed.rate_analysis_editing_description:
        row = layout.row(align=True)
        row.prop(ed, "rate_analysis_item_description", text="Description")
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
    ed = context.scene.bonsai5d_cost_editor

    item = _target_item(context)
    ctrl = get_rate_controller(item) if item is not None else None
    if ctrl is not None:
        sor = get_cost_item_schedule(ctrl)
        sor_name = (sor.Name if sor is not None else "") or "—"
        sor_type = (sor.PredefinedType or "") if sor is not None else ""

        box = layout.box()
        header = f"Rate controlled by: {sor_name}({sor_type})" if sor_type else f"Rate controlled by: {sor_name}"
        box.label(text=header, icon="LINKED")
        if ctrl.Identification:
            box.label(text=f"Identification: {ctrl.Identification}")
        if ctrl.Name:
            box.label(text=f"Name: {ctrl.Name}")

        try:
            from bonsai import tool
            file = tool.Ifc.get()
            value, unit = _get_rate_value_and_unit(file, ctrl.id())
            currency = ""
            monetary = file.by_type("IfcMonetaryUnit")
            if monetary:
                currency = monetary[0].Currency or ""
        except Exception:
            value, unit, currency = None, "", ""
        if value is not None:
            total_text = f"Value: {value:.2f}" + (f" {currency}" if currency else "")
            if unit:
                total_text += f" / {unit}"
            box.label(text=total_text)
        return

    row = layout.row(align=True)
    row.prop_enum(ed, "cost_value_mode", 'SUM')
    row.prop_enum(ed, "cost_value_mode", 'FIXED')
    row.prop_enum(ed, "cost_value_mode", 'RATE_ANALYSIS')
    layout.separator(factor=0.3)

    deps = get_rate_dependents(item) if item is not None else []
    if deps:
        layout.label(text=f"Cost value controls {len(deps)} other value(s)", icon="INFO")

    if ed.cost_value_mode == 'SUM':
        _draw_cost_value_sum(layout, context)
    elif ed.cost_value_mode == 'FIXED':
        _draw_cost_value_fixed(layout, context)
    else:
        _draw_rate_analysis(layout, context)


def _draw_cost_value_sum(layout, context):
    item = _target_item(context)
    is_sum = item is not None and is_summary_cost_item(item)
    if not is_sum:
        layout.operator(
            "cost_value.apply_sum",
            text="Clear cost values and mark item as a Sum",
            icon="ADD",
        )
        return

    layout.label(text="This item sums its children's costs.", icon="INFO")


def _draw_cost_value_fixed(layout, context):
    ed = context.scene.bonsai5d_cost_editor

    item = _target_item(context)
    if item is not None and get_cost_item_children(item):
        layout.label(text="This item has children — Fixed applies only to leaf items.", icon="ERROR")
        layout.label(text="Use Sum to aggregate its children's costs instead.")
        return

    is_sum = item is not None and is_summary_cost_item(item)
    is_rate_analysis = item is not None and item.ObjectType == "RATE_ANALYSIS"
    if (is_sum or is_rate_analysis) and not ed.cost_value_fixed_drafting:
        layout.operator(
            "cost_value.start_fixed_draft",
            text="Clear cost values and add new fixed cost value",
            icon="ADD",
        )
        return

    row = layout.row(align=True)
    row.alignment = 'RIGHT'
    row.operator("cost_value.add_fixed_component", text="", icon="ADD")
    row.operator("cost_value.remove_fixed_component", text="", icon="REMOVE")
    row.operator("cost_value.move_fixed_component_up", text="", icon="TRIA_UP")
    row.operator("cost_value.move_fixed_component_down", text="", icon="TRIA_DOWN")

    layout.template_list(
        "FIXED_UL_values", "fixed",
        ed, "cost_value_fixed_components",
        ed, "cost_value_fixed_active_index",
        rows=5,
    )

    comps = ed.cost_value_fixed_components
    total = sum(c.unit_price for c in comps)
    row = layout.row(align=True)
    row.label(text=f"Total: {total:.2f}")
    row.prop(ed, "cost_value_fixed_unit", text="")
    if ed.cost_value_fixed_unit == 'USERDEFINED':
        row.prop(ed, "cost_value_fixed_unit_custom", text="")
    if ed.cost_value_fixed_unit_mixed:
        layout.label(text="Rows had different units on load — unified above, review before applying.", icon="ERROR")

    layout.separator(factor=0.3)
    row = layout.row(align=True)
    row.operator("rate_analysis.load_from_ifc", text="Load", icon="FILE_REFRESH")
    row.operator("cost_value.apply_fixed", text="Apply Fixed", icon="EXPORT")


def _draw_rate_analysis(layout, context):
    ed = context.scene.bonsai5d_cost_editor

    item = _target_item(context)
    if item is not None and get_cost_item_children(item):
        layout.label(text="This item has children — Rate Analysis applies only to leaf items.", icon="ERROR")
        layout.label(text="Use Sum to aggregate its children's costs instead.")
        return

    is_applied = item is not None and item.ObjectType == "RATE_ANALYSIS"
    if not is_applied and not ed.rate_analysis_drafting:
        layout.operator("rate_analysis.start_draft", text="Clear cost values and add rate analysis", icon="ADD")
        return

    body = layout.column()

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
        ed, "rate_analysis_components",
        ed, "rate_analysis_active_index",
        rows=5,
    )

    comps = ed.rate_analysis_components
    idx = ed.rate_analysis_active_index
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
        box.prop(comp, "description", text="Name")
        # A free-form component owns its extended description; a linked one shows
        # the source price-list item's description in the print instead.
        if not comp.source_ifc_id:
            box.prop(comp, "long_description", text="Description")
        row = box.row(align=True)
        row.prop(comp, "qty")
        row.prop(comp, "unit", text="UM")
        if comp.unit == 'USERDEFINED':
            row.prop(comp, "unit_custom", text="")
        row.prop(comp, "unit_price", text="Unit Price")
        row = box.row()
        row.label(text=f"Subtotal: {comp.qty * comp.unit_price:.2f}")
        if comp.source_ifc_id:
            ref_label = comp.source_identification or f"#{comp.source_ifc_id}"
            row.label(text=f"Rate ref: {ref_label}", icon="LINKED")
        box.prop(comp, "apply_markup", text="Subject to safety costs, overhead and profit")

    ct, safety, sg, profit, subtotal, ct_incl, final = _get_totals(ed)
    box = body.box()

    def _amount_row(label, amount):
        split = box.split(factor=0.6)
        split.label(text=label)
        r = split.row(); r.alignment = 'RIGHT'; r.label(text=f"{amount:.2f}")

    def _pct_row(prop_name, label, amount):
        split = box.split(factor=0.6)
        split.prop(ed, prop_name, text=label)
        r = split.row(); r.alignment = 'RIGHT'; r.label(text=f"{amount:.2f}")

    # Category subtotals cover the marked-up base only; items already inclusive of
    # markups get their own section below.
    cat_totals = {}
    for c in ed.rate_analysis_components:
        if c.apply_markup:
            cat_totals[c.category] = cat_totals.get(c.category, 0.0) + c.qty * c.unit_price
    for cat_id, cat_label, _ in COMPONENT_CATEGORIES:
        total = cat_totals.get(cat_id, 0.0)
        if total:
            _amount_row(f"{cat_label}:", total)

    box.separator(factor=0.3)
    _amount_row("Technical Cost:", ct)
    box.separator(factor=0.3)
    _pct_row("rate_analysis_safety_pct", "Safety %", safety)
    _pct_row("rate_analysis_overhead_pct", "Overhead %", sg)
    _pct_row("rate_analysis_profit_pct", "Profit %", profit)

    if ct_incl:
        box.separator(factor=0.3)
        _amount_row("Subtotal:", subtotal)
        box.separator(factor=0.3)
        col = box.column()
        col.scale_y = 0.7
        col.label(text="Rate items already including safety costs,")
        col.label(text="overhead and profit:")
        _amount_row("", ct_incl)

    box.separator(factor=0.3)
    split = box.split(factor=0.6)
    split.prop(ed, "rate_analysis_rounding", text="Rounding")
    split.label(text="")

    box2 = body.box()
    split = box2.split(factor=0.6)
    row_label = split.row(align=True)
    row_label.label(text="FINAL PRICE:", icon="DISC")
    row_label.prop(ed, "rate_analysis_unit", text="")
    if ed.rate_analysis_unit == 'USERDEFINED':
        row_label.prop(ed, "rate_analysis_unit_custom", text="")
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
    ed = context.scene.bonsai5d_cost_editor

    item = _target_item(context)
    if item is not None and get_cost_item_children(item):
        layout.label(text="This item has children — Quantities applies only to leaf items.", icon="ERROR")
        return

    row = layout.row(align=True)
    row.prop(ed, "cost_quantities_unit", text="")
    if ed.cost_quantities_unit == 'USERDEFINED':
        row.prop(ed, "cost_quantities_unit_custom", text="")
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
        ed, "cost_quantities",
        ed, "cost_quantities_active_index",
        rows=5,
    )

    # Total row — "Totale:" centred, value aligned with "Parziale" column
    # Split factor ≈ (spacer+desc+4cols) / total_scale_units: 0.9+2.0+5.6 / 9.9 ≈ 0.86
    total = sum(
        _compute_partial_qty(r.qty_nr, r.qty_l, r.qty_b, r.qty_h)
        for r in ed.cost_quantities
    )
    unit_label = _unit_display_label(ed.cost_quantities_unit, ed.cost_quantities_unit_custom)
    total_row = layout.split(factor=0.86)
    lbl_col = total_row.row()
    lbl_col.alignment = 'CENTER'
    lbl_col.label(text="Totale:", icon="PROPERTIES")
    val_col = total_row.row()
    val_col.label(text=f"{total:.2f} {unit_label}".strip())

    layout.separator(factor=0.3)
    row = layout.row(align=True)
    row.operator("cost_quantities.load",  text="Load",             icon="FILE_REFRESH")
    row.operator("cost_quantities.apply", text="Apply Quantities", icon="EXPORT")


classes = [RATE_UL_analysis, FIXED_UL_values, MEAS_UL_rows, CostItemEditorPanel]
