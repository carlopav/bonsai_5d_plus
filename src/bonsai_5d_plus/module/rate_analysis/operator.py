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
_OVERHEAD_CAT = "Overhead"
_PROFIT_CAT = "Profit"
_ROUNDING_CAT = "Rounding"
_ALL_PA_CATEGORIES = _LINE_CATEGORIES | {_OVERHEAD_CAT, _PROFIT_CAT, _ROUNDING_CAT}

_IFC_REF_PREFIX = "#ifc:"
_DESCRIPTION_TEXT_NAME = "Bonsai5D+_Description"

# ---------------------------------------------------------------------------
# Text editor helpers
# ---------------------------------------------------------------------------

def _open_text_editor(context, text):
    for area in context.screen.areas:
        if area.type == 'TEXT_EDITOR':
            area.spaces.active.text = text
            area.spaces.active.show_word_wrap = True
            return
    area_target = max(
        (a for a in context.screen.areas if a.type not in ('PROPERTIES', 'TEXT_EDITOR')),
        key=lambda a: a.width * a.height,
        default=None,
    )
    if area_target:
        area_target.type = 'TEXT_EDITOR'
        area_target.spaces.active.text = text
        area_target.spaces.active.show_word_wrap = True


def _close_text_editor(context):
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

            cond = getattr(cv, "Condition", None) or ""
            if cond.startswith(_IFC_REF_PREFIX):
                try:
                    comp.source_ifc_id = int(cond[len(_IFC_REF_PREFIX):])
                    src = file.by_id(comp.source_ifc_id)
                    comp.source_identification = src.Identification or ""
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
                cv.Condition = f"{_IFC_REF_PREFIX}{comp.source_ifc_id}"

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
    RA_OT_LoadFromIfc,
    RA_OT_LoadController,
]
