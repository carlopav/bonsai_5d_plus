# Bonsai - OpenBIM 5D Blender Add-on based on Bonsai
# Copyright (C) 2026 Carlo Pavan <carlopav@gmail.com>
#
# This file is part of Bonsai5D+.  GNU GPL v3 or later.

import re
import time as _time
import bpy

try:
    from bonsai import tool as _bonsai_tool
    _IfcOperatorBase = (_bonsai_tool.Ifc.Operator, bpy.types.Operator)
    del _bonsai_tool
except Exception:
    _IfcOperatorBase = (bpy.types.Operator,)

# ---------------------------------------------------------------------------
# Constants (used by prop.py, ui.py)
# ---------------------------------------------------------------------------

COMPONENT_CATEGORIES = (
    ('NONE',         "—",            "No category (existing value, not a rate analysis component)"),
    ('SUB_CONTRACT', "Sub-Contract", "Subcontracted works (opere compiute)"),
    ('LABOR',        "Labor",        "Labor costs (manodopera)"),
    ('EQUIPMENT',    "Equipment",    "Equipment rental costs (noli)"),
    ('MATERIAL',     "Material",     "Material costs (materiali)"),
    ('SAFETY',       "Safety",       "Safety costs (oneri sicurezza)"),
)

_TO_IFC = {
    'SUB_CONTRACT': 'Sub-Contract',
    'LABOR':        'Labor',
    'EQUIPMENT':    'Equipment',
    'MATERIAL':     'Material',
    'SAFETY':       'Safety',
}
_FROM_IFC = {v: k for k, v in _TO_IFC.items()}
_CATEGORY_WRITE_ORDER = ['SUB_CONTRACT', 'LABOR', 'EQUIPMENT', 'MATERIAL', 'SAFETY']

_LINE_CATEGORIES = set(_TO_IFC.values())

# ---------------------------------------------------------------------------
# Quantity (libretto delle misure) constants
# ---------------------------------------------------------------------------

_QTY_TYPES = (
    ('AREA',   "Area",   "IfcQuantityArea",   "AreaValue",   "m²"),
    ('VOLUME', "Volume", "IfcQuantityVolume",  "VolumeValue", "m³"),
    ('LENGTH', "Length", "IfcQuantityLength",  "LengthValue", "m"),
    ('COUNT',  "Count",  "IfcQuantityCount",   "CountValue",  ""),
    ('WEIGHT', "Weight", "IfcQuantityWeight",  "WeightValue", "kg"),
    ('TIME',   "Time",   "IfcQuantityTime",    "TimeValue",   "h"),
)
_QTY_IFC_CLASS  = {t[0]: t[2] for t in _QTY_TYPES}
_QTY_VALUE_ATTR = {t[0]: t[3] for t in _QTY_TYPES}
_QTY_UNIT_ABBR  = {t[0]: t[4] for t in _QTY_TYPES}
# reverse: IfcClassName → type_id
_QTY_FROM_IFC   = {t[2]: t[0] for t in _QTY_TYPES}
_OVERHEAD_CAT = "Overhead"
_PROFIT_CAT = "Profit"
_ROUNDING_CAT = "Rounding"
_ALL_PA_CATEGORIES = _LINE_CATEGORIES | {_OVERHEAD_CAT, _PROFIT_CAT, _ROUNDING_CAT}

_IFC_REF_RE = re.compile(r"#ifc:(\d+)")
_DESCRIPTION_TEXT_NAME = "Bonsai5D+_Description"


def _build_cv_ref(source_ifc_id, source_identification):
    """Build a human-readable Description for a CostValue that references a source item."""
    ident = source_identification or f"#{source_ifc_id}"
    return f"ref:[{ident}](#ifc:{source_ifc_id})"


def _parse_cv_source_id(cv):
    """Return source IFC step-ID from Description (new format) or Condition (legacy), or None."""
    for field in ("Description", "Condition"):
        val = getattr(cv, field, None) or ""
        m = _IFC_REF_RE.search(val)
        if m:
            return int(m.group(1))
    return None

# ---------------------------------------------------------------------------
# Text editor helpers
# ---------------------------------------------------------------------------

def _open_text_editor(context, text):
    # Reuse any existing text editor in any open window
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'TEXT_EDITOR':
                area.spaces.active.text = text
                area.spaces.active.show_word_wrap = True
                return
    # Open a new floating window and convert its largest area
    bpy.ops.wm.window_new()
    new_win = context.window_manager.windows[-1]
    target = max(new_win.screen.areas, key=lambda a: a.width * a.height, default=None)
    if target:
        target.type = 'TEXT_EDITOR'
        target.spaces.active.text = text
        target.spaces.active.show_word_wrap = True


def _close_text_editor(context):
    # Close a dedicated floating window that contains the text editor
    for window in list(context.window_manager.windows):
        if window == context.window:
            continue
        if any(a.type == 'TEXT_EDITOR' for a in window.screen.areas):
            with context.temp_override(window=window):
                bpy.ops.wm.window_close()
            return
    # Fallback: revert embedded text editor area back to 3D Viewport
    for area in context.screen.areas:
        if area.type == 'TEXT_EDITOR':
            area.type = 'VIEW_3D'
            return


def _remove_description_text():
    if _DESCRIPTION_TEXT_NAME in bpy.data.texts:
        bpy.data.texts.remove(bpy.data.texts[_DESCRIPTION_TEXT_NAME])


# ---------------------------------------------------------------------------
# IFC helpers
# ---------------------------------------------------------------------------

def _get_rate_current_value(file, source_ifc_id):
    try:
        rate_item = file.by_id(source_ifc_id)
        total = 0.0
        found = False
        for cv in (rate_item.CostValues or []):
            if cv.AppliedValue is not None:
                v = cv.AppliedValue
                total += float(v.wrappedValue if hasattr(v, "wrappedValue") else v)
                found = True
        return total if found else None
    except Exception:
        return None


def _get_totals(wm):
    ct = sum(c.qty * c.unit_price for c in wm.rate_analysis_components)
    sg = ct * wm.rate_analysis_overhead_pct / 100.0
    profit = (ct + sg) * wm.rate_analysis_profit_pct / 100.0
    return ct, sg, profit, ct + sg + profit + wm.rate_analysis_rounding


def _get_or_create_unit_entity(file, unit_str):
    for u in file.by_type("IfcContextDependentUnit"):
        if (u.Name or "") == unit_str:
            return u
    dims = file.create_entity(
        "IfcDimensionalExponents",
        LengthExponent=0, MassExponent=0, TimeExponent=0,
        ElectricCurrentExponent=0, ThermodynamicTemperatureExponent=0,
        AmountOfSubstanceExponent=0, LuminousIntensityExponent=0,
    )
    return file.create_entity(
        "IfcContextDependentUnit",
        Dimensions=dims,
        UnitType="USERDEFINED",
        Name=unit_str,
    )


def _set_unit_basis(file, cv, qty, unit_str):
    if not unit_str:
        return False
    try:
        unit_entity = _get_or_create_unit_entity(file, unit_str)
        unit_basis = file.create_entity(
            "IfcMeasureWithUnit",
            ValueComponent=qty,
            UnitComponent=unit_entity,
        )
        cv.UnitBasis = unit_basis
        return True
    except Exception:
        return False


def _read_unit_basis(cv):
    ub = getattr(cv, "UnitBasis", None)
    if ub is None:
        return None, None
    try:
        vc = ub.ValueComponent
        qty = float(vc.wrappedValue if hasattr(vc, "wrappedValue") else vc)
        unit_str = str(getattr(ub.UnitComponent, "Name", None) or "")
        return qty, unit_str
    except Exception:
        return None, None


def _pct_label(label, pct):
    return f"{label} {pct:.1f}%"


def _parse_pct(name):
    m = re.search(r"(\d+(?:\.\d+)?)\s*%", name or "")
    return float(m.group(1)) if m else None


def _remove_analysis_values(tool, cost_item):
    for cv in list(cost_item.CostValues or []):
        tool.Ifc.run("cost.remove_cost_value", parent=cost_item, cost_value=cv)


def _get_cost_schedule(cost_item):
    for rel in (cost_item.HasAssignments or []):
        if rel.is_a("IfcRelAssignsToControl") and rel.RelatingControl.is_a("IfcCostSchedule"):
            return rel.RelatingControl
    for rel in (cost_item.Nests or []):
        return _get_cost_schedule(rel.RelatingObject)
    return None


def _get_cost_item_controller(cost_item):
    for rel in (cost_item.HasAssignments or []):
        if rel.is_a("IfcRelAssignsToControl"):
            ctrl = rel.RelatingControl
            if ctrl.is_a("IfcCostItem"):
                return ctrl
    return None


def _read_cost_item_info(context):
    try:
        from bonsai import tool
        file = tool.Ifc.get()
        wm = context.window_manager
        target_id = wm.rate_analysis_target_ifc_id
        if target_id:
            cost_item = file.by_id(target_id)
        else:
            cost_item = file.by_id(context.scene.BIMCostProperties.active_cost_item.ifc_definition_id)
        wm.rate_analysis_item_identification = cost_item.Identification or ""
        wm.rate_analysis_item_name = cost_item.Name or ""
        wm.rate_analysis_item_description = cost_item.Description or ""
    except Exception:
        pass


def _write_cost_item_info(tool, cost_item, wm):
    tool.Ifc.run("cost.edit_cost_item", cost_item=cost_item, attributes={
        "Identification": wm.rate_analysis_item_identification or None,
        "Name": wm.rate_analysis_item_name or None,
        "Description": wm.rate_analysis_item_description or None,
    })


def _compute_partial_qty(nr, l, b, h):
    """Product of non-zero fields; returns 0 if all fields are zero."""
    result = 1.0
    used = False
    for v in (nr, l, b, h):
        if v != 0.0:
            result *= v
            used = True
    return result if used else 0.0


def _build_formula_qty(nr, l, b, h):
    """Build 'NR × L × B × H' string from non-zero fields."""
    parts = []
    for v in (nr, l, b, h):
        if v != 0.0:
            parts.append(f"{v:g}")
    return " × ".join(parts)


def _parse_formula_qty(formula_str):
    """Parse 'NR × L × B × H' → (nr, l, b, h); missing/unparseable fields → 0.0."""
    if not formula_str:
        return 0.0, 0.0, 0.0, 0.0
    parts = [p.strip() for p in formula_str.split("×") if p.strip()]
    vals = []
    for p in parts[:4]:
        try:
            vals.append(float(p.replace(",", ".")))
        except ValueError:
            vals.append(0.0)
    while len(vals) < 4:
        vals.append(0.0)
    return vals[0], vals[1], vals[2], vals[3]


def _load_quantities(context, cost_item=None):
    """Populate cost_quantities collection from cost_item.CostQuantities."""
    wm = context.window_manager
    wm.cost_quantities.clear()
    wm.cost_quantities_active_index = 0
    if cost_item is None:
        try:
            from bonsai import tool
            file = tool.Ifc.get()
            target_id = wm.rate_analysis_target_ifc_id
            if target_id:
                cost_item = file.by_id(target_id)
            else:
                cost_item = file.by_id(
                    context.scene.BIMCostProperties.active_cost_item.ifc_definition_id
                )
        except Exception:
            return
    type_detected = False
    for q in (cost_item.CostQuantities or []):
        row = wm.cost_quantities.add()
        row.qty_desc = q.Name or ""
        row.ifc_id = q.id()
        ifc_type = q.is_a()
        type_id = _QTY_FROM_IFC.get(ifc_type, 'COUNT')
        if not type_detected:
            wm.cost_quantities_type = type_id
            type_detected = True
        val_attr = _QTY_VALUE_ATTR.get(type_id, "CountValue")
        stored_value = float(getattr(q, val_attr, 0.0) or 0.0)
        # Formula is the correct IFC4 attribute; fall back to Description for files
        # imported before this fix (XPWE importer used to write formula to Description)
        formula = getattr(q, "Formula", None) or q.Description or ""
        nr, l, b, h = _parse_formula_qty(formula)
        # Validate: recomputed partial must match stored value (within tolerance)
        recomputed = _compute_partial_qty(nr, l, b, h)
        if formula and abs(recomputed - stored_value) < max(abs(stored_value) * 0.001, 0.0001):
            row.qty_nr, row.qty_l, row.qty_b, row.qty_h = nr, l, b, h
        else:
            # Formula unreadable — put stored value in NR, leave others at 0
            row.qty_nr = stored_value


def _load_cost_item(context, item_id=None):
    from bonsai import tool

    file = tool.Ifc.get()
    if item_id is None:
        item_id = context.scene.BIMCostProperties.active_cost_item.ifc_definition_id
    cost_item = file.by_id(item_id)
    wm = context.window_manager

    wm.rate_analysis_components.clear()
    wm.rate_analysis_active_index = 0
    wm.rate_analysis_overhead_pct = 0.0
    wm.rate_analysis_profit_pct = 0.0
    wm.rate_analysis_rounding = 0.0
    wm.rate_analysis_target_ifc_id = cost_item.id()
    _read_cost_item_info(context)

    found = False

    for cv in (cost_item.CostValues or []):
        cat = cv.Category or ""

        if cat in _LINE_CATEGORIES or cat not in _ALL_PA_CATEGORIES:
            found = True
            comp = wm.rate_analysis_components.add()
            comp.category = _FROM_IFC.get(cat, 'NONE')
            comp.description = cv.Name or ""

            v = cv.AppliedValue
            line_total = float(v.wrappedValue if hasattr(v, "wrappedValue") else v) if v is not None else 0.0

            qty, unit_str = _read_unit_basis(cv)
            if qty is not None:
                comp.qty = qty
                comp.unit = unit_str or ""
                comp.unit_price = round(line_total / qty, 6) if qty else line_total
            else:
                comp.unit_price = line_total

            src_id = _parse_cv_source_id(cv)
            if src_id is not None:
                try:
                    comp.source_ifc_id = src_id
                    comp.source_identification = file.by_id(src_id).Identification or ""
                except Exception:
                    pass

            if comp.source_ifc_id:
                current = _get_rate_current_value(file, comp.source_ifc_id)
                if current is not None and round(current, 2) != round(comp.unit_price, 2):
                    comp.needs_rate_update = True

        elif cat == _OVERHEAD_CAT:
            found = True
            pct = _parse_pct(cv.Name)
            if pct is not None:
                wm.rate_analysis_overhead_pct = pct

        elif cat == _PROFIT_CAT:
            found = True
            pct = _parse_pct(cv.Name)
            if pct is not None:
                wm.rate_analysis_profit_pct = pct

        elif cat == _ROUNDING_CAT:
            found = True
            v = cv.AppliedValue
            if v is not None:
                wm.rate_analysis_rounding = float(
                    v.wrappedValue if hasattr(v, "wrappedValue") else v
                )

    _load_quantities(context, cost_item)
    return found


_handler_last_check = 0.0


@bpy.app.handlers.persistent
def _auto_load_handler(scene, depsgraph):
    global _handler_last_check
    t = _time.monotonic()
    if t - _handler_last_check < 0.1:
        return
    _handler_last_check = t
    try:
        wm = bpy.context.window_manager
        if not wm.rate_analysis_auto_load:
            return
        props = bpy.context.scene.BIMCostProperties
        if props.active_cost_item is None or props.active_cost_schedule_id == 0:
            return
        item_id = props.active_cost_item.ifc_definition_id
        if item_id == wm.rate_analysis_target_ifc_id:
            return
        _load_cost_item(bpy.context)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------

class RA_OT_AddComponent(bpy.types.Operator):
    bl_idname = "rate_analysis.add_component"
    bl_label = "Add Free-form Component"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        wm = context.window_manager
        wm.rate_analysis_components.add()
        wm.rate_analysis_active_index = len(wm.rate_analysis_components) - 1
        return {'FINISHED'}


class RA_OT_AddFromRate(bpy.types.Operator):
    bl_idname = "rate_analysis.add_from_rate"
    bl_label = "Add Component from Active Cost Item"
    bl_description = (
        "Add the currently selected cost item in the BIM Cost panel as a component. "
        "First use Load to pin the item being analysed, then browse to a rate and click this."
    )
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        try:
            props = context.scene.BIMCostProperties
            if props.active_cost_item is None or props.active_cost_schedule_id == 0:
                return False
            target = context.window_manager.rate_analysis_target_ifc_id
            return target == 0 or props.active_cost_item.ifc_definition_id != target
        except Exception:
            return False

    def execute(self, context):
        from bonsai import tool
        wm = context.window_manager
        props = context.scene.BIMCostProperties
        file = tool.Ifc.get()
        rate_item = file.by_id(props.active_cost_item.ifc_definition_id)

        comp = wm.rate_analysis_components.add()
        comp.description = rate_item.Name or ""
        comp.qty = 1.0
        comp.category = 'SUB_CONTRACT'
        comp.source_ifc_id = rate_item.id()
        comp.source_identification = rate_item.Identification or ""
        comp.unit_price = _get_rate_current_value(file, rate_item.id()) or 0.0

        wm.rate_analysis_active_index = len(wm.rate_analysis_components) - 1
        return {'FINISHED'}


class RA_OT_RemoveComponent(bpy.types.Operator):
    bl_idname = "rate_analysis.remove_component"
    bl_label = "Remove Component"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        wm = context.window_manager
        comps = wm.rate_analysis_components
        idx = wm.rate_analysis_active_index
        if 0 <= idx < len(comps):
            comps.remove(idx)
            wm.rate_analysis_active_index = max(0, idx - 1)
        return {'FINISHED'}


class RA_OT_MoveUp(bpy.types.Operator):
    bl_idname = "rate_analysis.move_up"
    bl_label = "Move Up"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        wm = context.window_manager
        comps = wm.rate_analysis_components
        idx = wm.rate_analysis_active_index
        if idx > 0:
            comps.move(idx, idx - 1)
            wm.rate_analysis_active_index = idx - 1
        return {'FINISHED'}


class RA_OT_MoveDown(bpy.types.Operator):
    bl_idname = "rate_analysis.move_down"
    bl_label = "Move Down"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        wm = context.window_manager
        comps = wm.rate_analysis_components
        idx = wm.rate_analysis_active_index
        if idx < len(comps) - 1:
            comps.move(idx, idx + 1)
            wm.rate_analysis_active_index = idx + 1
        return {'FINISHED'}


class RA_OT_ClearAll(bpy.types.Operator):
    bl_idname = "rate_analysis.clear_all"
    bl_label = "Clear Analysis"
    bl_description = "Clear all components and reset percentages"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        wm = context.window_manager
        wm.rate_analysis_components.clear()
        wm.rate_analysis_active_index = 0
        wm.rate_analysis_overhead_pct = 0.0
        wm.rate_analysis_profit_pct = 0.0
        wm.rate_analysis_rounding = 0.0
        return {'FINISHED'}


class RA_OT_RefreshComponentRate(bpy.types.Operator):
    bl_idname = "rate_analysis.refresh_component_rate"
    bl_label = "Update rate value"
    bl_description = "The linked rate value has changed — click to reload the current value"
    bl_options = {'REGISTER', 'UNDO'}

    component_index: bpy.props.IntProperty(options={'SKIP_SAVE'})

    def execute(self, context):
        from bonsai import tool
        wm = context.window_manager
        comps = wm.rate_analysis_components
        if not (0 <= self.component_index < len(comps)):
            return {'CANCELLED'}
        comp = comps[self.component_index]
        if not comp.source_ifc_id:
            return {'CANCELLED'}
        file = tool.Ifc.get()
        current = _get_rate_current_value(file, comp.source_ifc_id)
        if current is not None:
            comp.unit_price = current
        try:
            comp.source_identification = file.by_id(comp.source_ifc_id).Identification or ""
        except Exception:
            pass
        comp.needs_rate_update = False
        return {'FINISHED'}


class RA_OT_EditDescription(bpy.types.Operator):
    bl_idname = "rate_analysis.edit_description"
    bl_label = "Edit Description"
    bl_description = "Open Text Editor to edit the item description"

    def execute(self, context):
        wm = context.window_manager
        _remove_description_text()
        text = bpy.data.texts.new(_DESCRIPTION_TEXT_NAME)
        text.write(wm.rate_analysis_item_description)
        text.cursor_set(0, character=0)
        _open_text_editor(context, text)
        wm.rate_analysis_editing_description = True
        return {'FINISHED'}


class RA_OT_ApplyDescription(bpy.types.Operator):
    bl_idname = "rate_analysis.apply_description"
    bl_label = "Apply"
    bl_description = "Write the text back to the description and close the editor"

    def execute(self, context):
        wm = context.window_manager
        if _DESCRIPTION_TEXT_NAME in bpy.data.texts:
            wm.rate_analysis_item_description = bpy.data.texts[_DESCRIPTION_TEXT_NAME].as_string()
            self.report({'INFO'}, "Description applied")
        _remove_description_text()
        _close_text_editor(context)
        wm.rate_analysis_editing_description = False
        return {'FINISHED'}


class RA_OT_CancelDescription(bpy.types.Operator):
    bl_idname = "rate_analysis.cancel_description"
    bl_label = "Cancel"
    bl_description = "Discard changes and close the editor"

    def execute(self, context):
        _remove_description_text()
        _close_text_editor(context)
        context.window_manager.rate_analysis_editing_description = False
        return {'FINISHED'}


class RA_OT_SyncItemInfo(*_IfcOperatorBase):
    """Re-read Identification, Name and Description from the active (or pinned) cost item."""
    bl_idname = "rate_analysis.sync_item_info"
    bl_label = "Load identification from IFC"

    @classmethod
    def poll(cls, context):
        if context.window_manager.rate_analysis_target_ifc_id != 0:
            return True
        try:
            props = context.scene.BIMCostProperties
            return props.active_cost_item is not None and props.active_cost_schedule_id != 0
        except Exception:
            return False

    def _execute(self, context):
        wm = context.window_manager
        if wm.rate_analysis_target_ifc_id == 0:
            from bonsai import tool
            file = tool.Ifc.get()
            cost_item = file.by_id(
                context.scene.BIMCostProperties.active_cost_item.ifc_definition_id
            )
            wm.rate_analysis_target_ifc_id = cost_item.id()
        _read_cost_item_info(context)


class RA_OT_ApplyItemInfo(*_IfcOperatorBase):
    """Write Identification, Name and Description to the pinned target item."""
    bl_idname = "rate_analysis.apply_item_info"
    bl_label = "Write info to IFC"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.window_manager.rate_analysis_target_ifc_id != 0

    def _execute(self, context):
        from bonsai import tool
        import bonsai.bim.module.cost.data
        file = tool.Ifc.get()
        wm = context.window_manager
        cost_item = file.by_id(wm.rate_analysis_target_ifc_id)
        _write_cost_item_info(tool, cost_item, wm)
        bonsai.bim.module.cost.data.refresh()
        tool.Cost.load_cost_schedule_tree()


class RA_OT_ApplyToIfc(*_IfcOperatorBase):
    """Write the rate analysis to the active IFC cost item."""
    bl_idname = "rate_analysis.apply_to_ifc"
    bl_label = "Apply Rate Analysis to IFC"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.window_manager.rate_analysis_target_ifc_id != 0

    def _execute(self, context):
        from bonsai import tool
        import bonsai.bim.module.cost.data

        wm = context.window_manager
        file = tool.Ifc.get()
        cost_item = file.by_id(wm.rate_analysis_target_ifc_id)

        _write_cost_item_info(tool, cost_item, wm)
        _remove_analysis_values(tool, cost_item)
        ct, sg, profit, final = _get_totals(wm)

        ordered = sorted(
            wm.rate_analysis_components,
            key=lambda c: _CATEGORY_WRITE_ORDER.index(c.category)
            if c.category in _CATEGORY_WRITE_ORDER else len(_CATEGORY_WRITE_ORDER),
        )
        for comp in ordered:
            line_total = round(comp.qty * comp.unit_price, 2)
            cv = tool.Ifc.run("cost.add_cost_value", parent=cost_item)
            tool.Ifc.run("cost.edit_cost_value", cost_value=cv, attributes={
                "Name": comp.description,
                "Category": _TO_IFC.get(comp.category),
                "AppliedValue": line_total,
            })
            _set_unit_basis(file, cv, comp.qty, comp.unit)
            if comp.source_ifc_id:
                cv.Description = _build_cv_ref(comp.source_ifc_id, comp.source_identification)

        cv_sg = tool.Ifc.run("cost.add_cost_value", parent=cost_item)
        tool.Ifc.run("cost.edit_cost_value", cost_value=cv_sg, attributes={
            "Name": _pct_label("Overhead", wm.rate_analysis_overhead_pct),
            "Category": _OVERHEAD_CAT,
            "AppliedValue": round(sg, 2),
        })

        cv_profit = tool.Ifc.run("cost.add_cost_value", parent=cost_item)
        tool.Ifc.run("cost.edit_cost_value", cost_value=cv_profit, attributes={
            "Name": _pct_label("Profit", wm.rate_analysis_profit_pct),
            "Category": _PROFIT_CAT,
            "AppliedValue": round(profit, 2),
        })

        if wm.rate_analysis_rounding != 0.0:
            cv_r = tool.Ifc.run("cost.add_cost_value", parent=cost_item)
            tool.Ifc.run("cost.edit_cost_value", cost_value=cv_r, attributes={
                "Name": "Rounding",
                "Category": _ROUNDING_CAT,
                "AppliedValue": round(wm.rate_analysis_rounding, 2),
            })

        bonsai.bim.module.cost.data.refresh()
        tool.Cost.load_cost_schedule_tree()


def _find_parent_and_index(file, props):
    """Return (parent_cost_item_or_None, active_index_in_parent_or_None)."""
    try:
        active_id = props.active_cost_item.ifc_definition_id
        if not active_id:
            return None, None
        active = file.by_id(active_id)
        for rel in (active.Nests or []):
            obj = rel.RelatingObject
            if obj.is_a("IfcCostItem"):
                for r in (obj.IsNestedBy or []):
                    siblings = list(r.RelatedObjects)
                    if active in siblings:
                        return obj, siblings.index(active)
                return obj, None
    except Exception:
        pass
    return None, None


def _reorder_after_add(parent_item, new_item, insert_index):
    """Move new_item to insert_index within its parent's RelatedObjects list."""
    if parent_item is None or insert_index is None:
        return
    for r in (parent_item.IsNestedBy or []):
        siblings = list(r.RelatedObjects)
        if new_item in siblings:
            siblings.remove(new_item)
            siblings.insert(max(0, insert_index), new_item)
            r.RelatedObjects = siblings
            return


def _select_and_load(context, ifc_id):
    """Select new item in Bonsai's cost tree and load it in the editor."""
    try:
        props = context.scene.BIMCostProperties
        for i, item in enumerate(props.cost_items):
            if getattr(item, 'ifc_definition_id', None) == ifc_id:
                props.active_cost_item_index = i
                break
    except Exception:
        pass
    _load_cost_item(context, ifc_id)


class RA_OT_AddSummaryCost(*_IfcOperatorBase):
    bl_idname = "rate_analysis.add_summary_cost"
    bl_label = "Add Summary Cost"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context, properties):
        return (
            "Add a summary cost item (Category='*', sums child values) "
            "at the same level as the active one. "
            "If no item is active, adds at the root of the schedule."
        )

    @classmethod
    def poll(cls, context):
        try:
            return context.scene.BIMCostProperties.active_cost_schedule_id != 0
        except Exception:
            return False

    def _execute(self, context):
        from bonsai import tool
        import bonsai.bim.module.cost.data

        file = tool.Ifc.get()
        props = context.scene.BIMCostProperties
        schedule = file.by_id(int(props.active_cost_schedule_id))

        # Find where to insert: sibling of active item, or root if none active
        parent_item = None
        try:
            active_id = props.active_cost_item.ifc_definition_id
            if active_id:
                active = file.by_id(active_id)
                for rel in (active.Nests or []):
                    obj = rel.RelatingObject
                    if obj.is_a("IfcCostItem"):
                        parent_item = obj
                    break
        except Exception:
            pass

        if parent_item:
            new_item = tool.Ifc.run("cost.add_cost_item", cost_item=parent_item)
        else:
            new_item = tool.Ifc.run("cost.add_cost_item", cost_schedule=schedule)

        cv = tool.Ifc.run("cost.add_cost_value", parent=new_item)
        tool.Ifc.run("cost.edit_cost_value", cost_value=cv, attributes={"Category": "*"})

        bonsai.bim.module.cost.data.refresh()
        tool.Cost.load_cost_schedule_tree()
        _select_and_load(context, new_item.id())


class RA_OT_AddCostItem(*_IfcOperatorBase):
    """Add a plain cost item relative to the active one."""
    bl_idname = "rate_analysis.add_cost_item"
    bl_label = "Add Cost Item"
    bl_options = {'REGISTER', 'UNDO'}

    position: bpy.props.EnumProperty(
        items=[
            ('BEFORE', "Before",         "Insert a new cost item before the active one (same level)"),
            ('AFTER',  "After",          "Insert a new cost item after the active one (same level)"),
            ('CHILD',  "As child",       "Insert a new cost item as a child of the active one"),
        ],
        default='AFTER',
        options={'SKIP_SAVE'},
    )

    @classmethod
    def description(cls, context, properties):
        return {
            'BEFORE': "Insert a new cost item before the active one (same level)",
            'AFTER':  "Insert a new cost item after the active one (same level)",
            'CHILD':  "Insert a new cost item as a child of the active one",
        }.get(properties.position, "Add cost item")

    @classmethod
    def poll(cls, context):
        try:
            return context.scene.BIMCostProperties.active_cost_schedule_id != 0
        except Exception:
            return False

    def _execute(self, context):
        from bonsai import tool
        import bonsai.bim.module.cost.data

        file = tool.Ifc.get()
        props = context.scene.BIMCostProperties
        schedule = file.by_id(int(props.active_cost_schedule_id))

        if self.position == 'CHILD':
            try:
                active_id = props.active_cost_item.ifc_definition_id
                active = file.by_id(active_id) if active_id else None
            except Exception:
                active = None
            if active:
                new_item = tool.Ifc.run("cost.add_cost_item", cost_item=active)
            else:
                new_item = tool.Ifc.run("cost.add_cost_item", cost_schedule=schedule)
        else:
            parent_item, active_index = _find_parent_and_index(file, props)
            if parent_item:
                new_item = tool.Ifc.run("cost.add_cost_item", cost_item=parent_item)
                insert_index = active_index if self.position == 'BEFORE' else active_index + 1
                _reorder_after_add(parent_item, new_item, insert_index)
            else:
                new_item = tool.Ifc.run("cost.add_cost_item", cost_schedule=schedule)

        bonsai.bim.module.cost.data.refresh()
        tool.Cost.load_cost_schedule_tree()
        _select_and_load(context, new_item.id())


class RA_OT_LoadFromIfc(*_IfcOperatorBase):
    """Load rate analysis from the active IFC cost item."""
    bl_idname = "rate_analysis.load_from_ifc"
    bl_label = "Load Rate Analysis from IFC"

    @classmethod
    def poll(cls, context):
        try:
            props = context.scene.BIMCostProperties
            return props.active_cost_item is not None and props.active_cost_schedule_id != 0
        except Exception:
            return False

    def _execute(self, context):
        if not _load_cost_item(context):
            self.report({'WARNING'}, "No price analysis data found on this cost item.")


class RA_OT_LoadController(*_IfcOperatorBase):
    """Load the cost item that controls the current one."""
    bl_idname = "rate_analysis.load_controller"
    bl_label = "Load Controlling Item"

    @classmethod
    def poll(cls, context):
        wm = context.window_manager
        if wm.rate_analysis_target_ifc_id == 0:
            return False
        try:
            from bonsai import tool
            file = tool.Ifc.get()
            if not file:
                return False
            cost_item = file.by_id(wm.rate_analysis_target_ifc_id)
            return _get_cost_item_controller(cost_item) is not None
        except Exception:
            return False

    def _execute(self, context):
        from bonsai import tool
        file = tool.Ifc.get()
        wm = context.window_manager
        cost_item = file.by_id(wm.rate_analysis_target_ifc_id)
        controller = _get_cost_item_controller(cost_item)
        if controller:
            _load_cost_item(context, item_id=controller.id())


class QTY_OT_AddRow(bpy.types.Operator):
    bl_idname = "cost_quantities.add_row"
    bl_label = "Add Measurement Row"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        wm = context.window_manager
        row = wm.cost_quantities.add()
        row.qty_nr = 1.0
        wm.cost_quantities_active_index = len(wm.cost_quantities) - 1
        return {'FINISHED'}


class QTY_OT_RemoveRow(bpy.types.Operator):
    bl_idname = "cost_quantities.remove_row"
    bl_label = "Remove Measurement Row"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        wm = context.window_manager
        items = wm.cost_quantities
        idx = wm.cost_quantities_active_index
        if 0 <= idx < len(items):
            items.remove(idx)
            wm.cost_quantities_active_index = max(0, idx - 1)
        return {'FINISHED'}


class QTY_OT_MoveRowUp(bpy.types.Operator):
    bl_idname = "cost_quantities.move_row_up"
    bl_label = "Move Row Up"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        wm = context.window_manager
        items = wm.cost_quantities
        idx = wm.cost_quantities_active_index
        if idx > 0:
            items.move(idx, idx - 1)
            wm.cost_quantities_active_index = idx - 1
        return {'FINISHED'}


class QTY_OT_MoveRowDown(bpy.types.Operator):
    bl_idname = "cost_quantities.move_row_down"
    bl_label = "Move Row Down"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        wm = context.window_manager
        items = wm.cost_quantities
        idx = wm.cost_quantities_active_index
        if idx < len(items) - 1:
            items.move(idx, idx + 1)
            wm.cost_quantities_active_index = idx + 1
        return {'FINISHED'}


class QTY_OT_InsertRowAfter(bpy.types.Operator):
    bl_idname = "cost_quantities.insert_row_after"
    bl_label = "Insert Row Below"
    bl_options = {'REGISTER', 'UNDO'}

    index: bpy.props.IntProperty(options={'SKIP_SAVE'})

    def execute(self, context):
        wm = context.window_manager
        items = wm.cost_quantities
        items.add().qty_nr = 1.0
        new_idx = len(items) - 1
        target = self.index + 1
        if target < new_idx:
            items.move(new_idx, target)
        wm.cost_quantities_active_index = target
        return {'FINISHED'}


class QTY_OT_Load(*_IfcOperatorBase):
    """Load quantities from the pinned IFC cost item."""
    bl_idname = "cost_quantities.load"
    bl_label = "Load Quantities from IFC"

    @classmethod
    def poll(cls, context):
        wm = context.window_manager
        if wm.rate_analysis_target_ifc_id != 0:
            return True
        try:
            props = context.scene.BIMCostProperties
            return props.active_cost_item is not None and props.active_cost_schedule_id != 0
        except Exception:
            return False

    def _execute(self, context):
        _load_quantities(context)


class QTY_OT_Apply(*_IfcOperatorBase):
    """Write measurement rows to the pinned IFC cost item as CostQuantities."""
    bl_idname = "cost_quantities.apply"
    bl_label = "Apply Quantities to IFC"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.window_manager.rate_analysis_target_ifc_id != 0

    def _execute(self, context):
        from bonsai import tool
        import bonsai.bim.module.cost.data
        file = tool.Ifc.get()
        wm = context.window_manager
        cost_item = file.by_id(wm.rate_analysis_target_ifc_id)

        for q in list(cost_item.CostQuantities or []):
            file.remove(q)

        ifc_class = _QTY_IFC_CLASS[wm.cost_quantities_type]
        val_attr = _QTY_VALUE_ATTR[wm.cost_quantities_type]
        new_quantities = []
        for row in wm.cost_quantities:
            partial = _compute_partial_qty(row.qty_nr, row.qty_l, row.qty_b, row.qty_h)
            kw = {
                "Name": row.qty_desc or None,
                val_attr: round(partial, 6),
            }
            formula = _build_formula_qty(row.qty_nr, row.qty_l, row.qty_b, row.qty_h)
            if formula:
                kw["Formula"] = formula
            new_quantities.append(file.create_entity(ifc_class, **kw))

        cost_item.CostQuantities = new_quantities
        bonsai.bim.module.cost.data.refresh()
        tool.Cost.load_cost_schedule_tree()


classes = [
    RA_OT_AddComponent,
    RA_OT_AddFromRate,
    RA_OT_RemoveComponent,
    RA_OT_MoveUp,
    RA_OT_MoveDown,
    RA_OT_ClearAll,
    RA_OT_RefreshComponentRate,
    RA_OT_EditDescription,
    RA_OT_ApplyDescription,
    RA_OT_CancelDescription,
    RA_OT_SyncItemInfo,
    RA_OT_ApplyItemInfo,
    RA_OT_ApplyToIfc,
    RA_OT_AddSummaryCost,
    RA_OT_AddCostItem,
    RA_OT_LoadFromIfc,
    RA_OT_LoadController,
    QTY_OT_AddRow,
    QTY_OT_RemoveRow,
    QTY_OT_MoveRowUp,
    QTY_OT_MoveRowDown,
    QTY_OT_InsertRowAfter,
    QTY_OT_Load,
    QTY_OT_Apply,
]
